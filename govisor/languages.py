"""Sprachcodes vereinheitlichen — ein System statt drei.

**Das Problem.** Der Bestand führt dieselbe Sprache in drei Schreibweisen nebeneinander:
`DE` (2,25 Mio.), `DEU` (2,20 Mio.) und `de`. Grund ist die Quelle: die Legacy-Formulare
nutzen ISO-639-1 im `LG`-Attribut, eForms ISO-639-2/T in `languageID`, und einzelne Pfade
liefern Kleinschreibung. Gemessen sind es **56 verschiedene Codes für 24 Sprachen**.

Für eine Sprachumschaltung ist das unbrauchbar: wer nach `de` filtert, verliert die Hälfte.

**Zielsystem: ISO-639-1, klein.** Nicht aus Geschmack — das ist der Code, den der Browser
im `Accept-Language`-Header schickt, den das HTML-`lang`-Attribut erwartet und den jede
i18n-Bibliothek verwendet. Alles andere müsste an der Oberfläche wieder umgerechnet werden.

**Mehrwertige Angaben** (`DE;IT`, `IT;DE`, `DE IT` — 122 Zeilen, alle aus Südtirol) werden
NICHT auf einen Wert reduziert, sondern auf `de;it` vereinheitlicht. Die Zweisprachigkeit
ist eine Tatsache über die Vergabe, kein Formatfehler.

**Unbekanntes bleibt stehen** (nur kleingeschrieben). Ein Code, den diese Tabelle nicht
kennt, ist eine Lücke im Mapping — ihn zu verwerfen würde sie verstecken.
"""
from __future__ import annotations

import re

# ISO-639-2/T → ISO-639-1. Vollständig für die 24 im Bestand gemessenen Drei-Buchstaben-
# Codes; die Liste ist an den Daten erhoben, nicht aus dem Gedächtnis geschrieben.
_ISO3 = {
    "bul": "bg", "ces": "cs", "dan": "da", "deu": "de", "ell": "el", "eng": "en",
    "est": "et", "fin": "fi", "fra": "fr", "gle": "ga", "hrv": "hr", "hun": "hu",
    "ita": "it", "lav": "lv", "lit": "lt", "mlt": "mt", "nld": "nl", "pol": "pl",
    "por": "pt", "ron": "ro", "slk": "sk", "slv": "sl", "spa": "es", "swe": "sv",
    # Bibliografische Varianten (ISO-639-2/B) — TED liefert sie zwar nicht, aber sie
    # kosten nichts und ersparen später eine Fehlersuche.
    "ger": "de", "fre": "fr", "dut": "nl", "gre": "el", "cze": "cs", "slo": "sk",
    "rum": "ro", "may": "ms", "ice": "is",
}

_TRENNER = re.compile(r"[;,/ ]+")


def normalize(code: str | None) -> str | None:
    """Ein Sprachcode → ISO-639-1, klein. Mehrwertiges bleibt mehrwertig (`de;it`).

    None und Leerstrings kommen unverändert als None zurück — „keine Angabe" ist eine
    Aussage und wird nicht zu einer erfundenen Sprache.
    """
    if not code:
        return None
    teile = [t for t in _TRENNER.split(str(code).strip()) if t]
    if not teile:
        return None
    aus: list[str] = []
    for t in teile:
        k = t.lower()
        k = _ISO3.get(k, k)
        if k not in aus:            # `DE;DE` → `de`
            aus.append(k)
    return ";".join(aus)
