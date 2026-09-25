"""Wer nur unter seinem Namen bekannt ist, kommt in den Suchraum — wenn er belegt ist.

⚠ DER BEFUND. `suppliers.json` nahm nur Identitaeten auf, die ueber Handelsregister oder
TED-Kennnummer aufgeloest sind. Gemessen am 2026-09-25 sind das 17 % des Bestands, waehrend
**54 % aller Firmen die Methode `nur_name` tragen**. 13.390 davon haben mindestens drei
Zuschlaege und trotzdem kein Profil, keine Suche, keine Existenz im Produkt. Aufgefallen an
der Westfaelischen Drahtindustrie aus Hamm: fuenf Zuschlaege, kein Eintrag.

⚠ WIDERSPRUECHE WERDEN MARKIERT, NICHT AUFGELOEST. Sven am 2026-09-25: „die
widersprüchlichen markieren statt verschmelzen." 2.377 der Zielmenge fuehren ueber ihre
Meldungen mehrere Postleitzahlen — Niederlassungen ODER zwei gleichnamige Firmen, und
beides sieht gleich aus. Die Drahtindustrie selbst faellt in diese Gruppe (dreimal Hamm,
zweimal Berlin) und kommt deshalb NICHT herein. Das ist die richtige Antwort, nicht der
Rest eines ungeloesten Problems: bei der letzten Entity-Zusammenfuehrung zog die
naheliegende Namensregel 25.250 Zuschlaege in einen Klumpen.

⚠ „VORHANDEN" IST KEIN BELEG. 78 % der Zielmenge tragen irgendeine Postleitzahl, aber nur
45 % ueber mehrere Meldungen DIESELBE. Eine einzelne Adresse bestaetigt nichts.
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
from govisor import gold  # noqa: E402

BELEG = WURZEL / "data" / "gold" / "DE" / "entity_beleg.parquet"
EXPORT = WURZEL / "scripts" / "export_suppliers.py"


# ── Die Einstufung, an einem gebauten Datensatz gerechnet ───────────────────────────────
def _klassen(rows):
    """Die CASE-Regel aus `build_entity_beleg`, auf Testzeilen angewandt."""
    frei = ", ".join(f"'{d}'" for d in gold._BELEG_FREIMAILER)
    con = duckdb.connect()
    con.execute("CREATE TABLE s(entity_id VARCHAR, notice_id VARCHAR, plz VARCHAR, "
                "nid VARCHAR, maildomain VARCHAR)")
    con.executemany("INSERT INTO s VALUES (?,?,?,?,?)", rows)
    return dict(con.execute(f"""
      WITH roh AS (
        SELECT entity_id,
               count(DISTINCT plz) FILTER (WHERE plz IS NOT NULL) AS n_plz,
               count(*)            FILTER (WHERE plz IS NOT NULL) AS c_plz,
               count(DISTINCT nid) FILTER (WHERE nid IS NOT NULL AND nid <> '-') AS n_nid,
               count(DISTINCT maildomain) FILTER (
                    WHERE maildomain IS NOT NULL AND maildomain NOT IN ({frei})) AS n_domain,
               count(*) FILTER (
                    WHERE maildomain IS NOT NULL AND maildomain NOT IN ({frei})) AS c_domain
        FROM s GROUP BY 1)
      SELECT entity_id, CASE
               WHEN n_nid = 1                        THEN 'kennnummer'
               WHEN n_plz > 1                        THEN 'widerspruch'
               WHEN n_plz = 1 AND c_plz >= 2         THEN 'anschrift'
               WHEN n_domain = 1 AND c_domain >= 2   THEN 'maildomain'
               ELSE 'unbelegt' END
      FROM roh""").fetchall())


def test_eine_stabile_anschrift_belegt():
    k = _klassen([("a", "n1", "59067", None, None), ("a", "n2", "59067", None, None)])
    assert k["a"] == "anschrift"


def test_eine_einzelne_anschrift_belegt_nicht():
    """⚠ Der Unterschied zwischen 78 % und 45 %: einmal genannt ist nicht bestaetigt."""
    k = _klassen([("a", "n1", "59067", None, None)])
    assert k["a"] == "unbelegt"


def test_mehrere_anschriften_sind_ein_widerspruch():
    k = _klassen([("a", "n1", "59067", None, None), ("a", "n2", "10115", None, None)])
    assert k["a"] == "widerspruch"


def test_die_kennnummer_schlaegt_den_widerspruch():
    """Wer durchgehend dieselbe Kennnummer traegt, ist belegbar EINE Firma mit mehreren
    Standorten. Ohne sie bleibt es offen."""
    k = _klassen([("a", "n1", "59067", "X1", None), ("a", "n2", "10115", "X1", None)])
    assert k["a"] == "kennnummer"


def test_zwei_kennnummern_belegen_nicht():
    k = _klassen([("a", "n1", "59067", "X1", None), ("a", "n2", "59067", "X2", None)])
    assert k["a"] == "anschrift", k


def test_freimailer_belegen_keine_firma():
    """⚠ Eine @gmx.de-Adresse belegt, dass jemand ein Postfach hat."""
    k = _klassen([("a", "n1", None, None, "gmx.de"), ("a", "n2", None, None, "gmx.de")])
    assert k["a"] == "unbelegt"
    k2 = _klassen([("b", "n1", None, None, "wdi.de"), ("b", "n2", None, None, "wdi.de")])
    assert k2["b"] == "maildomain"


# ── Die Verdrahtung: ohne sie ist die Tabelle ein Datenfriedhof ─────────────────────────
def test_der_suchraum_laesst_belegte_herein_und_widersprueche_draussen():
    q = EXPORT.read_text(encoding="utf-8")
    assert "entity_beleg.parquet" in q, "der Export liest die Beleglage nicht"
    assert "_BELEG_OK = (\"kennnummer\", \"anschrift\", \"maildomain\")" in q
    assert "widerspruch" not in q.split("_BELEG_OK")[1][:200], (
        "ein Widerspruch darf nicht als Eintrittskarte gelten")
    # ⚠ DIE ZUTAT ALLEIN REICHT NICHT. Der erste Anlauf prueffte nur, dass die Tabelle
    # gelesen und die Liste definiert ist — mit `OR false` in der Bedingung blieb er gruen,
    # obwohl die Tuer zu war. Geprueft wird jetzt die BEDINGUNG selbst.
    i = q.index("CREATE OR REPLACE TEMP TABLE belegt AS")
    cte = q[i:q.index('"""', i + 10)]
    assert "coalesce(b.beleg, 'unbelegt') IN ({_beleg_liste})" in cte, (
        "die Beleglage haengt nicht in der Aufnahmebedingung")
    assert "LEFT JOIN {BELEG}" in cte, "die Belegtabelle ist nicht angebunden"


def test_die_belegtabelle_wird_in_allen_laendern_gebaut():
    """⚠ `export_suppliers.py` liest ueber alle Laender. Fehlt die Tabelle fuer eines,
    faellt dessen Bestand still auf die alte Regel zurueck."""
    assert "build_entity_beleg" in (WURZEL / "govisor" / "cli.py").read_text(encoding="utf-8")
    dach = (WURZEL / "scripts" / "build_dach_gold.py").read_text(encoding="utf-8")
    assert '("build_entity_beleg",' in dach, "AT/CH/LU bauen die Beleglage nicht"


def test_der_deckel_schneidet_nicht_stillschweigend_ab():
    """⚠ DER FEHLER, DER BEIM BAUEN PASSIERT IST. `MAX_ROWS` ist als Sicherung gegen
    Ausreisser gedacht. Mit der zweiten Tuer stiegen die Identitaeten ab 3 Zuschlaegen von
    32.659 auf 41.407 — ueber die damaligen 40.000. `ORDER BY wins DESC, identity_id`
    schnitt bei Gleichstand ALPHABETISCH ab: 5.523 Firmen mit genau drei Zuschlaegen
    verschwanden, lueckenlos ab „be…", und das Skript meldete nichts.
    """
    q = EXPORT.read_text(encoding="utf-8")
    i = q.index("MAX_ROWS = ")
    wert = int(q[i:].split("=")[1].split("#")[0].strip())
    if not BELEG.exists():
        return                          # ohne Gold keine Aussage
    con = duckdb.connect()
    G = (WURZEL / "data" / "gold" / "DE").as_posix()
    n = con.execute(f"""
      WITH belegt AS (SELECT DISTINCT ei.identity_id
        FROM read_parquet('{G}/entity_identity.parquet') ei
        JOIN read_parquet('{G}/entities.parquet') e ON e.entity_id = ei.entity_id
        LEFT JOIN read_parquet('{G}/entity_beleg.parquet') b ON b.entity_id = ei.entity_id
        WHERE e.method IN ('handelsregister_exakt','ted_nationalid')
           OR coalesce(b.beleg,'unbelegt') IN ('kennnummer','anschrift','maildomain')),
      w AS (SELECT ei.identity_id, p.notice_id
            FROM read_parquet('{G}/party_entity.parquet') p
            JOIN read_parquet('{G}/entity_identity.parquet') ei ON ei.entity_id = p.entity_id
            WHERE p.role='winner' AND ei.identity_id IN (SELECT identity_id FROM belegt))
      SELECT count(*) FROM (SELECT identity_id FROM w GROUP BY 1
                            HAVING count(DISTINCT notice_id) >= 3)""").fetchone()[0]
    assert n < wert, (
        f"der Deckel bindet: {n:,} Identitaeten ab 3 Zuschlaegen gegen MAX_ROWS={wert:,}. "
        "Er schneidet dann bei Gleichstand alphabetisch ab, ohne es zu melden.")
