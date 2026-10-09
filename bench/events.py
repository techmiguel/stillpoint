"""Test-bench file formats (interface I6, docs/architecture.md).

Ground truth (written by annotator.py):
    t_utc,event,person,note
    event ∈ start, end, enter, leave, standing, sitting, lying, fall, get_up, note

Device events (written by ha_export.py from Home Assistant):
    t_utc,device,signal,value
    signal ∈ occupancy (0/1), fall (0/1), count (integer)
"""
from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path

TRUTH_EVENTS = ("start", "end", "enter", "leave", "standing", "sitting", "lying", "fall", "get_up", "note")


def parse_t(s: str) -> float:
    """ISO 8601 (with Z or an offset) -> POSIX seconds."""
    s = s.strip().replace("Z", "+00:00")
    t = dt.datetime.fromisoformat(s)
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.timestamp()


def fmt_t(t: float) -> str:
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Truth:
    t: float
    event: str
    person: str = ""
    note: str = ""


@dataclass(frozen=True)
class DevEvent:
    t: float
    device: str
    signal: str
    value: float


def read_truth(path) -> list[Truth]:
    with open(path, newline="", encoding="utf-8") as f:
        out = []
        for r in csv.DictReader(f):
            if r["event"] not in TRUTH_EVENTS:
                raise ValueError(f"unknown event: {r['event']}")
            out.append(Truth(parse_t(r["t_utc"]), r["event"], r.get("person", ""), r.get("note", "")))
    return sorted(out, key=lambda e: e.t)


def write_truth(path, events) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_utc", "event", "person", "note"])
        for e in sorted(events, key=lambda e: e.t):
            w.writerow([fmt_t(e.t), e.event, e.person, e.note])


def read_dev(path) -> list[DevEvent]:
    with open(path, newline="", encoding="utf-8") as f:
        return sorted((DevEvent(parse_t(r["t_utc"]), r["device"], r["signal"], float(r["value"]))
                       for r in csv.DictReader(f)), key=lambda e: e.t)


def write_dev(path, events) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_utc", "device", "signal", "value"])
        for e in sorted(events, key=lambda e: e.t):
            w.writerow([fmt_t(e.t), e.device, e.signal, f"{e.value:g}"])


def truth_occupancy(truth: list[Truth]):
    """[t0, t1) intervals with at least one person, from enter/leave."""
    n, start, out = 0, None, []
    for e in truth:
        if e.event == "enter":
            n += 1
            if n == 1:
                start = e.t
        elif e.event == "leave":
            n = max(0, n - 1)
            if n == 0 and start is not None:
                out.append((start, e.t))
                start = None
    end = next((e.t for e in reversed(truth) if e.event == "end"), None)
    if start is not None and end is not None:
        out.append((start, end))
    return out


def step_signal(events: list[DevEvent], device: str, signal: str):
    """Step series (t, value) of one signal of one device."""
    return [(e.t, e.value) for e in events if e.device == device and e.signal == signal]


def value_at(series, t: float, default: float = 0.0) -> float:
    v = default
    for ts, val in series:
        if ts > t:
            break
        v = val
    return v


def rising_edges(series) -> list[float]:
    out, prev = [], 0.0
    for t, v in series:
        if v > 0.5 >= prev:
            out.append(t)
        prev = v
    return out


def falling_edges(series) -> list[float]:
    out, prev = [], 0.0
    for t, v in series:
        if v < 0.5 <= prev:
            out.append(t)
        prev = v
    return out


def session_span(truth: list[Truth]):
    t0 = next((e.t for e in truth if e.event == "start"), truth[0].t)
    t1 = next((e.t for e in reversed(truth) if e.event == "end"), truth[-1].t)
    return t0, t1


def ensure_dir(p) -> Path:
    p = Path(p)
    p.mkdir(parents=True, exist_ok=True)
    return p
