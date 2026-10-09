import os
import pcbnew
PCB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hardware", "radar60.kicad_pcb")
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(PCB)
for d in list(b.GetDrawings()):
    if d.Type() == pcbnew.PCB_TEXT_T and d.GetText().startswith(('radar60', '60 GHz', 'rev A', 'not a medical', 'Matter', 'this side', 'CERN-OHL', 'github.com')):
        b.Remove(d)


def legend(text, x, y, layer, size=1.0, th=0.15):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(text)
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(th))
    t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    b.Add(t)


F, B = pcbnew.F_SilkS, pcbnew.B_SilkS
legend("radar60", 121.2, 104.6, F, 1.4, 0.25)
legend("rev A 2026", 121.2, 106.6, F, 0.8, 0.13)
legend("60 GHz radar", 121.2, 108.1, F, 0.8, 0.13)
legend("Matter/Thread", 121.2, 109.6, F, 0.8, 0.13)
legend("radar60 rev A", 112.0, 114.6, B, 1.2, 0.2)
legend("60 GHz presence & fall sensor", 112.0, 116.4, B, 0.7, 0.12)
legend("not a medical device", 112.0, 117.8, B, 0.7, 0.12)
legend("this side faces the floor", 112.0, 119.2, B, 0.7, 0.12)
legend("CERN-OHL-S-2.0", 112.0, 120.9, B, 0.7, 0.12)
legend("github.com/techmiguel/radar60", 112.0, 122.2, B, 0.6, 0.1)
pcbnew.SaveBoard(PCB, b)
print("legends")
