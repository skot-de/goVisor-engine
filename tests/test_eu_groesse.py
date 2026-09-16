"""EU-Marktvermessung (`scripts/miss_eu_groesse.py`).

Zwei Dinge muessen halten: die Sperre vor der unvalidierten Firmenaufloesung, und die
monatsweise Zerlegung, ohne die die grossen Laender untermessen wuerden.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUELLE = ROOT / "scripts" / "miss_eu_groesse.py"


def test_aufgeloest_verweigert_ohne_ausdrueckliche_freigabe():
    """Eine stille Falschzahl ist schlimmer als keine.

    `--aufgeloest` liefert nachweislich zu hohe Werte (DE August 2025: 5.144 statt 4.600
    ueber Namen), und zwar ohne dass man es der Ausgabe ansieht. Bis zur Gegenprobe gegen
    die eigenen DE-Daten bleibt der Weg gesperrt. Wer die Sperre entfernt, muss den
    Modulkopf mitaendern — dieser Test zwingt ihn dazu.
    """
    ergebnis = subprocess.run(
        [sys.executable, "-B", str(QUELLE), "--firmen", "--aufgeloest", "--land", "DE"],
        capture_output=True, text=True, cwd=ROOT, timeout=60)
    assert ergebnis.returncode != 0, "--aufgeloest muss ohne Freigabe abbrechen"
    assert "VERWEIGERT" in ergebnis.stderr, "die Sperre muss sagen, warum sie sperrt"


def test_monatsweise_zerlegung_bleibt():
    """Der Deckel der Suchschnittstelle ist unsichtbar, die Gegenmassnahme muss es nicht sein.

    TED liefert hoechstens 15.000 Treffer je Abfrage und meldet das nicht. Ohne
    `_monate` waeren genau die grossen Laender untermessen: DE 58.406 Zuschlaege,
    PL 45.345, FR 32.591, ES 26.661, CZ 26.006, RO 24.182, BG 16.747.
    """
    quelle = QUELLE.read_text(encoding="utf-8")
    assert "API_DECKEL" in quelle and "_monate" in quelle
    baum = ast.parse(quelle)
    namen = {k.name for k in ast.walk(baum) if isinstance(k, ast.FunctionDef)}
    assert "_monate" in namen, "ohne Monatszerlegung schneidet TED still ab"


def test_kennung_erkennt_vorgangs_uuids():
    """Eine UUID identifiziert nichts ausserhalb ihres Dokuments.

    Wer darauf entdoppelt, ERHOEHT die Firmenzahl. `winner-identifier` traegt beides
    nebeneinander, gemessen am 2026-09-16 in fuenf Laendern.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("eu_groesse", QUELLE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert not m.kennung_taugt("8fb4b194-6b79-4319-b113-9fac454095f7")
    assert not m.kennung_taugt("")
    assert not m.kennung_taugt(None)
    assert m.kennung_taugt("DE310303402")      # Steuernummer
    assert m.kennung_taugt("54205494500416")   # SIRET
    assert m.kennung_taugt("440 953 776 00018")  # SIREN mit Leerzeichen
