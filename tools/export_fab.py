"""Fabrication files for the rev A board (JLCPCB), always from the current .kicad_pcb.

  python tools/export_fab.py            -> hardware/fabrication/

Gerber (4 copper layers + mask, silkscreen, paste, outline), Excellon drills, BOM and CPL in
JLCPCB format, schematic PDF and board STEP.
CPL rotations are KiCad's: check them in the JLCPCB viewer before ordering
(sign-off HUM-CPL-001 in verification/pcb).
"""
import csv
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / "hardware"
PCB = HW / "stillpoint.kicad_pcb"
SCH = HW / "stillpoint.kicad_sch"
OUT = HW / "fabrication"
CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
NOT_ASSEMBLED = ("TP", "FID", "J2")      # test pads, fiducials, Tag-Connect cable footprint


def run(*args):
    r = subprocess.run([CLI, *map(str, args)], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"kicad-cli {' '.join(map(str, args[:3]))} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout


def assembled(ref):
    return not ref.startswith(NOT_ASSEMBLED)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    gerb = OUT / "gerber"
    gerb.mkdir(parents=True)
    layers = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
    run("pcb", "export", "gerbers", "--layers", layers, "--subtract-soldermask", "-o", gerb, PCB)
    run("pcb", "export", "drill", "--format", "excellon", "--drill-origin", "absolute", "--excellon-units", "mm",
        "--excellon-separate-th", "--generate-map", "--map-format", "gerberx2", "-o", gerb, PCB)
    with zipfile.ZipFile(OUT / "stillpoint_revA_gerber.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(gerb.iterdir()):
            z.write(f, f.name)

    # BOM (JLCPCB: Comment, Designator, Footprint, LCSC Part #) from the schematic netlist
    net = OUT / "stillpoint.xml"
    run("sch", "export", "netlist", "--format", "kicadxml", "-o", net, SCH)
    groups = OrderedDict()
    for c in ET.parse(net).getroot().find("components"):
        ref = c.get("ref")
        if not assembled(ref):
            continue
        f = {x.get("name"): (x.text or "") for x in c.find("fields")}
        fp = c.findtext("footprint").split(":")[-1]
        key = (c.findtext("value"), fp, f.get("LCSC", ""), f.get("MPN", ""), f.get("Manufacturer", ""))
        groups.setdefault(key, []).append(ref)
    net.unlink()

    def refkey(r):
        p = r.rstrip("0123456789")
        return (p, int(r[len(p):] or 0))

    with open(OUT / "BOM_JLCPCB.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "Manufacturer", "MPN", "Qty"])
        for (val, fp, lcsc, mpn, man), refs in sorted(groups.items(), key=lambda kv: refkey(sorted(kv[1], key=refkey)[0])):
            refs = sorted(refs, key=refkey)
            w.writerow([val, ",".join(refs), fp, lcsc, man, mpn, len(refs)])

    # CPL (JLCPCB: Designator, Mid X, Mid Y, Layer, Rotation)
    pos = OUT / "pos.csv"
    run("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "--use-drill-file-origin",
        "--exclude-dnp", "-o", pos, PCB)
    rows = list(csv.DictReader(open(pos, encoding="utf-8")))
    pos.unlink()
    with open(OUT / "CPL_JLCPCB.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in rows:
            if assembled(r["Ref"]):
                w.writerow([r["Ref"], r["PosX"] + "mm", r["PosY"] + "mm",
                            "Top" if r["Side"].lower().startswith("top") else "Bottom", r["Rot"]])

    run("sch", "export", "pdf", "-o", OUT / "stillpoint_schematic.pdf", SCH)
    run("pcb", "export", "step", "--subst-models", "--force", "-o", OUT / "stillpoint.step", PCB)
    print("ok:", ", ".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
