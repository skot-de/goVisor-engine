"""Anzeige-Namen von Vergabestellen bereinigen — für saubere Profil-/Käufer-Vorschläge.

Zwei Probleme im Rohbestand, beide gemessen (2026-07-29, DE):

1. **„Bundesrepublik Deutschland, vertreten durch <X>"** (≈15k Käufer). Der generische Hoheits-
   Träger ist bedeutungslos; die **vertretene** Stelle <X> (Bundesministerium …, Autobahn GmbH …)
   ist die echte Vergabestelle. Achtung: bei SPEZIFISCHEN Präfixen („DB Netz AG, vertreten durch …",
   „Max-Planck-Gesellschaft …") ist der PRÄFIX die Stelle — dann NICHT die Vertretung nehmen.

2. **Uneinheitliche Schreibweise** — 30 % der distinkten Käufer-Namen sind KOMPLETT GROSS
   (Legacy-TED-Ära), der Rest gemischt. Für Anzeige/Vorschläge auf eine Form bringen.

``clean_display_name`` löst beides. Reiner String-Transform, idempotent, ohne Netz/DB. Wird auf
``entities.canonical_name`` angewandt (Gold), fließt damit in Käufer-Anzeige + Profil-Vorschläge.
Bewusst konservativ: im Zweifel wird NICHT umgeschrieben (lieber roh als falsch aufgelöst).
"""
from __future__ import annotations

import re

# Generische Hoheits-Träger: hier ist die VERTRETENE Stelle die echte Vergabestelle.
_SOVEREIGN = re.compile(
    r"^\s*(?:die\s+)?"
    r"(?:bundesrepublik\s+deutschland"
    r"|(?:das\s+|der\s+|die\s+)?(?:land|freistaat|bundesland)\s+[a-zäöüß][a-zäöüß.\-]+"
    r"|freie(?:\s+und)?\s+hansestadt\s+[a-zäöüß\-]+"
    r"|freie\s+hansestadt\s+[a-zäöüß\-]+)"
    r"\s*(?:,|$)", re.I)

# Trenner der Vertretungskette: „, vertreten durch[:] ", „ diese(s) vertreten durch ",
# auch „handelnd durch" (gleichbedeutend). Doppelpunkt/Komma/Whitespace toleriert.
_VERTRETEN = re.compile(
    r"\s*[,;]?\s*(?:diese[rs]?\s+)?(?:vertreten|handelnd)\s+durch\s*:?\s*", re.I)
# führender Artikel der vertretenen Stelle („das Bundesministerium …" → „Bundesministerium …")
_LEAD_ART = re.compile(r"^(?:der|die|das|den|dem|des)\s+", re.I)
# nachgestellter Vertretungs-Zusatz ohne „durch" („BRD, Bundesministerium für …") am Präfix
_TRAIL = re.compile(r"\s*[,–-]\s*$")

# Deutsche Titel-Schreibung: Partikel klein (außer am Wortanfang).
_LOWER = {"und", "oder", "der", "die", "das", "den", "dem", "des", "für", "im", "in",
          "am", "an", "auf", "aus", "bei", "mit", "nach", "von", "vom", "zu", "zur", "zum",
          "über", "unter", "vor", "durch", "gegen", "ohne", "um"}
# Tokens, die groß/gemischt bleiben (Rechtsformen, gängige Kürzel).
_KEEP = {
    "gmbh": "GmbH", "mbh": "mbH", "ggmbh": "gGmbH", "ag": "AG", "kg": "KG", "kgaa": "KGaA",
    "ohg": "OHG", "ug": "UG", "se": "SE", "eg": "eG", "ev": "e.V.", "e.v.": "e.V.",
    "aör": "AöR", "aor": "AöR", "kdör": "KdöR", "gbr": "GbR",
    "it": "IT", "edv": "EDV", "db": "DB", "kfw": "KfW", "dlr": "DLR", "thw": "THW",
    "bima": "BImA", "bwi": "BWI", "rwth": "RWTH", "tu": "TU", "fh": "FH", "hs": "HS",
    "nrw": "NRW", "wsa": "WSA", "asfinag": "ASFINAG",
}
_ROMAN = re.compile(r"^[ivxlcdm]+$", re.I)


def _titlecase_token(tok: str, first: bool) -> str:
    low = tok.lower()
    if low in _KEEP:
        return _KEEP[low]
    if not first and low in _LOWER:
        return low
    if _ROMAN.match(tok) and len(tok) <= 4:      # „III", „IV"
        return tok.upper()
    # Bindestrich-Komposita je Teil (Baden-Württemberg, Rhein-Main-Donau)
    if "-" in tok:
        return "-".join(_titlecase_token(p, False) if p else p for p in tok.split("-"))
    if not tok:
        return tok
    return tok[0].upper() + tok[1:].lower()


def _titlecase(name: str) -> str:
    parts = re.split(r"(\s+)", name)          # Whitespace erhalten
    out, seen_word = [], False
    for p in parts:
        if p.isspace() or not p:
            out.append(p)
            continue
        out.append(_titlecase_token(p, first=not seen_word))
        seen_word = True
    return "".join(out)


def normalize_case(name: str) -> str:
    """KOMPLETT GROSS / komplett klein → Titel-Schreibung. Gemischtes bleibt unangetastet
    (dort hat die Quelle die Groß/Kleinschreibung bereits gesetzt)."""
    letters = [c for c in name if c.isalpha()]
    if not letters:
        return name
    if all(c.isupper() for c in letters) or all(c.islower() for c in letters):
        return _titlecase(name)
    return name


def resolve_representation(name: str) -> str:
    """„Bundesrepublik Deutschland, vertreten durch <X>" → <X> (nur bei generischem Hoheits-Präfix).
    Bei spezifischem Präfix (DB Netz AG, Stadt München …) wird die Vertretungsklausel entfernt und
    der Präfix behalten. Kette: die ERSTE vertretene Stelle nach dem Hoheits-Träger (Ministerium/
    Behörde) — stabil + wiedererkennbar; tiefere „dieses vertreten durch"-Ebenen fallen weg."""
    if not _VERTRETEN.search(name):
        return name
    # (Hier stand eine Dreifachzuweisung, die denselben `split` zweimal ausfuehrte und
    # zwei der drei Namen nie benutzte.)
    tail = _VERTRETEN.split(name, maxsplit=1)
    prefix = tail[0]
    rest = tail[1] if len(tail) > 1 else ""
    if _SOVEREIGN.match(prefix):
        # vertretene Stelle nehmen; weitere Vertretungsebenen abschneiden, führenden Artikel weg
        body = _VERTRETEN.split(rest, maxsplit=1)[0]
        body = re.sub(r"\s*[,–-]\s*$", "", body).strip()
        body = _LEAD_ART.sub("", body).strip()
        return body or prefix
    # spezifischer Präfix → Vertretung droppen, Präfix behalten
    return _TRAIL.sub("", prefix).strip()


def clean_display_name(raw: str | None) -> str | None:
    """Vertretene Stelle auflösen + Casing vereinheitlichen. Idempotent, konservativ."""
    if not raw:
        return raw
    name = re.sub(r"\s+", " ", raw).strip()
    name = resolve_representation(name)
    name = normalize_case(name)
    return re.sub(r"\s+", " ", name).strip()
