# Design intent

Read by the independent reviewer. Facts the schematic cannot show; keep it short.

- Purpose of the board: ceiling-mounted 60 GHz FMCW presence/fall sensor (Infineon
  BGT60TR13C) with on-device DSP and Matter-over-Thread (MGM260P module). Not a
  medical device. Round Ø 60 mm, 4 layers, JLCPCB fab + assembly.
- Supply input: USB-C 5 V (default USB power, Rd = 5.1 k on CC1/CC2, no PD). USB 2.0
  data through CP2102N for logs at 3 Mbaud.
- Loads: radar 1.8 V 201 mA typ / 230 mA max active (duty-cycled frames);
  MGM260P up to 162 mA during +20 dBm TX bursts; CP2102N ~10 mA; RGB LED ~2 mA/colour.
  Worst-case simultaneous 3.3 V load ≈ 0.41 A.
- External connectors: J1 USB-C (power + data), J2 Tag-Connect TC2030-NL (SWD,
  reset, SWO) reachable with the enclosure open. SW1 commissioning, SW2 reset.
- Environment: indoor ceiling, closed plastic enclosure with a radome window,
  0–40 °C ambient. Radar on the BOTTOM side (B.Cu) facing the floor; nothing
  metallic in the ±60° cone in front of the antennas.
- Target fab/assembly: JLCPCB 4-layer 1.6 mm FR4 (JLC04161H-7628), ENIG, standard process
  (0.1 mm min track/space, 0.3/0.55 mm vias); BGT60TR13C is stocked at JLC (C3606641);
  MGM260P and the KC2016 XO are not, so they go through Global Sourcing or consignment.
- Stack-up: L1 parts + signals + GND pour; L2 solid GND; L3 +3V3 plane with a solid GND island
  under the radar; L4 radar (BGT60TR13C, oscillator, U8 translator, LED) + GND pour.
  Every GND / +3V3 pad has its own via to its plane.
- Radar supply filters: one 0.3 mm lane per domain from its BGA via on L1, through
  100 nF -> 1 uF -> 10 uF -> ferrite; a 0.4 mm +1V8_RAD bus feeds the ferrites.
- MCU pin map (rev A): radar SPI/control on the module's bottom pad row so the translators
  sit right below it: SCLK PA07 (16), MOSI PA08 (17), RST PD03 (18), CS PD02 (19),
  MISO PC00 (22), IRQ PC01 (24), OE_N PC02 (25), RADAR_PWR_EN PC03 (26). EUSART pins are
  routable to any port on MGM260P. PD00/PD01 left free for an optional 32 kHz crystal.
- Enclosure: board rests on three supports at 30/150/270 deg (bottom) and is clamped by
  three lid posts at the same angles (top); both faces are kept clear there (rule areas
  SUPPORT_*). USB-C J1 is vertical; the lid opening is centred over it.
- Decisions that look wrong but are intentional:
  - U7 (outputs to the radar) is on the top and U8 (IRQ/DO from the radar) on the bottom:
    the radar's row-1 balls interleave inputs and outputs, so splitting the translators
    over both faces is what lets every line route without crossings.
  - J2 (Tag-Connect TC2030-NL) is a pad pattern for the programming cable: nothing is
    mounted, so it is excluded from BOM and CPL and has no 3D model.
  - D1 is on the bottom (room-facing) side so it is visible through the radome.
  - Radar supply domains are split with ferrite pi filters per Infineon UG091722
    fig. 6; the radar 1.8 V LDO is fed from +3V3 (not 5 V) to keep its dissipation low.
  - Oscillator series resistor (R4, 150 Ω) is a tuning value per UG091722 §3.4.
  - SN74AVC4T245 translators run VCCA = 3.3 V (MCU side), VCCB = 1.8 V (radar side);
    unused B-side inputs of U8 are tied to GND on purpose.
  - MGM260P uses its built-in antenna (RFOUT pin 33 unconnected); it sits at the board
    edge opposite the radar with a copper keep-out per the module datasheet fig. 8.2.
  - BGT60TR13C DIV_TEST (M5) left unconnected (test output only).
