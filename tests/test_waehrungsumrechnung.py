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


# ── Die Kurse muessen frisch sein, nicht nur vorhanden ────────────────────────────────

def test_kursabruf_haengt_im_tageslauf_vor_dem_goldbau():
    """⚠ Die Fehlerklasse dieses Projekts: gebaut, nicht verdrahtet.

    Eine Kursdatei, die jemand einmal von Hand geholt hat, ist genau so lange richtig, wie
    sich die Welt nicht bewegt. Und die Reihenfolge ist kein Detail: `_wert_in_eur_sql()`
    liest die Datei beim Bauen der SQL-Ausdruecke — steht der Abruf hinter dem Gold-Bau,
    rechnet jeder Lauf mit den Kursen des Vortages.
    """
    lauf = (ROOT / "scripts" / "daily_leads.sh").read_text(encoding="utf-8")
    assert "fetch_ezb_kurse.py" in lauf, (
        "Der Kursabruf steht nicht im Tageslauf — die Umrechnung friert auf dem Stand der "
        "letzten Handholung ein.")
    assert lauf.index("fetch_ezb_kurse.py") < lauf.index("build_dach_gold.py"), (
        "Der Kursabruf steht NACH dem Gold-Bau. Dann gelten im Gold von heute die Kurse "
        "von gestern.")


def test_laufendes_jahr_wird_gemittelt_statt_geerbt():
    """Der Vorjahreskurs ist fuer das laufende Jahr eine schlechte Naeherung.

    Gemessen am 2026-09-15: HUF lag 7,1 % vom Jahresschnitt 2025 entfernt, NOK 5,0 %.
    Deshalb holt das Skript fuer das laufende Jahr die Monatsreihe und mittelt sie.
    """
    holer = (ROOT / "scripts" / "fetch_ezb_kurse.py").read_text(encoding="utf-8")
    assert "_hole_laufend" in holer and "M.{waehrung}.EUR" in holer, (
        "Kein laufender Jahresdurchschnitt aus der Monatsreihe — das laufende Jahr erbt "
        "still den Vorjahreskurs.")


@pytest.mark.skipif(not (ROOT / "data" / "reference" / "waehrungskurse.json").exists(),
                    reason="keine Kursdatei auf dieser Maschine")
def test_kurse_sind_nicht_veraltet():
    """Eine Kursdatei ohne Frist ist eine Behauptung ueber die Vergangenheit.

    30 Tage, dieselbe Frist wie beim Bibel-Nachlauf: darunter ein Anstoss zum Hinsehen,
    darueber ein Fehlschlag. Der Tageslauf holt taeglich; schlaegt das hier an, laeuft der
    Abruf seit einem Monat ins Leere, ohne dass etwas rot wurde.
    """
    import datetime as dt
    import json as _json
    roh = _json.loads((ROOT / "data" / "reference" / "waehrungskurse.json")
                      .read_text(encoding="utf-8"))
    geholt = dt.date.fromisoformat(roh["geholt_am"])
    alter = (dt.date.today() - geholt).days
    assert alter <= 30, (
        f"Die Kurse sind {alter} Tage alt (geholt {geholt}). Nachziehen mit: "
        "python3 scripts/fetch_ezb_kurse.py")
    # Und das laufende Jahr muss drinstehen, sonst faellt jede Vergabe von heute auf den
    # ELSE-Zweig und wird mit dem Vorjahreskurs gerechnet.
    jahr = str(dt.date.today().year)
    chf = roh["kurse"].get("CHF", {})
    assert jahr in chf, (
        f"Kein CHF-Kurs fuer {jahr} — Vergaben aus diesem Jahr erben den Vorjahreskurs.")


# ── Der Teilausfall, der wie ein Erfolg aussah ───────────────────────────────────────────────

@pytest.mark.skipif(not (ROOT / "data" / "reference" / "waehrungskurse.json").exists(),
                    reason="keine Kursdatei auf dieser Maschine")
def test_chf_wurde_frisch_geholt_und_nicht_uebernommen():
    """⚠ `geholt_am` gilt fuer die DATEI, nicht fuer jede Zahl darin.

    Am 2026-10-05 trug die Datei das Datum desselben Tages und hatte trotzdem keinen
    CHF-Kurs fuer 2026: der naechtliche Abruf bekam fuer `M.CHF` einen 504, das Skript
    uebersprang die Reihe und schrieb mit Exit 0 weiter. Zwoelf Waehrungen waren frisch,
    eine nicht, und nichts sagte es. `A.RON` fiel am selben Lauf ganz aus der Datei.

    Seitdem traegt die Datei zwei Buecher: `luecken` (was nicht geholt werden konnte) und
    `uebernommen` (was deshalb aus der vorigen Datei steht). Dieser Test prueft BEIDE fuer
    CHF — die einzige Fremdwaehrung mit nennenswertem Bestand (50.350 Bekanntmachungen
    gegen 216 fuer USD). Fuer ISK oder TRY waere derselbe Anspruch Laerm.

    ⚠ Schlaegt er an, sind die Zahlen trotzdem BENUTZBAR (die Uebernahme hat sie gerettet).
    Er sagt nur: der letzte Abruf kam fuer CHF nicht durch. Der naechste erfolgreiche Lauf
    macht ihn von selbst wieder gruen.
    """
    import json as _json
    roh = _json.loads((ROOT / "data" / "reference" / "waehrungskurse.json")
                      .read_text(encoding="utf-8"))
    assert "CHF" not in roh.get("luecken", {}), (
        f"CHF konnte nicht geholt werden: {roh.get('luecken', {}).get('CHF')}. "
        "Nachziehen mit: python3 scripts/fetch_ezb_kurse.py --waehrungen CHF")
    assert "CHF" not in roh.get("uebernommen", {}), (
        f"CHF-Jahre stammen aus einer frueheren Datei: "
        f"{roh.get('uebernommen', {}).get('CHF')}. Das Datum in `geholt_am` gilt fuer sie "
        "NICHT. Nachziehen mit: python3 scripts/fetch_ezb_kurse.py --waehrungen CHF")


def test_uebernahme_fuellt_luecken_und_meldet_nur_das_gefragte():
    """Die Uebernahme ist der eigentliche Schutz, also wird sie ohne Netz geprueft.

    Drei Eigenschaften, jede hat einen eigenen Grund:
    · fehlende Jahre werden gefuellt (sonst schrumpft die Datei bei jedem Ausfall),
    · frisch geholte Werte werden NICHT ueberschrieben (sonst friert ein alter Kurs fest),
    · nicht angefragte Waehrungen bleiben erhalten, aber ungemeldet (ein Lauf mit
      `--waehrungen CHF` soll die uebrigen zwoelf mitnehmen, ohne zwoelf Warnungen zu
      erzeugen, die niemanden angehen).
    """
    import importlib.util
    pfad = ROOT / "scripts" / "fetch_ezb_kurse.py"
    spec = importlib.util.spec_from_file_location("fetch_ezb_kurse", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)

    neu = {"CHF": {"2024": 0.95}}
    alt = {"CHF": {"2024": 9.99, "2025": 0.94}, "TRY": {"2025": 44.8}}
    uebernommen = modul._uebernimm(neu, alt, {"CHF"})

    assert neu["CHF"]["2025"] == 0.94, "fehlendes Jahr nicht uebernommen"
    assert neu["CHF"]["2024"] == 0.95, "frisch geholter Wert wurde ueberschrieben"
    assert neu["TRY"]["2025"] == 44.8, "nicht gefragte Waehrung ging verloren"
    assert uebernommen == {"CHF": ["2025"]}, (
        f"gemeldet werden soll nur das Gefragte, gemeldet wurde {uebernommen}")
