"""Kennzahl 1 — Aufwand gegen Zeitfenster, und warum die erste Deutung falsch war.

⚠ Gemessen liegt der Median bei 34 Tagen, in JEDER Aufwandsklasse (bis 10 Anforderungen 33
Tage, über 100 Anforderungen 35), Korrelation 0,08. Daraus wurde zuerst: „der Markt gibt
dieselbe Zeit, egal wie viel Arbeit drinsteckt."

Sven, beim Lesen: „also zwischen unter 10 Anforderungen und über 100 liegen zwei Tage?!"

Die Flachheit ist **kein Marktverhalten, sondern eine Vorgabe**: 68 % aller Fenster liegen
zwischen 28 und 40 Tagen, die häufigsten Werte sind 30 bis 36 — dort liegen die gesetzlichen
Mindestfristen. Und die kurzen Fenster sind kein aggressiver Auftraggeber, sondern ein
anderes Regelwerk: unter den Vorgängen mit höchstens 28 Tagen sind 21 % UVgO, im Rest 4 %.
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
    for k, l in (d.get("rahmen") or {}).items():
        assert 1 <= l["median"] <= 365, f"{k}: Median {l['median']} ausserhalb der Grenzen"
    for e in (d.get("leads") or {}).values():
        assert 1 <= e["tage"] <= 365


def test_verglichen_wird_je_regelwerk():
    """⚠ Der Fehler, der die Kennzahl unbrauchbar gemacht hätte. Ein globaler Median markiert
    jede UVgO-Vergabe als „knapp", obwohl sie ihrem eigenen Rahmen entspricht: VgV liegt bei
    34 Tagen, UVgO bei 30, und „eng" beginnt dort bei 20 statt bei 30."""
    assert "_rahmen" in EXPORT
    d = _daten()
    schluessel = set((d.get("rahmen") or {}))
    assert any(k.endswith(":uvgo") for k in schluessel), "UVgO hat keine eigene Gruppe"
    assert any(k.endswith(":vgv") for k in schluessel)
    # Und die Gruppen unterscheiden sich wirklich, sonst waere die Trennung Zierde.
    werte = {k: v["eng"] for k, v in (d.get("rahmen") or {}).items()}
    assert len(set(werte.values())) > 1, "alle Gruppen haben dieselbe Schwelle"


def test_kleine_gruppen_bekommen_keinen_vergleichswert():
    """⚠ Ein Median aus zwölf Fällen sieht aus wie einer aus zwölfhundert."""
    assert "len(werte) < 30" in EXPORT
    for k, v in (_daten().get("rahmen") or {}).items():
        assert v["n"] >= 30, f"{k}: Vergleichswert aus {v['n']} Vorgängen"


def test_die_falsche_aussage_ist_weg():
    """⚠ „unabhängig vom Aufwand" behauptete ein Marktverhalten, wo eine Vorschrift steht."""
    for datei in ("flat.en.json", "flat.fr.json"):
        kat = (WURZEL / "web" / "lib" / "i18n" / "messages" / datei).read_text(encoding="utf-8")
        assert "unabhängig vom Aufwand" not in kat
    assert "unabhängig vom Aufwand" not in CORE.split("*/")[-1]


def test_die_schwelle_ist_das_zehnte_perzentil():
    """⚠ Erste Fassung nahm das Viertel — die Zeile erschien bei 51 % aller Vorgänge, also bei
    jedem zweiten. Eine Zeile, die immer dasteht, liest bald niemand mehr."""
    assert "bei(0.10)" in EXPORT
    d = _daten()
    for k, l in (d.get("rahmen") or {}).items():
        assert l["eng"] <= l["unten"], f"{k}: „eng“ liegt über dem unteren Viertel"


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
    assert "if(!f || f.tage == null || !f.median || f.eng == null) return ''" in block
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
