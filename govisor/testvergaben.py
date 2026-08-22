"""Testausschreibungen erkennen — Übungsvorgänge, die keine echte Vergabe sind.

Portale legen Vorgänge an, damit Bieter die elektronische Angebotsabgabe üben können
(„Testvergabe für Bieter zur Übung der Angebotsabgabe"), und Behörden testen ihre eigene
Anbindung („TESTDL2025" der Bundesrechenzentrum GmbH, 524 Mio € Auftragswert). Solche
Vorgänge stehen im Bestand wie jede andere Vergabe und werden Nutzern als echte Ausschreibung
angezeigt.

⚠ WARUM DAS MUSTER SO ENG IST. „test" als Wortbestandteil ist im Vergabewesen völlig normal:
gemessen am 2026-08-22 tragen **203 von 43.642** Einträgen „test" im Titel — Testautomation,
Wafer Testing, SOC-Testsystem, eID Testbed, Materialprüfung. Ein Muster auf den Wortbestandteil
würde 196 echte Vergaben mit wegwerfen. Deshalb greift die Regel nur, wenn der TITEL ALS GANZES
die Testmarke ist. Sie findet damit genau 7 Vorgänge und lässt die 196 unberührt.

Eine Marke, zwei Verwender: `gold.py` setzt daraus das Qualitätsmerkmal `testvergabe`
(markieren statt filtern, wie bei allen anderen Merkmalen), `export_web_leads.py` nimmt sie
aus dem Frontend heraus. Das Muster steht deshalb hier und nicht zweimal woanders.
"""
import re

# POSIX-tauglich formuliert, damit dasselbe Muster in Python UND in DuckDB gilt.
# (?i) macht es fallunabhängig; DuckDB versteht das Präfix ebenso wie Python.
MUSTER = (
    r"(?i)^\s*("
    r"test[a-z0-9_-]{0,12}"                        # TESTDL2025, TESTAUSSCHREIBUNG, TEST-1
    r"|testausschreibung.*"                        # „TESTAUSSCHREIBUNG …"
    r"|testvergabe.*"                              # „Testvergabe für Bieter zur Übung …"
    r"|test\s*[/-]\s*schulungsverfahren.*"         # „Test / Schulungsverfahren …"
    r"|(dies\s+ist\s+)?eine?\s+test.*"             # „Dies ist eine Testausschreibung"
    r")\s*$"
)
_RX = re.compile(MUSTER)


def ist_testvergabe(titel: str | None) -> bool:
    """Ist der Titel als Ganzes eine Testmarke?"""
    return bool(titel and _RX.match(titel.strip()))


def sql_bedingung(spalte: str) -> str:
    """Dieselbe Regel als SQL-Ausdruck für DuckDB."""
    return f"regexp_matches({spalte}, '{MUSTER}')"
