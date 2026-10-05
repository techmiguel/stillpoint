/* Aplicación portable: una trama ADC entra, el estado publicable sale.
 *
 *   ADC -> dsp -> tracker -> registros del contrato -> ventanas por pista
 *       -> nn (int8) -> decisión con fallo seguro -> rf_outputs_t -> Matter
 *
 * No depende de ningún SDK. La capa de plataforma (port/) entrega las tramas
 * y traduce rf_outputs_t a atributos Matter (docs/04_matter.md). */
#pragma once
#include <stdbool.h>
#include <stdint.h>

#include "decision.h"
#include "dsp.h"
#include "tracker.h"

#define RF_APP_MAX_ZONES 3   /* endpoints 2-4 */

typedef struct {
    uint8_t id;
    rf_track_state_t state;
    float x, y, z;
    rf_posture_t posture;
    float confidence;
    rf_fall_t fall;
    bool evaluated;          /* ya tiene ventana completa */
} rf_person_t;

typedef struct {
    bool occupied;                       /* EP1 Occupancy */
    bool zone_occupied[RF_APP_MAX_ZONES]; /* EP2-4 */
    bool fall_alarm;                     /* EP5: caída confirmada o incierta */
    bool uncertain;                      /* EP6: alguna salida en «incierto» */
    uint8_t count;                       /* clúster de fabricante */
    rf_fall_t worst_fall;
    uint8_t n_people;
    rf_person_t people[RF_MAX_TRACKS];
    uint8_t n_proposed_exclusions;       /* zonas de interferencia aprendidas */
} rf_outputs_t;

typedef struct {
    uint8_t id;
    bool used;
    int n, head;
    float win[RF_WINDOW_FRAMES][RF_N_FIELDS];
    rf_decision_t dec;
    bool has_result;
    float probs[4];
    rf_posture_t posture;
    float conf;
    rf_fall_t fall;
} rf_track_slot_t;

/* Recibe cada registro de 66 B (para UART/USB de diagnóstico o captura). */
typedef void (*rf_record_cb)(const uint8_t *rec, void *ctx);

typedef struct {
    rf_dsp_t dsp;
    rf_tracker_t tk;
    rf_track_slot_t slots[RF_MAX_TRACKS];
    rf_box_t zones[RF_APP_MAX_ZONES];
    int n_zones;
    uint32_t n_frames;
    rf_record_cb on_record;
    void *cb_ctx;
} rf_app_t;

int rf_app_init(rf_app_t *app, const rf_radar_cfg_t *cfg, const rf_room_t *room, const rf_box_t *zones,
                int n_zones);
void rf_app_set_record_cb(rf_app_t *app, rf_record_cb cb, void *ctx);
void rf_app_frame(rf_app_t *app, const int16_t *adc, uint32_t t_ms, rf_outputs_t *out);
