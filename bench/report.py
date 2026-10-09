"""Acceptance-criteria report (docs/requirements.md) from the ground truth and the
device events (prototype and a commercial reference).

  python bench/report.py --truth truth.csv --events events.csv \
      --devices radar60 aqara_fp2 --out report/

Writes report/report.md and report/report.png. Every metric carries its n and
its 95 % confidence interval; with 0 events the upper bound is given.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from events import (ensure_dir, falling_edges, read_dev, read_truth, rising_edges,  # noqa: E402
                    session_span, step_signal, truth_occupancy)
from radarref.metrics import rate_per_day, wilson  # noqa: E402

# Thresholds from docs/requirements.md (copied here so the report can say pass/fail)
CRIT = {
    "P1": ("Occupied minutes detected", ">=", 0.99),
    "P3": ("False occupancies per day (empty room)", "<=", 1.0),
    "P4": ("Latency entry → occupied p95 (s)", "<=", 1.0),
    "P5": ("Latency exit → empty p95 (s)", "<=", 5.0),
    "F1": ("Falls notified", ">=", 0.90),
    "F2": ("False fall alarms per day", "<=", 0.1),
    "F3": ("Latency fall → notification p95 (s)", "<=", 10.0),
}
GRACE_S = 30.0       # after someone leaves, the room does not count as "empty" for this long
FALL_MATCH_S = 30.0


def occupied(intervals, t):
    return any(a <= t < b for a, b in intervals)


def metrics_for(truth, events, dev: str):
    t0, t1 = session_span(truth)
    hours = (t1 - t0) / 3600
    occ_iv = truth_occupancy(truth)
    occ = step_signal(events, dev, "occupancy")
    fall = step_signal(events, dev, "fall")
    grid = np.arange(t0, t1, 1.0)
    dev_on = np.array([_val(occ, t) for t in grid])
    tru_on = np.array([occupied(occ_iv, t) for t in grid])
    m = {}
    # P1: fully occupied minutes with the device "occupied" for >= 95 % of the minute
    mins = [(i, i + 60) for i in range(0, len(grid) - 59, 60) if tru_on[i:i + 60].all()]
    ok = sum(dev_on[a:b].mean() >= 0.95 for a, b in mins)
    m["P1"] = _prop(ok, len(mins))
    # P3: rises to occupied while the room is empty (outside the grace period after a leave)
    exits = [e.t for e in truth if e.event == "leave"]
    empty_s = sum(1 for t in grid if not occupied(occ_iv, t) and not any(0 <= t - x < GRACE_S for x in exits))
    fp = [t for t in rising_edges(occ) if t0 <= t < t1 and not occupied(occ_iv, t)
          and not any(0 <= t - x < GRACE_S for x in exits) and not any(0 <= a - t < 2.0 for a, _ in occ_iv)]
    m["P3"] = _rate(len(fp), empty_s / 3600)
    # P4 / P5: entry latency (room empty before) and exit latency (room empty after)
    lat_in = []
    for a, _ in occ_iv:
        r = [t for t in rising_edges(occ) if a - 2.0 <= t <= a + 10]
        lat_in.append(max(0.0, r[0] - a) if r else np.inf)
    lat_out = []
    for _, b in occ_iv:
        f = [t for t in falling_edges(occ) if b - 2.0 <= t <= b + 60]
        lat_out.append(max(0.0, f[0] - b) if f else np.inf)
    m["P4"] = _p95(lat_in)
    m["P5"] = _p95(lat_out)
    # F1 / F3 / F2: fall alarms (confirmed or uncertain) against simulated falls
    falls = [e.t for e in truth if e.event == "fall"]
    alarms = [t for t in rising_edges(fall) if t0 <= t < t1]
    used, lat = set(), []
    for tf in falls:
        cand = [i for i, ta in enumerate(alarms) if i not in used and tf <= ta <= tf + FALL_MATCH_S]
        if cand:
            used.add(cand[0])
            lat.append(alarms[cand[0]] - tf)
    m["F1"] = _prop(len(lat), len(falls))
    m["F3"] = _p95(lat if lat else [np.inf])
    m["F2"] = _rate(len(alarms) - len(used), hours)
    m["_series"] = (grid, dev_on, tru_on)
    m["_hours"] = hours
    return m


def _val(series, t):
    v = 0.0
    for ts, val in series:
        if ts > t:
            break
        v = val
    return v


def _prop(k, n):
    p, lo, hi = wilson(k, n)
    return {"value": p, "ci": (lo, hi), "n": n, "k": k}


def _rate(k, hours):
    if hours <= 0:
        return {"value": float("nan"), "ci": (float("nan"),) * 2, "n": k, "hours": hours}
    r, lo, hi = rate_per_day(k, hours)
    return {"value": r, "ci": (lo, hi), "n": k, "hours": hours}


def _p95(x):
    x = np.asarray(x, float)
    return {"value": float(np.percentile(x, 95)) if len(x) else float("nan"), "n": len(x),
            "missed": int(np.sum(~np.isfinite(x)))}


def passes(cid, v):
    _, op, thr = CRIT[cid]
    val = v["value"]
    if not np.isfinite(val):
        return False
    if cid in ("P3", "F2"):       # rates: the upper bound must pass, not the point value
        return v["ci"][1] <= thr
    if cid == "F1":               # docs/requirements.md: >= 90 % and the CI95 lower bound >= 80 %
        return val >= thr and v["ci"][0] >= 0.80
    if cid == "P1":
        return val >= thr
    return val <= thr


def fmt(cid, v):
    if "ci" in v and cid in ("P1", "F1"):
        return f"{100 * v['value']:.1f} % ({v['k']}/{v['n']}; CI95 {100 * v['ci'][0]:.1f}–{100 * v['ci'][1]:.1f} %)"
    if "hours" in v:
        return f"{v['value']:.2f} ({v['n']} in {v['hours']:.1f} h; CI95 upper {v['ci'][1]:.2f})"
    s = f"{v['value']:.1f} s (n={v['n']})"
    return s + (f", {v['missed']} missed" if v.get("missed") else "")


def report(truth, events, devs, out: Path, title: str, warning: str = ""):
    ensure_dir(out)
    res = {d: metrics_for(truth, events, d) for d in devs}
    L = [f"# {title}", ""]
    if warning:
        L += [f"> {warning}", ""]
    L += [f"Duration: {res[devs[0]]['_hours']:.1f} h. Falls, when present, are simulated by healthy adults "
          "on a crash mat (docs/data-protocol.md).", "",
          "| Criterion | Threshold | " + " | ".join(devs) + " |", "|---|---|" + "---|" * len(devs)]
    for cid, (name, op, thr) in CRIT.items():
        cells = []
        for d in devs:
            v = res[d][cid]
            cells.append(("✅ " if passes(cid, v) else "❌ ") + fmt(cid, v))
        L.append(f"| {cid} {name} | {op} {thr:g} | " + " | ".join(cells) + " |")
    if len(devs) > 1:
        a, b = devs[0], devs[1]
        L += ["", f"Kill criterion (docs/requirements.md): {a} must match {b} on P1, P2 and P3. "
              "P2 is measured separately with scenarios O1–O2."]
        for cid in ("P1", "P3"):
            va, vb = res[a][cid]["value"], res[b][cid]["value"]
            better = va >= vb if cid == "P1" else va <= vb
            L.append(f"- {cid}: {a} {'matches or beats' if better else 'does NOT match'} {b}.")
    (out / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    _plot(res, devs, out / "report.png", title)
    return res


def _plot(res, devs, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    grid, _, tru = res[devs[0]]["_series"]
    h = (grid - grid[0]) / 3600
    fig, axes = plt.subplots(len(devs) + 1, 1, figsize=(12, 1.4 * (len(devs) + 1) + 1), sharex=True)
    axes[0].fill_between(h, tru, step="post", color="k", alpha=.6)
    axes[0].set_ylabel("truth", rotation=0, ha="right")
    for ax, d in zip(axes[1:], devs):
        _, on, _ = res[d]["_series"]
        ax.fill_between(h, on, step="post", alpha=.7)
        miss = tru & (on < .5)
        fa = (~tru) & (on > .5)
        ax.fill_between(h, miss * 1.0, step="post", color="tab:red", alpha=.5, label="missed")
        ax.fill_between(h, fa * 1.0, step="post", color="tab:orange", alpha=.6, label="false occupancy")
        ax.set_ylabel(d, rotation=0, ha="right")
        ax.set_yticks([])
    axes[0].set_yticks([])
    axes[-1].set_xlabel("hours")
    axes[1].legend(fontsize=7, loc="upper right")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=100)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", required=True)
    ap.add_argument("--events", required=True)
    ap.add_argument("--devices", nargs="+", required=True)
    ap.add_argument("--out", default="report")
    ap.add_argument("--title", default="Test-bench report")
    ap.add_argument("--warning", default="")
    a = ap.parse_args(argv)
    report(read_truth(a.truth), read_dev(a.events), a.devices, Path(a.out), a.title, a.warning)
    print((Path(a.out) / "report.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
