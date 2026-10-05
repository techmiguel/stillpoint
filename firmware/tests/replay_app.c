/* Reproduce un fichero .rfad con la aplicación completa (rf_app_frame) y escribe
 * las salidas publicables por trama:
 *   "F <t> <recuento> <ocupado> <alarma_caida> <incierto>"
 *   "P <id> <postura> <caida> <evaluada>" por persona
 * Opcional: -r registros.bin guarda los registros de 66 B del contrato. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../src/app.h"

static int rd(FILE *f, void *p, size_t n) { return fread(p, 1, n, f) == n ? 0 : -1; }

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
        rf_box_t bb = {v[0], v[1], v[2], v[3]};
        b[i] = bb;
    }
    return 0;
}

static void save_record(const uint8_t *rec, void *ctx) { fwrite(rec, 1, RF_RECORD_SIZE, (FILE *)ctx); }

int main(int argc, char **argv)
{
    const char *in = NULL, *rec_path = NULL;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-r") && i + 1 < argc) {
            rec_path = argv[++i];
        } else {
            in = argv[i];
        }
    }
    FILE *f = in ? fopen(in, "rb") : NULL;
    if (!f) {
        fprintf(stderr, "uso: replay_app [-r registros.bin] fichero.rfad\n");
        return 2;
    }
    char magic[4];
    uint32_t ver, nfr;
    float rp[5];
    static rf_room_t room;
    if (rd(f, magic, 4) || memcmp(magic, "RFAD", 4) || rd(f, &ver, 4) || ver != 1 || rd(f, &nfr, 4) ||
        rd(f, rp, sizeof(rp)) || read_boxes(f, room.exits, &room.n_exits) ||
        read_boxes(f, room.exclusions, &room.n_exclusions)) {
        fprintf(stderr, "cabecera no válida\n");
        return 2;
    }
    room.mount_h = rp[0];
    room.x_min = rp[1];
    room.x_max = rp[2];
    room.y_min = rp[3];
    room.y_max = rp[4];
    static rf_app_t app;
    const rf_box_t zones[1] = {{-0.5f, 0.5f, -0.5f, 0.5f}}; /* zona de ejemplo bajo el sensor */
    if (rf_app_init(&app, &RF_RADAR_CFG_V1, &room, zones, 1) != 0) {
        fprintf(stderr, "configuración rechazada\n");
        return 3;
    }
    FILE *rf = rec_path ? fopen(rec_path, "wb") : NULL;
    if (rf) {
        rf_app_set_record_cb(&app, save_record, rf);
    }
    static int16_t adc[RF_N_RX * RF_N_CHIRPS * RF_N_SAMPLES];
    rf_outputs_t out;
    for (uint32_t i = 0; i < nfr; i++) {
        if (rd(f, adc, sizeof(adc))) {
            fprintf(stderr, "fichero truncado\n");
            return 2;
        }
        rf_app_frame(&app, adc, i * 100u, &out);
        printf("F %.1f %u %d %d %d\n", i / 10.0, out.count, out.occupied, out.fall_alarm, out.uncertain);
        for (int k = 0; k < out.n_people; k++) {
            const rf_person_t *p = &out.people[k];
            printf("P %u %d %d %d\n", p->id, p->posture, p->fall, p->evaluated);
        }
        if (getenv("RF_DEBUG") && (i + 1) % RF_WINDOW_HOP == 0) {
            for (int s = 0; s < RF_MAX_TRACKS; s++) {
                const rf_track_slot_t *sl = &app.slots[s];
                if (sl->used && sl->has_result) {
                    fprintf(stderr, "D %.1f %u %.4f %.4f %.4f %.4f post=%d fall=%d\n", i / 10.0, sl->id, sl->probs[0],
                            sl->probs[1], sl->probs[2], sl->probs[3], sl->posture, sl->fall);
                }
            }
        }
    }
    if (rf) {
        fclose(rf);
    }
    fclose(f);
    return 0;
}
