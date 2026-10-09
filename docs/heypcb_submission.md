# Circuit World submission (heypcb Hardware Challenge)

Text ready to paste when publishing the board from heypcb's Share menu.

## Title

radar60 — privacy-first 60 GHz presence & fall sensor (Matter over Thread)

## Summary (card)

A Ø60 mm ceiling sensor with no camera and no microphone. A 60 GHz FMCW radar counts
people, tracks where they are and their posture, flags falls, and still sees someone lying
completely still by the movement of their chest. Everything runs on the device and reports
over Matter/Thread: no cloud, no account.

## Description

**What it does**
- Infineon BGT60TR13C 60 GHz radar (1 TX / 3 RX, antennas in package) looking down from the
  ceiling through a λ/2 radome.
- On-device processing on the Silicon Labs MGM260P (EFR32MG26): range-Doppler + angle DSP,
  tracking, breathing micro-motion and an int8 neural network for posture and falls.
- Matter over Thread endpoints: occupancy, per-zone presence, fall and uncertainty.
- RGB status LED, commissioning button, USB-C power + 3 Mbaud log console (CP2102N).
- Not a medical device: a fall is a notification, never the only safety measure.

**How the board is made**
- 4 layers, Ø60 mm round, JLCPCB standard process (JLC04161H-7628, ENIG).
- L1 parts/signals · L2 solid GND · L3 3.3 V plane with a solid ground island under the radar ·
  L4 radar, 80 MHz oscillator, level translator, LED.
- Radar BGA (0.5 mm pitch, 0.275 mm pads per Infineon UG091722) fanned out in two staggered
  via rows; nothing but ground under the chip on the inner layers.
- Each of the radar's seven supply domains is a straight 0.3 mm lane from its ball through
  100 nF → 1 µF → 10 µF → ferrite, fed by a low-noise 7 µVrms LDO (Infineon's π-filter
  scheme, with the small capacitor closest to the ball).
- Radar SPI/control moved to the module's bottom pad row so the level translators sit right
  between the MCU and the radar; translators split over both faces so no radar line crosses.
- Module at the board edge with the antenna keep-out of its datasheet on every layer; the
  60 mm ground plane is exactly the width Silicon Labs recommends for the built-in antenna.
- Every ground and 3.3 V pad has its own via to its plane.
- Checked: ERC/DRC clean, schematic↔PCB parity, pin maps against the datasheets, BOM/CPL
  against the board, and a FreeCAD interference check of the real board STEP against the
  enclosure, lid clamps and radome.

**Open source**
Schematic, PCB, enclosure (FreeCAD), firmware (C, tested against a Python reference) and the
radar simulation/ML pipeline: https://github.com/techmiguel/radar60 (CERN-OHL-S-2.0).

## Licence

CERN-OHL-S-2.0

## Tags

radar, mmwave, 60ghz, matter, thread, presence-sensor, fall-detection, privacy, smart-home, bga
