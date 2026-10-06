"""Rev A, paso 5: retoques puntuales tras el autorutado (verificados con la DRC).

  python3 hardware/scripts/revA_5_retoques.py
"""
from pathlib import Path

import pcbnew

PCB = Path(__file__).resolve().parents[1] / "radar60.kicad_pcb"
mm = pcbnew.FromMM


# red -> (y de inicio del desvío, y de regreso): x + y y y - x separados 0,6 mm entre pistas
DETOUR = {"/LED_R": (114.6, 118.133), "/LED_G": (114.892, 117.841), "/LED_B": (115.133, 117.6)}


def near(p, x, y, tol=0.01):
    return abs(pcbnew.ToMM(p.x) - x) < tol and abs(pcbnew.ToMM(p.y) - y) < tol


def main():
    b = pcbnew.LoadBoard(str(PCB))
    kill = []
    new = []
    for t in b.GetTracks():
        # vía de GND duplicada (fan-out + cosido) que invadía la pista de +1V8_D de Y1/C13
        if t.GetClass() == "PCB_VIA" and near(t.GetPosition(), 106.1622, 99.8247):
            kill.append(t)
        # USB_DP en In2: quiebro de 0,2 mm frente al agujero no metalizado de J1 (103,75; 116,0)
        if (t.GetClass() == "PCB_TRACK" and t.GetNetname() == "/USB_DP" and t.GetLayer() == pcbnew.In2_Cu
                and near(t.GetStart(), 100.948, 117.68) and near(t.GetEnd(), 112.998, 105.63)):
            fx, fy = 103.189, 115.439            # pie de la perpendicular desde el agujero
            pts = [(fx - 1.4, fy + 1.4), (fx - 0.8 - 0.2, fy + 0.8 - 0.2), (fx + 0.8 - 0.2, fy - 0.8 - 0.2),
                   (fx + 1.4, fy - 1.4)]
            end_ = pcbnew.VECTOR2I(t.GetEnd().x, t.GetEnd().y)
            t.SetEnd(pcbnew.VECTOR2I(mm(pts[0][0]), mm(pts[0][1])))
            chain = pts[1:] + [(pcbnew.ToMM(end_.x), pcbnew.ToMM(end_.y))]
            prev = pts[0]
            for q in chain:
                n = pcbnew.PCB_TRACK(b)
                n.SetStart(pcbnew.VECTOR2I(mm(prev[0]), mm(prev[1])))
                n.SetEnd(pcbnew.VECTOR2I(mm(q[0]), mm(q[1])))
                n.SetWidth(t.GetWidth())
                n.SetLayer(t.GetLayer())
                n.SetNet(t.GetNet())
                new.append(n)
                prev = q
        # pistas de LED en In2: desvío de 1 mm a la izquierda para dejar sitio a la vía de GND de U6;
        # tramos a 45° escalonados para conservar la separación entre las tres
        if (t.GetClass() == "PCB_TRACK" and t.GetLayer() == pcbnew.In2_Cu
                and t.GetNetname() in DETOUR and t.GetStart().x == t.GetEnd().x):
            x = pcbnew.ToMM(t.GetStart().x)
            y0, y1 = pcbnew.ToMM(t.GetStart().y), pcbnew.ToMM(t.GetEnd().y)
            a, bb = DETOUR[t.GetNetname()]
            if y1 < a and y0 > bb + 1:
                path = [(x, y0), (x, bb + 1), (x - 1, bb), (x - 1, a + 1), (x, a), (x, y1)]
                t.SetEnd(pcbnew.VECTOR2I(mm(path[1][0]), mm(path[1][1])))
                for p0, p1 in zip(path[1:], path[2:]):
                    n = pcbnew.PCB_TRACK(b)
                    n.SetStart(pcbnew.VECTOR2I(mm(p0[0]), mm(p0[1])))
                    n.SetEnd(pcbnew.VECTOR2I(mm(p1[0]), mm(p1[1])))
                    n.SetWidth(t.GetWidth())
                    n.SetLayer(t.GetLayer())
                    n.SetNet(t.GetNet())
                    new.append(n)
    for n in new:
        b.Add(n)
    # isla de GND en F.Cu junto a U6: vía en el pad de GND del protector ESD (retorno corto al plano)
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(mm(93.0), mm(116.64)))
    v.SetWidth(mm(0.45))
    v.SetDrill(mm(0.2))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(b.FindNet("/GND"))
    b.Add(v)
    for k in kill:
        b.Remove(k)
    b.Save(str(PCB))


def cleanup():
    """Retira las vías de cosido (GND, sin pista) que participen en alguna violación de la DRC."""
    import json
    import subprocess
    import tempfile
    out = Path(tempfile.mkdtemp()) / "drc.json"
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--refill-zones", "-o", str(out), str(PCB)],
                   capture_output=True)
    bad = {it["uuid"] for v in json.loads(out.read_text())["violations"]
           if v["severity"] == "error" for it in v["items"]}
    b = pcbnew.LoadBoard(str(PCB))
    ends = set()
    for t in b.GetTracks():
        if t.GetClass() == "PCB_TRACK":
            ends.add((t.GetStart().x, t.GetStart().y))
            ends.add((t.GetEnd().x, t.GetEnd().y))
    kill = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "/GND"
            and not t.IsLocked() and t.m_Uuid.AsString() in bad
            and (t.GetPosition().x, t.GetPosition().y) not in ends]
    print("vías de cosido retiradas:", len(kill))
    for t in kill:
        b.Remove(t)
    b.Save(str(PCB))


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--limpiar"]:
        cleanup()
    else:
        main()
        import subprocess
        subprocess.run([sys.executable, __file__, "--limpiar"], check=True)
