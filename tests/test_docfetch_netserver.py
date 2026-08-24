"""NetServer-Abrufer — Wachen gegen die Fehler, die 261 Vorgänge auf Halde legten.

Ohne Netz. Geprüft wird die Logik, an der es scheiterte: welchen Rahmen der Abrufer liest,
welche Oberfläche er erkennt und wann „keine Datei" wirklich „keine Datei" heißt.
"""
from __future__ import annotations

from pathlib import Path

from govisor import docfetch_netserver as ns
from govisor import docfetch_queue as q

OID = "54321-Tender-19f6ecb40ae-38c0bb40d285174e"

# Die Brotkrume von had.de. Sie steht auf JEDER Seite des Portals, im Menü.
MENUE = "Ausschreibungen suchen | Aktuelle Ausschreibungen aus Hessen | eHAD-Vergabeunterlagen"


class Rahmen:
    def __init__(self, url, text="", knoepfe=(), sammel=None, parent=None, dateien=()):
        self.url, self._text = url, text
        self._knoepfe, self._sammel, self.parent_frame = list(knoepfe), sammel, parent
        self._dateien = dateien

    def query_selector_all(self, sel):
        return self._knoepfe if sel == ns._KNOPF else []

    def query_selector(self, sel):
        return self._sammel if sel == ns._SAMMEL else None

    def evaluate(self, js):
        # Der Abrufer fragt zweierlei ab: den Rumpftext und die Dateiliste. Ein Fake, der
        # auf beides dasselbe antwortet, laesst den Trockenlauf Buchstaben zaehlen.
        if "querySelectorAll" in js:
            return list(self._dateien)
        return self._text


class Seite:
    def __init__(self, rahmen):
        self.frames = rahmen
        self.main_frame = rahmen[0]

    def goto(self, url, wait_until=None):
        return None

    def wait_for_timeout(self, ms):
        pass


def _frameset(inhalt_text="", knoepfe=(), sammel=None, dateien=()):
    """had.de-Bauform: Menü im Hauptrahmen, Vorgang im Kindrahmen auf ANDEREM Host."""
    menue = Rahmen("https://www.had.de/NetServer/TenderingProcedureDetails?TenderOID=" + OID,
                   text=MENUE)
    inhalt = Rahmen("https://vergabe.had.de/NetServer/TenderingProcedureDetails?TenderOID=" + OID,
                    text=inhalt_text, knoepfe=knoepfe, sammel=sammel, parent=menue,
                    dateien=dateien)
    return Seite([menue, inhalt])


# ── Servlet-Tausch: die dokumentierten 404-Fallen ─────────────────────────────────────────

def test_servlet_wird_getauscht_nicht_nur_der_parameter():
    u = "https://x.de/NetServer/PublicationControllerServlet?function=Detail&TWOID=abc"
    z = ns.unterlagen_url(u)
    assert "TenderingProcedureDetails" in z and "PublicationControllerServlet" not in z


def test_servlet_tausch_auch_ohne_netserver_pfad():
    """xvergabe.de hängt an der Wurzel — der erste Fix erfasste nur `/NetServer/`."""
    z = ns.unterlagen_url("https://xvergabe.de/PublicationControllerServlet?function=Detail&TWOID=abc")
    assert z.endswith("thContext=publications")
    assert "/TenderingProcedureDetails?" in z


# ── Rahmen-Wahl ───────────────────────────────────────────────────────────────────────────

def test_rahmen_mit_knopf_gewinnt():
    s = _frameset(knoepfe=["knopf"])
    assert ns.inhalts_rahmen(s, OID) is s.frames[1]


def test_ohne_knopf_gewinnt_der_kindrahmen_mit_demselben_vorgang():
    """Der Menürahmen trägt denselben Vorgang nicht — er trägt gar keinen."""
    s = _frameset(inhalt_text="Der Sichtbarkeitszeitraum dieser Vergabe ist abgelaufen")
    assert ns.inhalts_rahmen(s, OID) is s.frames[1]


def test_einzelseite_bleibt_beim_hauptrahmen():
    s = Seite([Rahmen("https://vergabe.bremen.de/x?TenderOID=" + OID, text="Vergabeunterlagen")])
    assert ns.inhalts_rahmen(s, OID) is s.main_frame


# ── Die eigentliche Regression ────────────────────────────────────────────────────────────

def test_menue_gilt_nicht_als_unterlagen_abschnitt():
    """⚠ Der Fehler, der 188 Vorgänge kostete.

    Der Hauptrahmen sagt „…eHAD-Vergabeunterlagen", der Inhalt sagt nichts dergleichen.
    Wer die ganze Seite liest, meldet „leer" — also „die Vergabe hat wirklich keine Datei".
    Richtig ist „falsche Seite", denn nachgesehen wurde im Menü.
    """
    r = ns.hole_vergabe("https://www.had.de/x?TenderOID=" + OID,
                        _frameset(inhalt_text="Irgendein Vorgang ohne das Wort"),
                        Path("/dev/null"), dry_run=True)
    assert r["status"] != "leer"
    assert r["status"] == "fehler"


def test_leer_nur_wenn_der_inhalt_selbst_den_abschnitt_traegt():
    r = ns.hole_vergabe("https://www.had.de/x?TenderOID=" + OID,
                        _frameset(inhalt_text="Vergabeunterlagen\nkeine Version"),
                        Path("/dev/null"), dry_run=True)
    assert r["status"] == "leer"


# ── Sichtbarkeitsfenster ──────────────────────────────────────────────────────────────────

def test_abgelaufen_wird_erkannt_und_gilt_als_dauerhaft():
    r = ns.hole_vergabe("https://www.had.de/x?TenderOID=" + OID,
                        _frameset(inhalt_text="Der Sichtbarkeitszeitraum dieser Vergabe ist abgelaufen"),
                        Path("/dev/null"), dry_run=True)
    assert r["status"] == "abgelaufen"
    # Sonst liefe der Vorgang alle sieben Tage erneut gegen dieselbe Wand.
    assert r["status"] in q.DAUERHAFT


# ── Zweite Oberfläche ─────────────────────────────────────────────────────────────────────

class Sammelknopf:
    def click(self):
        pass


def test_neue_oberflaeche_gilt_nicht_als_leer():
    """xvergabe.de listet die Dateien sichtbar — nur unter anderen Klassen."""
    s = _frameset(inhalt_text="Vergabeunterlagen", sammel=Sammelknopf(),
                  dateien=["Leistungsverzeichnis.pdf", "Angebotsschreiben.pdf"])
    r = ns.hole_vergabe("https://xvergabe.de/x?TenderOID=" + OID, s,
                        Path("/dev/null"), dry_run=True)
    assert r["status"] == "probe"
    assert r["n_files"] == 2
    assert "Leistungsverzeichnis.pdf" in r["note"]
