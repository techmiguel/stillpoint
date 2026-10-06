#!/usr/bin/env bash
# Rev A: comprobaciones y ficheros de fabricación (JLCPCB / PCBWay).
#
#   bash hardware/scripts/fabricacion.sh
#
# Requiere KiCad 10 (kicad-cli). Rellena zonas, falla si el ERC o la DRC tienen
# errores, y deja en hardware/fab/revA/:
#   gerber/ (+ radar60_gerber.zip para subir), taladros y mapa, BOM y posiciones
#   (formato JLCPCB), PDF del esquema y de la placa, e informes ERC/DRC.
# Exporta además la placa montada a mechanical/cad/placa_revA.step, que usa
# mechanical/freecad_carcasa.py para comprobar interferencias con la carcasa.
# Los modelos 3D que faltan en la biblioteca de KiCad (USB-C y oscilador) están
# en hardware/lib/radar60.3dshapes y se enlazan en un directorio temporal.
set -euo pipefail
cd "$(dirname "$0")/.."
HW=$PWD
OUT=$HW/fab/revA
rm -rf "$OUT"
mkdir -p "$OUT/gerber"
PCB=radar60.kicad_pcb
SCH=radar60.kicad_sch

# ---- comprobaciones (ERC: solo errores; DRC: errores y avisos, con paridad)
kicad-cli sch erc --severity-error --exit-code-violations -o "$OUT/erc.rpt" $SCH
kicad-cli pcb drc --refill-zones --save-board --schematic-parity --severity-error \
  --exit-code-violations -o "$OUT/drc.rpt" $PCB
kicad-cli pcb drc --schematic-parity -o "$OUT/drc_completo.rpt" $PCB >/dev/null || true

# ---- Gerber (4 capas) y taladros
kicad-cli pcb export gerbers --no-protel-ext --subtract-soldermask -o "$OUT/gerber/" \
  -l F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts $PCB
kicad-cli pcb export drill --format excellon --excellon-separate-th --generate-map \
  --map-format gerberx2 -o "$OUT/gerber/" $PCB
(cd "$OUT/gerber" && zip -q -r ../radar60_gerber.zip .)

# ---- BOM (formato JLCPCB; la columna LCSC se rellena al elegir piezas)
kicad-cli sch export bom --exclude-dnp --group-by Value,Footprint \
  --fields 'Value,Reference,Footprint,${QUANTITY},Datasheet' \
  --labels 'Comment,Designator,Footprint,Quantity,Datasheet' -o "$OUT/bom.csv" $SCH

# ---- posiciones (CPL de JLCPCB): solo lo que va en la BOM
kicad-cli pcb export pos --format csv --units mm --side both --exclude-dnp -o "$OUT/pos_kicad.csv" $PCB
python3 - "$OUT" <<'EOF'
import csv, re, sys
from pathlib import Path
out = Path(sys.argv[1])


def expand(des):
    """KiCad agrupa en rangos (C5-C7); JLCPCB necesita cada referencia."""
    refs = []
    for part in des.split(","):
        m = re.fullmatch(r"([A-Z]+)(\d+)-([A-Z]+)(\d+)", part.strip())
        if m:
            refs += [f"{m.group(1)}{i}" for i in range(int(m.group(2)), int(m.group(4)) + 1)]
        elif part.strip():
            refs.append(part.strip())
    return refs


rows = list(csv.DictReader(open(out / "bom.csv", encoding="utf-8")))
refs = set()
for row in rows:
    row["Designator"] = ",".join(expand(row["Designator"]))
    refs.update(row["Designator"].split(","))
with open(out / "bom.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["Comment", "Designator", "Footprint", "Quantity", "LCSC", "Datasheet"])
    w.writeheader()
    for row in rows:
        w.writerow({**row, "LCSC": ""})
with open(out / "cpl.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for r in csv.DictReader(open(out / "pos_kicad.csv", encoding="utf-8")):
        if r["Ref"] in refs:
            w.writerow([r["Ref"], f'{float(r["PosX"]):.4f}mm', f'{float(r["PosY"]):.4f}mm',
                        "Top" if r["Side"] == "top" else "Bottom", r["Rot"]])
print("CPL:", len(refs), "componentes")
EOF

# ---- documentación de revisión
kicad-cli sch export pdf -o "$OUT/esquema.pdf" $SCH
kicad-cli pcb export pdf --mode-multipage --ibt -l F.Cu,In1.Cu,In2.Cu,B.Cu,F.SilkS,B.SilkS,Edge.Cuts \
  --cl Edge.Cuts -o "$OUT/placa.pdf" $PCB

# ---- placa montada para la comprobación mecánica
M3D=$(mktemp -d)
cp -r /usr/share/kicad/3dmodels/. "$M3D/" 2>/dev/null || true
mkdir -p "$M3D/Connector_USB.3dshapes" "$M3D/Oscillator.3dshapes"
cp lib/radar60.3dshapes/USB_C_Receptacle_G-Switch_GT-USB-7051x.step "$M3D/Connector_USB.3dshapes/"
cp lib/radar60.3dshapes/Oscillator_SMD_SiT_PQFN-4Pin_2.5x2.0mm.step "$M3D/Oscillator.3dshapes/"
KICAD10_3DMODEL_DIR=$M3D kicad-cli pcb export step --user-origin 100x100mm --subst-models -f \
  -o "$HW/../mechanical/cad/placa_revA.step" $PCB
rm -rf "$M3D"
echo "ficheros en $OUT"
