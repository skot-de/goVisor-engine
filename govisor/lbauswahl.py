"""Welcher Ausschnitt der Leistungsbeschreibung ans Modell geht.

**Warum es das gibt.** Eine LB ist im Median 172.000 Zeichen lang, ans Modell gehen 60.000
(`docextract.build_messages`). Die naheliegende Antwort — mehr schicken — ist gemessen und
widerlegt: 96 gepaarte Vorgaenge, 2,7× Text, 10 % WENIGER belegte Eintraege und 69 % mehr
Verwerfungen (s. Warnung ueber `build_messages`). Die Frage ist also nicht die Menge,
sondern die Auswahl.

**Stand der Messung (2026-08-22, 47 vollstaendige Dreiergruppen, gleiches Budget):**

    Verfahren   Zeichen Ø   Eintraege je Vorgang   Verwerfungsquote
    anfang         60.000                   30,5             18,0 %
    fenster        52.489                   33,3             10,4 %
    gemischt       54.859                   31,4              9,5 %

⚠ **Das ist ein Hinweis, kein Nachweis.** Die gepaarten Vorzeichentests tragen es nicht
(Eintraege 21:15, p ≈ 0,41; Verwerfungen 16:17, p ≈ 1,00). Die schoene Quote kommt von
wenigen Vorgaengen mit vielen Verwerfungen. Deshalb laeuft `anfang` als KONTROLLGRUPPE
weiter mit — die Pruefung sammelt sich ueber die Zeit im Normalbetrieb an, statt einen
eigenen bezahlten Versuch zu brauchen. Auswertung: `scripts/lb_auswahl_stand.py`.

Uebernommen wurde `fenster` trotz fehlender Signifikanz, weil es in KEINER gemessenen
Groesse schlechter ist und dabei 13 % weniger Text schickt — die Ersparnis steht auch dann,
wenn die Verbesserung sich nicht bestaetigt.
"""
from __future__ import annotations

import hashlib
import os
import re

BUDGET = 60_000
FENSTER = 1_500
# Anteil der Vorgaenge, die weiter mit `anfang` laufen. Klein genug, um kaum zu kosten,
# gross genug, um sich in Wochen zu einer Aussage zu summieren.
KONTROLLE = float(os.environ.get("GOVISOR_LB_KONTROLLE", "0.10"))

# Die Sprache der ANFORDERUNG, nicht die der Position. Aus den `req_types` abgeleitet, die
# die Extraktion tatsaechlich sucht — Fristen, Mindestanforderungen, Vertragsstrafen.
MUSTER = re.compile(
    r"mindestens|spätestens|vorzulegen|einzureichen|nachzuweisen|erforderlich|"
    r"muss|müssen|hat der (auftragnehmer|bieter)|ist verpflichtet|"
    r"vertragsstrafe|gewährleistung|haftung|kündigung|frist|termin|"
    r"anforderung|\bnorm\b|\bdin \b|\bvde \b|zulassung|zertifikat|nachweis|"
    r"gewichtung|wertung|zuschlag", re.I)


def _bloecke(text: str, ab: int = 0) -> list[tuple[int, int, float]]:
    """Zusammengefasste Fenster um Treffer, je mit ihrer Trefferdichte."""
    treffer = [m.start() for m in MUSTER.finditer(text, ab)]
    if not treffer:
        return []
    roh: list[tuple[int, int]] = []
    start = ende = None
    for pos in treffer:
        a, b = max(ab, pos - FENSTER // 2), min(len(text), pos + FENSTER // 2)
        if start is None:
            start, ende = a, b
        elif a <= ende:
            ende = max(ende, b)
        else:
            roh.append((start, ende))
            start, ende = a, b
    if start is not None:
        roh.append((start, ende))
    return [(a, b, sum(1 for p in treffer if a <= p < b) / max(1, b - a)) for a, b in roh]


def _sammle(text: str, bloecke, budget: int) -> str:
    """Dichteste Bloecke nehmen — aber in DOKUMENTREIHENFOLGE ausgeben.

    ⚠ Die Reihenfolge ist kein Schoenheitsfehler. Nach Dichte ausgegeben liest das Modell
    einen Flickenteppich, in dem Rueckbezuege („der genannte Nachweis", „diese Frist") ins
    Leere zeigen.
    """
    gewaehlt, rest = [], budget
    for a, b, _ in sorted(bloecke, key=lambda x: -x[2]):
        if rest <= 0:
            break
        laenge = min(b - a, rest)
        gewaehlt.append((a, a + laenge))
        rest -= laenge
    gewaehlt.sort()
    return "\n[…]\n".join(text[a:b] for a, b in gewaehlt)


def anfang(text: str, budget: int = BUDGET) -> str:
    """Kontrollgruppe: die ersten Zeichen, wie bis zum 22.08.2026 ueberall."""
    return text[:budget]


def fenster(text: str, budget: int = BUDGET) -> str:
    """Fenster um Anforderungssprache, ueber das ganze Dokument verteilt."""
    bl = _bloecke(text)
    return _sammle(text, bl, budget) if bl else text[:budget]


def gemischt(text: str, budget: int = BUDGET, kopf: int = 20_000) -> str:
    """Kopf behalten UND den Rest nach Dichte waehlen. Gemessen zwischen den beiden."""
    vorn = text[:kopf]
    bl = _bloecke(text, ab=kopf)
    return vorn + ("\n[…]\n" + _sammle(text, bl, budget - kopf) if bl else "")


VERFAHREN = {"anfang": anfang, "fenster": fenster, "gemischt": gemischt}


def verfahren_fuer(notice_id: str) -> str:
    """Welches Verfahren dieser Vorgang bekommt — stabil, nicht zufaellig.

    ⚠ Aus dem Hash der Kennung, nicht aus `random`: derselbe Vorgang bekommt bei einer
    Neuberechnung dasselbe Verfahren. Sonst vergleicht die Auswertung spaeter Vorgaenge
    mit sich selbst unter zwei Verfahren und haelt den Unterschied fuer einen Effekt.
    """
    if KONTROLLE <= 0:
        return "fenster"
    h = int(hashlib.md5((notice_id or "").encode()).hexdigest(), 16) % 1000
    return "anfang" if h < KONTROLLE * 1000 else "fenster"


def waehle(text: str, notice_id: str, budget: int = BUDGET) -> tuple[str, str]:
    """(Ausschnitt, Name des Verfahrens). Kurze Texte gehen unveraendert durch."""
    if len(text) <= budget:
        return text, "ganz"
    art = verfahren_fuer(notice_id)
    return VERFAHREN[art](text, budget), art
