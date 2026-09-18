"""Schliesst die Dubletten-Firewall Leads aus, ohne ihre Hauptbedingung geprueft zu haben?

⚠ WARUM DIESE DATEI EXISTIERT. Die Firewall beruht auf drei gemessenen Regeln, und die
erste ist die ±90-Tage-Bedingung: „aus der Abstandsverteilung (Median 2 T, 96 % binnen
90). 180 Tage bringen einen Punkt mehr und fangen dafuer gleichnamige
Wiederholungsvergaben ein."

`_in_zeitscheiben` laesst Saetze OHNE Datum bewusst in jeder Zeitscheibe mitlaufen — sie
„koennen mit allem paaren". Als Kandidatenregel ist das richtig. Als BELEG ist es etwas
anderes: so ein Paar hat die Hauptbedingung nicht bestanden, sondern uebersprungen.

Gemessen am 2026-09-17 ueber 115.044 DE-Paare:

    mit Datum     96.713   ausnahmslos <= 90 Tage (Median 27, Maximum exakt 90)
    ohne Datum    18.331   15,9 %, nie geprueft
      davon `kaeufer_und_titel`: 361 — und genau die schliessen Leads aus

Beispiel aus dem Bestand: „Neubau Optical Imaging Center- OIC." (2017) wurde mit „E94.1
OIC - Neubau Optical Imaging Center/VE 4.11 Montageschienen" gepaart. Dasselbe Bauprojekt,
sechs Jahre und eine andere Vergabeeinheit auseinander — von 68 Vorgaengen dieses Projekts
sind rund 60 eigenstaendige Gewerke.
"""
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
DEDUPE = WURZEL / "govisor" / "dedupe.py"
GOLD = WURZEL / "govisor" / "gold.py"


def _quelle(p: Path) -> str:
    """Datei ohne `#`-Kommentare — Pruefungen sollen Verhalten messen, nicht Prosa.

    ⚠ DREIFACH-ANFUEHRUNGSZEICHEN BLEIBEN STEHEN. Die erste Fassung entfernte sie als
    „Docstrings" — in `gold.py` steckt aber das ganze SQL in `f\"\"\"…\"\"\"`-Bloecken.
    Die Pruefung loeschte damit genau das, was sie messen sollte, und meldete den
    Beleg-Filter als verschwunden. Vierter Fall an einem Tag, in dem ein Waechter am
    eigenen Ausschnitt scheitert.
    """
    return re.sub(r"(?m)^\s*#.*$", "", p.read_text(encoding="utf-8"))


def test_datumslose_paare_bekommen_eine_eigene_stufe():
    """Ohne Datum darf ein Paar nicht als `kaeufer_und_titel` gelten.

    ⚠ Der Unterschied ist NICHT kosmetisch: `gold.py` schliesst Leads mit
    `WHERE d.beleg = 'kaeufer_und_titel'` aus. Faellt die Unterscheidung weg, schliessen
    361 ungepruefte Paare wieder aus.
    """
    code = _quelle(DEDUPE)
    assert "kaeufer_und_titel_ohne_datum" in code, (
        "datumslose Paare tragen wieder dieselbe Belegstufe wie gepruefte — sie "
        "schliessen dann Leads aus, ohne je auf den 90-Tage-Abstand geprueft worden zu sein")
    # Die Stufe muss an der DATUMSLAGE haengen, nicht an etwas anderem.
    # ⚠ Eindeutiger Anker noetig: `ohne_datum` heisst auch eine Liste in
    # `_in_zeitscheiben`, und die steht im Text FRUEHER. Die erste Fassung
    # dieses Tests griff jene Zeile und meldete die Regel als verschwunden.
    i = code.index("ohne_datum = not (")
    zeile = code[i:code.index("\n", i)]
    assert 's["d"]' in zeile and 't["d"]' in zeile, (
        "die neue Stufe wird nicht aus dem Datum abgeleitet")


def test_identische_titel_bleiben_belastbar():
    """⚠ Ohne Datum trennt die WORTMENGE, und nur die Enthaltung ist das Problem.

    Gemessen am 2026-09-17 ueber 366 datumslose `kaeufer_und_titel`-Paare:

        Wortmengen identisch   111   „SPA Loessnig, Sanierung Rundlaufbahn" doppelt
        eine enthaelt die andere 255  „Erweiterung Stadtbad Plauen - Los VM 004 -
                                       Abbrucharbeiten" gegen „Erweiterung Stadtbad Plauen"

    Identische Titel bei identischem Kaeufer sind auch ohne Datum ein Beleg — der Abstand
    haette daran nichts mehr zu entscheiden. Eine Enthaltung dagegen ist genau der Fall,
    den die 90 Tage abfangen sollen: dieselbe Baustelle, anderes Los, Jahre spaeter.

    Faellt diese Unterscheidung weg, kehren 111 echte Dubletten in die Liste zurueck —
    die Aenderung waere dann ein Tausch statt einer Verbesserung.
    """
    code = _quelle(DEDUPE)
    # ⚠ Eindeutiger Anker noetig: `ohne_datum` heisst auch eine Liste in
    # `_in_zeitscheiben`, und die steht im Text FRUEHER. Die erste Fassung
    # dieses Tests griff jene Zeile und meldete die Regel als verschwunden.
    i = code.index("ohne_datum = not (")
    zeile = code[i:code.index("\n", i)]
    # ⚠ NACH DER AENDERUNG BLEIBEN 118 DATUMSLOSE PAARE in `kaeufer_und_titel`, und das
    # ist KEIN Restfehler: es sind genau die mit identischem Titel. Wer die Zahl spaeter
    # sieht und „aufraeumt", macht die Verfeinerung rueckgaengig.
    assert 's["w"] != t["w"]' in zeile, (
        "die Stufe trifft wieder ALLE datumslosen Paare, auch die mit identischem Titel — "
        "111 echte Dubletten kaemen damit zurueck in die Liste")


def test_der_ausschluss_nimmt_nur_geprueft_belegte_paare():
    """`gold.py` darf nur die Stufe ausschliessen, die alle drei Regeln bestanden hat.

    ⚠ `kaeufer_und_titel_ohne_datum` beginnt mit `kaeufer_und_titel`. Ein `LIKE` oder
    `starts_with` an dieser Stelle wuerde die neue Stufe stillschweigend wieder
    einschliessen — die Unterscheidung waere dann da, aber wirkungslos.
    """
    code = _quelle(GOLD)
    i = code.index("notice_duplicates.parquet")
    block = code[i:i + 3000]
    assert "'kaeufer_und_titel'" in block, (
        "der Ausschluss filtert nicht mehr auf die belastbare Belegstufe")
    # ⚠ Die ungepruefte Stufe darf NICHT dabei sein.
    assert "'kaeufer_und_titel_ohne_datum'" not in block, (
        "der Ausschluss nimmt wieder Paare, die nie auf den 90-Tage-Abstand geprueft wurden")
    for lasch in ("beleg LIKE 'kaeufer_und_titel", "starts_with(d.beleg", "d.beleg ILIKE"):
        assert lasch not in block, (
            f"`{lasch}` faengt auch `kaeufer_und_titel_ohne_datum` — die ungeprueften "
            "Paare schliessen wieder aus")


def test_die_anreicherung_bleibt_auf_der_belastbaren_stufe():
    """Die Anreicherung uebernimmt Felder (Fristen!) aus der Dublette in den Master.

    Sie war schon vorher auf `kaeufer_und_titel` begrenzt, und das muss so bleiben: eine
    fremde FRIST zu uebernehmen ist schlimmer als eine Dublette stehen zu lassen.
    """
    code = _quelle(DEDUPE)
    ab = code.index("def anreichern")
    block = code[ab:]
    assert block.count("beleg = 'kaeufer_und_titel'") >= 3, (
        "die Anreicherung filtert nicht mehr auf die belastbare Stufe")
