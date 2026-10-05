"""Der Tageslauf muss den Baum laufen, in dem er LIEGT — nicht einen fest verdrahteten.

⚠ WARUM. Bis zum 2026-10-05 stand in `scripts/daily_leads.sh` ein fester Pfad auf den
Haupt-Baum. Nachts lief damit, was dort gerade ausgecheckt war; am 2026-10-05 war das ein
Zweig ohne den KMU-Fix vom 01.09. Fünf Wochen lang schrieb alter Code in
`web/data/strategie.json`, und in den Arbeitsbäumen sah alles grün aus, weil `data` und
`web/data` dort Symlinks in den Haupt-Baum sind.

⚠ Die naheliegende Lösung — `ROOT` aus `dirname "$0"` — ist FALSCH, und zwar aus einem Grund,
der nicht auf der Hand liegt: der Lauf legt beim Start eine **Selbstkopie** in `/tmp` an und
führt die aus (gegen das Nachladen einer Datei, die gerade bearbeitet wird; hat den Lauf am
17.08. und 19.08. getötet). In der Kopie zeigt `dirname "$0"` ins Temp-Verzeichnis.

Deshalb wird der Ort VOR der Kopie bestimmt, exportiert und von der Kopie übernommen. Dieser
Test fährt genau das ab — den Kopf des echten Skripts, in zwei verschiedenen Scheinbäumen.
Ein reiner Textabgleich („steht da noch ein fester Pfad?") würde die Selbstkopie nicht prüfen,
und gerade die ist die Stelle, an der es bricht.
"""
from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TAGESLAUF = ROOT / "scripts" / "daily_leads.sh"


def _scheinbaum(wo: pathlib.Path) -> pathlib.Path:
    """Ein Baum mit dem KOPF des echten Skripts, abgeschnitten vor der eigentlichen Arbeit."""
    (wo / "scripts").mkdir(parents=True, exist_ok=True)
    kopf = []
    for zeile in TAGESLAUF.read_text(encoding="utf-8").splitlines():
        if zeile.startswith('PY="python3 -u"'):
            kopf += ['echo "ROOT=$ROOT"', "exit 0"]
            break
        kopf.append(zeile)
    ziel = wo / "scripts" / "daily_leads.sh"
    ziel.write_text("\n".join(kopf) + "\n", encoding="utf-8")
    ziel.chmod(0o755)
    return ziel


def _lauf(skript: pathlib.Path, umgebung: dict | None = None) -> str:
    import os
    u = {k: v for k, v in os.environ.items() if k != "GOVISOR_ROOT"}
    u.update(umgebung or {})
    p = subprocess.run(["/bin/bash", str(skript)], capture_output=True, text=True, env=u)
    assert p.returncode == 0, p.stderr[-400:]
    m = re.search(r"^ROOT=(.*)$", p.stdout, re.M)
    assert m, f"keine ROOT-Zeile in der Ausgabe: {p.stdout[:300]}"
    return m.group(1).strip()


def test_der_lauf_nimmt_den_baum_in_dem_er_liegt(tmp_path):
    """Zwei Bäume, dasselbe Skript, zwei verschiedene Antworten."""
    a, b = tmp_path / "baum_a", tmp_path / "baum_b"
    assert _lauf(_scheinbaum(a)) == str(a.resolve())
    assert _lauf(_scheinbaum(b)) == str(b.resolve())


def test_der_ort_ueberlebt_die_selbstkopie(tmp_path):
    """⚠ DIE EIGENTLICHE PRUEFUNG. Der Lauf `exec`t sich in eine Kopie unter `/tmp`; dort ist
    `dirname "$0"` das Temp-Verzeichnis. Dass hier trotzdem der Baum herauskommt, geht nur
    ueber die exportierte Variable — ein gesetztes `GOVISOR_ROOT` muss also gewinnen, genau
    wie es die Kopie von ihrem Original bekommt."""
    a, b = tmp_path / "baum_a", tmp_path / "baum_b"
    _scheinbaum(a)
    assert _lauf(_scheinbaum(b), {"GOVISOR_ROOT": str(a)}) == str(a)


def test_ohne_erkennbaren_baum_bleibt_die_rueckfallebene(tmp_path):
    """Ein Aufruf ueber eine Symlink-Kette kann an einem Ort ohne `scripts/` landen. Dann
    soll der Lauf ARBEITEN statt ins Leere zu laufen — mit dem festen Pfad als letzter
    Ebene, nicht als Regelfall."""
    wo = tmp_path / "kaputt"
    skript = _scheinbaum(tmp_path / "echt")
    wo.mkdir()
    ziel = wo / "daily_leads.sh"
    ziel.write_bytes(skript.read_bytes())
    ziel.chmod(0o755)
    assert _lauf(ziel) == "/Users/svko_macmini/PROJEKTE/claude_code/C09_govisor"


def test_der_feste_pfad_steht_nur_noch_als_rueckfallebene():
    """Er darf vorkommen — aber nicht mehr als Zuweisung an `ROOT`."""
    text = "\n".join(z for z in TAGESLAUF.read_text(encoding="utf-8").splitlines()
                     if not z.lstrip().startswith("#"))
    assert not re.search(r'^ROOT="/Users/[^"]*C09_govisor"', text, re.M), (
        "`ROOT` wird wieder fest verdrahtet — damit laeuft nachts, was zufaellig im "
        "Haupt-Baum ausgecheckt ist.")
    assert 'GOVISOR_ROOT' in text, "die Uebergabe an die Selbstkopie fehlt"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
