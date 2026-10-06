# Puerto EFR32MG26 (Matter sobre Thread)

Todo lo que no depende del SDK está en `firmware/src/` y se prueba en el PC
contra la referencia Python (`python -m unittest discover -s ml/tests`). Esta
carpeta contiene solo la capa que **sí** depende del SDK de Silicon Labs y que
**no se ha compilado todavía con el SDK real**, porque el PC de desarrollo no lo
tiene. Los ficheros C (`radar_port.c`, `diag_uart.c`) pasan `gcc -fsyntax-only
-Wall -Wextra` contra cabeceras simuladas con las firmas del SDK y del driver
de Infineon; eso descarta errores de tipos y de nombres propios, no
discrepancias con las firmas reales. Se compila y prueba en la fase F2 con el kit.

| Fichero | Qué hace | Estado |
|---|---|---|
| `radar_port.c` | ganchos de plataforma del driver de Infineon (SPI, CS, RST, retardo), interrupción de FIFO, tarea de radar | comprobación sintáctica |
| `radar_settings_check.h` | impide compilar con un `radar_settings.h` distinto de la configuración v1 | sin compilar |
| `radar_pins.h` | pines del radar | revisar con el kit / esquema |
| `matter_bridge.cpp` | `rf_outputs_t` → atributos Matter (EP1–6 y clúster de fabricante, con `ContractVersion` y `ModelHash`), con límite de 2 informes/s salvo alarmas | sin compilar; los accesores `Radar60Presence::…` los genera ZAP a partir del XML |
| `app_radar_init.cpp` | arranque desde `AppTask::AppInit` | sin compilar |
| `diag_uart.c` | registros del contrato por UART con COBS (`tools/diag_reader.py`) y recepción de comandos (configuración de sala de `tools/room_cfg.py`, con confirmación) | COBS probado en PC; comprobación sintáctica |
| `cfg_store.c` | configuración de la sala en NVM3 (formato v1 de `src/room_cfg.h`); sin una válida, la de fábrica | `room_cfg.c` probado en PC contra la herramienta Python; comprobación sintáctica |
| `radar60_cluster.xml` | clúster de fabricante para ZAP | sin validar en ZAP |

## Pasos (F2)

1. Simplicity Studio 5 + Simplicity SDK + extensión Matter de Silicon Labs.
2. Proyecto nuevo desde el ejemplo **Matter – SoC Occupancy Sensor (Thread)** para la
   placa del EFR32MG26.
3. Componentes: `spidrv` (instancia `radar`, EUSART, 12 MHz para empezar),
   `gpiointerrupt`, `sleeptimer`, `iostream_eusart` o `iostream_usart` para el
   diagnóstico (3 Mbaud, lectura sin bloqueo) y `nvm3_default`. Comprobar que la
   clave NVM3 de `cfg_store.c` (0x0F600) no cae en el rango reservado por Matter.
   Potencia de Thread limitada a +10 dBm (balance de alimentación en
   `docs/09_hardware.md`).
4. Añadir al proyecto `firmware/src/*.c` (excepto pruebas), esta carpeta y la
   biblioteca `sensor-xensiv-bgt60trxx` de Infineon (Apache-2.0) sin su `*_mtb.c`.
5. Exportar `radar_settings.h` desde **Infineon Radar Fusion GUI** con:

   | Parámetro | Valor |
   |---|---|
   | Frecuencia inicial / final (muestreada) | 60,0 / 61,25 GHz |
   | Muestras por chirp | 128 a 2 MS/s |
   | Chirps por trama | 32, repetición 350 µs |
   | Trama | 100 ms (10 Hz) |
   | RX | 1, 2, 3 · TX 1 |

   `radar_settings_check.h` falla la compilación si algo no coincide.
6. ZAP: endpoints de `docs/04_matter.md` (EP1 ocupación, EP2–4 zonas,
   EP5 caída y EP6 incertidumbre como Boolean State) y el clúster `radar60_cluster.xml`.
7. Llamar a `RadarInit()` al final de `AppTask::AppInit()`.
8. Medir en el kit: ciclos de `rf_app_frame` (GPIO de TP10 + osciloscopio), RAM libre,
   y comparar los registros del flujo de diagnóstico con la referencia sobre el
   mismo escenario (`tools/diag_reader.py` + `ml/compare_c.py`).

## Sustituciones previstas para rendimiento

| Portable (probado) | Acelerado en el MCU | Condición |
|---|---|---|
| `rf_fft` | CMSIS-DSP `arm_cfft_f32` / MVP | registros del contrato idénticos al 99 % sobre `ml/compare_c.py` |
| `rf_dft_bin` (micro-movimiento) | FFT de 128 con relleno o Goertzel | ídem |
| `nn.c` | TFLite Micro + núcleos MVP | logits idénticos a `firmware/tests/nn_vectors.h` |
