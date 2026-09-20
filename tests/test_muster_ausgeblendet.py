"""Findet die Musteranalyse echte Haeufungen — und schweigt sie bei Basisraten?

⚠ Sven am 2026-09-20: „idealerweise haben wir eine automatische analyse die nach mustern
schaut und bei vielen gleichen gründen dem nachgeht." Vorausgegangen war seine Kritik an
der Anzeige im Produkt: „ich weiss nicht ob die angaben in den lead details ein mehrwert
haben — was soll der nutzer damit? die sind fuer uns wichtig."

⛔ DIE FALLE IST DIE BASISRATE. Fuenf weggeklickte Vorgaenge derselben CPV-Klasse sind kein
Muster, wenn diese Klasse ohnehin 80 % der Liste stellt. Dieselbe Sorte Fehler steckte in
der Entity-Zusammenfuehrung (die Ausgangszahl war eine Doppelzaehlung) und im Volumenband
(CPV-Mediane sahen aus wie veroeffentlichte Werte). Genau dieser Fall wird hier zuerst
geprueft, und zwar als Gegenprobe: die Analyse muss SCHWEIGEN.
"""
from __future__ import annotations

import importlib
import re
import sys
from collections import Counter
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SKRIPT = WURZEL / "scripts" / "muster_ausgeblendet.py"


def _modul():
    sys.path.insert(0, str(WURZEL / "scripts"))
    m = importlib.import_module("muster_ausgeblendet")
    return importlib.reload(m)


def _zeilen(grund: str, n: int, nutzer: str = "u1"):
    return [{"user": nutzer, "lead_id": f"L{i}", "grund": grund} for i in range(n)]


def test_eine_echte_haeufung_wird_gefunden():
    """Sechs Ausblendungen wegen Entfernung, alle in derselben Region — und die Region ist
    im Bestand selten. Das ist ein Muster mit einer Konsequenz."""
    m = _modul()
    m.merkmale = lambda ids: {f"L{i}": {"nuts2": "DEA1", "cpv4": "4531",
                                        "band": "250-500k", "buyer": "X"} for i in range(6)}
    m.grundraum = lambda sp: Counter({"DEA1": 50, "DE21": 950})     # DEA1 = 5 % des Bestands
    b = m.suche(_zeilen("Entfernung", 6), mindestens=4, lift=3.0)
    assert len(b) == 1, f"erwartet genau einen Befund, bekam {b}"
    assert b[0]["merkmal"] == "nuts2" and b[0]["wert"] == "DEA1"
    assert b[0]["adressat"] == "profil", "Entfernung ist ein Befund ueber den NUTZER"
    assert b[0]["lift"] >= 3.0
    assert "regionen_aus" in b[0]["konsequenz"], "die Konsequenz fehlt"


def test_eine_basisrate_wird_nicht_als_muster_gemeldet():
    """⛔ DIE WICHTIGSTE PRUEFUNG DIESER DATEI. Dieselben sechs Ausblendungen, aber die
    Region stellt 90 % des Bestands: dann sagt die Haeufung nichts ueber die Region,
    sondern ueber die Groesse. Ohne diese Gegenprobe waere der Bericht eine Liste der
    haeufigsten Merkmale — und die kennt man auch ohne Ausblendungen.
    """
    m = _modul()
    m.merkmale = lambda ids: {f"L{i}": {"nuts2": "DE21", "cpv4": "4531",
                                        "band": "250-500k", "buyer": "X"} for i in range(6)}
    m.grundraum = lambda sp: Counter({"DE21": 900, "DEA1": 100})    # DE21 = 90 %
    assert m.suche(_zeilen("Entfernung", 6), mindestens=4, lift=3.0) == [], (
        "eine Region, die 90 % des Bestands stellt, wird als Muster gemeldet — das ist "
        "die Basisrate, nicht der Grund")


def test_produktfehler_und_profilvorschlag_bleiben_getrennt():
    """⚠ „Fehlerhafte Zuordnung" ist ein Befund ueber UNS, kein Nutzerwunsch. Daraus einen
    Ausschluss zu bauen waere genau verkehrt: es muss unsere Kategorisierung geprueft
    werden, nicht der Bestand des Nutzers beschnitten."""
    m = _modul()
    m.merkmale = lambda ids: {f"L{i}": {"cpv4": "4531", "nuts2": "DE21",
                                        "band": "250-500k", "buyer": "X"} for i in range(5)}
    m.grundraum = lambda sp: Counter({"4531": 30, "7200": 970})
    b = m.suche(_zeilen("Fehlerhafte Zuordnung", 5), mindestens=4, lift=3.0)
    assert len(b) == 1 and b[0]["adressat"] == "produkt", (
        "eine fehlerhafte Zuordnung wird als Profilvorschlag behandelt")
    assert "pruefen" in b[0]["konsequenz"], (
        "die Konsequenz ist kein Ausschluss, sondern eine Pruefung unserer Zuordnung")


def test_gruende_ohne_achse_bekommen_keinen_vorschlag():
    """⚠ „Kein Interesse", „Zu kurzfristig" und „Keine Chance" liegen auf keiner Achse, die
    das Profil kennt. Sie werden gezaehlt und gemeldet — aber ein Vorschlag, den niemand
    umsetzen kann, ist schlimmer als keiner."""
    m = _modul()
    for grund in ("Kein Interesse", "Zu kurzfristig", "Keine Chance"):
        b = m.suche(_zeilen(grund, 5), mindestens=4, lift=3.0)
        assert len(b) == 1, f"{grund} wird gar nicht gemeldet"
        assert b[0]["adressat"] == "offen" and b[0]["konsequenz"] is None, (
            f"{grund} bekommt einen Vorschlag, obwohl es keine Achse gibt")


def test_nutzer_werden_nicht_zusammengeworfen():
    """⚠ Ein Muster ist die Gewohnheit EINES Nutzers. Drei Leute, die je zweimal dieselbe
    Region wegklicken, ergeben kein Profilproblem — sie haben drei verschiedene Profile."""
    m = _modul()
    m.merkmale = lambda ids: {f"L{i}": {"nuts2": "DEA1", "cpv4": "4531",
                                        "band": "250-500k", "buyer": "X"} for i in range(6)}
    m.grundraum = lambda sp: Counter({"DEA1": 50, "DE21": 950})
    z = (_zeilen("Entfernung", 2, "u1") + _zeilen("Entfernung", 2, "u2")
         + _zeilen("Entfernung", 2, "u3"))
    assert m.suche(z, mindestens=4, lift=3.0) == [], (
        "drei Nutzer mit je zwei Klicks ergeben ein Muster — jeder hat ein eigenes Profil")


def test_auch_ein_grund_ohne_achse_braucht_die_schwelle():
    """⚠ GEFUNDEN DURCH EINE GEGENPROBE, DIE NICHT ANKAM. Fuer Gruende MIT Achse gibt es
    zwei Schwellen (einmal ueber die Gruppe, einmal ueber den Merkmalswert); faellt die
    erste weg, faengt die zweite es auf. Fuer „Kein Interesse", „Zu kurzfristig" und
    „Keine Chance" gibt es nur die erste — ohne sie wuerde ein EINZELNER Klick als Befund
    gemeldet, und der Bericht saehe aus, als haette er etwas gefunden.
    """
    m = _modul()
    assert m.suche(_zeilen("Kein Interesse", 1), mindestens=4, lift=3.0) == [], (
        "ein einzelner Klick auf einen Grund ohne Achse wird als Muster gemeldet")
    assert len(m.suche(_zeilen("Kein Interesse", 4), mindestens=4, lift=3.0)) == 1, (
        "ab der Schwelle muss er gemeldet werden")


def test_die_schwellen_sind_einstellbar_und_wirken():
    m = _modul()
    m.merkmale = lambda ids: {f"L{i}": {"nuts2": "DEA1", "cpv4": "4531",
                                        "band": "250-500k", "buyer": "X"} for i in range(6)}
    m.grundraum = lambda sp: Counter({"DEA1": 50, "DE21": 950})
    assert m.suche(_zeilen("Entfernung", 6), mindestens=10, lift=3.0) == [], "n-Schwelle wirkt nicht"
    assert m.suche(_zeilen("Entfernung", 6), mindestens=4, lift=99.0) == [], "Lift-Schwelle wirkt nicht"


def test_je_grund_genau_eine_achse():
    """⚠ Wer alle Merkmale gegen alle Gruende prueft, bekommt bei vier Merkmalen und sechs
    Gruenden 24 Zahlen, von denen immer ein paar heraussstechen — Rauschen mit
    Nachkommastellen."""
    code = SKRIPT.read_text(encoding="utf-8")
    m = re.search(r"_ACHSE = \{([\s\S]*?)\n\}", code)
    assert m, "_ACHSE gibt es nicht mehr"
    achsen = re.findall(r'"([^"]+)":\s*\((None|"[^"]+"),', m.group(1))
    assert len(achsen) == 6, f"{len(achsen)} Gruende in der Achsentabelle, erwartet 6"
    mit = [a for a in achsen if a[1] != "None"]
    assert len(mit) == 3, (
        f"{len(mit)} Gruende haben eine Achse. Erwartet drei — die anderen drei liegen auf "
        f"keiner Groesse, die das Profil kennt.")


def test_die_anzeige_im_produkt_ist_weg():
    """⛔ Sven: „was soll der nutzer damit?" — die nutzeruebergreifende Zahl ist aus der
    Akte geflogen. Sie lenkt in die Irre: wer einen Vorgang wegen ENTFERNUNG wegklickt,
    sagt etwas ueber seinen Standort, nicht ueber den Vorgang.

    ⚠ Die EIGENE Angabe bleibt, und zwar nicht als Statistik: die Akte ist der einzige Weg,
    auf dem man einem ausgeblendeten Vorgang wiederbegegnet. Ohne sie stuende er da, als
    waere nie etwas gewesen.
    """
    akte = (WURZEL / "web" / "components" / "explorer" / "Vorgangsakte.tsx").read_text(encoding="utf-8")
    assert "antwort.ausblendungen" not in akte, "die fremde Zahl steht wieder in der Akte"
    assert "meineAusblendungen" in akte, "die eigene Angabe ist mit verschwunden"
    route = (WURZEL / "web" / "app" / "api" / "vorgang" / "route.ts").read_text(encoding="utf-8")
    assert "ausblendungen.json" not in route, "die Route laedt das Aggregat noch"


def test_die_analyse_laeuft_jede_nacht():
    """⚠ Ein Bericht, den man erst einschaltet, wenn man ihn braucht, existiert an dem Tag
    noch nicht. `gold_integrity` hing monatelang an einem Netzlauf, den niemand startete."""
    sh = (WURZEL / "scripts" / "daily_leads.sh").read_text(encoding="utf-8")
    assert "muster_ausgeblendet.py" in sh, "die Musteranalyse laeuft in keiner Nacht"
    i = sh.index("$PY scripts/muster_ausgeblendet.py")
    fenster = sh[i:i + 140]
    assert "--mindestens" in fenster and "--lift" in fenster, (
        "ohne beide Schwellen meldet der Bericht Basisraten als Muster")
