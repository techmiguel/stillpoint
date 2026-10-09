/* Radar start-up from the Matter application (AppTask::AppInit of the Silicon
 * Labs example). The room geometry comes from NVM3 (tools/room_cfg.py writes it
 * over the diagnostic UART) or, when there is no valid one, from the factory
 * configuration in src/room_cfg.c. NOT built on the development PC
 * (no SDK there). */
extern "C" {
#include "app.h"
#include "cfg_store.h"
int rf_radar_start(const rf_room_t * room, const rf_box_t * zones, int n_zones);
}

#include <lib/support/logging/CHIPLogging.h>

void RadarInit()
{
    rf_room_t room;
    rf_box_t zones[RF_APP_MAX_ZONES];
    int n_zones;
    if (!rf_cfg_load(&room, zones, &n_zones))
    {
        ChipLogProgress(AppServer, "stillpoint: no stored room configuration, using the factory one");
    }
    const int r = rf_radar_start(&room, zones, n_zones);
    if (r != 0)
    {
        // Fail safe: without the radar the device reports "uncertain" (EP6) and never
        // reports an empty room it has not measured.
        ChipLogError(AppServer, "stillpoint: radar failed to start (%d)", r);
    }
}
