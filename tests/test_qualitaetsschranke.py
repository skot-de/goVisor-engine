"""Die Qualitätsschranke selbst — ungetestete Prüflogik ist bloß Hoffnung.

Sie ist das Werkzeug, das zwischen den Etappen des Rückstau-Abbaus entscheidet, ob
weitergefahren werden darf. Wenn sie eine Verschlechterung übersieht, läuft der Abbau
fröhlich weiter und produziert stundenlang schlechtere Daten — teurer als jeder Fehlalarm.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _schranke():
    spec = importlib.util.spec_from_file_location(
        "qs", ROOT / "scripts/qualitaetsschranke.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _etappe(**kw):
    grund = {"ts": "2026-08-24T14:00:00+00:00", "aufrufe": 200, "vergaben": 100,
             "usd": 3.0, "usd_je_vergabe": 0.030, "bodenanteil": 1.0,
             "boden_treffer": 200, "boden_gesamt": 200, "punkte_je_vergabe": 40.0,
             "verwerfung": 0.12, "leer": 0, "abgebrochen": 0, "ohne_preis": 0}
    grund.update(kw)
    return grund


def _rot(befunde):
    return [t for a, t in befunde if a == "rot"]


def test_alles_im_rahmen_ergibt_keinen_roten_befund():
    qs = _schranke()
    assert _rot(qs.bewerte(_etappe(), _etappe(), 0.01, True)) == []


def test_undichter_preisdeckel_faellt_auf():
    """⚠ Der reale Fall: 304 von 311 Aufrufen liefen am Bodenpreis vorbei, 48 % zu viel
    gezahlt — und der Kontostand fiel dabei völlig plausibel."""
    qs = _schranke()
    r = _rot(qs.bewerte(_etappe(bodenanteil=0.02, boden_treffer=4, boden_gesamt=200),
                        _etappe(), 0.01, True))
    assert any("Preisdeckel ist undicht" in t for t in r)


def test_einbrechende_ausbeute_faellt_auf():
    """Das Kernrisiko im Dauerbetrieb: ein Modell wird schlechter, ohne Ankündigung."""
    qs = _schranke()
    r = _rot(qs.bewerte(_etappe(punkte_je_vergabe=30.0), _etappe(punkte_je_vergabe=40.0),
                        0.01, True))
    assert any("Ausbeute" in t and "Modell prüfen" in t for t in r)


def test_kleine_schwankung_der_ausbeute_ist_kein_alarm():
    qs = _schranke()
    assert _rot(qs.bewerte(_etappe(punkte_je_vergabe=37.0),
                           _etappe(punkte_je_vergabe=40.0), 0.01, True)) == []


def test_steigende_verwerfung_faellt_auf():
    """Die ehrlichere Zahl: mehr behauptet, weniger belegt."""
    qs = _schranke()
    r = _rot(qs.bewerte(_etappe(verwerfung=0.25), _etappe(verwerfung=0.12), 0.01, True))
    assert any("behauptet mehr" in t for t in r)


def test_luecke_zwischen_buch_und_abrechnung_faellt_auf():
    qs = _schranke()
    assert any("Abweichung" in t for t in _rot(qs.bewerte(_etappe(), _etappe(), 0.29, True)))
    # ... in beide Richtungen: das Buch darf auch nicht ZU VIEL melden
    assert any("Abweichung" in t for t in _rot(qs.bewerte(_etappe(), _etappe(), -0.29, True)))


def test_muell_faellt_auf():
    qs = _schranke()
    r = _rot(qs.bewerte(_etappe(leer=10, abgebrochen=5), _etappe(), 0.01, True))
    assert any("leere" in t for t in r)


def test_rote_testsuite_ist_immer_rot():
    qs = _schranke()
    assert _rot(qs.bewerte(_etappe(), _etappe(), 0.01, False)) == ["Testsuite"]


def test_erste_etappe_vergleicht_nicht_und_alarmiert_nicht():
    """Ohne Voretappe gibt es keinen Maßstab — dann wird nichts behauptet."""
    qs = _schranke()
    befunde = qs.bewerte(_etappe(punkte_je_vergabe=5.0), None, 0.01, True)
    assert _rot(befunde) == []
    assert any(a == "grau" for a, _ in befunde)


def test_steigende_stueckkosten_fallen_auf():
    qs = _schranke()
    r = _rot(qs.bewerte(_etappe(usd_je_vergabe=0.050), _etappe(usd_je_vergabe=0.030),
                        0.01, True))
    assert any("Stückkosten" in t for t in r)
