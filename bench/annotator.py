"""Keyboard ground-truth annotator (no camera).

The operator presses a key at the moment each step of the script happens.
Time comes from the PC clock: sync it over NTP before starting (on Windows:
Settings -> Time -> Sync now). A known offset can be given with --offset-ms
and is corrected when writing.

  python bench/annotator.py --out truth_S03_R1.csv --person S03

Keys: i start · f end · e enter · s leave · 1 standing · 2 sitting · 3 lying
      c fall · l get up · n note · z undo the last one
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from events import Truth, fmt_t, write_truth  # noqa: E402

KEYS = {"i": "start", "f": "end", "e": "enter", "s": "leave", "1": "standing", "2": "sitting",
        "3": "lying", "c": "fall", "l": "get_up", "n": "note"}


class Session:
    """Annotator logic, kept apart from the UI so it can be tested."""

    def __init__(self, path, person: str = "", offset_ms: float = 0.0, clock=time.time):
        self.path, self.person, self.offset, self.clock = Path(path), person, offset_ms / 1000, clock
        self.events: list[Truth] = []

    def key(self, k: str, note: str = "") -> Truth | None:
        if k == "z":
            if self.events:
                self.events.pop()
            self.save()
            return None
        if k not in KEYS:
            return None
        e = Truth(self.clock() - self.offset, KEYS[k], self.person, note)
        self.events.append(e)
        self.save()          # saved on every key press: a crash loses nothing
        return e

    def save(self):
        write_truth(self.path, self.events)


def gui(s: Session):
    import tkinter as tk
    root = tk.Tk()
    root.title("radar60 annotator")
    tk.Label(root, text=__doc__.split("Keys:")[1], justify="left", font=("Consolas", 11)).pack(padx=12, pady=6)
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
            log.insert(tk.END, f"{fmt_t(x.t)}  {x.event:8s} {x.note}")
        if e is None and k != "z":
            root.bell()
    root.bind("<Key>", on_key)
    root.mainloop()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--person", default="")
    ap.add_argument("--offset-ms", type=float, default=0.0, help="PC clock minus NTP time")
    a = ap.parse_args()
    gui(Session(a.out, a.person, a.offset_ms))
