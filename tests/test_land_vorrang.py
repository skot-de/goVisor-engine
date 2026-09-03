"""Laender-Vorrang in der LLM-Warteschlange (`scripts/analyze_docs.py`).

⚠ WARUM ES DIESE DATEI GIBT. Der Vorrang ist ein Sortier-Glied, das je nach Umgebung DA ist
oder NICHT — und beide Faelle sind schon beim Bauen schiefgegangen, jeweils erst zur
Laufzeit. Ein Fehler hier faellt im Dienst auf, mitten im Geldausgeben.
"""
import importlib.util
import os
import pathlib

import duckdb
import pytest

WURZEL = pathlib.Path(__file__).resolve().parent.parent


def _lade(prio: str):
    """`analyze_docs` mit gesetztem LAND_PRIO frisch laden (Modulkonstanten!)."""
    alt = os.environ.get("LAND_PRIO")
    os.environ["LAND_PRIO"] = prio
    try:
        spec = importlib.util.spec_from_file_location(
            "ad_test", WURZEL / "scripts" / "analyze_docs.py")
        m = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(m)
        except SystemExit:                     # der Sperr-/Guthaben-Check darf aussteigen
            pass
        return m
    finally:
        if alt is None:
            os.environ.pop("LAND_PRIO", None)
        else:
            os.environ["LAND_PRIO"] = alt


def _reihenfolge(rang_sql: str) -> list[str]:
    con = duckdb.connect()
    con.execute("""
        create table t(notice_id varchar, land varchar);
        insert into t values ('de_offen_frueh','DE'),('de_offen_spaet','DE'),
          ('lu_offen','LU'),('lu_zu','LU'),('de_zu','DE');
        create table l(lead_id varchar, phase varchar, deadline_date date);
        insert into l values ('de_offen_frueh','open','2026-10-01'),
          ('de_offen_spaet','open','2026-12-01'),('lu_offen','open','2026-09-20'),
          ('lu_zu','closed','2026-01-01'),('de_zu','closed','2026-01-01');""")
    # ⚠ GENAU DIE FORM AUS DEM SKRIPT: das Komma haengt am Rang, nicht an der Aufrufstelle.
    return [r[0] for r in con.execute(f"""
        select t.notice_id from t left join l on l.lead_id = t.notice_id
        order by (l.phase='open') desc nulls last, {rang_sql}
                 l.deadline_date desc nulls last, t.notice_id desc""").fetchall()]


def test_ohne_liste_wird_gar_kein_term_ausgegeben():
    """⚠ KEIN PLATZHALTER. Zwei Anlaeufe sind daran gescheitert, beide erst zur Laufzeit:

      · `0`    ist im ORDER BY eine SPALTENNUMMER  → „ORDER term out of range"
      · `NULL` ist ein Literal ohne Wirkung        → „non-integer literal has no effect"

    Der Vorgabefall ist der HAEUFIGSTE — jeder Lauf ohne Vorrangliste. Ein Platzhalter haette
    also nicht einen Sonderfall zerlegt, sondern den Normalbetrieb.
    """
    m = _lade("")
    assert m._land_rang_sql("t.land") == ""
    _reihenfolge(m._land_rang_sql("t.land"))       # muss ueberhaupt binden


def test_vorrang_wirkt_nur_unter_den_offenen():
    """Der Rang steht HINTER `phase='open'` — Absicht, nicht Zufall.

    Sven am 2026-08-18: „lass die alten, alt sein". Ein Laenderrang VOR der Offen-Pruefung
    wuerde ein ABGELAUFENES Dokument des bevorzugten Landes vor eine laufende Vergabe eines
    anderen schieben und genau das Geld verbrennen, das jene Regel spart.
    """
    ohne = _reihenfolge(_lade("")._land_rang_sql("t.land"))
    mit = _reihenfolge(_lade("LU,DE")._land_rang_sql("t.land"))

    assert ohne == ["de_offen_spaet", "de_offen_frueh", "lu_offen", "lu_zu", "de_zu"]
    assert mit[0] == "lu_offen", "das bevorzugte Land kommt unter den offenen zuerst"
    assert mit.index("lu_zu") > mit.index("de_offen_spaet"), (
        "ein ABGELAUFENER LU-Vorgang darf NICHT vor eine offene deutsche Vergabe rutschen")


def test_nicht_genannte_laender_kommen_hinten():
    m = _lade("LU")
    sql = m._land_rang_sql("t.land")
    assert "WHEN 'LU' THEN 0" in sql and "ELSE 1" in sql
    assert sql.endswith(","), "das Komma gehoert an den Rang, sonst bricht die leere Fassung"
