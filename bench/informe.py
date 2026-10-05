"""Informe de criterios de aceptación (docs/01) a partir de la verdad de terreno y
de los eventos de los dispositivos (prototipo y referencia comercial).

  python bench/informe.py --verdad verdad.csv --eventos eventos.csv \
      --dispositivos radar60 aqara_fp2 --salida informe/

Escribe informe/informe.md e informe/informe.png. Cada métrica lleva su n y
su intervalo de confianza del 95 %; con 0 eventos se da la cota superior.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from eventos import (ensure_dir, falling_edges, read_dev, read_truth, rising_edges,  # noqa: E402
                     session_span, step_signal, truth_occupancy)
from radarref.metrics import rate_per_day, wilson  # noqa: E402

# Umbrales de docs/01 (se copian aquí para que el informe diga cumple/no cumple)
CRIT = {
    "P1": ("Minutos ocupados detectados", ">=", 0.99),
    "P3": ("Falsas ocupaciones por día (sala vacía)", "<=", 1.0),
    "P4": ("Latencia entrada → ocupado p95 (s)", "<=", 1.0),
    "P5": ("Latencia salida → vacío p95 (s)", "<=", 5.0),
    "F1": ("Caídas notificadas", ">=", 0.90),
    "F2": ("Falsas alarmas de caída por día", "<=", 0.1),
    "F3": ("Latencia caída → notificación p95 (s)", "<=", 10.0),
}
GRACE_S = 30.0       # tras una salida, la sala no cuenta como «vacía» durante este margen
FALL_MATCH_S = 30.0


def occupied(intervals, t):
    return any(a <= t < b for a, b in intervals)


def metrics_for(truth, events, dev: str):
    t0, t1 = session_span(truth)
    hours = (t1 - t0) / 3600
    occ_iv = truth_occupancy(truth)
    occ = step_signal(events, dev, "ocupacion")
    fall = step_signal(events, dev, "caida")
    grid = np.arange(t0, t1, 1.0)
    dev_on = np.array([_val(occ, t) for t in grid])
    tru_on = np.array([occupied(occ_iv, t) for t in grid])
    m = {}
    # P1: minutos totalmente ocupados con el dispositivo en «ocupado» >= 95 % del minuto
    mins = [(i, i + 60) for i in range(0, len(grid) - 59, 60) if tru_on[i:i + 60].all()]
    ok = sum(dev_on[a:b].mean() >= 0.95 for a, b in mins)
    m["P1"] = _prop(ok, len(mins))
    # P3: subidas a ocupado con la sala vacía (fuera del margen tras una salida)
    exits = [e.t for e in truth if e.evento == "sale"]
    empty_s = sum(1 for t in grid if not occupied(occ_iv, t) and not any(0 <= t - x < GRACE_S for x in exits))
    fp = [t for t in rising_edges(occ) if t0 <= t < t1 and not occupied(occ_iv, t)
          and not any(0 <= t - x < GRACE_S for x in exits) and not any(0 <= a - t < 2.0 for a, _ in occ_iv)]
    m["P3"] = _rate(len(fp), empty_s / 3600)
    # P4 / P5: latencias de entrada (sala vacía antes) y de salida (sala vacía después)
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
    # F1 / F3 / F2: caídas (confirmada o incierta) frente a caídas simuladas
    falls = [e.t for e in truth if e.evento == "caida"]
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
    m["_horas"] = hours
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
    return {"valor": p, "ic": (lo, hi), "n": n, "k": k}


def _rate(k, hours):
    if hours <= 0:
        return {"valor": float("nan"), "ic": (float("nan"),) * 2, "n": k, "horas": hours}
    r, lo, hi = rate_per_day(k, hours)
    return {"valor": r, "ic": (lo, hi), "n": k, "horas": hours}


def _p95(x):
    x = np.asarray(x, float)
    return {"valor": float(np.percentile(x, 95)) if len(x) else float("nan"), "n": len(x),
            "perdidas": int(np.sum(~np.isfinite(x)))}


def cumple(cid, v):
    _, op, thr = CRIT[cid]
    val = v["valor"]
    if not np.isfinite(val):
        return False
    if cid in ("P3", "F2"):       # tasas: se exige la cota superior, no el valor puntual
        return v["ic"][1] <= thr
    if cid == "F1":               # docs/01: ≥ 90 % y límite inferior del IC95 ≥ 80 %
        return val >= thr and v["ic"][0] >= 0.80
    if cid == "P1":
        return val >= thr
    return val <= thr


def fmt(cid, v):
    if "ic" in v and cid in ("P1", "F1"):
        return f"{100 * v['valor']:.1f} % ({v['k']}/{v['n']}; IC95 {100 * v['ic'][0]:.1f}–{100 * v['ic'][1]:.1f} %)"
    if "horas" in v:
        return f"{v['valor']:.2f} ({v['n']} en {v['horas']:.1f} h; IC95 sup. {v['ic'][1]:.2f})"
    s = f"{v['valor']:.1f} s (n={v['n']})"
    return s + (f", {v['perdidas']} no detectadas" if v.get("perdidas") else "")


def report(truth, events, devs, out: Path, titulo: str, aviso: str = ""):
    ensure_dir(out)
    res = {d: metrics_for(truth, events, d) for d in devs}
    L = [f"# {titulo}", ""]
    if aviso:
        L += [f"> {aviso}", ""]
    L += [f"Duración: {res[devs[0]]['_horas']:.1f} h. Caídas simuladas por adultos sanos sobre colchoneta "
          "cuando las hay (docs/07).", "",
          "| Criterio | Umbral | " + " | ".join(devs) + " |", "|---|---|" + "---|" * len(devs)]
    for cid, (name, op, thr) in CRIT.items():
        cells = []
        for d in devs:
            v = res[d][cid]
            cells.append(("✅ " if cumple(cid, v) else "❌ ") + fmt(cid, v))
        L.append(f"| {cid} {name} | {op} {thr:g} | " + " | ".join(cells) + " |")
    if len(devs) > 1:
        a, b = devs[0], devs[1]
        L += ["", f"Criterio de abandono (docs/01): {a} debe igualar a {b} en P1, P2 y P3. "
              "P2 se mide aparte con los escenarios O1–O2."]
        for cid in ("P1", "P3"):
            va, vb = res[a][cid]["valor"], res[b][cid]["valor"]
            better = va >= vb if cid == "P1" else va <= vb
            L.append(f"- {cid}: {a} {'iguala o supera' if better else 'NO iguala'} a {b}.")
    (out / "informe.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    _plot(res, devs, out / "informe.png", titulo)
    return res


def _plot(res, devs, path, titulo):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    grid, _, tru = res[devs[0]]["_series"]
    h = (grid - grid[0]) / 3600
    fig, axes = plt.subplots(len(devs) + 1, 1, figsize=(12, 1.4 * (len(devs) + 1) + 1), sharex=True)
    axes[0].fill_between(h, tru, step="post", color="k", alpha=.6)
    axes[0].set_ylabel("verdad", rotation=0, ha="right")
    for ax, d in zip(axes[1:], devs):
        _, on, _ = res[d]["_series"]
        ax.fill_between(h, on, step="post", alpha=.7)
        miss = tru & (on < .5)
        fa = (~tru) & (on > .5)
        ax.fill_between(h, miss * 1.0, step="post", color="tab:red", alpha=.5, label="pérdida")
        ax.fill_between(h, fa * 1.0, step="post", color="tab:orange", alpha=.6, label="falsa ocupación")
        ax.set_ylabel(d, rotation=0, ha="right")
        ax.set_yticks([])
    axes[0].set_yticks([])
    axes[-1].set_xlabel("horas")
    axes[1].legend(fontsize=7, loc="upper right")
    fig.suptitle(titulo)
    fig.tight_layout()
    fig.savefig(path, dpi=100)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--verdad", required=True)
    ap.add_argument("--eventos", required=True)
    ap.add_argument("--dispositivos", nargs="+", required=True)
    ap.add_argument("--salida", default="informe")
    ap.add_argument("--titulo", default="Informe del banco de pruebas")
    ap.add_argument("--aviso", default="")
    a = ap.parse_args(argv)
    report(read_truth(a.verdad), read_dev(a.eventos), a.dispositivos, Path(a.salida), a.titulo, a.aviso)
    print((Path(a.salida) / "informe.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
