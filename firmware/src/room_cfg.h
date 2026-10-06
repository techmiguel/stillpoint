/* Configuración de la sala (geometría, puertas, exclusiones y zonas) en un
 * bloque binario v1 que se guarda en NVM3 y llega por la UART de diagnóstico
 * (tools/room_cfg.py). Portable y probado en PC contra la herramienta Python.
 *
 * Formato (little-endian, distancias en mm con signo):
 *   0  'R','6','R','C'                   firma
 *   4  u8 versión (1)  u8 reservado
 *   6  i16 altura de montaje, i16 x_min, x_max, y_min, y_max
 *  16  u8 n_puertas, u8 n_exclusiones, u8 n_zonas, u8 reservado
 *  20  cajas (x0, x1, y0, y1 en i16): puertas, exclusiones, zonas
 *   …  u16 CRC-16/CCITT de todo lo anterior
 */
#pragma once
#include <stddef.h>
#include <stdint.h>

#include "app.h"

#define RF_ROOM_CFG_VERSION 1u
#define RF_ROOM_CFG_MAX_SIZE (20u + 8u * (RF_MAX_ZONES + RF_MAX_ZONES + RF_APP_MAX_ZONES) + 2u)

enum {
    RF_ROOM_CFG_OK = 0,
    RF_ROOM_CFG_E_SIZE = -1,     /* longitud incoherente o búfer pequeño */
    RF_ROOM_CFG_E_MAGIC = -2,
    RF_ROOM_CFG_E_VERSION = -3,
    RF_ROOM_CFG_E_CRC = -4,
    RF_ROOM_CFG_E_RANGE = -5,    /* geometría fuera de límites */
};

/* Configuración de fábrica (sala de 4 x 4 m, techo a 2,6 m, una puerta, una zona). */
void rf_room_cfg_factory(rf_room_t *room, rf_box_t zones[RF_APP_MAX_ZONES], int *n_zones);

/* Comprueba límites físicos: altura 1,8-4 m, sala dentro de ±10 m, cajas con x0 < x1 e y0 < y1. */
int rf_room_cfg_validate(const rf_room_t *room, const rf_box_t *zones, int n_zones);

/* Devuelve la longitud escrita o un código de error negativo. */
int rf_room_cfg_pack(const rf_room_t *room, const rf_box_t *zones, int n_zones, uint8_t *out, size_t cap);

/* RF_ROOM_CFG_OK o un código negativo; si falla no modifica la salida. */
int rf_room_cfg_unpack(const uint8_t *in, size_t len, rf_room_t *room, rf_box_t zones[RF_APP_MAX_ZONES],
                       int *n_zones);
