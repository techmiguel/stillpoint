"""Rev A, paso 1: apilado de 4 capas, zonas prohibidas y colocación de la cara inferior.

Se ejecuta una sola vez sobre la placa con la cara superior ya colocada
(commit 91f0ae8):  python3 hardware/scripts/revA_1_colocacion.py
Necesita la API Python de KiCad 10 (pcbnew).

Geometría que se respeta (mechanical/freecad_carcasa.py, docs/09):
  * radar U1 en la cara inferior, centrado en la ventana del radomo (100, 100);
  * apoyos de la carcasa bajo la placa a 0°, 120° y 240° (r 27,4-30,4 mm, 6 mm de ancho);
  * antena del MGM260P: sin cobre en ninguna capa (descripción de la huella).
"""
from __future__ import annotations

import math
from pathlib import Path

import pcbnew

PCB = Path(__file__).resolve().parents[1] / "radar60.kicad_pcb"
mm = pcbnew.FromMM
CX, CY = 100.0, 100.0


def P(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def place(b, ref, x, y, rot, bottom=False):
    fp = b.FindFootprintByReference(ref)
    if bottom and fp.GetLayer() != pcbnew.B_Cu:
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    if not bottom and fp.GetLayer() != pcbnew.F_Cu:
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(P(x, y))
    return fp


def face(b, ref, net, toward):
    """Gira 180° un componente de 2 pads si el pad de `net` no es el más cercano a `toward`."""
    fp = b.FindFootprintByReference(ref)
    pads = list(fp.Pads())
    tx, ty = toward

    def d(p):
        q = p.GetPosition()
        return math.hypot(pcbnew.ToMM(q.x) - tx, pcbnew.ToMM(q.y) - ty)

    best = min(pads, key=d)
    if not best.GetNetname().endswith(net):
        fp.SetOrientationDegrees(fp.GetOrientationDegrees() + 180)


def rule_area(b, name, layers, pts, tracks=True, vias=True, pours=True, fps=False, pads=True):
    z = pcbnew.ZONE(b)
    z.SetIsRuleArea(True)
    z.SetZoneName(name)
    ls = pcbnew.LSET()
    for l in layers:
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    z.SetDoNotAllowTracks(tracks)
    z.SetDoNotAllowVias(vias)
    z.SetDoNotAllowZoneFills(pours)
    z.SetDoNotAllowPads(pads)
    z.SetDoNotAllowFootprints(fps)
    o = z.Outline()
    o.NewOutline()
    for x, y in pts:
        o.Append(mm(x), mm(y))
    b.Add(z)


def main():
    b = pcbnew.LoadBoard(str(PCB))

    # ---- 4 capas: F.Cu señal | In1 GND (plano) | In2 alimentación + GND | B.Cu radar
    b.SetCopperLayerCount(4)
    en = b.GetEnabledLayers()
    en.AddLayer(pcbnew.In1_Cu)
    en.AddLayer(pcbnew.In2_Cu)
    b.SetEnabledLayers(en)
    b.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    b.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_MIXED)
    b.SetLayerName(pcbnew.In1_Cu, "In1.Cu")
    b.SetLayerName(pcbnew.In2_Cu, "In2.Cu")
    b.GetDesignSettings().SetBoardThickness(mm(1.6))

    # ---- cara inferior: radar y su entorno inmediato
    place(b, "U1", CX, CY, 270, bottom=True)   # fila 1 (señales) hacia +x, columna M hacia +y
    # desacoplos de la columna M (VDDRF M1, VDDLF M3, VDDPLL M4, VDDVCO M6) y serie del reloj
    for ref, x in (("C5", 103.0), ("R4", 102.0), ("C15", 101.0), ("C6", 100.0), ("C7", 99.0)):
        place(b, ref, x, 105.9, 90, bottom=True)
    # fila 9 (VDDRF F9/G9) a la izquierda
    place(b, "C9", 95.7, 99.25, 0, bottom=True)
    place(b, "C10", 95.7, 100.75, 0, bottom=True)
    # fila 1: VDDD H1, VDDA J1, VAREF L1 a la derecha, tras las vías de las señales
    place(b, "C13", 105.4, 100.6, 0, bottom=True)
    place(b, "C11", 105.4, 101.6, 0, bottom=True)
    place(b, "C16", 105.4, 102.6, 0, bottom=True)
    # reloj de 80 MHz junto a R4 y su desacoplo
    place(b, "Y1", 105.6, 108.0, 180, bottom=True)
    place(b, "C17", 108.3, 108.0, 90, bottom=True)
    # ferritas y bulk de cada raíl del radar
    place(b, "FB1", 95.3, 105.0, 0, bottom=True)   # +1V8_RF
    place(b, "C8", 95.7, 102.6, 0, bottom=True)    # 1u RF
    place(b, "FB2", 107.6, 102.0, 90, bottom=True)  # +1V8_A
    place(b, "C12", 108.9, 102.0, 90, bottom=True)  # 1u A
    place(b, "FB3", 107.6, 98.6, 90, bottom=True)  # +1V8_D
    place(b, "C14", 108.9, 98.6, 90, bottom=True)  # 1u D
    # LED de estado visible desde la sala, bajo sus resistencias
    place(b, "D1", 100.0, 124.0, 0, bottom=True)

    # ---- cara superior: lo que faltaba
    place(b, "C22", 96.2, 88.3, 0)                  # bulk 3V3 del módulo (pad 15)
    place(b, "C23", 99.1, 87.7, 0)
    place(b, "R5", 109.6, 94.0, 0)                  # polarización CS_N a 1,8 V junto a U7
    place(b, "R6", 109.6, 95.1, 0)
    # holguras de patio en la cara superior (colocación previa)
    place(b, "C18", 99.5, 91.0, 90)
    place(b, "C20", 99.5, 99.5, 90)
    place(b, "C19", 108.5, 91.0, 90)
    place(b, "C21", 108.5, 99.5, 90)
    place(b, "TP6", 112.3, 91.7, 0)

    # el pad de alimentación de cada desacoplo hacia la bola correspondiente
    for ref, net, tgt in (("C5", "+1V8_RF", (102.0, 102.75)), ("R4", "RAD_OSC", (101.5, 102.75)),
                          ("C15", "+3V3_LF", (101.0, 102.75)), ("C6", "+1V8_RF", (100.5, 102.75)),
                          ("C7", "+1V8_RF", (99.5, 102.75)), ("C9", "+1V8_RF", (98.0, 99.75)),
                          ("C10", "+1V8_RF", (98.0, 100.25)), ("C13", "+1V8_D", (102.0, 100.75)),
                          ("C11", "+1V8_A", (102.0, 101.25)), ("C16", "VAREF", (102.0, 102.25)),
                          ("C17", "+1V8_D", (106.55, 107.25)), ("C8", "+1V8_RF", (98.0, 100.0)),
                          ("FB1", "+1V8_RF", (98.0, 101.0)), ("FB2", "+1V8_A", (105.0, 101.6)),
                          ("FB3", "+1V8_D", (105.0, 100.75)), ("C12", "+1V8_A", (107.6, 101.0)),
                          ("C14", "+1V8_D", (107.6, 100.0)), ("R5", "RAD_CS_N", (106.9, 94.0)),
                          ("R6", "RAD_DIO3", (106.9, 94.6))):
        face(b, ref, net, tgt)

    # ---- zonas prohibidas
    allcu = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
    u2 = b.FindFootprintByReference("U2").GetPosition()
    ux, uy = pcbnew.ToMM(u2.x), pcbnew.ToMM(u2.y)
    rule_area(b, "antena_MGM260P", allcu,
              [(ux - 4.4, uy - 9.0), (ux + 4.4, uy - 9.0), (ux + 4.4, uy - 2.7), (ux - 4.4, uy - 2.7)])
    # GND sólido en In2 bajo el encapsulado del radar (sin pistas ni vías de alimentación)
    rule_area(b, "radar_In2_GND_solido", [pcbnew.In2_Cu],
              [(96.4, 96.4), (103.6, 96.4), (103.6, 103.6), (96.4, 103.6)], tracks=True, vias=False,
              pours=False, pads=False)
    # apoyos de la carcasa (cara inferior): sin componentes
    for a in (0, 120, 240):
        th = math.radians(-a)   # FreeCAD (y arriba) -> KiCad (y abajo)
        c, s = math.cos(th), math.sin(th)
        pts = []
        for r, t in ((26.9, -3.6), (30.5, -3.6), (30.5, 3.6), (26.9, 3.6)):
            pts.append((CX + r * c - t * s, CY + r * s + t * c))
        rule_area(b, f"apoyo_carcasa_{a}", [pcbnew.B_Cu], pts, tracks=False, vias=False, pours=False,
                  fps=True, pads=False)

    b.Save(str(PCB))
    write_stackup()


# Apilado JLC04161H-7628 (4 capas, 1,6 mm), el estándar del fabricante con impedancia controlada.
STACKUP = """		(stackup
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
"""


def write_stackup():
    s = PCB.read_text(encoding="utf-8")
    if "(stackup" not in s:
        s = s.replace("\t(setup\n", "\t(setup\n" + STACKUP, 1)
        PCB.write_text(s, encoding="utf-8")


if __name__ == "__main__":
    main()
