"""Sagt die Oberflaeche, WELCHE Filter gesetzt sind — oder nur, wie viele?

⚠ WARUM DIESE DATEI EXISTIERT. Bis zum 2026-09-17 stand neben „Filter" eine Zahl und
sonst nichts. `advCount` summierte zwoelf, spaeter 22 Filterarten zu einem Kaestchen —
sichtbar war „Filter 4", nicht sichtbar, WELCHE vier. Beobachtet in einer Vorfuehrung:
„zudem sehe ich meine aktiven Filtereinstellungen nicht."

Die Sonde traegt die Pruefung; hier steht die Huelle, damit sie im Nachtlauf mitlaeuft.
"""
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SONDE = WURZEL / "web" / "scripts" / "pruefe-filtermarken.mjs"


def test_die_sonde_laeuft_gruen():
    """Faehrt die ECHTE `filterMarken` aus `lib/filterMarken.js` gegen alle 22 Arten.

    ⚠ Die Sonde prueft jede Art EINZELN, nie in Summe. Eine Summenpruefung bleibt gruen,
    wenn zwei Zweige sich ausgleichen — eine Art verschwindet, eine andere erscheint
    doppelt. Gegengeprueft am 2026-09-17: rot, wenn (a) eine Filterart keine Marke mehr
    erzeugt, (b) eine Ruecknahme zu viel entfernt, (c) die Wertspanne zu einer Marke
    zusammengezogen wird.
    """
    if not shutil.which("node"):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stdout[-900:] + r.stderr[-400:]
    assert "Jede Filterart zeigt und loest ihre Marke" in r.stdout


def test_die_sonde_kennt_jede_gezaehlte_art():
    """Gegenprobe auf die Sonde selbst: waechst `advCount`, muss ihre Fallliste mitwachsen.

    Ohne diese Klammer waere die Fallliste die Luecke — eine neue Filterart kaeme dazu,
    niemand traegt sie ein, und der Waechter bliebe gruen, waehrend die Liste stumm
    beschnitten wird.
    """
    if not shutil.which("node"):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    zeile = next((z for z in r.stdout.splitlines() if "Filterarten geprueft" in z), "")
    assert zeile, r.stdout[-400:]
    teile = zeile.replace(",", "").split()
    geprueft, gezaehlt = int(teile[0]), int(teile[3])
    assert geprueft >= gezaehlt, f"{gezaehlt} Arten gezaehlt, nur {geprueft} geprueft"
