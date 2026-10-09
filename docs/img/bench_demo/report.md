# Bench report (DEMO DATA)

> Synthetic data from bench/demo_data.py, used to test the tool. It describes no product.

Duration: 24.0 h. Falls, when present, are simulated by healthy adults on a crash mat (docs/data-protocol.md).

| Criterion | Threshold | prototype | reference |
|---|---|---|---|
| P1 Occupied minutes detected | >= 0.99 | ✅ 99.7 % (609/611; CI95 98.8–99.9 %) | ❌ 98.4 % (601/611; CI95 97.0–99.1 %) |
| P3 False occupancies per day (empty room) | <= 1 | ❌ 1.79 (1 in 13.4 h; CI95 upper 9.95) | ❌ 0.00 (0 in 13.4 h; CI95 upper 6.59) |
| P4 Latency entry → occupied p95 (s) | <= 1 | ✅ 0.8 s (n=17) | ❌ 1.2 s (n=17) |
| P5 Latency exit → empty p95 (s) | <= 5 | ✅ 4.0 s (n=17) | ❌ 6.3 s (n=17) |
| F1 Falls notified | >= 0.9 | ❌ 100.0 % (11/11; CI95 74.1–100.0 %) | ❌ 0.0 % (0/11; CI95 0.0–25.9 %) |
| F2 False fall alarms per day | <= 0.1 | ❌ 0.00 (0 in 24.0 h; CI95 upper 3.69) | ❌ 0.00 (0 in 24.0 h; CI95 upper 3.69) |
| F3 Latency fall → notification p95 (s) | <= 10 | ✅ 8.3 s (n=11) | ❌ nan s (n=1), 1 missed |

Kill criterion (docs/requirements.md): prototype must match reference on P1, P2 and P3. P2 is measured separately with scenarios O1–O2.
- P1: prototype matches or beats reference.
- P3: prototype does NOT match reference.
