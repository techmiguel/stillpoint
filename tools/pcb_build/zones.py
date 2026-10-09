"""Zones, rule areas and stackup for radar60. Idempotent: removes zones it created."""
import pcbnew, math, sys, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib, placement
importlib.reload(placement)
RX, RY = placement.RX, placement.RY
PCB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hardware", "radar60.kicad_pcb")
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(PCB)
_old = list(b.Zones())
for z in _old:
    b.Remove(z)
CX, CY, R = 100.0, 100.0, 30.0


def poly(pts):
    ch = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in pts:
        ch.Append(mm(x), mm(y))
    ch.SetClosed(True)
    return ch


def circle_pts(r, n=96):
    return [(CX + r * math.cos(2 * math.pi * i / n), CY + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def zone(layer, netname, pts, prio=0, name="", thermal=True, layers=None):
    z = pcbnew.ZONE(b)
    if layers:
        ls = pcbnew.LSET()
        for l in layers:
            ls.AddLayer(l)
        z.SetLayerSet(ls)
    else:
        z.SetLayer(layer)
    if netname:
        z.SetNet(b.FindNet(netname))
    z.Outline().AddOutline(poly(pts))
    z.SetAssignedPriority(prio)
    z.SetLocalClearance(mm(0.2))
    z.SetMinThickness(mm(0.2))
    z.SetThermalReliefGap(mm(0.25))
    z.SetThermalReliefSpokeWidth(mm(0.3))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL if thermal else pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    if name:
        z.SetZoneName(name)
    b.Add(z)
    return z


def rule_area(layers, pts, name, tracks=False, vias=False, pads=False, copper=False, fps=False):
    z = pcbnew.ZONE(b)
    z.SetIsRuleArea(True)
    ls = pcbnew.LSET()
    for l in layers:
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    z.Outline().AddOutline(poly(pts))
    z.SetDoNotAllowTracks(tracks)
    z.SetDoNotAllowVias(vias)
    z.SetDoNotAllowPads(pads)
    z.SetDoNotAllowZoneFills(copper)
    z.SetDoNotAllowFootprints(fps)
    z.SetZoneName(name)
    b.Add(z)
    return z


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def rot_rect(ang_deg, r0, r1, half_w):
    """Rectangle from radius r0 to r1 at FreeCAD angle ang (CCW from +X, Y up)."""
    a = math.radians(ang_deg)
    ux, uy = math.cos(a), -math.sin(a)   # KiCad Y is down
    vx, vy = -uy, ux
    return [(CX + ux * r + vx * s, CY + uy * r + vy * s) for r, s in ((r0, -half_w), (r1, -half_w), (r1, half_w), (r0, half_w))]


CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
edge = circle_pts(R - 0.3)
# ground planes and pours
zone(pcbnew.In1_Cu, "/GND", edge, 0, "GND_L2")
# solid ground island on L3 right under the radar (Infineon: ground plane under the chip, no signals)
ISLAND = (RX - 4.4, RY - 3.3, RX + 4.4, RY + 3.6)
zp = zone(pcbnew.In2_Cu, "/+3V3", edge, 0, "P3V3_L3")
zp.Outline().NewHole()
for x, y in rect(ISLAND[0] - 0.3, ISLAND[1] - 0.3, ISLAND[2] + 0.3, ISLAND[3] + 0.3):
    zp.Outline().Append(mm(x), mm(y), 0, 0)
zone(pcbnew.In2_Cu, "/GND", rect(*ISLAND), 2, "GND_L3_RADAR", thermal=False)
zone(pcbnew.F_Cu, "/GND", edge, 0, "GND_TOP")
zone(pcbnew.B_Cu, "/GND", edge, 0, "GND_BOT")
# solid ground under the radar on the bottom (balls connect fully)
zone(pcbnew.B_Cu, "/GND", rect(RX - 3.3, RY - 2.6, RX + 3.3, RY + 2.6), 1, "GND_RADAR", thermal=False)

# MGM260P built-in antenna: no copper on any layer (datasheet fig. 8.2: 8.8 x 4.8 mm from the module edge)
ux = placement.P['U2'][0]
top = placement.P['U2'][1] - 7.5
rule_area(CU, rect(ux - 4.4, CY - R - 1.0, ux + 4.4, top + 4.8), "ANTENNA_KEEPOUT", tracks=True, vias=True, pads=True, copper=True)
# enclosure: three board supports (bottom) and three lid clamps (top) at 30/150/270 deg
for i, a in enumerate((30, 150, 270)):
    pts = rot_rect(a, 26.6, 30.5, 3.6)
    rule_area([pcbnew.F_Cu, pcbnew.B_Cu], pts, f"SUPPORT_{a}", fps=True)

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(PCB, b)

# stackup (JLC04161H-7628) into (setup ...) if missing
s = open(PCB, encoding='utf8').read()
if '(stackup' not in s:
    stack = '''		(stackup
			(layer "F.SilkS" (type "Top Silk Screen"))
			(layer "F.Paste" (type "Top Solder Paste"))
			(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
			(layer "F.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 1" (type "prepreg") (thickness 0.2104) (material "7628") (epsilon_r 4.4) (loss_tangent 0.02))
			(layer "In1.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 2" (type "core") (thickness 1.065) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
			(layer "In2.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 3" (type "prepreg") (thickness 0.2104) (material "7628") (epsilon_r 4.4) (loss_tangent 0.02))
			(layer "B.Cu" (type "copper") (thickness 0.035))
			(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
			(layer "B.Paste" (type "Bottom Solder Paste"))
			(layer "B.SilkS" (type "Bottom Silk Screen"))
			(copper_finish "ENIG")
			(dielectric_constraints no)
		)
'''
    s = s.replace('\t(setup\n', '\t(setup\n' + stack, 1)
    open(PCB, 'w', encoding='utf8').write(s)
print("zones done")
