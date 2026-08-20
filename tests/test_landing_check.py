"""Eignungs-Check — die Regeln, die man der fertigen Seite nicht ansieht.

Der öffentliche Check auf der Startseite rechnet im Browser, aber nur mit dem, was
`scripts/export_landing.py` vorberechnet. Zwei Dinge daran sind still und teuer, wenn sie
kippen: dass GESCHÄTZTE Auftragswerte nicht in die Grössenverteilung geraten (der Bestand
trägt Median-Imputationen — eine Startseite, die daraus eine Spanne bildet, behauptet
Messung und zeigt Rechnung), und dass die kumulierte Zählung monoton bleibt (sonst sinkt
der angezeigte Anteil, während der Besucher eine höhere Deckung anklickt).
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _modul():
    spec = importlib.util.spec_from_file_location(
        "export_landing", ROOT / "scripts" / "export_landing.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("roh,erwartet", [
    ("225.100 €", 225_100), ("1,2 Mio €", 1_200_000), ("80 €", 80),
    ("1,5 Mrd €", 1_500_000_000), ("Wert offen", None), ("", None), (None, None),
])
def test_wert_eur(roh, erwartet):
    assert _modul()._wert_eur(roh) == erwartet


def _lead(lid, land, region, src, wert, tage=5):
    return {"id": lid, "land": land, "region": region, "endTage": tage,
            "volumen": {"src": src, "wert": wert}}


def test_geschaetzte_werte_zaehlen_nicht_zur_groessenverteilung(tmp_path):
    """`src == 'schaetz'` ist eine Imputation, kein veröffentlichter Auftragswert."""
    mod = _modul()
    (tmp_path / "web/data").mkdir(parents=True)
    (tmp_path / "web/data/leads-bau.json").write_text(json.dumps([
        _lead("a", "DE", "Bayern", "echt", "50.000 €"),
        _lead("b", "DE", "Bayern", "schaetz", "369.663 €"),
        _lead("c", "DE", "Bayern", "unbekannt", "Wert offen"),
    ]), encoding="utf-8")
    w = mod.eignungs_check(tmp_path, [{"schluessel": "bau", "label": "Bau"}], {})
    zelle = w["zellen"]["bau|Bayern"]
    assert zelle["offen"] == 3                 # gezählt werden alle offenen Vorgänge …
    assert zelle["mitWert"] == 1               # … verglichen nur die mit echtem Wert
    assert sum(zelle["stufen"]) == 1
    assert w["wert"]["min"] == w["wert"]["max"] == 50_000


def test_nur_bundeslaender_stehen_zur_auswahl(tmp_path):
    """Der Bestand trägt vereinzelt region='Deutschland' — das ist kein Bundesland."""
    mod = _modul()
    (tmp_path / "web/data").mkdir(parents=True)
    (tmp_path / "web/data/leads-bau.json").write_text(json.dumps([
        _lead("a", "DE", "Deutschland", "echt", "50.000 €"),
        _lead("b", "AT", None, "echt", "50.000 €"),
        _lead("c", "DE", "Bremen", "echt", "50.000 €"),
        _lead("d", "DE", "Bayern", "echt", "50.000 €", tage=-3),   # Frist abgelaufen
    ]), encoding="utf-8")
    w = mod.eignungs_check(tmp_path, [{"schluessel": "bau", "label": "Bau"}], {})
    raeume = {r["schluessel"] for r in w["regionen"]}
    assert raeume == {"alle", "DE", "AT", "Bremen"}
    assert "Bayern" not in raeume                                  # abgelaufen zählt nicht
    assert dict((r["schluessel"], r["offen"]) for r in w["regionen"])["alle"] == 3


def test_kumulierte_schwellen_steigen_monoton(tmp_path):
    """Wer mehr anklickt, darf nie weniger erfüllen — sonst rechnet die Seite gegen sich."""
    mod = _modul()
    (tmp_path / "web/data").mkdir(parents=True)
    (tmp_path / "web/data/leads-bau.json").write_text(json.dumps(
        [_lead(str(i), "DE", "Bremen", "echt", "50.000 €") for i in range(40)]), encoding="utf-8")
    analysen = {str(i): {"checklist": [
        {"req_type": "berufshaftpflicht", "value": str(250_000 * (i % 8 + 1))}
        for _ in (0,)]} for i in range(40)}
    w = mod.eignungs_check(tmp_path, [{"schluessel": "bau", "label": "Bau"}], analysen)
    kum = w["anforderungen"]["haftpflicht"]["je_fach"]["bau"]["kum"]
    assert kum == sorted(kum)
    assert kum[-1] <= w["anforderungen"]["haftpflicht"]["je_fach"]["bau"]["n"]


def test_duenne_fachgebiete_fallen_auf_den_gesamtbestand_zurueck(tmp_path):
    """Unter 30 Fundstellen trägt ein Fachgebiet keine Aussage — dann gibt es keinen Eintrag."""
    mod = _modul()
    (tmp_path / "web/data").mkdir(parents=True)
    (tmp_path / "web/data/leads-bau.json").write_text(json.dumps(
        [_lead(str(i), "DE", "Bremen", "echt", "50.000 €") for i in range(5)]), encoding="utf-8")
    analysen = {str(i): {"checklist": [{"req_type": "referenz_anzahl", "value": "3"}]}
                for i in range(5)}
    je_fach = mod.eignungs_check(
        tmp_path, [{"schluessel": "bau", "label": "Bau"}], analysen
    )["anforderungen"]["referenzen"]["je_fach"]
    assert "bau" not in je_fach and je_fach["alle"]["n"] == 5


def test_katalog_zaehlt_nur_belegte_anforderungen(tmp_path):
    """Erkannt wird über Begriffe im Zitat — und nur, was auch wirklich dasteht."""
    mod = _modul()
    analysen = {
        "a": {"checklist": [{"req_type": "formalie", "quote": "Eigenerklärung zur Eignung"},
                            {"req_type": "zertifikat", "quote": "DIN EN ISO 9001 gefordert"}]},
        "b": {"checklist": [{"req_type": "formalie", "quote": "Eigenerklärung beilegen"}]},
    }
    kat = mod.anforderungs_katalog(analysen, {"a": "bau", "b": "bau"}, {"a"})
    zeilen = {z["key"]: z for z in kat["katalog"]["bau"]["zeilen"]} if "bau" in kat["katalog"] else {}
    # unter 30 Verfahren gibt es bewusst KEINEN Fachgebiets-Katalog
    assert zeilen == {}
    assert "bau" not in kat["profile"]


def test_katalog_und_profile_ab_dreissig_verfahren():
    """Ab 30 Verfahren: Häufigkeit, Profile, und der Nenner ohne die anforderungslosen."""
    mod = _modul()
    analysen = {}
    for i in range(40):
        pruefungen = [{"req_type": "formalie", "quote": "Eigenerklärung zur Eignung"}]
        if i < 10:                                   # zehn verlangen 3 Mio Haftpflicht
            pruefungen.append({"req_type": "berufshaftpflicht", "value": "3000000",
                               "quote": "Betriebshaftpflicht in Höhe von 3.000.000 €"})
        analysen[str(i)] = {"checklist": pruefungen}
    fach = {str(i): "bau" for i in range(40)}
    kat = mod.anforderungs_katalog(analysen, fach, {"0", "1"})
    zeilen = {z["key"]: z for z in kat["katalog"]["bau"]["zeilen"]}
    assert zeilen["eigenerklaerung"]["anteil"] == 100
    assert zeilen["haftpflicht"]["n"] == 10
    p = kat["profile"]["bau"]
    assert p["n"] == 40 and p["ohne"] == 30       # 30 tragen keine bezifferte Anforderung
    # Die Gruppe mit der Forderung trägt die Stufe „3 Mio" (Index 3 der Haftpflicht-Leiter)
    fordernd = [g for g in p["gruppen"] if g[0] >= 0]
    assert sum(g[-1] for g in fordernd) == 10
    assert {g[0] for g in fordernd} == {mod.ANF_LEITER["haftpflicht"]["stufen"].index(3_000_000)}
    # Zwei der zehn sind offen und müssen als solche gezählt sein
    assert sum(g[-1] for g in fordernd if g[6] == 1) == 2
