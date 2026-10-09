"""Hand-planned radar fan-out on B.Cu: ball -> stub -> via, IRQ/DO lanes to U8,
oscillator, VAREF cap, ground stitching. All coordinates relative to the radar centre."""
import pcbnew, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib, placement
importlib.reload(placement)
RX, RY = placement.RX, placement.RY
PCB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hardware", "radar60.kicad_pcb")
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(PCB)
B = pcbnew.B_Cu
W_BGA = 0.15
VIA_D, VIA_DR = 0.55, 0.3
W_PWR = 0.25
fps = {f.GetReference(): f for f in b.GetFootprints()}


def pad(ref, num):
    for p in fps[ref].Pads():
        if p.GetNumber() == num:
            return p
    raise KeyError(ref + num)


def pxy(ref, num):
    q = pad(ref, num).GetPosition()
    return (q.x / 1e6, q.y / 1e6)


def A(rx, ry):
    return (RX + rx, RY + ry)


def net(name):
    n = b.FindNet(name)
    assert n is not None, name
    return n


def track(pts, netname, w=W_BGA, layer=B):
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(mm(x0), mm(y0)))
        t.SetEnd(pcbnew.VECTOR2I(mm(x1), mm(y1)))
        t.SetWidth(mm(w))
        t.SetLayer(layer)
        t.SetNet(net(netname))
        t.SetLocked(True)
        b.Add(t)


def via(xy, netname, d=VIA_D, dr=VIA_DR):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(mm(xy[0]), mm(xy[1])))
    v.SetWidth(mm(d))
    v.SetDrill(mm(dr))
    v.SetNet(net(netname))
    v.SetLocked(True)
    b.Add(v)


def ball_net(ball):
    return pad('U1', ball).GetNetname()


def fan(ball, path_rel, via_rel=None):
    """Track from the ball through relative waypoints; optional via at the end."""
    n = ball_net(ball)
    pts = [pxy('U1', ball)] + [A(*p) for p in path_rel]
    if via_rel:
        pts.append(A(*via_rel))
    track(pts, n, w=W_PWR if ('1V8' in n or '3V3' in n) else W_BGA)
    if via_rel:
        via(A(*via_rel), n)
    return n


# remove previous pre-routing (locked items we created)
for t in list(b.GetTracks()):
    if t.IsLocked():
        b.Remove(t)

# --- north row: signals and supplies, two staggered via rows ---
fan('B1', [], (-2.25, -3.25))            # CLK
fan('D1', [], (-1.25, -3.25))            # DI
fan('F1', [], (-0.25, -3.25))            # DIO3
fan('G1', [], (0.25, -4.05))             # CS_N
fan('H1', [], (0.75, -3.25))             # VDDD
fan('J1', [(1.25, -2.75), (1.45, -2.95)], (1.45, -4.05))   # VDDA
fan('M1', [(2.75, -2.6)], (3.1, -3.25))  # VDDRF (north)
# VAREF: cap on the bottom, right at the ball
c16 = {p.GetNumber(): p for p in fps['C16'].Pads()}
vref = 'VAREF'
vp = [p for p in c16.values() if p.GetNetname().endswith(vref)][0]
gp = [p for p in c16.values() if p.GetNetname().endswith('GND')][0]
vq, gq = vp.GetPosition(), gp.GetPosition()
track([pxy('U1', 'L1'), (vq.x / 1e6, vq.y / 1e6)], vp.GetNetname())
# C16 GND pad joins the bottom ground pour (lanes kept clear above it)

# IRQ / DO lanes to U8 (bottom, B side faces west)
irq_y = pxy('U8', '13')[1]
do_y = pxy('U8', '12')[1]
u8x = pxy('U8', '13')[0]
track([pxy('U1', 'C1'), A(-1.75, irq_y - RY), (u8x, irq_y)], ball_net('C1'))
track([pxy('U1', 'E1'), A(-0.75, do_y - RY), (u8x, do_y)], ball_net('E1'))

# --- east column ---
r4_osc = [p for p in fps['R4'].Pads() if p.GetNetname().endswith('RAD_OSC')][0].GetPosition()
r4_out = [p for p in fps['R4'].Pads() if p.GetNetname().endswith('OSC_OUT')][0].GetPosition()
track([pxy('U1', 'M2'), (r4_osc.x / 1e6, r4_osc.y / 1e6)], ball_net('M2'))
y1_out = pxy('Y1', '3')
track([(r4_out.x / 1e6, r4_out.y / 1e6), y1_out], '/OSC_OUT')
fan('M3', [], (3.95, -1.0))               # LF
fan('M4', [(3.3, -0.5), (3.6, -0.2)], (4.95, -0.2))   # PLL
fan('M6', [], (3.95, 0.6))                # VCO
# --- south row: F9 + G9 (VDDRF) joined, one via ---
track([pxy('U1', 'F9'), pxy('U1', 'G9')], ball_net('F9'), w=W_PWR)
track([A(0, 2.0), A(0, 3.3)], ball_net('F9'), w=W_PWR)
via(A(0, 3.3), ball_net('F9'))

# --- ground stitching around and inside the ball ring ---
for p in [(-3.95, -1.75), (-3.95, 0.0), (-3.95, 1.75), (-1.75, 3.3), (1.75, 3.3), (-3.3, -3.3),
          (-1.0, -0.7), (0.4, -0.7), (1.6, -0.7), (-1.0, 0.7), (0.4, 0.7), (1.6, 0.7)]:
    via(A(*p), '/GND')

filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
pcbnew.SaveBoard(PCB, b)
print("pre-route done")
