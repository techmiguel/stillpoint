/* Room configuration persistence (NVM3). */
#pragma once
#include <stddef.h>
#include <stdint.h>

#include "room_cfg.h"

/* 1 if loaded from NVM3, 0 if there was no valid one and the factory one is used. */
int rf_cfg_load(rf_room_t *room, rf_box_t zones[RF_APP_MAX_ZONES], int *n_zones);

/* Validates and stores the block; 0 when stored, negative code otherwise. */
int rf_cfg_save(const uint8_t *blob, size_t len);
