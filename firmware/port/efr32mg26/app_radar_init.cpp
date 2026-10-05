/* Arranque del radar desde la aplicación Matter (AppTask::AppInit del ejemplo
 * de Silicon Labs). La geometría de la sala es la configuración de fábrica de
 * la v1; en F2 se mueve a almacenamiento NVM3 y se escribe por el clúster de
 * fabricante o por UART. NO compilado en el PC de desarrollo (sin SDK). */
extern "C" {
#include "app.h"
int rf_radar_start(const rf_room_t * room, const rf_box_t * zones, int n_zones);
}

#include <lib/support/logging/CHIPLogging.h>

namespace {
const rf_room_t kRoom = {
    2.6f,                           // altura de montaje (m)
    -2.0f, 2.0f, -2.0f, 2.0f,       // límites de la sala (m)
    { { 1.6f, 2.0f, -0.5f, 0.5f } }, // puerta
    1,
    {},
    0,
};
const rf_box_t kZones[] = { { -2.0f, -0.8f, 0.6f, 2.0f } }; // p. ej. la cama
} // namespace

void RadarInit()
{
    const int r = rf_radar_start(&kRoom, kZones, 1);
    if (r != 0)
    {
        // Fallo seguro: sin radar el dispositivo se anuncia «incierto» (EP6) y no
        // informa de una sala vacía que no ha medido.
        ChipLogError(AppServer, "radar60: el radar no arranca (%d)", r);
    }
}
