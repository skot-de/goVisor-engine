"""Baustein-Extraktion aus alten Angeboten (Ticket #23, §10.1) + Themen-/Keyword-Zuordnung (§9.3/§9.4).

Der Nutzer lädt frühere eigene Angebote hoch; wiederverwendbare Passagen werden zu Bausteinen.
**Vor** dem Speichern wird PII geschwärzt (``govisor.pii``), Lebenslauf-Passagen werden gar nicht
übernommen (§10.3). Jeder Baustein bekommt ein Thema aus der festen Taxonomie (§9.4) und
abgeleitete Keywords (§9.3, „abgeleitet, nicht abgefragt"). Das Originaldokument wird NICHT
gespeichert (§10.2) — diese Funktion arbeitet nur auf dem übergebenen Text.
"""
from __future__ import annotations

import re
from collections import Counter

from . import pii

# Thema (§9.4) → Erkennungsmuster im Passagentext. Reihenfolge = Vorrang bei Mehrfachtreffer.
_THEME_KW: tuple[tuple[str, str], ...] = (
    ("zertifikate_qm",         r"zertifi|iso ?900\d|iso ?1400\d|qualitätsmanagement|qm-system|präqualif|gütezeichen"),
    ("datenschutz_avv",        r"datenschutz|dsgvo|\bavv\b|auftragsverarbeit|vertraulichk|verschwiegen"),
    ("nachhaltigkeit",         r"nachhaltig|umwelt|co2|klima|ökolog|energieeffizi"),
    ("referenzen",             r"referenz|vergleichbare (?:leistung|projekt|auftr)|projektliste|projektbeispiel"),
    ("personal_qualifikation", r"qualifikation|ausbildung|fachkraft|fachpersonal|schulung|zertifizierte mitarbeiter"),
    ("technische_ausstattung", r"ausstattung|maschinenpark|geräte|fuhrpark|technische ausstattung|werkzeug"),
    ("projektorganisation",    r"projektorganisation|projektablauf|methodik|vorgehensweise|zeitplan|meilenstein|qualitätssicherung"),
    ("unternehmensdarstellung", r"unternehmen|unser haus|gegründet|mitarbeiterzahl|jahresumsatz|firmenprofil|über uns"),
)
_THEME_COMPILED = tuple((t, re.compile(p, re.I)) for t, p in _THEME_KW)

_STOP = frozenset(
    "und oder der die das den dem des ein eine einer eines einem für mit von zur zum bei aus "
    "auf ist sind wird werden wurde haben hat unsere unserer unserem unseren unser sowie durch "
    "sich auch nach über als auch nicht kann können sowie diese dieser dieses alle jeder".split())


def assign_theme(text: str) -> str:
    for theme, rx in _THEME_COMPILED:
        if rx.search(text or ""):
            return theme
    return "sonstiges"


def derive_keywords(text: str, n: int = 5) -> list[str]:
    """Top-Inhaltswörter (≥4 Zeichen, ohne Stopwörter) — abgeleitet, nicht abgefragt (§9.3)."""
    words = [w.lower() for w in re.findall(r"[A-Za-zÄÖÜäöüß]{4,}", text or "")]
    freq = Counter(w for w in words if w not in _STOP)
    return [w for w, _ in freq.most_common(n)]


def _passages(text: str) -> list[str]:
    """Text in Kandidaten-Passagen zerlegen (Absätze/Überschriften)."""
    parts = re.split(r"\n\s*\n+", text or "")
    out = []
    for p in parts:
        p = re.sub(r"[ \t]+", " ", p).strip()
        if len(p) >= 40:                 # zu kurze Fragmente sind keine Bausteine
            out.append(p)
    return out


def extract_blocks(text: str, max_blocks: int = 40) -> dict:
    """Alt-Angebot-Text → Bausteine (§10.1). Rückgabe ``{blocks: [...], skipped_personal: int}``.

    Jeder Baustein: ``{theme, content (PII-geschwärzt), keywords, redactions}``. Lebenslauf-/
    reine Personendaten-Passagen werden übersprungen und gezählt (§10.3-4). ``content`` ist bereits
    geschwärzt — der Aufrufer speichert NUR das (verschlüsselt, §12.3), nie das Original (§10.2)."""
    blocks, skipped = [], 0
    for p in _passages(text):
        if pii.is_mostly_personal(p):
            skipped += 1
            continue
        clean, redactions = pii.redact(p)
        blocks.append({
            "theme": assign_theme(clean),
            "content": clean,
            "keywords": derive_keywords(clean),
            "redactions": redactions,
        })
        if len(blocks) >= max_blocks:
            break
    return {"blocks": blocks, "skipped_personal": skipped}


def participation_tuple(profile_id: str, notice_id: str) -> dict:
    """§11.2: aus einem Import wird AUSSCHLIESSLICH ``profil × verfahren × teilgenommen`` abgeleitet —
    NICHT der Angebotsinhalt, nicht der Preis. Nur nach gesonderter Zustimmung (§11.1) zu schreiben."""
    return {"profile_id": profile_id, "notice_id": notice_id, "participated": True}
