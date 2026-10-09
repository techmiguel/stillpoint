/* BGT60TR13C FIFO to firmware frame conversion.
 *
 * The FIFO delivers unsigned 12-bit samples interleaved by antenna:
 *   for each chirp, for each sample: RX1, RX2, RX3.
 * Output: int16 [rx][chirp][sample] with the per-chirp DC removed, in
 * counts (±2047). Exactly the conversion of ml/capture_kit.py::to_signed,
 * which is used to record real training data. */
#pragma once
#include <stdint.h>

#include "dsp.h"

#define RF_FIFO_SAMPLES (RF_N_RX * RF_N_CHIRPS * RF_N_SAMPLES)

void rf_bgt60_unpack(const uint16_t fifo[RF_FIFO_SAMPLES], int16_t adc[RF_FIFO_SAMPLES]);

/* Byte-wise FIFO read: every 3 bytes (MSB first) carry two 12-bit samples.
 * n_samples must be even (the Infineon driver requires it too). */
void rf_bgt60_unpack12(const uint8_t *bytes, uint16_t *samples, uint32_t n_samples);
