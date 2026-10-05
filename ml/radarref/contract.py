"""Carga del contrato de características y (de)serialización de registros.

Es la implementación de referencia del registro binario definido en
contracts/features_v1.yaml. El firmware (firmware/src/features_pack.c) debe
producir los mismos bytes; tests/test_contract.py lo comprueba con vectores
dorados.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "features_v1.yaml"

_HEADER = struct.Struct("<HBBIIBBH")  # magic, ver, n, frame_id, t_ms, track, flags, hash16


@dataclass(frozen=True)
class Contract:
    version: int
    frame_rate_hz: float
    window_frames: int
    window_hop_frames: int
    names: tuple[str, ...]
    scales: np.ndarray
    magic: int
    hash32: int

    @property
    def n(self) -> int:
        return len(self.names)

    @property
    def hash16(self) -> int:
        return self.hash32 & 0xFFFF

    def index(self, name: str) -> int:
        return self.names.index(name)

    @property
    def record_size(self) -> int:
        return _HEADER.size + 2 * self.n + 2


def canonical_string(spec: dict) -> str:
    """Forma canónica: lo que define el significado de los bytes, nada más."""
    parts = [f"v={spec['version']}", f"fr={spec['frame_rate_hz']}",
             f"w={spec['window_frames']}", f"hop={spec['window_hop_frames']}"]
    for f in spec["fields"]:
        parts.append(f"{f['name']}|{f['unit']}|{f['scale']}")
    return ";".join(parts)


def load(path: Path = CONTRACT_PATH) -> Contract:
    spec = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    canon = canonical_string(spec).encode("utf-8")
    return Contract(
        version=int(spec["version"]),
        frame_rate_hz=float(spec["frame_rate_hz"]),
        window_frames=int(spec["window_frames"]),
        window_hop_frames=int(spec["window_hop_frames"]),
        names=tuple(f["name"] for f in spec["fields"]),
        scales=np.array([f["scale"] for f in spec["fields"]], dtype=np.float64),
        magic=int(spec["record"]["magic"]),
        hash32=zlib.crc32(canon) & 0xFFFFFFFF,
    )


def crc16_ccitt(data: bytes, crc: int = 0xFFFF) -> int:
    """CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF). Igual que en C."""
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


def quantize(c: Contract, values: np.ndarray) -> np.ndarray:
    """Física -> int16 con redondeo al más cercano (mitades lejos de cero) y saturación."""
    v = np.asarray(values, dtype=np.float64) * c.scales
    q = np.sign(v) * np.floor(np.abs(v) + 0.5)
    return np.clip(q, -32768, 32767).astype(np.int16)


def dequantize(c: Contract, q: np.ndarray) -> np.ndarray:
    return np.asarray(q, dtype=np.float64) / c.scales


def pack(c: Contract, frame_id: int, t_ms: int, track_id: int, flags: int,
         values: np.ndarray) -> bytes:
    q = quantize(c, values)
    body = _HEADER.pack(c.magic, c.version, c.n, frame_id & 0xFFFFFFFF,
                        t_ms & 0xFFFFFFFF, track_id, flags, c.hash16)
    body += struct.pack(f"<{c.n}h", *q.tolist())
    return body + struct.pack("<H", crc16_ccitt(body))


class RecordError(ValueError):
    pass


def unpack(c: Contract, rec: bytes) -> dict:
    if len(rec) != c.record_size:
        raise RecordError(f"tamaño {len(rec)} != {c.record_size}")
    body, (crc,) = rec[:-2], struct.unpack("<H", rec[-2:])
    if crc16_ccitt(body) != crc:
        raise RecordError("CRC incorrecto")
    magic, ver, n, frame_id, t_ms, track, flags, h16 = _HEADER.unpack(body[:_HEADER.size])
    if magic != c.magic or ver != c.version or n != c.n or h16 != c.hash16:
        raise RecordError("cabecera no corresponde a este contrato")
    q = np.array(struct.unpack(f"<{c.n}h", body[_HEADER.size:]), dtype=np.int16)
    return {"frame_id": frame_id, "t_ms": t_ms, "track_id": track, "flags": flags,
            "q": q, "values": dequantize(c, q)}
