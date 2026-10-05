/* Registro de características del contrato v1 (contracts/features_v1.yaml).
 * Referencia de comportamiento: ml/radarref/contract.py. */
#pragma once
#include <stddef.h>
#include <stdint.h>

#include "features_v1.h"

uint16_t rf_crc16_ccitt(const uint8_t *data, size_t len);

/* Física -> int16: redondeo al más cercano (mitades lejos de cero) y saturación. */
void rf_quantize(const float values[RF_N_FIELDS], int16_t out[RF_N_FIELDS]);

/* Empaqueta un registro de RF_RECORD_SIZE bytes. Devuelve los bytes escritos. */
size_t rf_pack(uint32_t frame_id, uint32_t t_ms, uint8_t track_id, uint8_t flags,
               const float values[RF_N_FIELDS], uint8_t out[RF_RECORD_SIZE]);

/* 0 si el registro es válido para este contrato; <0 en caso contrario. */
int rf_unpack(const uint8_t rec[RF_RECORD_SIZE], int16_t q[RF_N_FIELDS],
              uint32_t *frame_id, uint32_t *t_ms, uint8_t *track_id, uint8_t *flags);
