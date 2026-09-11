"""Die Abdeckungs-Sonde — und warum drei vorhandene Wächter das Loch nicht sahen.

Am 2026-09-07 hatte Luxemburg für Juli NULL Bekanntmachungen und für August 16 statt ~250.
Drei Wächter liefen jede Nacht und schwiegen; drei bereits geholte Vergabeunterlagen fanden
deshalb keine Ausschreibung.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SKRIPT = WURZEL / "scripts" / "pruefe_abdeckung.py"
QUELLE = SKRIPT.read_text(encoding="utf-8")
LAUF = (WURZEL / "scripts" / "daily_leads.sh").read_text(encoding="utf-8")


def _modul():
    spec = importlib.util.spec_from_file_location("_pa", SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _modul()


def test_vergleicht_nur_die_ted_herkunft():
    """⚠ Silber trägt in drei von vier Ländern weitere Quellen, die TED nicht kennt. Gegen
    die Gesamtzahl gemessen meldete die Sonde im ersten Anlauf 116 bis 388 % „Abdeckung"
    und hätte eine fehlende TED-Lieferung dort NIE sehen können — genau den Fall, für den
    sie gebaut ist."""
    assert M.TED_HERKUNFT == ("legacy", "eforms")
    kern = QUELLE.split("def _silber(")[1].split("\ndef ")[0]
    assert "schema_gen in" in kern


def test_der_laufende_monat_zaehlt_als_GANZES_nicht():
    """Er füllt sich noch; ein Rückstand im Monatsschnitt ist der Normalzustand.

    ⚠ Seit dem 2026-09-11 gilt das nur noch für den Monat, NICHT für seine abgeschlossenen
    Tage — siehe die zweite Stufe unten. Der Satz hier war richtig und hat trotzdem zwei
    Nächte lang ein Loch von 676 Bekanntmachungen zugedeckt."""
    kern = QUELLE.split("def main(")[1]
    assert "m = (m - dt.timedelta(days=1)).replace(day=1)" in kern
    assert "laufender_monat(" in kern, "Die zweite Stufe wird nicht aufgerufen."


def test_schwelle_laesst_den_normalbereich_durch():
    """⚠ Die TED-Facette zählt mehr, als uns gehört (EU-Einrichtungen unter jeder
    Länderfacette). Gemessen liegt der Normalbereich bei 91 bis 103 %. Eine Schwelle bei
    95 % erzeugte einen Wächter, der jede Nacht schreit — und abgeschaltet wird."""
    assert 'default=0.8' in QUELLE


def test_alle_aktiven_laender_haben_einen_ted_code():
    """Ein Land ohne Code würde stillschweigend übersprungen — dann prüft die Sonde es nie."""
    from govisor.laender import AKTIV
    fehlt = [l for l in AKTIV if l not in M.ALPHA3]
    assert not fehlt, f"kein TED-Code hinterlegt: {fehlt}"


def test_sonde_laeuft_im_tageslauf():
    """Sonst ist sie gebaut und nicht verdrahtet — die Fehlerklasse, wegen der es sie gibt."""
    assert "scripts/pruefe_abdeckung.py" in LAUF


def test_projektpfad_vor_dem_govisor_import():
    """Der Tageslauf läuft unter launchd ohne PYTHONPATH; ein Import davor bricht stumm ab."""
    i_pfad = QUELLE.index("sys.path.insert(0, str(ROOT))")
    i_imp = QUELLE.index("from govisor.laender import AKTIV")
    assert i_pfad < i_imp


# ─────────────────────── Zweite Stufe: der laufende Monat, tageweise
#
# ⚠ Die Sonde prüfte bis zum 2026-09-11 nur abgeschlossene Monate. Am 2026-09-09
# holte der Live-Abruf für Deutschland 0 von 676 Bekanntmachungen, weil der Rechner
# mitten im Lauf schlief — und sie meldete zwei Nächte lang „alle geprueften Monate
# vollstaendig", weil sie auf August schaute. Der Wächter war nicht kaputt; er schaute
# an der Stelle vorbei, an der es brannte.

def test_eine_null_von_ted_gilt_als_nicht_beantwortet(monkeypatch):
    """⚠ GEMESSEN AM 2026-09-11: dieselbe Tagesabfrage (DEU) lieferte im ersten Anlauf
    **0** und eine Minute später dreimal hintereinander **540**. Wer die Null glaubt,
    meldet „ein ganzer Tag fehlt", sobald die Gegenstelle schluckt — und nach der dritten
    Fehlmeldung schaut niemand mehr hin."""
    from govisor import verify

    antworten = [0, 0, 540]

    class Antwort:
        status_code = 200

        def __init__(self, n):
            self._n = n

        def json(self):
            return {"totalNoticeCount": self._n}

    rufe = []

    def post(*a, **kw):
        rufe.append(1)
        return Antwort(antworten[len(rufe) - 1])

    monkeypatch.setattr(verify.requests, "post", post)
    monkeypatch.setattr(verify.time, "sleep", lambda s: None)
    assert verify._api_total("egal") == 540
    assert len(rufe) == 3, "Die Null wurde geglaubt statt wiederholt."


def test_kleine_laender_werden_nicht_tageweise_beurteilt(monkeypatch, capsys):
    """⚠ Im ersten Anlauf lief die Tagesaufloesung fuer jedes Land, und die Schweiz meldete
    am 2026-09-07 „29 von 103 (28 %)" — bei einer Fenstersumme von **100 %**. Da fehlte
    nichts, die Bekanntmachungen lagen an einem anderen Tag. Zuordnung ist kein Verlust."""
    m = _modul()
    tage = []
    monkeypatch.setattr(m, "_silber_zeitraum", lambda land, von, bis: 364)

    def ted(von, bis, cc, attempts=3):
        if von == bis:
            tage.append(von)
            return 103
        return 363

    monkeypatch.setattr(m, "api_count_zeitraum", ted)
    befunde = m.laufender_monat("CH", "CHE", tage=9, karenz=2, schwelle=0.8, boden=100)
    assert befunde == [], befunde
    assert tage == [], "Fuer ein kleines Land wurden Einzeltage abgefragt."
    assert "zu klein fuer Tagesaufloesung" in capsys.readouterr().out


def test_ein_ausgefallener_tag_wird_gemeldet(monkeypatch, capsys):
    """Der Fall vom 2026-09-09: ein Tag ganz ohne Abruf, in einem sonst gesunden Fenster.
    ⚠ Die Fenstersumme allein haette ihn NICHT gefunden — sie lag bei 81 % und damit ueber
    der Schwelle. Erst der Tag zeigt ihn."""
    m = _modul()
    heute = dt.date.today()
    loch = heute - dt.timedelta(days=2)

    monkeypatch.setattr(m, "api_count_zeitraum",
                        lambda von, bis, cc, attempts=3: 676 if von == bis else 4438)
    monkeypatch.setattr(m, "_silber_zeitraum",
                        lambda land, von, bis: 0 if von == bis == loch else
                        (3574 if von != bis else 600))
    befunde = m.laufender_monat("DE", "DEU", tage=9, karenz=2, schwelle=0.8, boden=100)
    assert any(f"{loch}" in b and "0 von 676" in b for b in befunde), befunde


def test_das_fenster_greift_nie_in_den_vormonat(monkeypatch):
    """Der Vormonat ist abgeschlossen und wird von der ersten Stufe geprueft — ihn hier
    noch einmal anzufassen, meldete denselben Befund zweimal."""
    m = _modul()
    gesehen = {}

    def ted(von, bis, cc, attempts=3):
        gesehen.setdefault("von", von)
        return 1000

    monkeypatch.setattr(m, "api_count_zeitraum", ted)
    monkeypatch.setattr(m, "_silber_zeitraum", lambda land, von, bis: 1000)
    m.laufender_monat("DE", "DEU", tage=60, karenz=2, schwelle=0.8, boden=100000)
    heute = dt.date.today()
    assert gesehen["von"] >= dt.date(heute.year, heute.month, 1), gesehen
