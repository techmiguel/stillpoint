#include "decision.h"

const rf_decision_params_t RF_DECISION_DEFAULTS = {
    .p_min = 0.60f, .p_fall = 0.50f, .vz_fall = -0.80f, .z_floor = 0.55f, .z_up = 1.00f,
    .confirm_s = 4.0f, .still_s = 2.0f, .resolve_max_s = 15.0f, .clear_s = 5.0f, .q_min = 0.30f,
    .ood_max = 3,
};

static uint32_t ms(float s) { return (uint32_t)(s * 1000.0f + 0.5f); }

void rf_decision_init(rf_decision_t *d, const rf_decision_params_t *p)
{
    d->p = *p;
    d->fall = RF_FALL_NONE;
    d->t_susp_ms = 0;
    d->t_up_ms = 0;
    d->has_t_up = false;
}

void rf_decision_update(rf_decision_t *d, const rf_decision_in_t *x,
                        rf_posture_t *posture, float *confidence, rf_fall_t *fall)
{
    const rf_decision_params_t *p = &d->p;
    /* Postura: exige evidencia reciente. Caída: basta con pista no tapada. */
    const bool trusted_fall = !x->occluded && x->ood_count <= p->ood_max;
    const bool trusted = trusted_fall && x->quality >= p->q_min;

    int k = 0;
    for (int i = 1; i < 3; i++) {
        if (x->probs[i] > x->probs[k]) {
            k = i;
        }
    }
    float s = x->probs[0] + x->probs[1] + x->probs[2];
    float conf = x->probs[k] / (s > 1e-6f ? s : 1e-6f);
    *confidence = conf;
    *posture = (trusted && conf >= p->p_min) ? (rf_posture_t)(k + 1) : RF_POSTURE_UNCERTAIN;

    const bool trigger = x->probs[3] >= p->p_fall || (x->vz_min <= p->vz_fall && x->z_c < p->z_floor);
    switch (d->fall) {
    case RF_FALL_NONE:
        if (trigger && trusted_fall) {
            d->fall = RF_FALL_SUSPECTED;
            d->t_susp_ms = x->t_ms;
        }
        break;
    case RF_FALL_SUSPECTED:
        if (!trusted_fall) {
            d->fall = RF_FALL_UNCERTAIN;
        } else if (x->z_c > p->z_up) {
            d->fall = RF_FALL_NONE;
        } else if (x->t_ms - d->t_susp_ms >= ms(p->confirm_s) && x->z_c < p->z_floor && x->still_s >= p->still_s) {
            d->fall = RF_FALL_CONFIRMED;
            d->has_t_up = false;
        } else if (x->t_ms - d->t_susp_ms >= ms(p->resolve_max_s)) {
            d->fall = RF_FALL_UNCERTAIN;
        }
        break;
    case RF_FALL_CONFIRMED:
    case RF_FALL_UNCERTAIN:
        if (trusted_fall && x->z_c > p->z_up) {
            if (!d->has_t_up) {
                d->t_up_ms = x->t_ms;
                d->has_t_up = true;
            }
            if (x->t_ms - d->t_up_ms >= ms(p->clear_s)) {
                d->fall = RF_FALL_NONE;
                d->has_t_up = false;
            }
        } else {
            d->has_t_up = false;
            if (d->fall == RF_FALL_UNCERTAIN && trusted_fall && x->z_c < p->z_floor &&
                x->still_s >= p->still_s) {
                d->fall = RF_FALL_CONFIRMED;
            }
        }
        break;
    }
    *fall = d->fall;
}
