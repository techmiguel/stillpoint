/* Logits int8 de nn.c frente a los núcleos de referencia de TFLite. */
#include <stdio.h>

#include "../src/nn.h"
#include "../src/nn_model.h"
#include "nn_vectors.h"

int main(void)
{
    int bad = 0;
    for (int i = 0; i < NNV_N; i++) {
        int8_t lo[NN_N_CLASSES];
        float p[NN_N_CLASSES];
        rf_nn_infer(nnv[i].win, lo, p);
        for (int k = 0; k < NN_N_CLASSES; k++) {
            if (lo[k] != nnv[i].logits[k]) {
                printf("FALLO ventana %d clase %d: %d != %d\n", i, k, lo[k], nnv[i].logits[k]);
                bad++;
            }
        }
    }
    printf("%s (%d discrepancias en %d ventanas x %d logits)\n", bad ? "MAL" : "OK", bad, NNV_N, NN_N_CLASSES);
    return bad != 0;
}
