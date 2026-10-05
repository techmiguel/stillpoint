# 09 · Hardware (rev A, fase F4)

La placa se diseña **después** de cerrar F2 con kits. Este documento fija
desde ahora los requisitos que el esquema debe cumplir.

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

## Puntos de prueba (obligatorios)

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
