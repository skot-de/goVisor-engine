"""Dauerverfahren zeigen keine erfundene Frist.

⚠ DER BEFUND, UND WER IHN GEFUNDEN HAT. Open-House- und Qualifizierungsverfahren stehen
dauerhaft offen; die Quellen tragen dafuer ein Platzhalterdatum (01.01.2100 in AT,
31.12.2099 in DE). Die Oberflaeche rechnete daraus eine Frist: „noch 26.761 Tage" in der
Liste, „in -24307 Mon." im Detail. Gemessen am 2026-09-25 bei 390 Vorgaengen. Aufgefallen
ist es Sven beim Nachsehen zu einem Drahthersteller, keiner Pruefung — die Zahl stand seit
Monaten sichtbar in der Liste.

⚠ DIE GEGENRICHTUNG IST DIE WICHTIGERE HAELFTE. Von 2.522 Open-House-Vorgaengen im Bestand
tragen nur diese 390 ein Platzhalterdatum; die uebrigen 2.132 haben eine ECHTE Frist. Eine
Regel „open_house zeigt nie eine Frist" waere bequem und falsch.

⚠ ERKANNT WIRD AM VERFAHREN, NICHT AM DATUM. Alle 390 tragen `verfahren: 'open_house'`.
Eine Datumsschwelle allein waere geraten und laege beim naechsten Platzhalter daneben.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SONDE = WURZEL / "web" / "scripts" / "pruefe-dauerverfahren.mjs"
CORE = WURZEL / "web" / "lib" / "explorerCore.js"


def _lauf():
    return subprocess.run(["node", str(SONDE)], capture_output=True, text=True,
                          cwd=WURZEL / "web", timeout=120)


def _mit_mutation(alt: str, neu: str):
    echt = CORE.read_text(encoding="utf-8")
    assert echt.count(alt) == 1, f"Anker nicht eindeutig ({echt.count(alt)}x): {alt[:70]}"
    try:
        CORE.write_text(echt.replace(alt, neu, 1), encoding="utf-8")
        return _lauf()
    finally:
        CORE.write_text(echt, encoding="utf-8")


def test_dauerverfahren_zeigen_laufend():
    r = _lauf()
    assert r.returncode == 0, r.stdout[-1200:] + r.stderr[-400:]
    assert "keine erfundene Frist" in r.stdout


def test_die_sonde_sieht_die_zurueckgerechnete_frist():
    """Gegenprobe mit dem Zustand vom 2026-09-25."""
    r = _mit_mutation("if(l.verfahren === 'open_house' && (l.tage == null || l.tage > 3650)){",
                      "if(false){")
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl wieder 26.761 Tage dastehen"
    assert "26.761" in r.stdout or "laufend" in r.stdout


def test_die_sonde_sieht_wenn_echte_fristen_verschwinden():
    """⚠ Die wichtigere Richtung: 2.132 Open-House-Vorgaenge HABEN eine Frist."""
    r = _mit_mutation("if(l.verfahren === 'open_house' && (l.tage == null || l.tage > 3650)){",
                      "if(l.verfahren === 'open_house'){")
    assert r.returncode == 1, (
        "die Sonde bleibt gruen, obwohl Dauerverfahren mit echter Frist ihren Countdown "
        "verlieren")
    assert "Countdown" in r.stdout


def test_die_sonde_sieht_eine_reine_datumsschwelle():
    """⚠ Ohne die Kennzeichnung waere es Raten: eine gewoehnliche Vergabe mit fernem Datum
    wuerde stillschweigend zum Dauerverfahren erklaert."""
    r = _mit_mutation("if(l.verfahren === 'open_house' && (l.tage == null || l.tage > 3650)){",
                      "if(l.tage == null || l.tage > 3650){")
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl allein das Datum entscheidet"
    assert "Kennzeichnung entscheidet" in r.stdout
