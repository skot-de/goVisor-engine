"""Sprecher-Zuordnung: jede Pruefung steht fuer einen Fehler, der tatsaechlich passiert ist.

Die Zahlen in den Beschreibungen sind am 2026-09-01 an 4.349 Anforderungen aus
Fragenkatalogen gemessen, nicht geschaetzt.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor import sprecher as sp                       # noqa: E402
from govisor.docextract import _normalize                # noqa: E402


def _urteil(roh: str, zitat: str) -> str:
    norm, karte = sp.indexkarte(roh)
    return sp.zuordnen(roh, norm, karte, _normalize(zitat), zitat)


def test_antwortmarke_weist_der_vergabestelle_zu():
    """Die verlaessliche Richtung: steht `Antwort:` davor, spricht die Vergabestelle."""
    roh = ("Frage 5: Duerfen mehrere Hauptangebote abgegeben werden?\n"
           "Antwort: Nein, es ist genau ein Hauptangebot zugelassen.")
    assert _urteil(roh, "es ist genau ein Hauptangebot zugelassen") == sp.VERGABESTELLE


def test_fragemarke_allein_genuegt_nicht():
    """DER FEHLER, DER AUFGEFALLEN IST.

    In vielen Katalogen folgt die Antwort direkt auf die Frage, ohne eigene Marke. Eine
    erste Fassung ordnete solche Saetze dem Bieter zu, weil die letzte Marke davor eine
    Frage war — und buchte damit 376 Saetze falsch, darunter das unverkennbar amtliche
    „Beide Positionen sind mit der neuen Version (3) aus dem LV gestrichen".
    """
    roh = ("Frage 3: Koennen die Positionen 12 und 13 entfallen?\n"
           "Beide Positionen sind mit der neuen Version (3) aus dem LV gestrichen.")
    assert _urteil(roh, "Beide Positionen sind mit der neuen Version") == sp.UNKLAR, (
        "Eine unmarkierte Antwort unter einer Frage darf nicht dem Bieter zugerechnet werden")


def test_fragehaftes_zitat_nach_fragemarke_ist_der_bieter():
    """Beides zusammen traegt: Fragemarke davor UND das Zitat klingt selbst nach Bieter."""
    roh = ("Frage 7: Gehen wir richtig in der Annahme, dass der Auftragnehmer nur "
           "Personal fuer Voll- und Teilzeit stellt?\nAntwort: Ja.")
    assert _urteil(roh, "Gehen wir richtig in der Annahme, dass der Auftragnehmer") == sp.BIETER


def test_tabellen_liefern_keine_zuordnung():
    """1.574 der 2.065 Fragenkataloge sind Tabellen: `Nr | Bieterfrage | Antwort | Datum`.

    Die Textextraktion plaettet sie, damit verschwindet die Reihenfolge. Wer hier
    trotzdem zuordnet, wuerfelt.
    """
    roh = ("Nr Bieterfrage Antwort Eingangsdatum\n"
           "1 Ist ISO 27001 zwingend? Nein, ein gleichwertiger Nachweis genuegt.")
    assert _urteil(roh, "ein gleichwertiger Nachweis genuegt") == sp.UNKLAR


def test_teilwoerter_sind_keine_marken():
    """Die Teilwort-Falle, die in diesem Projekt schon dreimal zugeschlagen hat.

    Ohne die Doppelpunkt-Bedingung griff die Marke mitten in „ZukunftJugendFRAGENstudie"
    und „NachFRAGE bzgl." und ordnete 982 Anforderungen einem Bieter zu.
    """
    for text in ("Thema Zukunft Jugend Fragenstudie zu Umweltfragen und Klima",
                 "Ich habe folgende Nachfrage bzgl des vorgesehenen Verfahrens",
                 "Bieterfragen Vergabenummer 2026-4012-00055 Seite 1"):
        assert not sp.FRAGE.search(text), f"{text!r} ist keine Fragemarke"


def test_indexkarte_verschiebt_sich_nicht_am_scharfen_s():
    """`ß`.casefold() ist `ss` — zwei Zeichen. Ohne die Laengenpruefung verschieben sich
    ab dort alle Positionen um eins und die Karte zeigt auf die falsche Stelle."""
    roh = "Straße: Antwort: Der Preis ist verbindlich vereinbart."
    norm, karte = sp.indexkarte(roh)
    assert len(norm) == len(karte)
    p = norm.find(_normalize("Der Preis ist verbindlich"))
    assert p >= 0 and roh[karte[p]:karte[p] + 3] == "Der"


def test_kurze_zitate_werden_nicht_zugeordnet():
    """Ein kurzes Zitat findet sich zufaellig irgendwo — dann entscheidet die Marke davor
    ueber eine Zuschreibung, die auf einem Zufallstreffer steht."""
    roh = "Antwort: Ja."
    assert _urteil(roh, "Ja") == sp.UNKLAR
