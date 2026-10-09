"""Room configuration for the firmware (v1 layout of firmware/src/room_cfg.h).

Builds the binary block from a JSON file and sends it over the diagnostic UART
(or writes it to a file). The device validates it, stores it in NVM3 and
restarts tracking with the new geometry; it answers with an acknowledgement
frame (0xA5, command, status).

  python tools/room_cfg.py tools/room_example.json --out frame.bin
  python tools/room_cfg.py room.json --port COM7          (needs pyserial)

JSON (metres, sensor axes; see docs/matter.md):
  {"mount_height": 2.6, "room": [x_min, x_max, y_min, y_max],
   "exits": [[x0, x1, y0, y1], ...], "exclusions": [...], "zones": [...]}
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
    if not 1.8 <= cfg["mount_height"] <= 4.0:
        raise ConfigError("mount height outside 1.8-4 m")
    if not _box_ok(cfg["room"]):
        raise ConfigError("room limits inconsistent or outside ±10 m")
    for key, n in (("exits", MAX_BOXES), ("exclusions", MAX_BOXES), ("zones", MAX_ZONES)):
        boxes = cfg.get(key, [])
        if len(boxes) > n:
            raise ConfigError(f"at most {n} {key}")
        for b in boxes:
            if not _box_ok(b):
                raise ConfigError(f"inconsistent {key} box: {b}")


def pack(cfg: dict) -> bytes:
    validate(cfg)
    boxes = [b for k in ("exits", "exclusions", "zones") for b in cfg.get(k, [])]
    body = MAGIC + struct.pack("<BB5hBBBB", VERSION, 0, _mm(cfg["mount_height"]),
                               *(_mm(v) for v in cfg["room"]), len(cfg.get("exits", [])),
                               len(cfg.get("exclusions", [])), len(cfg.get("zones", [])), 0)
    for b in boxes:
        body += struct.pack("<4h", *(_mm(v) for v in b))
    return body + struct.pack("<H", crc16_ccitt(body))


def unpack(blob: bytes) -> dict:
    if len(blob) < 22 or blob[:4] != MAGIC or blob[4] != VERSION:
        raise ConfigError("not a v1 configuration")
    h, x0, x1, y0, y1, ne, nx, nz = struct.unpack_from("<5hBBB", blob, 6)
    if len(blob) != 20 + 8 * (ne + nx + nz) + 2:
        raise ConfigError("inconsistent length")
    if crc16_ccitt(blob[:-2]) != struct.unpack_from("<H", blob, len(blob) - 2)[0]:
        raise ConfigError("bad CRC")
    boxes = [[v / 1000.0 for v in struct.unpack_from("<4h", blob, 20 + 8 * i)] for i in range(ne + nx + nz)]
    cfg = {"mount_height": h / 1000.0, "room": [x0 / 1000.0, x1 / 1000.0, y0 / 1000.0, y1 / 1000.0],
           "exits": boxes[:ne], "exclusions": boxes[ne:ne + nx], "zones": boxes[ne + nx:]}
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
    """Frame ready for the UART: COBS(command + block) + 0x00."""
    return cobs_encode(bytes([CMD_SET_ROOM]) + pack(cfg))


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("json")
    ap.add_argument("--out")
    ap.add_argument("--port")
    a = ap.parse_args(argv)
    cfg = json.loads(Path(a.json).read_text(encoding="utf-8"))
    frame = command(cfg)
    if a.out:
        Path(a.out).write_bytes(frame)
        print(f"{len(frame)} bytes -> {a.out}")
    if a.port:
        import serial  # pyserial
        from diag_reader import cobs_decode, frames
        with serial.Serial(a.port, 3_000_000, timeout=2) as s:
            s.write(frame)
            buf = s.read(4096)
        for fr in frames([buf]):
            msg = cobs_decode(fr)
            if len(msg) == 3 and msg[0] == ACK and msg[1] == CMD_SET_ROOM:
                st = struct.unpack("b", msg[2:3])[0]
                print("configuration accepted" if st == 0 else f"rejected by the device (code {st})")
                return 0 if st == 0 else 1
        print("no acknowledgement from the device", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
