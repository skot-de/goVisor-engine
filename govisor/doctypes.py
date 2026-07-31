"""Dokumenttyp-Klassifikation für Vergabeunterlagen (Ticket #23, §6.1).

Zwei Ebenen: (1) **Extraktions-Doktypen** — die fünf Typen mit eigener Extraktionsaufgabe
(§6a.3), in **Prioritätsreihenfolge** (§6.1); (2) ein Dateiname-Klassifikator, der laut
Struktur-Studie **69 %** der Dateien allein aus dem Namen trifft (Q3). Der Rest bleibt
``sonstiges`` und erscheint unter „Weitere Dokumente" (§7.5) bzw. braucht eine Inhaltsprobe.

Bewusst KEIN Textmuster-Cache (Q1b): der Name steuert nur die Auswahl, der Inhalt wird
einzeln verarbeitet.
"""
from __future__ import annotations

import re

# Extraktions-Doktypen in Prioritätsreihenfolge (§6.1: Eignung → Zuschlag → LB → Vertrag → Aufforderung).
PRIORITY: tuple[str, ...] = (
    "eignung", "zuschlagskriterien", "leistungsbeschreibung", "vertrag", "aufforderung",
)

# (doctype, Dateiname-Regex). Reihenfolge = Vorrang bei Mehrfachtreffer; Prioritäts-Typen zuerst,
# damit ein „Bewerbungsbedingungen"-Dokument als eignung (nicht als sonstiges) landet.
_FILENAME_RULES: tuple[tuple[str, str], ...] = (
    ("eignung",               r"eignung|eignungsnachw|eignungskrit|praequalif|präqualif|"
                              r"bewerbungsbed|teilnahmebed|vergabebed|referenz"),
    ("zuschlagskriterien",    r"zuschlag|wertung|wertungsmatrix|kriterienkatalog|bewertungsmatrix|kriterien"),
    ("leistungsbeschreibung", r"leistungsbeschr|leistungsverz|\blv\b|lastenheft|leistungskatalog|baubeschr|"
                              r"leistungsprogramm"),
    ("vertrag",               r"vertrag|\bevb\b|\bvob\b|\bvol\b|\bagb\b|\bzvb\b|\bbvb\b|"
                              r"besondere.*bedingung|zusaetzliche.*bedingung|zusätzliche.*bedingung"),
    ("aufforderung",          r"aufforder|anschreiben|angebotsauff|deckblatt.*angebot|begleitschreiben"),
    # Nicht-priorisierte Typen (erscheinen unter „Weitere Dokumente", §7.5):
    ("eigenerklaerung",       r"eigenerkl|verpflichtungserkl|\beee\b|einheitliche.?europ"),
    ("formblatt",             r"formblatt|form_|\bvhb\b|\b124\b|\b234\b|\b521\b|\b522\b|\b531\b"),
    ("preisblatt",            r"preisblatt|preisverz|kalkulat|angebotspreis|preistabelle|\bpreise?\b"),
    ("datenschutz",           r"datenschutz|dsgvo|\bavv\b|vertraulichk|verschwiegen"),
)
_COMPILED = tuple((dt, re.compile(pat, re.I)) for dt, pat in _FILENAME_RULES)


def classify(filename: str) -> str:
    """Doktyp aus dem Dateinamen (69 % Trefferquote, Q3). ``sonstiges`` wenn kein Muster greift."""
    name = filename or ""
    for doctype, rx in _COMPILED:
        if rx.search(name):
            return doctype
    return "sonstiges"


def is_priority(doctype: str) -> bool:
    return doctype in PRIORITY


def priority_rank(doctype: str) -> int:
    """0-basierter Rang für die Extraktionsreihenfolge; sehr groß für Nicht-Prioritäts-Typen."""
    return PRIORITY.index(doctype) if doctype in PRIORITY else len(PRIORITY) + 1
