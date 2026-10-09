#include "features_pack.h"

#include <math.h>
#include <string.h>

uint16_t rf_crc16_ccitt(const uint8_t *data, size_t len)
{
    uint16_t crc = 0xFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (int b = 0; b < 8; b++) {
            crc = (crc & 0x8000u) ? (uint16_t)((crc << 1) ^ 0x1021u) : (uint16_t)(crc << 1);
        }
    }
    return crc;
}

void rf_quantize(const float values[RF_N_FIELDS], int16_t out[RF_N_FIELDS])
{
    for (unsigned i = 0; i < RF_N_FIELDS; i++) {
        double v = (double)values[i] * (double)rf_scale[i];
        double q = (v < 0.0) ? -floor(-v + 0.5) : floor(v + 0.5);
        if (q > 32767.0) {
            q = 32767.0;
        } else if (q < -32768.0) {
            q = -32768.0;
        }
        out[i] = (int16_t)q;
    }
}

static void put16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static void put32(uint8_t *p, uint32_t v) { put16(p, (uint16_t)v); put16(p + 2, (uint16_t)(v >> 16)); }
static uint16_t get16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }
static uint32_t get32(const uint8_t *p) { return get16(p) | ((uint32_t)get16(p + 2) << 16); }

size_t rf_pack(uint32_t frame_id, uint32_t t_ms, uint8_t track_id, uint8_t flags,
               const float values[RF_N_FIELDS], uint8_t out[RF_RECORD_SIZE])
{
    int16_t q[RF_N_FIELDS];
    rf_quantize(values, q);
    put16(out + 0, RF_MAGIC);
    out[2] = RF_CONTRACT_VERSION;
    out[3] = RF_N_FIELDS;
    put32(out + 4, frame_id);
    put32(out + 8, t_ms);
    out[12] = track_id;
    out[13] = flags;
    put16(out + 14, RF_CONTRACT_HASH16);
    for (unsigned i = 0; i < RF_N_FIELDS; i++) {
        put16(out + 16 + 2 * i, (uint16_t)q[i]);
    }
    put16(out + RF_RECORD_SIZE - 2, rf_crc16_ccitt(out, RF_RECORD_SIZE - 2));
    return RF_RECORD_SIZE;
}

int rf_unpack(const uint8_t rec[RF_RECORD_SIZE], int16_t q[RF_N_FIELDS],
              uint32_t *frame_id, uint32_t *t_ms, uint8_t *track_id, uint8_t *flags)
{
    if (rf_crc16_ccitt(rec, RF_RECORD_SIZE - 2) != get16(rec + RF_RECORD_SIZE - 2)) {
        return -1;
    }
    if (get16(rec) != RF_MAGIC || rec[2] != RF_CONTRACT_VERSION || rec[3] != RF_N_FIELDS ||
        get16(rec + 14) != RF_CONTRACT_HASH16) {
        return -2;
    }
    *frame_id = get32(rec + 4);
    *t_ms = get32(rec + 8);
    *track_id = rec[12];
    *flags = rec[13];
    for (unsigned i = 0; i < RF_N_FIELDS; i++) {
        q[i] = (int16_t)get16(rec + 16 + 2 * i);
    }
    return 0;
}
