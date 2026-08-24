"""Staatsanzeiger — die Absage des Portals lesen, statt sie für einen Parser-Fehler zu halten.

Ohne Netz. „Kein ZIP-Link auf der Trefferliste" ist eine Aussage über UNSEREN Blick. Das
Portal sagt auf derselben Seite, woran es liegt.
"""
from __future__ import annotations

from pathlib import Path

from govisor import docfetch_queue as q
from govisor import docfetch_staatsanzeiger as sa

ABSAGE = ("Download Vergabeunterlagen ohne Registrierung\nEs sind Fehler aufgetreten.\n"
          "Die Vergabeunterlagen stehen nicht zum Download bereit. Bitte setzen Sie sich "
          "mit der Vergabestelle in Verbindung oder rufen Sie die Hotline an. (INFO 75630)")

TREFFER = ("<html><a href='https://www.staatsanzeiger-eservices.eu/"
           "L_204798_NC-0_TVZ-87569.zip'>ZIP</a></html>")


class Knopf:
    def click(self):
        pass


class Antwort:
    status = 200


class Seite:
    """Genug Playwright für den Zweig nach dem Klick auf den anonymen Weg."""

    def __init__(self, html="<html></html>", text=""):
        self._html, self._text = html, text
        self.frames = [object()]

    def on(self, ereignis, fn):
        pass

    def remove_listener(self, ereignis, fn):
        pass

    def goto(self, url, wait_until=None):
        return Antwort()

    def wait_for_timeout(self, ms):
        pass

    def query_selector(self, sel):
        return Knopf()

    def evaluate(self, js):
        return self._html if "outerHTML" in js else self._text


def test_absage_des_portals_ist_kein_fehlender_link():
    """⚠ Der Fehler, der 4 Vorgänge falsch beschriftete."""
    r = sa.hole_vergabe("u", Seite(text=ABSAGE), Path("/tmp/x.zip"), dry_run=True)
    assert r["status"] == "nicht_bereitgestellt"
    assert "75630" in r["note"]


def test_absage_ist_blockiert_durch_das_portal_nicht_durch_ein_konto():
    """Ein Konto hilft nicht — das Portal verweist an einen menschlichen Kanal."""
    assert q.BLOCKIERT.get("nicht_bereitgestellt") == "portal"
    assert "nicht_bereitgestellt" not in q.DAUERHAFT


def test_ohne_absage_bleibt_es_beim_ehrlichen_leer():
    r = sa.hole_vergabe("u", Seite(text="Irgendeine Trefferliste"), Path("/tmp/x.zip"),
                        dry_run=True)
    assert r["status"] == "leer"


def test_zip_link_wird_weiter_gefunden():
    """Regression: der gute Weg darf durch die neue Abfrage nicht verlorengehen."""
    r = sa.hole_vergabe("u", Seite(html=TREFFER, text="egal"), Path("/tmp/x.zip"),
                        dry_run=True)
    assert r["status"] != "leer"
    assert r["status"] != "nicht_bereitgestellt"


def test_frameset_bleibt_dauerhaft_aber_aus_dem_richtigen_grund():
    """Die Einstufung stimmt, ihre Begründung im Quelltext war überholt."""
    assert "frameset" in q.DAUERHAFT
    quelle = (Path(__file__).resolve().parent.parent / "govisor" / "docfetch_queue.py").read_text()
    assert "nur die Bekanntmachung" in quelle
