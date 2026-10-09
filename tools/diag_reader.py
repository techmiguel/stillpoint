"""Reads the firmware diagnostic stream (COBS-framed contract records) from a
serial port or a file and writes it as CSV.

  python tools/diag_reader.py COM7 out.csv          (needs pyserial)
  python tools/diag_reader.py capture.bin out.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

from radarref import contract as ct  # noqa: E402


def cobs_decode(frame: bytes) -> bytes:
    out, i = bytearray(), 0
    while i < len(frame):
        code = frame[i]
        if code == 0:
            raise ValueError("zero inside a COBS frame")
        out += frame[i + 1:i + code]
        i += code
        if code < 0xFF and i < len(frame):
            out.append(0)
    return bytes(out)


def frames(stream):
    """Splits a byte stream into frames at the 0x00 delimiter."""
    buf = bytearray()
    for chunk in stream:
        for b in chunk:
            if b == 0:
                if buf:
                    yield bytes(buf)
                buf.clear()
            else:
                buf.append(b)


def records(stream, c=None):
    c = c or ct.load()
    bad = 0
    for fr in frames(stream):
        try:
            yield ct.unpack(c, cobs_decode(fr))
        except (ValueError, ct.RecordError):
            bad += 1        # corrupt frame: dropped (the CRC catches it)
    if bad:
        print(f"warning: {bad} frames dropped", file=sys.stderr)


def main(src: str, dst: str):
    c = ct.load()
    if Path(src).exists():
        data = Path(src).read_bytes()
        stream = [data]
    else:
        import serial
        port = serial.Serial(src, 3_000_000, timeout=1)
        stream = iter(lambda: port.read(4096), b"")
    with open(dst, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["frame_id", "t_ms", "track_id", "state"] + list(c.names))
        n = 0
        for r in records(stream, c):
            w.writerow([r["frame_id"], r["t_ms"], r["track_id"], r["flags"]] + [f"{v:g}" for v in r["values"]])
            n += 1
    print(f"{n} records -> {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
