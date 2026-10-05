# 03 · Interfaces y responsables

Cada bloque tiene un responsable único. Un cambio en una interfaz lo propone
quien produce el dato y lo aprueba quien lo consume.

| Bloque | Responsable | Entrega |
|---|---|---|
| HW: placa, alimentación, RF | R-HW | esquema, PCB, BOM, informe de puesta en marcha |
| FW-DSP: radar, DSP, seguimiento | R-DSP | firmware de detección y registros del contrato |
| FW-Matter: modelo de datos, Thread | R-MAT | endpoints, puesta en marcha, OTA |
| ML: datos, modelo, decisión | R-ML | artefacto de modelo + informe de métricas |
| MEC: radomo y carcasa | R-MEC | STL/SCAD, informe de cupones |
| Banco: protocolo, métricas, comparación | R-BAN | registros, informe publicado |

> En un equipo de una persona, los roles se mantienen igualmente: cada
> entrega se revisa con el sombrero del consumidor antes de darla por buena.

## Interfaces

| ID | De → a | Formato | Fuente de verdad | Prueba que la protege |
|---|---|---|---|---|
| I1 | Radar → DSP | trama ADC int16 (3 × 32 × 128), cabecera con nº de trama y configuración | `RadarConfig` / `radar_limits.h` | `RadioLimitsTest`, `test_limits` (C) |
| **I2** | **DSP → ML** | **registro de características v1, 66 B** | **[contracts/features_v1.yaml](../contracts/features_v1.yaml)** | `ContractTest`, `golden_v1.h` (C) |
| I3 | ML → firmware | `model_int8.tflite` + `model_meta.json` + `model_data.h` | `ml/train.py` | `model_guard.h` (no compila si el hash no coincide) |
| I4 | Firmware → domótica | Matter (endpoints y clústeres) | [04](04_matter.md) | banco M1–M3 |
| I5 | HW ⇄ MEC | contorno de placa, cota antena–radomo, taladros | `mechanical/radomo.scad` | cupones F4 |
| I6 | Todos → banco | CSV de eventos con reloj NTP | [08](08_banco_pruebas.md) | script de métricas |

## I2 en detalle: el contrato de características

Es la interfaz que más daño hace si se rompe en silencio: un modelo entrenado
con una escala distinta sigue «funcionando» y da resultados basura.

- 24 campos `int16` en unidades físicas escaladas (mm, mm/s, cdB, mHz…). Lista
  y escalas en el YAML.
- Hash CRC-32 de la forma canónica (nombre | unidad | escala + parámetros de
  ventana). Viaja en cada registro (16 bits) y en el modelo (32 bits).
- El firmware **no compila** con un modelo de otro contrato
  (`_Static_assert` en `model_guard.h`) y la referencia Python **no carga** el
  modelo (`ModelMismatch`).
- El entrenamiento usa los valores *después* de cuantizar/decuantizar: el
  modelo ve exactamente lo que verá en la placa.
- Vectores dorados: `tools/gen_contract.py` genera los bytes esperados con
  Python; `firmware/tests/test_host.c` exige que C produzca los mismos.
- La normalización (media/desviación) y los límites de fuera de distribución
  van en `model_meta.json`, no en el contrato.
- Cambiar orden, unidad, escala o significado ⇒ `features_v2.yaml`. Las
  versiones publicadas no se editan.

Flujo al cambiar el contrato:

```bash
python tools/gen_contract.py
```

```bash
make -C firmware test
```

```bash
python -m unittest discover -s ml/tests
```
