"""Adressfelder in Ordnung bringen — an der Stelle, wo sie benutzt werden.

**Warum nicht im Silber.** Silber bildet ab, was die Quelle geschickt hat; das ist der Sinn
der Ebene und die Grundlage jeder späteren Fehlersuche. Gemessen am 2026-08-18 über 4,3 Mio.
Parteizeilen:

    Ort ist eine Zahl (Felder vertauscht)   1.332
    PLZ ohne jede Ziffer                    1.858
    ohne Ortsangabe                       479.019  (11 %)

Die ersten beiden verteilen sich über ALLE Jahrgänge und über 13 schreibende Module — sie
kommen also aus den Bekanntmachungen selbst. Sie dort zu überschreiben hiesse, den Beleg zu
verlieren, an dem man einen Parser-Fehler von einem Quellenfehler unterscheidet.

**Wie sie sich bemerkbar machen.** Beim Prüfen der Entitäten-Zusammenführungen stand da
„Wasserstrassen- und Schifffahrtsamt Mosel-Saar-Lahn, Ort=56070, PLZ=Koblenz". Eine
Ortsprüfung, die das für bare Münze nimmt, meldet einen Widerspruch, wo keiner ist — und
genau das ist heute mehrfach passiert.
"""
from __future__ import annotations

import re

_NUR_ZIFFERN = re.compile(r"^[0-9][0-9 /-]*$")
_HAT_ZIFFER = re.compile(r"[0-9]")
_BUCHSTABE = re.compile(r"[A-Za-zÄÖÜäöüß]")


def normalisiere(ort: str | None, plz: str | None) -> tuple[str | None, str | None, bool]:
    """``(ort, plz, korrigiert)``. Tauscht vertauschte Felder, sonst unverändert.

    Die Regel ist bewusst eng: getauscht wird NUR, wenn beide Seiten eindeutig zur anderen
    passen — der Ort besteht aus Ziffern UND die PLZ enthält Buchstaben, aber keine Ziffer.
    Ein „D-56070" in der PLZ ist deshalb kein Tauschgrund (Ländervorsatz, kommt häufig vor),
    und ein Ort namens „1. Bezirk" auch nicht (er hat einen Buchstaben).

    Was nicht eindeutig ist, bleibt liegen. Eine Adresse falsch zu drehen ist schlimmer als
    eine, die schief bleibt: nach dem Ort wird gefiltert und gruppiert.
    """
    o = (ort or "").strip() or None
    p = (plz or "").strip() or None
    if not o or not p:
        return o, p, False
    ort_ist_zahl = bool(_NUR_ZIFFERN.fullmatch(o))
    plz_ist_wort = bool(_BUCHSTABE.search(p)) and not _HAT_ZIFFER.search(p)
    if ort_ist_zahl and plz_ist_wort:
        return p, o, True
    return o, p, False


def sql_ort(ort_spalte: str = "town", plz_spalte: str = "postal_code") -> str:
    """Dieselbe Regel als SQL-Ausdruck — für die Stellen, die in DuckDB rechnen.

    Zwei Fassungen derselben Logik sind eine Fehlerquelle; deshalb steht die SQL-Fassung
    hier neben der Python-Fassung und nicht verstreut in den Skripten. Wer eine ändert,
    sieht die andere.
    """
    return (f"CASE WHEN regexp_matches({ort_spalte}, '^[0-9][0-9 /-]*$') "
            f"AND regexp_matches({plz_spalte}, '[A-Za-zÄÖÜäöüß]') "
            f"AND NOT regexp_matches({plz_spalte}, '[0-9]') "
            f"THEN {plz_spalte} ELSE {ort_spalte} END")


def sql_plz(ort_spalte: str = "town", plz_spalte: str = "postal_code") -> str:
    """Gegenstück zu :func:`sql_ort` — die PLZ nach demselben Tausch."""
    return (f"CASE WHEN regexp_matches({ort_spalte}, '^[0-9][0-9 /-]*$') "
            f"AND regexp_matches({plz_spalte}, '[A-Za-zÄÖÜäöüß]') "
            f"AND NOT regexp_matches({plz_spalte}, '[0-9]') "
            f"THEN {ort_spalte} ELSE {plz_spalte} END")
