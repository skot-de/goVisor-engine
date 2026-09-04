"""Schwärzung personenbezogener Daten für den Baustein-Import (Ticket #23, §10.3 — Pflicht).

Alte Angebote enthalten regelmäßig Personendaten (Projektleiter, Ansprechpartner, Personal-
listen, personengebundene Qualifikationen). Diese dürfen die Bibliothek **nicht ungefiltert**
erreichen (konsistent mit #11 §5.2 „Team, nicht Person"). Vor dem Speichern werden Namen,
E-Mail, Telefon durch **Platzhalter** ersetzt; Passagen, die überwiegend aus Personendaten
bestehen (Lebensläufe), werden gar nicht übernommen.

Bewusst **konservativ ohne NER-Modell**: erkennt titel-/rollengebundene Namen, E-Mail, Telefon
(nur mit Marker/Landesvorwahl, damit Beträge/Aktenzeichen nicht fälschlich als Nummer gelten).
Rückgabe trägt die Ersetzungen mit, damit der Nutzer sie sichtbar überschreiben kann (§10.3-3).
"""
from __future__ import annotations

import re

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# Telefon NUR mit Marker (Tel/Fon/Mobil/Fax) oder internationaler Vorwahl — sonst träfe es
# Beträge, Aktenzeichen, Postleitzahlen.
#
# ⚠ **DIE VORWAHL WAR AUF `+49` FESTGENAGELT — UND DER MARKER VERTRUG KEIN „+".** Beides
# zusammen liess in AT, CH und LU jede Nummer stehen, gemessen am 2026-09-04:
#
#     "Tel: +43 1 4000 12345"      NICHT geschwaerzt   ← Marker DA, aber `\(?\d` verlangt
#                                                        eine Ziffer, und „+" ist keine
#     "+41 44 412 11 11"           NICHT geschwaerzt
#     "+352 4796 1"                NICHT geschwaerzt
#     "Tel. 030 12345678"          geschwaerzt
#     "+49 30 12345678"            geschwaerzt          ← nur weil der zweite Zweig griff
#
# Deutschland war also durch den `\+49`-Zweig gedeckt und alle anderen aktiven Laender nicht.
# Das ist der EU-weit-Grundsatz: eine Funktion gilt fuer ALLE Laender, DE ist nur der
# Testfall. Die Vorwahl ist jetzt laenderneutral, und nach dem Marker darf eine stehen.
#
# Die Enge bleibt, wo sie hingehoert: OHNE Marker braucht es weiterhin ein „+" mit
# Laendervorwahl. `[\d\s()/-]` enthaelt bewusst weder Punkt noch Komma — „+1.234.567,89"
# bricht damit am ersten Punkt ab und wird nicht zur Telefonnummer.
_INT_VORWAHL = r"\+\d{1,3}[\s/-]?"
_TEL_MARKER = r"(?:Tel(?:efon)?|Fon|Mobil|Handy|Fax)\.?\s*:?\s*"
_PHONE = re.compile(
    rf"(?:{_TEL_MARKER}(?:{_INT_VORWAHL})?|{_INT_VORWAHL})\(?\d[\d\s()/-]{{5,}}\d", re.I)

# ⚠ **NAMEN GAB ES NUR MIT DEUTSCHEN UMLAUTEN.** `[A-ZÄÖÜ][a-zäöüß]+` traf „Max Mustermann",
# aber weder „Élodie Lefèvre" noch „Łukasz Kowalski" — in LU (franzoesisch) und bei jedem
# nicht-deutschen Namen in DE/AT/CH blieb der Name stehen. Die Buchstaben stehen bewusst
# ausgeschrieben statt als Unicode-Bereich: Latin Extended-A wechselt Gross und Klein im
# Zickzack (Ā ā Ă ă …), ein Bereich wuerde also beide Faelle vermischen und jedes
# GROSSGESCHRIEBENE Wort zum Namen machen.
_GROSS = "A-ZÄÖÜÀÁÂÃÅÆÇÈÉÊËÌÍÎÏÑÒÓÔÕØÙÚÛÝŁŚŻŹĆŃŘŠŽ"
_KLEIN = "a-zäöüßàáâãåæçèéêëìíîïñòóôõøùúûýÿłśżźćńřšž"
_NAME = rf"[{_GROSS}][{_KLEIN}]+(?:-[{_GROSS}][{_KLEIN}]+)?"
# „Herr/Frau [Titel] Vorname Nachname"
_TITLE_NAME = re.compile(
    rf"\b(?:Herr|Frau|Hr\.|Fr\.)\s+(?:Dr\.\s+|Prof\.\s+|Dipl\.[-\wäöü]*\s+)?{_NAME}(?:\s+{_NAME}){{0,2}}")
# „Ansprechpartner: Vorname Nachname" (Rolle + zwei Namensteile)
_ROLE = (r"Ansprechpartner(?:in)?|Projektleiter(?:in)?|Projektleitung|Bauleiter(?:in)?|"
         r"Bearbeiter(?:in)?|Sachbearbeiter(?:in)?|Kontaktperson|Kontakt")
_ROLE_NAME = re.compile(rf"\b(?:{_ROLE})\s*[:\-]?\s+({_NAME}\s+{_NAME}(?:\s+{_NAME})?)")

# Rollen → Platzhalter
_ROLE_PLACEHOLDER = [
    (re.compile(r"projektleit", re.I), "[Projektleitung]"),
    (re.compile(r"bauleit", re.I), "[Bauleitung]"),
    (re.compile(r"ansprechpartner|kontakt", re.I), "[Ansprechpartner]"),
]


def _role_placeholder(prefix: str) -> str:
    for rx, ph in _ROLE_PLACEHOLDER:
        if rx.search(prefix):
            return ph
    return "[Ansprechpartner]"


def redact(text: str) -> tuple[str, list[dict]]:
    """Personendaten → Platzhalter. Gibt ``(bereinigter_text, [{original, placeholder, typ}])``.

    Reihenfolge: E-Mail und Telefon zuerst (eindeutig), dann rollengebundene und titel-
    gebundene Namen. Ersetzungen werden gesammelt, damit das Frontend sie markiert (§10.3-3)."""
    repl: list[dict] = []

    def sub(rx, kind, ph):
        def _r(m):
            repl.append({"original": m.group(0), "placeholder": ph, "typ": kind})
            return ph
        return rx.sub(_r, text)

    text = sub(_EMAIL, "email", "[E-Mail]")
    text = sub(_PHONE, "telefon", "[Telefon]")

    # Rollen-Namen: Platzhalter nach Rolle wählen
    def _role(m):
        ph = _role_placeholder(m.group(0)[:m.start(1) - m.start(0)])
        repl.append({"original": m.group(1), "placeholder": ph, "typ": "name"})
        return m.group(0).replace(m.group(1), ph)
    text = _ROLE_NAME.sub(_role, text)

    text = sub(_TITLE_NAME, "name", "[Name]")
    return text, repl


# Marker für personengebundene Qualifikationen / Lebenslauf-Passagen (§10.3-4).
_CV = re.compile(r"\b(geboren am|geb\.|lebenslauf|curriculum|werdegang|staatsangeh|"
                 r"geburtsdatum|geburtsort|familienstand)\b", re.I)


def is_mostly_personal(text: str) -> bool:
    """Passage besteht überwiegend aus Personendaten (Lebenslauf) → NICHT übernehmen (§10.3-4).

    Heuristik: ein CV-Marker plus hohe Dichte an Personendaten, ODER sehr kurze Passage, die fast
    nur aus einem geschwärzten Namen/Kontakt besteht."""
    if not text or not text.strip():
        return True
    _, repl = redact(text)
    words = max(len(re.findall(r"\w+", text)), 1)
    density = len(repl) / words
    # CV-Marker (geboren/Lebenslauf/Werdegang …) ist ein starkes Lebenslauf-Signal: eine kurze
    # Passage damit — oder eine mit zusätzlichem Kontakt/Namen — ist Personendaten.
    if _CV.search(text) and (words < 60 or len(repl) >= 1):
        return True
    return words < 12 and len(repl) >= 1 and density > 0.15
