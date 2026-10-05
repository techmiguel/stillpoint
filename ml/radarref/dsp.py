"""Cadena DSP de referencia: rango-Doppler, CFAR, ángulo y micro-movimiento.

Dos caminos en paralelo, a propósito:
  * Camino de movimiento: se resta la media por chirp (MTI) dentro de la trama,
    FFT Doppler y CA-CFAR 2D. Ve a quien se mueve; borra a quien está quieto.
  * Camino de micro-movimiento: el valor a Doppler cero de cada celda de rango
    se acumula ~10 s entre tramas; se elimina la componente continua (muebles)
    y se mide la energía en banda lenta (respiración). Ve a quien está quieto.

El firmware implementa lo mismo en punto fijo (firmware/src/dsp/, fase F2).
Cualquier divergencia se detecta comparando las características (contrato),
no las detecciones intermedias.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np
from scipy.ndimage import uniform_filter

from .config import RadarConfig, Room


@dataclass
class Detection:
    x: float
    y: float
    z: float
    r: float
    vr: float
    power_db: float
    kind: str                 # "move" | "micro"
    micro_db: float = 0.0
    breath_hz: float = 0.0
    breath_snr_db: float = 0.0


def _parabolic(y_m1: float, y0: float, y_p1: float) -> float:
    den = y_m1 - 2 * y0 + y_p1
    return 0.0 if den == 0 else float(np.clip(0.5 * (y_m1 - y_p1) / den, -0.5, 0.5))


class FrontEnd:
    def __init__(self, cfg: RadarConfig, room: Room, cfar_db: float = 14.0,
                 micro_window: int = 100, micro_every: int = 5, r_min: float = 0.35,
                 max_dets: int = 48):
        self.cfg, self.room = cfg, room
        self.cfar = 10 ** (cfar_db / 10)
        self.rwin = np.hanning(cfg.n_samples)
        self.dwin = np.hanning(cfg.n_chirps)[None, :, None]
        self.k_min = int(np.ceil(r_min / cfg.range_res))
        self.k_max = min(cfg.n_range - 2, int(np.hypot(room.mount_h, 4.0) / cfg.range_res))
        self.max_dets = max_dets
        self.W, self.every = micro_window, micro_every
        self.buf: deque = deque(maxlen=micro_window)
        self.frame_idx = 0
        self.sensor = np.array([0.0, 0.0, room.mount_h])
        f = np.fft.fftfreq(micro_window, 1 / cfg.frame_rate_hz)
        self.f_micro = f
        self.band_slow = (f >= 0.1) & (f <= 2.0)
        self.band_fast = (np.abs(f) >= 3.0)
        self.band_breath = (f >= 0.1) & (f <= 0.6)
        self.twin = np.hanning(micro_window)

    # -- geometría ---------------------------------------------------------
    def _to_world(self, r: float, a0: complex, a1: complex, a2: complex):
        ux = np.angle(a1 * np.conj(a0)) / np.pi
        uy = np.angle(a2 * np.conj(a0)) / np.pi
        n = ux * ux + uy * uy
        if n > 0.98:
            s = np.sqrt(0.98 / n)
            ux, uy = ux * s, uy * s
        uz = -np.sqrt(1 - ux * ux - uy * uy)
        p = self.sensor + r * np.array([ux, uy, uz])
        return p

    # -- tramas ------------------------------------------------------------
    def process(self, adc: np.ndarray) -> list[Detection]:
        cfg = self.cfg
        X = np.fft.rfft(adc * self.rwin, axis=-1)[..., :cfg.n_range]   # (rx, chirp, rango)
        dets = self._moving(X)
        self.buf.append(X.mean(axis=1))
        self.frame_idx += 1
        if len(self.buf) == self.W and self.frame_idx % self.every == 0:
            dets += self._micro()
        return [d for d in dets if self.room.inside(d.x, d.y) and not self.room.excluded(d.x, d.y)]

    def _moving(self, X: np.ndarray) -> list[Detection]:
        cfg = self.cfg
        Xm = X - X.mean(axis=1, keepdims=True)
        RD = np.fft.fftshift(np.fft.fft(Xm * self.dwin, axis=1), axes=1)
        P = (np.abs(RD) ** 2).sum(axis=0)                                 # (dop, rango)
        g, t = 1, 4
        big, small = 2 * (g + t) + 1, 2 * g + 1
        s_big = uniform_filter(P, big, mode=("wrap", "nearest")) * big * big
        s_small = uniform_filter(P, small, mode=("wrap", "nearest")) * small * small
        noise = (s_big - s_small) / (big * big - small * small)
        zero = cfg.n_chirps // 2
        loc = P == np.maximum.reduce([np.roll(np.roll(P, i, 0), j, 1)
                                      for i in (-1, 0, 1) for j in (-1, 0, 1)])
        hit = (P > self.cfar * noise) & loc
        hit[zero, :] = False
        hit[:, :self.k_min] = False
        hit[:, self.k_max:] = False
        idx = np.argwhere(hit)
        if len(idx) > self.max_dets:
            idx = idx[np.argsort(P[hit])[::-1][:self.max_dets]]
        out = []
        for d, k in idx:
            dk = _parabolic(P[d, k - 1], P[d, k], P[d, k + 1])
            r = (k + dk) * cfg.range_res
            p = self._to_world(r, RD[0, d, k], RD[1, d, k], RD[2, d, k])
            vr = (d - zero) * cfg.v_res
            out.append(Detection(p[0], p[1], p[2], r, vr, 10 * np.log10(P[d, k] + 1e-12), "move"))
        return out

    def _micro(self) -> list[Detection]:
        cfg = self.cfg
        Z = np.array(self.buf)                                           # (t, rx, rango)
        D = Z - Z.mean(axis=0, keepdims=True)
        F = np.fft.fft(D * self.twin[:, None, None], axis=0)
        S = (np.abs(F) ** 2).sum(axis=1)                                 # (f, rango)
        slow = S[self.band_slow].sum(axis=0)
        fast = S[self.band_fast].mean(axis=0) * self.band_slow.sum()
        slow[:self.k_min] = 0
        slow[self.k_max:] = 0
        floor = np.median(slow[self.k_min:self.k_max]) + 1e-15
        cand = []
        for k in range(self.k_min, self.k_max):
            if slow[k] < slow[k - 1] or slow[k] < slow[k + 1]:
                continue
            ratio = slow[k] / (fast[k] + 1e-15)
            if slow[k] > 8 * floor and ratio > 10:
                cand.append((slow[k], k))
        out = []
        for _, k in sorted(cand, reverse=True)[:8]:
            dk = _parabolic(slow[k - 1], slow[k], slow[k + 1])
            r = (k + dk) * cfg.range_res
            # respiración: espectro de la fase desenrollada de la celda
            ph = np.unwrap(np.angle(D[:, int(np.argmax(np.abs(D[:, :, k]).mean(0))), k]))
            ph = (ph - ph.mean()) * self.twin
            PS = np.abs(np.fft.fft(ph)) ** 2
            bi = int(np.argmax(np.where(self.band_breath, PS, 0)))
            ref = np.median(PS[(self.f_micro >= 0.7)]) + 1e-15
            # Limitación conocida (docs/10_riesgos.md, R3): con 3 RX, dos personas
            # quietas en la misma celda de rango (±6 cm) dan una sola detección
            # con ángulo mezclado. El seguidor mantiene ambas pistas estáticas.
            fi = int(np.argmax(np.where(self.band_slow, S[:, k], 0)))
            p = self._to_world(r, F[fi, 0, k], F[fi, 1, k], F[fi, 2, k])
            out.append(Detection(p[0], p[1], p[2], r, 0.0, 10 * np.log10(slow[k] + 1e-15), "micro",
                                 micro_db=10 * np.log10(slow[k] + 1e-15),
                                 breath_hz=float(self.f_micro[bi]),
                                 breath_snr_db=float(10 * np.log10(PS[bi] / ref))))
        return out
