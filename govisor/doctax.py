"""Anforderungs-Taxonomie für die Vergabeunterlagen-Extraktion (Ticket #23, §3, §6a.1).

Anforderungen werden **semantisch** klassifiziert (``req_type``), nicht über Textabgleich —
die Taxonomie ist verfahrensübergreifend gültig und ist ein **Klassifikationsziel, kein
Textcache** (Q1b). Sie speist #15 und die Themenzuordnung der Bausteine (§9.3/§9.4).

Jeder ``req_type`` trägt ein festes ``theme`` aus der Bausteine-Themen-Taxonomie (§9.4), damit
eine extrahierte Anforderung direkt den passenden Profil-Baustein anziehen kann.
"""
from __future__ import annotations

# Feste Themen-Taxonomie der Bausteine (§9.4) — nicht nutzererweiterbar.
THEMES: tuple[str, ...] = (
    "unternehmensdarstellung", "referenzen", "zertifikate_qm", "datenschutz_avv",
    "nachhaltigkeit", "personal_qualifikation", "technische_ausstattung",
    "projektorganisation", "sonstiges",
)

# req_type → (Label, theme). Verfahrensübergreifend gültig.
REQ_TYPES: dict[str, tuple[str, str]] = {
    # K.-o.-/Eignungskriterien (§6a.3 Eignung)
    "mindestumsatz":                 ("Mindestumsatz", "unternehmensdarstellung"),
    "referenz_anzahl":               ("Mindestanzahl vergleichbarer Referenzen", "referenzen"),
    "referenz_mindestwert":          ("Referenz-Mindestwert", "referenzen"),
    "zertifikat":                    ("Gefordertes Zertifikat / Nachweis", "zertifikate_qm"),
    "ausschlussgrund":               ("Ausschluss-/Mindestbedingung", "sonstiges"),
    "eignung_technisch":             ("Technische Mindesteignung", "technische_ausstattung"),
    "eignung_personal":              ("Personelle Eignung / Qualifikation", "personal_qualifikation"),
    "berufshaftpflicht":             ("Berufs-/Betriebshaftpflicht-Deckung", "unternehmensdarstellung"),
    # Zuschlag (§6a.3 Zuschlagskriterien)
    "zuschlagskriterium":            ("Zuschlagskriterium mit Gewicht", "projektorganisation"),
    # Leistungsbeschreibung
    "leistung_menge":                ("Leistungsumfang / Menge", "sonstiges"),
    "technische_mindestanforderung": ("Technische Mindestanforderung", "technische_ausstattung"),
    # Vertrag
    "vertragsstrafe":                ("Vertragsstrafe", "sonstiges"),
    "haftung":                       ("Haftungsregelung", "sonstiges"),
    "laufzeit":                      ("Laufzeit / Verlängerungsoption", "sonstiges"),
    "kuendigung":                    ("Kündigungsrecht", "sonstiges"),
    # Formalien / Fristen (Aufforderung)
    "frist":                         ("Frist", "sonstiges"),
    "einzureichendes_dokument":      ("Einzureichendes Dokument / Anlage", "sonstiges"),
    "formalie":                      ("Formalie", "sonstiges"),
}

# Kennzeichnungsstufen der Extraktion (§7.2). „Vorschlag" gilt nur für generierte Bausteine (Ebene B),
# nicht für die Extraktion — daher hier nicht enthalten.
MARKINGS: tuple[str, ...] = ("Zitat", "Extrahiert", "Abgeleitet")
# Stufen mit Belegpflicht (§6a.2): müssen ein wörtliches, verifizierbares Zitat tragen.
MARKINGS_REQUIRE_QUOTE: frozenset[str] = frozenset({"Zitat", "Extrahiert"})


def theme_for(req_type: str) -> str:
    """Bausteine-Thema (§9.4) für einen req_type; ``sonstiges`` für Unbekanntes."""
    return REQ_TYPES.get(req_type, ("", "sonstiges"))[1]


def is_valid_req_type(req_type: str) -> bool:
    return req_type in REQ_TYPES
