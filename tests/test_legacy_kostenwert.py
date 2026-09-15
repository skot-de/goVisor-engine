"""Der Vor-2014-Endwert: formatierter Text und Waehrung am Eltern-Knoten.

⚠ **Zwei Fehler in einer Zeile, und der zweite hat den ersten versteckt.**

`_first_amount(costs, ("VALUE_COST",), ("CURRENCY",))` las den Betrag mit `_to_amount`
— das wirft das Dezimalkomma weg und liefert bei zwei Nachkommastellen das
**Hundertfache** — und suchte die Waehrung am Wertknoten, wo sie nicht steht. Sie haengt
am Eltern-Knoten `COSTS_RANGE_AND_CURRENCY_WITH_VAT_RATE`.

Ohne Waehrung fielen diese Saetze bis zum 2026-09-15 aus `final_value_clean` heraus (die
Pruefung verlangte EUR), und niemand rechnete je nach. Als die Waehrungsumrechnung sie
hereinholte, stand ein Schweizer Tunnellos mit **19 Mrd CHF** statt 190 Mio da.

Gemessen am 2026-09-15 ueber alle vier Laender: auf diesem Pfad trugen **100 %** der
Bekanntmachungen `value_currency IS NULL` — CH 1.422, AT 6.398, LU 1.558, DE 46.933 —
und rund 57 % davon zusaetzlich den Faktor 100.

Gegengeprueft an drei echten Bronze-Dateien (2785_2017, 371305_2012, 249447_2011): alle
drei liefern nach der Reparatur Betrag und Waehrung wie im XML.
"""
from __future__ import annotations

from govisor import schema

# Nachbau des echten Falls 346910_2016 (Gubristtunnel, 3. Roehre): Text mit
# Schmalleerzeichen als Tausender und Komma als Dezimaltrenner, `@FMTVAL` daneben,
# `@CURRENCY` am Eltern-Knoten.
_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<TED_EXPORT>
  <CODED_DATA_SECTION>
    <NOTICE_DATA>
      <ISO_COUNTRY VALUE="CH"/>
      <ORIGINAL_CPV CODE="45221000"/>
    </NOTICE_DATA>
    <CODIF_DATA><DIRECTIVE VALUE="2004/18/EC"/></CODIF_DATA>
  </CODED_DATA_SECTION>
  <FORM_SECTION>
    <CONTRACT_AWARD>
      <FD_CONTRACT_AWARD>
        <OBJECT_CONTRACT_INFORMATION_CONTRACT_AWARD_NOTICE>
          <DESCRIPTION_AWARD_NOTICE_INFORMATION>
            <TITLE_CONTRACT><P>ANU Los 201, Bau 3. Roehre Gubristtunnel.</P></TITLE_CONTRACT>
          </DESCRIPTION_AWARD_NOTICE_INFORMATION>
        </OBJECT_CONTRACT_INFORMATION_CONTRACT_AWARD_NOTICE>
        <AWARD_OF_CONTRACT>
          <CONTRACT_VALUE_INFORMATION>
            <COSTS_RANGE_AND_CURRENCY_WITH_VAT_RATE CURRENCY="CHF">
              <VALUE_COST FMTVAL="189945844.15">189 945 844,15</VALUE_COST>
            </COSTS_RANGE_AND_CURRENCY_WITH_VAT_RATE>
          </CONTRACT_VALUE_INFORMATION>
        </AWARD_OF_CONTRACT>
      </FD_CONTRACT_AWARD>
    </CONTRACT_AWARD>
  </FORM_SECTION>
</TED_EXPORT>"""

# Derselbe Satz ohne `@FMTVAL` — aeltere Jahrgaenge fuehren das Attribut nicht immer.
_XML_OHNE_FMTVAL = _XML.replace(b' FMTVAL="189945844.15"', b"")


def test_betrag_behaelt_seine_nachkommastellen():
    n = schema.parse(_XML, "346910_2016")
    assert n.final_value == 189_945_844.15, (
        f"final_value ist {n.final_value:,.2f} — bei 18.994.584.415 wurde das Dezimalkomma "
        "weggeworfen (`_to_amount` statt `_kosten_betrag`).")


def test_waehrung_kommt_vom_eltern_knoten():
    n = schema.parse(_XML, "346910_2016")
    assert n.value_currency == "CHF", (
        f"value_currency ist {n.value_currency!r}. Die Waehrung haengt an "
        "COSTS_RANGE_AND_CURRENCY_WITH_VAT_RATE, nicht am VALUE_COST — wer sie am "
        "Wertknoten sucht, findet nie eine, und der Wert faellt aus jeder Kennzahl.")


def test_ohne_fmtval_greift_die_europaeische_lesart():
    """`@FMTVAL` ist der sichere Weg, aber nicht der einzige."""
    n = schema.parse(_XML_OHNE_FMTVAL, "346910_2016")
    assert n.final_value == 189_945_844.15, (
        f"Ohne FMTVAL kommt {n.final_value:,.2f} heraus — der Textknoten muss europaeisch "
        "gelesen werden (Leerzeichen/Punkt = Tausender, Komma = Dezimal).")
    assert n.value_currency == "CHF"


def test_fmtval_wird_nicht_europaeisch_gelesen():
    """⚠ Die zwei Lesarten sind gegenlaeufig, und eine Verwechslung ist teuer.

    Im Text ist der Punkt ein TAUSENDER-Trenner (`1.234.567,89`), in `@FMTVAL` ist er der
    DEZIMAL-Trenner (`189945844.15`). Wer `@FMTVAL` durch die europaeische Lesart schickt,
    macht aus 189.945.844,15 die Zahl 18.994.584.415 — denselben Faktor 100, nur aus der
    anderen Richtung.
    """
    import xml.etree.ElementTree as ET
    elem = ET.fromstring('<VALUE_COST FMTVAL="1234567.89">1 234 567,89</VALUE_COST>')
    assert schema._kosten_betrag(elem) == 1_234_567.89


# ── Der Schaetzwert derselben Aera ────────────────────────────────────────────────────

_XML_SCHAETZ = _XML.replace(
    b"<CONTRACT_VALUE_INFORMATION>",
    b"""<CONTRACT_VALUE_INFORMATION>
            <INITIAL_ESTIMATED_TOTAL_VALUE_CONTRACT CURRENCY="CHF">
              <VALUE_COST>200 000 000,00</VALUE_COST>
              <INCLUDING_VAT><VAT_PRCT>8,0</VAT_PRCT></INCLUDING_VAT>
            </INITIAL_ESTIMATED_TOTAL_VALUE_CONTRACT>""")


def test_vor_2014_schaetzwert_wird_gelesen():
    """⚠ `VAL_ESTIMATED_TOTAL` gibt es erst ab den 2014er-Formularen.

    Davor heisst der Knoten `INITIAL_ESTIMATED_TOTAL_VALUE_CONTRACT`. Der OJS-Zweig las
    ihn seit Langem, der Legacy-Zweig nicht — gemessen am 2026-09-15 blieben dadurch
    26.383 Schaetzwerte leer, die im XML danebenstanden (DE 23.663, AT 2.072, LU 648).
    Ein fehlender Schaetzwert heisst im Produkt „Wert unbekannt", und das ist die
    teuerste Antwort, die ein Lead geben kann.
    """
    n = schema.parse(_XML_SCHAETZ, "346910_2016")
    assert n.estimated_value == 200_000_000.00, (
        f"estimated_value ist {n.estimated_value!r} — der Vor-2014-Knoten wird nicht "
        "gelesen.")
    assert n.final_value == 189_945_844.15, "der Endwert darf davon unberuehrt bleiben"
    assert n.value_currency == "CHF"


def test_neuer_knoten_hat_vorrang_vor_dem_alten():
    """Fuehrt eine Bekanntmachung beides, gilt der 2014er-Knoten."""
    xml = _XML_SCHAETZ.replace(
        b"<CONTRACT_VALUE_INFORMATION>",
        b'<CONTRACT_VALUE_INFORMATION><VAL_ESTIMATED_TOTAL CURRENCY="CHF">777.0'
        b"</VAL_ESTIMATED_TOTAL>", 1)
    n = schema.parse(xml, "346910_2016")
    assert n.estimated_value == 777.0, (
        f"estimated_value ist {n.estimated_value!r} — der alte Knoten hat den neuen "
        "ueberschrieben.")
