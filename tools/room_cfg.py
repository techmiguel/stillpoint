"""Configuración de la sala para el firmware (formato v1 de firmware/src/room_cfg.h).

Genera el bloque binario desde un JSON y lo envía por la UART de diagnóstico
(o lo guarda en un fichero). El dispositivo lo valida, lo guarda en NVM3 y
reinicia el seguimiento con la nueva geometría; responde con una trama de
confirmación (0xA5, comando, estado).

  python tools/room_cfg.py tools/sala_ejemplo.json --salida trama.bin
  python tools/room_cfg.py sala.json --puerto COM7          (requiere pyserial)

JSON (metros, ejes del sensor; ver docs/04_matter.md):
  {"altura_montaje": 2.6, "sala": [x_min, x_max, y_min, y_max],
   "puertas": [[x0, x1, y0, y1], ...], "exclusiones": [...], "zonas": [...]}
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "tools"))

from radarref.contract import crc16_ccitt  # noqa: E402

MAGIC = b"R6RC"
VERSION = 1
MAX_BOXES, MAX_ZONES = 8, 3          # RF_MAX_ZONES, RF_APP_MAX_ZONES
CMD_SET_ROOM = 0x01
ACK = 0xA5


class ConfigError(ValueError):
    pass


def _mm(v: float) -> int:
    return int(round(v * 1000.0))


def _box_ok(b) -> bool:
    x0, x1, y0, y1 = b
    return x0 < x1 and y0 < y1 and all(abs(v) <= 10.0 for v in b)


def validate(cfg: dict) -> None:
    if not 1.8 <= cfg["altura_montaje"] <= 4.0:
        raise ConfigError("altura de montaje fuera de 1,8-4 m")
    if not _box_ok(cfg["sala"]):
        raise ConfigError("límites de la sala incoherentes o fuera de ±10 m")
    for key, n in (("puertas", MAX_BOXES), ("exclusiones", MAX_BOXES), ("zonas", MAX_ZONES)):
        boxes = cfg.get(key, [])
        if len(boxes) > n:
            raise ConfigError(f"como mucho {n} {key}")
        for b in boxes:
            if not _box_ok(b):
                raise ConfigError(f"caja de {key} incoherente: {b}")


def pack(cfg: dict) -> bytes:
    validate(cfg)
    boxes = [b for k in ("puertas", "exclusiones", "zonas") for b in cfg.get(k, [])]
    body = MAGIC + struct.pack("<BB5hBBBB", VERSION, 0, _mm(cfg["altura_montaje"]),
                               *(_mm(v) for v in cfg["sala"]), len(cfg.get("puertas", [])),
                               len(cfg.get("exclusiones", [])), len(cfg.get("zonas", [])), 0)
    for b in boxes:
        body += struct.pack("<4h", *(_mm(v) for v in b))
    return body + struct.pack("<H", crc16_ccitt(body))


def unpack(blob: bytes) -> dict:
    if len(blob) < 22 or blob[:4] != MAGIC or blob[4] != VERSION:
        raise ConfigError("no es una configuración v1")
    h, x0, x1, y0, y1, ne, nx, nz = struct.unpack_from("<5hBBB", blob, 6)
    if len(blob) != 20 + 8 * (ne + nx + nz) + 2:
        raise ConfigError("longitud incoherente")
    if crc16_ccitt(blob[:-2]) != struct.unpack_from("<H", blob, len(blob) - 2)[0]:
        raise ConfigError("CRC incorrecto")
    boxes = [[v / 1000.0 for v in struct.unpack_from("<4h", blob, 20 + 8 * i)] for i in range(ne + nx + nz)]
    cfg = {"altura_montaje": h / 1000.0, "sala": [x0 / 1000.0, x1 / 1000.0, y0 / 1000.0, y1 / 1000.0],
           "puertas": boxes[:ne], "exclusiones": boxes[ne:ne + nx], "zonas": boxes[ne + nx:]}
    validate(cfg)
    return cfg


def cobs_encode(data: bytes) -> bytes:
    out, block = bytearray(), bytearray()
    for b in data:
        if b == 0:
            out += bytes([len(block) + 1]) + block
            block.clear()
        else:
            block.append(b)
            if len(block) == 254:
                out += bytes([255]) + block
                block.clear()
    out += bytes([len(block) + 1]) + block
    return bytes(out) + b"\x00"


def command(cfg: dict) -> bytes:
    """Trama lista para la UART: COBS(comando + bloque) + 0x00."""
    return cobs_encode(bytes([CMD_SET_ROOM]) + pack(cfg))


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("json")
    ap.add_argument("--salida")
    ap.add_argument("--puerto")
    a = ap.parse_args(argv)
    cfg = json.loads(Path(a.json).read_text(encoding="utf-8"))
    frame = command(cfg)
    if a.salida:
        Path(a.salida).write_bytes(frame)
        print(f"{len(frame)} bytes en {a.salida}")
    if a.puerto:
        import serial  # pyserial
        from diag_reader import cobs_decode, frames
        with serial.Serial(a.puerto, 3_000_000, timeout=2) as s:
            s.write(frame)
            buf = s.read(4096)
        for fr in frames([buf]):
            msg = cobs_decode(fr)
            if len(msg) == 3 and msg[0] == ACK and msg[1] == CMD_SET_ROOM:
                st = struct.unpack("b", msg[2:3])[0]
                print("configuración aceptada" if st == 0 else f"rechazada por el dispositivo (código {st})")
                return 0 if st == 0 else 1
        print("sin confirmación del dispositivo", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
