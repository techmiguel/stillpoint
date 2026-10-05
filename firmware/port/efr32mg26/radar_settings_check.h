/* La configuración exportada de Radar Fusion GUI debe coincidir con la que
 * usan la referencia, el entrenamiento y los límites EU (RF_RADAR_CFG_V1).
 * Si alguien reexporta con otros parámetros, el firmware no compila.
 * Nombres de macros según los ejemplos de Infineon; comprobarlos al exportar. */
#pragma once
#include "dsp.h"
#include "radar_settings.h"

_Static_assert(XENSIV_BGT60TRXX_CONF_NUM_SAMPLES_PER_CHIRP == RF_N_SAMPLES, "muestras por chirp");
_Static_assert(XENSIV_BGT60TRXX_CONF_NUM_CHIRPS_PER_FRAME == RF_N_CHIRPS, "chirps por trama");
_Static_assert(XENSIV_BGT60TRXX_CONF_NUM_RX_ANTENNAS == RF_N_RX, "antenas RX");
_Static_assert(XENSIV_BGT60TRXX_CONF_START_FREQ_HZ >= 57000000000ULL, "inicio por debajo de 57 GHz");
_Static_assert(XENSIV_BGT60TRXX_CONF_END_FREQ_HZ <= 64000000000ULL, "fin por encima de 64 GHz");
