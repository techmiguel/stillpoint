"""Schematic readability pass for hardware/stillpoint.kicad_sch.

The schematic connects pins through net labels placed on the pin ends. This script:
  * turns every pin label so its text runs away from the symbol body (no more labels
    lying across a pin row or on top of each other);
  * puts the reference and value of 2-pin passives beside the body, clear of the labels.
Connectivity is untouched: label positions never move. Run ERC afterwards.

  python tools/sch_tidy.py
"""
from __future__ import annotations

import math
import re
from pathlib import Path

SCH = Path(__file__).resolve().parents[1] / "hardware" / "stillpoint.kicad_sch"
PASSIVES = ("Device:C", "Device:R", "Device:FerriteBead_Small")


def parse(s: str, i: int = 0):
    """Minimal s-expression parser: returns (tree, end index). Strings keep their quotes off."""
    out = []
    i = s.index("(", i) + 1
    tok = ""
    while i < len(s):
        c = s[i]
        if c == "(":
            sub, i = parse(s, i)
            out.append(sub)
            continue
        if c == ")":
            if tok:
                out.append(tok)
            return out, i + 1
        if c == '"':
            j = i + 1
            while s[j] != '"':
                j += 2 if s[j] == "\\" else 1
            out.append(s[i + 1:j])
            i = j + 1
            continue
        if c.isspace():
            if tok:
                out.append(tok)
                tok = ""
        else:
            tok += c
        i += 1
    raise ValueError("unbalanced")


def find(node, key):
    return [n for n in node if isinstance(n, list) and n and n[0] == key]


def lib_pins(tree):
    """lib_id -> list of (x, y, angle) pin connection points in symbol units (y up)."""
    libs = {}
    for sym in find(find(tree, "lib_symbols")[0], "symbol"):
        pins = []

        def walk(n):
            for c in n:
                if isinstance(c, list):
                    if c and c[0] == "pin":
                        at = find(c, "at")[0]
                        pins.append((float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0))
                    else:
                        walk(c)
        walk(sym)
        libs[sym[1]] = pins
    return libs


def lib_bodies(tree):
    """(lib_id, unit) -> (xmin, ymin, xmax, ymax) of the body rectangle, symbol units (y up)."""
    out = {}
    for sym in find(find(tree, "lib_symbols")[0], "symbol"):
        for sub in find(sym, "symbol"):
            unit = int(sub[1].rsplit("_", 2)[1])
            for r in find(sub, "rectangle"):
                (x0, y0), (x1, y1) = (map(float, find(r, k)[0][1:3]) for k in ("start", "end"))
                box = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
                for u in ([unit] if unit else range(1, 9)):
                    old = out.get((sym[1], u))
                    if old is None or (box[2] - box[0]) * (box[3] - box[1]) > (old[2] - old[0]) * (old[3] - old[1]):
                        out[(sym[1], u)] = box      # the largest rectangle is the body outline
    return out


def to_sheet(px, py, ang, at, mirror):
    """Pin point and outward direction (degrees, sheet frame, y down) for an instance."""
    x0, y0, rot = at
    if mirror == "x":
        py, ang = -py, -ang
    elif mirror == "y":
        px, ang = -px, 180 - ang
    r = math.radians(rot)
    sx = px * math.cos(r) - py * math.sin(r)
    sy = px * math.sin(r) + py * math.cos(r)
    # pin angle points from the connection point into the body; outward is the opposite
    out = (ang + 180 + rot) % 360
    return (round(x0 + sx, 3), round(y0 - sy, 3)), out


def main():
    s = SCH.read_text(encoding="utf-8")
    tree, _ = parse(s)
    libs = lib_pins(tree)
    pin_dir = {}        # sheet point -> (outward direction, is a 2-pin passive)
    passives = {}       # reference -> (lib_id, x, y, rot)
    bodies = lib_bodies(tree)
    ics = {}            # (reference, unit) -> body top-left corner
    for inst in find(tree, "symbol"):
        lib = find(inst, "lib_id")[0][1]
        at = find(inst, "at")[0]
        at = (float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0)
        m = find(inst, "mirror")
        mirror = m[0][1] if m else None
        for px, py, ang in libs.get(lib, []):
            p, out = to_sheet(px, py, ang, at, mirror)
            pin_dir[p] = (out, lib in PASSIVES or lib == "Connector:TestPoint")
        ref = next(p[2] for p in find(inst, "property") if p[1] == "Reference")
        unit = int(find(inst, "unit")[0][1]) if find(inst, "unit") else 1
        if lib in PASSIVES:
            passives[ref] = (lib, *at)
        elif (lib, unit) in bodies and at[2] == 0 and not mirror:
            x0, _, _, y1 = bodies[(lib, unit)]
            ics[(ref, unit)] = (at[0] + x0, at[1] - y1)     # body top-left corner on the sheet

    # 1) labels point away from the body
    n_lab = 0

    def fix_label(m):
        nonlocal n_lab
        x, y = float(m.group(2)), float(m.group(3))
        hit = pin_dir.get((round(x, 3), round(y, 3)))
        if hit is None:
            return m.group(0)
        d = int(round(hit[0] / 90.0)) % 4 * 90
        rot = d                     # a label at angle d reads away from the pin in direction d
        if hit[1] and d in (90, 270):
            rot = 0                 # passives stacked in rows: horizontal labels stay clear of each other
        just = "left bottom" if rot in (0, 90) else "right bottom"
        body = re.sub(r"\(justify [^)]*\)", f"(justify {just})", m.group(5))
        n_lab += 1
        return f'{m.group(1)}(at {m.group(2)} {m.group(3)} {rot}){m.group(4)}{body}'
    s = re.sub(r'(\n\t\(label "[^"]*"\n\t\t)\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)(.*?)(\(effects.*?\n\t\t\))',
               fix_label, s, flags=re.S)

    # 2) passive fields beside the body
    n_fld = 0

    def fix_fields(m):
        nonlocal n_fld
        block = m.group(0)
        ref = re.search(r'\(property "Reference" "([^"]+)"', block).group(1)
        um = re.search(r'\n\t\t\(unit (\d+)\)', block)
        unit = int(um.group(1)) if um else 1
        if ref in passives:
            lib, x, y, rot = passives[ref]
            if int(rot) % 180 == 0:     # pins up/down: text to the right of the body, horizontal
                pos = {"Reference": (x + 2.54, y - 1.27, "left"), "Value": (x + 2.54, y + 1.27, "left")}
            else:                       # pins left/right: reference above, value below, centred
                pos = {"Reference": (x, y - 2.54, None), "Value": (x, y + 2.54, None)}
        elif (ref, unit) in ics:
            # ICs: above the top-left corner, right-aligned to the body edge, where no pin label goes
            x0, y0 = ics[(ref, unit)]
            rot = 0
            pos = {"Reference": (x0, y0 - 3.81, "right"), "Value": (x0, y0 - 1.27, "right")}
        else:
            return block

        def one(fm):
            name = fm.group(1)
            if name not in pos:
                return fm.group(0)
            px, py, j = pos[name]
            body = fm.group(3)
            body = re.sub(r"\n\t\t\t\t\(justify [^)]*\)", "", body)
            if j:
                body = body.replace("\n\t\t\t\t)\n\t\t\t)", f"\n\t\t\t\t)\n\t\t\t\t(justify {j})\n\t\t\t)", 1)
            # field angles are relative to the symbol: cancel its rotation so text reads horizontally
            return f'(property "{name}" "{fm.group(2)}"\n\t\t\t(at {px:g} {py:g} {int(rot) % 180}){body}'
        n_fld += 1
        return re.sub(r'\(property "(Reference|Value)" "([^"]*)"\n\t\t\t\(at [^)]*\)(.*?\n\t\t\))', one, block,
                      flags=re.S)
    s = re.sub(r'\n\t\(symbol\n\t\t\(lib_id "[^"]+"\).*?\n\t\)(?=\n)', fix_fields, s, flags=re.S)
    SCH.write_text(s, encoding="utf-8", newline="")
    print(f"labels oriented: {n_lab}, symbols tidied: {n_fld}")


if __name__ == "__main__":
    main()
