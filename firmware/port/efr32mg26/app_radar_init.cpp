/* Arranque del radar desde la aplicación Matter (AppTask::AppInit del ejemplo
 * de Silicon Labs). La geometría de la sala sale de NVM3 (tools/room_cfg.py la
 * escribe por la UART de diagnóstico) o, si no hay ninguna válida, de la
 * configuración de fábrica de src/room_cfg.c. NO compilado en el PC de
 * desarrollo (sin SDK). */
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
        ChipLogProgress(AppServer, "radar60: sin configuración de sala guardada, se usa la de fábrica");
    }
    const int r = rf_radar_start(&room, zones, n_zones);
    if (r != 0)
    {
        // Fallo seguro: sin radar el dispositivo se anuncia «incierto» (EP6) y no
        // informa de una sala vacía que no ha medido.
        ChipLogError(AppServer, "radar60: el radar no arranca (%d)", r);
    }
}
