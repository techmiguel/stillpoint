"""VAREF capacitor C16 (bottom, next to the radar): its ground pad is boxed in by the
IRQ/DO lanes and the fan-out vias, so it is tied on B.Cu to the nearest ground via east of it."""
import os
import pcbnew
PCB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hardware", "radar60.kicad_pcb")
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(PCB)
c16 = [f for f in b.GetFootprints() if f.GetReference() == 'C16'][0]
g = [p for p in c16.Pads() if p.GetNetname() == '/GND'][0].GetPosition()
vias = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == '/GND'
        and t.GetPosition().x > g.x + mm(2.5) and abs(t.GetPosition().y - g.y) < mm(0.4)]
v = min(vias, key=lambda t: t.GetPosition().x).GetPosition()
n = b.FindNet('/GND')
for s, e in ((g, pcbnew.VECTOR2I(v.x, g.y)), (pcbnew.VECTOR2I(v.x, g.y), v)):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(s)
    t.SetEnd(e)
    t.SetWidth(mm(0.25))
    t.SetLayer(pcbnew.B_Cu)
    t.SetNet(n)
    t.SetLocked(True)
    b.Add(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(PCB, b)
print("C16 GND tied to the via at", v.x / 1e6, v.y / 1e6)
