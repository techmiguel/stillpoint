# tools/pcb_build

Scripts that build `hardware/radar60.kicad_pcb` from the schematic. The board is not
drawn by hand: placement and every critical route are written down here, so they can be
reviewed and repeated.

| Step | Script | What it does |
|---|---|---|
| 1 | `build.py` + `placement.py` | footprints from the schematic netlist (with MPN/LCSC), nets and the placement of every part |
| 2 | `zones.py` | planes (L2 GND, L3 +3V3 with a GND island under the radar), GND pours, antenna keep-out, enclosure support pads, stackup |
| 3 | `prerout.py` | radar BGA escape (two staggered via rows), IRQ/DO lanes to U8, oscillator, GND vias under the chip |
| 4 | `rails.py` | one straight lane per radar supply domain (via → 100 n → 1 µ → 10 µ → ferrite), +1V8_RAD bus, CP2102N |
| 5 | `jbreak.py` | vertical USB-C breakout (VBUS through the row gap, D-/D+ crossed) and the USB pair through the ESD part to the CP2102N |
| 6 | `gndvias.py` | one plane via per GND or +3V3 pad |
| 7 | `route.py` | Freerouting for the rest (export DSN, route, import SES) |
| 8 | `zones.py`, `finalize.py`, `dangling.py`, `c16fix.py`, `thermal.py` | refill pours, solid connection on U1/U2/U3/J1/J2, remove dangling vias, C16 ground, U3 thermal vias |
| 9 | `silk.py`, `legends.py` | reference designators that clear pads and other text, test-point labels, board legends |

All in one go: `sh tools/pcb_build/pipeline.sh`. The autorouter never touches the locked
items (fan-out, rails, USB).
