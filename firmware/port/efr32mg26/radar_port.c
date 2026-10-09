/* EFR32MG26 port: platform hooks for the official Infineon driver
 * (sensor-xensiv-bgt60trxx, Apache-2.0) and the radar task.
 *
 * Needs Simplicity SDK + Matter extension (FreeRTOS), components:
 *   spidrv (instance "radar"), gpiointerrupt, sleeptimer, emlib_gpio.
 * NOT built on the development PC (no SDK). The portable code it uses (dsp,
 * tracker, nn, decision, app, bgt60_frame) is tested against Python.
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
#include "radar_settings.h"          /* exported from Infineon Radar Fusion GUI (see README) */
#include "radar_settings_check.h"    /* build fails if it does not match RF_RADAR_CFG_V1 */
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

/* Implemented in matter_bridge.cpp: publishes the outputs on the Matter thread. */
extern void rf_matter_publish(const rf_outputs_t *out);
/* Implemented in diag_uart.c: contract records over UART/USB (capture)
 * and configuration commands (tools/room_cfg.py). */
extern void rf_diag_record(const uint8_t *rec, void *ctx);
extern void rf_diag_poll(void);

static volatile bool s_reconfig;

/* From diag_uart.c, after a new configuration is stored in NVM3. */
void rf_radar_request_reconfig(void) { s_reconfig = true; }

/* Restarts the application with the stored geometry (live tracks are dropped). */
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

/* ---- driver platform hooks ------------------------------------------------- */
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
    /* the FIFO is packed in 12 bits: read bytes (DMA) and unpack */
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

/* ---- FIFO-full interrupt --------------------------------------------------- */
static void radar_irq(uint8_t int_no)
{
    (void)int_no;
    BaseType_t woken = pdFALSE;
    xSemaphoreGiveFromISR(s_irq_sem, &woken);
    portYIELD_FROM_ISR(woken);
}

/* ---- task --------------------------------------------------------------- */
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
            /* no frames: fail safe, publish "uncertain" and restart the radar */
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
    /* Start-up (rev A schematic): translators disabled, power the radar,
     * wait for the LDO and the XO (start-up <= 5 ms) to settle, drive
     * CS_N and DIO3 high and only then enable the translators. */
    GPIO_PinModeSet(RADAR_OE_N_PORT, RADAR_OE_N_PIN, gpioModePushPull, 1);
    GPIO_PinModeSet(RADAR_PWR_EN_PORT, RADAR_PWR_EN_PIN, gpioModePushPull, 1);
    sl_sleeptimer_delay_millisecond(10);
    GPIO_PinModeSet(RADAR_CS_PORT, RADAR_CS_PIN, gpioModePushPull, 1);
    GPIO_PinModeSet(RADAR_RST_PORT, RADAR_RST_PIN, gpioModePushPull, 1);
    GPIO_PinModeSet(RADAR_IRQ_PORT, RADAR_IRQ_PIN, gpioModeInput, 0);
    GPIO_PinOutClear(RADAR_OE_N_PORT, RADAR_OE_N_PIN);

    /* the EU check runs before the radar is touched: if it fails, nothing is transmitted */
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
