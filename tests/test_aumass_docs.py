"""aumass — eine abgelaufene Frist ist kein Fehlschlag.

Ohne Netz. Nach Fristende ersetzt aumass die ganze Seite durch einen Satz. Die Vergabe fiel
damit durch beide Prüfungen (kein Unterlagen-Abschnitt, keine Bekanntmachungsart) und
landete als `fehler` — obwohl nichts fehlgeschlagen war.
"""
from __future__ import annotations

from pathlib import Path

from govisor import docfetch_aumass as au
from govisor import docfetch_queue as q

URL = "https://plattform.aumass.de/Veroeffentlichung/av26c7ee-eu"

ABGELAUFEN = ("PLATTFORM FÜR AUSSCHREIBUNGEN UND EVERGABE\nDIE ANGEBOTSFRIST FÜR DIE "
              "AUSSCHREIBUNG AV26C7EE-EU: 1H0007, NEUBAU FEUERWEHR AHRWEILER - LOS 070 "
              "GEBÄUDEAUTOMATION IST ABGELAUFEN.\nGlossar\nKontakt")


class Antwort:
    status = 200


class Seite:
    def __init__(self, text):
        self._text = text

    def goto(self, url, wait_until=None):
        return Antwort()

    def wait_for_timeout(self, ms):
        pass

    def evaluate(self, js):
        return self._text

    def query_selector(self, sel):
        return None

    def query_selector_all(self, sel):
        return []


def test_abgelaufene_frist_ist_kein_fehler():
    r = au.hole_vergabe(URL, Seite(ABGELAUFEN), Path("/tmp/x.zip"), dry_run=True)
    assert r["status"] == "abgelaufen"
    assert r["status"] in q.DAUERHAFT


def test_ex_ante_bleibt_ohne_unterlagen():
    """Regression: die ältere Unterscheidung darf nicht verlorengehen."""
    r = au.hole_vergabe(URL, Seite("EX ANTE BEKANNTMACHUNG\nirgendwas"),
                        Path("/tmp/x.zip"), dry_run=True)
    assert r["status"] == "ohne_unterlagen"


def test_wirklich_unbekannte_seite_bleibt_ein_fehler():
    """⚠ Der Rest darf nicht mit weggeräumt werden — er ist die Arbeitsliste."""
    r = au.hole_vergabe(URL, Seite("Irgendeine Seite ohne Merkmal"),
                        Path("/tmp/x.zip"), dry_run=True)
    assert r["status"] == "fehler"
    assert r["note"] == "kein Unterlagen-Abschnitt"


def test_abgelaufen_braucht_beide_woerter():
    """„abgelaufen" allein könnte in jedem Fliesstext stehen."""
    r = au.hole_vergabe(URL, Seite("Die Gewährleistung ist abgelaufen, Angebote erbeten"),
                        Path("/tmp/x.zip"), dry_run=True)
    assert r["status"] == "fehler"
