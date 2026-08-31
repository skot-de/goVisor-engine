"""RIB (meinauftrag.rib.de) — die Umleitung ist kein Urteil.

Ohne Netz. Geprüft wird, in welche Klasse die drei Ausgänge fallen; das entscheidet, ob ein
Vorgang je wieder angefasst wird.
"""
from __future__ import annotations

from govisor import docfetch_queue as q

QUELLE = __import__("pathlib").Path(__file__).resolve().parent.parent / "govisor" / "docfetch_rib.py"
CODE = "\n".join(z for z in QUELLE.read_text(encoding="utf-8").splitlines()
                 if not z.lstrip().startswith("#"))


def test_umleitung_ist_nicht_dauerhaft():
    """⚠ Der Fehler, der 105 Vorgänge dauerhaft abschrieb.

    `/public/unavailable` ist ein Zustand des Augenblicks, keine Eigenschaft des Vorgangs.
    Als `abgelaufen` (DAUERHAFT) abgelegt wurde er nie wieder versucht — nachgemessen am
    2026-08-31 an 18 Fällen: 13 luden herunter, 7 bis 32 Dateien.
    """
    assert "nicht_abrufbar" in CODE
    assert "nicht_abrufbar" not in q.DAUERHAFT
    assert "nicht_abrufbar" not in q.KEIN_FEHLSCHLAG
    assert "nicht_abrufbar" not in q.BLOCKIERT, "es soll nach der Sperrfrist wiederkommen"


def test_rib_stuft_nichts_mehr_als_abgelaufen_ein():
    """`abgelaufen` bleibt den Abrufern vorbehalten, bei denen das Portal die Frist
    AUSDRÜCKLICH nennt (netserver, subreport, evergabe-online, aumass). Aus einer Umleitung
    lässt sie sich nicht ableiten."""
    assert '"abgelaufen"' not in CODE


def test_die_belegten_urteile_bleiben():
    """Was RIB wirklich belegen kann, behält seine Klasse."""
    assert "nur_bekanntmachung" in CODE and "nur_bekanntmachung" in q.KEIN_FEHLSCHLAG
    assert "kein_listenlayout" in CODE
    assert q.BLOCKIERT.get("kein_listenlayout") == "parser", "unser Problem, kein fehlender Zugang"
    assert "weg" in CODE and "weg" in q.DAUERHAFT


def test_rueckfall_auf_die_bekanntmachung_bleibt():
    """Bei fehlendem `documentsAttachments` nimmt der Abrufer, was da ist — und beschriftet
    es ehrlich. Nachgemessen: 83 % dieser Fälle geben weiter nur die Bekanntmachung her."""
    assert "bekanntmachungslinks" in CODE
