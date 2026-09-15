"""Fremdwaehrungen werden umgerechnet, nicht weggeworfen.

Bis zum 2026-09-15 stand in `gold.build_notice_quality` die Bedingung
``AND (value_currency = 'EUR' OR value_currency IS NULL)``. Sie war als Schutz gedacht
— keine Fremdwaehrung soll still als Euro gelten — wirkte aber als Filter: die Schweiz
verlor 50.339 CHF-Werte und behielt 619 EUR-Werte, also **1 %**. Kapitel 13 der
Laender-Bibel nennt das die teuerste Auslassung des CH-Onboardings.

Die Tests hier sichern die drei Eigenschaften, an denen die Reparatur haengt:
Richtung des Kurses, Kennzeichnung der Herkunft, und dass die alte Sperre nicht
zurueckkommt.
"""
from __future__ import annotations

import pathlib
import re

import duckdb
import pytest

from govisor import gold

ROOT = pathlib.Path(__file__).resolve().parent.parent
QUELLE = (ROOT / "govisor" / "gold.py").read_text(encoding="utf-8")


def test_kurse_vorhanden_und_plausibel():
    kurse = gold._kurse()
    assert "CHF" in kurse, (
        "Ohne CHF-Kurse faellt die Umrechnung stumm auf die alte Sperre zurueck. "
        "Nachziehen mit: python3 scripts/fetch_ezb_kurse.py")
    chf = kurse["CHF"]
    assert len(chf) >= 20, f"nur {len(chf)} CHF-Jahre — die Reihe beginnt 2004"
    # Der Franken stand nie weiter als Faktor 2 vom Euro weg; alles darueber waere ein
    # vertauschtes Verhaeltnis oder eine falsche Reihe.
    assert all(0.5 < k < 2.0 for k in chf.values()), f"unplausible CHF-Kurse: {chf}"


def test_richtung_der_umrechnung():
    """⚠ Die EZB nennt Einheiten je EUR. 2015 kostete ein Euro 1,0679 CHF.

    100.000 CHF sind damit rund 93.600 EUR — WENIGER, nicht mehr. Eine Multiplikation
    statt Division faellt beim Franken kaum auf (der Kurs liegt nahe 1) und wuerde die
    Marktgroesse still aufblasen. Deshalb wird hier gegen eine Waehrung geprueft, bei
    der die Richtung nicht zu uebersehen ist.
    """
    sql = gold._wert_in_eur_sql("betrag", "waehrung", "jahr")
    con = duckdb.connect()
    fall = con.execute(
        f"SELECT {sql} FROM (SELECT 100000.0 AS betrag, 'CHF' AS waehrung, 2015 AS jahr)"
    ).fetchone()[0]
    con.close()
    assert 90_000 < fall < 97_000, (
        f"100.000 CHF (2015) ergeben {fall:,.0f} EUR — erwartet ~93.600. "
        "Bei ~106.800 ist mal statt geteilt gerechnet.")


def test_euro_bleibt_unangetastet():
    sql = gold._wert_in_eur_sql("betrag", "waehrung", "jahr")
    con = duckdb.connect()
    eur, leer = con.execute(f"""
        SELECT ({sql}) FROM (SELECT 50000.0 betrag, 'EUR' waehrung, 2020 jahr)""").fetchone()[0], \
        con.execute(f"""
        SELECT ({sql}) FROM (SELECT 50000.0 betrag, NULL waehrung, 2020 jahr)""").fetchone()[0]
    con.close()
    assert eur == 50_000, f"EUR wurde veraendert: {eur}"
    assert leer == 50_000, f"Waehrung NULL gilt als EUR (TED-Konvention), war: {leer}"


def test_unbekannte_waehrung_faellt_aus_statt_zu_gelten():
    """AED fuehrt die EZB nicht. Ein Betrag ohne Kurs darf NICHT als Euro durchgehen."""
    sql = gold._wert_in_eur_sql("betrag", "waehrung", "jahr")
    con = duckdb.connect()
    fall = con.execute(
        f"SELECT {sql} FROM (SELECT 100000.0 betrag, 'AED' waehrung, 2020 jahr)").fetchone()[0]
    con.close()
    assert fall is None, f"AED wurde zu {fall} — ohne Kurs gibt es keinen Euro-Betrag"


def test_laufendes_jahr_faellt_auf_juengsten_kurs():
    """Fuer das laufende Jahr gibt es noch keinen Jahresdurchschnitt."""
    sql = gold._wert_in_eur_sql("betrag", "waehrung", "jahr")
    con = duckdb.connect()
    fall = con.execute(
        f"SELECT {sql} FROM (SELECT 100000.0 betrag, 'CHF' waehrung, 2099 jahr)").fetchone()[0]
    con.close()
    assert fall is not None, "ein Wert aus einem Jahr ohne Kurs darf nicht verschwinden"
    assert 90_000 < fall < 130_000, f"Ersatzkurs unplausibel: {fall}"


def test_alte_sperre_kommt_nicht_zurueck():
    """Die Bedingung, die die Schweiz 99 % ihrer Werte kostete."""
    for muster in (r"final_value\s*>=\s*100[^)]*value_currency\s*=\s*'EUR'",
                   r"CASE WHEN lo\.value_currency\s*=\s*'EUR' THEN lo\.value_amount"):
        assert not re.search(muster, QUELLE), (
            f"Die alte Waehrungssperre steht wieder in gold.py: {muster}")


def test_herkunft_wird_gekennzeichnet():
    """Ein umgerechneter Wert ist kein gemessener — Kapitel 13 verlangt die Markierung."""
    assert "'waehrung_umgerechnet'" in QUELLE, (
        "Ohne das Qualitaetsmerkmal sieht ein Schweizer Auftrag aus wie ein in Euro "
        "ausgeschriebener.")
    assert "'waehrung_fremd'" in QUELLE, (
        "`waehrung_umgerechnet` ERSETZT `waehrung_fremd` nicht — das eine sagt 'nicht in "
        "Euro', das andere 'von uns umgerechnet'.")
    assert "AS wert_umgerechnet" in QUELLE, (
        "Die Kennzeichnung muss bis in die Leads durchreichen, sonst kann die Oberflaeche "
        "sie nicht zeigen.")


@pytest.mark.skipif(not (ROOT / "data" / "silver" / "CH" / "notices").exists(),
                    reason="kein CH-Silber auf dieser Maschine")
def test_ch_werte_kommen_tatsaechlich_an():
    """Gegenprobe an echten Daten statt an der Formel."""
    sql = gold._wert_in_eur_sql()
    con = duckdb.connect()
    alt, neu = con.execute(f"""
        SELECT count(*) FILTER (WHERE final_value >= 100 AND final_value <= 1e9
                                  AND (value_currency='EUR' OR value_currency IS NULL)),
               count(*) FILTER (WHERE ({sql}) >= 100 AND ({sql}) <= 1e9)
        FROM read_parquet('{ROOT}/data/silver/CH/notices/**/*.parquet')""").fetchone()
    con.close()
    assert neu > alt * 10, (
        f"CH-Werte alt {alt:,} → neu {neu:,} — die Umrechnung greift nicht (erwartet ~25x)")
