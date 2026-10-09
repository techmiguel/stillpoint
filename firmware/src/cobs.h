/* COBS (Consistent Overhead Byte Stuffing) framing for UART records.
 * out needs n + n/254 + 2 bytes; the 0x00 delimiter is appended. */
#pragma once
#include <stddef.h>
#include <stdint.h>

size_t rf_cobs_encode(const uint8_t *in, size_t n, uint8_t *out);

/* Decodes a COBS frame without the trailing 0x00. Returns the bytes written to
 * out (at most n - 1) or -1 if the frame is malformed or does not fit in cap. */
int rf_cobs_decode(const uint8_t *in, size_t n, uint8_t *out, size_t cap);
