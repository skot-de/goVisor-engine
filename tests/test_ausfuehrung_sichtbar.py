"""Huelle, damit `pruefe-ausfuehrung.mjs` in der Suite und im Nachtlauf mitlaeuft."""
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SONDE = WURZEL / "web" / "scripts" / "pruefe-ausfuehrung.mjs"


def test_die_sonde_laeuft_gruen():
    """Gegengeprueft am 2026-10-05: rot, wenn (a) die vorbehaltene Ausfuehrung nicht
    das Ausschlusszeichen traegt, (b) eine blosse Auflage es faelschlich traegt,
    (c) die Kette keine Bedingungen liefert, (d) eine Uebersetzung fehlt.

    ⚠ (a) ist der Fall, auf den es ankommt: bei `reserved-execution=yes` darf ein
    gewoehnlicher Bieter gar nicht mitbieten. Als freundliches „i" daneben waere das
    eine Verharmlosung, die ihn die Arbeit an einem unmoeglichen Angebot kostet.
    """
    if not shutil.which("node"):
        return
    if not list((WURZEL / "web" / "data").glob("leads-*.json")):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True,
                       cwd=WURZEL, timeout=900)
    assert r.returncode == 0, r.stdout[-900:] + r.stderr[-400:]
    assert "Ausfuehrungsbedingungen" in r.stdout
