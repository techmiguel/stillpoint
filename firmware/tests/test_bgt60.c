/* test_bgt60 fifo.bin out.bin            interleaved uint16 FIFO -> int16 frame
 * test_bgt60 -p packed.bin out.bin       12-bit packed bytes -> uint16
 * The Python test checks both against capture_kit.to_signed and its own packing. */
#include <stdio.h>
#include <string.h>

#include "../src/bgt60_frame.h"

int main(int argc, char **argv)
{
    static uint16_t fifo[RF_FIFO_SAMPLES];
    static int16_t adc[RF_FIFO_SAMPLES];
    static uint8_t packed[RF_FIFO_SAMPLES * 3 / 2];
    if (argc == 4 && !strcmp(argv[1], "-p")) {
        FILE *f = fopen(argv[2], "rb");
        if (!f || fread(packed, sizeof(packed), 1, f) != 1) {
            return 2;
        }
        fclose(f);
        rf_bgt60_unpack12(packed, fifo, RF_FIFO_SAMPLES);
        FILE *o = fopen(argv[3], "wb");
        if (!o || fwrite(fifo, sizeof(fifo), 1, o) != 1) {
            return 2;
        }
        fclose(o);
        return 0;
    }
    if (argc != 3) {
        return 2;
    }
    FILE *f = fopen(argv[1], "rb");
    if (!f || fread(fifo, sizeof(fifo), 1, f) != 1) {
        return 2;
    }
    fclose(f);
    rf_bgt60_unpack(fifo, adc);
    FILE *o = fopen(argv[2], "wb");
    if (!o || fwrite(adc, sizeof(adc), 1, o) != 1) {
        return 2;
    }
    fclose(o);
    return 0;
}
