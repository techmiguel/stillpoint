"""Rev A, paso 2: rutado manual del entorno del radar (cara inferior) y planos de GND.

Se ejecuta tras revA_1_colocacion.py:  python3 hardware/scripts/revA_2_radar.py
Todo lo que traza queda bloqueado (el autorutado posterior no lo toca).

Criterios:
  * cada bola de alimentación va directa a su desacoplo, sin vía entre ambos;
  * el reloj de 80 MHz (M2 -> R4 -> Y1) va entero por B.Cu sobre GND continuo (In2);
  * las señales SPI/IRQ salen de la fila 1 hacia +x a vías escalonadas bajo el
    cuerpo de U8 (en la cara superior ahí no hay pads);
  * vías de GND dentro del anillo de bolas solo donde la cara superior está libre.
"""
from __future__ import annotations

import math
from pathlib import Path

import pcbnew

PCB = Path(__file__).resolve().parents[1] / "radar60.kicad_pcb"
mm = pcbnew.FromMM
B, F, I1, I2 = pcbnew.B_Cu, pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu


class Router:
    def __init__(self, board):
        self.b = board

    def net(self, name):
        n = self.b.FindNet("/" + name)
        assert n is not None, name
        return n

    def track(self, net, pts, w=0.2, layer=B):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(self.b)
            t.SetStart(pcbnew.VECTOR2I(mm(x0), mm(y0)))
            t.SetEnd(pcbnew.VECTOR2I(mm(x1), mm(y1)))
            t.SetWidth(mm(w))
            t.SetLayer(layer)
            t.SetNet(self.net(net))
            t.SetLocked(True)
            self.b.Add(t)

    def via(self, net, x, y, d=0.45, drill=0.2):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        v.SetWidth(mm(d))
        v.SetDrill(mm(drill))
        v.SetLayerPair(F, B)
        v.SetNet(self.net(net))
        v.SetLocked(True)
        self.b.Add(v)


def split_junctions(b):
    """Parte cada pista fija donde otra pista o vía de la misma red la toca a mitad de tramo.

    KiCad ya lo trata como conectado, pero Freerouting solo reconoce uniones en los extremos."""
    tol = mm(0.001)
    changed = True
    while changed:
        changed = False
        tracks = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and t.IsLocked()]
        pts = {}
        for t in b.GetTracks():
            if t.GetClass() == "PCB_VIA":
                pts.setdefault(t.GetNetCode(), []).append((t.GetPosition(), None))
            elif t.GetClass() == "PCB_TRACK":
                for q in (t.GetStart(), t.GetEnd()):
                    pts.setdefault(t.GetNetCode(), []).append((q, t.GetLayer()))
        for t in tracks:
            a, c = t.GetStart(), t.GetEnd()
            seg = pcbnew.SEG(a, c)
            for q, layer in pts.get(t.GetNetCode(), []):
                if layer is not None and layer != t.GetLayer():
                    continue
                if (q - a).EuclideanNorm() <= tol or (q - c).EuclideanNorm() <= tol:
                    continue
                if seg.Distance(q) <= tol:
                    t2 = pcbnew.PCB_TRACK(b)
                    t2.SetStart(q)
                    t2.SetEnd(c)
                    t2.SetWidth(t.GetWidth())
                    t2.SetLayer(t.GetLayer())
                    t2.SetNet(t.GetNet())
                    t2.SetLocked(True)
                    t.SetEnd(q)
                    b.Add(t2)
                    changed = True
                    break
            if changed:
                break


def gnd_zone(b, layer, priority, solid=False):
    z = pcbnew.ZONE(b)
    z.SetLayer(layer)
    z.SetNet(b.FindNet("/GND"))
    z.SetAssignedPriority(priority)
    z.SetLocalClearance(mm(0.2))
    z.SetMinThickness(mm(0.15))
    z.SetThermalReliefGap(mm(0.2))
    z.SetThermalReliefSpokeWidth(mm(0.25))
    # conexión sólida en todas: los pads finos del BGA y los pasantes del USB-C no admiten radios suficientes
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetZoneName(f"GND_{b.GetLayerName(layer)}")
    o = z.Outline()
    o.NewOutline()
    for i in range(96):
        a = 2 * math.pi * i / 96
        o.Append(mm(100 + 30.2 * math.cos(a)), mm(100 + 30.2 * math.sin(a)))
    b.Add(z)


def main():
    b = pcbnew.LoadBoard(str(PCB))
    r = Router(b)

    # ---- fila 1 (x = 102): señales a vías escalonadas
    for y, x_via, net in ((97.75, 103.2, "RAD_CLK"), (98.25, 104.0, "RAD_IRQ"), (98.75, 103.2, "RAD_DI"),
                          (99.25, 104.0, "RAD_DO"), (99.75, 103.2, "RAD_DIO3"), (100.25, 104.0, "RAD_CS_N")):
        r.track(net, [(102.0, y), (x_via, y)], w=0.15)
        r.via(net, x_via, y)
    # VDDD H1 -> C13; VDDA J1 -> C11 (+ vía al raíl en In2); VAREF L1 -> C16
    r.track("+1V8_D", [(102.0, 100.75), (104.92, 100.75)], w=0.2)
    r.track("+1V8_A", [(102.0, 101.25), (104.4, 101.25), (104.92, 101.6)], w=0.2)
    r.via("+1V8_A", 103.75, 101.25)
    # a la derecha de U8 (cara superior) para no caer en sus pads
    r.track("+1V8_A", [(103.75, 101.25), (108.5, 101.25), (109.0, 100.7)], w=0.25, layer=I2)
    r.via("+1V8_A", 109.0, 100.7)
    r.track("+1V8_A", [(109.0, 100.7), (108.9, 101.52)], w=0.3)
    r.track("+1V8_A", [(107.6, 101.21), (108.4, 101.21), (108.9, 101.52)], w=0.3)       # C12
    r.track("VAREF", [(102.0, 102.25), (104.5, 102.25), (104.92, 102.6)], w=0.2)
    # FB3 -> C13 por encima de los desacoplos; C14 junto a FB3
    r.track("+1V8_D", [(107.6, 99.39), (107.1, 99.9), (104.92, 99.9), (104.92, 100.6)], w=0.25)
    r.track("+1V8_D", [(107.6, 99.39), (108.4, 99.39), (108.9, 99.08)], w=0.3)

    # ---- columna M (y = 102.75)
    r.track("+1V8_RF", [(102.0, 102.75), (102.6, 103.35), (103.0, 103.75), (103.0, 105.42)], w=0.2)   # M1 -> C5
    r.track("RAD_OSC", [(101.5, 102.75), (101.5, 103.3), (102.0, 103.8), (102.0, 105.39)], w=0.2)     # M2 -> R4
    r.track("+3V3_LF", [(101.0, 102.75), (101.0, 105.42)], w=0.25)                                    # M3 -> C15
    r.track("+1V8_RF", [(100.5, 102.75), (100.5, 103.3), (100.0, 103.8), (100.0, 105.42)], w=0.2)    # M4 -> C6
    r.track("+1V8_RF", [(99.5, 102.75), (99.5, 103.3), (99.0, 103.8), (99.0, 105.42)], w=0.2)        # M6 -> C7
    r.via("+3V3_LF", 101.0, 104.95)
    # raíl RF: M6/M4 por B.Cu, M1 por In2 (por debajo de la vía de VDDLF)
    r.track("+1V8_RF", [(96.9, 104.4), (100.0, 104.4)], w=0.25)
    r.via("+1V8_RF", 100.0, 104.4)
    r.via("+1V8_RF", 103.0, 104.4)
    r.track("+1V8_RF", [(100.0, 104.4), (103.0, 104.4)], w=0.25, layer=I2)

    # ---- fila 9 (x = 98): F9/G9 -> C9/C10, raíl vertical a C8 y FB1
    r.track("+1V8_RF", [(98.0, 99.75), (96.9, 99.75)], w=0.2)
    r.track("+1V8_RF", [(98.0, 100.25), (96.9, 100.25)], w=0.2)
    r.track("+1V8_RF", [(96.9, 99.25), (96.9, 104.4)], w=0.25)
    for y in (99.25, 100.75, 102.6):
        r.track("+1V8_RF", [(96.9, y), (96.18, y)], w=0.25)
    r.track("+1V8_RF", [(96.9, 104.4), (96.5, 104.8), (96.09, 105.0)], w=0.3)

    # ---- reloj: R4 -> Y1 OUT; alimentación y desacoplo de Y1
    r.track("OSC_OUT", [(102.0, 106.41), (102.0, 107.25), (104.65, 107.25)], w=0.2)
    r.track("+1V8_D", [(106.55, 107.25), (106.55, 108.75)], w=0.3)
    r.track("+1V8_D", [(106.55, 107.25), (108.0, 107.25), (108.3, 107.52)], w=0.3)
    r.via("+1V8_D", 106.55, 106.3)
    r.track("+1V8_D", [(106.55, 106.3), (106.55, 107.25)], w=0.3)

    # ---- GND: dentro del anillo (cara superior libre en esos puntos) y junto a cada desacoplo
    for x, y in ((99.6, 98.3), (100.9, 98.3), (98.7, 100.0), (99.6, 101.2), (98.7, 101.8)):
        r.via("GND", x, y)
    for x, y in ((99.0, 107.0), (100.0, 107.0), (101.0, 107.0), (103.6, 106.4), (104.65, 109.75),
                 (108.3, 109.25), (94.4, 99.25), (94.4, 100.75), (94.4, 102.6)):
        r.via("GND", x, y)
    # bolas de GND interiores (B3, B4, B8) con su vecina del borde
    for (x0, y0), (x1, y1) in (((101.0, 97.75), (101.0, 97.25)), ((100.5, 97.75), (100.5, 97.25)),
                               ((98.5, 97.75), (98.5, 97.25))):
        r.track("GND", [(x0, y0), (x1, y1)], w=0.15)

    split_junctions(b)

    # ---- planos: In1 GND entero; F.Cu, In2 y B.Cu GND de relleno
    gnd_zone(b, I1, 0)
    gnd_zone(b, F, 0)
    gnd_zone(b, I2, 0)
    gnd_zone(b, B, 0, solid=True)

    b.Save(str(PCB))


if __name__ == "__main__":
    main()
