# Test bench

It does two things: measure the [acceptance criteria](requirements.md#acceptance-criteria-v1)
and compare against a commercial sensor under the same conditions.

## Set-up

- A 4 × 4 m room with the door marked as an exit zone.
- Device under test (DUT) and an Aqara FP2 on the ceiling, ≤ 30 cm apart, with the same
  zone configuration.
- Both in the same Home Assistant: the FP2 through its local integration, the DUT over
  Matter. The HA history is exported to CSV (`bench/ha_export.py`).
- Ground truth: a script + a timestamping app on NTP time (`bench/annotator.py`).
- Floor marks every 0.5 m for the position error (P7).

## Scenarios

| ID | Scenario | Criteria |
|---|---|---|
| E1 | Enter, walk around, leave through the door | P4, P5, P6 |
| E2 | Sit still for 30 min (reading, screen) | P1 |
| E3 | Sleep / lie down for 2 h | P1, A2 |
| O1 | Still person; another walks in front | P2 |
| O2 | Still person; another stops in front for 30 s and leaves | P2 |
| G1 | Empty room with a standing fan on for 8 h | P3 |
| G2 | Empty room with a curtain moved by a fan | P3 |
| G3 | Mirror ≥ 1 m² on a wall; one person walks next to it | P6 |
| A3–A5 | Lie down fast on the bed, sit down hard, crouch | F4 |
| C1 | Simulated falls from the [session script](data-protocol.md#session-script--25-min) | F1, F3 |
| V1 | Daily life in a home, 30 sensor-days | F2, P3 |
| M1–M3 | Commissioning ×10, Thread router reboot, power cut | S1, S2 |

## Metrics

[metrics.py](../ml/radarref/metrics.py) and [bench/report.py](../bench/report.py) compute:

- Proportions (P1, F1…) with a Wilson interval.
- Rates per day (P3, F2) with an exact Poisson interval. With 0 events the report says
  "0 in N days; 95 % upper bound 3.69/N per day", never "no false alarms".
- Latencies as p50/p95, pairing each event with the first detection.

A synthetic demo of the report (made-up devices, to test the tool) is in
[img/bench_demo/report.md](img/bench_demo/report.md).

## Published report

For every criterion: DUT value, reference value, n, interval, pass/fail, and the
limitations (simulated falls, one room, mounting height). Failures and the scenarios
where the reference wins are published too.
