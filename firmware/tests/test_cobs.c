/* Codifica con COBS el fichero argv[1] en bloques de argv[3] bytes y escribe el
 * flujo en argv[2]. La prueba Python lo decodifica con tools/diag_reader.py. */
#include <stdio.h>
#include <stdlib.h>

#include "../src/cobs.h"

int main(int argc, char **argv)
{
    if (argc != 4) {
        return 2;
    }
    const size_t blk = (size_t)atoi(argv[3]);
    FILE *f = fopen(argv[1], "rb"), *o = fopen(argv[2], "wb");
    if (!f || !o || blk == 0 || blk > 4096) {
        return 2;
    }
    static uint8_t in[4096], out[4096 + 4096 / 254 + 2];
    size_t n;
    while ((n = fread(in, 1, blk, f)) > 0) {
        fwrite(out, 1, rf_cobs_encode(in, n, out), o);
    }
    fclose(f);
    fclose(o);
    return 0;
}
