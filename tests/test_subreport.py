"""subreport ELViS — die vier Ausgänge auseinanderhalten.

Ohne Netz. Der Fehler, den diese Wachen festhalten: 124 Vorgänge standen als „0 Dateien"
im Manifest — ein Satz, der wie „hat keine Unterlagen" klingt und in Wahrheit vier
verschiedene Dinge bedeutete, jedes mit einer anderen Konsequenz.
"""
from __future__ import annotations

from govisor import docfetch_queue as q
from govisor import subreport as sr

KOPF = "Call for tenders\nELVISID\nE12345678\n\nContract notice\nName\nAction\nNationale Bekanntmachung\tdownload\n"
UNTEN = "\n\nGeneral Terms and Conditions of Business | Privacy Policy | Legal notice\nback\nLogin\n"


class Seite:
    """Playwright-Ersatz. `nach_klick` ist der Text, den der Ausklapper erzeugt."""

    def __init__(self, text, nach_klick=None, klick_scheitert=False):
        self._text, self._nach = text, nach_klick
        self._klick_scheitert = klick_scheitert
        self.geklickt = False

    def goto(self, url, wait_until=None):
        return None

    def wait_for_timeout(self, ms):
        pass

    def click(self, sel):
        if self._klick_scheitert:
            raise RuntimeError("kein solcher Knopf")
        self.geklickt = True

    def evaluate(self, js):
        return self._nach if (self.geklickt and self._nach) else self._text


def _abschnitt(zeilen, davor=KOPF, danach=UNTEN):
    return davor + "Access to the tender documents\nName\tValid until\tStatus\tAction\n" + zeilen + danach


# ── Die vier Ausgänge ─────────────────────────────────────────────────────────────────────

def test_anmeldung_noetig_ist_blockiert_nicht_leer():
    """Die Unterlagen LIEGEN dort. „leer" würde das Gegenteil behaupten."""
    t = _abschnitt("Gewässeraufweitung\t11.09.2026 08:30\t\tDownload\n",
                   danach="\nAlready registered and authorized subreport ELViS users can "
                          "download the documents.\n")
    r = sr.hole_liste("https://www.subreport.de/E1", Seite(t))
    assert r["status"] == "gated"
    assert q.BLOCKIERT.get(r["status"]) == "konto"


def test_abgelaufen_ist_dauerhaft():
    t = _abschnitt("Garten- und Landschaftsbauarbeiten\t15.06.2026 09:30\tValidity expired\t\n")
    r = sr.hole_liste("https://www.subreport.de/E2", Seite(t))
    assert r["status"] == "abgelaufen"
    assert r["status"] in q.DAUERHAFT


def test_aufgehoben_ist_dauerhaft():
    t = _abschnitt("Tief- und Rohrleitungsbau\t16.06.2026 09:00\tcanceled\t\n")
    r = sr.hole_liste("https://www.subreport.de/E3", Seite(t))
    assert r["status"] == "aufgehoben"
    assert r["status"] in q.DAUERHAFT


def test_passwort_ist_eigene_klasse_und_nicht_konto():
    """Ein Konto hilft hier nicht — das Passwort geht an eingeladene Bieter."""
    t = _abschnitt("Futterroboter\t18.09.2026 10:45\t\tdisplay\n")
    nach = t + "\nEnter password\nPlease enter the password for the restricted tender.\n"
    r = sr.hole_liste("https://www.subreport.de/E4", Seite(t, nach_klick=nach))
    assert r["status"] == "passwortgeschuetzt"
    assert q.BLOCKIERT.get(r["status"]) == "passwort"


def test_liste_wird_gelesen():
    t = _abschnitt("Lieferung gemäß Lastenheft\t30.09.2026 10:00\t\tdisplay\n")
    nach = t + "\n124 Eigenerklärung zur Eignung.pdf\nLV Blitzschutz.pdf\n"
    r = sr.hole_liste("https://www.subreport.de/E5", Seite(t, nach_klick=nach))
    assert r["status"] == "nur_liste"
    assert r["gefunden"] == 2


# ── Die Reihenfolge, an der es hängt ──────────────────────────────────────────────────────

def test_ausklapper_gewinnt_gegen_ein_wort_von_nebenan():
    """⚠ Der Kern der Sortierung.

    Steht „canceled" irgendwo in der Nachbarschaft, während die Zeile selbst ausklappbar
    ist, darf die Vergabe NICHT abgestempelt werden. Dieser Fehler erzeugt keinen
    Fehlschlag, sondern eine falsche Gewissheit — und die sieht niemand.
    """
    t = _abschnitt("Los 1 Rohbau\t30.09.2026 10:00\t\tdisplay\n"
                   "Los 2 Ausbau\t30.09.2026 10:00\tcanceled\t\n")
    nach = t + "\nLeistungsverzeichnis.pdf\n"
    r = sr.hole_liste("https://www.subreport.de/E6", Seite(t, nach_klick=nach))
    assert r["status"] == "nur_liste"


def test_abschnitt_reicht_nicht_bis_in_die_fusszeile():
    """Ohne Grenze wäre der Abschnitt „alles ab der Überschrift"."""
    lang = "x" * (sr._ABSCHNITT_MAX + 200) + "canceled"
    t = _abschnitt("Rohbau\t30.09.2026 10:00\t\tDownload\n" + lang,
                   danach="\nAlready registered and authorized users can download.\n")
    r = sr.hole_liste("https://www.subreport.de/E7", Seite(t))
    assert r["status"] == "gated"


def test_ohne_abschnitt_ist_es_ein_fehler_keine_aussage():
    r = sr.hole_liste("https://www.subreport.de/E8", Seite(KOPF + UNTEN))
    assert r["status"] == "fehler"
    assert r["status"] not in q.KEIN_FEHLSCHLAG


def test_bekanntmachungszeile_macht_noch_keine_unterlagen():
    """Über dem Abschnitt steht ein eigener `download`-Knopf für die Bekanntmachung."""
    assert "download" in KOPF
    t = _abschnitt("Rohbau\t30.09.2026 10:00\tValidity expired\t\n")
    assert sr.hole_liste("https://www.subreport.de/E9", Seite(t))["status"] == "abgelaufen"


# ── URL-Formen ────────────────────────────────────────────────────────────────────────────

def test_zweite_url_form_wird_abgeleitet():
    """312 Leads zeigen direkt auf die Bekanntmachungs-PDF — die Kennung steht in der URL."""
    z = sr.vergabeseite("https://www.subreport-elvis.de/download/bund/E63477415/x/bekanntmachung.pdf")
    assert z == "https://www.subreport.de/E63477415"
