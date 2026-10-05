# 02 · Arquitectura

## Bloques

```
 USB-C 5V ─► LDO 3V3 (MCU) ─┬─► LDO bajo ruido 1V8 (radar)
          └─► CP2102N (USB datos ⇄ UART)
                             │
 ┌──────────────┐  SPI 50 MHz + IRQ + RST  ┌──────────────────────────────────────┐
 │ BGT60TR13C   │ ───────────────────────► │ EFR32MG26 (Cortex-M33 + MVP)         │
 │ 1 TX / 3 RX  │  FIFO → DMA              │  DSP: FFT rango, MTI+Doppler, CFAR,  │
 │ antenas AiP  │                          │       ángulo, micro-movimiento       │
 └──────────────┘                          │  Seguimiento + lógica de habitación  │
      radomo PETG ~1,5 mm (λ/2)            │  Características (contrato v1)       │
                                           │  Clasificador int8 (MVP) + decisión  │
                                           │  Matter / Thread (FTD router) / BLE  │
                                           └──────────────────────────────────────┘
                                             SWD · UART · puntos de prueba
```

Flujo por trama (10 Hz): muestras ADC → FFT de rango → dos caminos
(movimiento y micro-movimiento) → detecciones 3D → pistas → registro de 66 B por
pista. A 2 Hz, cada pista con 2 s de historia pasa por el clasificador y por
la máquina de estados de decisión; los cambios se publican por Matter.

La implementación de referencia está en [ml/radarref](../ml/radarref); el
firmware la porta bloque a bloque y se compara contra ella **en el contrato**
(los registros de características), no en los pasos intermedios.

## Elección de componentes

| Opción | Pros | Contras | Decisión |
|---|---|---|---|
| **A. EFR32MG26** (un chip) | Matter + Thread + BLE en un chip con SDK maduro; acelerador MVP; hasta 3,2 MB flash / 512 kB RAM | El MVP es un acelerador matricial, no una NPU completa; 78 MHz | **v1** |
| B. PSoC Edge E84 + EFR32MG24 | NPU Ethos-U55, más CPU; Infineon tiene kit con el mismo radar | Dos chips, Thread por coprocesador (RCP), más BOM y firmware | Plan B si F2 muestra falta de CPU |
| C. nRF54L15 | Buen soporte Matter en Zephyr | Sin acelerador de IA | Descartada por requisito |

> Verificar las cifras exactas de memoria y frecuencia en la hoja de datos de
> la variante concreta antes de cerrar el esquema.

El modelo actual ocupa 14,6 KB y hace ~0,1 M MAC por inferencia: la carga de
IA es pequeña. El cuello de botella previsto es el DSP, no la inferencia.

## Parámetros del radar (v1)

| Parámetro | Valor | Consecuencia |
|---|---|---|
| Barrido | 60,0–61,25 GHz (1,25 GHz) | resolución en distancia 12 cm |
| Muestras/chirp | 128 reales a 2 MS/s | 64 celdas → 7,7 m |
| Chirps/trama | 32 cada 350 µs | v máx ±3,5 m/s, resolución 0,22 m/s |
| Tramas | 10 Hz, ciclo de trabajo 11 % | |
| Antenas RX | en L, λ/2 | azimut y elevación → posición 3D y altura |

## Presupuesto de cómputo y memoria (estimado; se mide en F2)

| Bloque | Ciclos/trama (est.) | RAM (est.) |
|---|---|---|
| FFT de rango 96 × 128 real (q15) | ~0,5 M | 24 KB entrada + 24 KB salida |
| MTI + Doppler 3 × 40 × 32 complejo | ~0,3 M | 15 KB |
| CFAR + ángulo + agrupado | ~0,2 M | 4 KB |
| Micro-movimiento (cada 5 tramas, 100 × 3 × 40) | ~0,4 M amortizado | 48 KB |
| Seguimiento + características | < 0,1 M | 4 KB |
| Clasificador (2 Hz × 3 pistas) | < 0,1 M amortizado | 16 KB arena |
| **Total** | **~1,5 M de 7,8 M disponibles (≈ 20 %)** | **~140 KB** + pila Matter |

Si en F2 la ocupación medida supera el 50 % o la RAM libre baja de 64 KB, se
activa el plan B.

## Firmware (tareas)

| Tarea | Prioridad | Periodo | Entrada → salida |
|---|---|---|---|
| `radar_isr` / DMA | ISR | FIFO | SPI → búfer de trama |
| `dsp` | alta | 100 ms | trama → detecciones |
| `track` | alta | 100 ms | detecciones → pistas + registros |
| `infer` | media | 500 ms | ventanas → postura/caída |
| `matter` | media | eventos | estado → atributos/eventos |
| `diag` | baja | bajo demanda | registros por UART/USB (captura de datos) |

Código ya portable y probado contra Python: [features_pack.c](../firmware/src/features_pack.c),
[decision.c](../firmware/src/decision.c), [radar_limits.h](../firmware/src/radar_limits.h),
[model_guard.h](../firmware/src/model_guard.h).

## Decisiones clave

1. **Dos caminos de detección.** El MTI clásico borra a quien no se mueve; el
   camino de respiración lo recupera. Es la causa raíz del fallo «persona
   quieta desaparece».
2. **Lógica de habitación.** Las personas entran y salen por puertas. Una pista
   confirmada solo se borra rápido junto a una zona de salida; en mitad de la
   sala se conserva (60 s ocluida, 120 s si ya mostró respiración).
3. **Sin modos.** Zonas, postura y caída salen del mismo flujo de pistas.
4. **El modelo no ve la posición absoluta.** x, y, distancia y estado se
   excluyen de la entrada para no aprender la geometría de las salas de entrenamiento.
5. **Regla física + modelo para la caída.** La sospecha se abre por el modelo
   *o* por un descenso rápido hasta el suelo; la confirmación exige seguir en
   el suelo y quieto 4 s. Un único componente no puede disparar ni silenciar una alarma.
