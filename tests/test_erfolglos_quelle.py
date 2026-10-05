"""`verfahren_status='erfolglos'`: die Quelle schlaegt die Ableitung.

WARUM ES DIESE DATEI GIBT. Bis zum 2026-10-05 wurde „erfolglos" ausschliesslich
ERSCHLOSSEN: Zuschlagsbekanntmachung ohne `awards`-Zeile. Mit der eForms-Umstellung
fiel das Signal von 13,0 % (2019) auf 0,9 % (2024) — nicht kaputt, sondern blind:
eForms schreibt fuer JEDES Los ein `LotResult`, auch fuer eines ohne Gewinner, also ist
`has_award` immer wahr. 11.201 von 12.169 echten Fehlvergaben standen als `unbekannt`.

Das trifft `retender_signal` und die Schwaeche-Achse von `market_opportunity`. Der
Ausfall war in KEINER Gesamtzahl sichtbar, weil die alten Jahre die Summen tragen —
nur in der Jahresreihe. Diese Suite prueft deshalb die Jahresreihe, nicht die Summe.

⚠ Und sie prueft beide Richtungen. Eine Regel, die nur „Quelle sagt leer" beachtet,
laesst den umgekehrten Fall stehen: die Quelle meldet vergebene Lose, der Parser hat
keine `awards`-Zeile gebildet, und die Ableitung erklaert das Verfahren fuer gescheitert.
Zwei solche Faelle lagen im Bestand.
"""
import pathlib

import pytest

pytest.importorskip("duckdb")
import duckdb  # noqa: E402

WURZEL = pathlib.Path(__file__).resolve().parents[1]
QUELLE = (WURZEL / "govisor" / "gold.py").read_text(encoding="utf-8")


def _q(land="DE"):
    p = WURZEL / "data" / "gold" / land / "quality.parquet"
    return p.as_posix() if p.exists() else None


def _n(land="DE"):
    return (WURZEL / "data" / "silver" / land / "notices" / "**" / "*.parquet").as_posix()


# ---- Verdrahtung, ohne Daten pruefbar ---------------------------------------

def test_die_quelle_steht_vor_der_ableitung():
    """Die Reihenfolge der CASE-Zweige IST die Regel.

    Stuende `NOT has_award` vor `quelle_sagt_leer`, griffe die Ableitung zuerst und die
    ausdrueckliche Angabe waere wirkungslos — ohne dass irgendetwas scheitert.
    """
    block = QUELLE.split("AS final_value_clean", 1)[1].split("AS verfahren_status", 1)[0]
    i_quelle = block.find("quelle_sagt_leer THEN 'erfolglos'")
    i_ableitung = block.find("NOT has_award")
    assert i_quelle > 0, "der Zweig `quelle_sagt_leer` fehlt"
    assert i_ableitung > 0, "der Rueckfall `NOT has_award` fehlt"
    assert i_quelle < i_ableitung, (
        "`NOT has_award` steht VOR `quelle_sagt_leer`. Damit entscheidet die Ableitung "
        "zuerst und die ausdrueckliche Angabe der Quelle laeuft ins Leere.")


def test_die_ableitung_ueberstimmt_die_quelle_nicht():
    """Der Rueckfall muss zurueckstehen, wenn die Quelle vergebene Lose meldet."""
    block = QUELLE.split("AS final_value_clean", 1)[1].split("AS verfahren_status", 1)[0]
    i = block.find("NOT has_award")
    rest = block[i:i + 220]
    assert "quelle_sagt_leer IS DISTINCT FROM FALSE" in rest, (
        "Der `NOT has_award`-Rueckfall hat keinen Riegel gegen die Quelle. Ein Vorgang, "
        "dessen Lose laut Quelle vergeben sind, wird dann als erfolglos gefuehrt, nur "
        "weil der Parser keine awards-Zeile gebildet hat.")


def test_nur_vollstaendig_leere_verfahren_zaehlen():
    """Teilvergaben duerfen nicht als erfolglos gelten.

    Gemessen: 12.169 Vorgaenge sind ganz leer, 3.455 nur teilweise. Die zu verschmelzen
    blaehte die Schwaeche-Achse von `market_opportunity` um ein Viertel auf.
    """
    assert "lose_vergeben = 0" in QUELLE, (
        "Die Bedingung `lose_vergeben = 0` fehlt — dann gilt schon ein einzelnes leeres "
        "Los als gescheitertes Verfahren.")
    # ⚠ Das SQL steht in der Variablen `ERGEBNIS`, nicht an der Stelle `erg AS (...)`.
    # Der erste Entwurf las dort nach und fand nur `{ERGEBNIS}` — ein Test, der an der
    # Einsetzstelle statt an der Definition sucht, prueft die Formatierung, nicht den Code.
    block = QUELLE.split("ERGEBNIS = (", 1)[1][:1200]
    assert "clos-nw" in block and "selec-w" in block, (
        "Das Ergebnis-CTE liest die TenderResultCode-Werte nicht mehr")
    assert "LotResult.TenderResultCode" in block, (
        "Der Pfad `LotResult.TenderResultCode` fehlt — ohne ihn kommt das CTE leer "
        "zurueck und jeder Vorgang faellt auf die alte Ableitung zurueck.")


# ---- Werte ------------------------------------------------------------------

@pytest.mark.skipif(not _q(), reason="quality DE nicht gebaut")
def test_keine_teilvergabe_gilt_als_erfolglos():
    con = duckdb.connect()
    n = con.execute(
        f"SELECT count(*) FROM read_parquet('{_q()}') "
        f"WHERE verfahren_status='erfolglos' AND lose_vergeben > 0").fetchone()[0]
    assert n == 0, f"{n} teilweise vergebene Verfahren stehen als erfolglos"


@pytest.mark.skipif(not _q(), reason="quality DE nicht gebaut")
def test_das_signal_sieht_in_den_eforms_jahren_wieder():
    """Die Jahresreihe, nicht die Summe.

    Vor der Aenderung: 2024 0,9 %, 2025 0,7 %, 2026 0,9 % — gegen 10 bis 13 % in den
    Jahren davor. Die Schwelle von 2 % ist bewusst weit unter dem gemessenen Stand
    (4,2 bis 5,3 %): sie soll das Erblinden fangen, nicht eine Schwankung.
    """
    con = duckdb.connect()
    for jahr, anteil in con.execute(f"""
            SELECT year(n.publication_date) j,
                   count(*) FILTER (WHERE q.verfahren_status='erfolglos')*1.0/count(*)
            FROM read_parquet('{_n()}', hive_partitioning=1) n
            LEFT JOIN read_parquet('{_q()}') q USING (notice_id)
            WHERE n.notice_kind='can' AND n.publication_date IS NOT NULL
              AND year(n.publication_date) BETWEEN 2024 AND 2026
            GROUP BY 1 HAVING count(*) > 5000""").fetchall():
        assert anteil > 0.02, (
            f"{jahr}: nur {100*anteil:.1f} % erfolglos. Das Signal erblindet wieder — "
            f"liest `TenderResultCode` noch jemand?")


@pytest.mark.skipif(not _q(), reason="quality DE nicht gebaut")
def test_altjahre_bleiben_unberuehrt():
    """Die Altformate tragen `TenderResultCode` nicht, also darf sich dort nichts ruehren.

    Die Werte stammen aus der Messung VOR der Aenderung (2026-10-04). Eine Abweichung
    hiesse, dass die neue Regel in Jahrgaenge greift, in denen es die Quelle gar nicht
    gibt — also ein Fehler in der Dreiwertigkeit von `quelle_sagt_leer`.
    """
    VORHER = {2019: 0.130, 2020: 0.105, 2021: 0.102, 2022: 0.123}
    con = duckdb.connect()
    for jahr, anteil in con.execute(f"""
            SELECT year(n.publication_date) j,
                   count(*) FILTER (WHERE q.verfahren_status='erfolglos')*1.0/count(*)
            FROM read_parquet('{_n()}', hive_partitioning=1) n
            LEFT JOIN read_parquet('{_q()}') q USING (notice_id)
            WHERE n.notice_kind='can' AND n.publication_date IS NOT NULL
              AND year(n.publication_date) BETWEEN 2019 AND 2022
            GROUP BY 1""").fetchall():
        soll = VORHER[jahr]
        assert abs(anteil - soll) < 0.005, (
            f"{jahr}: {100*anteil:.1f} % statt {100*soll:.1f} %. Die neue Regel greift "
            f"in ein Jahr, in dem die Quelle das Feld gar nicht traegt.")


@pytest.mark.skipif(not _q(), reason="quality DE nicht gebaut")
def test_der_grund_traegt_ein_bekanntes_vokabular():
    """BT-144. Ein roher, unbekannter Code waere ein Zeichen, dass der Pfad wandert."""
    ERLAUBT = {"no-rece", "all-rej", "chan-need", "ins-fund", "one-admis", "rev-buyer",
               "rev-body", "no-signed", "tch-pr-error", "other", "unpublished"}
    con = duckdb.connect()
    roh = {r[0] for r in con.execute(
        f"SELECT DISTINCT nichtvergabe_grund FROM read_parquet('{_q()}') "
        f"WHERE nichtvergabe_grund IS NOT NULL").fetchall()}
    # Mehrere Lose koennen verschiedene Gruende tragen, deshalb kommagetrennt.
    einzeln = {x for g in roh for x in str(g).split(",")}
    assert einzeln <= ERLAUBT, f"unbekannte Gruende: {einzeln - ERLAUBT}"


@pytest.mark.parametrize("land", ["AT", "CH", "LU"])
def test_gilt_in_allen_laendern(land):
    """EU-weit-Grundsatz: `TenderResultCode` steht in eForms, also ueberall."""
    p = _q(land)
    if not p:
        pytest.skip(f"quality {land} nicht gebaut")
    con = duckdb.connect()
    n = con.execute(
        f"SELECT count(*) FROM read_parquet('{p}') "
        f"WHERE nichtvergabe_grund IS NOT NULL").fetchone()[0]
    assert n > 0, (
        f"{land} traegt keinen einzigen Nichtvergabe-Grund. Gemessen am 2026-10-05: "
        f"AT 1.010, CH 1.013, LU 81. Null heisst, der Pfad ist dort nicht angeschlossen.")
