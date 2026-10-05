"""Direktvergabe-Begruendung (BT-136): Code, Codeliste, Daten.

WARUM DIESE DATEI. `ProcessJustification.ProcessReasonCode` traegt je nach `@listName`
DREI verschiedene Dinge — beschleunigtes Verfahren (true/false/0, 329.781 Vorgaenge),
Direktvergabe-Begruendung (47 Codes, 12.258) und fehlende E-Vergabe (5 Codes, 822).
Wert und `@listName` stehen als zwei Zeilen OHNE Index; paaren laesst sich das nicht.

Verwendbar ist das Feld nur, weil die drei Vokabulare **disjunkt** sind: der Wert
identifiziert seine Liste selbst. Diese Suite haelt genau das fest — waechst eine der
Listen um einen Code, der in einer anderen vorkommt, bricht die Annahme und die Suite
muss rot werden, bevor falsche Begruendungen im Produkt stehen.

⚠ Die Texte sind der AMTLICHE Wortlaut aus `data/reference/eforms/`, nicht unsere
Zusammenfassung. Die Codes benennen Ausnahmetatbestaende der Vergaberichtlinien; eine
eigene Kurzfassung waere die Umdeutung eines Rechtsbegriffs.
"""
import json
import pathlib
import re

import pytest

pytest.importorskip("duckdb")
import duckdb  # noqa: E402

WURZEL = pathlib.Path(__file__).resolve().parents[1]
QUELLE = (WURZEL / "govisor" / "gold.py").read_text(encoding="utf-8")
LISTE = WURZEL / "data" / "reference" / "eforms" / "direct-award-justification.json"

#: Die Vokabulare der beiden ANDEREN Listen unter demselben Element. Sie duerfen nie
#: als Direktvergabe-Grund durchkommen.
FREMD = {"true", "false", "0",                        # accelerated-procedure
         "phy-mod", "sen-info", "tdf-non-av", "ipr-iss", "sp-of-eq"}  # no-esubmission
#: TEDs Marke fuer „Angabe zurueckgehalten". Kein Grund.
ZURUECK = "unpublished"


def _export(land="DE"):
    p = WURZEL / "data" / "gold" / land / "lead_export.parquet"
    return p.as_posix() if p.exists() else None


# ---- Verdrahtung -------------------------------------------------------------

def test_spalte_in_beiden_exportpfaden():
    code = re.sub(r"(?m)^\s*#.*$", "", QUELLE)
    n = code.count("ctx.direct_award_reason")
    assert n >= 2, (
        f"ctx.direct_award_reason steht nur {n}x — erwartet einmal je Exportpfad "
        f"(build_lead_export und build_at_gold).")


def test_pfad_steht_in_der_positivliste_und_zwar_OHNE_listName():
    """⚠ Zwei Dinge auf einmal, und das zweite ist nicht Kosmetik.

    Mit `%ProcessReasonCode%` kamen 700.000 `accelerated-procedure`-Zeilen in den Scan
    und der DE-Lauf starb an der 5,5-GB-Grenze. Der Pfad muss ohne abschliessendes `%`
    stehen, damit nur die Wertzeile kommt.
    """
    block = QUELLE.split("def _lead_context_sql", 1)[1].split("GROUP BY notice_id", 1)[0]
    where = block.split("WHERE path LIKE", 1)[1]
    assert "'%ProcessJustification.ProcessReasonCode'" in where, (
        "Der Pfad fehlt in der Positivliste — die Spalte bliebe ueberall NULL.")
    assert "'%ProcessJustification.ProcessReasonCode%'" not in where, (
        "Der Pfad steht mit abschliessendem Platzhalter in der Positivliste. Damit "
        "kommen die @listName-Zeilen und 700.000 accelerated-procedure-Werte mit; "
        "der DE-Lauf stirbt an der Speichergrenze.")


def test_fremde_vokabulare_sind_ausgeschlossen():
    # ⚠ Der Name kommt ZWEIMAL vor: zuerst in der leeren Rueckfalltabelle, dann im
    # echten Ausdruck. Ein Schnitt an der ERSTEN Stelle endet vor der Ausschlussliste
    # und prueft eine Textstelle, die damit nichts zu tun hat.
    block = QUELLE.split("ProcessJustification.ProcessReasonCode'", 1)[1][:900]
    for wert in sorted(FREMD | {ZURUECK}):
        assert f"'{wert}'" in block, (
            f"`{wert}` fehlt in der Ausschlussliste. Es gehoert zu einer ANDEREN Liste "
            f"unter demselben Element und wuerde als Direktvergabe-Grund angezeigt.")


# ---- Codeliste ---------------------------------------------------------------

def test_die_amtliche_codeliste_liegt_vor():
    # ⚠ `data/` ist ein Symlink und damit unversioniert — dieselbe Lage wie beim
    # CPV-Katalog. Auf einer frischen Installation gibt es den Baum gar nicht; das ist
    # kein Defekt, sondern ein noch nicht gelaufener Abruf. Fehlt die Liste aber,
    # WAEHREND andere Referenzdaten da sind, hat jemand sie verloren — und im Produkt
    # steht dann der rohe Code.
    if not LISTE.parent.parent.is_dir():
        pytest.skip("data/reference fehlt — frische Installation ohne Referenzdaten")
    assert LISTE.exists(), (
        f"{LISTE} fehlt, obwohl data/reference existiert. "
        f"Holen: python3 scripts/hole_eforms_codeliste.py")
    d = json.loads(LISTE.read_text(encoding="utf-8"))
    assert len(d) >= 40, f"nur {len(d)} Codes — die Liste ist unvollstaendig"
    ohne = [k for k, v in d.items() if not v.get("de")]
    assert not ohne, f"ohne deutschen Wortlaut: {ohne[:6]}"


def test_die_drei_vokabulare_bleiben_disjunkt():
    """Die Annahme, auf der das ganze Feld steht.

    Kaeme ein Code aus `accelerated-procedure` oder `no-esubmission-justification` auch
    in der Direktvergabe-Liste vor, liesse sich nicht mehr unterscheiden, woher ein
    Wert stammt — und wir zeigten Rechtstexte an, die gar nicht gemeint sind.
    """
    if not LISTE.exists():
        pytest.skip("Codeliste fehlt")
    daj = set(json.loads(LISTE.read_text(encoding="utf-8")))
    schnitt = daj & FREMD
    assert not schnitt, (
        f"Die Vokabulare ueberschneiden sich in {sorted(schnitt)}. Damit faellt die "
        f"Grundlage des Feldes weg: der Wert identifiziert seine Liste nicht mehr.")


# ---- Werte -------------------------------------------------------------------

@pytest.mark.skipif(not _export(), reason="lead_export DE nicht gebaut")
def test_jeder_wert_steht_in_der_amtlichen_liste():
    if not LISTE.exists():
        pytest.skip("Codeliste fehlt")
    erlaubt = set(json.loads(LISTE.read_text(encoding="utf-8")))
    con = duckdb.connect()
    roh = {r[0] for r in con.execute(
        f"SELECT DISTINCT direct_award_reason FROM read_parquet('{_export()}') "
        f"WHERE direct_award_reason IS NOT NULL").fetchall()}
    assert roh <= erlaubt, f"Werte ausserhalb der Codeliste: {sorted(roh - erlaubt)}"


@pytest.mark.skipif(not _export(), reason="lead_export DE nicht gebaut")
def test_das_feld_ist_nicht_leer():
    con = duckdb.connect()
    n = con.execute(
        f"SELECT count(*) FROM read_parquet('{_export()}') "
        f"WHERE direct_award_reason IS NOT NULL").fetchone()[0]
    assert n > 500, (
        f"nur {n} Leads mit Begruendung — gemessen am 2026-10-05 waren es 4.946. "
        f"Ist der Pfad noch verdrahtet?")


@pytest.mark.parametrize("land", ["AT", "CH", "LU"])
def test_gilt_in_allen_laendern(land):
    """⚠ Die Schweiz ist der Sonderfall und zugleich die Gegenprobe.

    Die Codeliste benennt Ausnahmen der EU-Vergaberichtlinien. Die Schweiz faellt nicht
    darunter und meldet korrekt 0. Stuende dort eine nennenswerte Zahl, laege ein
    Lesefehler vor — dieselbe Logik wie beim EU-Mittel-Feld.
    """
    p = _export(land)
    if not p:
        pytest.skip(f"lead_export {land} nicht gebaut")
    con = duckdb.connect()
    n = con.execute(f"SELECT count(*) FROM read_parquet('{p}') "
                    f"WHERE direct_award_reason IS NOT NULL").fetchone()[0]
    if land == "CH":
        assert n == 0, (
            f"CH meldet {n} Direktvergabe-Begruendungen nach EU-Codeliste. Die Schweiz "
            f"faellt nicht unter die Richtlinien — das waere ein Lesefehler.")
    else:
        assert n > 0, (
            f"{land} meldet 0. Gemessen am 2026-10-05: AT 763, LU 14.")
