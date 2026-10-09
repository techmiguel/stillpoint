"""Radar supply rails on F.Cu: from each domain's BGA via straight through its
100 nF -> 1 uF -> 10 uF -> ferrite, plus the +1V8_RAD feed bus to the ferrites."""
import pcbnew, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PCB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hardware", "radar60.kicad_pcb")
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(PCB)
F = pcbnew.F_Cu
fps = {f.GetReference(): f for f in b.GetFootprints()}


def P(ref, num):
    for p in fps[ref].Pads():
        if p.GetNumber() == num:
            q = p.GetPosition()
            return (q.x / 1e6, q.y / 1e6)
    raise KeyError(ref + num)


def track(pts, netname, w=0.3):
    n = b.FindNet(netname)
    assert n, netname
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if abs(x0 - x1) < 1e-6 and abs(y0 - y1) < 1e-6:
            continue
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(mm(x0), mm(y0)))
        t.SetEnd(pcbnew.VECTOR2I(mm(x1), mm(y1)))
        t.SetWidth(mm(w))
        t.SetLayer(F)
        t.SetNet(n)
        t.SetLocked(True)
        b.Add(t)


def via_at(netname, near):
    """position of the radar fan-out via of a net (closest to `near`)"""
    best = None
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == netname:
            q = t.GetPosition()
            d = (q.x / 1e6 - near[0]) ** 2 + (q.y / 1e6 - near[1]) ** 2
            if best is None or d < best[0]:
                best = (d, (q.x / 1e6, q.y / 1e6))
    return best[1]


def lane(netname, start, corner_pts, caps, fb):
    pts = [start] + corner_pts + [P(r, '1') for r in caps] + [P(fb, '2')]
    track(pts, netname)


vD = via_at('/+1V8_D', (100.75, 99.25))
vA = via_at('/+1V8_A', (101.45, 98.45))
vRFn = via_at('/+1V8_RF', (103.1, 99.25))
vRFs = via_at('/+1V8_RF', (100.0, 105.8))
vLF = via_at('/+3V3_LF', (103.95, 101.5))
vPLL = via_at('/+1V8_PLL', (104.95, 102.3))
vVCO = via_at('/+1V8_VCO', (103.95, 103.1))

yD = P('C13', '1')[1]
yA = P('C11', '1')[1]
lane('/+1V8_D', vD, [(100.85, vD[1] - 0.25), (100.85, 97.6), (103.9, 97.6), (103.9, yD)], ['C13', 'C14', 'C29'], 'FB3')
lane('/+1V8_A', vA, [(104.5, vA[1]), (104.5, yA)], ['C11', 'C12', 'C28'], 'FB2')
track([vRFn, P('C7', '1')], '/+1V8_RF')
lane('/+3V3_LF', vLF, [], ['C15', 'C31', 'C30'], 'FB4')
yP = P('C10', '1')[1]
lane('/+1V8_PLL', vPLL, [(vPLL[0], yP)], ['C10', 'C33', 'C32'], 'FB5')
yV = P('C9', '1')[1]
lane('/+1V8_VCO', vVCO, [(vVCO[0], yV)], ['C9', 'C35', 'C34'], 'FB6')
lane('/+1V8_RF', vRFs, [], ['C5', 'C6', 'C8', 'C27'], 'FB1')

# +1V8_RAD bus: east column through FB3/FB2/FB5/FB6 inputs, down and west to FB1
BX = 113.9
fb1 = P('FB1', '1')
track([P('FB3', '1'), (BX, P('FB3', '1')[1]), (BX, P('FB6', '1')[1] + 0.0)], '/+1V8_RAD', 0.4)
for r in ('FB2', 'FB5', 'FB6'):
    track([P(r, '1'), (BX, P(r, '1')[1])], '/+1V8_RAD', 0.4)
track([(BX, P('FB6', '1')[1]), (BX, fb1[1]), fb1], '/+1V8_RAD', 0.4)
# tap for the oscillator ferrite FB7 on the bottom
tap_y = (P('FB5', '1')[1] + P('FB6', '1')[1]) / 2
fb7 = P('FB7', '1')
track([(BX, tap_y), (BX - 1.0, tap_y)], '/+1V8_RAD', 0.4)
v = pcbnew.PCB_VIA(b)
v.SetPosition(pcbnew.VECTOR2I(mm(BX - 1.0), mm(tap_y)))
v.SetWidth(mm(0.6))
v.SetDrill(mm(0.3))
v.SetNet(b.FindNet('/+1V8_RAD'))
v.SetLocked(True)
b.Add(v)
n = b.FindNet('/+1V8_RAD')
for (x0, y0), (x1, y1) in [((BX - 1.0, tap_y), (fb7[0], tap_y)), ((fb7[0], tap_y), fb7)]:
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(pcbnew.VECTOR2I(mm(x0), mm(y0)))
    t.SetEnd(pcbnew.VECTOR2I(mm(x1), mm(y1)))
    t.SetWidth(mm(0.4))
    t.SetLayer(pcbnew.B_Cu)
    t.SetNet(n)
    t.SetLocked(True)
    b.Add(t)
# CP2102N (rotated 180: sense/reset on its north side): sense up to the R7/R8 divider,
# reset up between R8 and R7 to R9
u8 = P('U5', '8')
r7, r8 = P('R7', '2'), P('R8', '1')
track([u8, (u8[0], r7[1]), r7], '/USB_VBUS_SENSE', 0.2)
track([r7, r8], '/USB_VBUS_SENSE', 0.2)
u9 = P('U5', '9')
r9 = P('R9', '2')
track([u9, (u9[0], r9[1] + 0.22), (r9[0], r9[1] + 0.22), r9], '/CP_RST', 0.2)
# CP2102N corner pads: GND pad 2 to the exposed pad, +3V3 pad 7 to pad 6
track([P('U5', '2'), (P('U5', '25')[0] + 1.1, P('U5', '2')[1])], '/GND', 0.25)
c25 = [p for p in fps['C25'].Pads() if p.GetNetname() == '/+3V3'][0].GetPosition()
c24 = [p for p in fps['C24'].Pads() if p.GetNetname() == '/+3V3'][0].GetPosition()
track([P('U5', '7'), (P('U5', '7')[0], c25.y / 1e6), (c25.x / 1e6, c25.y / 1e6)], '/+3V3', 0.25)
track([P('U5', '5'), P('U5', '6'), (P('U5', '6')[0] + 0.6, P('U5', '6')[1]), (c24.x / 1e6, c24.y / 1e6)], '/+3V3', 0.25)
pcbnew.SaveBoard(PCB, b)
print("rails done")
