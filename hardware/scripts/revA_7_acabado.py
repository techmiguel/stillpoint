"""Rev A, paso 7: acabado (descripciones desde el esquema y marcas de pin 1 de U7/U8).

  python3 hardware/scripts/revA_7_acabado.py
"""
import re
import subprocess
import tempfile
from pathlib import Path

import pcbnew

HW = Path(__file__).resolve().parents[1]
PCB = HW / "radar60.kicad_pcb"


def descriptions():
    net = Path(tempfile.mkdtemp()) / "radar60.net"
    subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(net),
                    str(HW / "radar60.kicad_sch")], check=True, capture_output=True)
    s = net.read_text(encoding="utf-8")
    s = s[s.index("(components"):s.index("(libparts")]
    out = {}
    for blk in re.split(r"\n\t\t\(comp\b", s)[1:]:
        ref = re.search(r'\(ref "([^"]+)"\)', blk).group(1)
        d = re.search(r'\(description "((?:[^"\\]|\\.)*)"\)', blk)
        ds = re.search(r'\(datasheet "((?:[^"\\]|\\.)*)"\)', blk)
        out[ref] = (d.group(1) if d else "", ds.group(1) if ds and ds.group(1) != "~" else "")
    return out


def main():
    desc = descriptions()
    b = pcbnew.LoadBoard(str(PCB))
    for fp in b.GetFootprints():
        if fp.GetReference() in desc:
            d, ds = desc[fp.GetReference()]
            fp.SetLibDescription(d)
            fp.SetField("Description", d)
            fp.SetField("Datasheet", ds)
        # triángulo de pin 1 de los traductores: fuera de los pads de C18/C20, sobre el pin 1
        if fp.GetReference() in ("U7", "U8"):
            for g in fp.GraphicalItems():
                if g.GetLayer() == pcbnew.F_SilkS and g.GetClass() == "PCB_SHAPE" and g.GetShapeStr() == "Polygon":
                    if g.GetBoundingBox().GetLeft() < pcbnew.FromMM(100.3):   # idempotente
                        g.Move(pcbnew.VECTOR2I(pcbnew.FromMM(0.45), pcbnew.FromMM(-0.87)))
    b.Save(str(PCB))


if __name__ == "__main__":
    main()
