"""USB-C (vertical GT-USB-7051A) breakout and USB pair, locked.

J1 rows:  north A1 A4 A5 A6 A7 A8 A9 A12 / south B12 B9 B8 B7 B6 B5 B4 B1 (0.79 mm pitch).
- VBUS pairs A4-B9 and A9-B4 joined vertically through the row gap, each to its own via.
- D- copies A7-B7 joined diagonally through the gap (top); D+ copies A6/B6 joined on the
  bottom through two vias.
- J1 -> ESD U6 south pins (D+ pin 1, D- pin 3); ESD north pins (D+ 6, D- 4) -> CP2102N.
  USBLC6 is flow-through, so the pair passes straight through the ESD footprint.
- GND pins to the shield legs; CC1/CC2 to R1/R2."""
import os
import pcbnew
PCB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hardware", "radar60.kicad_pcb")
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(PCB)
F, B = pcbnew.F_Cu, pcbnew.B_Cu
fps = {f.GetReference(): f for f in b.GetFootprints()}


def P(ref, num):
    q = [p for p in fps[ref].Pads() if p.GetNumber() == num][0].GetPosition()
    return (q.x / 1e6, q.y / 1e6)


def track(pts, net, w=0.25, layer=F):
    n = b.FindNet(net)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if abs(x0 - x1) < 1e-6 and abs(y0 - y1) < 1e-6:
            continue
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(mm(x0), mm(y0)))
        t.SetEnd(pcbnew.VECTOR2I(mm(x1), mm(y1)))
        t.SetWidth(mm(w))
        t.SetLayer(layer)
        t.SetNet(n)
        t.SetLocked(True)
        b.Add(t)


def via(xy, net, d=0.55):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(mm(xy[0]), mm(xy[1])))
    v.SetWidth(mm(d))
    v.SetDrill(mm(0.3))
    v.SetNet(b.FindNet(net))
    v.SetLocked(True)
    b.Add(v)


H = 0.5      # half pad length
a4, b9, a9, b4 = P('J1', 'A4'), P('J1', 'B9'), P('J1', 'A9'), P('J1', 'B4')
# VBUS
track([a4, b9], '/VBUS')
track([a9, b4], '/VBUS')
vl = (b9[0] + 0.54, b9[1] + H + 0.74)
vr = (a9[0] - 0.51, a9[1] - H - 0.74)
track([(b9[0], b9[1] + H), vl], '/VBUS')
track([(a9[0], a9[1] - H), vr], '/VBUS')
via(vl, '/VBUS')
via(vr, '/VBUS')
# GND pins to the shield legs
sh = sorted([p for p in fps['J1'].Pads() if p.GetNumber() == 'SH'], key=lambda p: (p.GetPosition().x, p.GetPosition().y))
shp = [(p.GetPosition().x / 1e6, p.GetPosition().y / 1e6) for p in sh]
a1, b12, a12, b1 = P('J1', 'A1'), P('J1', 'B12'), P('J1', 'A12'), P('J1', 'B1')
track([a1, b12], '/GND', 0.3)
track([a12, b1], '/GND', 0.3)
for pad, s, sgn in ((a1, shp[0], -1), (b12, shp[1], 1), (a12, shp[2], -1), (b1, shp[3], 1)):
    track([(pad[0], pad[1] + sgn * H), s], '/GND', 0.3)
# D-: A7 <-> B7 through the gap; D+: A6 / B6 joined on the bottom
a6, a7, b6, b7 = P('J1', 'A6'), P('J1', 'A7'), P('J1', 'B6'), P('J1', 'B7')
track([a7, b7], '/USB_DN', 0.2)
va6 = (a6[0], a6[1] - H - 0.7)
vb6 = (b6[0], b6[1] + H + 1.0)
track([(a6[0], a6[1] - H), va6], '/USB_DP', 0.2)
via(va6, '/USB_DP')
track([(b6[0], b6[1] + H), vb6], '/USB_DP', 0.2)
via(vb6, '/USB_DP')
track([va6, (va6[0], vb6[1] - 0.8), vb6], '/USB_DP', 0.2, B)
# J1 -> U6 south pins
u1, u2, u3 = P('U6', '1'), P('U6', '2'), P('U6', '3')
yDN, yDP = shp[1][1] + 0.85, shp[1][1] + 1.45
track([(b7[0], b7[1] + H), (b7[0], yDN), (u3[0], yDN), u3], '/USB_DN', 0.2)
track([vb6, (vb6[0], yDP), (u1[0], yDP), u1], '/USB_DP', 0.2)
gv = (u2[0], u2[1] + 1.45)
track([u2, gv], '/GND', 0.3)
via(gv, '/GND')
# U6 north pins -> CP2102N (rotated 180: D- pad 4 above D+ pad 3 on its east side)
u4, u5, u6 = P('U6', '4'), P('U6', '5'), P('U6', '6')
c3, c4 = P('U5', '3'), P('U5', '4')
track([c4, (u4[0] - 0.75, c4[1]), (u4[0], c4[1] + 0.75), u4], '/USB_DN', 0.2)
track([c3, (u6[0] - 0.5, c3[1]), (u6[0], c3[1] + 0.5), u6], '/USB_DP', 0.2)
vb = (u5[0], u5[1] - 1.45)
track([u5, vb], '/VBUS', 0.3)
via(vb, '/VBUS')
# CC1 north to R1, CC2 south to R2
a5, b5 = P('J1', 'A5'), P('J1', 'B5')
r1 = [p for p in fps['R1'].Pads() if p.GetNetname() == '/CC1'][0].GetPosition()
r2 = [p for p in fps['R2'].Pads() if p.GetNetname() == '/CC2'][0].GetPosition()
track([(a5[0], a5[1] - H), (r1.x / 1e6, r1.y / 1e6)], '/CC1', 0.2)
track([(b5[0], b5[1] + H), (r2.x / 1e6, r2.y / 1e6)], '/CC2', 0.2)
pcbnew.SaveBoard(PCB, b)
print("usb breakout done")
