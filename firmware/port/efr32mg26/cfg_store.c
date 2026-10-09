/* Room configuration in NVM3 (v1 layout from src/room_cfg.h).
 * NOT built on the development PC (no SDK); room_cfg.c itself is tested.
 * The key must stay outside the range reserved by the SDK's Matter stack:
 * check it against the documentation of the SDK version in use. */
#include "cfg_store.h"

#include "nvm3_default.h"

#define RF_NVM3_KEY_ROOM 0x0F600u

int rf_cfg_load(rf_room_t *room, rf_box_t zones[RF_APP_MAX_ZONES], int *n_zones)
{
    uint8_t buf[RF_ROOM_CFG_MAX_SIZE];
    uint32_t type;
    size_t len;
    if (nvm3_getObjectInfo(nvm3_defaultHandle, RF_NVM3_KEY_ROOM, &type, &len) == ECODE_NVM3_OK &&
        len <= sizeof(buf) &&
        nvm3_readData(nvm3_defaultHandle, RF_NVM3_KEY_ROOM, buf, len) == ECODE_NVM3_OK &&
        rf_room_cfg_unpack(buf, len, room, zones, n_zones) == RF_ROOM_CFG_OK) {
        return 1;
    }
    rf_room_cfg_factory(room, zones, n_zones);   /* no valid configuration: factory one */
    return 0;
}

int rf_cfg_save(const uint8_t *blob, size_t len)
{
    rf_room_t r;
    rf_box_t z[RF_APP_MAX_ZONES];
    int nz;
    const int e = rf_room_cfg_unpack(blob, len, &r, z, &nz);   /* never store anything invalid */
    if (e != RF_ROOM_CFG_OK) {
        return e;
    }
    return nvm3_writeData(nvm3_defaultHandle, RF_NVM3_KEY_ROOM, blob, len) == ECODE_NVM3_OK ? 0 : -10;
}
