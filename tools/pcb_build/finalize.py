"""After routing: solid zone connection on the module/radar/LDO/USB shield, drop vias that
ended up connected on one layer only, refill. Silkscreen refs are done by silk.py."""
import os
import pcbnew
PCB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hardware", "radar60.kicad_pcb")
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(PCB)
for fp in b.GetFootprints():
    if fp.GetReference() in ('U1', 'U2', 'U3', 'J1', 'J2'):
        fp.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.BuildConnectivity()

# dangling vias: no track/pad/zone on two different layers (plane vias count as connected)
removed = []
keep = []
for v in [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]:
    layers = set()
    for it in b.GetConnectivity().GetConnectedItems(v):
        if it.Type() in (pcbnew.PCB_TRACE_T, pcbnew.PCB_ARC_T):
            layers.add(it.GetLayer())
        elif it.Type() == pcbnew.PCB_PAD_T:
            layers.add('pad')
        elif it.Type() in (pcbnew.PCB_ZONE_T, pcbnew.PCB_FP_ZONE_T if hasattr(pcbnew, 'PCB_FP_ZONE_T') else -1):
            layers.add('zone')
    if len(layers) < 2 and 'zone' not in layers:
        removed.append((v.GetNetname(), round(v.GetPosition().x / 1e6, 2), round(v.GetPosition().y / 1e6, 2)))
        keep.append(v)
for v in keep:
    b.Remove(v)
if removed:
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(PCB, b)
print("finalized; dangling vias removed:", removed)
