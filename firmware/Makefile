# Pruebas en PC del código portable (no necesita la placa).
CC ?= gcc
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Werror -Iinclude -Isrc
SRC = src/features_pack.c src/decision.c

.PHONY: test clean
test: build/test_host
	./build/test_host

build/test_host: tests/test_host.c $(SRC) include/features_v1.h tests/golden_v1.h tests/decision_vectors.h
	mkdir -p build
	$(CC) $(CFLAGS) -o $@ tests/test_host.c $(SRC) -lm

clean:
	rm -rf build
