"""Qualifizierungssysteme kommen im Produkt an — und bekommen keine erfundene Frist.

⚠ DER BEFUND, GEMESSEN AM 2026-09-25. Von 48 Qualifizierungssystemen in den DE-Rohdaten
kamen 2 im Produkt an. `build_prospective_leads` verlangt eine ECHTE Frist in der Zukunft;
ein Qualifizierungssystem hat naturgemaess keine, denn wer die Bedingungen erfuellt, tritt
jederzeit bei. Die Fristschaetzung in `build_lead_deadline` setzte ihnen stattdessen
publication_date + ~30 Tage — und erzeugte damit einen Zustand, den es nicht gibt:
„abgelaufen" bei etwas, das dauerhaft offen steht. 22 von 38 galten so als vorbei.

⚠ DAS AMTLICHE MERKMAL WAR TOT. Vor eForms trug das Formular den Namen `F07_2014`; in DE
fiel es von 149 (2023) auf 12 (2024) auf NULL ab 2025. eForms fuehrt es als
`<cbc:SubTypeCode listName="notice-subtype">` weiter. Welche Zahl es ist, wurde gemessen,
nicht geraten: ueber drei Rohmonate tragen 63 % der Subtyp-15-Meldungen das Wort
„Qualifizierungssystem", bei jedem anderen Subtyp sind es unter 6 %.

⚠ ZWEI DUCKDB-FALLEN STECKEN DARIN, und beide sind still:
  * OHNE `union_by_name` liest DuckDB einen Glob nach dem Schema der ERSTEN Datei und
    verschluckt eine neue Spalte kommentarlos.
  * `union_by_name` allein reicht nicht: solange KEINE Datei die Spalte hat, ist der Name
    unbekannt und ein direkter Zugriff haelt die Gold-Kette mit einem Binder-Fehler an.
Deshalb `_subtyp_spalte`, und deshalb prueft dieser Test beide Zustaende.
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pytest

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
from govisor import gold  # noqa: E402


def _silber(ordner: Path, mit_spalte: bool) -> str:
    """Eine Silber-aehnliche Datei, mit oder ohne `notice_subtype`."""
    con = duckdb.connect()
    ziel = ordner / ("neu.parquet" if mit_spalte else "alt.parquet")
    if mit_spalte:
        con.execute(f"""COPY (
            SELECT * FROM (VALUES
              ('q1','cn','15', NULL),          -- Qualifizierungssystem, keine Frist
              ('q2','cn','16', NULL),          -- gewoehnliche Ausschreibung ohne Frist
              ('q3','cn','15', DATE '2026-12-01')  -- QS, das doch eine Frist nennt
            ) t(notice_id, notice_kind, notice_subtype, submission_deadline)
        ) TO '{ziel.as_posix()}' (FORMAT PARQUET)""")
    else:
        con.execute(f"""COPY (
            SELECT * FROM (VALUES ('a1','cn', NULL))
              t(notice_id, notice_kind, submission_deadline)
        ) TO '{ziel.as_posix()}' (FORMAT PARQUET)""")
    con.close()
    return ziel.as_posix()


def test_ohne_die_spalte_faellt_nichts_um(tmp_path):
    """⚠ DER GEFAEHRLICHERE FALL. Heute hat KEINE Silber-Datei die Spalte. Ein direkter
    Zugriff wuerde die ganze Gold-Kette anhalten — fuer alle Laender gleichzeitig."""
    _silber(tmp_path, mit_spalte=False)
    con = duckdb.connect()
    glob = f"'{(tmp_path / '*.parquet').as_posix()}'"
    ausdruck = gold._subtyp_spalte(con, glob)
    assert ausdruck == "CAST(NULL AS VARCHAR)", ausdruck
    # Und die Bedingung muss sich damit fehlerfrei ausfuehren lassen.
    wo = gold._qualifikationssystem_sql(ausdruck)
    n = con.execute(f"SELECT count(*) FROM read_parquet({glob}, union_by_name=1) n "
                    f"WHERE {wo}").fetchone()[0]
    assert n == 0


def test_mit_der_spalte_greift_die_erkennung(tmp_path):
    _silber(tmp_path, mit_spalte=True)
    con = duckdb.connect()
    glob = f"'{(tmp_path / '*.parquet').as_posix()}'"
    ausdruck = gold._subtyp_spalte(con, glob)
    assert ausdruck == "n.notice_subtype", ausdruck
    wo = gold._qualifikationssystem_sql(ausdruck)
    ids = [r[0] for r in con.execute(
        f"SELECT notice_id FROM read_parquet({glob}, union_by_name=1) n WHERE {wo} ORDER BY 1"
    ).fetchall()]
    assert ids == ["q1", "q3"], ids


def test_gemischte_dateien_verschlucken_die_spalte_nicht(tmp_path):
    """⚠ DIE STILLE FALLE. Eine alte Datei ohne die Spalte, eine neue mit ihr — genau der
    Zustand nach dem ersten Ingest. Ohne `union_by_name` liest DuckDB nach dem Schema der
    ERSTEN Datei und meldet dabei NICHTS."""
    _silber(tmp_path, mit_spalte=False)
    _silber(tmp_path, mit_spalte=True)
    con = duckdb.connect()
    glob = f"'{(tmp_path / '*.parquet').as_posix()}'"
    assert gold._subtyp_spalte(con, glob) == "n.notice_subtype"
    n = con.execute(f"SELECT count(*) FROM read_parquet({glob}, union_by_name=1) n "
                    f"WHERE {gold._qualifikationssystem_sql('n.notice_subtype')}").fetchone()[0]
    assert n == 2
    # Die Gegenprobe: ohne union_by_name geht die Spalte verloren.
    with pytest.raises(Exception):
        con.execute(f"SELECT notice_subtype FROM read_parquet({glob}) LIMIT 1").fetchone()


def test_beide_baustellen_benutzen_die_pruefung_und_union_by_name():
    """⚠ Wiring-Pruefung, und sie weiss das. Die Erkennung nuetzt nichts, wenn eine der
    beiden Stellen sie nicht benutzt — und `union_by_name` nichts, wenn es nur an einer
    von beiden steht."""
    q = (WURZEL / "govisor" / "gold.py").read_text(encoding="utf-8")
    for name in ("build_lead_deadline", "build_prospective_leads"):
        i = q.index(f"def {name}(")
        j = q.index("\ndef ", i + 10)
        blok = q[i:j]
        assert "_qualifikationssystem_sql(_subtyp_spalte(" in blok, f"{name} kennt die Pruefung nicht"
        assert "union_by_name=1" in blok, f"{name} liest ohne union_by_name"
        assert "{QS}" in blok, f"{name} benutzt die Bedingung nicht"


def test_die_fristherkunft_heisst_unbefristet_und_nicht_geschaetzt():
    """⚠ „geschaetzt" haette eine Genauigkeit behauptet, die niemand nachpruefen kann. Es
    gibt keine Frist — das ist eine Aussage, keine Schaetzung."""
    q = (WURZEL / "govisor" / "gold.py").read_text(encoding="utf-8")
    i = q.index("def build_lead_deadline(")
    blok = q[i:q.index("\ndef ", i + 10)]
    assert "WHEN {QS} THEN 'unbefristet'" in blok
    assert "WHEN {QS} THEN DATE '2100-01-01'" in blok, (
        "ohne Platzhalterdatum faellt es wieder aus der Frist-Bedingung")


def test_das_feld_ueberlebt_den_weg_bis_in_die_datei(tmp_path):
    """⚠ DER FEHLER, DEN ICH SELBST GEMACHT HABE. Die Extraktion war gebaut, getestet und
    gruen — und nach dem Nachtlauf stand die Spalte trotzdem nicht in Silber. Grund:
    `model.TABLES['notices']` ist ein FESTES Arrow-Schema, und ein Schluessel, der dort
    fehlt, wird beim Schreiben kommentarlos verworfen. Ein Test auf `normalize.rows` allein
    haette den Fehler nie gesehen; geprueft wird deshalb bis in die geschriebene Datei.
    """
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    from govisor import model

    zeile = {f.name: None for f in model.TABLES["notices"]}
    assert "notice_subtype" in zeile, (
        "das Feld fehlt im Arrow-Schema — dann faellt es beim Schreiben lautlos weg")
    zeile.update({"notice_id": "x", "notice_subtype": "15", "year": 2026, "month": 9})
    ziel = tmp_path / "probe.parquet"
    pq.write_table(pa.Table.from_pylist([zeile], schema=model.TABLES["notices"]), ziel)
    con = duckdb.connect()
    wert = con.execute(
        f"SELECT notice_subtype FROM read_parquet('{ziel.as_posix()}')").fetchone()[0]
    assert wert == "15", wert


def test_die_extraktion_liefert_den_subtyp_an_normalize():
    """Die Kette davor: XML -> parse -> rows. Ohne echte Rohdaten keine Aussage."""
    import glob

    from govisor import normalize, schema

    treffer = glob.glob(str(WURZEL / "data" / "raw_live" / "DE" / "*" / "490416-2026.xml"))
    if not treffer:
        return
    roh = Path(treffer[0]).read_bytes()
    n = schema.parse(roh, "490416_2026")
    assert n.notice_subtype == "15", n.notice_subtype
    zeilen = normalize.rows(n, roh, "DE", 2026, 7)["notices"]
    assert zeilen[0]["notice_subtype"] == "15"
