# 01 · Criterios de aceptación (v1)

Fijados el 2026-10-05, **antes** de tener hardware. Cambiarlos exige anotar
la fecha, el motivo y el valor anterior al final de este documento; nunca se
ajustan para que un resultado pase.

Todas las métricas se miden en el banco de [08](08_banco_pruebas.md), sobre
personas y habitaciones que no participaron en el entrenamiento, y se
publican con su n y su intervalo de confianza del 95 %.

## Presencia

| ID | Métrica | Umbral | Cómo se mide |
|---|---|---|---|
| P1 | Minutos ocupados detectados como ocupados (incluye personas quietas sentadas o tumbadas) | ≥ 99 % | por minuto, ≥ 20 h ocupadas |
| P2 | Persona quieta que desaparece cuando otra pasa por delante | 0 casos en ≥ 50 pases (cota sup. 95 % ≤ 6 %) | escenarios O1–O2 |
| P3 | Falsas ocupaciones en sala vacía con ventilador, cortina y espejo | ≤ 1 por día | ≥ 7 días vacía; Poisson exacto |
| P4 | Latencia entrada → ocupado | p95 ≤ 1,0 s | ≥ 50 entradas |
| P5 | Latencia salida por la puerta → vacío | p95 ≤ 5 s | ≥ 50 salidas |
| P6 | Recuento exacto (0–3 personas) | ≥ 90 % del tiempo | por segundo |
| P7 | Error de posición horizontal | mediana ≤ 0,30 m; p90 ≤ 0,50 m | contra marcas en el suelo |

## Postura

| ID | Métrica | Umbral |
|---|---|---|
| A1 | F1 macro de, sentada, tumbada (ventanas no abstenidas) | ≥ 0,85 |
| A2 | Tasa de «incierto» en condiciones normales | ≤ 5 % del tiempo |

## Caída

| ID | Métrica | Umbral | n mínimo y motivo |
|---|---|---|---|
| F1 | Caídas simuladas notificadas (confirmada o incierta) | ≥ 90 %, límite inferior IC95 ≥ 80 % | ≥ 100 caídas: con 90/100 el Wilson inferior es 0,83 |
| F2 | Falsas alarmas de caída en vida diaria | ≤ 0,1 por día | ≥ 30 días-sensor sin alarma (regla del tres: 3/30 = 0,1) |
| F3 | Latencia caída → notificación Matter | p95 ≤ 10 s | ≥ 100 caídas |
| F4 | Acostarse en cama, sentarse de golpe, agacharse | 0 alarmas en ≥ 50 de cada | escenarios A3–A5 |

## Sistema

| ID | Métrica | Umbral |
|---|---|---|
| S1 | Puesta en marcha Matter con Home Assistant | 10/10 sin reintentos manuales |
| S2 | Recuperación tras reinicio del router Thread | ≤ 60 s |
| S3 | Consumo | ≤ 1,0 W medio a 5 V |
| S4 | Emisión | 57–64 GHz y ≤ 20 dBm PIRE, verificado por configuración y medida aproximada |
| S5 | Temperatura de la carcasa | ≤ 15 °C sobre ambiente |

## Criterio de abandono

Al cerrar la fase F2 (cadena en kits, [06](06_plan_fases.md)) se compara
con el sensor comercial de referencia (Aqara FP2) en el mismo banco y el mismo
periodo. **Si el prototipo no iguala al de referencia en P1, P2 y P3, el
proyecto se detiene** o se replantea por escrito antes de fabricar placa.

## Registro de cambios de criterios

| Fecha | Criterio | Antes | Después | Motivo |
|---|---|---|---|---|
| — | — | — | — | — |
