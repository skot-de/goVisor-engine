"""Sieht der Nutzer, welche Vorgaenge ausgewertete Vergabeunterlagen haben?

⚠ WARUM DIESE DATEI EXISTIERT. `scripts/export_doc_analysis.py` schreibt seit Ticket 23
einen Index ueber alle Auswertungen der Vergabeunterlagen. Am 2026-09-17 ergab ein grep
ueber `web/` NULL Treffer fuer „doc-analysis-index": 10.951 ausgewertete Vorgaenge, samt
Ampel und Pruefpunkten, wurden jede Nacht geschrieben und von niemandem gelesen.

Aufgefallen ist es nicht durch einen Waechter, sondern durch eine Frage in einer
Vorfuehrung: „wo sehe ich, welche Ausschreibungen analysierte Unterlagen haben?"

Die Sonde traegt die eigentliche Pruefung; hier steht nur die Huelle, damit sie im
Nachtlauf mitlaeuft. Ohne diese Huelle liefe sie nirgends — und das waere dieselbe
Fehlerklasse eine Ebene hoeher.
"""
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SONDE = WURZEL / "web" / "scripts" / "pruefe-analyse-sichtbar.mjs"


def test_die_sonde_laeuft_gruen():
    """Fuehrt `applyAnalyse` aus `explorerCore.js` gegen die echten Lead-Dateien.

    ⚠ Eine Wortpruefung waere hier wertlos. Genau so ein Waechter stand schon einmal fuer
    die Cron-Sperre und blieb gruen, nachdem Aufruf UND Import entfernt worden waren.
    Gegengeprueft am 2026-09-17: die Sonde wird rot, wenn (a) die Spalte auf `on:false`
    steht, (b) `applyAnalyse` entfernt wird, (c) keine Datei unter `app/` den Index liest.
    """
    if not shutil.which("node") or not list((WURZEL / "web" / "data").glob("leads-*.json")):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-500:]
    assert "tragen eine Auswertung" in r.stdout
    assert "Auswertungen sind sichtbar" in r.stdout


def test_der_index_traegt_mehr_als_die_ampel():
    """Die Ampel ist als Merkmal unbrauchbar — 88,5 % aller Auswertungen sind gelb.

    Was trennt, ist die Dichte (`pruef` streut 0 bis 186, Median 57). Faellt der Export
    auf „nur Ampel" zurueck, sortiert die Spalte alles auf 0 und die Reihenfolge wird
    zufaellig. Das saehe aus wie ein kaputter Sortierknopf, nicht wie fehlende Daten.
    """
    import json
    datei = WURZEL / "web" / "data" / "doc-analysis-index.json"
    if not datei.exists():
        return
    idx = json.loads(datei.read_text(encoding="utf-8"))
    mit_dichte = [v for v in idx.values() if isinstance(v.get("pruef"), int) and v["pruef"] > 0]
    assert mit_dichte, "kein Eintrag traegt `pruef` — export_doc_analysis.py schreibt wieder nur die Ampel"
    anteil = len(mit_dichte) / len(idx)
    assert anteil > 0.5, f"nur {anteil:.1%} der Auswertungen tragen eine Dichte"
