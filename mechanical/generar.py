"""Lámina de mecánica: sección acotada, transmisión del radomo a 60 GHz y vista
3D de las piezas reales exportadas por FreeCAD (freecad_carcasa.py).

  python mechanical/generar.py      -> docs/img/mecanica.png

Física del radomo (incidencia normal, lámina con pérdidas): la transmisión es
máxima cuando el espesor es múltiplo de λ/2 dentro del material,
t = λ0 / (2·sqrt(εr)). Como εr del filamento impreso no se conoce con precisión
(2,6–3,0), se imprime el cupón escalonado y se elige el escalón con más SNR
medida con el kit (fase F4).
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CAD = HERE / "cad"

EPS_R = 2.8
TAN_D = 0.01
F0 = 60.6e9
LAMBDA0 = 299_792_458.0 / F0 * 1e3
T_RADOME = LAMBDA0 / (2 * np.sqrt(EPS_R))


def slab_transmission_db(t_mm, eps_r=EPS_R, tan_d=TAN_D, f=F0):
    """|T|² (dB) de una lámina dieléctrica a incidencia normal."""
    n = np.sqrt(eps_r * (1 - 1j * tan_d))
    k0 = 2 * np.pi * f / 299_792_458.0
    g = (1 - n) / (1 + n)
    ph = np.exp(-1j * n * k0 * np.asarray(t_mm) * 1e-3)
    T = (1 - g ** 2) * ph / (1 - g ** 2 * ph ** 2)
    return 20 * np.log10(np.abs(T))


def read_stl(path: Path) -> np.ndarray:
    data = path.read_bytes()
    if data[:5] == b"solid" and b"facet" in data[:400]:
        v = [list(map(float, ln.split()[1:4])) for ln in data.decode().splitlines() if ln.strip().startswith("vertex")]
        return np.array(v).reshape(-1, 3, 3)
    (n,) = struct.unpack_from("<I", data, 80)
    rec = np.frombuffer(data, dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")], count=n, offset=84)
    return rec["v"].astype(float)


def lamina(out: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    chk = json.loads((CAD / "comprobaciones.json").read_text(encoding="utf-8"))
    gap, t = chk["antena_radomo_mm"], chk["radomo_mm"]
    R_out = chk["diametro_mm"] / 2
    R_in, H = R_out - 2.0, chk["altura_total_mm"] - 2.4
    z_ant, z_pcb = t + gap, t + gap + 0.9
    fig = plt.figure(figsize=(15, 5))
    ax = fig.add_subplot(1, 3, 1)
    grey = dict(color="#78909c")
    ax.add_patch(plt.Rectangle((-R_out, 0), 2 * R_out, t, **grey))
    for s in (-1, 1):
        ax.add_patch(plt.Rectangle((s * R_in if s > 0 else -R_out, 0), 2.0, H, **grey))
        ax.add_patch(plt.Rectangle((s * (R_in - 3) if s > 0 else -R_in, t), 3.0, z_pcb - t, color="#b0bec5"))
    ax.add_patch(plt.Rectangle((-30, z_pcb), 60, 1.6, color="tab:green", alpha=.8, label="placa Ø60"))
    ax.add_patch(plt.Rectangle((-3.25, z_ant), 6.5, 0.9, color="tab:orange", label="BGT60TR13C (antenas abajo)"))
    ax.add_patch(plt.Rectangle((-R_out - 6, H), 2 * R_out + 12, 2.4, color="#90caf9", label="tapa (techo)"))
    for s in (-1, 1):
        ax.add_patch(plt.Rectangle((s * (R_in - 1.4) if s > 0 else -(R_in - 0.2), H - 4), 1.2, 4, color="#90caf9"))
    r_fov = gap * np.tan(np.radians(60))
    ax.fill([-r_fov, 0, r_fov], [t, z_ant, t], color="tab:red", alpha=.15, label="cono útil ±60°")
    ax.annotate(f"radomo {t:.2f} mm", (12, t / 2), (14, -7), arrowprops=dict(arrowstyle="->"), fontsize=8)
    ax.annotate(f"antena–radomo {gap:.2f} mm", (0, t + gap / 2), (-32, -9),
                arrowprops=dict(arrowstyle="->"), fontsize=8)
    ax.text(-R_out, H + 4, f"Ø{2 * R_out:.1f} × {chk['altura_total_mm']:.1f} mm · libre sobre placa "
            f"{chk['altura_libre_sobre_placa_mm']:.1f} mm · material en el cono: {chk['material_en_cono_FOV_mm3']} mm³",
            fontsize=7)
    ax.set_xlim(-R_out - 8, R_out + 8)
    ax.set_ylim(-12, H + 8)
    ax.set_aspect("equal")
    ax.set_title("Sección acotada (comprobaciones de FreeCAD)")
    ax.set_xlabel("mm")
    ax.legend(fontsize=6.5, loc="lower right")

    ax = fig.add_subplot(1, 3, 2)
    tt = np.linspace(0.5, 4, 400)
    for er in (2.6, 2.8, 3.0):
        ax.plot(tt, slab_transmission_db(tt, er), label=f"εr = {er}")
    ax.axvspan(1.2, 1.9, color="tab:orange", alpha=.15, label="escalones del cupón")
    ax.axvline(T_RADOME, ls=":", c="k")
    ax.set_xlabel("espesor (mm)")
    ax.set_ylabel("pérdida por paso (dB)")
    ax.set_ylim(-4, 0.2)
    ax.set_title("Radomo a 60,6 GHz (tan δ = 0,01)")
    ax.legend(fontsize=8)

    ax = fig.add_subplot(1, 3, 3, projection="3d")
    parts = [("carcasa", "#cfd8dc", 0.0), ("tapa", "#90caf9", H + 18)]
    for name, col, dz in parts:
        tri = read_stl(CAD / f"{name}.stl").copy()
        tri[..., 2] += dz
        ax.add_collection3d(Poly3DCollection(tri, facecolors=col, edgecolors=col, linewidths=0.05, shade=True))
    lim = R_out + 7
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_zlim(-5, H + 25)
    ax.set_box_aspect((1, 1, (H + 30) / (2 * lim)))
    ax.set_axis_off()
    ax.view_init(22, -55)
    ax.set_title("Piezas FreeCAD (explosionado)")
    fig.suptitle("Mecánica: carcasa de techo, radomo λ/2 y tapa con paso de USB-C")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=105)


if __name__ == "__main__":
    lamina(ROOT / "docs" / "img" / "mecanica.png")
    print(f"radomo {T_RADOME:.3f} mm: {slab_transmission_db(T_RADOME):.2f} dB por paso; "
          f"1,0 mm: {slab_transmission_db(1.0):.2f} dB")
