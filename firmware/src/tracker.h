/* Seguimiento multipersona con lógica de habitación.
 * Espejo de ml/radarref/tracker.py (ver allí el porqué de cada regla). */
#pragma once
#include <stdbool.h>
#include <stdint.h>

#include "dsp.h"
#include "features_v1.h"

#define RF_MAX_TRACKS 16
#define RF_HITS 20
#define RF_VR_HIST 10
#define RF_MOTION_HIST 1024
#define RF_MAX_MICRO_CAND 16

typedef enum { RF_TR_TENTATIVE = 0, RF_TR_MOVING, RF_TR_STATIC, RF_TR_OCCLUDED, RF_TR_INTERFERER } rf_track_state_t;

typedef struct {
    int n;
    float x, y;
    float z[RF_MAX_DETS], w[RF_MAX_DETS], vr[RF_MAX_DETS], p_lin[RF_MAX_DETS], px[RF_MAX_DETS], py[RF_MAX_DETS];
    float z_c, vr_mean, vr_std;
} rf_cluster_t;

typedef struct {
    uint8_t id;
    double kx[4], kP[4][4];
    rf_track_state_t state;
    bool confirmed, has_breath, occluded;
    uint8_t hits[RF_HITS];
    int n_hits, hits_head;
    double last_seen, last_move, last_micro;
    double z_c, z_max, z_min, z_std, vz, xy_extent;
    double vr_hist[RF_VR_HIST];
    int n_vr;
    double anchor_x, anchor_y, anchor_t, spread_ema;
    double breath_hz, breath_snr, micro_db;
    int cluster_idx; /* -1 si no hubo medida de movimiento en esta trama */
} rf_track_t;

typedef struct {
    rf_room_t room;
    rf_track_t tracks[RF_MAX_TRACKS];
    int n_tracks;
    uint8_t next_id;
    double motion_t[RF_MOTION_HIST], motion_x[RF_MOTION_HIST], motion_y[RF_MOTION_HIST];
    int motion_head, motion_len;
    double cand[RF_MAX_MICRO_CAND][4]; /* x, y, n, t */
    int n_cand;
    rf_box_t proposed_exclusions[RF_MAX_ZONES];
    int n_proposed;
    rf_cluster_t clusters[RF_MAX_DETS];
    int n_clusters;
} rf_tracker_t;

void rf_tracker_init(rf_tracker_t *tk, const rf_room_t *room);
void rf_tracker_step(rf_tracker_t *tk, double t, const rf_det_t *dets, int n_dets);
int rf_tracker_count(const rf_tracker_t *tk);
/* Vector de características del contrato (unidades físicas). */
void rf_tracker_features(const rf_tracker_t *tk, const rf_track_t *tr, double t, float f[RF_N_FIELDS]);
