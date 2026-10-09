"""Rebuild radar60.kicad_pcb from the schematic netlist: footprints from the
libraries, nets, placement (placement.py), board-only items. Routing is separate."""
import pcbnew, sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from netlist_util import load_netlist, fp_load
import importlib
import placement
importlib.reload(placement)

PCB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hardware", "radar60.kicad_pcb")
NET = os.path.join(HERE, "build", "radar60.xml")
mm = pcbnew.FromMM
V = lambda x, y: pcbnew.VECTOR2I(mm(x), mm(y))

b = pcbnew.LoadBoard(PCB)
old_fps = list(b.GetFootprints())
old_tr = list(b.GetTracks())
old_z = list(b.Zones())
old_d = [d for d in b.GetDrawings() if d.GetLayer() != pcbnew.Edge_Cuts]
for it in old_fps + old_tr + old_z + old_d:
    b.Remove(it)

comps, nets = load_netlist(NET)
netitems = {}
for name in nets:
    ni = b.FindNet(name)
    if ni is None:
        ni = pcbnew.NETINFO_ITEM(b, name)
        b.Add(ni)
    netitems[name] = ni
padnet = {}
for name, nodes in nets.items():
    for ref, pin in nodes:
        padnet[(ref, pin)] = name

STD_FIELDS = {"Footprint", "Datasheet", "Description", "Reference", "Value"}
missing = []
for ref, c in sorted(comps.items()):
    fp = fp_load(c['fp'])
    fp.SetReference(ref)
    fp.SetValue(c['value'])
    fp.SetPath(pcbnew.KIID_PATH("/" + c['tstamp']))
    fp.SetSheetname("/")
    fp.SetSheetfile("radar60.kicad_sch")
    if c['datasheet'] and c['datasheet'] != '~':
        fp.SetField("Datasheet", c['datasheet'])
    if c['description']:
        fp.SetField("Description", c['description'])
    for k, v in c['fields'].items():
        if k not in STD_FIELDS and v:
            fp.SetField(k, v)
            f = fp.GetField(k)
            f.SetVisible(False)
            f.SetLayer(pcbnew.F_Fab)
    if 'exclude_from_bom' in c['props']:
        fp.SetExcludedFromBOM(True)
    if ref == 'J2':      # Tag-Connect: pads for the programming cable, nothing is mounted
        fp.SetExcludedFromBOM(True)
        fp.SetExcludedFromPosFiles(True)
    if 'dnp' in c['props']:
        fp.SetDNP(True)
    b.Add(fp)
    for p in fp.Pads():
        n = padnet.get((ref, p.GetNumber()))
        if n:
            p.SetNet(netitems[n])
        elif p.GetNumber():
            missing.append(f"{ref}.{p.GetNumber()}")
    if ref in ('U1', 'U2', 'U3', 'J1'):
        fp.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    pl = placement.P.get(ref)
    if pl is None:
        x, y, rot, side = 140, 100, 0, 'F'
        print("unplaced", ref)
    else:
        x, y, rot, side = pl
    fp.SetPosition(V(x, y))
    if side == 'B':
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(rot)

# board-only: fiducials
for i, (x, y, side) in enumerate(placement.FIDUCIALS, 1):
    fp = fp_load("Fiducial:Fiducial_1mm_Mask2mm")
    fp.SetReference(f"FID{i}")
    fp.SetValue("Fiducial")
    fp.SetBoardOnly(True)
    fp.SetExcludedFromBOM(True)
    fp.SetExcludedFromPosFiles(False)
    b.Add(fp)
    fp.SetPosition(V(x, y))
    if side == 'B':
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)

if missing:
    print("pads without net:", missing)
b.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_POWER)
pcbnew.SaveBoard(PCB, b)
print("saved", len(list(b.GetFootprints())), "footprints")
