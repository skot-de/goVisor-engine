"""EU-Kofinanzierung: `eu_funded` / `eu_programme` in `lead_export`.

Das Feld lag seit dem 2026-07-23 als bekannt und ungenutzt im Bronze-Inventar und ist
am 2026-10-04 angeschlossen worden. Diese Suite prueft nicht, DASS es die Spalte gibt,
sondern die vier Arten, auf die sie still falsch werden kann:

  1. Sie wird gebaut und nicht verdrahtet — die haeufigste Fehlerklasse hier. Eine
     Spalte voller NULL sieht aus wie eine Quelle, die nichts hergibt.
  2. Der Pfad faengt das Falsche. `%FundingProgramCode` trifft die ja/nein-Angabe UND
     den Programmnamen; rutscht `ERDF_2021` in `eu_funded`, steht dort eine 1 ohne Beleg.
  3. Aus Schweigen wird NEIN. Die Altformate kennen kein ausdrueckliches „nicht
     EU-finanziert". Wer dort 0 schreibt, behauptet etwas, das die Quelle nicht sagt.
  4. Die zwei Exportpfade (DE und AT) laufen auseinander — genau so stand AT am
     2026-08-22 auf 0 %, waehrend die Quelle die Werte trug.
"""
import os
import pathlib
import re

import pytest

pytest.importorskip("duckdb")
import duckdb  # noqa: E402

WURZEL = pathlib.Path(__file__).resolve().parent.parent
QUELLE = (WURZEL / "govisor" / "gold.py").read_text(encoding="utf-8")


def _export(land: str) -> str | None:
    p = WURZEL / "data" / "gold" / land / "lead_export.parquet"
    return p.as_posix() if p.exists() else None


# ---- 1. Verdrahtung: ohne Daten pruefbar -------------------------------------

def test_spalten_in_beiden_exportpfaden():
    """`build_lead_export` und `build_at_gold` fuehren getrennte Auswahllisten.

    ⚠ Der Test liest den Quelltext, weil der Fehler genau dort entsteht: eine Spalte
    wird in der einen Liste ergaenzt und in der anderen vergessen. Zur Laufzeit faellt
    das erst auf, wenn jemand AT-Leads ansieht.
    """
    # Kommentare raus, sonst schlaegt die Pruefung an der eigenen Erklaerung an.
    code = re.sub(r"(?m)^\s*#.*$", "", QUELLE)
    for spalte in ("ctx.eu_funded", "ctx.eu_programme"):
        n = code.count(spalte)
        assert n >= 2, (
            f"{spalte} steht nur {n}x im Code. Erwartet: einmal je Exportpfad "
            f"(build_lead_export und build_at_gold). Eine fehlende Stelle heisst, "
            f"dass ein Land die Spalte durchgehend leer traegt.")


def test_pfade_stehen_in_der_positivliste():
    """Die WHERE-Liste in `_lead_context_sql` ist eine Positivliste.

    Fehlt ein Pfad dort, liest das CTE ihn gar nicht erst: die Spalte kommt ueberall
    als NULL heraus, ohne Fehler und ohne roten Test. Dieser hier ist der rote Test.
    """
    block = QUELLE.split("def _lead_context_sql", 1)[1].split("GROUP BY notice_id", 1)[0]
    where = block.split("WHERE path LIKE", 1)[1]
    for pfad in ("%FundingProgramCode", "%EU_PROGR_RELATED%",
                 "%RELATES_TO_EU_PROJECT_YES.P"):
        assert pfad in where, f"{pfad} fehlt in der Positivliste von _lead_context_sql"


def test_leere_rueckfalltabelle_kennt_die_spalten():
    """Ein Land ohne `attributes` liefert eine leere Tabelle mit denselben Spalten.

    Fehlt dort eine Spalte, bricht der Gold-Bau fuer dieses Land mit einem
    Binder-Fehler ab — und zwar mitten im Lauf, nicht beim Start.
    """
    block = QUELLE.split("def _lead_context_sql", 1)[1].split("return f\"\"\"", 1)[0]
    for spalte in ("eu_funded", "eu_programme"):
        assert f"AS {spalte}" in block, (
            f"{spalte} fehlt in der leeren Rueckfalltabelle von _lead_context_sql")


# ---- 2. Werte: nur mit gebauten Daten ----------------------------------------

@pytest.mark.skipif(not _export("DE"), reason="lead_export DE nicht gebaut")
def test_eu_funded_nur_null_null_eins():
    """Drei Zustaende, kein vierter. Ein Programmname in dieser Spalte waere Fall 2."""
    con = duckdb.connect()
    werte = {r[0] for r in con.execute(
        f"SELECT DISTINCT eu_funded FROM read_parquet('{_export('DE')}')").fetchall()}
    assert werte <= {None, 0, 1}, f"unerwartete Werte in eu_funded: {werte - {None,0,1}}"


@pytest.mark.skipif(not _export("DE"), reason="lead_export DE nicht gebaut")
def test_eu_funded_ist_nicht_leer():
    """Die Verdrahtungsprobe mit Daten: eine durchgehend leere Spalte ist der Fehler.

    Gemessen am 2026-10-04: DE traegt rund 33.000 EU-finanzierte Vorgaenge. Die
    Schwelle ist bewusst niedrig — sie soll „gar nichts" fangen, nicht eine
    Schwankung des Bestandes.
    """
    con = duckdb.connect()
    ja, nein = con.execute(
        f"SELECT count(*) FILTER (WHERE eu_funded = 1), "
        f"count(*) FILTER (WHERE eu_funded = 0) "
        f"FROM read_parquet('{_export('DE')}')").fetchone()
    assert ja > 100, f"nur {ja} EU-finanzierte Leads — ist der Pfad noch verdrahtet?"
    assert nein > 100, (
        f"nur {nein} ausdruecklich NICHT EU-finanzierte Leads. eForms sagt "
        f"`no-eu-funds` ausdruecklich; fehlt das, liest der Pfad nur die Altformate.")


@pytest.mark.skipif(not _export("DE"), reason="lead_export DE nicht gebaut")
def test_altformate_tragen_nie_ein_ausdrueckliches_nein():
    """Fall 3: Schweigen darf nicht zu „nein" werden.

    ⚠ Hier stand zuerst eine Schwelle („mehr als 20 % muessen unbekannt sein"), und die
    war geraten. Gemessen am 2026-10-04 streut der Anteil ueber die Laender von **0,4 %
    (LU) bis 64,3 % (AT)** — er haengt daran, wieviel eForms gegen nationale Quellen ein
    Land liefert, und sagt ueber die Richtigkeit des Feldes nichts aus. Eine Schwelle
    darauf haette den Code bei jeder Verschiebung des Quellenmixes rot gemacht.

    Geprueft wird deshalb die AUSSAGE statt eines Anteils: nur eForms kennt ein
    ausdrueckliches `no-eu-funds`. Eine 0 an einem `legacy`-, `ojs`- oder `text`-Vorgang
    waere eine Behauptung, die die Quelle nicht deckt.
    """
    con = duckdb.connect()
    N = (WURZEL / "data/silver/DE/notices/**/*.parquet").as_posix()
    schuldig = con.execute(f"""
        SELECT n.schema_gen, count(*) FROM read_parquet('{_export('DE')}') e
        JOIN read_parquet('{N}', hive_partitioning=1) n ON n.notice_id = e.lead_id
        WHERE e.eu_funded = 0 AND n.schema_gen IN ('legacy','ojs','text')
        GROUP BY 1""").fetchall()
    assert not schuldig, (
        f"Generationen ohne ausdrueckliches NEIN tragen trotzdem eine 0: {schuldig}. "
        f"Aus fehlendem `EU_PROGR_RELATED` darf kein „nicht gefoerdert\" werden.")


@pytest.mark.skipif(not _export("DE"), reason="lead_export DE nicht gebaut")
def test_programmname_nie_ohne_foerderung():
    """Ein Programmname bei `eu_funded = 0` waere ein Widerspruch in einer Zeile."""
    con = duckdb.connect()
    n = con.execute(
        f"SELECT count(*) FROM read_parquet('{_export('DE')}') "
        f"WHERE eu_programme IS NOT NULL AND eu_funded = 0").fetchone()[0]
    assert n == 0, f"{n} Leads tragen ein Programm, sind aber als nicht gefoerdert markiert"


@pytest.mark.skipif(not _export("DE"), reason="lead_export DE nicht gebaut")
def test_programmcode_nicht_in_der_janein_spalte():
    """Fall 2 gegengeprueft: `eu_programme` traegt Namen, keine ja/nein-Codes."""
    con = duckdb.connect()
    schmutz = {r[0] for r in con.execute(
        f"SELECT DISTINCT eu_programme FROM read_parquet('{_export('DE')}') "
        f"WHERE lower(eu_programme) IN ('eu-funds','no-eu-funds','eu-funded',"
        f"'eu-programme','true','false','1','0')").fetchall()}
    assert not schmutz, f"ja/nein-Vokabular in eu_programme gelandet: {schmutz}"


@pytest.mark.parametrize("land", ["AT", "CH", "LU"])
def test_feld_gilt_in_allen_laendern(land):
    """EU-weit-Grundsatz: das Feld steht in eForms und gilt damit ueberall.

    ⚠ Die Schweiz ist der Sonderfall und zugleich die beste Gegenprobe: das Feld ist
    dort vorhanden, die Antwort muss aber durchgehend „nein" sein, weil die Schweiz
    kein Mitgliedstaat ist. Stuende dort eine nennenswerte Zahl EU-finanzierter
    Vorgaenge, laege ein Lesefehler vor.
    """
    pfad = _export(land)
    if not pfad:
        pytest.skip(f"lead_export {land} nicht gebaut")
    con = duckdb.connect()
    gesamt, ja = con.execute(
        f"SELECT count(*), count(*) FILTER (WHERE eu_funded = 1) "
        f"FROM read_parquet('{pfad}')").fetchone()
    if not gesamt:
        pytest.skip(f"{land}: keine Leads")
    anteil = ja / gesamt
    if land == "CH":
        assert anteil < 0.01, (
            f"CH meldet {100*anteil:.1f} % EU-finanziert. Die Schweiz ist kein "
            f"Mitgliedstaat — das waere ein Lesefehler, kein Befund.")
    else:
        assert ja > 0, (
            f"{land} meldet 0 EU-finanzierte Leads. Gemessen am 2026-10-04 trug "
            f"AT 1.233 und LU 2.178 Vorgaenge mit `eu-funds` in `attributes`. "
            f"Null heisst hier: der Pfad ist fuer dieses Land nicht angeschlossen.")
