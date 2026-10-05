# Pruebas en PC del código portable (no necesita la placa).
# En Windows sin gcc: `pip install ziglang` y `make CC="python -m ziglang cc"`,
# o directamente `python tools/build_host.py`.
CC ?= gcc
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Werror -Iinclude -Isrc
CORE = src/features_pack.c src/decision.c
DSP = src/rf_fft.c src/dsp.c src/tracker.c src/nn.c src/app.c

.PHONY: test replay clean
test: build/test_host
	./build/test_host

build/test_host: tests/test_host.c $(CORE) include/features_v1.h tests/golden_v1.h tests/decision_vectors.h
	mkdir -p build
	$(CC) $(CFLAGS) -o $@ tests/test_host.c $(CORE) -lm

replay: build/replay

build/replay: tests/replay.c $(CORE) $(DSP)
	mkdir -p build
	$(CC) $(CFLAGS) -o $@ tests/replay.c $(CORE) $(DSP) -lm

clean:
	rm -rf build
