"""Rev A, paso 3: autorutado del resto con Freerouting y reposición de los planos de GND.

  python3 hardware/scripts/revA_3_autorutado.py [ruta/a/freerouting.jar] [java]

Lo trazado a mano en el paso 2 está bloqueado y Freerouting lo conserva. Los
rellenos de GND de F.Cu, In2 y B.Cu se quitan antes de exportar (Freerouting
los vería como obstáculos) y se reponen después; In1 queda como plano y el
autorutador conecta a él cada pad de GND con una vía.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
from revA_2_radar import gnd_zone  # noqa: E402

PCB = Path(__file__).resolve().parents[1] / "radar60.kicad_pcb"
LOCKS = Path(tempfile.gettempdir()) / "radar60_bloqueos_temporales.json"


def sexpr_end(s: str, i: int) -> int:
    """Índice tras el paréntesis que cierra el que abre en s[i]."""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "(":
            depth += 1
        elif s[j] == ")":
            depth -= 1
            if depth == 0:
                return j + 1
    raise ValueError("s-expresión sin cerrar")


def drop_gnd(dsn: Path):
    """GND va por planos y vías propias: se deja la red (y el plano de In1) sin pines que rutar."""
    s = dsn.read_text(encoding="utf-8")
    i = s.index("(net /GND\n")
    j = sexpr_end(s, i)
    s = s[:i] + "(net /GND (pins))" + s[j:]
    s = npth_keepouts(s)
    dsn.write_text(s, encoding="utf-8")


def npth_keepouts(s: str) -> str:
    """Los agujeros no metalizados salen como pines anónimos (@n) del tamaño del agujero; KiCad les
    exige 0,4 mm de holgura de borde y Freerouting solo aplica la general (0,15): se agrandan 0,5 mm."""
    import re
    names = set(re.findall(r'\(pin (\S+) @\d+ ', s))
    for name in names:
        i = s.index(f"(padstack {name}\n")
        block = s[i:sexpr_end(s, i)]
        big = block.replace(f"(padstack {name}", f"(padstack {name[:-1]}_npth\"" if name.endswith('"')
                            else f"(padstack {name}_npth", 1)
        big = re.sub(r"\((circle|path) (\S+) ([\d.]+)",
                     lambda m: f"({m.group(1)} {m.group(2)} {float(m.group(3)) + 500:g}", big)
        s = s[:i] + big + "\n    " + s[i:]
        new = name[:-1] + '_npth"' if name.endswith('"') else name + "_npth"
        s = re.sub(rf"\(pin {re.escape(name)} (@\d+) ", lambda m: f"(pin {new} {m.group(1)} ", s)
    # agujeros redondos exportados como círculos prohibidos (diámetro + 2 x 0,2): a 0,4 de holgura
    s = re.sub(r'\(keepout "" \(circle (\S+) ([\d.]+) ',
               lambda m: f'(keepout "" (circle {m.group(1)} {float(m.group(2)) + 400:g} ', s)
    return s


def main(jar: str, java: str, rip=()):
    """rip: redes cuyo rutado no bloqueado se levanta para volver a rutarlas."""
    b = pcbnew.LoadBoard(str(PCB))
    kill = [z for z in b.Zones() if z.GetZoneName() in ("GND_F.Cu", "GND_In2.Cu", "GND_B.Cu")]
    kill += [t for t in b.GetTracks() if t.GetNetname() in rip and not t.IsLocked()]
    if rip:
        # despeja el cosido de GND (vías sin pista) en el entorno de los pads de esas redes
        pts = [p.GetPosition() for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname() in rip]
        x0, x1 = min(q.x for q in pts) - pcbnew.FromMM(2), max(q.x for q in pts) + pcbnew.FromMM(2)
        y0, y1 = min(q.y for q in pts) - pcbnew.FromMM(2), max(q.y for q in pts) + pcbnew.FromMM(2)
        ends = {(q.x, q.y) for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"
                for q in (t.GetStart(), t.GetEnd())}
        kill += [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "/GND"
                 and not t.IsLocked() and (t.GetPosition().x, t.GetPosition().y) not in ends
                 and x0 <= t.GetPosition().x <= x1 and y0 <= t.GetPosition().y <= y1]
    temp_locked = []
    if rip:
        # rutado parcial: el resto queda fijo para Freerouting y se desbloquea al terminar
        for t in b.GetTracks():
            if t.GetNetname() not in rip and not t.IsLocked():
                t.SetLocked(True)
                temp_locked.append(t.m_Uuid.AsString())
    LOCKS.write_text(json.dumps(temp_locked))
    for z in kill:
        b.Remove(z)
    tmp = Path(tempfile.mkdtemp())
    dsn, ses = tmp / "radar60.dsn", tmp / "radar60.ses"
    assert pcbnew.ExportSpecctraDSN(b, str(dsn))
    drop_gnd(dsn)
    subprocess.run([java, "-Dgui.enabled=false", "-jar", jar, "-de", str(dsn), "-do", str(ses),
                    "-mp", "200", "-mt", "3", "--gui.enabled=false",
                    "--usage_and_diagnostic_data.disable_analytics=true"], check=True)
    assert pcbnew.ImportSpecctraSES(b, str(ses))
    b.Save(str(PCB))
    # tras ImportSpecctraSES la capa SWIG queda inservible en este proceso: zonas en otro
    subprocess.run([sys.executable, __file__, "--zonas"], check=True)


def zonas():
    b = pcbnew.LoadBoard(str(PCB))
    relock = set(json.loads(LOCKS.read_text())) if LOCKS.exists() else set()
    for t in b.GetTracks():
        if t.m_Uuid.AsString() in relock:
            t.SetLocked(False)
    gnd_zone(b, pcbnew.F_Cu, 0)
    gnd_zone(b, pcbnew.In2_Cu, 0)
    gnd_zone(b, pcbnew.B_Cu, 0, solid=True)
    b.Save(str(PCB))


if __name__ == "__main__" and sys.argv[1:] == ["--zonas"]:
    zonas()
elif __name__ == "__main__":
    # uso: revA_3_autorutado.py [--levantar /RED1,/RED2] [jar] [java]
    args = sys.argv[1:]
    rip = ()
    if args[:1] == ["--levantar"]:
        rip, args = tuple(args[1].split(",")), args[2:]
    main(args[0] if args else "/opt/freerouting/freerouting-2.5.0-executable.jar",
         args[1] if len(args) > 1 else "/usr/lib/jvm/java-25-openjdk-amd64/bin/java", rip)
