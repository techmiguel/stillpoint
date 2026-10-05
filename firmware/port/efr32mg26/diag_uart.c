/* Flujo de diagnóstico: cada registro de 66 B del contrato sale por UART
 * (CP2102N -> USB) enmarcado con COBS y un 0x00 final, para capturar datos con
 * la placa propia (fases F2-F4). Lo decodifica tools/diag_reader.py.
 * NO compilado en el PC de desarrollo (sin SDK); cobs.c sí está probado. */
#include <stdint.h>

#include "cobs.h"
#include "features_v1.h"
#include "sl_iostream.h"

void rf_diag_record(const uint8_t *rec, void *ctx)
{
    (void)ctx;
    uint8_t buf[RF_RECORD_SIZE + RF_RECORD_SIZE / 254 + 2];
    const size_t n = rf_cobs_encode(rec, RF_RECORD_SIZE, buf);
    sl_iostream_write(SL_IOSTREAM_STDOUT, buf, n);
}
