"""Rev A, paso 10: cambios derivados de la revisión con las hojas de datos (docs/referencias).

  python3 hardware/scripts/revA_10_hojas_de_datos.py      (esquema y placa)

Después: revA_8_huellas.py (pads del BGA a Ø0,275), revA_7_acabado.py
(descripciones) y fabricacion.sh. Origen de cada cambio en docs/09_hardware.md.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HW = Path(__file__).resolve().parents[1]
SCH = HW / "radar60.kicad_sch"
PCB = HW / "radar60.kicad_pcb"

# referencia -> (valor, hoja de datos o None para no tocarla)
VALUES = {
    "C16": ("470n", None),      # VAREF: Cb2 = 470 nF de baja ESR (hoja del BGT60TR13C, MADC)
    "C8": ("10u", None),        # VDDRF: 10 µF + 1 µF + 1 µF como la placa de referencia de Infineon
    "C9": ("1u", None),
    "C10": ("1u", None),
    "C12": ("10u", None),       # VDDA: 10 µF tras la ferrita (referencia de Infineon)
    "C17": ("1u", None),        # alimentación del oscilador
    "C15": ("10u", None),       # VDDLF: filtro RC con R13 (≤ 0,5 mA de consumo)
    "C25": ("4.7u", None),      # CP2102N: 4,7 µF + 0,1 µF por pin de alimentación
    "R4": ("150", None),        # serie del reloj: valor de partida de Infineon (se ajusta en F2)
    "U4": ("TPS7A2018PDBVR", "https://www.ti.com/lit/ds/symlink/tps7a20.pdf"),   # 7 µVrms, mismo patillaje
    "U2": ("MGM260PB22VNA5", None),   # +10 dBm, antena integrada (código completo)
    # el SiT8008 (MEMS) da 1,3-2 ps de jitter 12 kHz-20 MHz y el radar pide 1 ps: XO de cuarzo de la
    # misma familia que el de la placa de referencia (Kyocera K), mismo patrón 2520 y patillaje
    "Y1": ("KC2520K80.0000", ""),
}
# FB4 (ferrita de VDDLF) pasa a ser R13 (47 Ω): mismos puntos de conexión en el esquema
FB4_NEW = {"ref": "R13", "value": "47", "lib_id": "Device:R_Small",
           "footprint": "Resistor_SMD:R_0603_1608Metric", "descr": "Resistor, small symbol"}


def sexpr_end(s: str, i: int) -> int:
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "(":
            depth += 1
        elif s[j] == ")":
            depth -= 1
            if depth == 0:
                return j + 1
    raise ValueError("s-expresión sin cerrar")


def symbol_blocks(s: str):
    pos = 0
    while (i := s.find("\n\t(symbol\n", pos)) >= 0:
        j = sexpr_end(s, i + 1)
        yield i + 1, j
        pos = j


def set_prop(blk: str, name: str, value: str) -> str:
    return re.sub(rf'(\(property "{name}" )"[^"]*"', lambda m: f'{m.group(1)}"{value}"', blk, count=1)


def schematic():
    s = SCH.read_text(encoding="utf-8")
    # símbolo R_Small en la caché del esquema
    if '(symbol "Device:R_Small"' not in s:
        lib = Path("/usr/share/kicad/symbols/Device.kicad_sym").read_text(encoding="utf-8")
        i = lib.index('(symbol "R_Small"')
        blk = lib[i:sexpr_end(lib, i)].replace('(symbol "R_Small"', '(symbol "Device:R_Small"', 1)
        k = s.index("(lib_symbols") + len("(lib_symbols")
        s = s[:k] + "\n" + blk + s[k:]
    out, last = [], 0
    for i, j in symbol_blocks(s):
        blk = s[i:j]
        m = re.search(r'\(property "Reference" "([^"]+)"', blk)
        ref = m.group(1) if m else None
        if ref in VALUES:
            val, ds = VALUES[ref]
            blk = set_prop(blk, "Value", val)
            if ds is not None:
                blk = set_prop(blk, "Datasheet", ds)
        elif ref == "FB4":
            blk = blk.replace('(lib_id "Device:FerriteBead_Small")', f'(lib_id "{FB4_NEW["lib_id"]}")', 1)
            blk = set_prop(blk, "Reference", FB4_NEW["ref"])
            blk = set_prop(blk, "Value", FB4_NEW["value"])
            blk = set_prop(blk, "Footprint", FB4_NEW["footprint"])
            blk = set_prop(blk, "Description", FB4_NEW["descr"])
            blk = blk.replace('(reference "FB4")', f'(reference "{FB4_NEW["ref"]}")')
        out.append(s[last:i])
        out.append(blk)
        last = j
    out.append(s[last:])
    SCH.write_text("".join(out), encoding="utf-8")
    print("esquema actualizado")


def board():
    import pcbnew
    b = pcbnew.LoadBoard(str(PCB))
    old = None
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref in VALUES:
            fp.SetValue(VALUES[ref][0])
        if ref == "FB4":
            old = fp
    if old is not None:
        new = pcbnew.FootprintLoad("/usr/share/kicad/footprints/Resistor_SMD.pretty", "R_0603_1608Metric")
        new.SetFPID(pcbnew.LIB_ID("Resistor_SMD", "R_0603_1608Metric"))
        new.SetParent(b)
        new.SetPosition(old.GetPosition())
        if old.GetLayer() == pcbnew.B_Cu:
            new.Flip(new.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        new.SetOrientation(old.GetOrientation())
        new.SetPath(old.GetPath())
        new.SetSheetname(old.GetSheetname())
        new.SetSheetfile(old.GetSheetfile())
        new.SetReference(FB4_NEW["ref"])
        new.SetValue(FB4_NEW["value"])
        rf, of = new.Reference(), old.Reference()
        rf.SetPosition(of.GetPosition())
        rf.SetVisible(of.IsVisible())
        rf.SetTextSize(of.GetTextSize())
        rf.SetTextThickness(of.GetTextThickness())
        nets = {p.GetNumber(): p.GetNet() for p in old.Pads()}
        for p in new.Pads():
            p.SetNet(nets[p.GetNumber()])
        b.Add(new)
        b.Remove(old)          # al final: tras Remove() la capa SWIG deja de ser fiable
    b.Save(str(PCB))
    print("placa actualizada")


if __name__ == "__main__":
    if sys.argv[1:] == ["--placa"]:
        board()
    else:
        schematic()
        subprocess.run([sys.executable, __file__, "--placa"], check=True)
