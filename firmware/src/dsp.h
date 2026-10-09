/* Radar DSP: range-Doppler + CFAR (motion) and micro-motion
 * (breathing). Mirror of ml/radarref/dsp.py; tests/replay.c compares them. */
#pragma once
#include <stdbool.h>
#include <stdint.h>

#include "radar_limits.h"
#include "rf_fft.h"

#define RF_N_RX 3
#define RF_N_CHIRPS 32
#define RF_N_SAMPLES 128
#define RF_N_RANGE (RF_N_SAMPLES / 2)
#define RF_MICRO_W 100        /* frames in the micro-motion window (10 s) */
#define RF_MICRO_EVERY 5
#define RF_MICRO_BINS 48      /* range cells kept (covers 5.7 m) */
#define RF_MAX_DETS 48       /* same as FrontEnd.max_dets */
#define RF_MAX_ZONES 8

typedef struct {
    float x0, x1, y0, y1;
} rf_box_t;

typedef struct {
    float mount_h;
    float x_min, x_max, y_min, y_max;
    rf_box_t exits[RF_MAX_ZONES];
    int n_exits;
    rf_box_t exclusions[RF_MAX_ZONES];
    int n_exclusions;
} rf_room_t;

bool rf_room_inside(const rf_room_t *r, float x, float y, float margin);
bool rf_room_near_exit(const rf_room_t *r, float x, float y);
bool rf_room_excluded(const rf_room_t *r, float x, float y);

typedef enum { RF_DET_MOVE = 0, RF_DET_MICRO = 1 } rf_det_kind_t;

typedef struct {
    float x, y, z, r, vr, power_db;
    rf_det_kind_t kind;
    float micro_db, breath_hz, breath_snr_db;
} rf_det_t;

typedef struct {
    rf_radar_cfg_t cfg;
    rf_room_t room;
    float range_res, v_res;
    int k_min, k_max;
    float cfar;
    float rwin[RF_N_SAMPLES], dwin[RF_N_CHIRPS], twin[RF_MICRO_W];
    rf_cpx_t X[RF_N_RX][RF_N_CHIRPS][RF_N_RANGE];       /* range spectrum */
    rf_cpx_t RD[RF_N_RX][RF_N_CHIRPS][RF_N_RANGE];      /* range-Doppler (shifted) */
    float P[RF_N_CHIRPS][RF_N_RANGE];
    rf_cpx_t micro[RF_MICRO_W][RF_N_RX][RF_MICRO_BINS]; /* ring buffer */
    int micro_head, micro_len;
    uint32_t frame_idx;
} rf_dsp_t;

/* 0 if the configuration is valid and fits the buffers; <0 otherwise. */
int rf_dsp_init(rf_dsp_t *d, const rf_radar_cfg_t *cfg, const rf_room_t *room);

/* adc: [rx][chirp][sample] in 12-bit counts (±2047). Returns the number of detections. */
int rf_dsp_process(rf_dsp_t *d, const int16_t *adc, rf_det_t *out, int max_out);
