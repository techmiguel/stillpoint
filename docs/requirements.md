# Requirements

## What it is

A USB-C powered ceiling sensor. A 60 GHz FMCW radar tells how many people are in
**one** room, where they are, their posture (standing, sitting, lying) and whether
someone fell. There is no camera and no microphone. All processing runs on the device
and the result is published over Matter on Thread: no cloud, no account.

## What it is not

- **Not a medical device.** A fall is a *notification*, never the only safety measure
  for a person. This sentence goes in the README, on the box and in the Matter device
  description.
- It does not measure vital signs with clinical value. Breathing is only used as
  evidence that someone is there.

## v1 scope (frozen)

| Topic | v1 | Out of v1 |
|---|---|---|
| Rooms | 1, up to 4 × 4 m | several rooms, corridors |
| Mounting | ceiling, 2.4–2.9 m, antennas facing the floor | wall, corner |
| People | up to 3 (criteria measured with 1–2) | more than 3, pets |
| Radar | BGT60TR13C with antennas in package | custom antennas |
| Power | USB-C 5 V | battery |
| Output | Matter 1.3+ over Thread | Wi-Fi, Zigbee, cloud |

## Known failures of commercial sensors, and the design answer

| Reported problem | Design answer | Where it is checked |
|---|---|---|
| Ghost detections (fan, mirror) | room limits, excluded zones, multipath filter, fixed sources with micro-Doppler but no breathing are learned as interferers | `test_fan_becomes_interferer`, `test_mirror_ghost_not_counted`, bench G1–G3 |
| A still person vanishes when someone walks in front | a breathing (micro-motion) path independent of MTI; an OCCLUDED track state; tracks are only dropped quickly next to a door | `test_still_person_survives_occlusion`, bench O1–O2 |
| Mutually exclusive modes (sleep / zones / fall) | one track stream; zones, posture and falls are always computed together; the compute budget is sized for the worst case | [architecture](architecture.md#compute-and-memory-budget) |
| Battery trade-offs | out of v1 scope: mains powered | — |
| Ecosystem lock-in | standard Matter; local configuration; no account | [matter](matter.md), bench M1 |
| No independent metrics | criteria fixed before starting, published bench, comparison with a commercial sensor, confidence intervals | below, [test bench](test-bench.md) |

## Technical guardrails

- Every number below was fixed before any design work.
- The whole chain is validated on evaluation kits before a board is ordered ([plan](plan.md)).
- Fail safe: without confidence the output is "uncertain"; a possible fall that cannot be
  verified is published as "uncertain fall", never silenced
  ([decision.py](../ml/radarref/decision.py)).
- Emission stays inside 57–64 GHz and ≤ 20 dBm EIRP, enforced in firmware
  ([regulatory](regulatory.md), [radar_limits.h](../firmware/src/radar_limits.h)).
- The board has SWD, UART, USB data and test points on every rail ([hardware](hardware.md)).

## Data guardrails

- Written consent from everyone recorded ([data protocol](data-protocol.md)).
- Training and test are split by person **and** by room; the code enforces it
  ([split.py](../ml/radarref/split.py)).
- Falls are simulated by healthy adults on a crash mat; every published fall metric says so.
- Public datasets and the simulator are for prototyping only: no final model is trained
  only on them and no published metric comes from them.

## Acceptance criteria (v1)

Fixed on 2026-10-05, **before** any hardware. Changing one requires logging the date,
the reason and the old value at the end of this document; they are never tuned to make
a result pass.

Every metric is measured on the [test bench](test-bench.md), on people and rooms that
were not used for training, and is published with its n and its 95 % confidence interval.

### Presence

| ID | Metric | Threshold | How |
|---|---|---|---|
| P1 | Occupied minutes detected as occupied (including still people sitting or lying) | ≥ 99 % | per minute, ≥ 20 occupied hours |
| P2 | Still person who vanishes when another walks in front | 0 cases in ≥ 50 passes (95 % upper bound ≤ 6 %) | scenarios O1–O2 |
| P3 | False occupancy in an empty room with fan, curtain and mirror | ≤ 1 per day | ≥ 7 empty days; exact Poisson |
| P4 | Latency entry → occupied | p95 ≤ 1.0 s | ≥ 50 entries |
| P5 | Latency exit through the door → empty | p95 ≤ 5 s | ≥ 50 exits |
| P6 | Exact count (0–3 people) | ≥ 90 % of the time | per second |
| P7 | Horizontal position error | median ≤ 0.30 m; p90 ≤ 0.50 m | against floor marks |

### Posture

| ID | Metric | Threshold |
|---|---|---|
| A1 | Macro F1 over standing, sitting, lying (non-abstained windows) | ≥ 0.85 |
| A2 | "Uncertain" rate in normal conditions | ≤ 5 % of the time |

### Falls

| ID | Metric | Threshold | Minimum n and why |
|---|---|---|---|
| F1 | Simulated falls notified (confirmed or uncertain) | ≥ 90 %, CI95 lower bound ≥ 80 % | ≥ 100 falls: at 90/100 the Wilson lower bound is 0.83 |
| F2 | False fall alarms in daily life | ≤ 0.1 per day | ≥ 30 sensor-days without an alarm (rule of three: 3/30 = 0.1) |
| F3 | Latency fall → Matter notification | p95 ≤ 10 s | ≥ 100 falls |
| F4 | Lying down in bed, sitting down hard, crouching | 0 alarms in ≥ 50 of each | scenarios A3–A5 |

### System

| ID | Metric | Threshold |
|---|---|---|
| S1 | Matter commissioning with Home Assistant | 10/10 without manual retries |
| S2 | Recovery after a Thread border router reboot | ≤ 60 s |
| S3 | Power | ≤ 1.0 W average at 5 V |
| S4 | Emission | 57–64 GHz and ≤ 20 dBm EIRP, by configuration and a rough measurement |
| S5 | Enclosure temperature | ≤ 15 °C above ambient |

### Kill criterion

At the end of phase F2 (the chain running on the kits, see [plan](plan.md)) the prototype
is compared with the commercial reference (Aqara FP2) on the same bench over the same
period. **If the prototype does not match the reference on P1, P2 and P3, the project
stops**, or is re-planned in writing, before a board is ordered.

### Criteria change log

| Date | Criterion | Before | After | Reason |
|---|---|---|---|---|
| — | — | — | — | — |
