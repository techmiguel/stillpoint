"""Rev A, paso 9: USB_DP de J1 a U5 por B.Cu y una vía en cada isla de GND que no tenga ninguna.

  python3 hardware/scripts/revA_9_usb_islas.py
"""
from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import pcbnew

PCB = Path(__file__).resolve().parents[1] / "radar60.kicad_pcb"
mm = pcbnew.FromMM

# USB_DP: vía en el tramo J1 -> U6 (y = 119), B.Cu por debajo de J1 y diagonal hasta U5
DP_PATH_B = [(97.0, 119.0), (97.7, 119.7), (104.8, 119.7), (111.9, 112.6), (111.9, 105.0), (112.3, 104.55)]
DP_PATH_F = [(112.3, 104.55), (112.6, 104.75), (113.5625, 104.75)]
# +3V3 al oeste de U5: se aparta para dejar sitio a la vía de USB_DP junto al pad 3
V33_DROP = [((112.85, 103.848), (112.31, 104.387)), ((112.31, 104.387), (111.945, 104.753)),
            ((111.945, 104.753), (111.945, 105.481))]
V33_NEW = [(112.85, 103.848), (111.4, 103.848), (111.4, 105.481)]
U6_GND_VIA = (93.0, 116.64)     # vía en el pad de GND del protector ESD (se perdió al despejar el cosido)


def track(b, net, pts, layer, w=0.2):
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(mm(x0), mm(y0)))
        t.SetEnd(pcbnew.VECTOR2I(mm(x1), mm(y1)))
        t.SetWidth(mm(w))
        t.SetLayer(layer)
        t.SetNet(net)
        b.Add(t)


def via(b, net, x, y, d=0.45, drill=0.2):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    v.SetWidth(mm(d))
    v.SetDrill(mm(drill))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(net)
    v.SetLocked(True)
    b.Add(v)


def near(p, q, tol=0.01):
    return abs(pcbnew.ToMM(p.x) - q[0]) < tol and abs(pcbnew.ToMM(p.y) - q[1]) < tol


def usb_dp():
    b = pcbnew.LoadBoard(str(PCB))
    dp = b.FindNet("/USB_DP")
    kill = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetname() == "/+3V3"
            and any((near(t.GetStart(), a) and near(t.GetEnd(), c)) or (near(t.GetStart(), c) and near(t.GetEnd(), a))
                    for a, c in V33_DROP)]
    assert len(kill) == len(V33_DROP), len(kill)
    track(b, b.FindNet("/+3V3"), V33_NEW, pcbnew.F_Cu, w=0.3)
    via(b, b.FindNet("/GND"), *U6_GND_VIA)
    via(b, dp, *DP_PATH_B[0])
    track(b, dp, DP_PATH_B, pcbnew.B_Cu)
    via(b, dp, *DP_PATH_B[-1])
    track(b, dp, DP_PATH_F, pcbnew.F_Cu)
    for t in kill:
        b.Remove(t)
    b.Save(str(PCB))


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def islands():
    """Rellena las zonas y pone una vía de GND en cada isla de F.Cu/B.Cu/In2 sin vía ni pad pasante."""
    b = pcbnew.LoadBoard(str(PCB))
    zs = [b.GetArea(i) for i in range(b.GetAreaCount())]
    pcbnew.ZONE_FILLER(b).Fill(zs)
    gnd = b.FindNet("/GND")
    anchors = [t.GetPosition() for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "/GND"]
    anchors += [p.GetPosition() for fp in b.GetFootprints() for p in fp.Pads()
                if p.GetNetname() == "/GND" and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
    added = 0
    for z in zs:
        if z.GetIsRuleArea() or z.GetLayer() == pcbnew.In1_Cu:
            continue
        polys = z.GetFilledPolysList(z.GetLayer())
        for k in range(polys.OutlineCount()):
            ol = polys.COutline(k)
            if any(ol.PointInside(a) for a in anchors):
                continue
            pts = [(pcbnew.ToMM(ol.CPoint(i).x), pcbnew.ToMM(ol.CPoint(i).y)) for i in range(ol.PointCount())]
            bb = ol.BBox()
            best = None
            x0, y0 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
            x1, y1 = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
            n = 20
            for i in range(n + 1):
                for j in range(n + 1):
                    x, y = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * j / n
                    if not ol.PointInside(pcbnew.VECTOR2I(mm(x), mm(y))):
                        continue
                    d = min(seg_dist(x, y, *pts[m], *pts[(m + 1) % len(pts)]) for m in range(len(pts)))
                    if best is None or d > best[0]:
                        best = (d, x, y)
            if best and best[0] >= 0.25:     # cabe una vía de 0,45 dentro de la isla
                via(b, gnd, best[1], best[2])
                added += 1
                print(f"isla {z.GetZoneName()} ({best[1]:.2f}, {best[2]:.2f}): vía añadida")
    b.Save(str(PCB))
    print("vías en islas:", added)


if __name__ == "__main__":
    if sys.argv[1:] == ["--islas"]:
        islands()
    else:
        usb_dp()
        subprocess.run([sys.executable, __file__, "--islas"], check=True)
