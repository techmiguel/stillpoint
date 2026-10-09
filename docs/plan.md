# Plan and risks

Each phase ends at a gate with a verifiable criterion. A phase does not start until the
previous one is closed.

| Phase | Content | Exit gate | Status |
|---|---|---|---|
| **F0** Definition | scope, numeric criteria, contract v1, interfaces, consent, reference chain in simulation | documents reviewed; tests green | **done (2026-10-05)** |
| **F1** Kit + PC | BGT60TR13C evaluation kit over USB; capture with Infineon's radar SDK; run `radarref` on real data; tune CFAR, breathing thresholds and interferer learning | P1, P2, P4 met *offline* in 2 rooms | tools ready; capture pending |
| **F2** Embedded kit | EFR32MG26 kit + radar board over SPI; port DSP, tracking and decision; Matter with HA; measure cycles and RAM; ≥ 7-day comparison against an Aqara FP2 | **kill criterion** (P1, P2, P3 ≥ reference); compute budget ≤ 50 % | firmware written and tested on PC; SDK build pending |
| **F3** Data and model | consented campaign: ≥ 12 people, ≥ 4 rooms, ≥ 150 simulated falls on a mat; retrain on real data; split by person and room | A1, A2, F1, F4 on the test split | pending |
| **F4** Own board rev A | schematic and PCB, radome from coupons, enclosure; bring-up | contract records match the kit's on the same scenario; S3–S5 | **designed and verified; order after F2** |
| **F5** Final bench | 30 sensor-days of daily life, scripted scenarios, comparison with the reference | every criterion in [requirements](requirements.md#acceptance-criteria-v1) | pending |
| **F6** Publication | metrics report with CIs, anonymized bench data, open design | — | pending |

## Done ahead of the hardware

Everything that can be written and checked on a PC has been done, so the phases that need
hardware start by measuring instead of programming. None of this closes a gate: gates
need real measurements.

| Phase | Done | How it was checked | Still needed for the gate |
|---|---|---|---|
| F0 | Python reference chain: FMCW simulator, two-path DSP, tracking with room logic, contract, int8 classifier, decision; regression scenarios for the known failures | `ml/tests` | — |
| F1 | `ml/capture_kit.py` (capture with the Infineon SDK, same conversion as the firmware), `bench/` (annotation, events, Home Assistant export, report with CIs) | `ml/tests/test_bench.py`, demo report in [img/bench_demo](img/bench_demo/report.md) | captures in 2 real rooms |
| F2 | Complete C firmware (DSP, tracking, int8 inference, decision, application) identical to Python; EFR32MG26 port (driver, Matter with a manufacturer cluster, COBS diagnostics, room configuration in NVM3) | C ↔ Python equivalence end to end with gcc and clang, ASan/UBSan; the port is only syntax-checked against SDK stub headers | build with the Simplicity SDK, measure cycles and RAM, 7 days against an Aqara FP2 |
| F4 | Rev A schematic and 4-layer PCB, placed and routed, with fabrication files; enclosure, lid, λ/2 radome and coupon in FreeCAD | ERC/DRC clean, no schematic/PCB differences, `kicadverify verify` PASS; `mechanical/enclosure.py` assertions with the real board STEP | order after F2 ([hardware](hardware.md)) |

CI (`.github/workflows/ci.yml`) runs the firmware tests with gcc and clang and the
C ↔ Python equivalence under sanitizers on every push.

## Material for F1–F2

| Item | Use |
|---|---|
| Infineon BGT60TR13C evaluation kit with USB base board | real frames on the PC |
| Silicon Labs EFR32MG26 development kit | embedded DSP, Matter/Thread |
| Thread border router (HA with Matter Server + Thread adapter) | commissioning and bench |
| Aqara FP2 | commercial reference on the bench |
| Crash mat ≥ 5 cm | fall protocol |
| Standing fan, mirror ≥ 1 m², curtain | ghost scenarios |

## Risks and known limitations

| ID | Risk / limitation | Probability | Impact | Mitigation | Status |
|---|---|---|---|---|---|
| R1 | The simulator is optimistic: real breathing is weaker and multipath more complex | high | high | F1 with real data before any fine tuning; no synthetic metric is published | open |
| R2 | Fixed interferers (fan) count as a person until learned (20 s in simulation) | medium | medium | persist learned zones; manual excluded zones; measure in G1–G2 | open |
| R3 | Two still people at the same range (±6 cm) give a single breathing detection with a blended angle | medium | medium | room logic keeps both static tracks; documented; more chirps/RX in v2 | accepted for v1 |
| R4 | Identity swaps when two people cross | medium | low for count, medium for posture | association penalty between a still track and a fast measurement; swap metric on the bench | partly mitigated |
| R5 | The EFR32MG26 MVP or RAM is not enough for DSP + Matter | medium | high | measure in F2; plan B (PSoC Edge E84 + EFR32MG24 RCP) | open |
| R6 | Lying on a high or low bed mistaken for a fall | medium | high | height rule (0.55 m) + a configurable "bed" zone where lying is not a fall; scenario A3 | open |
| R7 | Home Assistant does not expose the manufacturer cluster (count, postures) | high | medium | essentials in standard clusters; count per zone; follow Matter's evolution | open |
| R8 | Simulated falls ≠ real falls of older people | certain | high | stated next to every metric; include slow falls and falls from sitting; never presented as a medical device | accepted |
| R9 | A printed radome detunes the radar (thickness, humidity, pigments) | medium | medium | thickness coupons measured with the kit; natural PETG, 100 % infill | open |
| R10 | Plastic next to the module antenna detunes 2.4 GHz | medium | medium | measure RSSI with and without the enclosure; thin the wall in that sector if more than 3 dB is lost | open |
| R11 | Radar die temperature inside the closed enclosure | low | medium | ~60 mW average; read the internal sensor in the closed enclosure, keep it below 70 °C | open |
| R12 | MGM260P and KC2016 not stocked at JLCPCB | high | low | Global Sourcing or consigned parts; KC2016 alternative to be checked for ≤ 1 ps jitter | open |
