/* COBS (Consistent Overhead Byte Stuffing) para enmarcar registros en UART.
 * out debe tener n + n/254 + 2 bytes; se añade el 0x00 delimitador. */
#pragma once
#include <stddef.h>
#include <stdint.h>

size_t rf_cobs_encode(const uint8_t *in, size_t n, uint8_t *out);

/* Decodifica una trama COBS sin el 0x00 final. Devuelve los bytes escritos en
 * out (como mucho n - 1) o -1 si la trama está mal formada o no cabe en cap. */
int rf_cobs_decode(const uint8_t *in, size_t n, uint8_t *out, size_t cap);
