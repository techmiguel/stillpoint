"""Modelo paramétrico de la carcasa en FreeCAD (sólidos B-rep).

Ejecutar con el intérprete de FreeCAD (sin interfaz):
  "C:\\Program Files\\FreeCAD 1.1\\bin\\freecadcmd.exe" -c "exec(open(r'mechanical/freecad_carcasa.py').read())"

Salidas en mechanical/cad/: radar60.FCStd (documento editable), carcasa/tapa/
cupon .step y .stl, y comprobaciones.json. Las comprobaciones son aserciones:
si una cota no cumple, el script falla y no exporta.

Si existe mechanical/cad/placa_revA.step (la placa montada, exportada desde
KiCad con hardware/scripts/fabricacion.sh), se comprueba además el conjunto
real: componentes contra carcasa, tapa y cono de las antenas, y el paso de la
clavija USB-C por la tapa.
"""
import json
import math
import os

import FreeCAD as App
import Mesh
import MeshPart
import Part

V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.join(os.getcwd(), "mechanical")
OUT = os.path.join(HERE, "cad")
os.makedirs(OUT, exist_ok=True)

# ---- parámetros (mismos que generar.py / radomo.scad) -------------------------
EPS_R = 2.8
LAMBDA0 = 299792458.0 / 60.6e9 * 1e3        # 4,95 mm
T_RAD = LAMBDA0 / (2 * math.sqrt(EPS_R))     # radomo λ/2 en el material
GAP = LAMBDA0                                # antenas (cara inferior del chip) -> cara interior del radomo
CHIP_H = 0.9                                 # alto del BGT60TR13C bajo la placa
PCB_R, PCB_T = 30.0, 1.6
CLEAR = 0.4
R_IN = PCB_R + CLEAR
WALL = 2.0
R_OUT = R_IN + WALL
H_INNER = 14.0
Z_ANT = T_RAD + GAP                          # plano de antenas
Z_PCB = Z_ANT + CHIP_H                       # cara inferior de la placa
H = Z_PCB + H_INNER                          # altura total de la carcasa
LID_T, LID_EXTRA = 2.4, 6.0
LIP_H, LIP_W = 4.0, 1.2
CABLE = (14.0, 9.0)                          # paso del conector USB-C vertical + funda
CABLE_XY = (0.0, -16.0)                      # sobre J1: KiCad (100, 116) -> carcasa (x - 100, 100 - y)
PLUG = (12.4, 6.6)                           # funda típica de una clavija USB-C (mayor que la mayoría)
PCB_STEP = os.path.join(OUT, "placa_revA.step")
SCREW_D, CSK_D = 4.2, 8.4
FOV_DEG = 60.0                               # semiángulo útil de las antenas


def cyl(r, h, z=0.0):
    return Part.makeCylinder(r, h, V(0, 0, z))


def carcasa():
    body = cyl(R_OUT, H).cut(cyl(R_IN, H, T_RAD))
    # apoyos de la placa: la placa descansa en Z_PCB -> antenas exactamente a GAP del radomo
    for a in (0, 120, 240):
        s = Part.makeBox(3.0, 6.0, Z_PCB - T_RAD, V(R_IN - 3.0, -3.0, T_RAD))
        s.rotate(V(0, 0, 0), V(0, 0, 1), a)
        body = body.fuse(s)
    # ventilación en la mitad superior, lejos del cono de las antenas
    for a in range(30, 360, 60):
        slot = Part.makeBox(WALL + 2, 3.0, 4.0, V(R_IN - 1, -1.5, Z_PCB + 8))
        slot.rotate(V(0, 0, 0), V(0, 0, 1), a)
        body = body.cut(slot)
    # chaflán del borde exterior inferior (estética, no toca el radomo útil)
    edges = [e for e in body.Edges if abs(e.BoundBox.ZMax) < 1e-6 and abs(e.BoundBox.XMax - R_OUT) < 1e-3]
    if edges:
        body = body.makeChamfer(0.8, edges)
    return body.removeSplitter()


def tapa():
    R = R_OUT + LID_EXTRA
    plate = cyl(R, LID_T)
    plate = plate.cut(Part.makeBox(CABLE[0], CABLE[1], LID_T + 2,
                                   V(CABLE_XY[0] - CABLE[0] / 2, CABLE_XY[1] - CABLE[1] / 2, -1)))
    for sx in (-1, 1):
        x = sx * (R - 4.5)
        plate = plate.cut(Part.makeCylinder(SCREW_D / 2, LID_T + 2, V(x, 0, -1)))
        plate = plate.cut(Part.makeCone(SCREW_D / 2, CSK_D / 2, 1.2, V(x, 0, LID_T - 1.2)))   # avellanado
    lip = cyl(R_IN - 0.2, LIP_H, -LIP_H).cut(cyl(R_IN - 0.2 - LIP_W, LIP_H + 1, -LIP_H - 0.5))
    return plate.fuse(lip).removeSplitter()


def cupon():
    s = None
    for i in range(8):
        t = 1.2 + 0.1 * i
        b = Part.makeBox(20, 20, t, V(i * 22, 0, 0))
        for k in range(i + 1):                       # muescas = número de escalón (sin fuentes)
            b = b.cut(Part.makeBox(1.0, 2.0, t + 1, V(i * 22 + 1.5 + 1.8 * k, 17.5, -0.5)))
        s = b if s is None else s.fuse(b)
    return s


def placa_y_radar():
    pcb = cyl(PCB_R, PCB_T, Z_PCB)
    chip = Part.makeBox(6.5, 5.0, CHIP_H, V(-3.25, -2.5, Z_ANT))
    return pcb, chip


def cono_fov():
    h = Z_ANT - T_RAD
    r = h * math.tan(math.radians(FOV_DEG))
    return Part.makeCone(r, 0.0, h, V(0, 0, T_RAD))


def comprobar(c, t, pcb, chip):
    res = {}
    # 1) distancia antena-radomo
    assert abs((Z_ANT - T_RAD) - GAP) < 1e-6
    res["antena_radomo_mm"] = round(Z_ANT - T_RAD, 3)
    # 2) nada de la carcasa (salvo el radomo) dentro del cono útil de las antenas
    inter = cono_fov().common(c).Volume
    res["material_en_cono_FOV_mm3"] = round(inter, 4)
    assert inter < 1e-6, "hay material de la carcasa en el campo de visión"
    # 3) la placa cabe y no interfiere con la carcasa
    res["holgura_radial_placa_mm"] = round(R_IN - PCB_R, 2)
    assert pcb.common(c).Volume < 1e-6 and chip.common(c).Volume < 1e-6
    # 4) espacio para componentes sobre la placa hasta el labio de la tapa
    t_mounted = t.copy()
    t_mounted.translate(V(0, 0, H))
    space = (H - LIP_H) - (Z_PCB + PCB_T)
    res["altura_libre_sobre_placa_mm"] = round(space, 2)
    assert space >= 6.0, "no cabe el conector USB-C vertical"
    assert t_mounted.common(c).Volume < 1e-3, "la tapa interfiere con la carcasa"
    assert t_mounted.common(pcb).Volume < 1e-6
    # 5) el labio encaja: holgura radial con la pared interior
    res["holgura_labio_mm"] = round(R_IN - (R_IN - 0.2), 2)
    res["radomo_mm"] = round(T_RAD, 3)
    res["altura_total_mm"] = round(H + LID_T, 2)
    res["diametro_mm"] = round(2 * R_OUT, 2)
    if os.path.exists(PCB_STEP):
        res.update(comprobar_conjunto(c, t_mounted))
    return res


def placa_real():
    """Placa montada (KiCad, origen en el centro): cara inferior de la placa en Z_PCB."""
    sh = Part.Shape()
    sh.read(PCB_STEP)
    bb = sh.BoundBox
    # el exportador de KiCad deja la cara inferior de la placa en z = 0
    sh.translate(V(0, 0, Z_PCB))
    return sh, bb


def comprobar_conjunto(c, t_mounted):
    res = {}
    asm, bb = placa_real()
    solids = asm.Solids
    v_c = sum(s.common(c).Volume for s in solids)
    v_t = sum(s.common(t_mounted).Volume for s in solids)
    cone = cono_fov()
    # el propio radar toca el vértice del cono (sus antenas están en ese plano): se excluye
    v_fov = sum(s.common(cone).Volume for s in solids if s.BoundBox.ZMin > Z_ANT - 1e-3 and
                not (abs(s.BoundBox.Center.x) < 4 and abs(s.BoundBox.Center.y) < 4 and s.BoundBox.ZMax <= Z_PCB + 1e-3))
    # la clavija se coloca sobre el J1 real (el componente más alto de la cara superior), no sobre el agujero
    j1 = max(solids, key=lambda s: s.BoundBox.ZMax).BoundBox
    plug = Part.makeBox(PLUG[0], PLUG[1], 30.0,
                        V(j1.Center.x - PLUG[0] / 2, j1.Center.y - PLUG[1] / 2, j1.ZMax))
    res["usb_c_centro_mm"] = [round(j1.Center.x, 2), round(j1.Center.y, 2)]
    v_plug = plug.common(t_mounted).Volume
    top = max(s.BoundBox.ZMax for s in solids) - (Z_PCB + PCB_T)
    bottom = (Z_PCB) - min(s.BoundBox.ZMin for s in solids)
    res.update({
        "conjunto_placa_carcasa_mm3": round(v_c, 4),
        "conjunto_placa_tapa_mm3": round(v_t, 4),
        "conjunto_componentes_en_cono_FOV_mm3": round(v_fov, 4),
        "clavija_usb_contra_tapa_mm3": round(v_plug, 4),
        "componente_mas_alto_cara_superior_mm": round(top, 2),
        "componente_mas_alto_cara_inferior_mm": round(bottom, 2),
    })
    assert v_c < 1e-3, f"la placa montada interfiere con la carcasa ({v_c:.3f} mm3)"
    assert v_t < 1e-3, f"la placa montada interfiere con la tapa ({v_t:.3f} mm3)"
    assert v_fov < 1e-3, "hay componentes en el campo de visión de las antenas"
    assert v_plug < 1e-3, "la clavija USB-C no pasa por la tapa"
    return res


def export(doc, name, shape):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    Part.export([obj], os.path.join(OUT, name + ".step"))
    m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.05, AngularDeflection=0.2)
    m.write(os.path.join(OUT, name + ".stl"))
    return obj


def main():
    doc = App.newDocument("radar60")
    c, t, k = carcasa(), tapa(), cupon()
    pcb, chip = placa_y_radar()
    res = comprobar(c, t, pcb, chip)
    export(doc, "carcasa", c)
    export(doc, "tapa", t)
    export(doc, "cupon_radomo", k)
    for name, sh in (("placa_referencia", pcb), ("bgt60_referencia", chip)):
        doc.addObject("Part::Feature", name).Shape = sh
    doc.recompute()
    doc.saveAs(os.path.join(OUT, "radar60.FCStd"))
    res["volumen_cm3"] = {"carcasa": round(c.Volume / 1000, 2), "tapa": round(t.Volume / 1000, 2)}
    with open(os.path.join(OUT, "comprobaciones.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
    print("OK", json.dumps(res, ensure_ascii=False))


main()
