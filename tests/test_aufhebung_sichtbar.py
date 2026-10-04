"""Huelle, damit `pruefe-aufhebung.mjs` in der Suite und im Nachtlauf mitlaeuft.

Ohne diese Datei liefe die Sonde nirgends — dieselbe Fehlerklasse eine Ebene ueber dem,
was sie prueft.
"""
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SONDE = WURZEL / "web" / "scripts" / "pruefe-aufhebung.mjs"


def test_die_sonde_laeuft_gruen():
    """Gegengeprueft am 2026-10-05: die Sonde wird rot, wenn (a) `aufgehoben` aus dem
    Export faellt, (b) die Ansicht das Merkmal nicht mehr liest, (c) ein Grund keine
    Uebersetzung hat — Fall (c) sieht der allgemeine i18n-Waechter nicht, weil die
    Texte als Daten und nicht als Literale in die Ansicht kommen.
    """
    if not shutil.which("node"):
        return
    if not (WURZEL / "web" / "data" / "vorgang").is_dir():
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True,
                       cwd=WURZEL, timeout=900)
    assert r.returncode == 0, r.stdout[-900:] + r.stderr[-400:]
    assert "aufgehoben" in r.stdout
