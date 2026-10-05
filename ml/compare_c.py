"""Compara el DSP + seguimiento en C con la referencia Python, trama a trama.

Uso: python compare_c.py [escenario ...]   (por defecto, todos)
Escribe docs/img/c_vs_python_<escenario>.png y devuelve el resumen.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_host  # noqa: E402
from radarref import adcfile, scenarios  # noqa: E402
from radarref import contract as ct  # noqa: E402
from radarref.pipeline import Pipeline  # noqa: E402
from radarref.sim import Simulator  # noqa: E402


def parse(text: str):
    frames = []
    for line in text.splitlines():
        p = line.split()
        if p[0] == "F":
            frames.append({"t": float(p[1]), "count": int(p[2]), "tracks": {}})
        elif p[0] == "T":
            frames[-1]["tracks"][int(p[1])] = (int(p[2]), np.array([float(v) for v in p[3:]]))
    return frames


def run(name: str, exe: Path):
    scene, dur, _ = scenarios.ALL[name]()
    sim = Simulator(scene)
    n = int(dur * 10)
    adc = [sim.frame(i / 10) for i in range(n)]
    pipe = Pipeline(scene.room, sim.cfg)
    py = []
    for i, a in enumerate(adc):
        o = pipe.step(i / 10, a)
        py.append({"count": o.count, "tracks": {tid: (st, f) for tid, st, f in o.tracks}})
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / f"{name}.rfad"
        adcfile.write(path, scene.room, adc)
        r = subprocess.run([str(exe), str(path)], capture_output=True, text=True, check=True)
    cc = parse(r.stdout)
    assert len(cc) == len(py)
    c = ct.load()
    count_eq = np.mean([a["count"] == b["count"] for a, b in zip(py, cc)])
    # características de pistas presentes en ambos con el mismo id
    diffs = []
    for a, b in zip(py, cc):
        for tid, (st, f) in a["tracks"].items():
            if tid in b["tracks"]:
                diffs.append(np.abs(ct.quantize(c, f).astype(int) - ct.quantize(c, b["tracks"][tid][1]).astype(int)))
    diffs = np.array(diffs) if diffs else np.zeros((0, c.n))
    exact = float(np.mean(diffs == 0)) if len(diffs) else float("nan")
    xy = c.index("x"), c.index("y")
    pos_err_mm = float(np.percentile(np.hypot(diffs[:, xy[0]], diffs[:, xy[1]]), 99)) if len(diffs) else float("nan")
    return {"escenario": name, "tramas": n, "recuento_igual": round(float(count_eq), 4),
            "valores_cuantizados_identicos": round(exact, 4), "error_posicion_p99_mm": round(pos_err_mm, 2),
            "py": py, "c": cc}


def plot(res, out: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, len(res), figsize=(4.4 * len(res), 3.6), squeeze=False)
    for ax, r in zip(axes[0], res):
        t = np.arange(r["tramas"]) / 10
        ax.step(t, [f["count"] for f in r["py"]], where="post", lw=3, alpha=.4, label="Python (referencia)")
        ax.step(t, [f["count"] for f in r["c"]], where="post", lw=1.2, c="k", label="C (firmware)")
        ax.set_title(f"{r['escenario']}: recuento igual {100 * r['recuento_igual']:.1f} %\n"
                     f"valores idénticos {100 * r['valores_cuantizados_identicos']:.1f} %", fontsize=9)
        ax.set_xlabel("t (s)")
        ax.set_ylim(-.3, 3.3)
    axes[0][0].set_ylabel("personas")
    axes[0][0].legend(fontsize=7)
    fig.suptitle("Firmware C frente a la referencia Python con las mismas tramas ADC")
    fig.tight_layout()
    fig.savefig(out, dpi=105)


def main(names):
    exe = build_host.build("replay")
    res = [run(n, exe) for n in (names or list(scenarios.ALL))]
    for r in res:
        print({k: v for k, v in r.items() if k not in ("py", "c")})
    out = ROOT / "docs" / "img" / "c_vs_python.png"
    plot(res, out)
    print("figura:", out)
    return res


if __name__ == "__main__":
    main(sys.argv[1:])
