"""Métricas del banco de pruebas con intervalos de confianza.

Se publican siempre con su intervalo y su n: «0 falsas alarmas en 3 días» no
demuestra lo mismo que «0 en 30 días».
"""
from __future__ import annotations

import numpy as np
from scipy import stats


def wilson(k: int, n: int, conf: float = 0.95):
    """Proporción k/n con intervalo de Wilson."""
    if n == 0:
        return float("nan"), 0.0, 1.0
    z = stats.norm.ppf(0.5 + conf / 2)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, c - h), min(1.0, c + h)


def rate_per_day(events: int, hours: float, conf: float = 0.95):
    """Tasa de Poisson por día con intervalo exacto (Garwood)."""
    days = hours / 24
    a = 1 - conf
    lo = 0.0 if events == 0 else stats.chi2.ppf(a / 2, 2 * events) / 2
    hi = stats.chi2.ppf(1 - a / 2, 2 * events + 2) / 2
    return events / days, lo / days, hi / days


def days_needed(max_rate_per_day: float, conf: float = 0.95) -> float:
    """Días sin eventos necesarios para afirmar tasa < max con confianza `conf`
    (cota unilateral; con 95 % es la «regla del tres»)."""
    return -np.log(1 - conf) / max_rate_per_day


def match_events(truth_t, det_t, max_latency_s: float):
    """Empareja cada evento real con la primera detección en [t, t+max].
    Devuelve (aciertos, latencias, detecciones_falsas)."""
    det = sorted(det_t)
    used = set()
    lat = []
    for t in sorted(truth_t):
        for i, d in enumerate(det):
            if i not in used and t <= d <= t + max_latency_s:
                used.add(i)
                lat.append(d - t)
                break
    return len(lat), np.array(lat), len(det) - len(used)


def macro_f1(y, yhat, n_classes: int, ignore=None):
    f1 = []
    for k in range(n_classes):
        m = np.ones_like(y, bool) if ignore is None else yhat != ignore
        tp = np.sum((y == k) & (yhat == k) & m)
        fp = np.sum((y != k) & (yhat == k) & m)
        fn = np.sum((y == k) & (yhat != k) & m)
        f1.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return float(np.mean(f1)), f1
