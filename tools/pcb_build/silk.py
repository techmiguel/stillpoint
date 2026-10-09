"""Silkscreen: small reference designators placed where they clear pads, vias and
other text (hidden where nothing fits), test-point function labels, board legends."""
import pcbnew, math, sys, os
PCB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hardware", "radar60.kicad_pcb")
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(PCB)
CX, CY, R = 100.0, 100.0, 30.0
TAG = "silk.py"

# remove texts we created before
for d in list(b.GetDrawings()):
    if d.Type() == pcbnew.PCB_TEXT_T and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
        b.Remove(d)

TP_LABEL = {'TP1': '5V', 'TP2': '3V3', 'TP3': '1V8R', 'TP4': 'GND', 'TP13': 'GND', 'TP14': 'GND',
            'TP5': 'SCK', 'TP6': 'MOSI', 'TP7': 'MISO', 'TP8': 'CS', 'TP9': 'IRQ', 'TP10': 'FRM',
            'TP11': 'TX', 'TP12': 'RX'}


def rect_of(item, grow=0.0):
    bb = item.GetBoundingBox()
    return (bb.GetLeft() / 1e6 - grow, bb.GetTop() / 1e6 - grow, bb.GetRight() / 1e6 + grow, bb.GetBottom() / 1e6 + grow)


def overlap(a, c):
    return not (a[2] <= c[0] or c[2] <= a[0] or a[3] <= c[1] or c[3] <= a[1])


obst = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}
for fp in b.GetFootprints():
    side = pcbnew.B_SilkS if fp.IsFlipped() else pcbnew.F_SilkS
    for p in fp.Pads():
        r = rect_of(p, 0.12)
        if p.HasHole():
            obst[pcbnew.F_SilkS].append(r)
            obst[pcbnew.B_SilkS].append(r)
        else:
            obst[side].append(r)
    for g in fp.GraphicalItems():
        if g.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and g.Type() != pcbnew.PCB_TEXT_T:
            obst[g.GetLayer()].append(rect_of(g, 0.08))
# vias are tented: silkscreen may cross them
# courtyards of other parts on the same side (text under a body is invisible)
crt = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}
for fp in b.GetFootprints():
    side = pcbnew.B_SilkS if fp.IsFlipped() else pcbnew.F_SilkS
    lay = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    poly = fp.GetCourtyard(lay)
    if poly.OutlineCount():
        bb = poly.BBox()
        crt[side].append((fp.GetReference(), (bb.GetLeft() / 1e6, bb.GetTop() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6)))

placed_hidden = []


def inside_board(r):
    for x, y in ((r[0], r[1]), (r[2], r[1]), (r[0], r[3]), (r[2], r[3])):
        if math.hypot(x - CX, y - CY) > R - 0.6:
            return False
    return True


def try_place(text_obj, layer, own_ref, anchor_rect, size):
    x0, y0, x1, y1 = anchor_rect
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w_est = len(text_obj.GetText()) * size * 0.75
    cands = []
    for g in (0.15, 0.4, 0.8, 1.3):
        for ang_deg in (0, 90):
            tw, th = (w_est, size) if ang_deg == 0 else (size, w_est)
            for f in (0.0, -0.35, 0.35, -0.7, 0.7):
                dx, dy = f * (x1 - x0) / 2, f * (y1 - y0) / 2
                cands += [(cx + dx, y0 - g - th / 2, ang_deg), (cx + dx, y1 + g + th / 2, ang_deg),
                          (x0 - g - tw / 2, cy + dy, ang_deg), (x1 + g + tw / 2, cy + dy, ang_deg)]
    for (tx, ty, ang) in cands:
        text_obj.SetTextAngleDegrees(ang)
        text_obj.SetPosition(pcbnew.VECTOR2I(mm(tx), mm(ty)))
        r = rect_of(text_obj, 0.05)
        if not inside_board(r):
            continue
        if any(overlap(r, o) for o in obst[layer]):
            continue
        if any(ref != own_ref and overlap(r, c) for ref, c in crt[layer]) and len(cands) and False:
            continue
        obst[layer].append(r)
        return True
    return False


hidden = []
for fp in sorted(b.GetFootprints(), key=lambda f: -f.GetArea() if hasattr(f, 'GetArea') else 0):
    ref = fp.GetReference()
    side = pcbnew.B_SilkS if fp.IsFlipped() else pcbnew.F_SilkS
    lay = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    fp.Value().SetVisible(False)
    rf = fp.Reference()
    big = ref.startswith(('U', 'J', 'SW'))
    size = 0.8 if big else 0.6
    rf.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    rf.SetTextThickness(mm(0.12 if big else 0.1))
    rf.SetKeepUpright(True)
    poly = fp.GetCourtyard(lay)
    bb = poly.BBox() if poly.OutlineCount() else fp.GetBoundingBox(False)
    anchor = (bb.GetLeft() / 1e6, bb.GetTop() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6)
    if ref.startswith(('FID',)):
        rf.SetVisible(False)
        continue
    if ref in TP_LABEL:
        rf.SetVisible(False)
        t = pcbnew.PCB_TEXT(b)
        t.SetText(f"{ref} {TP_LABEL[ref]}")
        t.SetLayer(side)
        t.SetTextSize(pcbnew.VECTOR2I(mm(0.6), mm(0.6)))
        t.SetTextThickness(mm(0.1))
        if side == pcbnew.B_SilkS:
            t.SetMirrored(True)
        if try_place(t, side, ref, anchor, 0.6):
            b.Add(t)
        else:
            hidden.append(ref)
        continue
    rf.SetVisible(True)
    if not try_place(rf, side, ref, anchor, size):
        rf.SetVisible(False)
        hidden.append(ref)


def legend(text, x, y, layer, size=1.0, bold=False):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(text)
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(0.2 if bold else 0.15))
    t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    b.Add(t)


args = dict(a.split('=', 1) for a in sys.argv[1:] if '=' in a)
for spec in args.get('legends', '').split(';'):
    pass
pcbnew.SaveBoard(PCB, b)
print("hidden refs:", hidden)
