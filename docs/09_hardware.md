# 09 · Hardware (rev A, fase F4)

El esquema rev A y la PCB se han adelantado en paralelo a F1–F2 para tener
la placa lista cuando los kits validen la arquitectura; **no se pide a
fábrica antes de cerrar F2**, porque cualquier cambio de pines, reloj o
alimentación que salga de los kits se incorpora primero aquí. Este documento
fija los requisitos que el esquema cumple y el estado del diseño.

## Datos verificados en la hoja de datos del BGT60TR13C (v2.4.6)

- Encapsulado PG-VF2BGA-40-1: 6,5 × 5 × 0,9 mm, 40 bolas de 0,3 mm a paso
  0,5 mm (rejilla A–M × 1–9: perímetro más B3, B4 y B8; no hay M8). Antenas en
  la cara superior del chip: el radar va en la **cara inferior** de la placa,
  mirando al suelo.
- **E/S a 1,8 V (máximo absoluto 2 V)**: con el MCU a 3,3 V hacen falta
  traductores de nivel en CLK, DI, CS_N, DIO3 (reset), DO e IRQ.
- Alimentación: VDDD, VDDA, VDDRF, VDDVCO y VDDPLL a 1,8 V (201 mA típ.,
  230 mA máx. en activo); VDDLF a 3,3 V; VAREF (1,2 V) es una salida que solo
  lleva condensador de desacoplo.
- OSC_CLK: reloj CMOS de 1,8 V a 80 MHz (75–85 MHz; 78 MHz no permitido),
  jitter de fase ≤ 1 ps: oscilador XO, no cristal.
- Reset por hardware obligatorio tras el arranque: con CS_N = 1, DIO3 hace 1→0→1 (≥ 100 ns).
- FIFO de 8192 palabras de 24 bits (dos muestras de 12 bits por palabra); SPI hasta 50 MHz.
- Potencia TX máxima (#31) = +5 dBm; ganancia de antena 3,5 dBi típ. (5 máx.):
  **PIRE máx. ≈ 10 dBm**, por debajo de los 20 dBm de la UE.
- Separación entre antenas RX: 2,5 mm (λ/2), coherente con la referencia.

## BOM preliminar

| Ref | Pieza | Función | Notas |
|---|---|---|---|
| U1 | Infineon BGT60TR13C | radar 60 GHz, 1 TX / 3 RX, antenas en encapsulado | huella, apilado y reglas de la nota de aplicación de Infineon; copiar la disposición de su placa de referencia |
| U2 | Silicon Labs EFR32MG26 | MCU + Thread + BLE + MVP | módulo o chip; un módulo certificado simplifica la parte de 2,4 GHz |
| Y1 | 80 MHz (según hoja de datos del BGT60) | reloj del radar | lo más cerca posible de U1 |
| U3 | LDO de bajo ruido 1,8 V | alimentación del radar | ruido de alimentación ⇒ espurios en el espectro: elegir según recomendación de Infineon |
| U4 | LDO 3,3 V ≥ 500 mA | MCU y periféricos | |
| U5 | CP2102N | USB datos ⇄ UART | captura de registros y de tramas reducidas a 3 Mbaud |
| J1 | USB-C receptáculo 16 pines | alimentación 5 V + datos USB 2.0 | resistencias CC 5,1 kΩ; ESD en D+/D-; fusible rearmable |
| J2 | Tag-Connect TC2030 o 2×5 1,27 mm | SWD + reset + UART | accesible con la carcasa abierta |
| D1 | LED RGB | estado: puesta en marcha, error de radar, caída | apagable por configuración (dormitorio) |
| SW1 | pulsador | puesta en marcha / restablecer | accesible con clip |

## Requisitos del esquema

- Interfaz radar: SPI hasta 50 MHz, IRQ de FIFO, RST y, si existe, línea de
  disparo; nivel lógico compatible con el VDDIO elegido para U1 (verificar).
- Separación de dominios: el radar en un plano de masa continuo bajo U1;
  2,4 GHz de U2 en el extremo opuesto de la placa.
- Radar orientado al centro de la ventana del radomo; nada metálico (tornillos,
  blindajes, cobre) en el cono de ±60° delante de las antenas.
- Dimensiones objetivo: placa redonda Ø 60 mm, 4 capas.

## Estado de la PCB rev A

Hecho (KiCad 10, `hardware/`): esquema con ERC sin errores, PCB sincronizada
con el esquema, contorno circular de Ø 60 mm y colocación de la cara superior
(MGM260P con la antena de 2,4 GHz hacia el borde, USB-C vertical, LDO, CP2102N,
traductores de nivel, SWD, pulsadores y puntos de prueba).

Pendiente, en este orden (requiere KiCad 10 con DRC; no se hace a mano sobre
el fichero porque el BGA de 0,5 mm y la zona de 60 GHz no admiten errores
sin verificación):

1. **Cara inferior**, mirando al suelo: U1 (BGT60TR13C) centrado en la ventana
   del radomo según `mechanical/cad/comprobaciones.json`; Y1 (80 MHz) pegado a
   OSC_CLK con R4 (22 Ω) en serie junto a Y1; desacoplos por bola
   C5–C17 a ≤ 1 mm de cada bola; FB1–FB3 (de +1V8_RAD a los raíles RF, A y D)
   y C22/C23 (desacoplo de 3,3 V en el lado del radar); R5/R6, polarizaciones
   a 1,8 V de CS_N y DIO3 junto a U1; D1 (LED RGB) junto al borde, visible desde abajo. Hoy estos 24
   componentes siguen fuera del contorno.
2. **Apilado de 4 capas** con control de impedancia (L1 señal, L2 GND
   continuo, L3 alimentación, L4 señal/radar) tomando del fabricante el
   apilado que pida la nota de aplicación de Infineon. Nada de cobre, vías ni
   serigrafía en el cono de ±60° delante de las antenas de U1, salvo lo que la
   huella de referencia de Infineon prevea.
3. **Fan-out del BGA**: vía en pad rellena y tapada (VIPPO) o perro-hueso
   según el paso de 0,5 mm y las reglas del fabricante elegido; comprobar
   antes el coste de VIPPO en JLCPCB/PCBWay.
4. **Rutado**: OSC_CLK lo más corto posible y sin cruzar divisiones del plano;
   SPI del radar (≤ 50 MHz) por L4 sobre GND continuo con la longitud
   igualada de forma grosera; USB D+/D− como par diferencial de 90 Ω; raíles de
   1,8 V del radar en estrella desde U4 a través de las ferritas.
5. **Zonas**: GND en L2 sin cortes bajo U1 y bajo la antena del MGM260P (que
   necesita además su zona de exclusión de cobre en todas las capas según la
   hoja de datos del módulo); costura de vías de GND en el borde.
6. **DRC** sin errores con las reglas del fabricante, revisión 3D contra
   `mechanical/cad/carcasa.step` (altura libre 8,4 mm sobre la placa).
7. **Fabricación**: Gerber, taladros, BOM y posiciones; verificar existencias
   del BGT60TR13C y del MGM260P en el servicio de montaje.



| TP | Señal | Para qué |
|---|---|---|
| TP1–TP3 | 5 V, 3,3 V, 1,8 V | puesta en marcha y medida de consumo |
| TP4 | GND (×3, repartidos) | sondas |
| TP5–TP8 | SPI SCLK, MOSI, MISO, CS del radar | analizador lógico |
| TP9 | IRQ del radar | latencia y temporización de trama |
| TP10 | GPIO libre «trama procesada» | medir ciclos de DSP con osciloscopio |
| TP11–TP12 | UART TX/RX | consola sin USB |

## Fabricación (JLCPCB / PCBWay)

- Exportar con `kicad-manufacture`: Gerber, taladros, BOM y posiciones.
- Pedir el apilado con control de impedancia que indique Infineon para la zona del radar.
- Montaje del BGT60TR13C por el fabricante (BGA/eWLB fino): verificar disponibilidad
  en su catálogo de componentes antes del pedido; si no lo hay, consigna de piezas.
- Lote rev A: 5 placas; 2 se reservan para pruebas destructivas/térmicas.

## Puesta en marcha (checklist)

1. Sin componentes de RF: rails, consumo en reposo, USB enumera.
2. SWD: programar firmware de diagnóstico; UART responde.
3. Radar: lectura del ID por SPI; trama de prueba; espectro sin espurios
   fijos con la sala vacía.
4. Mismo escenario que en el kit: los registros del contrato deben coincidir
   en distribución (presencia, recuento, altura) con los del kit.
