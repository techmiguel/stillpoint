/* FFT compleja radix-2 en coma flotante (portable).
 * En el EFR32MG26 se sustituye por la versión acelerada (CMSIS-DSP / MVP)
 * con la misma interfaz; las pruebas en PC fijan el comportamiento. */
#pragma once
#include <stddef.h>

typedef struct {
    float re, im;
} rf_cpx_t;

/* Transformada directa in situ, n potencia de 2 (n <= 1024). Convenio numpy:
 * X[k] = sum x[n] exp(-2*pi*j*k*n/N), sin normalizar. */
void rf_fft(rf_cpx_t *x, size_t n);

/* DFT de un único bin k de una señal de longitud n con paso `stride`. */
rf_cpx_t rf_dft_bin(const rf_cpx_t *x, size_t n, size_t stride, size_t k);

/* Ventana de Hann igual a numpy.hanning(n). */
void rf_hann(float *w, size_t n);
