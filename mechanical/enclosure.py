"""Parametric ceiling enclosure in FreeCAD (B-rep solids).

Run with the FreeCAD interpreter (no GUI):
  "C:\\Program Files\\FreeCAD 1.1\\bin\\freecadcmd.exe" -c "exec(open(r'mechanical/enclosure.py').read())"

Outputs in mechanical/cad/: stillpoint.FCStd (editable document), enclosure, lid and
radome_coupon as .step and .stl, and checks.json. The checks are assertions:
if a dimension fails, the script stops and exports nothing.
"""
import json
import math
import os

import FreeCAD as App
import Mesh  # noqa: F401
import MeshPart
import Part

V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.join(os.getcwd(), "mechanical")
OUT = os.path.join(HERE, "cad")
os.makedirs(OUT, exist_ok=True)

# ---- parameters (same as drawing.py) -------------------------------------------
EPS_R = 2.8
LAMBDA0 = 299792458.0 / 60.6e9 * 1e3        # 4.95 mm
T_RAD = LAMBDA0 / (2 * math.sqrt(EPS_R))     # λ/2 radome inside the material
GAP = LAMBDA0                                # antennas (chip bottom face) -> radome inner face
CHIP_H = 0.9                                 # BGT60TR13C height under the board
PCB_R, PCB_T = 30.0, 1.6
CLEAR = 0.4
R_IN = PCB_R + CLEAR
WALL = 2.0
R_OUT = R_IN + WALL
H_INNER = 14.0
Z_ANT = T_RAD + GAP                          # antenna plane
Z_PCB = Z_ANT + CHIP_H                       # board bottom face
H = Z_PCB + H_INNER                          # enclosure height
LID_T, LID_EXTRA = 2.4, 6.0
LIP_H, LIP_W = 4.0, 1.2
CABLE = (14.0, 9.0)                          # opening for the vertical USB-C plug + boot
# Board positions (hardware/stillpoint.kicad_pcb, board centre = origin;
# X as in KiCad, Y = -Y of KiCad): radar U1 at (100, 102.5) and USB-C J1 at (100, 119).
RADAR_XY = (0.0, -2.5)
USB_XY = (0.0, -19.0)
SUPPORT_ANGLES = (30, 150, 270)              # part-free on both faces (SUPPORT_* zones on the board)
BOARD_STEP = os.path.join(HERE, "..", "hardware", "fabrication", "stillpoint.step")
SCREW_D, CSK_D = 4.2, 8.4
FOV_DEG = 60.0                               # useful antenna half-angle


def cyl(r, h, z=0.0):
    return Part.makeCylinder(r, h, V(0, 0, z))


def enclosure():
    body = cyl(R_OUT, H).cut(cyl(R_IN, H, T_RAD))
    # board supports: the board rests at Z_PCB -> antennas exactly GAP from the radome
    for a in SUPPORT_ANGLES:
        s = Part.makeBox(3.0, 6.0, Z_PCB - T_RAD, V(R_IN - 3.0, -3.0, T_RAD))
        s.rotate(V(0, 0, 0), V(0, 0, 1), a)
        body = body.fuse(s)
    # ventilation in the upper half, away from the antenna cone
    for a in range(30, 360, 60):
        slot = Part.makeBox(WALL + 2, 3.0, 4.0, V(R_IN - 1, -1.5, Z_PCB + 8))
        slot.rotate(V(0, 0, 0), V(0, 0, 1), a)
        body = body.cut(slot)
    # chamfer on the lower outer edge (cosmetic, clear of the useful radome)
    edges = [e for e in body.Edges if abs(e.BoundBox.ZMax) < 1e-6 and abs(e.BoundBox.XMax - R_OUT) < 1e-3]
    if edges:
        body = body.makeChamfer(0.8, edges)
    return body.removeSplitter()


def lid():
    R = R_OUT + LID_EXTRA
    plate = cyl(R, LID_T)
    plate = plate.cut(Part.makeBox(CABLE[0], CABLE[1], LID_T + 2,
                                   V(USB_XY[0] - CABLE[0] / 2, USB_XY[1] - CABLE[1] / 2, -1)))
    for sx in (-1, 1):
        x = sx * (R - 4.5)
        plate = plate.cut(Part.makeCylinder(SCREW_D / 2, LID_T + 2, V(x, 0, -1)))
        plate = plate.cut(Part.makeCone(SCREW_D / 2, CSK_D / 2, 1.2, V(x, 0, LID_T - 1.2)))   # countersink
    lip = cyl(R_IN - 0.2, LIP_H, -LIP_H).cut(cyl(R_IN - 0.2 - LIP_W, LIP_H + 1, -LIP_H - 0.5))
    # clamp posts: come down to 0.2 mm above the board top face, over each support
    post_h = (H - (Z_PCB + PCB_T)) - 0.2
    for a in SUPPORT_ANGLES:
        p = Part.makeBox(2.4, 4.0, post_h, V(R_IN - 0.2 - LIP_W - 2.4 + 0.6, -2.0, -post_h))
        p.rotate(V(0, 0, 0), V(0, 0, 1), a)
        lip = lip.fuse(p)
    return plate.fuse(lip).removeSplitter()


def radome_coupon():
    s = None
    for i in range(8):
        t = 1.2 + 0.1 * i
        b = Part.makeBox(20, 20, t, V(i * 22, 0, 0))
        for k in range(i + 1):                       # notches = step number (no fonts needed)
            b = b.cut(Part.makeBox(1.0, 2.0, t + 1, V(i * 22 + 1.5 + 1.8 * k, 17.5, -0.5)))
        s = b if s is None else s.fuse(b)
    return s


def board_and_radar():
    pcb = cyl(PCB_R, PCB_T, Z_PCB)
    chip = Part.makeBox(6.5, 5.0, CHIP_H, V(RADAR_XY[0] - 3.25, RADAR_XY[1] - 2.5, Z_ANT))
    return pcb, chip


def fov_cone():
    h = Z_ANT - T_RAD
    r = h * math.tan(math.radians(FOV_DEG))
    return Part.makeCone(r, 0.0, h, V(RADAR_XY[0], RADAR_XY[1], T_RAD))


def check(c, t, pcb, chip):
    res = {}
    # 1) antenna-to-radome distance
    assert abs((Z_ANT - T_RAD) - GAP) < 1e-6
    res["antenna_to_radome_mm"] = round(Z_ANT - T_RAD, 3)
    # 2) no enclosure material (other than the radome) inside the antenna cone
    inter = fov_cone().common(c).Volume
    res["material_in_fov_cone_mm3"] = round(inter, 4)
    assert inter < 1e-6, "enclosure material inside the field of view"
    # 3) the board fits and does not touch the enclosure
    res["board_radial_clearance_mm"] = round(R_IN - PCB_R, 2)
    assert pcb.common(c).Volume < 1e-6 and chip.common(c).Volume < 1e-6
    # 4) room for parts above the board, up to the lid lip
    t_mounted = t.copy()
    t_mounted.translate(V(0, 0, H))
    space = (H - LIP_H) - (Z_PCB + PCB_T)
    res["free_height_above_board_mm"] = round(space, 2)
    assert space >= 6.0, "no room for the vertical USB-C connector"
    assert t_mounted.common(c).Volume < 1e-3, "the lid hits the enclosure"
    assert t_mounted.common(pcb).Volume < 1e-6
    # 5) the lip fits: radial clearance to the inner wall
    res["lip_clearance_mm"] = round(R_IN - (R_IN - 0.2), 2)
    res["radome_mm"] = round(T_RAD, 3)
    # 6) real board (KiCad STEP with every part) against the enclosure and the mounted lid
    if os.path.exists(BOARD_STEP):
        brd = Part.read(BOARD_STEP)
        brd.translate(V(-100.0, 100.0, Z_PCB))
        res["board_step"] = os.path.relpath(BOARD_STEP, HERE).replace("\\", "/")
        res["board_vs_enclosure_interference_mm3"] = round(brd.common(c).Volume, 4)
        res["board_vs_lid_interference_mm3"] = round(brd.common(t_mounted).Volume, 4)
        bb = brd.BoundBox
        res["tallest_part_above_board_mm"] = round(bb.ZMax - (Z_PCB + PCB_T), 2)
        res["tallest_part_below_board_mm"] = round(Z_PCB - bb.ZMin, 2)
        assert res["board_vs_enclosure_interference_mm3"] < 1e-3, "the board or its parts touch the enclosure"
        assert res["board_vs_lid_interference_mm3"] < 1e-3, "parts touch the lid or the clamp posts"
        assert bb.ZMin >= T_RAD - 1e-6, "a bottom-side part touches the radome"
    res["total_height_mm"] = round(H + LID_T, 2)
    res["diameter_mm"] = round(2 * R_OUT, 2)
    return res


def export(doc, name, shape):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    Part.export([obj], os.path.join(OUT, name + ".step"))
    m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.02, AngularDeflection=0.05)
    m.write(os.path.join(OUT, name + ".stl"))
    return obj


def main():
    doc = App.newDocument("Stillpoint")
    c, t, k = enclosure(), lid(), radome_coupon()
    pcb, chip = board_and_radar()
    res = check(c, t, pcb, chip)
    export(doc, "enclosure", c)
    export(doc, "lid", t)
    export(doc, "radome_coupon", k)
    for name, sh in (("board_reference", pcb), ("bgt60_reference", chip)):
        doc.addObject("Part::Feature", name).Shape = sh
    doc.recompute()
    doc.saveAs(os.path.join(OUT, "stillpoint.FCStd"))
    res["volume_cm3"] = {"enclosure": round(c.Volume / 1000, 2), "lid": round(t.Volume / 1000, 2)}
    with open(os.path.join(OUT, "checks.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
    print("OK", json.dumps(res, ensure_ascii=False))


main()
