"""Genera los STL de la carcasa, la tapa de techo y el cupón de radomo, y una
lámina de vistas con la transmisión del radomo a 60 GHz.

  python mechanical/generar.py            -> mechanical/stl/*.stl, docs/img/mecanica.png

Física del radomo (incidencia normal, lámina dieléctrica con pérdidas):
la transmisión es máxima cuando el espesor es múltiplo de λ/2 dentro del
material, t = λ0 / (2·sqrt(εr)). Como εr del filamento impreso no se conoce con
precisión (2,6–3,0), se imprime un cupón escalonado y se elige el escalón que
da más SNR con el kit (fase F4). Mismos parámetros que radomo.scad.

Las piezas se mallan por vóxeles: en Z, las capas se alinean con el espesor del
radomo para que este sea exacto; en XY la resolución es 0,4 mm (ancho de boquilla).
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

EPS_R = 2.8
TAN_D = 0.01
F0 = 60.6e9
LAMBDA0 = 299_792_458.0 / F0 * 1e3                    # mm
T_RADOME = LAMBDA0 / (2 * np.sqrt(EPS_R))             # mm
GAP = LAMBDA0                                          # antena-radomo: múltiplo de λ0/2
PCB_R = 30.0
WALL = 2.0
H_INNER = 14.0
R_IN = PCB_R + 0.4
R_OUT = R_IN + WALL
DXY = 0.4


def slab_transmission_db(t_mm, eps_r=EPS_R, tan_d=TAN_D, f=F0):
    """|T|² (dB) de una lámina a incidencia normal."""
    n = np.sqrt(eps_r * (1 - 1j * tan_d))
    k0 = 2 * np.pi * f / 299_792_458.0
    g = (1 - n) / (1 + n)
    ph = np.exp(-1j * n * k0 * np.asarray(t_mm) * 1e-3)
    T = (1 - g ** 2) * ph / (1 - g ** 2 * ph ** 2)
    return 20 * np.log10(np.abs(T))


# ---------------------------------------------------------------- vóxeles
class Grid:
    def __init__(self, x0, x1, y0, y1, zs):
        self.x = np.arange(x0 + DXY / 2, x1, DXY)
        self.y = np.arange(y0 + DXY / 2, y1, DXY)
        self.zb = np.asarray(zs)                       # bordes en z (no uniformes)
        self.z = 0.5 * (self.zb[1:] + self.zb[:-1])
        self.X, self.Y = np.meshgrid(self.x, self.y, indexing="ij")
        self.R = np.hypot(self.X, self.Y)
        self.v = np.zeros((len(self.x), len(self.y), len(self.z)), bool)

    def zmask(self, z0, z1):
        return (self.z > z0) & (self.z < z1)

    def add(self, mask2d, z0, z1, value=True):
        zm = self.zmask(z0, z1)
        self.v[np.ix_(np.ones(len(self.x), bool), np.ones(len(self.y), bool), zm)] |= False
        sub = self.v[:, :, zm]
        sub[mask2d] = value
        self.v[:, :, zm] = sub


def mesh(g: Grid):
    """Caras de vóxel expuestas -> triángulos (malla cerrada)."""
    v = np.pad(g.v, 1)
    xb = np.concatenate([[g.x[0] - DXY / 2], g.x + DXY / 2])
    yb = np.concatenate([[g.y[0] - DXY / 2], g.y + DXY / 2])
    zb = g.zb
    tris = []
    for axis in range(3):
        for sgn in (1, -1):
            nb = np.roll(v, -sgn, axis=axis)
            face = v & ~nb
            i, j, k = np.nonzero(face[1:-1, 1:-1, 1:-1])
            if not len(i):
                continue
            x0, x1 = xb[i], xb[i + 1]
            y0, y1 = yb[j], yb[j + 1]
            z0, z1 = zb[k], zb[k + 1]
            if axis == 0:
                xx = x1 if sgn > 0 else x0
                q = [(xx, y0, z0), (xx, y1, z0), (xx, y1, z1), (xx, y0, z1)]
            elif axis == 1:
                yy = y1 if sgn > 0 else y0
                q = [(x0, yy, z0), (x0, yy, z1), (x1, yy, z1), (x1, yy, z0)]
            else:
                zz = z1 if sgn > 0 else z0
                q = [(x0, y0, zz), (x1, y0, zz), (x1, y1, zz), (x0, y1, zz)]
            P = [np.stack([np.broadcast_to(c, i.shape) for c in p], 1) for p in q]
            if sgn < 0:
                P = P[::-1]
            tris.append(np.stack([P[0], P[1], P[2]], 1))
            tris.append(np.stack([P[0], P[2], P[3]], 1))
    return np.concatenate(tris)


def write_stl(path: Path, tris: np.ndarray, name: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    rec = np.zeros(len(tris), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"], rec["v"] = n, tris
    with open(path, "wb") as f:
        f.write(name.encode()[:80].ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        f.write(rec.tobytes())


def zedges(*segments):
    """Bordes en z: cada tramo (z0, z1, paso) se divide en capas enteras."""
    out = [segments[0][0]]
    for z0, z1, step in segments:
        n = max(1, int(round((z1 - z0) / step)))
        out += list(np.linspace(z0, z1, n + 1)[1:])
    return np.array(out)


# ---------------------------------------------------------------- piezas
def carcasa() -> Grid:
    H = T_RADOME + GAP + H_INNER
    g = Grid(-R_OUT - 1, R_OUT + 1, -R_OUT - 1, R_OUT + 1,
             zedges((0, T_RADOME, T_RADOME / 4), (T_RADOME, T_RADOME + GAP, 0.25), (T_RADOME + GAP, H, 0.3)))
    disc = g.R <= R_OUT
    g.add(disc, 0, T_RADOME)                                  # radomo plano, espesor λ/2 exacto
    g.add((g.R <= R_OUT) & (g.R > R_IN), 0, H)                 # pared
    ang = np.degrees(np.arctan2(g.Y, g.X)) % 360
    for a in (0, 120, 240):                                    # apoyos: la placa queda a GAP del radomo
        sector = (np.abs(((ang - a + 180) % 360) - 180) < 4) & (g.R > R_IN - 3) & (g.R <= R_IN)
        g.add(sector, T_RADOME, T_RADOME + GAP)
    for a in range(30, 360, 60):                               # ventilación lejos del radar
        slot = (np.abs(((ang - a + 180) % 360) - 180) < 2.0) & (g.R > R_IN - .1)
        zm = g.zmask(T_RADOME + GAP + 8, T_RADOME + GAP + 12)
        sub = g.v[:, :, zm]
        sub[slot] = False
        g.v[:, :, zm] = sub
    return g


def tapa() -> Grid:
    R = R_OUT + 6
    g = Grid(-R - 1, R + 1, -R - 1, R + 1, zedges((0, 2.4, 0.3), (2.4, 6.4, 0.4)))
    plate = (g.R <= R) & ~((np.abs(g.X) < 7) & (np.abs(g.Y) < 4.5))   # paso del cable USB-C
    for sx in (-1, 1):
        plate &= np.hypot(g.X - sx * (R - 4), g.Y) > 2.1                  # tornillos/tacos
    g.add(plate, 0, 2.4)
    lip = (g.R <= R_IN - 0.2) & (g.R > R_IN - 1.4)                         # encaje a presión en la carcasa
    g.add(lip, 2.4, 6.4)
    return g


def cupon() -> Grid:
    steps = [1.2 + 0.1 * i for i in range(8)]
    g = Grid(0, 8 * 22, 0, 20, zedges((0, 1.9, 0.05)))
    for i, t in enumerate(steps):
        g.add((g.X >= i * 22) & (g.X < i * 22 + 20), 0, t)
    return g


def edges(c):
    return np.concatenate([[c[0] - DXY / 2], c + DXY / 2])


def lamina(parts, out: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(14, 4.6))
    # 1) sección de la carcasa con la placa y la tapa
    ax = fig.add_subplot(1, 3, 1)
    g = parts["carcasa"]
    j = len(g.y) // 2
    sec = g.v[:, j, :].T
    ax.pcolormesh(edges(g.x), g.zb, np.ma.masked_where(~sec, sec), cmap="Greys", vmin=0, vmax=1.4, shading="flat")
    zpcb = T_RADOME + GAP
    ax.add_patch(plt.Rectangle((-PCB_R, zpcb), 2 * PCB_R, 1.6, color="tab:green", alpha=.7, label="placa Ø60"))
    ax.add_patch(plt.Rectangle((-3.25, zpcb - 0.9), 6.5, 0.9, color="tab:orange", label="BGT60TR13C (antenas)"))
    gt = parts["tapa"]
    st = gt.v[:, len(gt.y) // 2, :].T
    Htot = T_RADOME + GAP + H_INNER
    ax.pcolormesh(edges(gt.x), Htot + 6.4 - gt.zb[::-1], np.ma.masked_where(~st[::-1], st[::-1]), cmap="Blues", vmin=0, vmax=1.4,
                  shading="flat")
    ax.annotate(f"radomo {T_RADOME:.2f} mm (λ/2 en εr={EPS_R})", (0, T_RADOME / 2), (5, -6),
                arrowprops=dict(arrowstyle="->"), fontsize=8)
    ax.annotate(f"antena–radomo {GAP:.2f} mm (λ0)", (0, T_RADOME + GAP / 2), (-30, -8),
                arrowprops=dict(arrowstyle="->"), fontsize=8)
    ax.set_aspect("equal")
    ax.set_ylim(-12, Htot + 10)
    ax.set_title("Sección (techo arriba, suelo abajo)")
    ax.set_xlabel("mm")
    ax.legend(fontsize=7, loc="upper right")
    # 2) transmisión del radomo
    ax = fig.add_subplot(1, 3, 2)
    t = np.linspace(0.5, 4, 400)
    for er in (2.6, 2.8, 3.0):
        ax.plot(t, slab_transmission_db(t, er), label=f"εr = {er}")
    ax.axvspan(1.2, 1.9, color="tab:orange", alpha=.15, label="escalones del cupón")
    ax.axvline(T_RADOME, ls=":", c="k")
    ax.set_xlabel("espesor (mm)")
    ax.set_ylabel("pérdida por paso (dB)")
    ax.set_ylim(-4, 0.2)
    ax.set_title("Radomo a 60,6 GHz (tan δ = 0,01), una pasada")
    ax.legend(fontsize=8)
    # 3) vista 3D gruesa
    ax = fig.add_subplot(1, 3, 3, projection="3d")
    c = parts["carcasa"]
    step = 5
    vv = c.v[::step, ::step, ::2]
    ax.voxels(vv, facecolors="#cfd8dc", edgecolor="#90a4ae", linewidth=0.2)
    ax.set_box_aspect((1, 1, (T_RADOME + GAP + H_INNER) / (2 * R_OUT + 2)))
    ax.set_axis_off()
    ax.view_init(35, -60)
    ax.set_title("Carcasa (vista simplificada)")
    fig.suptitle("Mecánica: carcasa de techo, radomo λ/2 y cupón de calibración")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=105)


def main():
    parts = {"carcasa": carcasa(), "tapa": tapa(), "cupon_radomo": cupon()}
    for name, g in parts.items():
        tris = mesh(g)
        write_stl(HERE / "stl" / f"{name}.stl", tris, f"radar60 {name}")
        print(f"{name}: {len(tris)} triángulos")
    lamina(parts, ROOT / "docs" / "img" / "mecanica.png")
    print(f"radomo: {T_RADOME:.3f} mm; pérdida por paso {slab_transmission_db(T_RADOME):.2f} dB; "
          f"con 1,0 mm: {slab_transmission_db(1.0):.2f} dB")


if __name__ == "__main__":
    main()
