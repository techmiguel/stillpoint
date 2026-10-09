/* Replays a file of ADC frames through the C DSP and tracker and writes,
 * per frame, the count and the features of every confirmed track.
 *
 * Input layout (little-endian), written by ml/radarref/adcfile.py:
 *   "RFAD" u32 version=1 u32 n_frames
 *   f32 mount_h x_min x_max y_min y_max
 *   u32 n_exits, n_exits × f32[4]; u32 n_excl, n_excl × f32[4]
 *   n_frames × int16[3][32][128]
 * Output (text): "F <t> <count> <n_tracks>" and per track "T <id> <state> <f0> ... <f23>".
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../src/dsp.h"
#include "../src/tracker.h"

static int rd(FILE *f, void *p, size_t n)
{
    return fread(p, 1, n, f) == n ? 0 : -1;
}

static int read_boxes(FILE *f, rf_box_t *b, int *n)
{
    uint32_t k;
    if (rd(f, &k, 4) || k > RF_MAX_ZONES) {
        return -1;
    }
    *n = (int)k;
    for (uint32_t i = 0; i < k; i++) {
        float v[4];
        if (rd(f, v, sizeof(v))) {
            return -1;
        }
        b[i].x0 = v[0];
        b[i].x1 = v[1];
        b[i].y0 = v[2];
        b[i].y1 = v[3];
    }
    return 0;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: replay file.rfad\n");
        return 2;
    }
    FILE *f = fopen(argv[1], "rb");
    if (!f) {
        perror(argv[1]);
        return 2;
    }
    char magic[4];
    uint32_t ver, nfr;
    float rp[5];
    static rf_room_t room;
    if (rd(f, magic, 4) || memcmp(magic, "RFAD", 4) || rd(f, &ver, 4) || ver != 1 || rd(f, &nfr, 4) ||
        rd(f, rp, sizeof(rp)) || read_boxes(f, room.exits, &room.n_exits) ||
        read_boxes(f, room.exclusions, &room.n_exclusions)) {
        fprintf(stderr, "invalid header\n");
        return 2;
    }
    room.mount_h = rp[0];
    room.x_min = rp[1];
    room.x_max = rp[2];
    room.y_min = rp[3];
    room.y_max = rp[4];

    static rf_dsp_t dsp;
    static rf_tracker_t tk;
    if (rf_dsp_init(&dsp, &RF_RADAR_CFG_V1, &room) != 0) {
        fprintf(stderr, "radar configuration rejected\n");
        return 3;
    }
    rf_tracker_init(&tk, &room);
    static int16_t adc[RF_N_RX * RF_N_CHIRPS * RF_N_SAMPLES];
    static rf_det_t dets[RF_MAX_DETS + 16];
    for (uint32_t i = 0; i < nfr; i++) {
        if (rd(f, adc, sizeof(adc))) {
            fprintf(stderr, "file truncated at frame %u\n", i);
            return 2;
        }
        const double t = i / 10.0;
        const int n = rf_dsp_process(&dsp, adc, dets, RF_MAX_DETS + 16);
        rf_tracker_step(&tk, t, dets, n);
        int conf = 0;
        for (int k = 0; k < tk.n_tracks; k++) {
            conf += tk.tracks[k].confirmed;
        }
        printf("F %.1f %d %d\n", t, rf_tracker_count(&tk), conf);
        for (int k = 0; k < tk.n_tracks; k++) {
            const rf_track_t *tr = &tk.tracks[k];
            if (!tr->confirmed) {
                continue;
            }
            float feat[RF_N_FIELDS];
            rf_tracker_features(&tk, tr, t, feat);
            printf("T %u %d", tr->id, (int)tr->state);
            for (unsigned j = 0; j < RF_N_FIELDS; j++) {
                printf(" %.6g", feat[j]);
            }
            printf("\n");
        }
    }
    fclose(f);
    return 0;
}
