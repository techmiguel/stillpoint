/* Portable floating-point radix-2 complex FFT.
 * On the EFR32MG26 it is replaced by the accelerated version (CMSIS-DSP / MVP)
 * with the same interface; the PC tests pin the behaviour. */
#pragma once
#include <stddef.h>

typedef struct {
    float re, im;
} rf_cpx_t;

/* In-place forward transform, n a power of 2 (n <= 1024). numpy convention:
 * X[k] = sum x[n] exp(-2*pi*j*k*n/N), unnormalized. */
void rf_fft(rf_cpx_t *x, size_t n);

/* DFT of a single bin k of a length-n signal with step `stride`. */
rf_cpx_t rf_dft_bin(const rf_cpx_t *x, size_t n, size_t stride, size_t k);

/* Hann window equal to numpy.hanning(n). */
void rf_hann(float *w, size_t n);
