"""Healy-Hudson-Unterlagen — die Fehlerseite lesen, statt über die Vergabe zu urteilen.

Ohne Netz. 14 Vorgänge standen als „keine Dateien auf der Vorgangsseite" im Manifest — eine
Aussage über die VERGABE, obwohl die Seite eine über die ANFRAGE machte.
"""
from __future__ import annotations

from pathlib import Path

from govisor import docfetch_healyhudson as hh
from govisor import docfetch_queue as q

FEHLER = "https://bieterzugang.deutsche-evergabe.de/evergabe.bieter/ErrorMessage.aspx?ErrorMessageKey="
VORGANG = "https://fbhh-evergabe.web.hamburg.de/evergabe.bieter/eva/supplierportal/x/subproject/1"

# Echte Vorgangsseiten tragen Tausende Zeichen. Ein Fake mit drei Woertern loest die Wache
# gegen leer geladene Seiten aus — und pruefte dann etwas anderes als gemeint.
def _seitentext(kern: str) -> str:
    rahmen = ("Öffentliche Verfahren Bieterassistent Einladungscode Nicht angemeldet Home "
              "Details Projektinformationen Auftraggeber Auftraggebertyp Öffentlicher "
              "Auftraggeber Verfahren Projektnummer Titel Vergabeordnung Leistungsart "
              "Vergabeart Vertragsart Ausführungsort Fristen und Termine Bekanntmachung "
              "Einreichungsfrist Bindefrist Verfahrensbeschreibung ")
    return kern + "\n" + rahmen * 2


class Antwort:
    def __init__(self, status=200):
        self.status = status


class Seite:
    def __init__(self, url, text="", dateien=(), knopf=None, status=200):
        self.url, self._text = url, text
        self._dateien, self._knopf, self._status = list(dateien), knopf, status

    def goto(self, url, wait_until=None):
        return Antwort(self._status)

    def wait_for_timeout(self, ms):
        pass

    def evaluate(self, js):
        # Zwei Abfragen, zwei Antworten: Rumpftext und Dateiliste.
        if "querySelectorAll" in js:
            return [{"name": n, "ref": "/d/" + n} for n in self._dateien]
        return self._text

    def query_selector(self, sel):
        return self._knopf


def test_noch_nicht_veroeffentlicht_wartet_auf_die_welt():
    r = hh.hole_vergabe("x", Seite(FEHLER + "Project.NotBeenPublished"), Path("/tmp"), dry_run=True)
    assert r["status"] == "nicht_veroeffentlicht"
    # Weder unser Fehler noch ein fehlender Zugang — und schon gar nicht „nie wieder".
    assert r["status"] in q.WARTET
    assert r["status"] not in q.DAUERHAFT
    assert r["status"] not in q.BLOCKIERT


def test_nicht_mehr_verfuegbar_ist_dauerhaft():
    r = hh.hole_vergabe("x", Seite(FEHLER + "SubProject.NotAvailable"), Path("/tmp"), dry_run=True)
    assert r["status"] == "weg"
    assert r["status"] in q.DAUERHAFT


def test_unbekannter_fehlerschluessel_wird_benannt_nicht_geraten():
    r = hh.hole_vergabe("x", Seite(FEHLER + "Etwas.Neues"), Path("/tmp"), dry_run=True)
    assert r["status"] == "fehler"
    assert "Etwas.Neues" in r["note"]


def test_fehlerseite_wird_nicht_als_leere_vergabe_gemeldet():
    """⚠ Der Fehler, der 14 Vorgänge falsch beschriftete."""
    for schluessel in ("Project.NotBeenPublished", "SubProject.NotAvailable"):
        r = hh.hole_vergabe("x", Seite(FEHLER + schluessel), Path("/tmp"), dry_run=True)
        assert r["status"] != "leer", schluessel


def test_echte_vorgangsseite_ohne_dateien_bleibt_leer():
    r = hh.hole_vergabe("x", Seite(VORGANG, text=_seitentext("Projektinformationen")), Path("/tmp"), dry_run=True)
    assert r["status"] == "leer"


def test_dashboard_bleibt_unterscheidbar_von_leer():
    s = Seite("https://portal.deutsche-evergabe.de/dashboards/dashboard_off/abc", text=_seitentext("Anzahl: 7"))
    r = hh.hole_vergabe("x", s, Path("/tmp"), dry_run=True)
    assert r["status"] == "kein_downloadbereich"
    # Zugangsfrage, kein Urteil über die Vergabe — s. test_docfetch_queue.
    assert q.BLOCKIERT.get(r["status"]) == "konto"


def test_leer_geladene_seite_ist_kein_befund():
    """⚠ Ein leerer Rumpf ist NIE eine Aussage über eine Vergabe.

    Ohne diese Wache landet ein misslungener Ladevorgang als `leer` im Manifest — also als
    Befund über das Portal, obwohl nichts gesehen wurde. Genau so stand am 2026-08-24 eine
    Seite mit 0 Zeichen als „kein Unterlagen-Link" beim Ausschreibungsblatt.
    """
    r = hh.hole_vergabe("x", Seite(VORGANG, text=""), Path("/tmp"), dry_run=True)
    assert r["status"] == "fehler"
    assert "leer geladen" in r["note"]
    # Und er darf nicht als erledigt gelten, sonst wird er nie wiederholt.
    assert r["status"] not in q.KEIN_FEHLSCHLAG
