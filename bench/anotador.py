"""Anotador de verdad de terreno por teclado (sin cámara).

El operador pulsa una tecla en el momento en que ocurre cada cosa del guion.
La hora sale del reloj del PC: sincronizarlo por NTP antes de empezar (en
Windows: Configuración -> Hora -> Sincronizar ahora). La desviación conocida se
puede anotar con --desfase-ms y se corrige al escribir.

  python bench/anotador.py --salida verdad_S03_R1.csv --persona S03

Teclas: i inicio · f fin · e entra · s sale · 1 de pie · 2 sentado · 3 tumbado
        c caída · l levanta · n nota · z deshacer el último
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eventos import Truth, fmt_t, write_truth  # noqa: E402

KEYS = {"i": "inicio", "f": "fin", "e": "entra", "s": "sale", "1": "de_pie", "2": "sentado",
        "3": "tumbado", "c": "caida", "l": "levanta", "n": "nota"}


class Session:
    """Lógica del anotador, separada de la interfaz para poder probarla."""

    def __init__(self, path, persona: str = "", offset_ms: float = 0.0, clock=time.time):
        self.path, self.persona, self.offset, self.clock = Path(path), persona, offset_ms / 1000, clock
        self.events: list[Truth] = []

    def key(self, k: str, nota: str = "") -> Truth | None:
        if k == "z":
            if self.events:
                self.events.pop()
            self.save()
            return None
        if k not in KEYS:
            return None
        e = Truth(self.clock() - self.offset, KEYS[k], self.persona, nota)
        self.events.append(e)
        self.save()          # se guarda en cada pulsación: un cierre inesperado no pierde datos
        return e

    def save(self):
        write_truth(self.path, self.events)


def gui(s: Session):
    import tkinter as tk
    root = tk.Tk()
    root.title("Anotador radar60")
    tk.Label(root, text=__doc__.split("Teclas:")[1], justify="left", font=("Consolas", 11)).pack(padx=12, pady=6)
    log = tk.Listbox(root, width=60, height=14, font=("Consolas", 10))
    log.pack(padx=12, pady=6)
    note = tk.Entry(root, width=60)
    note.pack(padx=12, pady=(0, 10))

    def on_key(ev):
        if root.focus_get() is note and ev.char not in ("\r",):
            return
        k = ev.char.lower()
        e = s.key(k, note.get() if k == "n" else "")
        if k == "n":
            note.delete(0, tk.END)
        log.delete(0, tk.END)
        for x in s.events[-14:]:
            log.insert(tk.END, f"{fmt_t(x.t)}  {x.evento:8s} {x.nota}")
        if e is None and k != "z":
            root.bell()
    root.bind("<Key>", on_key)
    root.mainloop()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", required=True)
    ap.add_argument("--persona", default="")
    ap.add_argument("--desfase-ms", type=float, default=0.0, help="reloj del PC menos hora NTP")
    a = ap.parse_args()
    gui(Session(a.salida, a.persona, a.desfase_ms))
