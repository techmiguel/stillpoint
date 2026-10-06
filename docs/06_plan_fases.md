# 06 · Plan por fases

Cada fase termina en una puerta con criterio verificable. No se abre la
siguiente sin cerrar la anterior.

| Fase | Contenido | Puerta de salida | Estado |
|---|---|---|---|
| **F0** Definición | alcance, criterios numéricos, contrato v1, interfaces, consentimiento, cadena de referencia en simulación | documentos 00–10 revisados; 22 pruebas en verde | **hecha (2026-10-05)** |
| **F1** Kit + PC | kit de evaluación BGT60TR13C por USB; captura con el SDK de radar de Infineon; ejecutar `radarref` sobre datos reales; ajustar CFAR, umbrales de respiración y aprendizaje de interferentes | P1, P2, P4 cumplidos *fuera de línea* en 2 salas propias | pendiente |
| **F2** Kit embebido | kit EFR32MG26 + placa del radar por SPI; portar DSP, seguimiento y decisión; Matter con HA; medir ciclos y RAM; banco comparativo con Aqara FP2 durante ≥ 7 días | **criterio de abandono** (P1, P2, P3 ≥ referencia); presupuesto de cómputo ≤ 50 % | pendiente |
| **F3** Datos y modelo | campaña con consentimiento: ≥ 12 personas, ≥ 4 salas, ≥ 150 caídas simuladas sobre colchoneta; reentrenar con datos reales; separar por persona y sala | A1, A2, F1, F4 en partición de prueba | pendiente |
| **F4** Placa propia rev A | esquema y PCB (JLCPCB/PCBWay), radomo por cupones, carcasa; puesta en marcha | registros del contrato idénticos a los del kit en el mismo escenario; S3–S5 | pendiente |
| **F5** Banco final | 30 días-sensor de vida diaria, escenarios scriptados, comparación con referencia | todos los criterios de [01](01_criterios_aceptacion.md) | pendiente |
| **F6** Publicación | informe de métricas con IC, datos de banco anonimizados, diseño abierto, documentación en inglés | — | pendiente |

## Material para F1–F2

| Elemento | Uso |
|---|---|
| Kit de evaluación BGT60TR13C con placa base USB (Infineon) | captura de tramas reales en PC |
| Kit de desarrollo EFR32MG26 (Silicon Labs) | DSP embebido, Matter/Thread |
| Router de borde Thread (HA con Matter Server + adaptador Thread) | puesta en marcha y banco |
| Aqara FP2 | referencia comercial del banco |
| Colchoneta de caídas ≥ 5 cm | protocolo de caídas |
| Ventilador de pie, espejo ≥ 1 m², cortina | escenarios de fantasmas |

## Qué hay hecho en F0

- Cadena completa de referencia en Python: simulador FMCW, DSP con dos caminos,
  seguimiento con lógica de habitación, contrato, clasificador int8, decisión.
- Escenarios de regresión para los fallos conocidos (oclusión, ventilador,
  espejo, latencia) y pruebas unitarias (22 en verde).
- Código C portable del contrato, la decisión y los límites RF, con vectores
  dorados generados desde Python; compila sin avisos con un compilador cruzado RISC-V.
  `make -C firmware test` ejecutado con gcc y clang (2026-10-05).
- Entrenamiento de extremo a extremo con datos sintéticos, separación por persona
  y sala, exportación int8 (14,6 KB) y cabecera C del modelo.

## Adelantado de F1, F2 y F4 (sin hardware)

Para que las fases con material empiecen midiendo y no programando, se ha
adelantado todo lo que puede escribirse y verificarse en un PC. Ninguna de
estas piezas cierra su puerta: las puertas exigen medidas reales.

| Fase | Hecho | Cómo se ha verificado | Qué falta para la puerta |
|---|---|---|---|
| F1 | `ml/capture_kit.py` (captura con el SDK de Infineon y conversión idéntica a la del firmware), `bench/` (anotación, eventos, exportación de Home Assistant, informe con IC) | `ml/tests/test_bench.py`, demo con datos sintéticos en `docs/img/informe_demo` | capturas en 2 salas propias |
| F2 | Firmware C completo (DSP, seguimiento, int8, decisión, aplicación) idéntico a Python; puerto EFR32MG26 (driver, Matter con clúster de fabricante, diagnóstico COBS) | equivalencia C↔Python de punta a punta con gcc y clang, ASan/UBSan; el puerto, solo comprobación sintáctica contra cabeceras simuladas del SDK | compilar con el Simplicity SDK, medir ciclos y RAM, 7 días contra Aqara FP2 |
| F4 | Esquema rev A y PCB de 4 capas colocada y rutada, con ficheros de fabricación; carcasa, tapa, radomo λ/2 y cupón en FreeCAD | ERC y DRC de KiCad sin errores y sin diferencias esquema-placa; aserciones de `mechanical/freecad_carcasa.py` con la placa montada real | contrastar con la guía de Infineon, elegir piezas LCSC y pedir tras cerrar F2 ([09](09_hardware.md#estado-de-la-pcb-rev-a)) |

La integración continua (`.github/workflows/ci.yml`) ejecuta las pruebas
del firmware con gcc y clang y la equivalencia con sanitizadores en cada push.
