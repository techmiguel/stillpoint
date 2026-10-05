#include "dsp.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
#define C0 299792458.0
#define ADC_SCALE (1.0f / 2047.0f)

/* ---- sala ------------------------------------------------------------- */
static bool in_box(const rf_box_t *b, float x, float y, float m)
{
    return b->x0 - m <= x && x <= b->x1 + m && b->y0 - m <= y && y <= b->y1 + m;
}

bool rf_room_inside(const rf_room_t *r, float x, float y, float margin)
{
    return r->x_min - margin <= x && x <= r->x_max + margin && r->y_min - margin <= y && y <= r->y_max + margin;
}

bool rf_room_near_exit(const rf_room_t *r, float x, float y)
{
    for (int i = 0; i < r->n_exits; i++) {
        if (in_box(&r->exits[i], x, y, 0.3f)) {
            return true;
        }
    }
    return false;
}

bool rf_room_excluded(const rf_room_t *r, float x, float y)
{
    for (int i = 0; i < r->n_exclusions; i++) {
        if (in_box(&r->exclusions[i], x, y, 0.0f)) {
            return true;
        }
    }
    return false;
}

/* ---- utilidades ---------------------------------------------------------- */
static float cabs2(rf_cpx_t a) { return a.re * a.re + a.im * a.im; }

static float parabolic(double ym1, double y0, double yp1)
{
    const double den = ym1 - 2.0 * y0 + yp1;
    if (den == 0.0) {
        return 0.0f;
    }
    double v = 0.5 * (ym1 - yp1) / den;
    return (float)(v < -0.5 ? -0.5 : (v > 0.5 ? 0.5 : v));
}

static double phase_diff(rf_cpx_t a, rf_cpx_t b) /* angle(a * conj(b)) */
{
    return atan2((double)a.im * b.re - (double)a.re * b.im, (double)a.re * b.re + (double)a.im * b.im);
}

static void to_world(const rf_dsp_t *d, float r, rf_cpx_t a0, rf_cpx_t a1, rf_cpx_t a2, float *x, float *y,
                     float *z)
{
    double ux = phase_diff(a1, a0) / M_PI, uy = phase_diff(a2, a0) / M_PI;
    const double n = ux * ux + uy * uy;
    if (n > 0.98) {
        const double s = sqrt(0.98 / n);
        ux *= s;
        uy *= s;
    }
    const double uz = -sqrt(1.0 - ux * ux - uy * uy);
    *x = (float)(r * ux);
    *y = (float)(r * uy);
    *z = (float)(d->room.mount_h + r * uz);
}

static int cmp_float(const void *a, const void *b)
{
    const float fa = *(const float *)a, fb = *(const float *)b;
    return (fa > fb) - (fa < fb);
}

static double median(float *v, int n) /* reordena v */
{
    qsort(v, (size_t)n, sizeof(float), cmp_float);
    return (n % 2) ? v[n / 2] : 0.5 * ((double)v[n / 2 - 1] + v[n / 2]);
}

static float db(double p) { return (float)(10.0 * log10(p)); }

/* ---- inicialización ------------------------------------------------------ */
int rf_dsp_init(rf_dsp_t *d, const rf_radar_cfg_t *cfg, const rf_room_t *room)
{
    if (rf_radar_check_eu(cfg) != RF_CFG_OK) {
        return -1;
    }
    if (cfg->n_samples != RF_N_SAMPLES || cfg->n_chirps != RF_N_CHIRPS) {
        return -2;
    }
    memset(d, 0, sizeof(*d));
    d->cfg = *cfg;
    d->room = *room;
    const double f_c = cfg->f_start_hz + cfg->bandwidth_hz / 2.0;
    const double lambda = C0 / f_c;
    d->range_res = (float)(C0 / (2.0 * cfg->bandwidth_hz));
    d->v_res = (float)(lambda / (2.0 * cfg->n_chirps * cfg->t_chirp_s));
    d->k_min = (int)ceil(0.35 / d->range_res);
    int km = (int)(hypot(room->mount_h, 4.0) / d->range_res);
    d->k_max = km < RF_N_RANGE - 2 ? km : RF_N_RANGE - 2;
    if (d->k_max >= RF_MICRO_BINS) {
        return -3;
    }
    d->cfar = (float)pow(10.0, 14.0 / 10.0);
    rf_hann(d->rwin, RF_N_SAMPLES);
    rf_hann(d->dwin, RF_N_CHIRPS);
    rf_hann(d->twin, RF_MICRO_W);
    return 0;
}

/* ---- camino de movimiento ------------------------------------------------ */
static int moving(rf_dsp_t *d, rf_det_t *out, int max_out)
{
    const int NC = RF_N_CHIRPS, NR = RF_N_RANGE, zero = NC / 2;
    static rf_cpx_t col[RF_N_CHIRPS];
    for (int rx = 0; rx < RF_N_RX; rx++) {
        for (int k = 0; k < NR; k++) {
            double mr = 0, mi = 0;
            for (int c = 0; c < NC; c++) {
                mr += d->X[rx][c][k].re;
                mi += d->X[rx][c][k].im;
            }
            mr /= NC;
            mi /= NC;
            for (int c = 0; c < NC; c++) {
                col[c].re = (float)((d->X[rx][c][k].re - mr) * d->dwin[c]);
                col[c].im = (float)((d->X[rx][c][k].im - mi) * d->dwin[c]);
            }
            rf_fft(col, NC);
            for (int c = 0; c < NC; c++) { /* fftshift */
                d->RD[rx][c][k] = col[(c + NC / 2) % NC];
            }
        }
    }
    for (int c = 0; c < NC; c++) {
        for (int k = 0; k < NR; k++) {
            d->P[c][k] = cabs2(d->RD[0][c][k]) + cabs2(d->RD[1][c][k]) + cabs2(d->RD[2][c][k]);
        }
    }
    /* CA-CFAR: guarda 1, entrenamiento 4; envolvente en Doppler, borde repetido en rango */
    const int g = 1, t = 4, big = 2 * (g + t) + 1, small = 2 * g + 1;
    typedef struct {
        int c, k;
        float p;
    } cand_t;
    static cand_t cand[RF_N_CHIRPS * RF_N_RANGE];
    int nc = 0;
    for (int c = 0; c < NC; c++) {
        if (c == zero) {
            continue;
        }
        for (int k = d->k_min; k < d->k_max; k++) {
            const float p = d->P[c][k];
            bool loc = true;
            for (int i = -1; i <= 1 && loc; i++) {
                for (int j = -1; j <= 1; j++) {
                    if (d->P[(c + i + NC) % NC][(k + j + NR) % NR] > p) {
                        loc = false;
                        break;
                    }
                }
            }
            if (!loc) {
                continue;
            }
            double sb = 0, ss = 0;
            for (int i = -(g + t); i <= g + t; i++) {
                const int ci = (c + i + NC) % NC;
                for (int j = -(g + t); j <= g + t; j++) {
                    int kj = k + j;
                    kj = kj < 0 ? 0 : (kj >= NR ? NR - 1 : kj);
                    sb += d->P[ci][kj];
                    if (abs(i) <= g && abs(j) <= g) {
                        ss += d->P[ci][kj];
                    }
                }
            }
            const double noise = (sb - ss) / (double)(big * big - small * small);
            if (p > d->cfar * noise) {
                cand[nc].c = c;
                cand[nc].k = k;
                cand[nc].p = p;
                nc++;
            }
        }
    }
    if (nc > RF_MAX_DETS) { /* las más potentes */
        for (int i = 1; i < nc; i++) {
            cand_t v = cand[i];
            int j = i - 1;
            while (j >= 0 && cand[j].p < v.p) {
                cand[j + 1] = cand[j];
                j--;
            }
            cand[j + 1] = v;
        }
        nc = RF_MAX_DETS;
    }
    int n = 0;
    for (int i = 0; i < nc && n < max_out; i++) {
        const int c = cand[i].c, k = cand[i].k;
        const float dk = parabolic(d->P[c][k - 1], d->P[c][k], d->P[c][k + 1]);
        const float r = (k + dk) * d->range_res;
        rf_det_t *o = &out[n++];
        to_world(d, r, d->RD[0][c][k], d->RD[1][c][k], d->RD[2][c][k], &o->x, &o->y, &o->z);
        o->r = r;
        o->vr = (float)(c - zero) * d->v_res;
        o->power_db = db((double)d->P[c][k] + 1e-12);
        o->kind = RF_DET_MOVE;
        o->micro_db = o->breath_hz = o->breath_snr_db = 0.0f;
    }
    return n;
}

/* ---- camino de micro-movimiento ------------------------------------------ */
#define W RF_MICRO_W
#define FR_BIN(i) ((i) < W / 2 ? (float)(i) / 10.0f : (float)((i) - W) / 10.0f) /* fftfreq(W, 0.1) */

static int micro(rf_dsp_t *d, rf_det_t *out, int max_out)
{
    static rf_cpx_t D[W][RF_N_RX][RF_MICRO_BINS];
    static float slow[RF_MICRO_BINS], fast[RF_MICRO_BINS], Sk[W];
    static rf_cpx_t Fk[W][RF_N_RX];
    static float tmp[W];
    const int K0 = d->k_min, K1 = d->k_max;
    int n_slow = 0, n_fast = 0;
    for (int i = 0; i < W; i++) {
        const float f = FR_BIN(i);
        n_slow += (f >= 0.1f - 1e-6f && f <= 2.0f + 1e-6f);
        n_fast += (fabsf(f) >= 3.0f - 1e-6f);
    }
    /* orden temporal y eliminación de la componente continua (muebles) */
    for (int rx = 0; rx < RF_N_RX; rx++) {
        for (int k = 0; k <= K1 && k < RF_MICRO_BINS; k++) {
            double mr = 0, mi = 0;
            for (int t = 0; t < W; t++) {
                const rf_cpx_t v = d->micro[(d->micro_head + t) % W][rx][k];
                mr += v.re;
                mi += v.im;
            }
            mr /= W;
            mi /= W;
            for (int t = 0; t < W; t++) {
                const rf_cpx_t v = d->micro[(d->micro_head + t) % W][rx][k];
                D[t][rx][k].re = (float)(v.re - mr);
                D[t][rx][k].im = (float)(v.im - mi);
            }
        }
    }
    memset(slow, 0, sizeof(slow));
    memset(fast, 0, sizeof(fast));
    static rf_cpx_t xw[W];
    for (int k = K0; k < K1; k++) {
        double s = 0, f = 0;
        for (int rx = 0; rx < RF_N_RX; rx++) {
            for (int t = 0; t < W; t++) {
                xw[t].re = D[t][rx][k].re * d->twin[t];
                xw[t].im = D[t][rx][k].im * d->twin[t];
            }
            for (int i = 0; i < W; i++) {
                const float fr = FR_BIN(i);
                const bool is_slow = fr >= 0.1f - 1e-6f && fr <= 2.0f + 1e-6f;
                const bool is_fast = fabsf(fr) >= 3.0f - 1e-6f;
                if (!is_slow && !is_fast) {
                    continue;
                }
                const float p = cabs2(rf_dft_bin(xw, W, 1, (size_t)i));
                if (is_slow) {
                    s += p;
                } else {
                    f += p;
                }
            }
        }
        slow[k] = (float)s;
        fast[k] = (float)(f / n_fast * n_slow);
    }
    int nb = 0;
    for (int k = K0; k < K1; k++) {
        tmp[nb++] = slow[k];
    }
    const double floor_ = median(tmp, nb) + 1e-15;
    typedef struct {
        float s;
        int k;
    } mc_t;
    mc_t cand[RF_MICRO_BINS];
    int nc = 0;
    for (int k = K0; k < K1; k++) {
        if (slow[k] < slow[k - 1] || slow[k] < slow[k + 1]) {
            continue;
        }
        const double ratio = slow[k] / ((double)fast[k] + 1e-15);
        if (slow[k] > 8.0 * floor_ && ratio > 10.0) {
            cand[nc].s = slow[k];
            cand[nc].k = k;
            nc++;
        }
    }
    /* orden descendente por (potencia, k) como sorted(..., reverse=True) */
    for (int i = 1; i < nc; i++) {
        mc_t v = cand[i];
        int j = i - 1;
        while (j >= 0 && (cand[j].s < v.s || (cand[j].s == v.s && cand[j].k < v.k))) {
            cand[j + 1] = cand[j];
            j--;
        }
        cand[j + 1] = v;
    }
    int n = 0;
    for (int ci = 0; ci < nc && ci < 8 && n < max_out; ci++) {
        const int k = cand[ci].k;
        const float dk = parabolic(slow[k - 1], slow[k], slow[k + 1]);
        const float r = (k + dk) * d->range_res;
        /* canal con más amplitud media */
        int ch = 0;
        double best = -1;
        for (int rx = 0; rx < RF_N_RX; rx++) {
            double a = 0;
            for (int t = 0; t < W; t++) {
                a += sqrt(cabs2(D[t][rx][k]));
            }
            if (a > best) {
                best = a;
                ch = rx;
            }
        }
        /* fase desenrollada (numpy.unwrap) */
        double ph[W], acc = 0, mean = 0;
        double prev = atan2(D[0][ch][k].im, D[0][ch][k].re);
        ph[0] = prev;
        for (int t = 1; t < W; t++) {
            const double raw = atan2(D[t][ch][k].im, D[t][ch][k].re);
            const double dd = raw - prev;
            double ddm = fmod(dd + M_PI, 2 * M_PI);
            if (ddm < 0) {
                ddm += 2 * M_PI;
            }
            ddm -= M_PI;
            if (ddm == -M_PI && dd > 0) {
                ddm = M_PI;
            }
            if (fabs(dd) >= M_PI) {
                acc += ddm - dd;
            }
            prev = raw;
            ph[t] = raw + acc;
        }
        for (int t = 0; t < W; t++) {
            mean += ph[t];
        }
        mean /= W;
        for (int t = 0; t < W; t++) {
            xw[t].re = (float)((ph[t] - mean) * d->twin[t]);
            xw[t].im = 0.0f;
        }
        float PS[W / 2];
        for (int i = 0; i < W / 2; i++) {
            PS[i] = cabs2(rf_dft_bin(xw, W, 1, (size_t)i));
        }
        int bi = 0;
        float bv = 0.0f;
        for (int i = 0; i < W / 2; i++) {
            const float fr = FR_BIN(i);
            if (fr >= 0.1f - 1e-6f && fr <= 0.6f + 1e-6f && PS[i] > bv) {
                bv = PS[i];
                bi = i;
            }
        }
        int nr = 0;
        for (int i = 0; i < W / 2; i++) {
            if (FR_BIN(i) >= 0.7f - 1e-6f) {
                tmp[nr++] = PS[i];
            }
        }
        const double ref = median(tmp, nr) + 1e-15;
        /* bin de banda lenta con más energía en esta celda -> ángulo */
        int fi = 0;
        float fv = 0.0f;
        for (int i = 0; i < W; i++) {
            const float fr = FR_BIN(i);
            if (!(fr >= 0.1f - 1e-6f && fr <= 2.0f + 1e-6f)) {
                continue;
            }
            float s = 0.0f;
            for (int rx = 0; rx < RF_N_RX; rx++) {
                for (int t = 0; t < W; t++) {
                    xw[t].re = D[t][rx][k].re * d->twin[t];
                    xw[t].im = D[t][rx][k].im * d->twin[t];
                }
                Fk[i][rx] = rf_dft_bin(xw, W, 1, (size_t)i);
                s += cabs2(Fk[i][rx]);
            }
            Sk[i] = s;
            if (s > fv) {
                fv = s;
                fi = i;
            }
        }
        rf_det_t *o = &out[n++];
        to_world(d, r, Fk[fi][0], Fk[fi][1], Fk[fi][2], &o->x, &o->y, &o->z);
        o->r = r;
        o->vr = 0.0f;
        o->power_db = o->micro_db = db((double)slow[k] + 1e-15);
        o->kind = RF_DET_MICRO;
        o->breath_hz = FR_BIN(bi);
        o->breath_snr_db = db(PS[bi] / ref);
    }
    return n;
}

/* ---- trama ---------------------------------------------------------------- */
int rf_dsp_process(rf_dsp_t *d, const int16_t *adc, rf_det_t *out, int max_out)
{
    static rf_cpx_t buf[RF_N_SAMPLES];
    for (int rx = 0; rx < RF_N_RX; rx++) {
        for (int c = 0; c < RF_N_CHIRPS; c++) {
            const int16_t *s = adc + ((size_t)rx * RF_N_CHIRPS + c) * RF_N_SAMPLES;
            for (int i = 0; i < RF_N_SAMPLES; i++) {
                buf[i].re = (float)s[i] * ADC_SCALE * d->rwin[i];
                buf[i].im = 0.0f;
            }
            rf_fft(buf, RF_N_SAMPLES);
            memcpy(d->X[rx][c], buf, sizeof(rf_cpx_t) * RF_N_RANGE);
        }
    }
    static rf_det_t tmp[RF_MAX_DETS + 16];
    int n = moving(d, tmp, RF_MAX_DETS);

    /* valor a Doppler cero de cada celda -> búfer de micro-movimiento */
    const int slot = (d->micro_head + d->micro_len) % W;
    for (int rx = 0; rx < RF_N_RX; rx++) {
        for (int k = 0; k < RF_MICRO_BINS; k++) {
            double mr = 0, mi = 0;
            for (int c = 0; c < RF_N_CHIRPS; c++) {
                mr += d->X[rx][c][k].re;
                mi += d->X[rx][c][k].im;
            }
            d->micro[slot][rx][k].re = (float)(mr / RF_N_CHIRPS);
            d->micro[slot][rx][k].im = (float)(mi / RF_N_CHIRPS);
        }
    }
    if (d->micro_len < W) {
        d->micro_len++;
    } else {
        d->micro_head = (d->micro_head + 1) % W;
    }
    d->frame_idx++;
    if (d->micro_len == W && d->frame_idx % RF_MICRO_EVERY == 0) {
        n += micro(d, tmp + n, 8);
    }
    int m = 0;
    for (int i = 0; i < n && m < max_out; i++) {
        if (rf_room_inside(&d->room, tmp[i].x, tmp[i].y, 0.15f) && !rf_room_excluded(&d->room, tmp[i].x, tmp[i].y)) {
            out[m++] = tmp[i];
        }
    }
    return m;
}
