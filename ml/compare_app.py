"""Punta a punta: aplicación C completa frente a la referencia Python (cadena +
clasificador + decisión) sobre los escenarios de caída de eval_events.py y el
de oclusión. Comprueba además que los registros que emite C los decodifica la
referencia Python sin errores.

Uso: python compare_app.py   -> docs/img/app_c_vs_python.png
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
from eval_events import ROOM, ROOMS, SUBJ, SUBJECTS, scenes  # noqa: E402
from radarref import adcfile, scenarios  # noqa: E402
from radarref import contract as ct  # noqa: E402
from radarref.classifier import Classifier, Inference  # noqa: E402
from radarref.config import Room  # noqa: E402
from radarref.pipeline import Pipeline  # noqa: E402
from radarref.sim import Person, Scene, Simulator  # noqa: E402

ART = Path(__file__).resolve().parent / "artifacts" / "synth_v1"


def all_scenes():
    out = {}
    rp = ROOMS[ROOM]
    for col, (name, (keys, falls)) in enumerate(scenes().items()):
        room = Room(mount_h=rp["mount_h"])
        person = Person(keys, fall_times=falls, **SUBJECTS[SUBJ])
        out[name] = (Scene(room=room, people=[person], clutter=rp["clutter"], seed=99 + col), 30.0)
    sc, dur, _ = scenarios.occlusion()
    out["oclusion"] = (sc, dur)
    return out


def parse(text):
    frames = []
    for line in text.splitlines():
        p = line.split()
        if p[0] == "F":
            frames.append({"count": int(p[2]), "alarm": int(p[4]), "people": {}})
        else:
            frames[-1]["people"][int(p[1])] = (int(p[2]), int(p[3]), int(p[4]))
    return frames


def run(name, scene, dur, exe, clf):
    sim = Simulator(scene)
    n = int(dur * 10)
    adc = [sim.frame(i / 10) for i in range(n)]
    pipe, inf = Pipeline(scene.room, sim.cfg), Inference(clf)
    py = []
    for i, a in enumerate(adc):
        o = pipe.step(i / 10, a)
        res = inf.step(o)
        ppl = {}
        for tid, st, _ in o.tracks:
            if st == 4:
                continue
            r = res.get(tid)
            ppl[tid] = (r[1], r[3], 1) if r else (0, 0, 0)
        py.append({"count": o.count, "people": ppl})
    with tempfile.TemporaryDirectory() as d:
        f, rec = Path(d) / "s.rfad", Path(d) / "r.bin"
        adcfile.write(f, scene.room, adc)
        r = subprocess.run([str(exe), "-r", str(rec), str(f)], capture_output=True, text=True, check=True)
        raw = rec.read_bytes()
    cc = parse(r.stdout)
    c = ct.load()
    nrec = len(raw) // c.record_size
    for k in range(nrec):   # lanza RecordError si un registro de C no es válido
        ct.unpack(c, raw[k * c.record_size:(k + 1) * c.record_size])
    pairs = [(a["people"][t], b["people"][t]) for a, b in zip(py, cc) for t in a["people"] if t in b["people"]]
    agree = np.mean([x == y for x, y in pairs]) if pairs else float("nan")
    count_eq = np.mean([a["count"] == b["count"] for a, b in zip(py, cc)])

    def first_alarm(frames):
        for i, f in enumerate(frames):
            if any(v[1] in (2, 3) for v in f["people"].values()):
                return i / 10
        return None
    return {"escenario": name, "recuento_igual": round(float(count_eq), 4),
            "postura_y_caida_iguales": round(float(agree), 4), "registros_C_validos": nrec,
            "alarma_python_s": first_alarm(py), "alarma_C_s": first_alarm(cc), "py": py, "c": cc, "n": n}


def plot(res, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, len(res), figsize=(4.2 * len(res), 5.2), sharex="col", squeeze=False)
    for j, r in enumerate(res):
        t = np.arange(r["n"]) / 10

        def series(frames, k):
            return [max([v[k] for v in f["people"].values()], default=0) for f in frames]
        for i, (k, lab) in enumerate(((1, "caída (0 no, 1 sosp., 2 conf., 3 inc.)"), (0, "postura (0 inc., 1 pie, 2 sent., 3 tumb.)"))):
            ax = axes[i][j]
            ax.step(t, series(r["py"], k), where="post", lw=3, alpha=.4, label="Python")
            ax.step(t, series(r["c"], k), where="post", lw=1.1, c="k", label="C")
            ax.set_ylim(-.3, 3.3)
            if j == 0:
                ax.set_ylabel(lab, fontsize=8)
        axes[0][j].set_title(f"{r['escenario']}\niguales {100 * r['postura_y_caida_iguales']:.1f} %  "
                             f"alarma C {r['alarma_C_s']} s / Py {r['alarma_python_s']} s", fontsize=9)
        axes[1][j].set_xlabel("t (s)")
    axes[0][0].legend(fontsize=7)
    fig.suptitle("Aplicación completa en C (DSP + seguimiento + red int8 + decisión) frente a Python")
    fig.tight_layout()
    fig.savefig(out, dpi=105)


def main():
    exe = build_host.build("replay_app")
    clf = Classifier(ART)
    res = [run(n, s, d, exe, clf) for n, (s, d) in all_scenes().items()]
    for r in res:
        print({k: v for k, v in r.items() if k not in ("py", "c", "n")})
    plot(res, ROOT / "docs" / "img" / "app_c_vs_python.png")
    return res


if __name__ == "__main__":
    main()
