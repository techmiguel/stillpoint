"""ADC frame file (.rfad) shared by the Python reference, the C replayer
(firmware/tests/replay.c) and the kit capture tool."""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

from .config import Room


def write(path: str | Path, room: Room, frames) -> int:
    """frames: iterable of (3, 32, 128) arrays in ±1 scale (like Simulator.frame)."""
    frames = list(frames)
    with open(path, "wb") as f:
        f.write(b"RFAD" + struct.pack("<II", 1, len(frames)))
        f.write(struct.pack("<5f", room.mount_h, room.x_min, room.x_max, room.y_min, room.y_max))
        for boxes in (room.exits, room.exclusions):
            f.write(struct.pack("<I", len(boxes)))
            for b in boxes:
                f.write(struct.pack("<4f", *b))
        for fr in frames:
            f.write(np.round(np.asarray(fr) * 2047).astype("<i2").tobytes())
    return len(frames)


def read(path: str | Path):
    """Returns (Room, generator of frames in ±1 scale)."""
    data = Path(path).read_bytes()
    if data[:4] != b"RFAD":
        raise ValueError("not an RFAD file")
    ver, n = struct.unpack_from("<II", data, 4)
    if ver != 1:
        raise ValueError(f"unsupported version {ver}")
    off = 12
    h, x0, x1, y0, y1 = struct.unpack_from("<5f", data, off)
    off += 20
    boxes = []
    for _ in range(2):
        (k,) = struct.unpack_from("<I", data, off)
        off += 4
        boxes.append([tuple(struct.unpack_from("<4f", data, off + 16 * i)) for i in range(k)])
        off += 16 * k
    room = Room(mount_h=h, x_min=x0, x_max=x1, y_min=y0, y_max=y1, exits=boxes[0], exclusions=boxes[1])
    size = 3 * 32 * 128 * 2

    def frames():
        for i in range(n):
            a = np.frombuffer(data, "<i2", 3 * 32 * 128, off + i * size).reshape(3, 32, 128)
            yield a.astype(np.float64) / 2047
    return room, frames()
