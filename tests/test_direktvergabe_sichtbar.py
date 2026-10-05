"""Huelle, damit `pruefe-direktvergabe.mjs` in der Suite und im Nachtlauf mitlaeuft."""
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SONDE = WURZEL / "web" / "scripts" / "pruefe-direktvergabe.mjs"


def test_die_sonde_laeuft_gruen():
    """Gegengeprueft am 2026-10-05: rot, wenn (a) die Ansicht das Feld nicht mehr
    liest, (b) der Export die Codeliste nicht findet und rohe Codes ausgibt,
    (c) ein Wortlaut keine Uebersetzung hat — (c) sieht der allgemeine i18n-Waechter
    nicht, weil die Texte als Daten und nicht als Literale in die Ansicht kommen.
    """
    if not shutil.which("node"):
        return
    if not list((WURZEL / "web" / "data").glob("leads-*.json")):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True,
                       cwd=WURZEL, timeout=900)
    assert r.returncode == 0, r.stdout[-900:] + r.stderr[-400:]
    assert "Direktvergabe" in r.stdout
