/* The configuration exported from Radar Fusion GUI must match the one used by
 * the reference, the training and the EU limits (RF_RADAR_CFG_V1).
 * Re-exporting with other parameters breaks the build.
 * Macro names follow the Infineon examples; check them when exporting. */
#pragma once
#include "dsp.h"
#include "radar_settings.h"

_Static_assert(XENSIV_BGT60TRXX_CONF_NUM_SAMPLES_PER_CHIRP == RF_N_SAMPLES, "samples per chirp");
_Static_assert(XENSIV_BGT60TRXX_CONF_NUM_CHIRPS_PER_FRAME == RF_N_CHIRPS, "chirps per frame");
_Static_assert(XENSIV_BGT60TRXX_CONF_NUM_RX_ANTENNAS == RF_N_RX, "RX antennas");
_Static_assert(XENSIV_BGT60TRXX_CONF_START_FREQ_HZ >= 57000000000ULL, "start below 57 GHz");
_Static_assert(XENSIV_BGT60TRXX_CONF_END_FREQ_HZ <= 64000000000ULL, "stop above 64 GHz");
