/* Pins of the rev A board (hardware/radar60.kicad_sch, U2 = MGM260P).
 * On the development kit, adjust them to the wiring of the radar board. */
#pragma once
#include "em_gpio.h"

/* Radar: the signals leave from the module's bottom pad row (pads 16-22), which
 * faces the U7/U8 translators and the radar, so no route crosses another.
 * PD00/PD01 (pads 21/20) stay free for an optional 32.768 kHz crystal. */
#define RADAR_CS_PORT gpioPortD          /* pad 19, SPI_CS -> U7 1A1 -> CS_N */
#define RADAR_CS_PIN 2
#define RADAR_RST_PORT gpioPortD         /* pad 18, RAD_RST_3V3 -> U7 1A2 -> DIO3 */
#define RADAR_RST_PIN 3
#define RADAR_IRQ_PORT gpioPortC         /* pad 24, RAD_IRQ_3V3 <- U8 1A1 <- IRQ */
#define RADAR_IRQ_PIN 1
/* Enables U4 (TPS7A2018, +1V8_RAD); R3 keeps it off during reset. */
#define RADAR_PWR_EN_PORT gpioPortC      /* pad 26 */
#define RADAR_PWR_EN_PIN 3
/* 1OE/2OE of U7 and U8, active low; R13 holds it high (outputs high-Z)
 * until the firmware pulls it low. */
#define RADAR_OE_N_PORT gpioPortC        /* pad 25 */
#define RADAR_OE_N_PIN 2

/* SPI (spidrv instance "radar", EUSART1; EUSART routing accepts any port
 * on the MGM260P, datasheet table 6.x):
 *   SCLK PA07 (pad 16) · MOSI/TX PA08 (pad 17) · MISO/RX PC00 (pad 22).
 * CS driven as GPIO (RADAR_CS_*), not by the peripheral. */
#define RADAR_SPI_SCLK_PORT gpioPortA
#define RADAR_SPI_SCLK_PIN 7
#define RADAR_SPI_MOSI_PORT gpioPortA
#define RADAR_SPI_MOSI_PIN 8
#define RADAR_SPI_MISO_PORT gpioPortC
#define RADAR_SPI_MISO_PIN 0

/* Rest of the board */
#define BOARD_BTN_PORT gpioPortB         /* pad 3, SW1 to GND: internal pull-up */
#define BOARD_BTN_PIN 3
#define BOARD_TP_FRAME_PORT gpioPortB    /* pad 2, TP10 "frame processed" */
#define BOARD_TP_FRAME_PIN 4
/* RGB LED D1 (common anode to +3V3): low = on */
#define BOARD_LED_R_PORT gpioPortB       /* pad 6, R10 750 Ω */
#define BOARD_LED_R_PIN 0
#define BOARD_LED_G_PORT gpioPortB       /* pad 5, R11 1 kΩ */
#define BOARD_LED_G_PIN 1
#define BOARD_LED_B_PORT gpioPortB       /* pad 4, R12 330 Ω */
#define BOARD_LED_B_PIN 2
/* Console (CP2102N U5). Net names are from the CP2102N side:
 * VCOM_TX = CP2102N TXD -> MCU RX; VCOM_RX = CP2102N RXD <- MCU TX. */
#define BOARD_VCOM_RX_PORT gpioPortA     /* pad 12, net VCOM_TX */
#define BOARD_VCOM_RX_PIN 5
#define BOARD_VCOM_TX_PORT gpioPortA     /* pad 13, net VCOM_RX */
#define BOARD_VCOM_TX_PIN 6
