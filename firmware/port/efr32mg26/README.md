# EFR32MG26 port (Matter over Thread)

Everything that does not depend on the SDK lives in `firmware/src/` and is
tested on the PC against the Python reference
(`cd ml && python -m unittest discover -s tests`). This folder holds only the
layer that **does** depend on the Silicon Labs SDK. It has **not been built
against the real SDK yet**. `radar_port.c` and `diag_uart.c` pass
`gcc -fsyntax-only -Wall -Wextra` against stub headers that carry the SDK and
Infineon driver signatures. That rules out type and name errors, not mismatches
with the real signatures. Building and testing with the kit is phase F2.

| File | What it does | Status |
|---|---|---|
| `radar_port.c` | Infineon driver platform hooks (SPI, CS, RST, delay), FIFO interrupt, radar task | syntax-checked |
| `radar_settings_check.h` | refuses to build with a `radar_settings.h` that differs from config v1 | not built |
| `radar_pins.h` | rev A board pins (radar, LED, button, console) | matches `hardware/` and `verification/pcb/pins.yaml` |
| `matter_bridge.cpp` | `rf_outputs_t` → Matter attributes (EP1–6 plus the manufacturer cluster with `ContractVersion` and `ModelHash`), at most 2 reports/s except alarms | not built; ZAP generates the `Radar60Presence::…` accessors from the XML |
| `app_radar_init.cpp` | start-up from `AppTask::AppInit` | not built |
| `diag_uart.c` | contract records over UART with COBS (`tools/diag_reader.py`) and command input (room configuration from `tools/room_cfg.py`, acknowledged) | COBS tested on PC; syntax-checked |
| `cfg_store.c` | room configuration in NVM3 (v1 layout from `src/room_cfg.h`); factory default when none is valid | `room_cfg.c` tested on PC against the Python tool; syntax-checked |
| `radar60_cluster.xml` | manufacturer cluster for ZAP | not validated in ZAP |

## Steps (F2)

1. Simplicity Studio 5 + Simplicity SDK + Silicon Labs Matter extension.
2. New project from the **Matter – SoC Occupancy Sensor (Thread)** example for the
   EFR32MG26 board.
3. Components: `spidrv` (instance `radar`, EUSART1, 12 MHz to start with; on the
   rev A board SCLK PA07, MOSI PA08, MISO PC00 and CS as GPIO, see `radar_pins.h`),
   `gpiointerrupt`, `sleeptimer`, `iostream_eusart` or `iostream_usart` for
   diagnostics (3 Mbaud, non-blocking reads) and `nvm3_default`. Check that the
   NVM3 key in `cfg_store.c` (0x0F600) is outside the range Matter reserves.
   The board's module is the MGM260PB32VNA5 (+20 dBm, the same as the kit); the
   3.3 V regulator (TLV75733P, 1 A) is sized for its TX peaks (budget in
   [`docs/hardware.md`](../../../docs/hardware.md)).
4. Add `firmware/src/*.c` (except tests), this folder and Infineon's
   `sensor-xensiv-bgt60trxx` library (Apache-2.0) without its `*_mtb.c`.
5. Export `radar_settings.h` from **Infineon Radar Fusion GUI** with:

   | Parameter | Value |
   |---|---|
   | Start / stop frequency (sampled) | 60.0 / 61.25 GHz |
   | Samples per chirp | 128 at 2 MS/s |
   | Chirps per frame | 32, 350 µs repetition |
   | Frame | 100 ms (10 Hz) |
   | RX | 1, 2, 3 · TX 1 |

   `radar_settings_check.h` fails the build if anything differs.
6. ZAP: endpoints from [`docs/matter.md`](../../../docs/matter.md) (EP1 occupancy,
   EP2–4 zones, EP5 fall and EP6 uncertainty as Boolean State) and the
   `radar60_cluster.xml` cluster.
7. Call `RadarInit()` at the end of `AppTask::AppInit()`.
8. Measure on the kit: `rf_app_frame` cycles (TP10 GPIO + oscilloscope), free RAM,
   and compare the diagnostic stream with the reference on the same scenario
   (`tools/diag_reader.py` + `ml/compare_c.py`).

## Planned speed-ups

| Portable (tested) | Accelerated on the MCU | Acceptance |
|---|---|---|
| `rf_fft` | CMSIS-DSP `arm_cfft_f32` / MVP | contract records ≥ 99 % identical in `ml/compare_c.py` |
| `rf_dft_bin` (micro-motion) | zero-padded 128-point FFT or Goertzel | same |
| `nn.c` | TFLite Micro + MVP kernels | logits identical to `firmware/tests/nn_vectors.h` |
