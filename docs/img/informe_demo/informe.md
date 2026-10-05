# Informe del banco (DATOS DE DEMOSTRACIÓN)

> Datos sintéticos generados por bench/demo_datos.py para probar la herramienta. No describen ningún producto.

Duración: 24.0 h. Caídas simuladas por adultos sanos sobre colchoneta cuando las hay (docs/07).

| Criterio | Umbral | prototipo | referencia |
|---|---|---|---|
| P1 Minutos ocupados detectados | >= 0.99 | ✅ 99.7 % (609/611; IC95 98.8–99.9 %) | ❌ 98.4 % (601/611; IC95 97.0–99.1 %) |
| P3 Falsas ocupaciones por día (sala vacía) | <= 1 | ❌ 1.79 (1 en 13.4 h; IC95 sup. 9.95) | ❌ 0.00 (0 en 13.4 h; IC95 sup. 6.59) |
| P4 Latencia entrada → ocupado p95 (s) | <= 1 | ✅ 0.8 s (n=17) | ❌ 1.2 s (n=17) |
| P5 Latencia salida → vacío p95 (s) | <= 5 | ✅ 4.0 s (n=17) | ❌ 6.3 s (n=17) |
| F1 Caídas notificadas | >= 0.9 | ❌ 100.0 % (11/11; IC95 74.1–100.0 %) | ❌ 0.0 % (0/11; IC95 0.0–25.9 %) |
| F2 Falsas alarmas de caída por día | <= 0.1 | ❌ 0.00 (0 en 24.0 h; IC95 sup. 3.69) | ❌ 0.00 (0 en 24.0 h; IC95 sup. 3.69) |
| F3 Latencia caída → notificación p95 (s) | <= 10 | ✅ 8.3 s (n=11) | ❌ nan s (n=1), 1 no detectadas |

Criterio de abandono (docs/01): prototipo debe igualar a referencia en P1, P2 y P3. P2 se mide aparte con los escenarios O1–O2.
- P1: prototipo iguala o supera a referencia.
- P3: prototipo NO iguala a referencia.
