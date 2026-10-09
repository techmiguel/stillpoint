/* A model trained against another feature contract does not compile.
 * model_data.h is written by ml/train.py together with the .tflite. */
#pragma once
#include "features_v1.h"
#include "model_data.h"

_Static_assert(MODEL_CONTRACT_HASH32 == RF_CONTRACT_HASH32,
               "model_data.h was trained against another feature contract: retrain or regenerate");
