"""Huelle, damit `pruefe-eu-mittel.mjs` in der Suite und im Nachtlauf mitlaeuft.

Die eigentliche Pruefung steht in der Sonde. Hier steht nur, was sie startet — ohne
diese Datei liefe sie nirgends, und das waere dieselbe Fehlerklasse („gebaut, nicht
verdrahtet") eine Ebene ueber dem, was sie prueft.
"""
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SONDE = WURZEL / "web" / "scripts" / "pruefe-eu-mittel.mjs"


def test_die_sonde_laeuft_gruen():
    """Rendert den Anforderungsblock aus `explorerCore.js` in allen drei Zustaenden.

    Gegengeprueft am 2026-10-04: die Sonde wird rot, wenn (a) die EU-Zeile aus
    `explorerCore.js` verschwindet, (b) sie auch bei `null` erscheint, (c) das Feld
    nicht mehr aus `export_web_leads.py` kommt.
    """
    if not shutil.which("node"):
        return
    if not list((WURZEL / "web" / "data").glob("leads-*.json")):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True,
                       cwd=WURZEL, timeout=600)
    assert r.returncode == 0, r.stdout[-900:] + r.stderr[-400:]
    assert "EU-kofinanziert" in r.stdout
