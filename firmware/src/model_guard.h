/* Un modelo entrenado con otro contrato de características no compila.
 * model_data.h lo genera ml/train.py junto con el .tflite. */
#pragma once
#include "features_v1.h"
#include "model_data.h"

_Static_assert(MODEL_CONTRACT_HASH32 == RF_CONTRACT_HASH32,
               "model_data.h se entrenó con otro contrato de características: reentrenar o regenerar");
