#include "app.h"

#include <math.h>
#include <string.h>

#include "features_pack.h"
#include "nn.h"

int rf_app_init(rf_app_t *app, const rf_radar_cfg_t *cfg, const rf_room_t *room, const rf_box_t *zones,
                int n_zones)
{
    memset(app, 0, sizeof(*app));
    const int r = rf_dsp_init(&app->dsp, cfg, room);
    if (r != 0) {
        return r; /* fallo seguro: el radar no arranca con una configuración inválida */
    }
    rf_tracker_init(&app->tk, room);
    app->n_zones = n_zones < RF_APP_MAX_ZONES ? n_zones : RF_APP_MAX_ZONES;
    for (int i = 0; i < app->n_zones; i++) {
        app->zones[i] = zones[i];
    }
    return 0;
}

void rf_app_set_record_cb(rf_app_t *app, rf_record_cb cb, void *ctx)
{
    app->on_record = cb;
    app->cb_ctx = ctx;
}

static rf_track_slot_t *slot_for(rf_app_t *app, uint8_t id, bool create)
{
    rf_track_slot_t *free_slot = NULL;
    for (int i = 0; i < RF_MAX_TRACKS; i++) {
        if (app->slots[i].used && app->slots[i].id == id) {
            return &app->slots[i];
        }
        if (!app->slots[i].used && !free_slot) {
            free_slot = &app->slots[i];
        }
    }
    if (!create || !free_slot) {
        return NULL;
    }
    memset(free_slot, 0, sizeof(*free_slot));
    free_slot->used = true;
    free_slot->id = id;
    rf_decision_init(&free_slot->dec, &RF_DECISION_DEFAULTS);
    return free_slot;
}

static void window_push(rf_track_slot_t *s, const float f[RF_N_FIELDS])
{
    /* lo que entra al modelo es lo que viaja en el registro: cuantizar y volver */
    int16_t q[RF_N_FIELDS];
    rf_quantize(f, q);
    float *row = s->win[(s->head + s->n) % RF_WINDOW_FRAMES];
    for (unsigned j = 0; j < RF_N_FIELDS; j++) {
        row[j] = (float)((double)q[j] / (double)rf_scale[j]);
    }
    if (s->n < (int)RF_WINDOW_FRAMES) {
        s->n++;
    } else {
        s->head = (s->head + 1) % RF_WINDOW_FRAMES;
    }
}

static void evaluate(rf_track_slot_t *s, double t) /* t en s */
{
    float w[RF_WINDOW_FRAMES][RF_N_FIELDS];
    for (int i = 0; i < (int)RF_WINDOW_FRAMES; i++) {
        memcpy(w[i], s->win[(s->head + i) % RF_WINDOW_FRAMES], sizeof(w[i]));
    }
    int8_t logits[4];
    const int ood = rf_nn_infer((const float(*)[RF_N_FIELDS])w, logits, s->probs);
    const float *last = w[RF_WINDOW_FRAMES - 1];
    float vz_min = w[0][RF_F_VZ];
    for (int i = 1; i < (int)RF_WINDOW_FRAMES; i++) {
        vz_min = w[i][RF_F_VZ] < vz_min ? w[i][RF_F_VZ] : vz_min;
    }
    rf_decision_in_t in = {
        .t_ms = (uint32_t)llround(t * 1000.0),
        .probs = {s->probs[0], s->probs[1], s->probs[2], s->probs[3]},
        .z_c = last[RF_F_Z_CENTROID],
        .vz_min = vz_min,
        .still_s = last[RF_F_STILL_S],
        .quality = last[RF_F_QUALITY],
        .occluded = last[RF_F_OCCLUDED] > 0.5f,
        .ood_count = ood,
    };
    rf_decision_update(&s->dec, &in, &s->posture, &s->conf, &s->fall);
    s->has_result = true;
}

static bool in_zone(const rf_box_t *b, float x, float y)
{
    return b->x0 <= x && x <= b->x1 && b->y0 <= y && y <= b->y1;
}

void rf_app_frame(rf_app_t *app, const int16_t *adc, uint32_t t_ms, rf_outputs_t *out)
{
    const double t = (double)t_ms / 1000.0;
    static rf_det_t dets[RF_MAX_DETS + 16];
    const int n = rf_dsp_process(&app->dsp, adc, dets, RF_MAX_DETS + 16);
    rf_tracker_step(&app->tk, t, dets, n);
    app->n_frames++;

    /* ventanas de las pistas confirmadas; se liberan las de pistas desaparecidas */
    bool alive[RF_MAX_TRACKS] = {false};
    for (int k = 0; k < app->tk.n_tracks; k++) {
        const rf_track_t *tr = &app->tk.tracks[k];
        if (!tr->confirmed) {
            continue;
        }
        float f[RF_N_FIELDS];
        rf_tracker_features(&app->tk, tr, t, f);
        rf_track_slot_t *s = slot_for(app, tr->id, true);
        if (s) {
            window_push(s, f);
            alive[s - app->slots] = true;
        }
        if (app->on_record) {
            uint8_t rec[RF_RECORD_SIZE];
            rf_pack(app->n_frames, t_ms, tr->id, (uint8_t)tr->state, f, rec);
            app->on_record(rec, app->cb_ctx);
        }
    }
    for (int i = 0; i < RF_MAX_TRACKS; i++) {
        if (app->slots[i].used && !alive[i]) {
            app->slots[i].used = false;
        }
    }
    if (app->n_frames % RF_WINDOW_HOP == 0) {
        for (int i = 0; i < RF_MAX_TRACKS; i++) {
            if (app->slots[i].used && app->slots[i].n == (int)RF_WINDOW_FRAMES) {
                evaluate(&app->slots[i], t);
            }
        }
    }

    /* salidas publicables */
    memset(out, 0, sizeof(*out));
    out->count = (uint8_t)rf_tracker_count(&app->tk);
    out->occupied = out->count > 0;
    out->n_proposed_exclusions = (uint8_t)app->tk.n_proposed;
    for (int k = 0; k < app->tk.n_tracks; k++) {
        const rf_track_t *tr = &app->tk.tracks[k];
        if (!tr->confirmed || tr->state == RF_TR_INTERFERER) {
            continue;
        }
        rf_person_t *p = &out->people[out->n_people++];
        p->id = tr->id;
        p->state = tr->state;
        p->x = (float)tr->kx[0];
        p->y = (float)tr->kx[1];
        p->z = (float)tr->z_c;
        for (int z = 0; z < app->n_zones; z++) {
            out->zone_occupied[z] |= in_zone(&app->zones[z], p->x, p->y);
        }
        const rf_track_slot_t *s = slot_for(app, tr->id, false);
        if (s && s->has_result) {
            p->evaluated = true;
            p->posture = s->posture;
            p->confidence = s->conf;
            p->fall = s->fall;
        } else {
            p->posture = RF_POSTURE_UNCERTAIN; /* sin ventana completa: se declara, no se inventa */
        }
        out->uncertain |= p->posture == RF_POSTURE_UNCERTAIN || p->fall == RF_FALL_UNCERTAIN;
        out->fall_alarm |= p->fall == RF_FALL_CONFIRMED || p->fall == RF_FALL_UNCERTAIN;
        if (p->fall > out->worst_fall && p->fall != RF_FALL_SUSPECTED) {
            out->worst_fall = p->fall;
        } else if (out->worst_fall == RF_FALL_NONE && p->fall == RF_FALL_SUSPECTED) {
            out->worst_fall = RF_FALL_SUSPECTED;
        }
    }
}
