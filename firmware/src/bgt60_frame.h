/* Conversión del FIFO del BGT60TR13C al formato de trama del firmware.
 *
 * El FIFO entrega muestras de 12 bits sin signo intercaladas por antena:
 *   para cada chirp, para cada muestra: RX1, RX2, RX3.
 * Salida: int16 [rx][chirp][muestra] sin componente continua por chirp, en
 * cuentas (±2047). Es exactamente la conversión de ml/capture_kit.py::to_signed,
 * con la que se graban los datos de entrenamiento reales. */
#pragma once
#include <stdint.h>

#include "dsp.h"

#define RF_FIFO_SAMPLES (RF_N_RX * RF_N_CHIRPS * RF_N_SAMPLES)

void rf_bgt60_unpack(const uint16_t fifo[RF_FIFO_SAMPLES], int16_t adc[RF_FIFO_SAMPLES]);

/* Lectura del FIFO por bytes: cada 3 bytes (MSB primero) llevan 2 muestras de 12 bits.
 * n_samples debe ser par (lo exige también el driver de Infineon). */
void rf_bgt60_unpack12(const uint8_t *bytes, uint16_t *samples, uint32_t n_samples);
