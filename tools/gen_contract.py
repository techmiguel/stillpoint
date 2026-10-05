"""Genera, a partir de contracts/features_v1.yaml y de la referencia Python:

  firmware/include/features_v1.h     índices, escalas, hash y tamaño del registro
  firmware/tests/golden_v1.h         vectores dorados: valores -> bytes esperados
  firmware/tests/decision_vectors.h  secuencias de entradas -> salidas de decision.py

Uso (desde la raíz): python tools/gen_contract.py
La CI falla si el resultado difiere de lo versionado (tests/test_contract.py).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

from radarref import contract as ct  # noqa: E402
from radarref.decision import Inputs, Params, TrackDecision  # noqa: E402


def fl(x: float, digits: int = 9) -> str:
    """Literal float de C: siempre con punto decimal y sufijo f."""
    s = f"{float(x):.{digits}g}"
    return (s if any(ch in s for ch in ".eEn") else s + ".0") + "f"


def header(c: ct.Contract) -> str:
    L = ["/* Generado por tools/gen_contract.py desde contracts/features_v1.yaml. No editar. */",
         "#pragma once", "#include <stdint.h>", "",
         f"#define RF_CONTRACT_VERSION {c.version}u",
         f"#define RF_CONTRACT_HASH32 0x{c.hash32:08X}u",
         f"#define RF_CONTRACT_HASH16 0x{c.hash16:04X}u",
         f"#define RF_MAGIC 0x{c.magic:04X}u",
         f"#define RF_N_FIELDS {c.n}u",
         f"#define RF_RECORD_SIZE {c.record_size}u",
         f"#define RF_FRAME_RATE_HZ {c.frame_rate_hz:g}f",
         f"#define RF_WINDOW_FRAMES {c.window_frames}u",
         f"#define RF_WINDOW_HOP {c.window_hop_frames}u", "",
         "typedef enum {"]
    L += [f"    RF_F_{n.upper()} = {i}," for i, n in enumerate(c.names)]
    L += ["} rf_field_t;", "",
          "static const float rf_scale[RF_N_FIELDS] = {",
          "    " + ", ".join(f"{s:g}.0f" for s in c.scales), "};", ""]
    return "\n".join(L)


def golden(c: ct.Contract) -> str:
    rng = np.random.default_rng(42)
    cases = []
    lims = np.array([3, 3, 2.5, 2.5, 2.5, 1, 1, 3, 3, 3, 3.5, 3, 60, 60, 48, 60, 60, .6, 40, 6, 4, 3000, 1, 1])
    for k in range(6):
        v = (rng.uniform(-1, 1, c.n) * lims).astype(np.float32)
        if k == 5:   # saturación y redondeo de mitades
            v[0], v[1], v[2] = np.float32(40.0), np.float32(-40.0), np.float32(0.0005)
        cases.append((1000 + k, 100 * k, k + 1, 0, v.astype(np.float64)))
    L = ["/* Generado por tools/gen_contract.py. No editar. */", "#pragma once", "#include <stdint.h>", "",
         f"#define GOLDEN_N {len(cases)}", "typedef struct { uint32_t frame_id, t_ms; uint8_t track, flags;",
         "  float v[RF_N_FIELDS]; uint8_t rec[RF_RECORD_SIZE]; } golden_t;",
         "static const golden_t golden[GOLDEN_N] = {"]
    for fid, t, tr, flags, v in cases:
        rec = ct.pack(c, fid, t, tr, flags, v)
        vs = ", ".join(fl(x) for x in v)
        bs = ", ".join(f"0x{b:02x}" for b in rec)
        L.append(f"  {{{fid}u, {t}u, {tr}u, {flags}u, {{{vs}}}, {{{bs}}}}},")
    L += ["};", ""]
    return "\n".join(L)


def decision_vectors() -> str:
    """Secuencias con caída, cama, oclusión y fuera de distribución."""
    p = Params()
    seqs = []
    rng = np.random.default_rng(7)
    def mk(kind):
        steps = []
        for i in range(60):
            t = i * 0.5
            if kind == "fall":
                down = t >= 5
                probs = (0.1, 0.05, 0.05, 0.8) if 5 <= t < 7 else ((0.05, .05, .9, 0) if down else (.9, .05, .05, 0))
                steps.append(Inputs(t, probs, 0.3 if down else 1.2, -1.5 if 5 <= t < 6 else 0.0,
                                    max(0.0, t - 7), 0.8, False, 0))
            elif kind == "bed":
                lie = t >= 8
                probs = (.05, .1, .85, 0) if lie else (.8, .15, .05, 0)
                steps.append(Inputs(t, probs, 0.7 if lie else 1.2, -0.4 if 7 <= t < 8 else 0, max(0, t - 9), .7, False, 0))
            elif kind == "occluded":
                probs = (.1, .05, .05, .8) if 4 <= t < 6 else (.3, .3, .4, 0)
                steps.append(Inputs(t, probs, 0.4 if t >= 4 else 1.2, -1.2 if 4 <= t < 5 else 0, 0.0, .5,
                                    t >= 6, 0))
            else:   # ruido aleatorio con OOD esporádico
                # redondeo a 4 decimales: el valor impreso en C es el mismo que usa Python
                r4 = lambda x: round(float(x), 4)  # noqa: E731
                pr = rng.dirichlet(np.ones(4))
                steps.append(Inputs(t, tuple(r4(x) for x in pr), r4(rng.uniform(0.1, 1.8)), r4(rng.uniform(-2, .5)),
                                    r4(rng.uniform(0, 10)), r4(rng.uniform(0, 1)), bool(rng.random() < .1),
                                    int(rng.integers(0, 6))))
        return steps
    for kind in ("fall", "bed", "occluded", "random"):
        d = TrackDecision(p)
        seqs.append([(s, d.update(s)) for s in mk(kind)])
    n = sum(len(s) for s in seqs)
    L = ["/* Generado por tools/gen_contract.py. No editar. */", "#pragma once", "",
         "typedef struct { int reset; float t, p[4], z_c, vz_min, still_s, quality; int occluded, ood;",
         "  int exp_posture, exp_fall; } dvec_t;", f"#define DVEC_N {n}", "static const dvec_t dvec[DVEC_N] = {"]
    for seq in seqs:
        for i, (s, (post, _conf, fall)) in enumerate(seq):
            pr = ", ".join(fl(x, 6) for x in s.probs)
            L.append(f"  {{{int(i == 0)}, {fl(s.t)}, {{{pr}}}, {fl(s.z_c, 6)}, {fl(s.vz_min, 6)}, {fl(s.still_s, 6)}, "
                     f"{fl(s.quality, 6)}, {int(s.occluded)}, {s.ood_count}, {post}, {fall}}},")
    L += ["};", ""]
    return "\n".join(L)


def main():
    c = ct.load()
    out = {ROOT / "firmware/include/features_v1.h": header(c),
           ROOT / "firmware/tests/golden_v1.h": golden(c),
           ROOT / "firmware/tests/decision_vectors.h": decision_vectors()}
    for path, text in out.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        print("escrito", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
