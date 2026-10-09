#include "nn.h"

#include <math.h>
#include <stddef.h>
#include <string.h>

#include "nn_model.h"

_Static_assert(NN_CONTRACT_HASH32 == RF_CONTRACT_HASH32,
               "nn_model.h was exported against another feature contract");

/* ---- gemmlowp / TFLite fixed-point arithmetic -------------------------------- */
static int32_t srdhm(int32_t a, int32_t b) /* SaturatingRoundingDoublingHighMul */
{
    if (a == b && a == INT32_MIN) {
        return INT32_MAX;
    }
    const int64_t ab = (int64_t)a * (int64_t)b;
    const int32_t nudge = ab >= 0 ? (1 << 30) : (1 - (1 << 30));
    return (int32_t)((ab + nudge) / (1LL << 31));
}

static int32_t rdbpot(int32_t x, int e) /* RoundingDivideByPOT */
{
    const int32_t mask = (int32_t)((1LL << e) - 1);
    const int32_t rem = x & mask;
    const int32_t thr = (mask >> 1) + (x < 0 ? 1 : 0);
    return (x >> e) + (rem > thr ? 1 : 0);
}

int32_t nn_multiply_by_quantized_multiplier(int32_t x, int32_t mult, int shift)
{
    const int left = shift > 0 ? shift : 0, right = shift > 0 ? 0 : -shift;
    return rdbpot(srdhm((int32_t)((int64_t)x * (1LL << left)), mult), right);
}

/* Single-rounding variant (TFLite int64 overload) used by the per-channel
 * dense layer. Checked: 0 mismatches in 2400 logits against TFLite;
 * the convolution's double rounding would give 5. */
static int32_t mbqm_single(int64_t x, int32_t mult, int shift)
{
    const int32_t reduced = mult < 0x7FFF0000 ? ((mult + (1 << 15)) >> 16) : 0x7FFF;
    const int total = 15 - shift;
    return (int32_t)((x * reduced + ((int64_t)1 << (total - 1))) >> total);
}

static int8_t clamp8(int32_t v, int32_t lo, int32_t hi)
{
    return (int8_t)(v < lo ? lo : (v > hi ? hi : v));
}

/* ---- layers (data in [length][channel]) ------------------------------------- */
static void conv(const nn_layer_t *L, const int8_t *in, int8_t *out)
{
    const int pad = (L->k - 1) / 2;
    for (int x = 0; x < L->out_len; x++) {
        for (int co = 0; co < L->out_ch; co++) {
            int32_t acc = L->b[co];
            for (int kk = 0; kk < L->k; kk++) {
                const int xi = x - pad + kk;
                if (xi < 0 || xi >= L->in_len) {
                    continue;
                }
                const int8_t *w = L->w + ((size_t)co * L->k + kk) * L->in_ch;
                const int8_t *v = in + (size_t)xi * L->in_ch;
                for (int ci = 0; ci < L->in_ch; ci++) {
                    acc += ((int32_t)v[ci] - L->in_zp) * w[ci];
                }
            }
            acc = nn_multiply_by_quantized_multiplier(acc, L->mult[co], L->shift[co]) + L->out_zp;
            out[(size_t)x * L->out_ch + co] = clamp8(acc, L->act_min, L->act_max);
        }
    }
}

static void pool(const nn_layer_t *L, const int8_t *in, int8_t *out)
{
    for (int x = 0; x < L->out_len; x++) {
        for (int c = 0; c < L->out_ch; c++) {
            int32_t acc = L->op == NN_MAXPOOL ? -128 : 0;
            for (int kk = 0; kk < L->k; kk++) {
                const int32_t v = in[(size_t)(x * L->k + kk) * L->in_ch + c];
                if (L->op == NN_MAXPOOL) {
                    acc = v > acc ? v : acc;
                } else {
                    acc += v;
                }
            }
            if (L->op == NN_AVGPOOL) {
                acc = acc > 0 ? (acc + L->k / 2) / L->k : (acc - L->k / 2) / L->k;
            }
            out[(size_t)x * L->out_ch + c] = clamp8(acc, L->act_min, L->act_max);
        }
    }
}

static void fc(const nn_layer_t *L, const int8_t *in, int8_t *out)
{
    for (int co = 0; co < L->out_ch; co++) {
        int32_t acc = L->b[co];
        const int8_t *w = L->w + (size_t)co * L->in_ch;
        for (int ci = 0; ci < L->in_ch; ci++) {
            acc += ((int32_t)in[ci] - L->in_zp) * w[ci];
        }
        acc = mbqm_single(acc, L->mult[co], L->shift[co]) + L->out_zp;
        out[co] = clamp8(acc, L->act_min, L->act_max);
    }
}

#define NN_BUF 1024

int rf_nn_infer(const float window[][RF_N_FIELDS], int8_t *logits, float *probs)
{
    static int8_t a[NN_BUF], b[NN_BUF];
    /* input normalization + quantization (rint = round half to even, like numpy) */
    for (int t = 0; t < NN_WINDOW; t++) {
        for (int j = 0; j < NN_N_IN; j++) {
            const double x = ((double)window[t][nn_used_idx[j]] - nn_mean[j]) / nn_std[j];
            double q = rint(x / NN_IN_SCALE + NN_IN_ZP);
            q = q < -128 ? -128 : (q > 127 ? 127 : q);
            a[t * NN_N_IN + j] = (int8_t)q;
        }
    }
    int8_t *src = a, *dst = b;
    for (int n = 0; n < NN_N_LAYERS; n++) {
        const nn_layer_t *L = &nn_layers[n];
        if (L->op == NN_CONV) {
            conv(L, src, dst);
        } else if (L->op == NN_FC) {
            fc(L, src, dst);
        } else {
            pool(L, src, dst);
        }
        int8_t *tmp = src;
        src = dst;
        dst = tmp;
    }
    memcpy(logits, src, NN_N_CLASSES);
    /* float softmax over the dequantized logits */
    double z[NN_N_CLASSES], zmax = -1e300, s = 0;
    for (int k = 0; k < NN_N_CLASSES; k++) {
        z[k] = ((double)logits[k] - NN_OUT_ZP) * NN_OUT_SCALE;
        zmax = z[k] > zmax ? z[k] : zmax;
    }
    for (int k = 0; k < NN_N_CLASSES; k++) {
        z[k] = exp(z[k] - zmax);
        s += z[k];
    }
    for (int k = 0; k < NN_N_CLASSES; k++) {
        probs[k] = (float)(z[k] / s);
    }
    /* out of distribution: last-frame features outside the training range */
    int ood = 0;
    for (int j = 0; j < NN_N_IN; j++) {
        const float v = window[NN_WINDOW - 1][nn_used_idx[j]];
        ood += (v < nn_ood_lo[j]) || (v > nn_ood_hi[j]);
    }
    return ood;
}

uint32_t rf_nn_model_hash(void) { return NN_MODEL_HASH32; }
