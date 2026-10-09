/* Per-track fail-safe decision. Mirror of ml/radarref/decision.py;
 * firmware/tests/decision_vectors.h forces both to agree. */
#pragma once
#include <stdbool.h>
#include <stdint.h>

typedef enum { RF_POSTURE_UNCERTAIN = 0, RF_POSTURE_STANDING, RF_POSTURE_SITTING, RF_POSTURE_LYING } rf_posture_t;
typedef enum { RF_FALL_NONE = 0, RF_FALL_SUSPECTED, RF_FALL_CONFIRMED, RF_FALL_UNCERTAIN } rf_fall_t;

typedef struct {
    float p_min, p_fall, vz_fall, z_floor, z_up, confirm_s, still_s, resolve_max_s, clear_s, q_min;
    int ood_max;
} rf_decision_params_t;

typedef struct {
    uint32_t t_ms;           /* time in whole ms: no rounding in comparisons */
    float probs[4];          /* standing, sitting, lying, fall */
    float z_c, vz_min, still_s, quality;
    bool occluded;
    int ood_count;
} rf_decision_in_t;

typedef struct {
    rf_decision_params_t p;
    rf_fall_t fall;
    uint32_t t_susp_ms;
    uint32_t t_up_ms;
    bool has_t_up;
} rf_decision_t;

extern const rf_decision_params_t RF_DECISION_DEFAULTS;

void rf_decision_init(rf_decision_t *d, const rf_decision_params_t *p);
void rf_decision_update(rf_decision_t *d, const rf_decision_in_t *x,
                        rf_posture_t *posture, float *confidence, rf_fall_t *fall);
