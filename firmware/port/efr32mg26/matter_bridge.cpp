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
#include "features_v1.h"
#include "nn.h"
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
    static bool sStaticDone = false;
    if (!sStaticDone) {
        // Identidad del firmware: versión del contrato de características y modelo embebido.
        Radar60Presence::Attributes::ContractVersion::Set(kEpRoom, RF_CONTRACT_VERSION);
        Radar60Presence::Attributes::ModelHash::Set(kEpRoom, rf_nn_model_hash());
        sStaticDone = true;
    }
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
    // Clúster de fabricante (radar60_cluster.xml) en EP1: recuento y estado de
    // caída detallado. Accesores que genera ZAP para el clúster 0xFFF1FC01.
    if (o.count != sPublished.count) {
        Radar60Presence::Attributes::PersonCount::Set(kEpRoom, o.count);
    }
    if (o.worst_fall != sPublished.worst_fall) {
        Radar60Presence::Attributes::FallState::Set(kEpRoom, static_cast<uint8_t>(o.worst_fall));
    }
    if (o.uncertain != sPublished.uncertain) {
        Radar60Presence::Attributes::Uncertain::Set(kEpRoom, o.uncertain);
    }
    if (o.n_proposed_exclusions != sPublished.n_proposed_exclusions) {
        Radar60Presence::Attributes::ProposedExclusions::Set(kEpRoom, o.n_proposed_exclusions);
    }
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
        out->uncertain != sLastSent.uncertain || out->count != sLastSent.count ||
        out->worst_fall != sLastSent.worst_fall || out->n_proposed_exclusions != sLastSent.n_proposed_exclusions ||
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
