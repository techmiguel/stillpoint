# 08 · Banco de pruebas

Sirve para dos cosas: medir los criterios de [01](01_criterios_aceptacion.md)
y comparar con un sensor comercial en las mismas condiciones.

## Montaje

- Sala de 4 × 4 m con puerta marcada como zona de salida.
- Dispositivo bajo prueba (DUT) y Aqara FP2 en el techo, separados ≤ 30 cm,
  con la misma configuración de zonas.
- Ambos integrados en el mismo Home Assistant; el FP2 por su integración
  local, el DUT por Matter. El registro de HA se exporta a CSV.
- Verdad de terreno: guion + aplicación de marcas de tiempo (NTP).
- Marcas en el suelo cada 0,5 m para el error de posición (P7).

## Escenarios

| ID | Escenario | Criterios |
|---|---|---|
| E1 | Entrar, recorrer, salir por la puerta | P4, P5, P6 |
| E2 | Sentarse quieto 30 min (lectura, pantalla) | P1 |
| E3 | Dormir / tumbarse 2 h | P1, A2 |
| O1 | Persona quieta; otra pasa por delante | P2 |
| O2 | Persona quieta; otra se detiene 30 s tapándola y sale | P2 |
| G1 | Sala vacía con ventilador de pie encendido 8 h | P3 |
| G2 | Sala vacía con cortina movida por un ventilador | P3 |
| G3 | Espejo ≥ 1 m² en una pared; una persona camina junto a él | P6 |
| A3–A5 | Acostarse rápido en la cama, sentarse de golpe, agacharse | F4 |
| C1 | Caídas simuladas del guion de [07](07_protocolo_datos.md) | F1, F3 |
| V1 | Vida diaria en un hogar, 30 días-sensor | F2, P3 |
| M1–M3 | Puesta en marcha ×10, reinicio del router Thread, corte de alimentación | S1, S2 |

## Métricas

[metrics.py](../ml/radarref/metrics.py) calcula:

- Proporciones (P1, F1…) con intervalo de Wilson.
- Tasas por día (P3, F2) con intervalo de Poisson exacto. Con 0 eventos, el
  informe dice «0 en N días; cota superior 95 %: 3,69/N por día» y no «sin
  falsas alarmas».
- Latencias como p50/p95 emparejando cada evento con la primera detección.

## Informe publicado

Para cada criterio: valor del DUT, valor de la referencia, n, intervalo,
cumple/no cumple, y las limitaciones (caídas simuladas, una sala, altura de
montaje). Se publican también los fallos y los escenarios donde la
referencia gana.
