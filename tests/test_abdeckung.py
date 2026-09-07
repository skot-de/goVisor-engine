"""Die Abdeckungs-Sonde — und warum drei vorhandene Wächter das Loch nicht sahen.

Am 2026-09-07 hatte Luxemburg für Juli NULL Bekanntmachungen und für August 16 statt ~250.
Drei Wächter liefen jede Nacht und schwiegen; drei bereits geholte Vergabeunterlagen fanden
deshalb keine Ausschreibung.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SKRIPT = WURZEL / "scripts" / "pruefe_abdeckung.py"
QUELLE = SKRIPT.read_text(encoding="utf-8")
LAUF = (WURZEL / "scripts" / "daily_leads.sh").read_text(encoding="utf-8")


def _modul():
    spec = importlib.util.spec_from_file_location("_pa", SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _modul()


def test_vergleicht_nur_die_ted_herkunft():
    """⚠ Silber trägt in drei von vier Ländern weitere Quellen, die TED nicht kennt. Gegen
    die Gesamtzahl gemessen meldete die Sonde im ersten Anlauf 116 bis 388 % „Abdeckung"
    und hätte eine fehlende TED-Lieferung dort NIE sehen können — genau den Fall, für den
    sie gebaut ist."""
    assert M.TED_HERKUNFT == ("legacy", "eforms")
    kern = QUELLE.split("def _silber(")[1].split("\ndef ")[0]
    assert "schema_gen in" in kern


def test_der_laufende_monat_zaehlt_nicht():
    """Er füllt sich noch; ein Rückstand dort ist der Normalzustand, kein Befund."""
    kern = QUELLE.split("def main(")[1]
    assert "m = (m - dt.timedelta(days=1)).replace(day=1)" in kern


def test_schwelle_laesst_den_normalbereich_durch():
    """⚠ Die TED-Facette zählt mehr, als uns gehört (EU-Einrichtungen unter jeder
    Länderfacette). Gemessen liegt der Normalbereich bei 91 bis 103 %. Eine Schwelle bei
    95 % erzeugte einen Wächter, der jede Nacht schreit — und abgeschaltet wird."""
    assert 'default=0.8' in QUELLE


def test_alle_aktiven_laender_haben_einen_ted_code():
    """Ein Land ohne Code würde stillschweigend übersprungen — dann prüft die Sonde es nie."""
    from govisor.laender import AKTIV
    fehlt = [l for l in AKTIV if l not in M.ALPHA3]
    assert not fehlt, f"kein TED-Code hinterlegt: {fehlt}"


def test_sonde_laeuft_im_tageslauf():
    """Sonst ist sie gebaut und nicht verdrahtet — die Fehlerklasse, wegen der es sie gibt."""
    assert "scripts/pruefe_abdeckung.py" in LAUF


def test_projektpfad_vor_dem_govisor_import():
    """Der Tageslauf läuft unter launchd ohne PYTHONPATH; ein Import davor bricht stumm ab."""
    i_pfad = QUELLE.index("sys.path.insert(0, str(ROOT))")
    i_imp = QUELLE.index("from govisor.laender import AKTIV")
    assert i_pfad < i_imp
