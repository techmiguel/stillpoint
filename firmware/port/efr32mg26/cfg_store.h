/* Persistencia de la configuración de la sala (NVM3). */
#pragma once
#include <stddef.h>
#include <stdint.h>

#include "room_cfg.h"

/* 1 si se cargó de NVM3, 0 si no había una válida y se usa la de fábrica. */
int rf_cfg_load(rf_room_t *room, rf_box_t zones[RF_APP_MAX_ZONES], int *n_zones);

/* Valida y guarda el bloque; 0 si queda guardado, código negativo si no. */
int rf_cfg_save(const uint8_t *blob, size_t len);
