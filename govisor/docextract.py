"""Typisierte, belegpflichtige Extraktion aus Vergabeunterlagen (Ticket #23, §6a).

Kein Universal-Prompt: **je Dokumenttyp** eine eigene Aufgabe mit eigenem Schema und
Few-Shot-Beispielen (§6a.3). Jede Extraktion liefert schema-valide Objekte (keine Prosa),
und jede Aussage der Stufen *Zitat*/*Extrahiert* muss ein **wörtliches, im Quelltext
verifizierbares Zitat** tragen (§6a.2, Belegpflicht) — sonst wird der Eintrag verworfen.

Der LLM-Aufruf ist injizierbar (``chat_fn``), damit Schema-Validierung und Zitat-Verifikation
ohne echten LLM testbar sind. Q1b: kein Textcache — die Qualität kommt aus Schema + Beleg.
"""
from __future__ import annotations

import json
import re

from . import doctax

# Je Extraktions-Doktyp: Ziel, erlaubte req_types, Few-Shot-Beispiele (aus realem Unterlagen-Stil).
_TASKS: dict[str, dict] = {
    "eignung": {
        "ziel": ("K.-o.- und Eignungskriterien: Mindestumsatz, Mindestanzahl und -wert vergleichbarer "
                 "Referenzen, geforderte Zertifikate/Nachweise, Ausschluss-/Mindestbedingungen, "
                 "personelle/technische Mindesteignung, Haftpflicht-Deckung."),
        "req_types": ["mindestumsatz", "referenz_anzahl", "referenz_mindestwert", "zertifikat",
                      "ausschlussgrund", "eignung_technisch", "eignung_personal", "berufshaftpflicht"],
        "beispiele": [
            {"req_type": "referenz_mindestwert", "value": "500000", "unit": "EUR",
             "quote": "Mindestens drei vergleichbare Referenzen aus den letzten fünf Jahren mit einem "
                      "Volumen von je mindestens 500.000 EUR.", "marking": "Zitat"},
            {"req_type": "zertifikat", "value": "ISO 9001", "unit": None,
             "quote": "Der Bieter hat ein gültiges Zertifikat nach DIN EN ISO 9001 vorzulegen.",
             "marking": "Zitat"},
        ],
    },
    "zuschlagskriterien": {
        "ziel": "Zuschlagskriterien mit Gewichten, Punktesysteme, Preis-/Qualitätsanteil.",
        "req_types": ["zuschlagskriterium"],
        "beispiele": [
            {"req_type": "zuschlagskriterium", "value": "Preis", "unit": "60 %",
             "quote": "Die Wertung erfolgt zu 60 % über den Preis und zu 40 % über die Qualität.",
             "marking": "Zitat"},
            {"req_type": "zuschlagskriterium", "value": "Qualität", "unit": "40 %",
             "quote": "Die Wertung erfolgt zu 60 % über den Preis und zu 40 % über die Qualität.",
             "marking": "Zitat"},
        ],
    },
    "leistungsbeschreibung": {
        "ziel": "Leistungsumfang, Mengen, Fristen und technische Mindestanforderungen der Leistung.",
        "req_types": ["leistung_menge", "technische_mindestanforderung", "frist"],
        "beispiele": [
            {"req_type": "technische_mindestanforderung", "value": "24/7-Erreichbarkeit", "unit": None,
             "quote": "Der Auftragnehmer stellt eine Störungsannahme mit 24/7-Erreichbarkeit sicher.",
             "marking": "Zitat"},
            {"req_type": "leistung_menge", "value": "1200", "unit": "Stück",
             "quote": "Zu liefern sind 1.200 Stück gemäß Position 1.1.", "marking": "Zitat"},
        ],
    },
    "vertrag": {
        "ziel": "Vertragsstrafen, Haftungsregelungen, Laufzeit und Verlängerungsoptionen, Kündigungsrechte.",
        "req_types": ["vertragsstrafe", "haftung", "laufzeit", "kuendigung"],
        "beispiele": [
            {"req_type": "vertragsstrafe", "value": "0,2 % je Werktag", "unit": None,
             "quote": "Bei Verzug wird eine Vertragsstrafe von 0,2 % der Auftragssumme je Werktag fällig.",
             "marking": "Zitat"},
            {"req_type": "laufzeit", "value": "24 Monate, +2×12 Monate", "unit": None,
             "quote": "Die Laufzeit beträgt 24 Monate mit der Option auf zweimalige Verlängerung um je "
                      "12 Monate.", "marking": "Zitat"},
        ],
    },
    "aufforderung": {
        "ziel": "Fristen (Angebots-, Frage-, Bindefrist), Formalien und geforderte einzureichende Anlagen.",
        "req_types": ["frist", "einzureichendes_dokument", "formalie"],
        "beispiele": [
            {"req_type": "frist", "value": "2026-08-15 12:00", "unit": None,
             "quote": "Angebote sind bis spätestens 15.08.2026, 12:00 Uhr einzureichen.", "marking": "Zitat"},
            {"req_type": "einzureichendes_dokument", "value": "Eigenerklärung Eignung", "unit": None,
             "quote": "Mit dem Angebot ist die Eigenerklärung zur Eignung (Formblatt 124) einzureichen.",
             "marking": "Zitat"},
        ],
    },
}

_MIN_QUOTE_LEN = 12          # kürzere „Zitate" sind kein Beleg (zu leicht zufällig im Text)
_MAX_ITEMS = 40              # Deckel je Dokument (Ausreißer/Prompt-Injection-Flut bändigen)


def supported(doctype: str) -> bool:
    return doctype in _TASKS


def _normalize(s: str) -> str:
    """Für die Zitat-Suche: Whitespace/Zeilenumbrüche kollabieren, casefold (§6a.2)."""
    return re.sub(r"\s+", " ", (s or "")).strip().casefold()


def verify_quote(quote: str, text: str) -> bool:
    """Wörtliches Zitat im Quelltext auffindbar (normalisiert)? Belegpflicht §6a.2."""
    q = _normalize(quote)
    if len(q) < _MIN_QUOTE_LEN:
        return False
    return q in _normalize(text)


def validate_item(item: dict, allowed_req_types: set[str] | None = None) -> bool:
    """Schema-Prüfung (§6a.1): dict, gültiger req_type, gültige marking, Beleg wo Pflicht."""
    if not isinstance(item, dict):
        return False
    rt = item.get("req_type")
    if not doctax.is_valid_req_type(rt):
        return False
    if allowed_req_types is not None and rt not in allowed_req_types:
        return False
    marking = item.get("marking")
    if marking not in doctax.MARKINGS:
        return False
    quote = item.get("quote")
    if marking in doctax.MARKINGS_REQUIRE_QUOTE and not (isinstance(quote, str) and quote.strip()):
        return False
    return True


def build_messages(doctype: str, text: str, source_file: str, cap: int = 60000) -> list[dict]:
    task = _TASKS[doctype]
    schema = ('{"req_type": <einer aus der Liste>, "value": <Wert oder null>, "unit": <Einheit oder null>, '
              '"quote": "<wörtliches Zitat aus dem Text>", "source_page": <Seitenzahl oder null>, '
              '"marking": "Zitat|Extrahiert|Abgeleitet"}')
    sys = (
        "Du bist Vergabe-Analyst und extrahierst aus EINEM Dokument einer öffentlichen Ausschreibung "
        "(DE/CH) strukturierte Anforderungen. Extrahiere NUR, was wörtlich belegbar im Text steht — "
        "nichts erfinden, nichts aus Allgemeinwissen ergänzen.\n"
        f"Ziel für diesen Dokumenttyp: {task['ziel']}\n"
        f"Erlaubte req_type-Werte (ausschließlich diese): {', '.join(task['req_types'])}.\n"
        "Antworte als JSON-ARRAY von Objekten, jedes Objekt exakt in diesem Schema:\n"
        f"{schema}\n"
        "Regeln: 'quote' ist ein WÖRTLICHES, zusammenhängendes Zitat aus dem Text (nicht paraphrasiert). "
        "marking='Zitat' wenn die Aussage wörtlich dasteht; 'Extrahiert' wenn du sie strukturiert aus dem "
        "Zitat ableitest; 'Abgeleitet' nur für Einschätzungen (dann darf 'quote' fehlen). "
        "Gib ein leeres Array [] zurück, wenn nichts Belegbares vorhanden ist. Keine Erklärungen, nur JSON."
    )
    examples = json.dumps(task["beispiele"], ensure_ascii=False)
    user = f"Beispiele für gültige Objekte:\n{examples}\n\n--- DOKUMENT ({source_file}) ---\n{text[:cap]}"
    return [{"role": "system", "content": sys}, {"role": "user", "content": user}]


def _parse_array(raw: str) -> list | None:
    txt = re.sub(r"^```json|^```|```$", "", (raw or "").strip(), flags=re.M).strip()
    try:
        data = json.loads(txt)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):                       # LLM lieferte ein einzelnes Objekt statt Array
        data = [data]
    return data if isinstance(data, list) else None


def extract(doctype: str, text: str, source_file: str, chat_fn=None,
            model: str | None = None) -> dict:
    """Ein Dokument → verifizierte Anforderungsliste + Verwerfungszahl.

    Rückgabe: ``{"items": [...], "rejected": int, "skipped"?: bool, "parse_error"?: bool}``.
    Jedes item trägt zusätzlich ``theme`` (aus der Taxonomie) und ``source_file``. Schema-invalide
    oder unbelegte Einträge (Zitat nicht im Quelltext) werden verworfen und gezählt (§6a.2).
    """
    if doctype not in _TASKS:
        return {"items": [], "rejected": 0, "skipped": True}
    if chat_fn is None:
        from .llm import chat as chat_fn                      # lazy: Tests injizieren einen Fake
    task = _TASKS[doctype]
    allowed = set(task["req_types"])
    messages = build_messages(doctype, text, source_file)

    parsed = None
    for _ in range(2):                                        # schema-invalide Antwort 1× wiederholen (§6a.1)
        try:
            raw = chat_fn(messages, model=model) if model else chat_fn(messages)
        except TypeError:
            raw = chat_fn(messages)
        parsed = _parse_array(raw)
        if parsed is not None:
            break
    if parsed is None:
        return {"items": [], "rejected": 0, "parse_error": True}

    items, rejected = [], 0
    for raw_item in parsed[:_MAX_ITEMS]:
        if not validate_item(raw_item, allowed):
            rejected += 1
            continue
        marking = raw_item["marking"]
        quote = raw_item.get("quote") or ""
        if marking in doctax.MARKINGS_REQUIRE_QUOTE and not verify_quote(quote, text):
            rejected += 1                                     # Belegpflicht verletzt → verwerfen (§6a.2)
            continue
        rt = raw_item["req_type"]
        items.append({
            "req_type": rt,
            "label": doctax.REQ_TYPES[rt][0],
            "theme": doctax.theme_for(rt),
            "value": raw_item.get("value"),
            "unit": raw_item.get("unit"),
            "quote": quote,
            "source_file": source_file,
            "source_page": raw_item.get("source_page"),
            "marking": marking,
        })
    return {"items": items, "rejected": rejected}
