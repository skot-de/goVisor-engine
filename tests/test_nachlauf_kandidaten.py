"""Die Nachlauf-Rechnung nennt die Vorgaenge, bei denen ein Nachlauf etwas aendert.

⚠ WARUM DAS EIN EIGENER WAECHTER IST. Die Zahl entscheidet ueber Geld. Am 2026-09-21 lag
die naheliegende Antwort („alle veralteten Auswertungen", 3.344, 43 bis 71 USD) um mehr als
das Doppelte daneben: nur 651 davon enthalten ueberhaupt eine Datei, die heute anders
eingeordnet wuerde. Eine Rechnung, die still zur Obergrenze zurueckfaellt, ist schlimmer
als keine — sie sieht aus wie eine Messung.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SONDE = WURZEL / "scripts" / "nachlauf_kandidaten.py"


def _lauf():
    return subprocess.run([sys.executable, str(SONDE)], capture_output=True, text=True,
                          cwd=WURZEL, timeout=300)


def test_die_rechnung_laeuft_und_trennt_die_zwei_schienen():
    r = _lauf()
    if r.returncode == 2:
        return                      # keine Auswertungen im Baum — kein Befund
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-400:]
    assert "ohne analysiert_am" in r.stdout and "mit analysiert_am" in r.stdout, (
        "die zwei Schienen sind zusammengefallen; dann sagt die Zahl nicht mehr, ob die "
        "Veralterung oder die juengste Regel der Grund ist")
    assert "Untergrenze" in r.stdout, "die Rechnung nennt ihre eigene Grenze nicht mehr"


def test_die_rechnung_zaehlt_nicht_einfach_alle_auswertungen():
    """⚠ Der eigentliche Anspruch. Betroffen ist, wo sich etwas AENDERT — nicht alles, was
    alt ist."""
    r = _lauf()
    if r.returncode == 2:
        return
    zahlen = []
    for zeile in r.stdout.splitlines():
        if "Auswertungen · davon betroffen" in zeile:
            # ⚠ Am WORT lesen, nicht an der Position: der erste Anlauf griff Feld 4
            # statt 5 und scheiterte am Wort „betroffen" selbst.
            teile = zeile.replace(",", "").split()
            zahlen.append((int(teile[0]), int(teile[teile.index("betroffen") + 1])))
    assert zahlen, r.stdout
    for gesamt, betroffen in zahlen:
        assert betroffen <= gesamt
        assert betroffen < gesamt, (
            "betroffen == gesamt: die Rechnung ist auf die Obergrenze zurueckgefallen")


def test_sie_rechnet_gegen_die_auswertungsliste_des_erzeugers():
    """⚠ Die Menge der ausgewerteten Doktypen steht in `analyze_docs.py`. Eine zweite,
    abweichende Liste in der Rechnung waere eine stille Falschaussage ueber Geld."""
    q = SONDE.read_text(encoding="utf-8")
    assert 'AUSWERTUNG = set(("fragenantworten",) + tuple(doctypes.PRIORITY))' in q
    az = (WURZEL / "scripts" / "analyze_docs.py").read_text(encoding="utf-8")
    assert 'AUSWERTUNG = ("fragenantworten",) + tuple(doctypes.PRIORITY)' in az, (
        "der Erzeuger waehlt seine Doktypen anders als die Rechnung")
