"""Ticket #23 Phase 5 — PII-Schwärzung (§10.3) + Baustein-Extraktion/Themen (§9.4/§10.1)."""
from govisor import pii, blocks


def test_pii_redacts_contact_data():
    t = ("Ansprechpartner: Max Mustermann, Tel. 030 123456, E-Mail max.mustermann@example.de. "
         "Für Rückfragen steht Frau Dr. Erika Musterfrau zur Verfügung.")
    clean, repl = pii.redact(t)
    assert "max.mustermann@example.de" not in clean and "[E-Mail]" in clean
    assert "030 123456" not in clean and "[Telefon]" in clean
    assert "Max Mustermann" not in clean
    assert "Erika Musterfrau" not in clean and "[Name]" in clean
    kinds = {r["typ"] for r in repl}
    assert {"email", "telefon", "name"} <= kinds


def test_pii_keeps_business_numbers():
    # Beträge/Aktenzeichen ohne Telefon-Marker dürfen NICHT als Telefon geschwärzt werden
    t = "Die Auftragssumme beträgt 1.250.000 EUR, Aktenzeichen VG-2026-0815, Baujahr 2018."
    clean, repl = pii.redact(t)
    assert "1.250.000" in clean and "VG-2026-0815" in clean
    assert not any(r["typ"] == "telefon" for r in repl)


def test_is_mostly_personal():
    assert pii.is_mostly_personal("Max Mustermann, geboren am 01.01.1980, Tel. 030 999888")
    assert not pii.is_mostly_personal(
        "Unser Unternehmen erbringt seit 1998 Gebäudereinigung mit einem zertifizierten QM-System.")


def test_extract_blocks_redacts_and_themes():
    text = (
        "Über uns: Unser Unternehmen wurde 1998 gegründet und beschäftigt 120 Mitarbeiter.\n\n"
        "Referenzen: Vergleichbare Projekte für die Stadt Musterstadt und den Landkreis Beispiel.\n\n"
        "Ansprechpartner: Max Mustermann, E-Mail max@example.de, geboren am 01.01.1980 in Musterstadt.\n\n"
        "Qualitätsmanagement: Wir sind nach DIN EN ISO 9001 zertifiziert.")
    res = blocks.extract_blocks(text)
    themes = {b["theme"] for b in res["blocks"]}
    assert "referenzen" in themes and "zertifikate_qm" in themes and "unternehmensdarstellung" in themes
    # die Ansprechpartner/CV-Passage wird als personenbezogen übersprungen
    assert res["skipped_personal"] >= 1
    # kein Baustein trägt die E-Mail im Klartext
    assert all("max@example.de" not in b["content"] for b in res["blocks"])
    # Keywords abgeleitet
    assert all(isinstance(b["keywords"], list) for b in res["blocks"])


def test_assign_theme_and_keywords():
    assert blocks.assign_theme("Wir sind nach ISO 9001 zertifiziert") == "zertifikate_qm"
    assert blocks.assign_theme("Unsere Referenzprojekte umfassen …") == "referenzen"
    assert blocks.assign_theme("Völlig neutraler Satz ohne Merkmale") == "sonstiges"
    kw = blocks.derive_keywords("Gebäudereinigung Gebäudereinigung Unterhaltsreinigung Fensterreinigung")
    assert "gebäudereinigung" in kw


def test_participation_tuple_is_minimal():
    t = blocks.participation_tuple("prof-1", "notice-9")
    assert t == {"profile_id": "prof-1", "notice_id": "notice-9", "participated": True}


# ---- EU-weit: die Schwaerzung galt nur fuer Deutschland ------------------------
import pytest


@pytest.mark.parametrize("land,text", [
    ("AT (Marker + Vorwahl)", "Tel: +43 1 4000 12345"),
    ("AT (nur Vorwahl)",      "Erreichbar unter +43 1 4000 12345"),
    ("CH",                    "Erreichbar unter +41 44 412 11 11"),
    ("LU",                    "Erreichbar unter +352 4796 1"),
    ("DE (Marker)",           "Rueckfragen an Tel. 030 12345678"),
    ("DE (Vorwahl)",          "Erreichbar unter +49 30 12345678"),
])
def test_telefon_wird_in_jedem_aktiven_land_geschwaerzt(land, text):
    """⚠ GEMESSEN AM 2026-09-04: nur Deutschland war gedeckt.

    Das Muster verlangte einen Marker (Tel/Fon/Mobil/Fax) ODER die Vorwahl `+49`. Zwei
    Loecher daraus:

      · Die Vorwahl war auf DE festgenagelt — `+43`, `+41`, `+352` fielen durch.
      · Nach dem Marker verlangte es eine ZIFFER (`\\(?\\d`). „Tel: +43 …" scheiterte damit
        am Pluszeichen — Marker vorhanden, trotzdem nicht geschwaerzt. In DE rettete nur
        der zweite Zweig `\\+49`.

    Das ist der EU-weit-Grundsatz: eine Funktion gilt fuer ALLE Laender, DE ist nur der
    Testfall. Und es trifft hier Personendaten in Bausteinen, die mit `sichtbarkeit='firma'`
    an alle mit belegtem Anspruch gehen (supabase/0016).
    """
    clean, repl = pii.redact(text)
    assert "[Telefon]" in clean, f"{land}: Nummer bleibt stehen — {clean}"
    assert repl and repl[0]["typ"] == "telefon"


@pytest.mark.parametrize("text", [
    "Ansprechpartner: Max Mustermann",
    "Ansprechpartner: Élodie Lefèvre",
    "Ansprechpartner: Łukasz Kowalski",
])
def test_namen_auch_ohne_deutsche_umlaute(text):
    """`[A-ZÄÖÜ][a-zäöüß]+` kannte nur deutsche Namen.

    In Luxemburg (franzoesisch) und bei jedem nicht-deutschen Namen in DE/AT/CH blieb er
    stehen. Die Buchstaben stehen im Muster ausgeschrieben und nicht als Unicode-Bereich:
    Latin Extended-A wechselt Gross und Klein im Zickzack (Ā ā Ă ă …), ein Bereich wuerde
    beide Faelle vermischen und jedes GROSSGESCHRIEBENE Wort zum Namen machen.
    """
    clean, repl = pii.redact(text)
    assert "[Ansprechpartner]" in clean, f"Name bleibt stehen — {clean}"
    assert any(r["typ"] == "name" for r in repl)


@pytest.mark.parametrize("text", [
    "Nachtrag von +1.234.567,89 EUR",
    "Vergabenummer 2026 4711 0815",
    "Musterstadt 80331 Bayern",
])
def test_die_erweiterung_macht_keine_telefonnummern_aus_zahlen(text):
    """Die Enge bleibt, wo sie hingehoert.

    Ohne Marker braucht es weiterhin ein „+" mit Laendervorwahl, und `[\\d\\s()/-]` enthaelt
    bewusst weder Punkt noch Komma — „+1.234.567,89" bricht am ersten Punkt ab. Sonst haette
    die laenderneutrale Vorwahl aus jedem Betrag eine Telefonnummer gemacht.
    """
    clean, repl = pii.redact(text)
    assert not [r for r in repl if r["typ"] == "telefon"], f"faelschlich geschwaerzt: {clean}"
