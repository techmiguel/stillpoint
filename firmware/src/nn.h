/* int8 inference of the posture/fall classifier.
 *
 * Arithmetic identical to the TFLite reference kernels (and therefore to
 * TFLite Micro and CMSIS-NN/MVP, which are bit-exact with them): per-channel
 * convolution with fixed-point multiplier, max/avg pool and a dense layer.
 * tests/test_nn.c requires int8 logits identical to TFLite's.
 * On the EFR32MG26 it can be swapped for TFLite Micro with MVP kernels without
 * changing the rf_nn_* interface. */
#pragma once
#include <stdint.h>

#include "features_v1.h"

typedef enum { NN_CONV = 0, NN_MAXPOOL, NN_AVGPOOL, NN_FC } nn_op_t;

typedef struct {
    nn_op_t op;
    int in_len, in_ch, out_len, out_ch, k;
    int32_t in_zp, out_zp, act_min, act_max;
    const int8_t *w;         /* conv: [cout][k][cin]; fc: [cout][cin] */
    const int32_t *b;
    const int32_t *mult;
    const int8_t *shift;
} nn_layer_t;

int32_t nn_multiply_by_quantized_multiplier(int32_t x, int32_t mult, int shift);

/* Window in physical units [NN_WINDOW][RF_N_FIELDS] -> int8 logits and probabilities.
 * Returns how many last-frame features fall outside the training range
 * (input to the fail-safe decision). */
int rf_nn_infer(const float window[][RF_N_FIELDS], int8_t *logits, float *probs);
/* Fingerprint of the embedded model (CRC32 of the exported .tflite): ModelHash attribute. */
uint32_t rf_nn_model_hash(void);
