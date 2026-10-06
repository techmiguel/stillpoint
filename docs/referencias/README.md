# Documentación de referencia

Hojas de datos usadas en la revisión del diseño rev A. Cada dato contrastado y
el cambio que provocó están en [docs/09_hardware.md](../09_hardware.md#verificación-con-las-hojas-de-datos-docsreferencias).

| Fichero | Componente | Usado para |
|---|---|---|
| `infineon-bgt60tr13c-datasheet-en.pdf` | BGT60TR13C, hoja v2.4.9 | bolas, alimentación y ruido, reloj, VAREF, consumos |
| `infineon-ug091722-bgt60tr13c-shield-usermanual-en.pdf` | placa de referencia BGT60TR13C shield, rev 2.50 | patrón de pads, filtros π por dominio, oscilador y su resistencia serie |
| `mgm260p-datasheet.pdf`, `Silicon_Laboratories_mgm260p_datasheet.pdf` | MGM260P, rev 1.1 | códigos de pedido, patillaje, patrón de soldadura, zona de antena, consumos |
| `mgm240p-datasheet.pdf` | MGM240P | compatibilidad de huella (fila exterior) |
| `ug613-xgm260-ek2713a-user-guide.pdf` | kit de evaluación xGM260P | fase F2 |
| `gswitch_gtusb7051a_apr22_xonlink.pdf` | USB-C vertical GT-USB-7051A | altura y patrón |
| `AP2112-271550.pdf` | LDO AP2112 | ruido, θJA, corriente |
| `SiT8008B-datasheet.pdf` | oscilador SiT8008 | jitter (descartado: no cumple 1 ps) |
| `sn74avc4t245.pdf` | traductor SN74AVC4T245 | patillaje, DIR/OE, entradas sin usar |
| `cp2102n-datasheet.pdf` | CP2102N | alimentación sin regulador, RSTb, VBUS |
| `DS_usblc6-2.pdf` | USBLC6-2 | patillaje |

Faltan, para cerrar el pedido: la hoja del Kyocera KC2520K de 80 MHz elegido y
la del TI TPS7A20 (su patillaje SOT-23-5 se ha tomado del resumen de TI).
