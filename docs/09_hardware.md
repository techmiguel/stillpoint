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

## BOM rev A (principales; completa en `hardware/fab/revA/bom.csv`)

| Ref | Pieza | Función | Notas |
|---|---|---|---|
| U1 | Infineon BGT60TR13C | radar 60 GHz, 1 TX / 3 RX, antenas en encapsulado | cara inferior; pads Ø0,275 según la placa de referencia de Infineon |
| U2 | Silicon Labs MGM260PB22VNA5 | EFR32MG26, Thread/Matter, +10 dBm, antena integrada | mismo encapsulado y patillaje que la variante de +20 dBm (MGM260PB32VNA5) |
| U3 | Diodes AP2112K-3.3 | 3,3 V (MCU, CP2102N, VDDLF) | 600 mA; θJA 184 °C/W |
| U4 | TI TPS7A2018PDBVR | 1,8 V del radar, 7 µVrms | mismo patillaje SOT-23-5 que el AP2112K; habilitado por el MCU |
| Y1 | Kyocera KC2520K, 80 MHz, 1,8 V | reloj del radar, cuarzo, jitter ≤ 1 ps | familia K de la placa de referencia (KC2016K); patrón 2520 estándar |
| U5 | Silicon Labs CP2102N-A02-GQFN24 | USB ⇄ UART de diagnóstico | regulador interno sin usar (fig. 2.3) |
| U6 | ST USBLC6-2SC6 | ESD de D+/D- y VBUS | |
| U7, U8 | TI SN74AVC4T245PW | traductores 3,3 V ⇄ 1,8 V del radar | aislamiento de VCC: alta impedancia con el radar apagado |
| J1 | G-Switch GT-USB-7051A | USB-C vertical | 7,5 mm sobre la placa |
| J2 | Tag-Connect TC2030-NL | SWD + reset + UART | solo pads |

## Requisitos del esquema

- Interfaz radar: SPI hasta 50 MHz, IRQ de FIFO, RST y, si existe, línea de
  disparo; nivel lógico compatible con el VDDIO elegido para U1 (verificar).
- Separación de dominios: el radar en un plano de masa continuo bajo U1;
  2,4 GHz de U2 en el extremo opuesto de la placa.
- Radar orientado al centro de la ventana del radomo; nada metálico (tornillos,
  blindajes, cobre) en el cono de ±60° delante de las antenas.
- Dimensiones objetivo: placa redonda Ø 60 mm, 4 capas.

## Verificación con las hojas de datos (docs/referencias)

Datos contrastados con los PDF del fabricante y cambios que provocaron:

| Componente | Comprobado | Resultado |
|---|---|---|
| BGT60TR13C (hoja v2.4.9, tabla 1) | 40 bolas y funciones | coincide con el esquema (A1/A2 VSSD, K1 VSSA, 20 VSSRF, DIO3 = reset) |
| BGT60TR13C (shield, fig. 5c) | patrón de pads | orientación correcta (rotación sin espejo); **pads Ø0,25 → Ø0,275** |
| BGT60TR13C (§8.1) | VAREF | **C16 100 nF → 470 nF** de baja ESR |
| BGT60TR13C (tabla 5) | ruido de alimentación ≤ 20 µVpp en 20-700 kHz en cada raíl | **U4 AP2112K-1.8 (50 µVrms) → TPS7A2018 (7 µVrms)**; desacoplos como la placa de referencia: **C8 → 10 µF, C9/C10 → 1 µF, C12 → 10 µF, C17 → 1 µF**; VDDLF (≤ 0,5 mA) con filtro RC: **FB4 → R13 47 Ω y C15 → 10 µF** (corte < 1 kHz, caída 23 mV) |
| BGT60TR13C (tabla 5) | reloj: 75-85 MHz CMOS 1,8 V, jitter de fase 1 ps (12 kHz-20 MHz) | el **SiT8008 MEMS da 1,3 ps típ. / 2 ps máx.: no cumple**. Pasa a cuarzo **Kyocera KC2520K** (1,0 ps; 0,5 ps en la versión de bajo ruido), con el mismo patrón 2520 y patillaje |
| Shield (§3.4) | serie del reloj | **R4 22 Ω → 150 Ω** (valor de Infineon). Se ajusta en F2: si hay pico a corta distancia en el mapa distancia-Doppler, subirla; si empeora el ruido de fase, bajarla |
| Shield (fig. 6) | filtros π por dominio | iguales en RF, A, D y LF. Diferencia aceptada: PLL y VCO comparten el filtro de RF (Infineon los separa); se vigila el ruido de fase en F2 |
| MGM260P (hoja rev 1.1) | patillaje de 36 pads | coincide con el esquema (VDD 15, RESETn 31, SPI en PC00-PC03, UART en PA05/PA06) |
| MGM260P (fig. 8.2) | patrón de soldadura y zona de antena | coinciden: columnas a 11,30, pads 2,4 × 0,6, zona sin cobre 8,8 × 4,8 mm; módulo en el centro de un borde y plano de 60 mm (pide 50-60) |
| MGM260P (tabla 2.1) | código de pedido | el esquema decía MGM260PB32VNA, incompleto; **pasa a MGM260PB22VNA5 (+10 dBm)**, que fija por hardware el límite de potencia del balance |
| MGM260P (fig. 8.1) | altura | 2,15 nominal, 2,35 máx.: modelo 3D a 2,35 |
| GT-USB-7051A (plano) | altura | 7,50 mm: modelo 3D actualizado; la comprobación mecánica sigue en 0 mm³ |
| AP2112 | θJA SOT-23-5 | 184 °C/W (se suponían 250) |
| SN74AVC4T245 | patillaje, DIR/OE, entradas sin usar | correcto: DIR alto A→B, OE activo bajo; 2B1/2B2 de U8 a GND como exige TI |
| CP2102N (fig. 2.3) | alimentación sin regulador, RSTb, VBUS | correcto (VREGIN = VDD = 3,3 V, 1 kΩ en RSTb, divisor 22,1/47,5 kΩ); **C25 1 µF → 4,7 µF** (pide 4,7 µF + 0,1 µF) |
| USBLC6-2 | patillaje | correcto |

Riesgos que quedan para F2, sin solución de diseño posible antes de medir:
- **Plástico junto a la antena del módulo.** Silicon Labs pide evitar dieléctricos
  cerca de la antena. La pared de la carcasa (2 mm de PLA) queda a unos 1,5 mm
  del borde del módulo. Medir el RSSI con y sin carcasa; si se pierden más de
  3 dB, adelgazar la pared en ese sector.
- **Temperatura del radar.** La cara del chip debe quedar por debajo de 70 °C.
  Disipa unos 60 mW de media, pero hay que medirla con su sensor interno dentro
  de la carcasa cerrada.

## Estado de la PCB rev A

**Diseño terminado** (KiCad 10, `hardware/`): ERC sin errores, DRC sin errores
ni conexiones pendientes y sin diferencias con el esquema. Solo quedan dos
avisos: U7/U8 difieren de la biblioteca porque su marca de pin 1 se desplazó
0,9 mm para que no la tapen C18/C20. Ficheros de fabricación y procedimiento en
[hardware/scripts](../hardware/scripts/README.md).

![cara superior](img/pcb_revA_superior.png) ![cara inferior](img/pcb_revA_inferior.png)

| Aspecto | Decisión |
|---|---|
| Apilado | 4 capas JLC04161H-7628, 1,6 mm: F.Cu señal · In1 GND entero (sin pistas) · In2 alimentaciones/señal con relleno de GND · B.Cu radar |
| Radar U1 | cara inferior, centrado en la ventana del radomo (100, 100), fila de señales hacia los traductores; GND sólido en In2 bajo el encapsulado |
| Fan-out del BGA | sin vía en pad: las bolas de señal y alimentación están en el anillo exterior; pistas de 0,15-0,25 mm; B3/B4/B8 unidas a su vecina de GND; vías de GND dentro del anillo solo donde la cara superior está libre |
| Desacoplos del radar | cada bola de alimentación va directa a su condensador (≤ 3 mm), sin vía entre ambos; ferritas y bulk de cada raíl en la cara inferior |
| Reloj 80 MHz | M2 → R4 (150 Ω, ajustable en F2) → Y1 entero en B.Cu: 6,3 mm |
| SPI del radar | 13-17 mm por traza, vías escalonadas bajo U8 hacia los traductores |
| USB (velocidad completa) | D+/D- de 0,2 mm; protector ESD U6 con vía de GND en su pad |
| MGM260P | antena hacia el borde, sin cobre ni vías en ninguna capa bajo ella |
| GND | rellenos en las 4 capas, ~490 vías de cosido y una vía junto a cada pad de GND, todas validadas con la DRC |
| Mecánica | sin componentes sobre los apoyos de la carcasa; componente más alto 7,5 mm arriba (J1) y 1,19 mm abajo |

Comprobaciones mecánicas con la placa montada (STEP exportado de KiCad, ver
`mechanical/cad/comprobaciones.json`): interferencia placa-carcasa, placa-tapa
y componentes en el cono de ±60° de las antenas: 0 mm³. Una clavija USB-C con
funda de 12,4 × 6,6 mm colocada sobre el J1 real pasa por la tapa; el paso de
cable se movió a la vertical de J1, a 16 mm del centro (con el paso centrado
anterior la comprobación falla).

**Pendiente antes de pedir la placa**:

1. Elegir piezas en LCSC (columna `LCSC` de `bom.csv`), comprobar existencias
   del BGT60TR13C, el MGM260P, el TPS7A2018 y el KC2520K, y revisar las
   rotaciones del CPL en el visor del fabricante. El montaje es a doble cara.
2. Confirmar con la hoja del KC2520K elegido (código exacto de 80 MHz y 1,8 V)
   que su patrón coincide con la huella 2520 actual (pads de 1,1 × 1,0 a ±0,95 × ±0,75).
3. Pedir solo tras cerrar F2: cualquier cambio de pines o alimentación que salga
   de los kits se incorpora antes aquí.

## Balance de alimentación (estimado; se mide en F2)

U3 (AP2112K-3.3, SOT-23-5) baja de 5 V a 3,3 V todo el consumo, incluido el del
radar a través de U4. Ciclo de trama v1: 32 chirps de 350 µs cada 100 ms, más
~2 ms de arranque y lectura del FIFO (13 % de ciclo). Con el MGM260PB22VNA5
(+10 dBm):

| | 3V3 pico | U3 pico | 3V3 medio | U3 medio |
|---|---|---|---|---|
| Estimación | 273 mA | 0,46 W | 59 mA | 0,10 W (≈ +18 °C con 184 °C/W) |

U4 (TPS7A2018) disipa 0,34 W durante 13 ms en cada trama y unos 52 mW de media.

Supuestos (hojas de datos):
- radar a 230 mA en activo (máximo, tabla 6) y 2,8 mA en reposo;
- MGM260P: 19,4 mA transmitiendo a +10 dBm (1 % del tiempo), 6 mA en
  recepción y unos 4 mA de CPU a 80 MHz;
- CP2102N a 10 mA y LED encendido.

El pico de 5 V queda por debajo de 0,3 A, lejos de la corriente de
mantenimiento del fusible rearmable. En F2 hay que medir la corriente media y
la temperatura de U3 y U4 dentro de la carcasa cerrada. Si U3 supera 85 °C, se
sustituye por un regulador conmutado de 3,3 V. En ese caso, VDDLF sigue
protegida por su filtro RC.

## Puntos de prueba (obligatorios)

| TP | Señal | Para qué |
|---|---|---|
| TP1–TP3 | 5 V, 3,3 V, 1,8 V | puesta en marcha y medida de consumo |
| TP4 | GND | sondas (más GND en el Tag-Connect J2) |
| TP5–TP8 | SPI SCLK, MOSI, MISO, CS del radar | analizador lógico |
| TP9 | IRQ del radar | latencia y temporización de trama |
| TP10 | GPIO libre «trama procesada» | medir ciclos de DSP con osciloscopio |
| TP11–TP12 | UART TX/RX | consola sin USB |

## Fabricación (JLCPCB / PCBWay)

- Exportar con `bash hardware/scripts/fabricacion.sh` (falla si el ERC o la DRC tienen errores): Gerber, taladros, BOM y posiciones en `hardware/fab/revA/`.
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
