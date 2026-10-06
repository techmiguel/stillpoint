"""Rev A, paso 4: vías de GND (fan-out de cada pad y cosido de planos) validadas por DRC.

  python3 hardware/scripts/revA_4_gnd.py

Cada vía candidata se coloca, se pasa la DRC de KiCad (kicad-cli) y, si
participa en cualquier violación, se retira y se prueba la siguiente posición.
También quita las vías de señal que el autorutado dejó conectadas en una sola capa.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

PCB = Path(__file__).resolve().parents[1] / "radar60.kicad_pcb"
mm = pcbnew.FromMM
BAD = {"clearance", "hole_clearance", "hole_to_hole", "shorting_items", "tracks_crossing",
       "copper_edge_clearance", "items_not_allowed", "solder_mask_bridge", "via_dangling",
       "drill_out_of_range", "annular_width", "track_dangling", "courtyards_overlap"}
RADAR = (95.5, 95.5, 104.5, 104.5)     # sin cosido bajo el radar y su fan-out (ya tiene sus vías)


def drc() -> dict:
    out = Path(tempfile.mkdtemp()) / "drc.json"
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--refill-zones", "-o", str(out), str(PCB)],
                   capture_output=True, check=False)
    return json.loads(out.read_text())


def offenders(rep) -> set[str]:
    bad = set()
    for v in rep.get("violations", []):
        if v["type"] in BAD:
            for it in v.get("items", []):
                bad.add(it["uuid"])
    return bad


def set_zone_connections(b):
    for i in range(b.GetAreaCount()):
        z = b.GetArea(i)
        if not z.GetIsRuleArea():
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)


def courtyards(b):
    boxes = []
    for fp in b.GetFootprints():
        for side in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            c = fp.GetCourtyard(side)
            if c.OutlineCount():
                bb = c.BBox()
                boxes.append((pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
                              pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())))
    return boxes


def inside(x, y, box, m=0.0):
    return box[0] - m <= x <= box[2] + m and box[1] - m <= y <= box[3] + m


def add_via(b, net, x, y):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    v.SetWidth(mm(0.5))
    v.SetDrill(mm(0.25))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(net)
    b.Add(v)
    return v.m_Uuid.AsString()


def add_track(b, net, a, c, layer):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1])))
    t.SetEnd(pcbnew.VECTOR2I(mm(c[0]), mm(c[1])))
    t.SetWidth(mm(0.25))
    t.SetLayer(layer)
    t.SetNet(net)
    b.Add(t)
    return t.m_Uuid.AsString()


def remove_uuids(b, uuids):
    uu = set(uuids)
    for t in list(b.GetTracks()):
        if t.m_Uuid.AsString() in uu:
            b.Remove(t)


# ---- operaciones (cada una en su propio proceso: pcbnew admite un solo LoadBoard por proceso)

def op_prepare(st):
    """Zonas con conexión sólida, quita vías de señal colgantes, calcula candidatas de fan-out."""
    b = pcbnew.LoadBoard(str(PCB))
    set_zone_connections(b)
    dead = set(st.get("dangling", []))
    kill = [t for t in b.GetTracks()
            if t.GetClass() == "PCB_VIA" and t.m_Uuid.AsString() in dead and t.GetNetname() != "/GND"]
    todo = []
    for fp in b.GetFootprints():
        if fp.GetReference() == "U1":
            continue
        for p in fp.Pads():
            if p.GetNetname() != "/GND" or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            c = p.GetPosition()
            x, y = pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)
            bb = p.GetBoundingBox()
            w, h = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
            layer = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
            if w > 2.0 and h > 2.0:          # pad expuesto (QFN): vías en el pad
                for dx in (-0.6, 0.6):
                    for dy in (-0.6, 0.6):
                        todo.append({"pad": None, "layer": layer, "cands": [(x + dx, y + dy)], "i": 0})
                continue
            cands = []
            for d in (0.0, 0.25, 0.5):
                for k in range(8):
                    a = math.pi / 4 * k
                    r = math.hypot(w / 2 * abs(math.cos(a)), h / 2 * abs(math.sin(a))) + 0.45 + d
                    cands.append((x + r * math.cos(a), y + r * math.sin(a)))
            todo.append({"pad": (x, y), "layer": layer, "cands": cands, "i": 0})
    st["todo"] = todo
    for t in kill:                       # al final: tras Remove() la capa SWIG deja de ser fiable
        b.Remove(t)
    b.Save(str(PCB))


def op_fan_place(st):
    b = pcbnew.LoadBoard(str(PCB))
    gnd = b.FindNet("/GND")
    st["placed"] = []
    for k, t in enumerate(st["todo"]):
        if t.get("ok") or t["i"] >= len(t["cands"]):
            continue
        x, y = t["cands"][t["i"]]
        u = [add_via(b, gnd, x, y)]
        if t["pad"]:
            u.append(add_track(b, gnd, t["pad"], (x, y), t["layer"]))
        t["uuids"] = u
        st["placed"].append(k)
    b.Save(str(PCB))


def op_fan_check(st):
    bad = set(st["bad"])
    b = pcbnew.LoadBoard(str(PCB))
    rm = []
    for k in st["placed"]:
        t = st["todo"][k]
        if any(u in bad for u in t["uuids"]):
            rm += t["uuids"]
            t["i"] += 1
        else:
            t["ok"] = True
    remove_uuids(b, rm)
    b.Save(str(PCB))
    st["n_bad"] = len(rm)


def op_stitch_place(st, pitch=1.6, r_max=28.6):
    b = pcbnew.LoadBoard(str(PCB))
    gnd = b.FindNet("/GND")
    boxes = courtyards(b)
    mine = []
    n = int(r_max / pitch) + 1
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x = 100 + i * pitch + (pitch / 2 if j % 2 else 0)
            y = 100 + j * pitch * 0.866
            if math.hypot(x - 100, y - 100) > r_max or inside(x, y, RADAR):
                continue
            if any(inside(x, y, bx, 0.3) for bx in boxes):
                continue
            mine.append(add_via(b, gnd, x, y))
    st["stitch"] = mine
    b.Save(str(PCB))


def op_stitch_check(st):
    bad = set(st["bad"]) & set(st["stitch"])
    b = pcbnew.LoadBoard(str(PCB))
    remove_uuids(b, bad)
    b.Save(str(PCB))
    st["stitch"] = [u for u in st["stitch"] if u not in bad]
    st["n_bad"] = len(bad)


# ---- orquestación

STATE = Path(tempfile.gettempdir()) / "radar60_gnd_state.json"


def run(op, st):
    STATE.write_text(json.dumps(st))
    subprocess.run([sys.executable, __file__, op], check=True)
    return json.loads(STATE.read_text())


def main():
    rep = drc()
    st = {"dangling": [it["uuid"] for v in rep["violations"] if v["type"] == "via_dangling" for it in v["items"]]}
    st = run("prepare", st)
    for rnd in range(24):
        st = run("fan_place", st)
        if not st["placed"]:
            break
        st["bad"] = sorted(offenders(drc()))
        st = run("fan_check", st)
        print(f"fan-out ronda {rnd}: {len(st['placed'])} probadas, {st['n_bad'] // 2} rechazadas")
    print("pads de GND sin vía propia:", sum(1 for t in st["todo"] if not t.get("ok")))
    st = run("stitch_place", st)
    for rnd in range(3):
        st["bad"] = sorted(offenders(drc()))
        st = run("stitch_check", st)
        print(f"cosido ronda {rnd}: {st['n_bad']} vías retiradas, {len(st['stitch'])} quedan")
        if not st["n_bad"]:
            break


if __name__ == "__main__":
    if len(sys.argv) > 1:
        s = json.loads(STATE.read_text())
        globals()["op_" + sys.argv[1]](s)
        STATE.write_text(json.dumps(s))
    else:
        main()
