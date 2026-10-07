# Design intent

Read by the independent reviewer. Facts the schematic cannot show; keep it short.
Fuente: docs/09_hardware.md y docs/02_arquitectura.md (rev A).

- Purpose of the board: sensor de techo de presencia y caídas con radar FMCW de 60 GHz (Infineon BGT60TR13C) y Thread/Matter (Silicon Labs MGM260PB22VNA5); placa redonda de Ø 60 mm, 4 capas. No es un dispositivo médico.
- Supply input (voltage range, source, max current): USB-C 5 V (VBUS) con fusible rearmable F1 de 500 mA; pico estimado en 5 V < 0,3 A. U3 AP2112K-3.3 da +3V3; U4 TPS7A2018 da +1V8_RAD para el radar, habilitado por el MCU (RADAR_PWR_EN, 100 kΩ a GND: apagado por defecto). Filtros π por dominio del radar (+1V8_RF, +1V8_A, +1V8_D) y RC de 47 Ω + 10 µF para VDDLF (+3V3_LF).
- Loads and their currents (motors, relays, LEDs, radios): radar 230 mA máx. en activo y 2,8 mA en reposo (1,8 V); MGM260P 19,4 mA transmitiendo a +10 dBm; CP2102N ~10 mA; LED RGB D1 con 1 kΩ por cátodo. Pico estimado en 3V3: 273 mA; medio: 59 mA.
- External connectors and what plugs into them: J1 USB-C vertical (GT-USB-7051A, solo USB 2.0 full speed para el CP2102N y alimentación); J2 Tag-Connect TC2030-NL (SWD, reset y UART), solo pads sin cuerpo.
- Environment (temperature, humidity, mains, battery, enclosure): interior, techo, dentro de carcasa de PLA con radomo λ/2; sin red eléctrica ni batería (no hay tensiones peligrosas). Cara del radar < 70 °C (pendiente de medir en F2).
- Target fab/assembly house and process: JLCPCB, 4 capas JLC04161H-7628 de 1,6 mm (1 oz exterior, 0,5 oz interior), montaje por las dos caras, BGA de 0,5 mm (BGT60TR13C) en la cara inferior.
- Decisions that look wrong but are intentional: radar en B.Cu mirando al suelo; sin agujeros de montaje (la placa se apoya en tres soportes de la carcasa a 0/120/240°, zonas apoyo_carcasa_*); VDDPLL y VDDVCO comparten el filtro de RF; banco 2 de U8 sin usar con 2B1/2B2 a GND (lo exige TI); fan-out del BGA con pistas de 0,15-0,25 mm y sin vía en pad; U7/U8 con la marca de pin 1 desplazada respecto a la biblioteca; el MGM260P usa solo la fila exterior de 36 pads (la interior es opcional según su hoja).
