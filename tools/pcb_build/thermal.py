"""Extra ground vias around U3 (TLV75733P, up to ~0.7 W): the thermal pad is solidly joined
to the top ground pour, and these vias carry the heat into the L2 ground plane."""
import os, math
import pcbnew
PCB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hardware", "radar60.kicad_pcb")
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(PCB)
gnd = b.FindNet('/GND')
u3 = [f for f in b.GetFootprints() if f.GetReference() == 'U3'][0]
c = u3.GetPosition()
items = [p for f in b.GetFootprints() for p in f.Pads()] + list(b.GetTracks())
placed = []
for r in (1.7, 2.1, 2.5):
    for k in range(16):
        a = 2 * math.pi * k / 16
        pt = pcbnew.VECTOR2I(int(c.x + mm(r) * math.cos(a)), int(c.y + mm(r) * math.sin(a)))
        shape = pcbnew.SHAPE_CIRCLE(pt, mm(0.275))
        ok = True
        for it in items:
            for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
                if it.IsOnLayer(lay) and it.GetEffectiveShape(lay).Collide(shape, mm(0.12 if it.GetNetCode() != gnd.GetNetCode() else 0.0)):
                    if it.GetNetCode() != gnd.GetNetCode() or it.Type() == pcbnew.PCB_VIA_T:
                        ok = False
            if not ok:
                break
        if ok and all(math.hypot(pt.x - q.x, pt.y - q.y) > mm(0.85) for q in placed):
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pt)
            v.SetWidth(mm(0.55))
            v.SetDrill(mm(0.3))
            v.SetNet(gnd)
            v.SetLocked(True)
            b.Add(v)
            items.append(v)
            placed.append(pt)
        if len(placed) >= 6:
            break
    if len(placed) >= 6:
        break
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(PCB, b)
print("U3 thermal vias:", [(round(p.x / 1e6, 2), round(p.y / 1e6, 2)) for p in placed])
