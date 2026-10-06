"""Rev A, paso 6: referencias de serigrafía sin solapes, validadas con la DRC.

  python3 hardware/scripts/revA_6_serigrafia.py

Cada referencia (0,8 mm, el mínimo del fabricante) prueba posiciones alrededor
de su patio; la que no encuentra hueco se oculta en serigrafía (sigue en la capa
Fab para el plano de montaje). pcbnew admite un solo LoadBoard por proceso, así
que cada ronda se ejecuta en un subproceso.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

PCB = Path(__file__).resolve().parents[1] / "radar60.kicad_pcb"
STATE = Path(tempfile.gettempdir()) / "radar60_silk_state.json"
mm = pcbnew.FromMM
SILK = {"silk_over_copper", "silk_overlap", "silk_edge_clearance", "text_height", "text_thickness"}
H, TH = 0.8, 0.12


def drc_bad_refs() -> dict:
    out = Path(tempfile.mkdtemp()) / "drc.json"
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "-o", str(out), str(PCB)], capture_output=True)
    bad = {}
    for v in json.loads(out.read_text())["violations"]:
        if v["type"] in SILK:
            for it in v["items"]:
                d = it["description"]
                if d.startswith("Reference field of "):
                    ref = d.split()[3]
                    bad[ref] = bad.get(ref, 0) + 1
    return bad


def candidates(fp):
    side = fp.GetLayer() == pcbnew.B_Cu
    c = fp.GetCourtyard(pcbnew.B_CrtYd if side else pcbnew.F_CrtYd)
    bb = c.BBox() if c.OutlineCount() else fp.GetBoundingBox(False)
    x0, y0 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
    x1, y1 = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    n = len(fp.GetReference())
    hw = 0.8 * 0.6 * n / 2 + 0.1          # semiancho aproximado del texto
    out = []
    for g in (0.55, 0.9, 1.4):
        out += [(cx, y0 - g), (cx, y1 + g), (x0 - g - hw + 0.3, cy), (x1 + g + hw - 0.3, cy),
                (x0 - hw, y0 - g), (x1 + hw, y0 - g), (x0 - hw, y1 + g), (x1 + hw, y1 + g)]
    return out


def op(step):
    st = json.loads(STATE.read_text())
    b = pcbnew.LoadBoard(str(PCB))
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        f = fp.Reference()
        if step == "init":
            f.SetTextSize(pcbnew.VECTOR2I(mm(H), mm(H)))
            f.SetTextThickness(mm(TH))
            f.SetTextAngleDegrees(0)
            st[ref] = {"i": 0, "n": len(candidates(fp)), "ok": False}
        s = st[ref]
        if step != "init" and s["ok"]:
            continue
        if step == "check":
            if ref in st["_bad"]:
                s["i"] += 1
            else:
                s["ok"] = True
                continue
        if s["i"] < s["n"]:
            x, y = candidates(fp)[s["i"]]
            f.SetVisible(True)
            f.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        else:
            f.SetVisible(False)        # sin hueco: solo en Fab
            s["ok"] = True
    b.Save(str(PCB))
    STATE.write_text(json.dumps(st))


def main():
    STATE.write_text(json.dumps({}))
    subprocess.run([sys.executable, __file__, "init"], check=True)
    for rnd in range(30):
        st = json.loads(STATE.read_text())
        bad = drc_bad_refs()
        pend = [r for r, s in st.items() if not r.startswith("_") and not s["ok"]]
        print(f"ronda {rnd}: {len(bad)} referencias con conflicto, {len(pend)} pendientes")
        if not bad and rnd:
            break
        st["_bad"] = sorted(bad)
        STATE.write_text(json.dumps(st))
        subprocess.run([sys.executable, __file__, "check"], check=True)
    st = json.loads(STATE.read_text())
    print("ocultas en serigrafía:", sorted(r for r, s in st.items()
                                         if not r.startswith("_") and s["i"] >= s["n"]))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        op(sys.argv[1])
    else:
        main()
