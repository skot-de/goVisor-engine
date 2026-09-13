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


def test_es_wird_nicht_tageweise_gegen_ted_verglichen():
    """⚠ DIE REGEL, DIE ICH ZWEI TAGE LANG DRIN HATTE, WAR FALSCH GEBAUT.

    Sie verglich unser `publication_date` mit der TED-Facette `publication-date` — und das
    sind **nicht dieselben Felder**. Nachgewiesen Stück für Stück am 2026-09-13: von acht
    Bekanntmachungen, die TED unter dem 2026-09-11 führt, liegen ALLE ACHT bei uns, zwei
    unter dem 09.09. und sechs unter dem 10.09. Es fehlte nichts. Die Sonde meldete
    trotzdem „DE 2026-09-11: 0 von 569 (0 %)".

    Der Versatz geht in beide Richtungen (04.09.: wir 598, TED 540 — 08.09.: wir 647,
    TED 577), lässt sich also nicht wegrechnen. Über genug Tage mittelt er sich heraus,
    über einen nicht.

    ⚠ Der eine echte Fund (09.09., 0 von 676) war Glück, nicht Konstruktion: die Datei war
    an dem Tag wirklich leer. Eine Regel, die einmal zufällig richtig liegt und danach
    jede Nacht schreit, ist schlechter als keine — sie entwertet alle übrigen Meldungen mit.
    """
    kern = QUELLE.split("def laufender_monat(")[1].split("\ndef ")[0]
    assert "api_count_zeitraum(tag, tag" not in kern, \
        "Die Tagesregel ist zurück — sie vergleicht zwei verschiedene Datumsfelder."
    assert "while tag <= bis" not in kern, "Es wird wieder tageweise geschleift."
    assert "nicht dieselben Felder" in QUELLE, \
        "Die Begruendung fehlt — dann baut sie der Naechste wieder ein."


def test_die_karenz_deckt_den_datumsversatz():
    """Vier Tage sind gemessen, nicht geschätzt. Am 2026-09-13 über alle vier Länder:

        Karenz 2:  DE 85 % · AT  86 % · CH  89 % · LU  75 %   ← LU faellt durch
        Karenz 3:  DE 94 % · AT  95 % · CH 100 % · LU  85 %
        Karenz 4:  DE 98 % · AT 103 % · CH 100 % · LU 102 %

    Wer sie kleiner stellt, misst den Versatz statt der Abdeckung — und bekommt jede Nacht
    eine Meldung, hinter der nichts steckt.
    """
    assert 'ap.add_argument("--karenz", type=int, default=4' in QUELLE
    assert "Karenz 4 Tage:" in QUELLE, "die Messung hinter der Zahl steht nirgends"


def test_ein_leeres_fenster_wird_gemeldet(monkeypatch, capsys):
    """Was die Fenstersumme weiterhin findet: ein Land, das systematisch zurückfaellt."""
    m = _modul()
    monkeypatch.setattr(m, "api_count_zeitraum", lambda von, bis, cc, attempts=3: 5000)
    monkeypatch.setattr(m, "_silber_zeitraum", lambda land, von, bis: 1000)
    befunde = m.laufender_monat("DE", "DEU", tage=9, karenz=4, schwelle=0.8)
    assert len(befunde) == 1 and "20 %" in befunde[0], befunde


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
    m.laufender_monat("DE", "DEU", tage=60, karenz=4, schwelle=0.8)
    heute = dt.date.today()
    assert gesehen["von"] >= dt.date(heute.year, heute.month, 1), gesehen
