/* Enlace de diagnóstico por UART (CP2102N -> USB), tramas COBS terminadas en 0x00.
 *   Salida: cada registro de 66 B del contrato (tools/diag_reader.py) y las
 *           confirmaciones de comandos (0xA5, comando, estado).
 *   Entrada: comandos de tools/room_cfg.py; hoy solo 0x01 = configuración de sala.
 * NO compilado en el PC de desarrollo (sin SDK); cobs.c y room_cfg.c sí están probados. */
#include <stdint.h>

#include "cfg_store.h"
#include "cobs.h"
#include "features_v1.h"
#include "sl_iostream.h"

#define CMD_SET_ROOM 0x01u
#define ACK 0xA5u

/* Lo implementa radar_port.c: aplica la nueva geometría en la siguiente trama. */
extern void rf_radar_request_reconfig(void);

static void send_frame(const uint8_t *msg, size_t n)
{
    uint8_t buf[RF_RECORD_SIZE + RF_RECORD_SIZE / 254 + 2];
    if (n > RF_RECORD_SIZE) {
        return;
    }
    sl_iostream_write(SL_IOSTREAM_STDOUT, buf, rf_cobs_encode(msg, n, buf));
}

void rf_diag_record(const uint8_t *rec, void *ctx)
{
    (void)ctx;
    send_frame(rec, RF_RECORD_SIZE);
}

static void dispatch(const uint8_t *msg, int n)
{
    int8_t st = -20;                    /* comando desconocido */
    if (n >= 1 && msg[0] == CMD_SET_ROOM) {
        st = (int8_t)rf_cfg_save(msg + 1, (size_t)n - 1);
        if (st == 0) {
            rf_radar_request_reconfig();
        }
    }
    const uint8_t ack[3] = {ACK, n >= 1 ? msg[0] : 0, (uint8_t)st};
    send_frame(ack, sizeof(ack));
}

/* Se llama desde la tarea del radar en cada trama (100 ms): lee sin bloquear. */
void rf_diag_poll(void)
{
    static uint8_t frame[RF_ROOM_CFG_MAX_SIZE + 8];
    static size_t n;
    static int overflow;
    uint8_t in[64];
    size_t got = 0;
    if (sl_iostream_read(SL_IOSTREAM_STDIN, in, sizeof(in), &got) != SL_STATUS_OK) {
        return;
    }
    for (size_t i = 0; i < got; i++) {
        if (in[i] != 0) {
            if (n < sizeof(frame)) {
                frame[n++] = in[i];
            } else {
                overflow = 1;
            }
            continue;
        }
        if (n && !overflow) {
            uint8_t msg[sizeof(frame)];
            const int m = rf_cobs_decode(frame, n, msg, sizeof(msg));
            if (m > 0) {
                dispatch(msg, m);
            }
        }
        n = 0;
        overflow = 0;
    }
}
