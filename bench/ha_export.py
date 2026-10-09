"""Converts a Home Assistant history export into device events.

In HA: History -> pick entities and period -> Download data (CSV with columns
entity_id,state,last_changed). A mapping file says which entity is which
signal of which device:

  # map.csv
  entity_id,device,signal
  binary_sensor.radar60_occupancy,radar60,occupancy
  binary_sensor.radar60_fall,radar60,fall
  binary_sensor.presence_sensor_fp2_presence_sensor_1,aqara_fp2,occupancy

  python bench/ha_export.py history.csv map.csv events.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from events import DevEvent, parse_t, write_dev  # noqa: E402

ON = {"on", "detected", "occupied", "true", "1", "home"}
OFF = {"off", "clear", "not_occupied", "false", "0", "not_home"}


def convert(history_csv, map_csv) -> list[DevEvent]:
    with open(map_csv, newline="", encoding="utf-8") as f:
        mapping = {r["entity_id"]: (r["device"], r["signal"]) for r in csv.DictReader(f)}
    out = []
    with open(history_csv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            m = mapping.get(r["entity_id"])
            if not m:
                continue
            s = r["state"].strip().lower()
            if s in ON:
                v = 1.0
            elif s in OFF:
                v = 0.0
            else:
                try:
                    v = float(s)
                except ValueError:
                    continue          # unavailable / unknown: a gap, not an event
            out.append(DevEvent(parse_t(r["last_changed"]), m[0], m[1], v))
    return sorted(out, key=lambda e: e.t)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    ev = convert(sys.argv[1], sys.argv[2])
    write_dev(sys.argv[3], ev)
    print(f"{len(ev)} events -> {sys.argv[3]}")
