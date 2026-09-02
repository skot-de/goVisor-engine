"""Kennzahl 1 — Aufwand gegen Zeitfenster.

DER BEFUND, gemessen am 2026-09-02 über 3.400 Vorgänge: zwischen Bekanntmachung und Frist
liegen im Median 34 Tage, **unabhängig vom Aufwand**. Von „bis 10 Anforderungen" (33 Tage)
bis „über 100" (35 Tage), Korrelation 0,08. Ein Verfahren mit 186 Anforderungen bekommt
dieselbe Zeit wie eines mit dreien.

⚠ Sie braucht BEIDE Seiten: die Bekanntmachung sagt wann veröffentlicht und wann Frist, die
Unterlagen sagen wie viel Arbeit. Wer nur eine hat, kann sie nicht rechnen.
"""
from __future__ import annotations

import json
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
DATEI = WURZEL / "web" / "data" / "fenster.json"
EXPORT = (WURZEL / "scripts" / "export_fenster.py").read_text(encoding="utf-8")
CORE = (WURZEL / "web" / "lib" / "explorerCore.js").read_text(encoding="utf-8")


def _daten() -> dict:
    return json.loads(DATEI.read_text(encoding="utf-8")) if DATEI.exists() else {}


def test_das_fenster_ist_begrenzt():
    """⚠ Ohne Ober- und Untergrenze verschiebt EIN Rahmenvertrag mit Frist 2029 den Median um
    Wochen, und eine Frist vor der Veröffentlichung ist ein Datenfehler, kein kurzes Fenster."""
    assert "UNTEN, OBEN = 1, 365" in EXPORT
    d = _daten()
    for land, l in (d.get("laender") or {}).items():
        assert 1 <= l["median"] <= 365, f"{land}: Median {l['median']} ausserhalb der Grenzen"
    for tage in (d.get("leads") or {}).values():
        assert 1 <= tage <= 365


def test_die_schwelle_ist_das_zehnte_perzentil():
    """⚠ Erste Fassung nahm das Viertel — die Zeile erschien bei 51 % aller Vorgänge, also bei
    jedem zweiten. Eine Zeile, die immer dasteht, liest bald niemand mehr."""
    assert "bei(0.10)" in EXPORT
    d = _daten()
    for land, l in (d.get("laender") or {}).items():
        assert l["eng"] <= l["unten"], f"{land}: „eng“ liegt über dem unteren Viertel"


def test_nur_der_enge_fall_wird_gezeigt():
    """„Mehr Zeit als üblich" ändert keine Entscheidung: man bewirbt sich nicht, WEIL viel
    Zeit ist. Der enge Fall kippt sie, und zwar bevor man die Liste durchgeht."""
    block = CORE[CORE.index("function renderFensterBlock"):CORE.index("function renderChecklistBlock")]
    assert "f.tage > f.eng" in block
    assert "mehr Zeit als üblich" not in block


def test_ohne_beide_seiten_keine_zeile():
    """⚠ Das Fenster allein ist eine Frist, die Anforderungszahl allein ist eine Zahl. Erst
    zusammen entsteht die Aussage — und genau deshalb kann sie sonst niemand rechnen."""
    block = CORE[CORE.index("function renderFensterBlock"):CORE.index("function renderChecklistBlock")]
    assert "if(!f || f.tage == null || !f.median) return ''" in block
    assert "if(!n) return ''" in block


def test_die_kennzahl_steht_im_verzeichnis():
    from govisor import kennzahlen as kz
    treffer = [k for k in kz.ALLE if k.schluessel == "aufwandGegenZeitfenster"]
    assert treffer, "Kennzahl 1 fehlt im Verzeichnis"
    assert treffer[0].bezug == "markt"


def test_sie_steht_nicht_mehr_unter_geplant():
    """⚠ Sie ist gebaut. Bleibt sie unter `geplant`, sucht die nächste Sitzung nach Arbeit,
    die es nicht mehr gibt — dieselbe Alterung, gegen die das Verzeichnis angelegt wurde."""
    from govisor import kennzahlen as kz
    treffer = [k for k in kz.ALLE if k.schluessel == "aufwandGegenZeitfenster"]
    assert treffer[0].flaeche != "geplant", "gebaut, steht aber noch unter „geplant“"
