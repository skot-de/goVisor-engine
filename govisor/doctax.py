"""Anforderungs-Taxonomie für die Vergabeunterlagen-Extraktion (Ticket #23, §3, §6a.1).

Anforderungen werden **semantisch** klassifiziert (``req_type``), nicht über Textabgleich —
die Taxonomie ist verfahrensübergreifend gültig und ist ein **Klassifikationsziel, kein
Textcache** (Q1b). Sie speist #15 und die Themenzuordnung der Bausteine (§9.3/§9.4).

Das Thema einer Anforderung (§9.4) bestimmt ``theme_fuer_anforderung`` aus ihrem **Text**,
damit sie den passenden Profil-Baustein anziehen kann. ``theme_for(req_type)`` ist nur noch
der Rückfall für Anforderungen, deren Text nichts hergibt.
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
    # ⚠ Hier stand bis zum 2026-09-15 "projektorganisation" — fuer ALLE 10.508 Zuschlags-
    # kriterien im Bestand, weil das Thema aus dem Typ kam und nicht aus dem Inhalt. Ein
    # Zuschlagskriterium kann aber alles sein: Preis, Nachhaltigkeit, Personal. Der Typ sagt
    # darueber nichts, also sagt der Rueckfall jetzt auch nichts. Das Thema kommt aus dem Text,
    # s. `theme_fuer_anforderung`. Befund stand seit dem 2026-09-01 in build_doc_analysis.py.
    "zuschlagskriterium":            ("Zuschlagskriterium mit Gewicht", "sonstiges"),
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
    """Bausteine-Thema (§9.4) allein aus dem req_type; ``sonstiges`` für Unbekanntes.

    ⚠ NUR als Rückfall gedacht. Der req_type trennt die **Art** der Anforderung
    (Frist, Formalie, Zuschlagskriterium), nicht ihr **Thema**. Wer diese Funktion
    direkt benutzt, bekommt für jeden req_type genau einen Wert und damit eine Spalte
    ohne eigene Information. Für Anforderungen: ``theme_fuer_anforderung``.
    """
    return REQ_TYPES.get(req_type, ("", "sonstiges"))[1]


def theme_fuer_anforderung(req_type: str, *texte: object) -> str:
    """Bausteine-Thema (§9.4) einer Anforderung, aus ihrem **Text** bestimmt.

    Der erste Text, der ein Themenmuster trifft, gewinnt; deshalb das Konkreteste zuerst
    übergeben (``value`` vor ``quote`` vor ``label``). Trifft keiner, greift der Rückfall
    über den req_type — der ist für die Eignungsarten (``zertifikat`` → ``zertifikate_qm``,
    ``referenz_anzahl`` → ``referenzen``) richtig konstruiert und sonst ``sonstiges``.

    ⚠ WARUM NICHT ÜBER DEN TYP. Am 2026-09-15 gemessen: alle 18 req_type-Werte bildeten auf
    genau ein Thema ab, 70,5 % der 571.677 Zeilen landeten auf ``sonstiges``, und **alle**
    10.508 Zuschlagskriterien trugen ``projektorganisation``. Eine Spalte, die sich vollständig
    aus einer anderen ableitet, trägt keine Information — sie täuscht nur welche vor.
    """
    from .blocks import assign_theme  # spät, damit doctax importierbar bleibt ohne blocks
    for t in texte:
        if t is None:
            continue
        s = str(t).strip()
        if not s:
            continue
        thema = assign_theme(s)
        if thema != "sonstiges":
            return thema
    return theme_for(req_type)


def is_valid_req_type(req_type: str) -> bool:
    return req_type in REQ_TYPES
