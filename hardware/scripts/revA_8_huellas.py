"""Rev A, paso 8: actualiza las huellas desde su biblioteca (atributo SMD/THT y modelo 3D).

  python3 hardware/scripts/revA_8_huellas.py

Las huellas de la placa venían sin `(attr smd)` ni modelo 3D, lo que deja
componentes fuera del fichero de posiciones y del STEP. Se sustituye cada una
por la de su biblioteca conservando posición, cara, giro, enlace con el
esquema, campos y textos, y la red de cada pad. Antes de guardar se comprueba
que todos los pads quedan exactamente donde estaban (si no, no se guarda nada).
"""
from __future__ import annotations

import os
from pathlib import Path

import pcbnew

HW = Path(__file__).resolve().parents[1]
PCB = HW / "radar60.kicad_pcb"
SYS = Path(os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))


def lib_path(nick: str) -> Path:
    return HW / "lib" / "radar60.pretty" if nick == "radar60" else SYS / f"{nick}.pretty"


def pads(fp):
    return sorted((p.GetNumber(), p.GetPosition().x, p.GetPosition().y, p.GetNetname()) for p in fp.Pads())


def main():
    b = pcbnew.LoadBoard(str(PCB))
    old_fps = list(b.GetFootprints())
    new_fps = []
    for old in old_fps:
        nick = str(old.GetFPID().GetLibNickname())
        name = str(old.GetFPID().GetLibItemName())
        new = pcbnew.FootprintLoad(str(lib_path(nick)), name)
        assert new is not None, (nick, name)
        new.SetFPID(old.GetFPID())
        new.SetParent(b)
        new.SetPosition(old.GetPosition())
        if old.GetLayer() == pcbnew.B_Cu:
            new.Flip(new.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        new.SetOrientation(old.GetOrientation())
        new.SetPath(old.GetPath())
        new.SetSheetname(old.GetSheetname())
        new.SetSheetfile(old.GetSheetfile())
        new.SetLocked(old.IsLocked())
        for f in old.GetFields():
            nf = new.GetField(f.GetName()) if new.HasField(f.GetName()) else None
            if nf is None:
                new.SetField(f.GetName(), f.GetText())
                nf = new.GetField(f.GetName())
            nf.SetText(f.GetText())
            nf.SetPosition(f.GetPosition())
            nf.SetVisible(f.IsVisible())
            nf.SetTextSize(f.GetTextSize())
            nf.SetTextThickness(f.GetTextThickness())
            nf.SetTextAngle(f.GetTextAngle())
            nf.SetLayer(f.GetLayer())
        new.SetLibDescription(old.GetLibDescription())
        # marca de pin 1 de U7/U8 desplazada en el paso 7
        if old.GetReference() in ("U7", "U8"):
            for g in new.GraphicalItems():
                if g.GetLayer() == pcbnew.F_SilkS and g.GetClass() == "PCB_SHAPE" and g.GetShapeStr() == "Polygon":
                    g.Move(pcbnew.VECTOR2I(pcbnew.FromMM(0.45), pcbnew.FromMM(-0.87)))
        byname = {}
        for p in old.Pads():
            byname.setdefault(p.GetNumber(), []).append(p)
        used = {}
        for p in new.Pads():
            cands = byname.get(p.GetNumber(), [])
            # pads repetidos (escudo del USB-C): el más cercano
            q = min(cands, key=lambda c: (c.GetPosition() - p.GetPosition()).EuclideanNorm()) if cands else None
            if q is not None:
                p.SetNet(q.GetNet())
        new_fps.append((old, new))
    # comprobación antes de tocar la placa
    for old, new in new_fps:
        a, c = pads(old), pads(new)
        if len(a) != len(c) or any(x[0] != y[0] or abs(x[1] - y[1]) > 1000 or abs(x[2] - y[2]) > 1000
                                   or x[3] != y[3] for x, y in zip(a, c)):
            raise SystemExit(f"{old.GetReference()}: los pads de la biblioteca no coinciden; no se guarda")
    for old, new in new_fps:
        b.Add(new)
    for old, _ in new_fps:      # al final: tras Remove() la capa SWIG deja de ser fiable
        b.Remove(old)
    b.Save(str(PCB))
    print(f"{len(new_fps)} huellas actualizadas desde biblioteca")


if __name__ == "__main__":
    main()
