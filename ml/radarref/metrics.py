"""Test-bench metrics with confidence intervals.

Always published with their interval and their n: "0 false alarms in 3 days"
does not prove the same as "0 in 30 days".
"""
from __future__ import annotations

import numpy as np
from scipy import stats


def wilson(k: int, n: int, conf: float = 0.95):
    """Proportion k/n with a Wilson interval."""
    if n == 0:
        return float("nan"), 0.0, 1.0
    z = stats.norm.ppf(0.5 + conf / 2)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, c - h), min(1.0, c + h)


def rate_per_day(events: int, hours: float, conf: float = 0.95):
    """Poisson rate per day with an exact (Garwood) interval."""
    days = hours / 24
    a = 1 - conf
    lo = 0.0 if events == 0 else stats.chi2.ppf(a / 2, 2 * events) / 2
    hi = stats.chi2.ppf(1 - a / 2, 2 * events + 2) / 2
    return events / days, lo / days, hi / days


def days_needed(max_rate_per_day: float, conf: float = 0.95) -> float:
    """Event-free days needed to claim rate < max with confidence `conf`
    (one-sided bound; at 95 % this is the "rule of three")."""
    return -np.log(1 - conf) / max_rate_per_day


def match_events(truth_t, det_t, max_latency_s: float):
    """Matches every true event with the first detection in [t, t+max].
    Returns (hits, latencies, false_detections)."""
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
