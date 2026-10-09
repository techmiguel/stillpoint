"""Data split by person AND by room.

Project rule: a test session shares neither person nor room with any
training or validation session. Sessions that would mix them (a
training person recorded in the test room) are discarded; that is the
price of metrics that mean something.
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
        raise LeakageError("validation and test share a person or a room")
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
    """Fails if two partitions share a person or a room."""
    names = [k for k in ("train", "val", "test") if parts.get(k)]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            for attr in ("subject", "room"):
                sa = {getattr(s, attr) for s in parts[a]}
                sb = {getattr(s, attr) for s in parts[b]}
                if sa & sb:
                    raise LeakageError(f"{a} and {b} share {attr}: {sorted(sa & sb)}")
