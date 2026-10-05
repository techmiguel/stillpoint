#include "rf_fft.h"

#include <math.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

void rf_fft(rf_cpx_t *x, size_t n)
{
    /* permutación por inversión de bits */
    for (size_t i = 1, j = 0; i < n; i++) {
        size_t bit = n >> 1;
        for (; j & bit; bit >>= 1) {
            j ^= bit;
        }
        j ^= bit;
        if (i < j) {
            rf_cpx_t t = x[i];
            x[i] = x[j];
            x[j] = t;
        }
    }
    for (size_t len = 2; len <= n; len <<= 1) {
        const double ang = -2.0 * M_PI / (double)len;
        for (size_t i = 0; i < n; i += len) {
            for (size_t k = 0; k < len / 2; k++) {
                const float wr = (float)cos(ang * (double)k);
                const float wi = (float)sin(ang * (double)k);
                rf_cpx_t *a = &x[i + k];
                rf_cpx_t *b = &x[i + k + len / 2];
                const float tr = b->re * wr - b->im * wi;
                const float ti = b->re * wi + b->im * wr;
                b->re = a->re - tr;
                b->im = a->im - ti;
                a->re += tr;
                a->im += ti;
            }
        }
    }
}

rf_cpx_t rf_dft_bin(const rf_cpx_t *x, size_t n, size_t stride, size_t k)
{
    double re = 0.0, im = 0.0;
    const double ang = -2.0 * M_PI * (double)k / (double)n;
    for (size_t i = 0; i < n; i++) {
        const double c = cos(ang * (double)i), s = sin(ang * (double)i);
        const rf_cpx_t v = x[i * stride];
        re += v.re * c - v.im * s;
        im += v.re * s + v.im * c;
    }
    rf_cpx_t out = {(float)re, (float)im};
    return out;
}

void rf_hann(float *w, size_t n)
{
    if (n == 1) {
        w[0] = 1.0f;
        return;
    }
    for (size_t i = 0; i < n; i++) {
        w[i] = (float)(0.5 - 0.5 * cos(2.0 * M_PI * (double)i / (double)(n - 1)));
    }
}
