#include "tracker.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#define DT 0.1
#define GATE 0.8
#define MICRO_WINDOW_S 10.0
#define INTERFERER_S 20.0
#define HOLD_TENTATIVE 0.5
#define HOLD_EXIT 2.0
#define HOLD_OCCLUDED 60.0
#define HOLD_BREATH 120.0
#define HOLD_DEFAULT 30.0

static double db(double x) { return x > 0 ? 10.0 * log10(x) : 0.0; }

void rf_tracker_init(rf_tracker_t *tk, const rf_room_t *room)
{
    memset(tk, 0, sizeof(*tk));
    tk->room = *room;
    tk->next_id = 1;
}

/* ---- historial de aciertos -------------------------------------------------- */
static void hit_push(rf_track_t *tr, uint8_t v)
{
    tr->hits[(tr->hits_head + tr->n_hits) % RF_HITS] = v;
    if (tr->n_hits < RF_HITS) {
        tr->n_hits++;
    } else {
        tr->hits_head = (tr->hits_head + 1) % RF_HITS;
    }
}

static int hit_sum(const rf_track_t *tr, int last)
{
    int s = 0, n = last < tr->n_hits ? last : tr->n_hits;
    for (int i = tr->n_hits - n; i < tr->n_hits; i++) {
        s += tr->hits[(tr->hits_head + i) % RF_HITS];
    }
    return s;
}

static void vr_push(rf_track_t *tr, double v)
{
    if (tr->n_vr < RF_VR_HIST) {
        tr->vr_hist[tr->n_vr++] = v;
    } else {
        memmove(tr->vr_hist, tr->vr_hist + 1, sizeof(double) * (RF_VR_HIST - 1));
        tr->vr_hist[RF_VR_HIST - 1] = v;
    }
}

/* ---- Kalman de velocidad constante en (x, y) --------------------------------- */
static void kf_predict(rf_track_t *tr)
{
    double F[4][4] = {{1, 0, DT, 0}, {0, 1, 0, DT}, {0, 0, 1, 0}, {0, 0, 0, 1}};
    const double g2 = DT * DT / 2, q2 = 0.5 * 0.5;
    const double G[4][2] = {{g2, 0}, {0, g2}, {DT, 0}, {0, DT}};
    double x[4] = {0}, FP[4][4] = {{0}}, P[4][4] = {{0}};
    for (int i = 0; i < 4; i++) {
        for (int j = 0; j < 4; j++) {
            x[i] += F[i][j] * tr->kx[j];
        }
    }
    for (int i = 0; i < 4; i++) {
        for (int j = 0; j < 4; j++) {
            for (int k = 0; k < 4; k++) {
                FP[i][j] += F[i][k] * tr->kP[k][j];
            }
        }
    }
    for (int i = 0; i < 4; i++) {
        for (int j = 0; j < 4; j++) {
            for (int k = 0; k < 4; k++) {
                P[i][j] += FP[i][k] * F[j][k];
            }
            P[i][j] += (G[i][0] * G[j][0] + G[i][1] * G[j][1]) * q2;
        }
    }
    memcpy(tr->kx, x, sizeof(x));
    memcpy(tr->kP, P, sizeof(P));
}

static void kf_update(rf_track_t *tr, double zx, double zy, double r)
{
    double S[2][2] = {{tr->kP[0][0] + r * r, tr->kP[0][1]}, {tr->kP[1][0], tr->kP[1][1] + r * r}};
    const double det = S[0][0] * S[1][1] - S[0][1] * S[1][0];
    const double Si[2][2] = {{S[1][1] / det, -S[0][1] / det}, {-S[1][0] / det, S[0][0] / det}};
    double K[4][2];
    for (int i = 0; i < 4; i++) {
        for (int j = 0; j < 2; j++) {
            K[i][j] = tr->kP[i][0] * Si[0][j] + tr->kP[i][1] * Si[1][j];
        }
    }
    const double y0 = zx - tr->kx[0], y1 = zy - tr->kx[1];
    for (int i = 0; i < 4; i++) {
        tr->kx[i] += K[i][0] * y0 + K[i][1] * y1;
    }
    double P[4][4];
    for (int i = 0; i < 4; i++) {
        for (int j = 0; j < 4; j++) {
            P[i][j] = tr->kP[i][j] - (K[i][0] * tr->kP[0][j] + K[i][1] * tr->kP[1][j]);
        }
    }
    memcpy(tr->kP, P, sizeof(P));
}

/* ---- agrupamiento ------------------------------------------------------------- */
static void make_clusters(rf_tracker_t *tk, const rf_det_t *dets, int n)
{
    int order[RF_MAX_DETS + 16], m = 0;
    for (int i = 0; i < n; i++) {
        if (dets[i].kind != RF_DET_MOVE) {
            continue;
        }
        int j = m++;
        while (j > 0 && dets[order[j - 1]].power_db < dets[i].power_db) { /* estable, descendente */
            order[j] = order[j - 1];
            j--;
        }
        order[j] = i;
    }
    int seed[RF_MAX_DETS];
    tk->n_clusters = 0;
    for (int a = 0; a < m && a < RF_MAX_DETS; a++) {
        const rf_det_t *d = &dets[order[a]];
        int g = 0;
        for (; g < tk->n_clusters; g++) {
            const rf_det_t *s = &dets[seed[g]];
            if (hypot(d->x - s->x, d->y - s->y) < 0.6) {
                break;
            }
        }
        if (g == tk->n_clusters) {
            seed[g] = order[a];
            tk->clusters[g].n = 0;
            tk->n_clusters++;
        }
        rf_cluster_t *c = &tk->clusters[g];
        c->z[c->n] = d->z;
        c->vr[c->n] = d->vr;
        c->p_lin[c->n] = (float)pow(10.0, d->power_db / 10.0);
        c->px[c->n] = d->x;
        c->py[c->n] = d->y;
        c->n++;
    }
    for (int g = 0; g < tk->n_clusters; g++) {
        rf_cluster_t *c = &tk->clusters[g];
        double ps = 0, x = 0, y = 0, zc = 0, vm = 0, vs = 0;
        for (int i = 0; i < c->n; i++) {
            ps += c->p_lin[i];
        }
        for (int i = 0; i < c->n; i++) {
            c->w[i] = (float)(c->p_lin[i] / ps);
            x += c->w[i] * c->px[i];
            y += c->w[i] * c->py[i];
        }
        double ws = 0;
        for (int i = 0; i < c->n; i++) {
            ws += c->w[i];
        }
        for (int i = 0; i < c->n; i++) {
            zc += c->w[i] * c->z[i];
            vm += c->w[i] * c->vr[i];
        }
        zc /= ws;
        vm /= ws;
        for (int i = 0; i < c->n; i++) {
            vs += c->w[i] * (c->vr[i] - vm) * (c->vr[i] - vm);
        }
        c->x = (float)x;
        c->y = (float)y;
        c->z_c = (float)zc;
        c->vr_mean = (float)vm;
        c->vr_std = (float)sqrt(vs / ws);
    }
}

/* ---- pistas ----------------------------------------------------------------------- */
static rf_track_t *new_track(rf_tracker_t *tk, double t, double x, double y)
{
    if (tk->n_tracks >= RF_MAX_TRACKS) {
        return NULL;
    }
    rf_track_t *tr = &tk->tracks[tk->n_tracks++];
    memset(tr, 0, sizeof(*tr));
    tr->id = tk->next_id;
    tk->next_id = (uint8_t)(tk->next_id % 250 + 1);
    tr->kx[0] = x;
    tr->kx[1] = y;
    tr->kP[0][0] = tr->kP[1][1] = 0.1;
    tr->kP[2][2] = tr->kP[3][3] = 1.0;
    tr->state = RF_TR_TENTATIVE;
    tr->last_seen = tr->last_move = t;
    tr->last_micro = -1e9;
    tr->z_c = tr->z_max = tr->z_min = 1.0;
    tr->anchor_x = x;
    tr->anchor_y = y;
    tr->anchor_t = t;
    tr->cluster_idx = -1;
    return tr;
}

static double track_range(const rf_tracker_t *tk, const rf_track_t *tr)
{
    const double dz = tr->z_c - tk->room.mount_h;
    return sqrt(tr->kx[0] * tr->kx[0] + tr->kx[1] * tr->kx[1] + dz * dz);
}

static bool is_multipath(const rf_tracker_t *tk, const rf_track_t *tr)
{
    if (tr->n_vr < 8) {
        return false;
    }
    for (int k = 0; k < tk->n_tracks; k++) {
        const rf_track_t *o = &tk->tracks[k];
        if (o == tr || !o->confirmed || o->n_vr < 8) {
            continue;
        }
        const int n = tr->n_vr < o->n_vr ? tr->n_vr : o->n_vr;
        const double *a = tr->vr_hist + tr->n_vr - n, *b = o->vr_hist + o->n_vr - n;
        double ma = 0, mb = 0, sa = 0, sb = 0, sab = 0;
        for (int i = 0; i < n; i++) {
            ma += a[i];
            mb += b[i];
        }
        ma /= n;
        mb /= n;
        for (int i = 0; i < n; i++) {
            sa += (a[i] - ma) * (a[i] - ma);
            sb += (b[i] - mb) * (b[i] - mb);
            sab += (a[i] - ma) * (b[i] - mb);
        }
        const double stda = sqrt(sa / n), stdb = sqrt(sb / n);
        if (stda > 0.05 && stdb > 0.05 && sab / sqrt(sa * sb) > 0.9 &&
            track_range(tk, tr) > track_range(tk, o) + 0.3) {
            return true;
        }
    }
    return false;
}

static bool is_occluded(const rf_tracker_t *tk, const rf_track_t *tr)
{
    const double h = tk->room.mount_h;
    double u[3] = {tr->kx[0], tr->kx[1], tr->z_c - h};
    const double ru = sqrt(u[0] * u[0] + u[1] * u[1] + u[2] * u[2]);
    for (int k = 0; k < tk->n_tracks; k++) {
        const rf_track_t *o = &tk->tracks[k];
        if (o == tr || !o->confirmed || o->state == RF_TR_INTERFERER) {
            continue;
        }
        double v[3] = {o->kx[0], o->kx[1], o->z_max - h};
        const double rv = sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
        double a[3] = {u[0] / ru, u[1] / ru, u[2] / ru}, b[3] = {v[0] / rv, v[1] / rv, v[2] / rv};
        const double cx = a[1] * b[2] - a[2] * b[1], cy = a[2] * b[0] - a[0] * b[2], cz = a[0] * b[1] - a[1] * b[0];
        if (rv < ru - 0.3 && sqrt(cx * cx + cy * cy + cz * cz) < 0.35) {
            return true;
        }
    }
    return false;
}

static void update_move(rf_tracker_t *tk, rf_track_t *tr, int ci, double t)
{
    const rf_cluster_t *c = &tk->clusters[ci];
    kf_update(tr, c->x, c->y, 0.15);
    tr->cluster_idx = ci;
    tr->last_seen = t;
    hit_push(tr, 1);
    const double zc = c->z_c, resid = zc - tr->z_c;
    tr->z_c += 0.5 * resid;
    tr->vz = 0.8 * tr->vz + 0.2 * resid / DT;
    double zmax = c->z[0], zmin = c->z[0], ws = 0, zs = 0;
    for (int i = 0; i < c->n; i++) {
        zmax = c->z[i] > zmax ? c->z[i] : zmax;
        zmin = c->z[i] < zmin ? c->z[i] : zmin;
        ws += c->w[i];
        zs += c->w[i] * (c->z[i] - zc) * (c->z[i] - zc);
    }
    tr->z_max = 0.6 * tr->z_max + 0.4 * zmax;
    tr->z_min = 0.6 * tr->z_min + 0.4 * zmin;
    tr->z_std = 0.6 * tr->z_std + 0.4 * sqrt(zs / ws);
    if (c->n > 1) { /* np.cov(xy.T, aweights=w + 1e-9), autovalor mayor */
        double v1 = 0, v2 = 0, mx = 0, my = 0, sxx = 0, syy = 0, sxy = 0;
        for (int i = 0; i < c->n; i++) {
            const double w = (double)c->w[i] + 1e-9;
            v1 += w;
            v2 += w * w;
            mx += w * c->px[i];
            my += w * c->py[i];
        }
        mx /= v1;
        my /= v1;
        for (int i = 0; i < c->n; i++) {
            const double w = (double)c->w[i] + 1e-9, dx = c->px[i] - mx, dy = c->py[i] - my;
            sxx += w * dx * dx;
            syy += w * dy * dy;
            sxy += w * dx * dy;
        }
        const double fact = v1 - v2 / v1;
        sxx /= fact;
        syy /= fact;
        sxy /= fact;
        double ev = 0.5 * (sxx + syy) + sqrt(0.25 * (sxx - syy) * (sxx - syy) + sxy * sxy);
        tr->xy_extent = 0.7 * tr->xy_extent + 0.3 * sqrt(ev > 0 ? ev : 0);
    }
    vr_push(tr, c->vr_mean);
    tr->spread_ema = 0.95 * tr->spread_ema + 0.05 * c->vr_std;
    const double speed = hypot(tr->kx[2], tr->kx[3]);
    if (speed > 0.3 || fabs(c->vr_mean) > 0.3 || c->vr_std > 0.3) {
        tr->last_move = t;
    }
    if (!tr->confirmed && hit_sum(tr, 5) >= 3) {
        if (is_multipath(tk, tr)) {
            tr->last_seen = -1e9;
        } else {
            tr->confirmed = true;
        }
    }
}

static void update_micro(rf_tracker_t *tk, double t, const rf_det_t *m)
{
    rf_track_t *best = NULL;
    double bd = 0.7;
    for (int k = 0; k < tk->n_tracks; k++) {
        rf_track_t *tr = &tk->tracks[k];
        const double d = hypot(m->x - tr->kx[0], m->y - tr->kx[1]);
        if (d < bd && tr->state != RF_TR_INTERFERER) {
            best = tr;
            bd = d;
        }
    }
    const bool breath_ok = m->breath_hz >= 0.12f && m->breath_hz <= 0.6f && m->breath_snr_db > 15.0f;
    if (best) {
        kf_update(best, m->x, m->y, 0.35);
        best->last_seen = t;
        best->last_micro = t;
        best->micro_db = m->micro_db;
        best->breath_hz = m->breath_hz;
        best->breath_snr = m->breath_snr_db;
        best->has_breath = best->has_breath || (breath_ok && best->confirmed);
        if (best->cluster_idx < 0) {
            best->z_c += 0.3 * (m->z - best->z_c);
            best->z_max += 0.3 * (m->z + 0.15 - best->z_max);
            best->z_min += 0.3 * (m->z - 0.15 - best->z_min);
        }
        return;
    }
    if (!breath_ok) {
        return;
    }
    for (int i = 0; i < tk->n_cand; i++) {
        double *c = tk->cand[i];
        if (hypot(m->x - c[0], m->y - c[1]) < 0.5 && t - c[3] < 1.5) {
            c[0] = 0.5 * (c[0] + m->x);
            c[1] = 0.5 * (c[1] + m->y);
            c[2] += 1;
            c[3] = t;
            if (c[2] >= 3) {
                rf_track_t *tr = new_track(tk, t, c[0], c[1]);
                if (tr) {
                    tr->confirmed = tr->has_breath = true;
                    tr->state = RF_TR_STATIC;
                    tr->z_c = m->z;
                    tr->z_max = m->z + 0.15;
                    tr->z_min = m->z - 0.15;
                    tr->last_micro = t;
                }
                memmove(&tk->cand[i], &tk->cand[i + 1], sizeof(tk->cand[0]) * (size_t)(tk->n_cand - i - 1));
                tk->n_cand--;
            }
            return;
        }
    }
    if (tk->n_cand < RF_MAX_MICRO_CAND) {
        double *c = tk->cand[tk->n_cand++];
        c[0] = m->x;
        c[1] = m->y;
        c[2] = 1;
        c[3] = t;
    }
}

static void update_states(rf_tracker_t *tk, double t)
{
    int nc = 0;
    for (int i = 0; i < tk->n_cand; i++) {
        if (t - tk->cand[i][3] < 1.5) {
            memmove(tk->cand[nc++], tk->cand[i], sizeof(tk->cand[0]));
        }
    }
    tk->n_cand = nc;
    int keep = 0;
    for (int k = 0; k < tk->n_tracks; k++) {
        rf_track_t *tr = &tk->tracks[k];
        if (tr->cluster_idx < 0) {
            hit_push(tr, t - tr->last_micro < 1.0 ? 1 : 0);
            tr->kx[2] *= 0.7;
            tr->kx[3] *= 0.7;
            tr->vz *= 0.7;
        }
        if (!rf_room_inside(&tk->room, (float)tr->kx[0], (float)tr->kx[1], 0.3f)) {
            continue;
        }
        tr->occluded = false;
        if (tr->state == RF_TR_INTERFERER) {
            /* nada */
        } else if (tr->cluster_idx >= 0 && t - tr->last_move < 1.0) {
            tr->state = tr->confirmed ? RF_TR_MOVING : RF_TR_TENTATIVE;
        } else if (t - tr->last_micro < 3.0) {
            tr->state = RF_TR_STATIC;
        } else if (tr->confirmed && is_occluded(tk, tr)) {
            tr->state = RF_TR_OCCLUDED;
            tr->occluded = true;
        } else if (tr->confirmed && tr->has_breath) {
            tr->state = RF_TR_STATIC;
        }
        if (hypot(tr->kx[0] - tr->anchor_x, tr->kx[1] - tr->anchor_y) > 0.4) {
            tr->anchor_x = tr->kx[0];
            tr->anchor_y = tr->kx[1];
            tr->anchor_t = t;
        } else if (tr->confirmed && !tr->has_breath && t - tr->anchor_t > INTERFERER_S && tr->spread_ema > 0.5 &&
                   hit_sum(tr, RF_HITS) >= 16 && tr->state != RF_TR_INTERFERER) {
            tr->state = RF_TR_INTERFERER;
            if (tk->n_proposed < RF_MAX_ZONES) {
                rf_box_t b = {(float)(tr->kx[0] - .4), (float)(tr->kx[0] + .4), (float)(tr->kx[1] - .4),
                              (float)(tr->kx[1] + .4)};
                tk->proposed_exclusions[tk->n_proposed++] = b;
            }
        }
        const double miss = t - tr->last_seen;
        double hold;
        if (!tr->confirmed) {
            hold = HOLD_TENTATIVE;
        } else if (rf_room_near_exit(&tk->room, (float)tr->kx[0], (float)tr->kx[1])) {
            hold = HOLD_EXIT;
        } else if (tr->state == RF_TR_OCCLUDED) {
            hold = HOLD_OCCLUDED;
        } else if (tr->has_breath) {
            hold = HOLD_BREATH;
        } else {
            hold = HOLD_DEFAULT;
        }
        if (miss <= hold) {
            if (keep != k) {
                tk->tracks[keep] = *tr;
            }
            keep++;
        }
    }
    tk->n_tracks = keep;
}

typedef struct {
    double cost;
    int i, j;
} pair_t;

static int cmp_pair(const void *a, const void *b)
{
    const pair_t *p = a, *q = b;
    if (p->cost != q->cost) {
        return p->cost < q->cost ? -1 : 1;
    }
    if (p->i != q->i) {
        return p->i - q->i;
    }
    return p->j - q->j;
}

void rf_tracker_step(rf_tracker_t *tk, double t, const rf_det_t *dets, int n_dets)
{
    make_clusters(tk, dets, n_dets);
    for (int k = 0; k < tk->n_tracks; k++) {
        kf_predict(&tk->tracks[k]);
        tk->tracks[k].cluster_idx = -1;
    }
    static pair_t pairs[RF_MAX_DETS * RF_MAX_TRACKS];
    int np = 0;
    const int nt0 = tk->n_tracks;
    for (int i = 0; i < tk->n_clusters; i++) {
        for (int j = 0; j < nt0; j++) {
            const rf_track_t *tr = &tk->tracks[j];
            double c = hypot(tk->clusters[i].x - tr->kx[0], tk->clusters[i].y - tr->kx[1]);
            if ((tr->state == RF_TR_STATIC || tr->state == RF_TR_OCCLUDED) && fabs(tk->clusters[i].vr_mean) > 0.3) {
                c += 0.5;
            }
            pairs[np].cost = c;
            pairs[np].i = i;
            pairs[np].j = j;
            np++;
        }
    }
    qsort(pairs, (size_t)np, sizeof(pair_t), cmp_pair);
    bool used_c[RF_MAX_DETS] = {false}, used_t[RF_MAX_TRACKS] = {false};
    for (int p = 0; p < np; p++) {
        if (pairs[p].cost > GATE || used_c[pairs[p].i] || used_t[pairs[p].j]) {
            continue;
        }
        used_c[pairs[p].i] = used_t[pairs[p].j] = true;
        update_move(tk, &tk->tracks[pairs[p].j], pairs[p].i, t);
    }
    for (int i = 0; i < tk->n_clusters; i++) {
        if (!used_c[i]) {
            rf_track_t *tr = new_track(tk, t, tk->clusters[i].x, tk->clusters[i].y);
            if (tr) {
                update_move(tk, tr, i, t);
            }
        }
    }
    /* estela de movimiento reciente: ahí una detección micro no es respiración */
    for (int i = 0; i < tk->n_clusters; i++) {
        const int s = (tk->motion_head + tk->motion_len) % RF_MOTION_HIST;
        tk->motion_t[s] = t;
        tk->motion_x[s] = tk->clusters[i].x;
        tk->motion_y[s] = tk->clusters[i].y;
        if (tk->motion_len < RF_MOTION_HIST) {
            tk->motion_len++;
        } else {
            tk->motion_head = (tk->motion_head + 1) % RF_MOTION_HIST;
        }
    }
    while (tk->motion_len && t - tk->motion_t[tk->motion_head] > MICRO_WINDOW_S) {
        tk->motion_head = (tk->motion_head + 1) % RF_MOTION_HIST;
        tk->motion_len--;
    }
    for (int i = 0; i < n_dets; i++) {
        if (dets[i].kind != RF_DET_MICRO) {
            continue;
        }
        bool trail = false;
        for (int h = 0; h < tk->motion_len && !trail; h++) {
            const int s = (tk->motion_head + h) % RF_MOTION_HIST;
            trail = hypot(dets[i].x - tk->motion_x[s], dets[i].y - tk->motion_y[s]) < 0.6;
        }
        if (!trail) {
            update_micro(tk, t, &dets[i]);
        }
    }
    update_states(tk, t);
}

int rf_tracker_count(const rf_tracker_t *tk)
{
    int n = 0;
    for (int k = 0; k < tk->n_tracks; k++) {
        n += tk->tracks[k].confirmed && tk->tracks[k].state != RF_TR_INTERFERER;
    }
    return n;
}

void rf_tracker_features(const rf_tracker_t *tk, const rf_track_t *tr, double t, float f[RF_N_FIELDS])
{
    for (int i = 0; i < (int)RF_N_FIELDS; i++) {
        f[i] = 0.0f;
    }
    f[RF_F_X] = (float)tr->kx[0];
    f[RF_F_Y] = (float)tr->kx[1];
    f[RF_F_Z_CENTROID] = (float)tr->z_c;
    f[RF_F_Z_MAX] = (float)tr->z_max;
    f[RF_F_Z_MIN] = (float)tr->z_min;
    f[RF_F_Z_STD] = (float)tr->z_std;
    f[RF_F_XY_EXTENT] = (float)tr->xy_extent;
    f[RF_F_VX] = (float)tr->kx[2];
    f[RF_F_VY] = (float)tr->kx[3];
    f[RF_F_VZ] = (float)tr->vz;
    if (tr->cluster_idx >= 0) {
        const rf_cluster_t *c = &tk->clusters[tr->cluster_idx];
        double ea = 0, er = 0, pt = 0;
        for (int i = 0; i < c->n; i++) {
            pt += c->p_lin[i];
            if (c->vr[i] < 0) {
                ea += c->p_lin[i];
            } else if (c->vr[i] > 0) {
                er += c->p_lin[i];
            }
        }
        f[RF_F_VR_MEAN] = c->vr_mean;
        f[RF_F_VR_STD] = c->vr_std;
        f[RF_F_E_APPROACH_DB] = (float)db(ea);
        f[RF_F_E_RECEDE_DB] = (float)db(er);
        f[RF_F_N_POINTS] = (float)c->n;
        f[RF_F_POWER_DB] = (float)db(pt);
    }
    const bool recent = t - tr->last_micro < 3.0;
    f[RF_F_MICRO_DB] = recent ? (float)tr->micro_db : 0.0f;
    f[RF_F_BREATH_HZ] = recent ? (float)tr->breath_hz : 0.0f;
    f[RF_F_BREATH_SNR_DB] = recent ? (float)tr->breath_snr : 0.0f;
    f[RF_F_RANGE] = (float)track_range(tk, tr);
    f[RF_F_STATE] = (float)tr->state;
    const double still = t - tr->last_move;
    f[RF_F_STILL_S] = (float)(still < 3276.0 ? still : 3276.0);
    f[RF_F_OCCLUDED] = tr->occluded ? 1.0f : 0.0f;
    f[RF_F_QUALITY] = tr->n_hits ? (float)hit_sum(tr, RF_HITS) / (float)tr->n_hits : 0.0f;
}
