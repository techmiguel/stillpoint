"""One ground via per ground SMD pad (short stub to the In1/In2 planes), placed where it
clears every other-net copper item. Locked, so routing passes keep them."""
import pcbnew, math, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hardware", "radar60.kicad_pcb")
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(PCB)
VD, VDR, W = 0.55, 0.3, 0.3
CLR = 0.15
CX, CY, R = 100.0, 100.0, 30.0
SKIP = {'U1'}                      # radar handled by prerout.py
gnd = b.FindNet('/GND')
p3 = b.FindNet('/+3V3')
import importlib, placement
RX, RY = placement.RX, placement.RY
ISLAND = (RX - 4.4 - 0.6, RY - 3.3 - 0.6, RX + 4.4 + 0.6, RY + 3.6 + 0.6)

# obstacles: (layerset_fn, shape) via KiCad geometry: use pads' effective polygons and tracks
items = []
for fp in b.GetFootprints():
    for p in fp.Pads():
        items.append(p)
for t in b.GetTracks():
    items.append(t)
keepouts = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]


def clear_of(x, y, layer_items, net=None):
    net = net or gnd
    if net.GetNetCode() == p3.GetNetCode() and ISLAND[0] < x < ISLAND[2] and ISLAND[1] < y < ISLAND[3]:
        return False
    pt = pcbnew.VECTOR2I(mm(x), mm(y))
    if math.hypot(x - CX, y - CY) > R - 0.3 - VD / 2 - 0.2:
        return False
    for z in keepouts:
        if z.Outline().Contains(pt):
            return False
    via_shape = pcbnew.SHAPE_CIRCLE(pt, mm(VD / 2))
    for it in layer_items:
        same = it.GetNetCode() == net.GetNetCode()
        need = mm(0.1 if same else CLR)
        for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
            if not it.IsOnLayer(lay):
                continue
            sh = it.GetEffectiveShape(lay)
            if sh.Collide(via_shape, need):
                return False
    # hole-to-hole / hole clearance against other holes
    for it in layer_items:
        if it.Type() == pcbnew.PCB_PAD_T and it.HasHole():
            q = it.GetPosition()
            if math.hypot(q.x / 1e6 - x, q.y / 1e6 - y) < VDR / 2 + it.GetDrillSize().x / 2e6 + 0.3:
                return False
    return True


def stub_clear(x0, y0, x1, y1, layer, pad, net=None):
    net = net or gnd
    seg = pcbnew.SHAPE_SEGMENT(pcbnew.VECTOR2I(mm(x0), mm(y0)), pcbnew.VECTOR2I(mm(x1), mm(y1)), mm(W))
    for it in items:
        if it.GetNetCode() == net.GetNetCode() or not it.IsOnLayer(layer):
            continue
        if it.GetEffectiveShape(layer).Collide(seg, mm(CLR)):
            return False
    return True


placed = 0
failed = []
for fp, p in [(fp, p) for fp in b.GetFootprints() for p in fp.Pads()]:
        if fp.GetReference() in SKIP:
            continue
        if p.GetNetCode() not in (gnd.GetNetCode(), p3.GetNetCode()) or p.GetAttribute() not in (pcbnew.PAD_ATTRIB_SMD, pcbnew.PAD_ATTRIB_CONN):
            continue
        net = p.GetNet()
        layer = pcbnew.B_Cu if fp.IsFlipped() else pcbnew.F_Cu
        q = p.GetPosition()
        px, py = q.x / 1e6, q.y / 1e6
        bb = p.GetBoundingBox()
        hw, hh = bb.GetWidth() / 2e6, bb.GetHeight() / 2e6
        c = fp.GetPosition()
        ox, oy = px - c.x / 1e6, py - c.y / 1e6
        base = math.atan2(oy, ox) if math.hypot(ox, oy) > 0.05 else 0.0
        best = None
        for dist_extra in (0.45, 0.65, 0.9, 1.2):
            for k in range(16):
                ang = base + (k // 2) * (math.pi / 8) * (1 if k % 2 == 0 else -1)
                ext = abs(hw * math.cos(ang)) + abs(hh * math.sin(ang))
                d = ext + dist_extra
                vx, vy = px + d * math.cos(ang), py + d * math.sin(ang)
                if clear_of(vx, vy, items, net) and stub_clear(px, py, vx, vy, layer, p, net):
                    best = (vx, vy)
                    break
            if best:
                break
        if not best:
            failed.append(f"{fp.GetReference()}.{p.GetNumber()}")
            continue
        vx, vy = best
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(mm(vx), mm(vy)))
        v.SetWidth(mm(VD))
        v.SetDrill(mm(VDR))
        v.SetNet(net)
        v.SetLocked(True)
        b.Add(v)
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(q)
        t.SetEnd(v.GetPosition())
        t.SetWidth(mm(W))
        t.SetLayer(layer)
        t.SetNet(net)
        t.SetLocked(True)
        b.Add(t)
        items.extend([v, t])
        placed += 1
pcbnew.SaveBoard(PCB, b)
print("gnd vias", placed, "failed", failed)

# CP2102N exposed pad: 5 stitching vias (cross pattern, between the paste windows)
b = pcbnew.LoadBoard(PCB)
fp = [f for f in b.GetFootprints() if f.GetReference() == 'U5'][0]
c = fp.GetPosition()
for dx, dy in ((0, 0), (1.0, 0), (-1.0, 0), (0, 1.0), (0, -1.0)):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(c.x + mm(dx), c.y + mm(dy)))
    v.SetWidth(mm(VD))
    v.SetDrill(mm(VDR))
    v.SetNet(gnd)
    v.SetLocked(True)
    b.Add(v)
pcbnew.SaveBoard(PCB, b)
print("U5 EP vias added")
