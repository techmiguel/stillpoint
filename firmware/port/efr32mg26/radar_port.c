/* Puerto EFR32MG26: ganchos de plataforma del driver oficial de Infineon
 * (sensor-xensiv-bgt60trxx, Apache-2.0) y tarea de radar.
 *
 * Requiere Simplicity SDK + extensión Matter (FreeRTOS), componentes:
 *   spidrv (instancia "radar"), gpiointerrupt, sleeptimer, emlib_gpio.
 * NO compilado en el PC de desarrollo (sin SDK). Lo portable que usa (dsp,
 * tracker, nn, decision, app, bgt60_frame) está probado contra Python.
 */
#include <stdbool.h>
#include <string.h>

#include "FreeRTOS.h"
#include "em_gpio.h"
#include "gpiointerrupt.h"
#include "semphr.h"
#include "sl_sleeptimer.h"
#include "spidrv.h"
#include "task.h"

#include "app.h"
#include "bgt60_frame.h"
#include "cfg_store.h"
#include "radar_pins.h"
#include "radar_settings.h"          /* exportado desde Infineon Radar Fusion GUI (ver README) */
#include "radar_settings_check.h"    /* falla la compilación si no coincide con RF_RADAR_CFG_V1 */
#include "xensiv_bgt60trxx.h"
#include "xensiv_bgt60trxx_platform.h"

extern SPIDRV_Handle_t sl_spidrv_radar_handle;

typedef struct {
    SPIDRV_Handle_t spi;
} rf_iface_t;

static rf_iface_t s_iface;
static xensiv_bgt60trxx_t s_dev;
static SemaphoreHandle_t s_irq_sem;
static uint8_t s_packed[RF_FIFO_SAMPLES * 3 / 2];
static uint16_t s_fifo[RF_FIFO_SAMPLES];
static int16_t s_adc[RF_FIFO_SAMPLES];
static rf_app_t s_app;
static rf_outputs_t s_out;

/* Lo implementa matter_bridge.cpp: publica las salidas en el hilo de Matter. */
extern void rf_matter_publish(const rf_outputs_t *out);
/* Lo implementa diag_uart.c: registros del contrato por UART/USB (captura en F2-F4)
 * y comandos de configuración (tools/room_cfg.py). */
extern void rf_diag_record(const uint8_t *rec, void *ctx);
extern void rf_diag_poll(void);

static volatile bool s_reconfig;

/* Desde diag_uart.c, tras guardar una configuración nueva en NVM3. */
void rf_radar_request_reconfig(void) { s_reconfig = true; }

/* Reinicia la aplicación con la geometría guardada (se pierden las pistas en curso). */
static void reconfigure(void)
{
    rf_room_t room;
    rf_box_t zones[RF_APP_MAX_ZONES];
    int nz;
    rf_cfg_load(&room, zones, &nz);
    if (rf_app_init(&s_app, &RF_RADAR_CFG_V1, &room, zones, nz) == 0) {
        rf_app_set_record_cb(&s_app, rf_diag_record, NULL);
    }
}

/* ---- ganchos de plataforma del driver -------------------------------------- */
void xensiv_bgt60trxx_platform_rst_set(const void *iface, bool val)
{
    (void)iface;
    val ? GPIO_PinOutSet(RADAR_RST_PORT, RADAR_RST_PIN) : GPIO_PinOutClear(RADAR_RST_PORT, RADAR_RST_PIN);
}

void xensiv_bgt60trxx_platform_spi_cs_set(const void *iface, bool val)
{
    (void)iface;
    val ? GPIO_PinOutSet(RADAR_CS_PORT, RADAR_CS_PIN) : GPIO_PinOutClear(RADAR_CS_PORT, RADAR_CS_PIN);
}

int32_t xensiv_bgt60trxx_platform_spi_transfer(void *iface, uint8_t *tx_data, uint8_t *rx_data, uint32_t len)
{
    rf_iface_t *it = iface;
    static uint8_t dummy[8];
    Ecode_t e;
    if (rx_data == NULL) {
        e = SPIDRV_MTransmitB(it->spi, tx_data, (int)len);
    } else {
        e = SPIDRV_MTransferB(it->spi, tx_data ? tx_data : dummy, rx_data, (int)len);
    }
    return e == ECODE_EMDRV_SPIDRV_OK ? XENSIV_BGT60TRXX_STATUS_OK : XENSIV_BGT60TRXX_STATUS_COM_ERROR;
}

int32_t xensiv_bgt60trxx_platform_spi_fifo_read(void *iface, uint16_t *rx_data, uint32_t len)
{
    /* el FIFO va empaquetado en 12 bits: se lee por bytes (DMA) y se desempaqueta */
    rf_iface_t *it = iface;
    const int nbytes = (int)(len * 3 / 2);
    if (SPIDRV_MReceiveB(it->spi, s_packed, nbytes) != ECODE_EMDRV_SPIDRV_OK) {
        return XENSIV_BGT60TRXX_STATUS_COM_ERROR;
    }
    rf_bgt60_unpack12(s_packed, rx_data, len);
    return XENSIV_BGT60TRXX_STATUS_OK;
}

void xensiv_bgt60trxx_platform_delay(uint32_t ms) { sl_sleeptimer_delay_millisecond((uint16_t)ms); }

uint32_t xensiv_bgt60trxx_platform_word_reverse(uint32_t x) { return __builtin_bswap32(x); }

void xensiv_bgt60trxx_platform_assert(bool expr)
{
    if (!expr) {
        __BKPT(0);
    }
}

/* ---- interrupción de FIFO lleno ------------------------------------------- */
static void radar_irq(uint8_t int_no)
{
    (void)int_no;
    BaseType_t woken = pdFALSE;
    xSemaphoreGiveFromISR(s_irq_sem, &woken);
    portYIELD_FROM_ISR(woken);
}

/* ---- tarea -------------------------------------------------------------- */
static void radar_task(void *arg)
{
    (void)arg;
    uint32_t t_ms = 0;
    for (;;) {
        rf_diag_poll();
        if (s_reconfig) {
            s_reconfig = false;
            reconfigure();
        }
        if (xSemaphoreTake(s_irq_sem, pdMS_TO_TICKS(500)) != pdTRUE) {
            /* sin tramas: fallo seguro, se publica «incierto» y se reinicia el radar */
            memset(&s_out, 0, sizeof(s_out));
            s_out.uncertain = true;
            rf_matter_publish(&s_out);
            xensiv_bgt60trxx_soft_reset(&s_dev, XENSIV_BGT60TRXX_RESET_FIFO);
            xensiv_bgt60trxx_start_frame(&s_dev, true);
            continue;
        }
        if (xensiv_bgt60trxx_get_fifo_data(&s_dev, s_fifo, RF_FIFO_SAMPLES) != XENSIV_BGT60TRXX_STATUS_OK) {
            continue;
        }
        rf_bgt60_unpack(s_fifo, s_adc);
        rf_app_frame(&s_app, s_adc, t_ms, &s_out);
        t_ms += 100;
        rf_matter_publish(&s_out);
    }
}

int rf_radar_start(const rf_room_t *room, const rf_box_t *zones, int n_zones)
{
    s_iface.spi = sl_spidrv_radar_handle;
    GPIO_PinModeSet(RADAR_CS_PORT, RADAR_CS_PIN, gpioModePushPull, 1);
    GPIO_PinModeSet(RADAR_RST_PORT, RADAR_RST_PIN, gpioModePushPull, 1);
    GPIO_PinModeSet(RADAR_IRQ_PORT, RADAR_IRQ_PIN, gpioModeInput, 0);

    /* la comprobación EU se hace antes de tocar el radar: si falla, no emite */
    if (rf_app_init(&s_app, &RF_RADAR_CFG_V1, room, zones, n_zones) != 0) {
        return -1;
    }
    rf_app_set_record_cb(&s_app, rf_diag_record, NULL);
    if (xensiv_bgt60trxx_init(&s_dev, &s_iface, false) != XENSIV_BGT60TRXX_STATUS_OK ||
        xensiv_bgt60trxx_config(&s_dev, register_list, XENSIV_BGT60TRXX_CONF_NUM_REGS) != XENSIV_BGT60TRXX_STATUS_OK ||
        xensiv_bgt60trxx_set_fifo_limit(&s_dev, RF_FIFO_SAMPLES) != XENSIV_BGT60TRXX_STATUS_OK) {
        return -2;
    }
    s_irq_sem = xSemaphoreCreateBinary();
    GPIOINT_Init();
    GPIOINT_CallbackRegister(RADAR_IRQ_PIN, radar_irq);
    GPIO_ExtIntConfig(RADAR_IRQ_PORT, RADAR_IRQ_PIN, RADAR_IRQ_PIN, true, false, true);
    if (xTaskCreate(radar_task, "radar", 2048, NULL, tskIDLE_PRIORITY + 3, NULL) != pdPASS) {
        return -3;
    }
    return xensiv_bgt60trxx_start_frame(&s_dev, true) == XENSIV_BGT60TRXX_STATUS_OK ? 0 : -4;
}
