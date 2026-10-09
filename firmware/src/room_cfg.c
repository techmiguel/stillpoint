#include "room_cfg.h"

#include <math.h>
#include <string.h>

#include "features_pack.h"   /* rf_crc16_ccitt */

static const uint8_t MAGIC[4] = {'R', '6', 'R', 'C'};

static void put16(uint8_t *p, int32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)((uint32_t)v >> 8); }
static int16_t get16(const uint8_t *p) { return (int16_t)(uint16_t)(p[0] | (p[1] << 8)); }
static int16_t to_mm(float m) { return (int16_t)lrintf(m * 1000.0f); }
static float from_mm(int16_t v) { return (float)v / 1000.0f; }

void rf_room_cfg_factory(rf_room_t *room, rf_box_t zones[RF_APP_MAX_ZONES], int *n_zones)
{
    memset(room, 0, sizeof(*room));
    room->mount_h = 2.6f;
    room->x_min = -2.0f;
    room->x_max = 2.0f;
    room->y_min = -2.0f;
    room->y_max = 2.0f;
    room->exits[0] = (rf_box_t){1.6f, 2.0f, -0.5f, 0.5f};   /* door */
    room->n_exits = 1;
    memset(zones, 0, sizeof(rf_box_t) * RF_APP_MAX_ZONES);
    zones[0] = (rf_box_t){-2.0f, -0.8f, 0.6f, 2.0f};        /* e.g. the bed */
    *n_zones = 1;
}

static int box_ok(const rf_box_t *b)
{
    return b->x0 < b->x1 && b->y0 < b->y1 && fabsf(b->x0) <= 10.0f && fabsf(b->x1) <= 10.0f &&
           fabsf(b->y0) <= 10.0f && fabsf(b->y1) <= 10.0f;
}

int rf_room_cfg_validate(const rf_room_t *room, const rf_box_t *zones, int n_zones)
{
    if (!(room->mount_h >= 1.8f && room->mount_h <= 4.0f)) {
        return RF_ROOM_CFG_E_RANGE;
    }
    const rf_box_t r = {room->x_min, room->x_max, room->y_min, room->y_max};
    if (!box_ok(&r)) {
        return RF_ROOM_CFG_E_RANGE;
    }
    if (room->n_exits < 0 || room->n_exits > RF_MAX_ZONES || room->n_exclusions < 0 ||
        room->n_exclusions > RF_MAX_ZONES || n_zones < 0 || n_zones > RF_APP_MAX_ZONES) {
        return RF_ROOM_CFG_E_RANGE;
    }
    for (int i = 0; i < room->n_exits; i++) {
        if (!box_ok(&room->exits[i])) {
            return RF_ROOM_CFG_E_RANGE;
        }
    }
    for (int i = 0; i < room->n_exclusions; i++) {
        if (!box_ok(&room->exclusions[i])) {
            return RF_ROOM_CFG_E_RANGE;
        }
    }
    for (int i = 0; i < n_zones; i++) {
        if (!box_ok(&zones[i])) {
            return RF_ROOM_CFG_E_RANGE;
        }
    }
    return RF_ROOM_CFG_OK;
}

static size_t put_box(uint8_t *p, const rf_box_t *b)
{
    put16(p, to_mm(b->x0));
    put16(p + 2, to_mm(b->x1));
    put16(p + 4, to_mm(b->y0));
    put16(p + 6, to_mm(b->y1));
    return 8;
}

static size_t get_box(const uint8_t *p, rf_box_t *b)
{
    b->x0 = from_mm(get16(p));
    b->x1 = from_mm(get16(p + 2));
    b->y0 = from_mm(get16(p + 4));
    b->y1 = from_mm(get16(p + 6));
    return 8;
}

int rf_room_cfg_pack(const rf_room_t *room, const rf_box_t *zones, int n_zones, uint8_t *out, size_t cap)
{
    int e = rf_room_cfg_validate(room, zones, n_zones);
    if (e != RF_ROOM_CFG_OK) {
        return e;
    }
    const size_t len = 20u + 8u * (size_t)(room->n_exits + room->n_exclusions + n_zones) + 2u;
    if (cap < len) {
        return RF_ROOM_CFG_E_SIZE;
    }
    memcpy(out, MAGIC, 4);
    out[4] = RF_ROOM_CFG_VERSION;
    out[5] = 0;
    put16(out + 6, to_mm(room->mount_h));
    put16(out + 8, to_mm(room->x_min));
    put16(out + 10, to_mm(room->x_max));
    put16(out + 12, to_mm(room->y_min));
    put16(out + 14, to_mm(room->y_max));
    out[16] = (uint8_t)room->n_exits;
    out[17] = (uint8_t)room->n_exclusions;
    out[18] = (uint8_t)n_zones;
    out[19] = 0;
    size_t w = 20;
    for (int i = 0; i < room->n_exits; i++) {
        w += put_box(out + w, &room->exits[i]);
    }
    for (int i = 0; i < room->n_exclusions; i++) {
        w += put_box(out + w, &room->exclusions[i]);
    }
    for (int i = 0; i < n_zones; i++) {
        w += put_box(out + w, &zones[i]);
    }
    const uint16_t crc = rf_crc16_ccitt(out, w);
    out[w++] = (uint8_t)crc;
    out[w++] = (uint8_t)(crc >> 8);
    return (int)w;
}

int rf_room_cfg_unpack(const uint8_t *in, size_t len, rf_room_t *room, rf_box_t zones[RF_APP_MAX_ZONES],
                       int *n_zones)
{
    if (len < 22u) {
        return RF_ROOM_CFG_E_SIZE;
    }
    if (memcmp(in, MAGIC, 4) != 0) {
        return RF_ROOM_CFG_E_MAGIC;
    }
    if (in[4] != RF_ROOM_CFG_VERSION) {
        return RF_ROOM_CFG_E_VERSION;
    }
    const int ne = in[16], nx = in[17], nz = in[18];
    if (ne > RF_MAX_ZONES || nx > RF_MAX_ZONES || nz > RF_APP_MAX_ZONES) {
        return RF_ROOM_CFG_E_RANGE;
    }
    const size_t need = 20u + 8u * (size_t)(ne + nx + nz) + 2u;
    if (len != need) {
        return RF_ROOM_CFG_E_SIZE;
    }
    if (rf_crc16_ccitt(in, need - 2u) != (uint16_t)(in[need - 2u] | (in[need - 1u] << 8))) {
        return RF_ROOM_CFG_E_CRC;
    }
    rf_room_t r;
    rf_box_t z[RF_APP_MAX_ZONES];
    memset(&r, 0, sizeof(r));
    memset(z, 0, sizeof(z));
    r.mount_h = from_mm(get16(in + 6));
    r.x_min = from_mm(get16(in + 8));
    r.x_max = from_mm(get16(in + 10));
    r.y_min = from_mm(get16(in + 12));
    r.y_max = from_mm(get16(in + 14));
    r.n_exits = ne;
    r.n_exclusions = nx;
    size_t p = 20;
    for (int i = 0; i < ne; i++) {
        p += get_box(in + p, &r.exits[i]);
    }
    for (int i = 0; i < nx; i++) {
        p += get_box(in + p, &r.exclusions[i]);
    }
    for (int i = 0; i < nz; i++) {
        p += get_box(in + p, &z[i]);
    }
    const int e = rf_room_cfg_validate(&r, z, nz);
    if (e != RF_ROOM_CFG_OK) {
        return e;
    }
    *room = r;
    memcpy(zones, z, sizeof(z));
    *n_zones = nz;
    return RF_ROOM_CFG_OK;
}
