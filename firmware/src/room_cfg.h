/* Room configuration (geometry, exits, exclusions and zones) as a v1
 * binary block stored in NVM3 and received over the diagnostic UART
 * (tools/room_cfg.py). Portable and tested on the PC against the Python tool.
 *
 * Layout (little-endian, signed distances in mm):
 *   0  'R','6','R','C'                   magic
 *   4  u8 version (1)  u8 reserved
 *   6  i16 mount height, i16 x_min, x_max, y_min, y_max
 *  16  u8 n_exits, u8 n_exclusions, u8 n_zones, u8 reserved
 *  20  boxes (x0, x1, y0, y1 as i16): exits, exclusions, zones
 *   …  u16 CRC-16/CCITT over everything above
 */
#pragma once
#include <stddef.h>
#include <stdint.h>

#include "app.h"

#define RF_ROOM_CFG_VERSION 1u
#define RF_ROOM_CFG_MAX_SIZE (20u + 8u * (RF_MAX_ZONES + RF_MAX_ZONES + RF_APP_MAX_ZONES) + 2u)

enum {
    RF_ROOM_CFG_OK = 0,
    RF_ROOM_CFG_E_SIZE = -1,     /* inconsistent length or buffer too small */
    RF_ROOM_CFG_E_MAGIC = -2,
    RF_ROOM_CFG_E_VERSION = -3,
    RF_ROOM_CFG_E_CRC = -4,
    RF_ROOM_CFG_E_RANGE = -5,    /* geometry out of bounds */
};

/* Factory configuration (4 x 4 m room, 2.6 m ceiling, one door, one zone). */
void rf_room_cfg_factory(rf_room_t *room, rf_box_t zones[RF_APP_MAX_ZONES], int *n_zones);

/* Checks physical limits: height 1.8-4 m, room within ±10 m, boxes with x0 < x1 and y0 < y1. */
int rf_room_cfg_validate(const rf_room_t *room, const rf_box_t *zones, int n_zones);

/* Returns the length written or a negative error code. */
int rf_room_cfg_pack(const rf_room_t *room, const rf_box_t *zones, int n_zones, uint8_t *out, size_t cap);

/* RF_ROOM_CFG_OK or a negative code; on failure the output is left untouched. */
int rf_room_cfg_unpack(const uint8_t *in, size_t len, rf_room_t *room, rf_box_t zones[RF_APP_MAX_ZONES],
                       int *n_zones);
