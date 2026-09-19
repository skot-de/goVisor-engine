"""Steht in der Volumenspalte ein Wert, den jemand veroeffentlicht hat?

⚠ GEMELDET AM 2026-09-19: „prüf mal bitte die volumenangabe, bei mir steht überall
259.360". Nachgemessen war das kein Anzeigefehler, sondern die Rechnung selbst.

`value_band_effektiv` bildet je CPV-Klasse einen Median und setzt ihn ueberall dort ein,
wo der Lead keinen eigenen Wert hat (`band_source='imputiert'`). `build_lead_export` gab
diesen Median als `value_eur` aus und bildete `imputiert` auf `'estimated'` ab — also auf
dasselbe Vokabular wie ein Schaetzwert, den die Vergabestelle SELBST veroeffentlicht hat.

Gemessen, was dabei herauskam:

    CPV 45000000 (generisch „Bauarbeiten")   2.632 offene Leads · 963 Kaeufer · alle 391.540 €
    der gemeldete Wert 259.360 €               345 Leads · 186 Kaeufer · 85 CPV-Codes

Vier Leads mit 391.540 € einzeln nachgeschlagen — Stadt Sindelfingen, Handwerkskammer
Niederbayern, Bundesamt fuer Bauwesen, Ennepe-Ruhr-Kreis: in Silber steht bei allen
`estimated_value = None`. Die Zahl kam nicht aus der Bekanntmachung.

⚠ UND DIE UNTERLAGEN HELFEN NICHT. Gegengeprueft ueber 3.001 ausgewertete Vorgaenge:
53,9 % nennen einen Begriff wie „Auftragswert" oder „Auftragssumme", aber nur 4,1 % haben
einen Betrag in der Naehe — und jeder davon ist eine REFERENZANFORDERUNG („Ausfuehrung von
Klinkerarbeiten mit einem Auftragswert von mindestens 400.000 Euro netto"). Das ist der
Wert, den das FRUEHERE Projekt des Bieters haben muss. Der geschaetzte Auftragswert ist
genau die Zahl, die eine Vergabestelle zurueckhaelt.

Entschieden von Sven: „ich will das da nur werte stehen, wenn wir sie ausgelesen haben,
nicht wenn wir sie geschätzt haben."
"""
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
GOLD = WURZEL / "govisor" / "gold.py"


def _block() -> str:
    """Der Wert-Abschnitt aus `build_lead_export`, ohne SQL-Kommentare.

    ⚠ Ohne das Entfernen prueft der Test die Begruendung darueber — sie nennt
    naturgemaess genau die Worte, auf die er anspringt (F13).
    """
    s = GOLD.read_text(encoding="utf-8")
    i = s.index("def build_lead_export")
    block = s[i:s.index("AS value_converted", i)]
    return re.sub(r"^\s*--.*$", "", block, flags=re.M)


def test_ein_imputierter_median_wird_nicht_als_wert_ausgegeben():
    b = _block()
    m = re.search(r"CASE WHEN d\.band_source([^A]*?)AS value_eur", b, re.S)
    assert m, "die Wertzuweisung in build_lead_export sieht anders aus"
    bed = m.group(1)
    assert "'echt'" in bed and "'geschaetzt'" in bed, (
        "die Bedingung zaehlt die erlaubten Herkuenfte nicht mehr auf")
    assert "imputiert" not in bed, (
        "ein imputierter CPV-Median wird wieder als Wert ausgegeben. Dann steht bei "
        "hunderten Leads verschiedener Kaeufer dieselbe Zahl, als haette sie jemand "
        "veroeffentlicht.")


def test_imputiert_ist_nicht_mehr_estimated():
    """⚠ Der zweite Teil, und ohne ihn waere der erste wirkungslos: solange `imputiert`
    auf `estimated` abgebildet wird, sagt das Vokabular „geschaetzt" ueber etwas, das
    gerechnet ist. Das Frontend kann den Unterschied dann nicht zeigen."""
    b = _block()
    m = re.search(r"CASE d\.band_source WHEN 'echt'(.*?)AS value_source", b, re.S)
    assert m, "die Herkunftszuweisung sieht anders aus"
    assert "'imputiert'" not in m.group(1), (
        "`imputiert` wird wieder auf ein Vokabular abgebildet, das Gemessenes meint")


def test_das_gebuehrenband_bleibt_unberuehrt():
    """⚠ `value_band` speist die Gebuehrenrechnung, nicht die Anzeige. Dort ist eine
    imputierte Groessenordnung ausdruecklich gewollt (docs/pricing-modell.md), und
    `band_source` steht daneben. Wer hier mit aufraeumt, nimmt der Abrechnung ihre
    Grundlage."""
    assert "d.band_effektiv" in _block(), (
        "das Wertband wird nicht mehr ausgegeben — die Gebuehrenrechnung haette dann "
        "keine Groessenordnung mehr")
