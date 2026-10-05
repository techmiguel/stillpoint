# 00 · Alcance y límites

## Qué es

Sensor de techo, alimentado por USB-C, que con un radar FMCW de 60 GHz detecta
cuántas personas hay en **una** habitación, dónde están y en qué postura
(de pie, sentada, tumbada) y notifica caídas. No tiene cámara ni micrófono.
Todo el cálculo se hace en el aparato y el resultado se publica por Matter
sobre Thread, sin nube ni cuenta.

## Qué no es

- **No es un dispositivo médico.** La caída es una *notificación*; nunca el
  único medio de seguridad de una persona. Esta frase va en el README, en la
  caja y en la descripción del dispositivo en Matter.
- No mide constantes vitales con valor clínico. La respiración se usa solo
  como evidencia de presencia.

## Alcance de la v1 (cerrado)

| Tema | v1 | Fuera de v1 |
|---|---|---|
| Habitaciones | 1, hasta 4 × 4 m | varias, pasillos |
| Montaje | techo, 2,4–2,9 m, antenas al suelo | pared, esquina |
| Personas | hasta 3 (criterios medidos con 1–2) | más de 3, mascotas |
| Radar | BGT60TR13C con antenas en encapsulado | diseño de antenas propias |
| Alimentación | USB-C 5 V | batería |
| Salida | Matter 1.3+ sobre Thread | Wi-Fi, Zigbee, nube |

## Respuesta a los problemas conocidos de los productos comerciales

| Problema reportado | Respuesta de diseño | Dónde se verifica |
|---|---|---|
| Detecciones fantasma (ventilador, espejo) | Límites de sala, zonas excluidas, filtro de camino múltiple, aprendizaje de fuentes fijas con micro-Doppler sin respiración | `test_fan_becomes_interferer`, `test_mirror_ghost_not_counted`, banco G1–G3 |
| Persona quieta desaparece al pasar otra por delante | Camino de micro-movimiento (respiración) independiente del MTI; estado OCLUIDA; las pistas solo se borran rápido junto a una puerta | `test_still_person_survives_occlusion`, banco O1–O2 |
| Modos excluyentes (sueño / zonas / caída) | Un único flujo de pistas; zonas, postura y caída se calculan siempre a la vez. El presupuesto de cómputo se dimensiona para el peor caso | docs/02 §Presupuesto |
| Compromiso de batería | Fuera de alcance v1: alimentación por cable | — |
| Dependencia de ecosistema | Matter estándar; configuración local; sin cuenta | docs/04, banco M1 |
| Falta de métricas independientes | Criterios fijados antes de empezar, banco publicado, comparación con sensor comercial, intervalos de confianza | docs/01, docs/08 |

## Límites técnicos (resumen; detalle en cada documento)

- Criterios numéricos fijados antes de diseñar: [01](01_criterios_aceptacion.md).
- Toda la cadena se valida con kits antes de fabricar placa: [06](06_plan_fases.md).
- Fallo seguro: sin confianza se publica «incierto»; una posible caída que no
  puede verificarse se publica como «caída incierta», nunca se calla
  ([decision.py](../ml/radarref/decision.py)).
- Emisión dentro de 57–64 GHz y ≤ 20 dBm PIRE, impuesto en firmware
  ([05](05_regulatorio_60ghz.md), [radar_limits.h](../firmware/src/radar_limits.h)).
- Placa con SWD, UART, USB de datos y puntos de prueba accesibles ([09](09_hardware.md)).

## Límites de datos

- Consentimiento escrito de todas las personas grabadas ([plantilla](07b_consentimiento_plantilla.md)).
- Entrenamiento y prueba separados por persona **y** por habitación; el código
  lo impone ([split.py](../ml/radarref/split.py)).
- Las caídas son simuladas por adultos sanos sobre colchoneta; consta en cada
  métrica publicada.
- Los conjuntos públicos y el simulador sirven para prototipar; ningún modelo
  final se entrena solo con ellos y ninguna métrica publicada sale de ellos.
