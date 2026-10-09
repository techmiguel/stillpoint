"""Remove vias that KiCad's DRC reports as dangling (connected on one layer only)."""
import pcbnew, json, subprocess, os, sys
PCB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hardware", "stillpoint.kicad_pcb")
CLI = r"C:/Program Files/KiCad/10.0/bin/kicad-cli.exe"
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build", "drc_dangling.json")
gone = []
for it_ in range(4):
    subprocess.run([CLI, "pcb", "drc", "--format", "json", "--severity-all", "-o", out, PCB], capture_output=True)
    d = json.load(open(out, encoding="utf-8"))
    descs = [(v["type"], i["description"], i["pos"]["x"], i["pos"]["y"]) for v in d["violations"]
             if v["type"] in ("via_dangling", "track_dangling") for i in v["items"]]
    if not descs:
        break
    b = pcbnew.LoadBoard(PCB)
    dead = []
    for t in b.GetTracks():
        isvia = t.Type() == pcbnew.PCB_VIA_T
        for typ, desc, x, y in descs:
            if typ == "via_dangling" and isvia:
                q = t.GetPosition()
                if abs(q.x / 1e6 - x) < 0.01 and abs(q.y / 1e6 - y) < 0.01:
                    dead.append(t)
            elif typ == "track_dangling" and not isvia and t.GetNetname() in desc:
                for q in (t.GetStart(), t.GetEnd()):
                    if abs(q.x / 1e6 - x) < 0.01 and abs(q.y / 1e6 - y) < 0.01:
                        dead.append(t)
    dead = list({id(t): t for t in dead}.values())
    for t in dead:
        gone.append((t.GetNetname(), "via" if t.Type() == pcbnew.PCB_VIA_T else "track"))
        b.Remove(t)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(PCB, b)
print("removed:", gone)
