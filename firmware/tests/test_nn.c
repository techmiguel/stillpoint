/* int8 logits of nn.c against the TFLite reference kernels. */
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
                printf("FAIL window %d class %d: %d != %d\n", i, k, lo[k], nnv[i].logits[k]);
                bad++;
            }
        }
    }
    printf("%s (%d mismatches in %d windows x %d logits)\n", bad ? "FAIL" : "OK", bad, NNV_N, NN_N_CLASSES);
    return bad != 0;
}
