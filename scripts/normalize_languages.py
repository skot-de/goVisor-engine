"""Sprachcodes im Bestand vereinheitlichen — `DE`/`DEU`/`de` → `de`.

Der Parser schreibt seit dem zugehörigen Commit kanonisch (s. `govisor/languages.py`); dieses
Skript zieht den Altbestand nach. Betroffen sind zwei Spalten:
  · `notices.language`      — eine Anzeigesprache je Notice
  · `notice_text.language`  — je Sprachfassung eine Zeile

**Warum es nötig ist.** Gemessen führt der Bestand **56 verschiedene Codes für 24 Sprachen**:
`DE` (2,25 Mio.) neben `DEU` (2,20 Mio.) neben `de`, weil die Legacy-Formulare ISO-639-1 im
`LG`-Attribut nutzen und eForms ISO-639-2/T in `languageID`. Für eine Sprachumschaltung ist
das unbrauchbar — wer nach `de` filtert, verliert die Hälfte.

**Kein Informationsverlust.** Die Abbildung ist rein verlustfrei: verschiedene Schreibweisen
derselben Sprache fallen zusammen, verschiedene Sprachen bleiben getrennt. Mehrwertige
Angaben (`DE;IT`, 122 Zeilen aus Südtirol) werden vereinheitlicht, nicht reduziert.

Sicherungen: `.part` + `rename` (atomar), Zeilenzahl muss erhalten bleiben, `--dry-run`
zeigt die Bilanz. Idempotent — ein zweiter Lauf findet nichts mehr.

Aufruf:  python scripts/normalize_languages.py [--laender DE,AT,CH,EU] [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import languages  # noqa: E402  (Pfad muss zuerst stehen)

SILBER = ROOT / "data" / "silver"
TABELLEN = ("notices", "notice_text")


def _case_sql(codes: set[str]) -> str:
    """CASE-Ausdruck aus der gemessenen Codeliste — kein Mapping in SQL nachbauen.

    Die Wahrheit liegt in `languages.normalize`; hier wird sie nur auf die tatsächlich
    vorkommenden Werte angewandt und als SQL materialisiert. So können Python-Funktion und
    Migration nicht auseinanderlaufen.
    """
    zweige = []
    for c in sorted(codes):
        neu = languages.normalize(c)
        if neu is not None and neu != c:
            zweige.append(f"WHEN language = '{c}' THEN '{neu}'")
    if not zweige:
        return ""
    return "CASE " + " ".join(zweige) + " ELSE language END"


def main(laender: list[str], dry: bool) -> int:
    con = duckdb.connect()
    gesamt_dateien = gesamt_zeilen = 0
    for land in laender:
        for tabelle in TABELLEN:
            basis = SILBER / land / tabelle
            dateien = sorted(basis.glob("*/*.parquet"))
            if not dateien:
                continue
            geaendert = zeilen = 0
            for f in dateien:
                q = f.as_posix()
                codes = {r[0] for r in con.execute(
                    f"SELECT DISTINCT language FROM read_parquet('{q}')").fetchall() if r[0]}
                case = _case_sql(codes)
                if not case:
                    continue                    # schon kanonisch
                n0 = con.execute(f"SELECT count(*) FROM read_parquet('{q}')").fetchone()[0]
                betroffen = con.execute(
                    f"SELECT count(*) FROM read_parquet('{q}') "
                    f"WHERE language <> ({case})").fetchone()[0]
                geaendert += 1
                zeilen += betroffen
                if dry:
                    continue
                spalten = [d[0] for d in con.execute(
                    f"SELECT * FROM read_parquet('{q}') LIMIT 0").description]
                sel = ", ".join(f"({case}) AS language" if s == "language" else s
                                for s in spalten)
                tmp = f.with_suffix(".part")
                con.execute(f"COPY (SELECT {sel} FROM read_parquet('{q}')) "
                            f"TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
                n1 = con.execute(f"SELECT count(*) FROM read_parquet('{tmp.as_posix()}')").fetchone()[0]
                if n1 != n0:
                    tmp.unlink(missing_ok=True)
                    raise SystemExit(f"ABBRUCH {f}: {n1} statt {n0} Zeilen")
                tmp.replace(f)
            if geaendert:
                print(f"  {land}/{tabelle}: {geaendert} Dateien, {zeilen:,} Zeilen"
                      + (" (dry-run)" if dry else " umgeschrieben"))
                gesamt_dateien += geaendert
                gesamt_zeilen += zeilen
    print(f"\nSumme: {gesamt_dateien} Dateien, {gesamt_zeilen:,} Zeilen"
          + (" — dry-run" if dry else " vereinheitlicht"))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--laender", default="DE,AT,CH,EU")
    ap.add_argument("--dry-run", dest="dry", action="store_true")
    a = ap.parse_args()
    sys.exit(main([x.strip() for x in a.laender.split(",") if x.strip()], a.dry))
