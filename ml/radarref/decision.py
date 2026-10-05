"""Decisión por pista con fallo seguro. Espejo exacto: firmware/src/decision.c.

Principio: si no hay confianza, se declara «incierto»; nunca se inventa una
postura ni se calla una posible caída. La caída es una notificación, no un
medio de seguridad (docs/00).

Postura publicada: 0 incierta, 1 de pie, 2 sentada, 3 tumbada.
Caída:  0 ninguna, 1 sospecha, 2 confirmada, 3 incierta (posible caída sin
        poder verificar: pista ocluida o perdida durante la sospecha).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

P_UNCERTAIN, P_STANDING, P_SITTING, P_LYING = range(4)
F_NONE, F_SUSPECTED, F_CONFIRMED, F_UNCERTAIN = range(4)


@dataclass(frozen=True)
class Params:
    p_min: float = 0.60        # confianza mínima para publicar una postura
    p_fall: float = 0.50       # probabilidad de caída que abre sospecha
    vz_fall: float = -0.80     # m/s, descenso rápido (regla física independiente)
    z_floor: float = 0.55      # m, centroide "en el suelo" (cama ~0,6-0,8: riesgo R6)
    z_up: float = 1.00         # m, centroide "levantado"
    confirm_s: float = 4.0     # tiempo en el suelo y quieto para confirmar
    still_s: float = 2.0
    resolve_max_s: float = 15.0
    clear_s: float = 5.0       # tiempo levantado para borrar una caída confirmada
    q_min: float = 0.30        # calidad mínima de pista
    ood_max: int = 3           # nº máx. de características fuera de rango


@dataclass(frozen=True)
class Inputs:
    """Lo que el firmware tiene en cada evaluación (2 Hz) para una pista."""
    t: float
    probs: tuple              # (de pie, sentado, tumbado, caída)
    z_c: float
    vz_min: float             # mínimo de vz en la ventana
    still_s: float
    quality: float
    occluded: bool
    ood_count: int


class TrackDecision:
    def __init__(self, p: Params = Params()):
        self.p = p
        self.fall = F_NONE
        self.t_susp = 0          # ms
        self.t_up = None         # ms

    def update(self, x: Inputs):
        p = self.p
        probs = np.asarray(x.probs, dtype=np.float64)
        # Para la postura se exige evidencia reciente. Para la caída no: quien
        # yace quieto tras caer deja de dar detecciones, y eso no puede
        # impedir confirmarla. Basta con que la pista exista y no esté tapada.
        trusted_fall = not x.occluded and x.ood_count <= p.ood_max
        trusted = trusted_fall and x.quality >= p.q_min

        # --- postura -------------------------------------------------------
        k = int(np.argmax(probs[:3]))
        conf = float(probs[k] / max(probs[:3].sum(), 1e-6))
        posture = (k + 1) if (trusted and conf >= p.p_min) else P_UNCERTAIN

        # --- caída ---------------------------------------------------------
        # Los tiempos se comparan en milisegundos enteros: una alarma no puede
        # depender del redondeo de coma flotante (con float, 9,4 - 5,4 < 4).
        tm = int(round(x.t * 1000))
        ms = lambda s: int(round(s * 1000))  # noqa: E731
        trigger = probs[3] >= p.p_fall or (x.vz_min <= p.vz_fall and x.z_c < p.z_floor)
        if self.fall == F_NONE:
            if trigger and trusted_fall:
                self.fall, self.t_susp = F_SUSPECTED, tm
        elif self.fall == F_SUSPECTED:
            if not trusted_fall:
                self.fall = F_UNCERTAIN
            elif x.z_c > p.z_up:
                self.fall = F_NONE                      # se levantó / falsa alarma
            elif (tm - self.t_susp >= ms(p.confirm_s) and x.z_c < p.z_floor
                  and x.still_s >= p.still_s):
                self.fall, self.t_up = F_CONFIRMED, None
            elif tm - self.t_susp >= ms(p.resolve_max_s):
                self.fall = F_UNCERTAIN                 # no se resuelve: se avisa como incierta
        elif self.fall in (F_CONFIRMED, F_UNCERTAIN):
            if trusted_fall and x.z_c > p.z_up:
                self.t_up = tm if self.t_up is None else self.t_up
                if tm - self.t_up >= ms(p.clear_s):
                    self.fall, self.t_up = F_NONE, None
            else:
                self.t_up = None
                if self.fall == F_UNCERTAIN and trusted_fall and x.z_c < p.z_floor and x.still_s >= p.still_s:
                    self.fall = F_CONFIRMED
        return posture, conf, self.fall


def inputs_from_window(c, win: np.ndarray, t: float, probs, lo=None, hi=None, used=None) -> Inputs:
    """Construye Inputs a partir de una ventana (W, n) en unidades físicas."""
    last = win[-1]
    ood = 0
    if lo is not None:
        idx = used if used is not None else np.arange(c.n)
        ood = int(np.sum((last[idx] < lo) | (last[idx] > hi)))
    return Inputs(t=t, probs=tuple(float(v) for v in probs), z_c=float(last[c.index("z_centroid")]),
                  vz_min=float(win[:, c.index("vz")].min()), still_s=float(last[c.index("still_s")]),
                  quality=float(last[c.index("quality")]), occluded=bool(last[c.index("occluded")] > .5),
                  ood_count=ood)
