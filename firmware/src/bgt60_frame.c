#include "bgt60_frame.h"

#include <math.h>

void rf_bgt60_unpack12(const uint8_t *bytes, uint16_t *samples, uint32_t n_samples)
{
    for (uint32_t i = 0; i + 1 < n_samples; i += 2) {
        const uint8_t *b = bytes + (i / 2) * 3;
        samples[i] = (uint16_t)((b[0] << 4) | (b[1] >> 4));
        samples[i + 1] = (uint16_t)(((b[1] & 0x0F) << 8) | b[2]);
    }
}

void rf_bgt60_unpack(const uint16_t fifo[RF_FIFO_SAMPLES], int16_t adc[RF_FIFO_SAMPLES])
{
    for (int c = 0; c < RF_N_CHIRPS; c++) {
        for (int rx = 0; rx < RF_N_RX; rx++) {
            double mean = 0.0;
            for (int s = 0; s < RF_N_SAMPLES; s++) {
                mean += fifo[((size_t)c * RF_N_SAMPLES + s) * RF_N_RX + rx] & 0x0FFF;
            }
            mean /= RF_N_SAMPLES;
            int16_t *out = adc + ((size_t)rx * RF_N_CHIRPS + c) * RF_N_SAMPLES;
            for (int s = 0; s < RF_N_SAMPLES; s++) {
                double v = rint((double)(fifo[((size_t)c * RF_N_SAMPLES + s) * RF_N_RX + rx] & 0x0FFF) - mean);
                v = v > 2047.0 ? 2047.0 : (v < -2047.0 ? -2047.0 : v);
                out[s] = (int16_t)v;
            }
        }
    }
}
