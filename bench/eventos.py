"""Formatos del banco de pruebas (interfaz I6, docs/03).

Verdad de terreno (lo escribe anotador.py):
    t_utc,evento,persona,nota
    evento ∈ inicio, fin, entra, sale, de_pie, sentado, tumbado, caida, levanta, nota

Eventos de dispositivo (lo escribe ha_export.py a partir de Home Assistant):
    t_utc,dispositivo,senal,valor
    senal ∈ ocupacion (0/1), caida (0/1), personas (entero)
"""
from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path

TRUTH_EVENTS = ("inicio", "fin", "entra", "sale", "de_pie", "sentado", "tumbado", "caida", "levanta", "nota")


def parse_t(s: str) -> float:
    """ISO 8601 (con Z o con zona) -> segundos POSIX."""
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
    evento: str
    persona: str = ""
    nota: str = ""


@dataclass(frozen=True)
class DevEvent:
    t: float
    dispositivo: str
    senal: str
    valor: float


def read_truth(path) -> list[Truth]:
    with open(path, newline="", encoding="utf-8") as f:
        out = []
        for r in csv.DictReader(f):
            if r["evento"] not in TRUTH_EVENTS:
                raise ValueError(f"evento desconocido: {r['evento']}")
            out.append(Truth(parse_t(r["t_utc"]), r["evento"], r.get("persona", ""), r.get("nota", "")))
    return sorted(out, key=lambda e: e.t)


def write_truth(path, events) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_utc", "evento", "persona", "nota"])
        for e in sorted(events, key=lambda e: e.t):
            w.writerow([fmt_t(e.t), e.evento, e.persona, e.nota])


def read_dev(path) -> list[DevEvent]:
    with open(path, newline="", encoding="utf-8") as f:
        return sorted((DevEvent(parse_t(r["t_utc"]), r["dispositivo"], r["senal"], float(r["valor"]))
                       for r in csv.DictReader(f)), key=lambda e: e.t)


def write_dev(path, events) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_utc", "dispositivo", "senal", "valor"])
        for e in sorted(events, key=lambda e: e.t):
            w.writerow([fmt_t(e.t), e.dispositivo, e.senal, f"{e.valor:g}"])


def truth_occupancy(truth: list[Truth]):
    """Intervalos [t0, t1) con al menos una persona según entra/sale."""
    n, start, out = 0, None, []
    for e in truth:
        if e.evento == "entra":
            n += 1
            if n == 1:
                start = e.t
        elif e.evento == "sale":
            n = max(0, n - 1)
            if n == 0 and start is not None:
                out.append((start, e.t))
                start = None
    end = next((e.t for e in reversed(truth) if e.evento == "fin"), None)
    if start is not None and end is not None:
        out.append((start, end))
    return out


def step_signal(events: list[DevEvent], dispositivo: str, senal: str):
    """Serie escalonada (t, valor) de una señal de un dispositivo."""
    return [(e.t, e.valor) for e in events if e.dispositivo == dispositivo and e.senal == senal]


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
    t0 = next((e.t for e in truth if e.evento == "inicio"), truth[0].t)
    t1 = next((e.t for e in reversed(truth) if e.evento == "fin"), truth[-1].t)
    return t0, t1


def ensure_dir(p) -> Path:
    p = Path(p)
    p.mkdir(parents=True, exist_ok=True)
    return p
