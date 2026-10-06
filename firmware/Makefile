# Pruebas en PC del código portable (no necesita la placa).
# En Windows sin gcc: `pip install ziglang` y `make CC="python -m ziglang cc"`,
# o directamente `python tools/build_host.py`.
CC ?= gcc
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Werror -Iinclude -Isrc
CORE = src/features_pack.c src/decision.c
DSP = src/rf_fft.c src/dsp.c src/tracker.c src/nn.c src/app.c

.PHONY: test all replay clean
# `test` compila además todo el código portable con -Werror (DSP, app, FIFO,
# COBS): los programas que necesitan datos de Python se ejecutan desde ml/tests.
test: all
	./build/test_host
	./build/test_nn
	./build/test_room_cfg

all: build/test_host build/test_nn build/replay build/replay_app build/test_bgt60 build/test_cobs build/test_room_cfg

build/test_host: tests/test_host.c $(CORE) include/features_v1.h tests/golden_v1.h tests/decision_vectors.h
	mkdir -p build
	$(CC) $(CFLAGS) -o $@ tests/test_host.c $(CORE) -lm

replay: build/replay

build/test_nn: tests/test_nn.c src/nn.c src/nn.h src/model_data.h tests/nn_vectors.h
	mkdir -p build
	$(CC) $(CFLAGS) -o $@ tests/test_nn.c src/nn.c -lm

build/replay_app: tests/replay_app.c $(CORE) $(DSP)
	mkdir -p build
	$(CC) $(CFLAGS) -o $@ tests/replay_app.c $(CORE) $(DSP) -lm

build/test_bgt60: tests/test_bgt60.c src/bgt60_frame.c
	mkdir -p build
	$(CC) $(CFLAGS) -o $@ tests/test_bgt60.c src/bgt60_frame.c -lm

build/test_room_cfg: tests/test_room_cfg.c src/room_cfg.c src/room_cfg.h src/features_pack.c src/cobs.c
	mkdir -p build
	$(CC) $(CFLAGS) -o $@ tests/test_room_cfg.c src/room_cfg.c src/features_pack.c src/cobs.c -lm

build/test_cobs: tests/test_cobs.c src/cobs.c
	mkdir -p build
	$(CC) $(CFLAGS) -o $@ tests/test_cobs.c src/cobs.c -lm

build/replay: tests/replay.c $(CORE) $(DSP)
	mkdir -p build
	$(CC) $(CFLAGS) -o $@ tests/replay.c $(CORE) $(DSP) -lm

clean:
	rm -rf build
