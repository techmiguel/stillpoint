/* Traduce rf_outputs_t a atributos Matter (docs/04_matter.md).
 * Base: ejemplo «Matter - SoC Occupancy Sensor» de la extensión Matter de
 * Silicon Labs, con los endpoints añadidos en ZAP según docs/04.
 * NO compilado en el PC de desarrollo (sin SDK). */
#include <app-common/zap-generated/attributes/Accessors.h>
#include <app/clusters/occupancy-sensor-server/occupancy-sensor-server.h>
#include <platform/CHIPDeviceLayer.h>

#include <atomic>
#include <cstring>

extern "C" {
#include "app.h"
}

using namespace chip;
using namespace chip::app::Clusters;

namespace {
constexpr EndpointId kEpRoom = 1;
constexpr EndpointId kEpZone0 = 2;    // 2..4
constexpr EndpointId kEpFall = 5;
constexpr EndpointId kEpUncertain = 6;

rf_outputs_t sPending;    // escrito por la tarea de radar antes de ScheduleWork
rf_outputs_t sPublished;  // solo en el hilo de Matter
rf_outputs_t sLastSent;   // solo en la tarea de radar
std::atomic<bool> sScheduled{false};
uint32_t sLastReportMs = 0;

void SetOccupancy(EndpointId ep, bool on)
{
    OccupancySensing::Attributes::Occupancy::Set(ep, on ? OccupancySensing::OccupancyBitmap::kOccupied
                                                        : static_cast<OccupancySensing::OccupancyBitmap>(0));
}

void Publish(intptr_t)
{
    sScheduled = false;
    const rf_outputs_t o = sPending;   // copia tomada en el hilo de Matter
    if (o.occupied != sPublished.occupied) {
        SetOccupancy(kEpRoom, o.occupied);
    }
    for (int z = 0; z < RF_APP_MAX_ZONES; z++) {
        if (o.zone_occupied[z] != sPublished.zone_occupied[z]) {
            SetOccupancy(static_cast<EndpointId>(kEpZone0 + z), o.zone_occupied[z]);
        }
    }
    // Caída confirmada O incierta: una posible caída no verificable se notifica.
    if (o.fall_alarm != sPublished.fall_alarm) {
        BooleanState::Attributes::StateValue::Set(kEpFall, o.fall_alarm);
    }
    if (o.uncertain != sPublished.uncertain) {
        BooleanState::Attributes::StateValue::Set(kEpUncertain, o.uncertain);
    }
    // Clúster de fabricante (radar60_cluster.xml): recuento y estado de caída detallado.
    // Se escriben con los accesores que genera ZAP para el clúster 0xFFF1FC01.
    sPublished = o;
}
} // namespace

extern "C" void rf_matter_publish(const rf_outputs_t * out)
{
    // Se llama desde la tarea de radar a 10 Hz. Solo se programa trabajo en el
    // hilo de Matter si algo publicable cambió, y como mucho 2 veces por segundo
    // salvo una alarma de caída, que sale de inmediato.
    const uint32_t now = static_cast<uint32_t>(chip::System::SystemClock().GetMonotonicMilliseconds64().count());
    // Se compara con lo último enviado desde esta tarea, sin leer el estado del
    // hilo de Matter. Un cambio frenado por el límite se reintenta en la trama siguiente.
    const bool changed = out->occupied != sLastSent.occupied || out->fall_alarm != sLastSent.fall_alarm ||
        out->uncertain != sLastSent.uncertain ||
        std::memcmp(out->zone_occupied, sLastSent.zone_occupied, sizeof(out->zone_occupied)) != 0;
    const bool urgent = out->fall_alarm && !sLastSent.fall_alarm;
    if (!changed || (!urgent && now - sLastReportMs < 500) || sScheduled.exchange(true)) {
        return;
    }
    sLastReportMs = now;
    sPending = *out;
    sLastSent = *out;
    DeviceLayer::PlatformMgr().ScheduleWork(Publish, 0);
}
