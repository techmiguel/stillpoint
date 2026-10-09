"""Product renders for the README and the project page, made with KiCad's ray tracer.

The FreeCAD enclosure and lid (mechanical/cad/*.stl) are added as extra 3D models to a
temporary copy of the board, so board, enclosure and lid share one scene and one light
set. Each view is rendered on a transparent background and composited on a soft studio
backdrop with a contact shadow.

  python tools/render_views.py   -> docs/img/{exploded,board_top,board_bottom}.png, docs/share/{iso_top,iso_bot}.webp, og.jpg
"""
from __future__ import annotations

import struct
import subprocess
import tempfile
import uuid
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / "hardware"
CAD = ROOT / "mechanical" / "cad"
OUT = ROOT / "docs" / "img"
SHARE = ROOT / "docs" / "share"
CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"

Z_PCB = 1.478 + 4.947 + 0.9          # board bottom above the radome face (mechanical/enclosure.py)
H = Z_PCB + 14.0                     # enclosure height (lid seat)
TOP = Z_PCB + 1.6                    # board top face: the origin of top-side 3D models
SHELL = (0.93, 0.93, 0.91)           # matte white PETG


def read_stl(path: Path) -> np.ndarray:
    data = path.read_bytes()
    (n,) = struct.unpack_from("<I", data, 80)
    rec = np.frombuffer(data, dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")], count=n, offset=84)
    return rec["v"].astype(float)


def stl_to_wrl(stl: Path, wrl: Path, colour, transparency=0.0):
    """VRML 2 with shared vertices and a crease angle, so curved walls shade smoothly."""
    tri = read_stl(stl)
    pts, idx = np.unique(np.round(tri.reshape(-1, 3), 4), axis=0, return_inverse=True)
    faces = idx.reshape(-1, 3)
    s = 1 / 2.54                                     # KiCad VRML units are 0.1 inch
    p = " ".join(f"{x * s:.5f} {y * s:.5f} {z * s:.5f}," for x, y, z in pts)
    f = " ".join(f"{a} {b} {c} -1," for a, b, c in faces)
    wrl.write_text(
        "#VRML V2.0 utf8\nShape {\n appearance Appearance { material Material {"
        f" diffuseColor {colour[0]} {colour[1]} {colour[2]} specularColor 0.04 0.04 0.04"
        f" shininess 0.05 transparency {transparency} }} }}\n"
        f" geometry IndexedFaceSet {{ creaseAngle 0.6 solid FALSE coord Coordinate {{ point [ {p} ] }}"
        f" coordIndex [ {f} ] }}\n}}\n", encoding="utf-8")


def footprint(name: str, model: Path, dz: float) -> str:
    u = lambda: str(uuid.uuid4())  # noqa: E731
    prop = lambda k, v, layer: (f'\t\t(property "{k}" "{v}"\n\t\t\t(at 0 0 0)\n\t\t\t(layer "{layer}")\n'  # noqa: E731
                                f'\t\t\t(hide yes)\n\t\t\t(uuid "{u()}")\n\t\t\t(effects\n\t\t\t\t(font\n'
                                f'\t\t\t\t\t(size 1 1)\n\t\t\t\t\t(thickness 0.15)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n')
    return (f'\t(footprint "render:{name}"\n\t\t(layer "F.Cu")\n\t\t(uuid "{u()}")\n\t\t(at 100 100)\n'
            + prop("Reference", "REN_" + name, "F.SilkS") + prop("Value", name, "F.Fab")
            + '\t\t(attr board_only exclude_from_pos_files exclude_from_bom)\n'
            f'\t\t(model "{model.as_posix()}"\n\t\t\t(offset\n\t\t\t\t(xyz 0 0 {dz:.3f})\n\t\t\t)\n'
            '\t\t\t(scale\n\t\t\t\t(xyz 1 1 1)\n\t\t\t)\n\t\t\t(rotate\n\t\t\t\t(xyz 0 0 0)\n\t\t\t)\n\t\t)\n\t)\n')


def render(board: Path, out: Path, w=1800, h=1350, rotate="", zoom=1.0, side="top", pan=""):
    args = [CLI, "pcb", "render", "-o", str(out), "-w", str(w), "--height", str(h), "--side", side,
            "--quality", "high", "--background", "transparent", "--perspective", "--zoom", str(zoom),
            "--use-board-stackup-colors", "--light-camera", "0.55", "--light-top", "0.45", "--light-side", "0.35"]
    if rotate:
        args += ["--rotate", rotate]
    if pan:
        args += ["--pan", pan]
    r = subprocess.run(args + [str(board)], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stdout + r.stderr)
    a = np.asarray(Image.open(out))[..., 3] > 200          # the object; the floor shadow is fainter
    rows, cols = np.where(a.any(1))[0], np.where(a.any(0))[0]
    margin = 6
    if rows[0] < margin or cols[0] < margin or rows[-1] >= h - margin or cols[-1] >= w - margin:
        render(board, out, w, h, rotate, zoom * 0.85, side, pan)     # clipped: back the camera off


def studio(src: Path, dst: Path, pad=0.10):
    """Keep the object, fade KiCad's floor shadow out around it, and place both on a soft
    light backdrop, so there is no visible floor rectangle."""
    from scipy.ndimage import distance_transform_edt
    rgba = np.asarray(Image.open(src).convert("RGBA")).astype(float)
    alpha = rgba[..., 3] / 255
    obj = alpha > 0.8
    rows, cols = np.where(obj.any(1))[0], np.where(obj.any(0))[0]
    h, w = rows[-1] - rows[0], cols[-1] - cols[0]
    fade = np.exp(-distance_transform_edt(~obj) / (0.06 * max(h, w)))
    a = np.where(obj, alpha, alpha * fade)
    y0, y1 = max(0, rows[0] - int(pad * h)), min(alpha.shape[0], rows[-1] + int(pad * h))
    x0, x1 = max(0, cols[0] - int(pad * w)), min(alpha.shape[1], cols[-1] + int(pad * w))
    rgb, a = rgba[y0:y1, x0:x1, :3], a[y0:y1, x0:x1, None]
    H_, W = a.shape[:2]
    yy, xx = np.mgrid[0:H_, 0:W]
    r = np.hypot((xx - W / 2) / W, (yy - H_ * 0.45) / H_)
    bg = np.clip(247 - 30 * r ** 1.6, 210, 247)[..., None] + np.array([0, 1, 3])
    out = rgb * a + bg * (1 - a)
    Image.fromarray(out.clip(0, 255).astype(np.uint8), "RGB").save(dst, optimize=True)


def main():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        stl_to_wrl(CAD / "enclosure.stl", d / "enclosure.wrl", SHELL)
        stl_to_wrl(CAD / "lid.stl", d / "lid.wrl", SHELL)
        src = (HW / "stillpoint.kicad_pcb").read_text(encoding="utf-8")
        cut = src.rstrip().rfind(")")

        def scene(name, parts):
            b = HW / f"_render_{name}.kicad_pcb"    # next to the project, so ${KIPRJMOD} resolves
            b.write_text(src[:cut] + "".join(parts) + src[cut:], encoding="utf-8")
            return b

        boards = {
            "exploded": scene("exploded", [footprint("enclosure", d / "enclosure.wrl", -TOP - 26),
                                           footprint("lid", d / "lid.wrl", H - TOP + 30)]),
            "board": scene("board", []),
        }
        views = [
            ("exploded", "exploded", dict(rotate="-62,0,28", zoom=0.55)),
            ("board_top", "board", dict(rotate="-38,0,22", zoom=0.95)),
            ("board_bottom", "board", dict(side="bottom", rotate="-38,0,-22", zoom=0.95)),
        ]
        try:
            for name, b, kw in views:
                raw = d / f"{name}.png"
                render(boards[b], raw, **kw)
                studio(raw, OUT / f"{name}.png")
                print("wrote", OUT / f"{name}.png")
                if name.startswith("board_"):
                    cutout(raw, SHARE / ("iso_top.webp" if name == "board_top" else "iso_bot.webp"))
            og(d / "board_top.png", SHARE / "og.jpg")
            print("wrote share assets in", SHARE)
        finally:
            for b in boards.values():
                b.unlink(missing_ok=True)


def cutout(src: Path, dst: Path, width=1300):
    """Transparent board render for the project page (object only, no floor)."""
    im = Image.open(src).convert("RGBA")
    a = np.asarray(im)[..., 3]
    im.putalpha(Image.fromarray(np.where(a > 200, a, 0).astype(np.uint8)))
    im = im.crop(im.getbbox())
    im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(dst, "WEBP", quality=88, method=6)


def og(board_png: Path, dst: Path):
    """1200 x 630 social preview: name, claim and the board."""
    from PIL import ImageDraw, ImageFont
    W, H_ = 1200, 630
    yy, xx = np.mgrid[0:H_, 0:W]
    glow = np.exp(-(((xx - 920) / 460) ** 2 + ((yy - 330) / 360) ** 2))
    bg = np.dstack([13 + 18 * glow, 16 + 20 * glow, 21 + 24 * glow])
    canvas = Image.fromarray(bg.clip(0, 255).astype(np.uint8), "RGB")
    board = Image.open(board_png).convert("RGBA")
    a = np.asarray(board)[..., 3]
    board.putalpha(Image.fromarray(np.where(a > 200, a, 0).astype(np.uint8)))
    board = board.crop(board.getbbox())
    board.thumbnail((500, 540), Image.LANCZOS)
    canvas.paste(board, (W - board.width - 36, (H_ - board.height) // 2), board)
    d = ImageDraw.Draw(canvas)
    font = lambda name, size: ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)  # noqa: E731
    gold, ink, muted = (220, 170, 66), (229, 233, 239), (143, 154, 169)
    d.text((64, 70), "60 GHz RADAR · MATTER OVER THREAD · OPEN HARDWARE", font=font("segoeuib.ttf", 20), fill=muted)
    d.text((60, 120), "Stillpoint", font=font("segoeuib.ttf", 96), fill=ink)
    d.text((64, 262), "It sees the room.", font=font("segoeuib.ttf", 44), fill=ink)
    d.text((64, 318), "It never sees you.", font=font("segoeuib.ttf", 44), fill=gold)
    d.text((64, 410), "Counts people, knows their posture and reports falls,\n"
                      "even someone lying perfectly still. No camera, no cloud.",
           font=font("segoeui.ttf", 24), fill=muted, spacing=10)
    d.text((64, 540), "github.com/techmiguel/stillpoint", font=font("segoeuib.ttf", 22), fill=gold)
    canvas.save(dst, quality=90, optimize=True)


if __name__ == "__main__":
    main()
