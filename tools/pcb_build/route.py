"""Autoroute with Freerouting: export DSN (without the outer GND pours), route, import SES."""
import pcbnew, sys, os, subprocess, time
HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hardware", "stillpoint.kicad_pcb")
import glob
JAVA = os.environ.get("JAVA", "java")
FR = os.environ.get("FREEROUTING_JAR", os.path.join(HERE, "freerouting-2.5.0.jar"))
DSN = os.path.join(HERE, "build", "stillpoint.dsn")
SES = os.path.join(HERE, "build", "stillpoint.ses")
passes = sys.argv[1] if len(sys.argv) > 1 else "60"

b = pcbnew.LoadBoard(PCB)
# unlocked tracks/vias from a previous run go away
for t in list(b.GetTracks()):
    if not t.IsLocked():
        b.Remove(t)
for z in list(b.Zones()):
    if not z.GetIsRuleArea() and z.GetZoneName() in ('GND_TOP', 'GND_BOT'):
        b.Remove(z)
ok = pcbnew.ExportSpecctraDSN(b, DSN)
print("dsn", ok)
if os.path.exists(SES):
    os.remove(SES)
t0 = time.time()
r = subprocess.run([JAVA, "-Djava.awt.headless=true", "-jar", FR, "--gui.enabled=false", "-de", DSN, "-do", SES,
                    "--router.fanout.enabled=false", "--router.autorouter.max_passes=" + passes,
                    "--router.optimizer.enabled=true", "--router.automatic_neckdown=false", "-mt", "6", "-l", "en"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
print("freerouting", r.returncode, round(time.time() - t0), "s")
print("\n".join(l for l in (r.stdout + r.stderr).splitlines() if any(k in l for k in ("pass", "unrouted", "Unrouted", "completed", "ERROR", "error", "incomplete", "score")))[-3000:])
if not os.path.exists(SES):
    sys.exit("no SES")
ok = pcbnew.ImportSpecctraSES(b, SES)
print("ses", ok)
pcbnew.SaveBoard(PCB, b)
