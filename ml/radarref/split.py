"""Separación de datos por persona Y por habitación.

Regla del proyecto: una sesión de prueba no comparte persona ni habitación con
ninguna sesión de entrenamiento o validación. Las sesiones que mezclarían
(persona de entrenamiento grabada en la habitación de prueba) se descartan;
es el precio de que las métricas valgan.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    id: str
    subject: str
    room: str


class LeakageError(AssertionError):
    pass


def split(sessions, test_subjects, test_rooms, val_subjects=(), val_rooms=()):
    ts, tr_, vs, vr = set(test_subjects), set(test_rooms), set(val_subjects), set(val_rooms)
    if ts & vs or tr_ & vr:
        raise LeakageError("validación y prueba comparten persona o habitación")
    out = {"train": [], "val": [], "test": [], "discarded": []}
    for s in sessions:
        if s.subject in ts and s.room in tr_:
            out["test"].append(s)
        elif s.subject in vs and s.room in vr:
            out["val"].append(s)
        elif s.subject not in ts | vs and s.room not in tr_ | vr:
            out["train"].append(s)
        else:
            out["discarded"].append(s)
    check(out)
    return out


def check(parts) -> None:
    """Falla si dos particiones comparten persona o habitación."""
    names = [k for k in ("train", "val", "test") if parts.get(k)]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            for attr in ("subject", "room"):
                sa = {getattr(s, attr) for s in parts[a]}
                sb = {getattr(s, attr) for s in parts[b]}
                if sa & sb:
                    raise LeakageError(f"{a} y {b} comparten {attr}: {sorted(sa & sb)}")
