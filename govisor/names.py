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

from . import locales

# ⚠ DAS HOHEITSMUSTER LIEGT IM LÄNDERPROFIL, NICHT HIER. Es stand bis 2026-10-06 als
# modulfeste deutsche Regex an dieser Stelle — angewandt auf ALLE Länder. Folge, gemessen:
# „Republik Österreich vertreten durch die Bundesministerin für Landesverteidigung" (5.251
# AT-Zeilen) wurde nie aufgelöst, weil „Republik Österreich" in einem deutschen Muster nicht
# vorkommt. Jetzt: `locales.active().re_sovereign` (s. EU-weit-Grundsatz in CLAUDE.md).

# Trenner der Vertretungskette: „, vertreten durch[:] ", „ diese(s) vertreten durch ",
# „endvertreten durch", auch „handelnd durch" (gleichbedeutend).
# ⚠ `(?:end)?` MUSS HIER STEHEN, und `\b` davor. Ohne beides matchte „vertreten" innerhalb
# von „endvertreten", das „end" blieb stehen und wurde Teil des Schlüssels:
# `'land schleswig holstein end'` (1.679 Zeilen), `'bundesrepublik deutschland end'` (567).
_VERTRETEN = re.compile(
    r"\s*[,;]?\s*(?:diese[rs]?\s+)?\b(?:end)?(?:vertreten|handelnd)\s+durch\s*:?\s*", re.I)
# führender Artikel der vertretenen Stelle („das Bundesministerium …" → „Bundesministerium …")
# ⚠ `\b\s*` statt `\s+`: bei einem abgeschnittenen Namen („… vertreten durch den") blieb der
# Artikel sonst als ganzer Name stehen — gemessen 7 Anzeigenamen, die wörtlich „Den"/„Das"
# hiessen, und im Schlüssel eine Entität `den`.
_LEAD_ART = re.compile(r"^(?:der|die|das|den|dem|des)\b\s*", re.I)
# Was nach dem Abschneiden übrig bleiben MUSS, damit es eine Stelle benennt. Ein Rest ohne
# Buchstaben (oder leer) ist keine Vergabestelle → Rückfall auf den Präfix.
_HAT_WORT = re.compile(r"[^\W\d_]{2,}", re.U)
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
    Behörde) — stabil + wiedererkennbar; tiefere „dieses vertreten durch"-Ebenen fallen weg.

    ⚠ DIESE FUNKTION ENTSCHEIDET SEIT 2026-10-06 AUCH DEN MERGE-SCHLÜSSEL, nicht nur den
    Anzeigenamen. Vorher lief sie allein auf der Anzeige, während `normalize_company` die
    Klausel stumpf abschnitt und den GENERISCHEN Präfix behielt — die Entität hiess dann
    `freistaat bayern` und sammelte 297 fremde Stellen, während die Anzeige daneben
    „Staatliches Hochbauamt Würzburg" zeigte. Ein Name, 297 Auftraggeber dahinter. Das ist
    Fallenkatalog C9 in seiner teuersten Form (s. `entities.normalize_company`).

    Welcher Präfix generisch ist, sagt das aktive Länderprofil (``re_sovereign``) — nicht
    diese Datei.
    """
    if not _VERTRETEN.search(name or ""):
        return name
    tail = _VERTRETEN.split(name, maxsplit=1)
    prefix = tail[0]
    rest = tail[1] if len(tail) > 1 else ""
    if locales.active().re_sovereign.match(prefix):
        # vertretene Stelle nehmen; weitere Vertretungsebenen abschneiden, führenden Artikel weg
        body = _VERTRETEN.split(rest, maxsplit=1)[0]
        body = re.sub(r"\s*[,–-]\s*$", "", body).strip()
        body = _LEAD_ART.sub("", body).strip()
        # Ein Rest, der kein Wort mehr enthält, benennt keine Stelle (abgeschnittene Namen:
        # „… vertreten durch den"). Dann ist der Hoheitsträger die beste verfügbare Auskunft.
        if _HAT_WORT.search(body):
            return body
        return _TRAIL.sub("", prefix).strip()
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
