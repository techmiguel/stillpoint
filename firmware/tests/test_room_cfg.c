/* Pruebas de room_cfg.c y del decodificador COBS.
 *   test_room_cfg                 autoprueba (ida y vuelta, corrupción, límites, COBS)
 *   test_room_cfg trama.bin f.bin decodifica una trama de tools/room_cfg.py, imprime la
 *                                 configuración y escribe en f.bin el bloque de fábrica */
#include <stdio.h>
#include <string.h>

#include "../src/cobs.h"
#include "../src/room_cfg.h"

static int fails;
#define CHECK(c)                                                    \
    do {                                                            \
        if (!(c)) {                                                 \
            printf("FALLO %s:%d %s\n", __FILE__, __LINE__, #c);     \
            fails++;                                                \
        }                                                           \
    } while (0)

static void print_box(const char *k, const rf_box_t *b)
{
    printf("%s %.3f %.3f %.3f %.3f\n", k, b->x0, b->x1, b->y0, b->y1);
}

static int selftest(void)
{
    rf_room_t r, r2;
    rf_box_t z[RF_APP_MAX_ZONES], z2[RF_APP_MAX_ZONES];
    int nz, nz2;
    uint8_t buf[RF_ROOM_CFG_MAX_SIZE];
    rf_room_cfg_factory(&r, z, &nz);
    const int n = rf_room_cfg_pack(&r, z, nz, buf, sizeof(buf));
    CHECK(n == 20 + 8 * 2 + 2);
    CHECK(rf_room_cfg_unpack(buf, (size_t)n, &r2, z2, &nz2) == RF_ROOM_CFG_OK);
    CHECK(nz2 == 1 && r2.n_exits == 1 && r2.n_exclusions == 0);
    CHECK(r2.mount_h == 2.6f && r2.exits[0].x0 == 1.6f && z2[0].y1 == 2.0f);
    /* cualquier byte alterado se rechaza y no toca la salida */
    for (int i = 0; i < n; i++) {
        uint8_t c[RF_ROOM_CFG_MAX_SIZE];
        memcpy(c, buf, (size_t)n);
        c[i] ^= 0x5A;
        r2.mount_h = -1.0f;
        CHECK(rf_room_cfg_unpack(c, (size_t)n, &r2, z2, &nz2) != RF_ROOM_CFG_OK);
        CHECK(r2.mount_h == -1.0f);
    }
    CHECK(rf_room_cfg_unpack(buf, (size_t)n - 1, &r2, z2, &nz2) == RF_ROOM_CFG_E_SIZE);
    CHECK(rf_room_cfg_pack(&r, z, nz, buf, 10) == RF_ROOM_CFG_E_SIZE);
    /* límites físicos */
    rf_room_t bad = r;
    bad.mount_h = 1.2f;
    CHECK(rf_room_cfg_pack(&bad, z, nz, buf, sizeof(buf)) == RF_ROOM_CFG_E_RANGE);
    bad = r;
    bad.x_min = 3.0f;
    CHECK(rf_room_cfg_pack(&bad, z, nz, buf, sizeof(buf)) == RF_ROOM_CFG_E_RANGE);
    bad = r;
    bad.exits[0].y0 = 0.6f;
    CHECK(rf_room_cfg_pack(&bad, z, nz, buf, sizeof(buf)) == RF_ROOM_CFG_E_RANGE);
    CHECK(rf_room_cfg_pack(&r, z, RF_APP_MAX_ZONES + 1, buf, sizeof(buf)) == RF_ROOM_CFG_E_RANGE);
    /* configuración máxima */
    rf_room_t big = r;
    rf_box_t zb[RF_APP_MAX_ZONES];
    big.n_exits = big.n_exclusions = RF_MAX_ZONES;
    for (int i = 0; i < RF_MAX_ZONES; i++) {
        big.exits[i] = big.exclusions[i] = (rf_box_t){-1.0f + 0.1f * i, 1.0f, -1.0f, 1.0f};
    }
    for (int i = 0; i < RF_APP_MAX_ZONES; i++) {
        zb[i] = (rf_box_t){0.0f, 1.0f, 0.0f, 1.0f + i};
    }
    CHECK(rf_room_cfg_pack(&big, zb, RF_APP_MAX_ZONES, buf, sizeof(buf)) == (int)RF_ROOM_CFG_MAX_SIZE);
    CHECK(rf_room_cfg_unpack(buf, RF_ROOM_CFG_MAX_SIZE, &r2, z2, &nz2) == RF_ROOM_CFG_OK);
    /* COBS: ida y vuelta con ceros y bloques largos; tramas mal formadas */
    uint8_t raw[600], enc[700], dec[600];
    for (size_t i = 0; i < sizeof(raw); i++) {
        raw[i] = (uint8_t)(i % 7 == 0 ? 0 : i);
    }
    for (size_t len = 0; len <= sizeof(raw); len += 37) {
        const size_t m = rf_cobs_encode(raw, len, enc);
        CHECK(enc[m - 1] == 0);
        CHECK(rf_cobs_decode(enc, m - 1, dec, sizeof(dec)) == (int)len);
        CHECK(memcmp(raw, dec, len) == 0);
    }
    const uint8_t bad1[] = {0x05, 0x11, 0x22};      /* el código promete más bytes */
    const uint8_t bad2[] = {0x03, 0x11, 0x00};      /* cero dentro de la trama */
    CHECK(rf_cobs_decode(bad1, sizeof(bad1), dec, sizeof(dec)) == -1);
    CHECK(rf_cobs_decode(bad2, sizeof(bad2), dec, sizeof(dec)) == -1);
    CHECK(rf_cobs_decode(enc, rf_cobs_encode(raw, 100, enc) - 1, dec, 10) == -1);
    printf(fails ? "FALLOS: %d\n" : "OK (%d fallos)\n", fails);
    return fails ? 1 : 0;
}

int main(int argc, char **argv)
{
    if (argc == 1) {
        return selftest();
    }
    if (argc != 3) {
        return 2;
    }
    static uint8_t frame[1024], msg[1024];
    FILE *f = fopen(argv[1], "rb");
    if (!f) {
        return 2;
    }
    size_t n = fread(frame, 1, sizeof(frame), f);
    fclose(f);
    if (n == 0 || frame[n - 1] != 0) {
        return 3;
    }
    const int m = rf_cobs_decode(frame, n - 1, msg, sizeof(msg));
    if (m < 1 || msg[0] != 0x01) {
        return 3;
    }
    rf_room_t r;
    rf_box_t z[RF_APP_MAX_ZONES];
    int nz;
    const int e = rf_room_cfg_unpack(msg + 1, (size_t)m - 1, &r, z, &nz);
    printf("estado %d\n", e);
    if (e == RF_ROOM_CFG_OK) {
        printf("altura %.3f\n", r.mount_h);
        printf("sala %.3f %.3f %.3f %.3f\n", r.x_min, r.x_max, r.y_min, r.y_max);
        for (int i = 0; i < r.n_exits; i++) {
            print_box("puerta", &r.exits[i]);
        }
        for (int i = 0; i < r.n_exclusions; i++) {
            print_box("exclusion", &r.exclusions[i]);
        }
        for (int i = 0; i < nz; i++) {
            print_box("zona", &z[i]);
        }
    }
    uint8_t blob[RF_ROOM_CFG_MAX_SIZE];
    rf_room_cfg_factory(&r, z, &nz);
    const int k = rf_room_cfg_pack(&r, z, nz, blob, sizeof(blob));
    FILE *o = fopen(argv[2], "wb");
    if (!o || k < 0) {
        return 2;
    }
    fwrite(blob, 1, (size_t)k, o);
    fclose(o);
    return 0;
}
