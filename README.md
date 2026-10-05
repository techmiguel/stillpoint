# radar60 · Sensor de presencia y caídas por radar de 60 GHz

Sensor de techo, sin cámara ni micrófono, que indica cuántas personas hay en
una habitación, dónde están y en qué postura, y notifica caídas. Detecta a
quien está completamente quieto por el movimiento del pecho al respirar. Todo
se calcula en el aparato y se publica por **Matter sobre Thread**, sin nube ni cuenta.

> **No es un dispositivo médico.** La detección de caídas es una notificación,
> nunca el único medio de seguridad de una persona.

## Estado: fase F0 cerrada (definición + cadena de referencia)

| Bloque | Estado |
|---|---|
| Criterios numéricos, alcance, interfaces, plan, riesgos | ✅ [docs/](docs) |
| Contrato de características firmware ↔ entrenamiento (v1, 66 B) | ✅ [contracts/features_v1.yaml](contracts/features_v1.yaml) |
| Cadena de referencia Python: simulador FMCW → DSP → seguimiento → características → modelo int8 → decisión | ✅ [ml/radarref](ml/radarref) |
| Pruebas de regresión de los fallos conocidos (oclusión, ventilador, espejo, latencia) | ✅ 22 pruebas en verde |
| Código C portable: registro del contrato, decisión con fallo seguro, límites RF, guardia de modelo | ✅ compila; ⏳ falta ejecutar `make -C firmware test` en PC |
| Captura con kit de evaluación (F1), firmware embebido + Matter (F2) | ⏳ |
| Campaña de datos reales, placa, radomo, banco final (F3–F5) | ⏳ |

Todas las cifras actuales salen de **simulación**: validan que la cadena
funciona de extremo a extremo, no el producto. No se publican como métricas.

![oclusión](docs/img/escenario_occlusion.png)
![caída](docs/img/eventos_caida.png)

## Documentación

| | |
|---|---|
| [00 Alcance y límites](docs/00_alcance_y_guardrails.md) | qué es, qué no, respuesta a cada problema conocido |
| [01 Criterios de aceptación](docs/01_criterios_aceptacion.md) | umbrales numéricos y criterio de abandono |
| [02 Arquitectura](docs/02_arquitectura.md) | bloques, componentes, presupuesto de cómputo |
| [03 Interfaces y responsables](docs/03_interfaces_y_responsables.md) | I1–I6; el contrato de características |
| [04 Matter](docs/04_matter.md) | endpoints y clústeres |
| [05 Emisión 60 GHz](docs/05_regulatorio_60ghz.md) | límites en Europa y cómo se imponen |
| [06 Plan por fases](docs/06_plan_fases.md) | puertas de fase y material |
| [07 Protocolo de datos](docs/07_protocolo_datos.md) · [consentimiento](docs/07b_consentimiento_plantilla.md) | grabación, etiquetado, separación |
| [08 Banco de pruebas](docs/08_banco_pruebas.md) | escenarios y métricas con IC |
| [09 Hardware](docs/09_hardware.md) | BOM, puntos de prueba, fabricación |
| [10 Riesgos](docs/10_riesgos.md) | riesgos y limitaciones conocidas |

## Uso

Requisitos: Python 3.10+, `pip install -r requirements.txt`.

Pruebas (desde `ml/`):

```bash
python -m unittest discover -s tests -v
```

Figuras de los escenarios:

```bash
python plot_scenarios.py
```

Conjunto sintético, entrenamiento y evaluación por eventos:

```bash
python make_synth_dataset.py --jobs 4
```

```bash
python train.py
```

```bash
python eval_events.py
```

Tras cambiar el contrato (desde la raíz):

```bash
python tools/gen_contract.py
```

```bash
make -C firmware test
```

## Estructura

```
contracts/   contrato de características (fuente de verdad de I2)
docs/        ingeniería: criterios, arquitectura, plan, protocolo, banco
firmware/    C portable + pruebas contra vectores dorados de Python
mechanical/  radomo y carcasa paramétricos (OpenSCAD)
ml/          cadena de referencia, simulador, entrenamiento, métricas
tools/       generadores (cabeceras C, vectores dorados)
```
