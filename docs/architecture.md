# Architecture

## Blocks

```
 USB-C 5V ─► LDO 3V3 (MCU) ─┬─► low-noise LDO 1V8 (radar)
          └─► CP2102N (USB data ⇄ UART)
                             │
 ┌──────────────┐  SPI 50 MHz + IRQ + RST  ┌──────────────────────────────────────┐
 │ BGT60TR13C   │ ───────────────────────► │ EFR32MG26 (Cortex-M33 + MVP)         │
 │ 1 TX / 3 RX  │  FIFO → DMA              │  DSP: range FFT, MTI+Doppler, CFAR,  │
 │ AiP antennas │                          │       angle, micro-motion            │
 └──────────────┘                          │  Tracking + room logic               │
      PETG radome ~1.5 mm (λ/2)            │  Features (contract v1)              │
                                           │  int8 classifier (MVP) + decision    │
                                           │  Matter / Thread (FTD router) / BLE  │
                                           └──────────────────────────────────────┘
                                             SWD · UART · test points
```

Per frame (10 Hz): ADC samples → range FFT → two paths (motion and micro-motion) → 3D
detections → tracks → one 66-byte record per track. At 2 Hz every track with 2 s of
history goes through the classifier and the decision state machine; changes are
published over Matter.

The reference implementation is [ml/radarref](../ml/radarref). The firmware ports it
block by block and is compared against it **on the contract** (the feature records),
not on the intermediate steps.

## Key decisions

1. **Two detection paths.** Classic MTI erases whoever does not move; the breathing path
   brings them back. That is the root cause of "a still person disappears".
2. **Room logic.** People enter and leave through doors. A confirmed track is only dropped
   quickly next to an exit zone; in the middle of the room it is kept (60 s when occluded,
   120 s if it has shown breathing).
3. **No modes.** Zones, posture and falls all come from the same track stream.
4. **The model never sees absolute position.** x, y, range and track state are excluded
   from its input so it cannot learn the geometry of the training rooms.
5. **Physics rule + model for falls.** A suspicion opens on the model *or* on a fast
   descent to the floor; confirmation needs the person to stay on the floor and still for
   4 s. No single component can trigger or silence an alarm.

## Component choice

| Option | Pros | Cons | Decision |
|---|---|---|---|
| **A. EFR32MG26** (single chip) | Matter + Thread + BLE in one chip with a mature SDK; MVP accelerator; up to 3.2 MB flash / 512 kB RAM | MVP is a matrix accelerator, not a full NPU; 78 MHz | **v1** |
| B. PSoC Edge E84 + EFR32MG24 | Ethos-U55 NPU, more CPU; Infineon sells a kit with the same radar | two chips, Thread through an RCP, more BOM and firmware | plan B if F2 runs out of CPU |
| C. nRF54L15 | good Matter support in Zephyr | no AI accelerator | rejected |

The current model is 14.6 KB and needs ~0.1 M MAC per inference: the AI load is small.
The expected bottleneck is the DSP, not inference.

## Radar parameters (v1)

| Parameter | Value | Consequence |
|---|---|---|
| Sweep | 60.0–61.25 GHz (1.25 GHz) | 12 cm range resolution |
| Samples/chirp | 128 real at 2 MS/s | 64 bins → 7.7 m |
| Chirps/frame | 32 every 350 µs | v max ±3.5 m/s, 0.22 m/s resolution |
| Frames | 10 Hz, 11 % duty cycle | |
| RX antennas | L-shaped, λ/2 | azimuth and elevation → 3D position and height |

## Compute and memory budget

Estimated; measured in F2.

| Block | Cycles/frame (est.) | RAM (est.) |
|---|---|---|
| Range FFT 96 × 128 real (q15) | ~0.5 M | 24 KB in + 24 KB out |
| MTI + Doppler 3 × 40 × 32 complex | ~0.3 M | 15 KB |
| CFAR + angle + clustering | ~0.2 M | 4 KB |
| Micro-motion (every 5 frames, 100 × 3 × 40) | ~0.4 M amortized | 48 KB |
| Tracking + features | < 0.1 M | 4 KB |
| Classifier (2 Hz × 3 tracks) | < 0.1 M amortized | 16 KB arena |
| **Total** | **~1.5 M of 7.8 M available (≈ 20 %)** | **~140 KB** + Matter stack |

If F2 measures more than 50 % CPU or less than 64 KB free RAM, plan B starts.

## Firmware tasks

| Task | Priority | Period | Input → output |
|---|---|---|---|
| `radar_isr` / DMA | ISR | FIFO | SPI → frame buffer |
| `dsp` | high | 100 ms | frame → detections |
| `track` | high | 100 ms | detections → tracks + records |
| `infer` | medium | 500 ms | windows → posture/fall |
| `matter` | medium | on events | state → attributes/events |
| `diag` | low | on demand | records over UART/USB (data capture) |

All of `firmware/src/` is portable C, tested on the PC against the Python reference.
The SDK-dependent layer is in [firmware/port/efr32mg26](../firmware/port/efr32mg26).

## Interfaces

Each block has one owner. An interface change is proposed by whoever produces the data
and approved by whoever consumes it. In a one-person team the roles still apply: every
deliverable is reviewed wearing the consumer's hat before it is accepted.

| ID | From → to | Format | Source of truth | Test that guards it |
|---|---|---|---|---|
| I1 | Radar → DSP | int16 ADC frame (3 × 32 × 128) | `RadarConfig` / `radar_limits.h` | `RadioLimitsTest`, `test_limits` (C) |
| **I2** | **DSP → ML** | **feature record v1, 66 bytes** | **[contracts/features_v1.yaml](../contracts/features_v1.yaml)** | `ContractTest`, `golden_v1.h` (C) |
| I3 | ML → firmware | `model_int8.tflite` + `model_meta.json` + `model_data.h` | `ml/train.py` | `model_guard.h` (does not compile on a hash mismatch) |
| I4 | Firmware → home automation | Matter (endpoints and clusters) | [matter.md](matter.md) | bench M1–M3 |
| I5 | Hardware ⇄ mechanics | board outline, antenna–radome distance, supports | `mechanical/enclosure.py` | interference check against the board STEP; radome coupon |
| I6 | Everyone → bench | event CSVs with an NTP clock | [test-bench.md](test-bench.md) | `ml/tests/test_bench.py` |

### I2 in detail: the feature contract

This is the interface that does the most damage if it breaks silently: a model trained
on a different scale keeps "working" and returns garbage.

- 24 `int16` fields in scaled physical units (mm, mm/s, cdB, mHz…). List and scales in the YAML.
- A CRC-32 hash of the canonical form (name | unit | scale + window parameters). It
  travels in every record (16 bits) and in the model (32 bits).
- The firmware **does not compile** with a model from another contract
  (`_Static_assert` in `model_guard.h`) and the Python reference **refuses to load** it
  (`ModelMismatch`).
- Training uses the values *after* quantize/dequantize: the model sees exactly what it
  will see on the board.
- Golden vectors: `tools/gen_contract.py` writes the expected bytes from Python;
  `firmware/tests/test_host.c` requires C to produce the same ones.
- Normalization (mean/std) and the out-of-distribution limits live in
  `model_meta.json`, not in the contract.
- Changing order, unit, scale or meaning ⇒ `features_v2.yaml`. Published versions are
  never edited.

After changing the contract:

```bash
python tools/gen_contract.py
```

```bash
make -C firmware test
```

```bash
cd ml && python -m unittest discover -s tests
```
