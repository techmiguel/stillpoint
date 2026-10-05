/* Límites de emisión en Europa (57-64 GHz, 100 mW PIRE) aplicados en firmware.
 * Ninguna configuración del radar llega al BGT60TR13C sin pasar por aquí.
 * Ver docs/05_regulatorio_60ghz.md. Espejo: ml/radarref/config.py::check_eu. */
#pragma once
#include <stdint.h>

typedef struct {
    double f_start_hz;
    double bandwidth_hz;
    uint16_t n_samples;
    double fs_hz;
    uint16_t n_chirps;
    double t_chirp_s;
    double frame_rate_hz;
    float eirp_dbm;          /* estimada a partir de la potencia TX configurada y la ganancia AiP */
} rf_radar_cfg_t;

typedef enum {
    RF_CFG_OK = 0,
    RF_CFG_BAND = -1,        /* barrido fuera de 57-64 GHz */
    RF_CFG_EIRP = -2,        /* PIRE > 20 dBm */
    RF_CFG_TIMING = -3,      /* los chirps no caben en la trama */
} rf_cfg_status_t;

#define RF_EU_F_MIN_HZ 57.0e9
#define RF_EU_F_MAX_HZ 64.0e9
#define RF_EU_EIRP_MAX_DBM 20.0f

static inline rf_cfg_status_t rf_radar_check_eu(const rf_radar_cfg_t *c)
{
    if (c->f_start_hz < RF_EU_F_MIN_HZ || c->f_start_hz + c->bandwidth_hz > RF_EU_F_MAX_HZ) {
        return RF_CFG_BAND;
    }
    if (c->eirp_dbm > RF_EU_EIRP_MAX_DBM) {
        return RF_CFG_EIRP;
    }
    if ((double)c->n_chirps * c->t_chirp_s * c->frame_rate_hz >= 1.0) {
        return RF_CFG_TIMING;
    }
    return RF_CFG_OK;
}

/* Configuración v1 (igual que RadarConfig por defecto). */
static const rf_radar_cfg_t RF_RADAR_CFG_V1 = {
    .f_start_hz = 60.0e9, .bandwidth_hz = 1.25e9, .n_samples = 128, .fs_hz = 2.0e6,
    .n_chirps = 32, .t_chirp_s = 350e-6, .frame_rate_hz = 10.0, .eirp_dbm = 10.0f,
};
