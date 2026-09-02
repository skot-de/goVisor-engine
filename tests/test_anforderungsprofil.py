"""Kennzahl 2 — worin verlangt dieser Vorgang mehr als üblich?

⚠ „STRENGE" IST FÜR DIE HÄLFTE DER BEREICHE DAS FALSCHE WORT. Die Übergabe nennt die Kennzahl
so; nachgesehen, was drinsteht:

    eignung      „Technische Mindesteignung", „Mindestanzahl vergleichbarer Referenzen"
    ausschluss   „Ausschluss-/Mindestbedingung"        → HÜRDEN, sie schliessen aus
    formalitaet  „Ausfüllbares Formular (61 Felder)"   → AUFWAND, kein Hindernis
    leistung     „Leistungsumfang / Menge"             → UMFANG, ausführlich ist nicht streng
"""
from __future__ import annotations

import json
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
DATEI = WURZEL / "web" / "data" / "anforderungsprofil.json"
EXPORT = (WURZEL / "scripts" / "export_anforderungsprofil.py").read_text(encoding="utf-8")
CORE = (WURZEL / "web" / "lib" / "explorerCore.js").read_text(encoding="utf-8")
API = (WURZEL / "web" / "app" / "api" / "lead-detail" / "route.ts").read_text(encoding="utf-8")


def _daten() -> dict:
    return json.loads(DATEI.read_text(encoding="utf-8")) if DATEI.exists() else {}


def test_jeder_bereich_traegt_seine_art():
    """Ohne die Art hiesse ein ausführliches Leistungsverzeichnis „streng"."""
    assert "ART = {" in EXPORT
    for b, l in (_daten().get("bereiche") or {}).items():
        assert l["art"] in ("huerde", "aufwand", "umfang"), f"{b}: unbekannte Art {l['art']}"


def test_nur_eignung_und_ausschluss_sind_huerden():
    """⚠ Die inhaltliche Entscheidung. Formalitäten sind Arbeit, kein Hindernis; wer sie zur
    Hürde erklärt, warnt vor dem Falschen."""
    huerden = {b.split(":")[1] for b, l in (_daten().get("bereiche") or {}).items()
               if l["art"] == "huerde"}
    assert huerden == {"eignung", "ausschluss"}, f"Hürden: {huerden}"


def test_die_huerde_gewinnt_den_platz():
    """⚠ Zuerst sortierte die API nur nach dem Vielfachen des Medians — dann stand
    „Zuschlagskriterien 21 statt 3" (Umfang, 7-fach) vor „Ausschlusskriterien 17 statt 5"
    (Hürde, 3,4-fach). Bei zwei Plätzen entscheidet die Reihenfolge, was überhaupt zu sehen
    ist."""
    stelle = API[API.index("const auffaellig"):API.index("if (auffaellig.length)")]
    assert 'art === "huerde" ? 0' in stelle
    assert ".slice(0, 2)" in stelle, "ohne Deckel wären es bis zu sieben Zeilen"


def test_das_wort_haengt_an_der_art():
    block = CORE[CORE.index("function renderProfilBlock"):CORE.index("/* KENNZAHL 1")]
    assert "Eine Hürde mehr" in block
    assert "Das ist Arbeit, kein Hindernis" in block
    assert "Mehr zu lesen" in block


def test_kleine_bereiche_bekommen_keinen_vergleichswert():
    assert "MIND_VORGAENGE = 200" in EXPORT
    for b, l in (_daten().get("bereiche") or {}).items():
        assert l["n"] >= 200, f"{b}: Vergleichswert aus {l['n']} Vorgängen"


def test_die_achse_misst_die_vergabe_nicht_uns():
    """⚠ Die Prüfung, an der Kennzahl 1 fast gescheitert wäre: misst die Anforderungszahl die
    Vergabe oder unsere Leseleistung? Nachgemessen sind die Mediane über die Zahl gelesener
    Dateien stabil (leistung 25/25/25/26, eignung 3/3/3/3), Korrelation 0,196. Der Nachweis
    gehört in die Datei, damit ihn niemand ein zweites Mal führen muss."""
    assert "Korrelation 0,196" in EXPORT
    assert "stabil" in EXPORT
