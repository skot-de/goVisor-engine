"""Ticket #23 Phase 1 — Extraktions-Kern: Schema-Validierung + Zitat-Verifikation (§6a).

Der LLM ist injiziert (Fake-chat_fn) — geprüft wird die belegpflichtige, schema-gebundene
Verarbeitung, nicht das Modell.
"""
import json

from govisor import doctax, docextract
from govisor.doctypes import classify, PRIORITY, priority_rank


DOC = (
    "Bewerbungsbedingungen\n\n"
    "Der Bieter hat ein gültiges Zertifikat nach DIN EN ISO 9001 vorzulegen.\n"
    "Mindestens drei vergleichbare Referenzen aus den letzten fünf Jahren mit einem Volumen von je "
    "mindestens 500.000 EUR sind nachzuweisen.\n"
)


def _fake(items):
    def chat_fn(messages, model=None):
        return json.dumps(items, ensure_ascii=False)
    return chat_fn


def test_verify_quote_normalizes_and_rejects_fabricated():
    assert docextract.verify_quote("ISO 9001 vorzulegen", DOC)
    # Whitespace/Umbruch-Normalisierung: mehrfacher Space + andere Groß-/Kleinschreibung findet trotzdem
    assert docextract.verify_quote("gültiges   Zertifikat nach DIN EN ISO 9001", DOC)
    assert not docextract.verify_quote("Mindestumsatz von 2 Millionen EUR jährlich", DOC)  # nicht im Text
    assert not docextract.verify_quote("ISO", DOC)                                          # zu kurz


def test_verify_quote_survives_pdf_hyphenation():
    # PDF-Zeilenumbruch-Trennstrich + Interpunktion dürfen den Beleg nicht scheitern lassen
    src = "Der Auftragnehmer erbringt die Leistungs-\nbeschreibung gemäß Anlage 3 zum Vertrag."
    assert docextract.verify_quote("Leistungsbeschreibung gemäß Anlage 3", src)
    assert docextract.verify_quote("Auftrag-\nnehmer erbringt die Leistungsbeschreibung", src)
    assert not docextract.verify_quote("Leistungsbeschreibung gemäß Anlage 7", src)   # 7 ≠ 3 → nicht belegt


def test_validate_item_schema():
    ok = {"req_type": "zertifikat", "quote": "…", "marking": "Zitat"}
    assert docextract.validate_item(ok)
    assert not docextract.validate_item({"req_type": "quatsch", "quote": "x", "marking": "Zitat"})
    assert not docextract.validate_item({"req_type": "zertifikat", "quote": "x", "marking": "Erfunden"})
    assert not docextract.validate_item({"req_type": "zertifikat", "quote": "", "marking": "Zitat"})  # Beleg fehlt
    # allowed-Liste greift
    assert not docextract.validate_item(ok, allowed_req_types={"mindestumsatz"})
    # Abgeleitet darf ohne quote
    assert docextract.validate_item({"req_type": "haftung", "marking": "Abgeleitet"})


def test_extract_keeps_verified_drops_unverified_and_invalid():
    items = [
        {"req_type": "zertifikat", "value": "ISO 9001", "unit": None,
         "quote": "Der Bieter hat ein gültiges Zertifikat nach DIN EN ISO 9001 vorzulegen.",
         "marking": "Zitat"},                                             # verifizierbar → behalten
        {"req_type": "mindestumsatz", "value": "2 Mio", "unit": "EUR",
         "quote": "Ein Mindestumsatz von 2 Mio EUR ist nachzuweisen.", "marking": "Zitat"},  # Zitat NICHT im Text → verworfen
        {"req_type": "quatsch", "value": None, "unit": None, "quote": "…", "marking": "Zitat"},  # Schema-invalid → verworfen
    ]
    res = docextract.extract("eignung", DOC, "Teil_A_Bewerbungsbedingungen.pdf", chat_fn=_fake(items))
    assert res["rejected"] == 2
    assert len(res["items"]) == 1
    it = res["items"][0]
    assert it["req_type"] == "zertifikat"
    assert it["theme"] == doctax.theme_for("zertifikat") == "zertifikate_qm"
    assert it["source_file"] == "Teil_A_Bewerbungsbedingungen.pdf"


def test_extract_parse_error_and_unsupported():
    def garbage(messages, model=None):
        return "das ist kein JSON"
    assert docextract.extract("eignung", DOC, "x.pdf", chat_fn=garbage).get("parse_error")
    assert docextract.extract("sonstiges", DOC, "x.pdf", chat_fn=_fake([])).get("skipped")


def test_extract_allowed_req_types_enforced():
    # zuschlagskriterium ist bei doctype 'eignung' nicht erlaubt → verworfen
    items = [{"req_type": "zuschlagskriterium", "value": "Preis", "unit": "60%",
              "quote": "Der Bieter hat ein gültiges Zertifikat nach DIN EN ISO 9001 vorzulegen.",
              "marking": "Zitat"}]
    res = docextract.extract("eignung", DOC, "x.pdf", chat_fn=_fake(items))
    assert res["items"] == [] and res["rejected"] == 1


def test_classifier_and_priority():
    assert classify("Teil_B_Leistungsbeschreibung.pdf") == "leistungsbeschreibung"
    assert classify("Bewerbungsbedingungen.pdf") == "eignung"
    assert classify("Zuschlagskriterien_Wertung.pdf") == "zuschlagskriterien"
    assert classify("random_anlage_b1_bilder.pdf") == "sonstiges"
    # Priorität: Eignung vor Aufforderung
    assert priority_rank("eignung") < priority_rank("aufforderung")
    assert priority_rank("sonstiges") > priority_rank("aufforderung")
    assert PRIORITY[0] == "eignung"
