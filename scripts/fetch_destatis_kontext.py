"""Destatis-Regionalkontext je Kreis (A–D) → ``data/reference/kreis_kontext.parquet``.

Ergänzt die reine Nachfragesicht (unsere Ausschreibungen) um den regionalen Kontext:

  A **Angebotsseite**  44231-01-03-4  Baubetriebe, tätige Personen, baugewerblicher Umsatz
  B **Vorlaufindikator** 31111-05-01-4 Baugenehmigungen (Wohn- + Nichtwohngebäude)
  C **Fiskalische Kapazität** 71327-Z-02 Schulden der kommunalen Kernhaushalte + Beteiligungen
  D **Normalisierung** 12411-01-01-4 Bevölkerung · 13111-01-03-4 SV-Beschäftigte

Speichert **long** (eine Zeile je Kreis × Jahr × Kennzahl) — bewusst nicht breit, weil die
Kennzahl-Codes je Statistik variieren; die Auswertung pickt sich, was sie braucht.
NUTS-3-Zuordnung über normalisierten Kreisnamen, nur EINDEUTIGE Treffer (Rest bleibt NULL).

Aufruf:  python scripts/fetch_destatis_kontext.py [--year 2023]
"""
import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from scripts.fetch_destatis import fetch_flat_csv, log  # noqa: E402

# Tabelle → (Themenblock, Fallback-Jahre falls das Wunschjahr leer ist)
TABLES = {
    "44231-01-03-4": ("A_angebot", [2023, 2022, 2021]),
    "31111-05-01-4": ("B_vorlauf", [2023, 2022, 2021]),
    "71327-Z-02": ("C_fiskal", [2023, 2022, 2021]),
    "12411-01-01-4": ("D_bevoelkerung", [2023, 2022, 2021]),
    "13111-01-03-4": ("D_beschaeftigte", [2023, 2022, 2021]),
}


def _kreis_rows(con, csv_path, table, block):
    """FKREISE-Zeilen einer Flat-CSV in Long-Form (ags, name, jahr, code, label, wert)."""
    R = (f"read_csv('{csv_path}', delim=';', header=true, auto_detect=true, "
         f"ignore_errors=true, all_varchar=true)")
    return con.execute(f"""
        SELECT '{table}' AS tabelle, '{block}' AS block,
               regexp_replace("1_variable_attribute_code", '^[A-Za-z]+', '') AS ags,
               "1_variable_attribute_label" AS kreis_name,
               TRY_CAST(regexp_extract("time", '([0-9]{{4}})', 1) AS INT) AS jahr,  -- {{4}} escapen (f-String!), "time" quoten (Typ-Keyword)
               value_variable_code AS kennzahl_code,
               value_variable_label AS kennzahl_label,
               TRY_CAST(value AS DOUBLE) AS wert,
               value_unit AS einheit
        FROM {R}
        WHERE "1_variable_code" LIKE '%KREISE%' AND TRY_CAST(value AS DOUBLE) IS NOT NULL
    """).fetch_arrow_table()


def main(year: int) -> int:
    import duckdb
    import pyarrow as pa

    con = duckdb.connect(); con.execute("SET threads=4")
    cache = ROOT / "data" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    parts = []
    for table, (block, years) in TABLES.items():
        got = False
        for y in [year] + [x for x in years if x != year]:
            p = cache / f"destatis_{table}_{y}.csv"
            if p.exists():
                log(f"{table} ({block}) — Jahr {y} (Cache)")
            else:
                try:
                    log(f"{table} ({block}) — Jahr {y}")
                    p.write_text(fetch_flat_csv(y, table=table))
                except Exception as exc:
                    log(f"  übersprungen: {str(exc)[:110]}")
                    continue
            tbl = _kreis_rows(con, p.as_posix(), table, block)
            if tbl.num_rows:
                parts.append(tbl)
                log(f"  → {tbl.num_rows:,} Kreis-Zeilen")
                got = True
                break
            log("  keine Kreis-Zeilen, nächstes Jahr")
        if not got:
            log(f"  {table}: KEINE Daten gefunden")

    if not parts:
        log("nichts geholt"); return 0
    con.register("_all", pa.concat_tables(parts, promote_options="default"))
    norm = (r"lower(trim(regexp_replace(regexp_replace({c},"
            r"'(,\s*)?(Landkreis|Kreisfreie Stadt|Stadtkreis|Kreis|Landeshauptstadt)\s*$','','gi'),"
            r"'^(Landkreis|Kreis|Stadtkreis)\s+','','gi')))")
    con.execute(f"""CREATE TEMP TABLE nuts AS
        SELECT {norm.format(c='name')} AS nkey, any_value(nuts_code) AS nuts_code, count(*) AS n
        FROM read_parquet('data/gold/DE/dim_nuts.parquet') WHERE level=3 GROUP BY 1""")
    out = ROOT / "data" / "reference" / "kreis_kontext.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"""COPY (
        SELECT a.*, CASE WHEN nuts.n = 1 THEN nuts.nuts_code END AS nuts_code
        FROM _all a LEFT JOIN nuts ON nuts.nkey = {norm.format(c='a.kreis_name')}
    ) TO '{out.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    n, mapped, blocks = con.execute(
        f"SELECT count(*), count(nuts_code), count(DISTINCT block) "
        f"FROM read_parquet('{out.as_posix()}')").fetchone()
    log(f"FERTIG: {n:,} Zeilen aus {blocks} Blöcken → {out} ({mapped:,} mit NUTS-3)")
    con.close()
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2023)
    main(ap.parse_args().year)
