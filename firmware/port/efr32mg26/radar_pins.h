/* Pines del radar. Valores para la placa propia rev A (hardware/radar60.kicad_sch);
 * con el kit de desarrollo, ajustarlos al cableado de la placa del radar. */
#pragma once
#include "em_gpio.h"

#define RADAR_CS_PORT gpioPortC
#define RADAR_CS_PIN 3
#define RADAR_RST_PORT gpioPortC
#define RADAR_RST_PIN 4
#define RADAR_IRQ_PORT gpioPortC
#define RADAR_IRQ_PIN 5
/* SPI (instancia spidrv "radar", EUSART1): SCLK PC0, MOSI PC1, MISO PC2 */
