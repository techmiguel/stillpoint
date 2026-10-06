#include "cobs.h"

size_t rf_cobs_encode(const uint8_t *in, size_t n, uint8_t *out)
{
    size_t w = 1, code_pos = 0;
    uint8_t code = 1;
    for (size_t r = 0; r < n; r++) {
        if (in[r] == 0) {
            out[code_pos] = code;
            code = 1;
            code_pos = w++;
        } else {
            out[w++] = in[r];
            if (++code == 0xFF) {
                out[code_pos] = code;
                code = 1;
                code_pos = w++;
            }
        }
    }
    out[code_pos] = code;
    out[w++] = 0x00;
    return w;
}

int rf_cobs_decode(const uint8_t *in, size_t n, uint8_t *out, size_t cap)
{
    size_t r = 0, w = 0;
    while (r < n) {
        const uint8_t code = in[r];
        if (code == 0 || r + code > n) {
            return -1;
        }
        for (size_t k = 1; k < code; k++) {
            if (in[r + k] == 0 || w >= cap) {
                return -1;
            }
            out[w++] = in[r + k];
        }
        r += code;
        if (code < 0xFF && r < n) {
            if (w >= cap) {
                return -1;
            }
            out[w++] = 0;
        }
    }
    return (int)w;
}
