#!/bin/sh
# Rebuilds hardware/radar60.kicad_pcb from the schematic: placement, planes, hand-planned
# radar fan-out / supply rails / USB breakout, plane vias, Freerouting for the rest,
# pours, clean-up and silkscreen. Needs KiCad 10 and, for routing, Java 25 + the
# Freerouting 2.5.0 jar (JAVA=... FREEROUTING_JAR=... sh tools/pcb_build/pipeline.sh).
set -e
cd "$(dirname "$0")"
KP="${KICAD_PYTHON:-C:/Program Files/KiCad/10.0/bin/python.exe}"
CLI="${KICAD_CLI:-C:/Program Files/KiCad/10.0/bin/kicad-cli.exe}"
mkdir -p build
"$CLI" sch export netlist --format kicadxml -o build/radar60.xml ../../hardware/radar60.kicad_sch >/dev/null
for s in build zones prerout rails jbreak gndvias route zones finalize dangling c16fix thermal silk legends; do
  echo "== $s"; "$KP" -u $s.py 2>&1 | grep -v -E "swig/python|image handler" || true
done
"$CLI" pcb drc --severity-all --exit-code-violations -o build/drc.rpt ../../hardware/radar60.kicad_pcb && echo "DRC clean"
