/* Feature record of contract v1 (contracts/features_v1.yaml).
 * Behavioural reference: ml/radarref/contract.py. */
#pragma once
#include <stddef.h>
#include <stdint.h>

#include "features_v1.h"

uint16_t rf_crc16_ccitt(const uint8_t *data, size_t len);

/* Physical -> int16: round to nearest (halves away from zero) and saturate. */
void rf_quantize(const float values[RF_N_FIELDS], int16_t out[RF_N_FIELDS]);

/* Packs one record of RF_RECORD_SIZE bytes. Returns the bytes written. */
size_t rf_pack(uint32_t frame_id, uint32_t t_ms, uint8_t track_id, uint8_t flags,
               const float values[RF_N_FIELDS], uint8_t out[RF_RECORD_SIZE]);

/* 0 if the record is valid for this contract; <0 otherwise. */
int rf_unpack(const uint8_t rec[RF_RECORD_SIZE], int16_t q[RF_N_FIELDS],
              uint32_t *frame_id, uint32_t *t_ms, uint8_t *track_id, uint8_t *flags);
