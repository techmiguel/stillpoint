/* Inferencia int8 del clasificador de postura/caída.
 *
 * Aritmética idéntica a los núcleos de referencia de TFLite (y, por tanto, a
 * TFLite Micro y a CMSIS-NN/MVP, que son exactos respecto a ellos): convolución
 * por canal con multiplicador en punto fijo, max/avg pool y capa densa.
 * tests/test_nn.c exige logits int8 idénticos a los de TFLite.
 * En el EFR32MG26 puede sustituirse por TFLite Micro con núcleos MVP sin cambiar
 * la interfaz rf_nn_*. */
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

/* Ventana en unidades físicas [NN_WINDOW][RF_N_FIELDS] -> logits int8 y probabilidades.
 * Devuelve el nº de características de la última trama fuera del rango de
 * entrenamiento (para la decisión con fallo seguro). */
int rf_nn_infer(const float window[][RF_N_FIELDS], int8_t *logits, float *probs);
