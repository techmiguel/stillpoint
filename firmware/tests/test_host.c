/* Pruebas en PC del código portable del firmware frente a la referencia Python.
 * Compilar: make -C firmware test   (gcc o clang del PC) */
#include <stdio.h>
#include <string.h>

#include "../src/decision.h"
#include "../src/features_pack.h"
#include "../src/radar_limits.h"
#include "decision_vectors.h"
#include "golden_v1.h"

static int fails = 0;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("FALLO %s:%d: ", __FILE__, __LINE__); \
    printf(__VA_ARGS__); printf("\n"); } } while (0)

static void test_golden(void)
{
    for (int i = 0; i < GOLDEN_N; i++) {
        uint8_t rec[RF_RECORD_SIZE];
        rf_pack(golden[i].frame_id, golden[i].t_ms, golden[i].track, golden[i].flags, golden[i].v, rec);
        CHECK(memcmp(rec, golden[i].rec, RF_RECORD_SIZE) == 0, "registro dorado %d distinto de Python", i);
        int16_t q[RF_N_FIELDS];
        uint32_t fid, t;
        uint8_t tr, fl;
        CHECK(rf_unpack(rec, q, &fid, &t, &tr, &fl) == 0 && fid == golden[i].frame_id, "unpack %d", i);
        rec[20] ^= 0x01;
        CHECK(rf_unpack(rec, q, &fid, &t, &tr, &fl) == -1, "CRC no detecta corrupción en %d", i);
    }
}

static void test_decision(void)
{
    rf_decision_t d;
    for (int i = 0; i < DVEC_N; i++) {
        const dvec_t *v = &dvec[i];
        if (v->reset) {
            rf_decision_init(&d, &RF_DECISION_DEFAULTS);
        }
        rf_decision_in_t x = {v->t, {v->p[0], v->p[1], v->p[2], v->p[3]}, v->z_c, v->vz_min, v->still_s,
                              v->quality, v->occluded != 0, v->ood};
        rf_posture_t post;
        rf_fall_t fall;
        float conf;
        rf_decision_update(&d, &x, &post, &conf, &fall);
        CHECK((int)post == v->exp_posture && (int)fall == v->exp_fall,
              "vector %d: postura %d/%d caída %d/%d", i, post, v->exp_posture, fall, v->exp_fall);
    }
}

static void test_limits(void)
{
    CHECK(rf_radar_check_eu(&RF_RADAR_CFG_V1) == RF_CFG_OK, "config v1 debe ser válida");
    rf_radar_cfg_t c = RF_RADAR_CFG_V1;
    c.bandwidth_hz = 4.5e9;
    CHECK(rf_radar_check_eu(&c) == RF_CFG_BAND, "64,5 GHz debe rechazarse");
    c = RF_RADAR_CFG_V1;
    c.eirp_dbm = 21.0f;
    CHECK(rf_radar_check_eu(&c) == RF_CFG_EIRP, "21 dBm debe rechazarse");
}

int main(void)
{
    test_golden();
    test_decision();
    test_limits();
    printf("%s (%d fallos; %d registros dorados, %d vectores de decisión)\n", fails ? "MAL" : "OK", fails,
           GOLDEN_N, DVEC_N);
    return fails != 0;
}
