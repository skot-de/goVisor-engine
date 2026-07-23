"""Supabase auf einen **Entwicklungs-Sample** eindampfen (und dort halten).

**Warum.** Die Entwicklung läuft lokal auf Parquet (s. `CLAUDE.md`, „Arbeitsweise").
Der Volldatensatz belegte 453 von 500 MB im Free-Tier — Platz, den während der
Entwicklung niemand braucht, der aber jeden weiteren Push ans Limit drückt. Ein Sample
hält die API **echt bespielbar** fürs Frontend-Prototyping (PostgREST, RLS, Volltextsuche
verhalten sich identisch), kostet aber nur einen Bruchteil.

**Geschichtet, nicht zufällig.** Ein Zufallsziehung aus 85.947 Leads träfe fast nur den
Regelfall: 86 % `expiring`, 96 % TED, 84 % Einzellos. Das Frontend würde dann gegen einen
Sonderfall entwickelt und bei jeder Abweichung brechen. Deshalb wird über die vier
Dimensionen geschichtet, die die Darstellung tatsächlich verändern:

  Phase (expiring/open/planned) × Quelle (TED/DÖE) × Beschreibungstiefe × Mehrlosigkeit

Zusätzlich werden **Extremfälle erzwungen** (meiste Lose, längster Text, fehlender Wert,
fehlende Region, Amtsinhaber vorhanden/fehlend) — genau die Zeilen, an denen ein UI
zerbricht und die eine Quote nie zuverlässig erwischt.

**Löschen läuft über psql, nicht REST.** `?lead_id=not.in.(…)` mit 2.000 IDs ergäbe eine
~30 kB lange URL; ausserdem ist ein Anti-Join gegen eine Hilfstabelle schlicht der
richtige Weg. Danach `VACUUM FULL` — ohne das bleibt die Datei gross, nur innen leer.

Aufruf:  python3 scripts/supabase_dev_sample.py [--size 2000] [--dry-run]
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(ROOT)

import duckdb  # noqa: E402

EXPORT = "data/gold/DE/lead_export.parquet"
LOTS = "data/gold/DE/lead_lot.parquet"
TABLES = ["gov_lead_lots", "gov_lead_cpv", "gov_leads"]   # Kinder zuerst


def pick_sample(size: int) -> list[str]:
    """Geschichtete Auswahl + erzwungene Extremfälle."""
    con = duckdb.connect()
    con.execute("SET threads=4")
    # Schichten: je Kombination anteilig ziehen, aber MINDESTENS 5 Zeilen, damit auch
    # duenn besetzte Kombinationen (z. B. phase='planned') im Sample landen.
    rows = con.execute(f"""
        WITH s AS (
          SELECT lead_id,
                 phase,
                 (slug LIKE 'd%')            AS is_doe,
                 has_detailed_description     AS reich,
                 (n_lots > 1)                 AS mehrlos
            FROM read_parquet('{EXPORT}')
        ), g AS (
          SELECT *, count(*) OVER (PARTITION BY phase, is_doe, reich, mehrlos) AS grp_n,
                    count(*) OVER ()                                          AS tot,
                    row_number() OVER (PARTITION BY phase, is_doe, reich, mehrlos
                                       ORDER BY lead_id)                      AS rn
            FROM s
        )
        SELECT lead_id FROM g
         WHERE rn <= greatest(5, ceil({size} * grp_n / tot))
    """).fetchall()
    keep = {r[0] for r in rows}

    # Extremfaelle: die Zeilen, an denen ein UI bricht. Je Kriterium die Spitze.
    # Jedes Teil-SELECT geklammert — `ORDER BY … LIMIT` direkt vor einem UNION ist ein
    # Parser-Fehler (der ORDER BY wuerde sonst zur Gesamt-Union gehoeren).
    picks = [
        "ORDER BY n_lots DESC NULLS LAST LIMIT 5",
        "ORDER BY total_description_length DESC NULLS LAST LIMIT 5",
        "WHERE value_eur IS NULL LIMIT 5",
        "WHERE market_region_name IS NULL LIMIT 5",
        "WHERE incumbent_name IS NULL LIMIT 5",
        "WHERE incumbent_group_size > 1 LIMIT 5",
        "WHERE description IS NULL LIMIT 5",
        "WHERE timing_implausible LIMIT 5",
    ]
    union = " UNION ".join(
        f"(SELECT lead_id FROM read_parquet('{EXPORT}') {p})" for p in picks)
    extremes = con.execute(union).fetchall()
    keep |= {r[0] for r in extremes}
    con.close()
    return sorted(keep)


def describe(ids: list[str]) -> None:
    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("CREATE TEMP TABLE keep(lead_id VARCHAR)")
    con.executemany("INSERT INTO keep VALUES (?)", [(i,) for i in ids])
    r = con.execute(f"""
        SELECT count(*) n,
          count(*) FILTER (WHERE phase='open') offen,
          count(*) FILTER (WHERE phase='planned') geplant,
          count(*) FILTER (WHERE slug LIKE 'd%') doe,
          count(*) FILTER (WHERE has_detailed_description) reich,
          count(*) FILTER (WHERE n_lots > 1) mehrlos,
          count(*) FILTER (WHERE value_eur IS NULL) ohne_wert,
          count(DISTINCT market_nuts3) regionen, max(n_lots) max_lose
        FROM read_parquet('{EXPORT}') WHERE lead_id IN (SELECT lead_id FROM keep)""").fetchone()
    lots = con.execute(
        f"SELECT count(*) FROM read_parquet('{LOTS}') WHERE lead_id IN (SELECT lead_id FROM keep)"
    ).fetchone()[0]
    con.close()
    print(f"  Sample: {r[0]:,} Leads · {lots:,} Lose")
    print(f"    phase=open {r[1]:,} · planned {r[2]:,} · DÖE {r[3]:,} · reich {r[4]:,}")
    print(f"    mehrlosig {r[5]:,} · ohne Wert {r[6]:,} · {r[7]:,} Regionen · max {r[8]} Lose")


def db_url() -> str:
    import build_search_index as bsi
    return bsi.db_url()


def psql(uri: str, sql: str, quiet=True) -> str:
    cmd = ["psql", uri, "-P", "pager=off", "-v", "ON_ERROR_STOP=1"]
    if quiet:
        cmd.append("-q")
    out = subprocess.run(cmd, input=sql, capture_output=True, text=True,
                         env={**os.environ, "PGCONNECT_TIMEOUT": "20"})
    if out.returncode != 0:
        raise SystemExit(f"psql fehlgeschlagen:\n{out.stderr[:900]}")
    return out.stdout


SIZES = ("select relname, to_char(n_live_tup,'999G999G999') zeilen, "
         "pg_size_pretty(pg_total_relation_size(relid)) groesse "
         "from pg_stat_user_tables where schemaname='public' "
         "order by pg_total_relation_size(relid) desc; "
         "select pg_size_pretty(pg_database_size(current_database())) db_gesamt;")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=2000, help="Zielgroesse (Richtwert)")
    ap.add_argument("--dry-run", action="store_true", help="nur auswaehlen und zeigen")
    args = ap.parse_args()

    print(f"Waehle geschichtetes Sample (~{args.size:,} Leads) …")
    ids = pick_sample(args.size)
    describe(ids)
    if args.dry_run:
        print("--dry-run → nichts geloescht.")
        return 0

    uri = db_url()
    print("\nVORHER:"); print(psql(uri, SIZES, quiet=False))

    # Hilfstabelle statt einer 30-kB-URL. `unnest` haelt das Statement kurz.
    lit = ",".join("'" + i.replace("'", "''") + "'" for i in ids)
    print(f"Loesche alles ausserhalb des Samples ({len(ids):,} lead_id bleiben) …")
    t = time.time()
    psql(uri, f"""
        drop table if exists _dev_keep;
        create table _dev_keep(lead_id text primary key);
        insert into _dev_keep select unnest(array[{lit}]);
        {''.join(f"delete from {t} where lead_id not in (select lead_id from _dev_keep);"
                 for t in TABLES)}
        drop table _dev_keep;
    """)
    print(f"  geloescht in {time.time()-t:.0f}s · raeume Speicher frei (VACUUM FULL) …")
    # Ohne VACUUM FULL bleibt die Datei gross — Supabase misst den Plattenverbrauch,
    # nicht die Zahl lebender Zeilen.
    t = time.time()
    psql(uri, "".join(f"vacuum full {t};\nanalyze {t};\n" for t in TABLES))
    print(f"  fertig in {time.time()-t:.0f}s")

    print("\nSuchindex auf dem Sample neu bauen …")
    import build_search_index as bsi
    psql(uri, bsi.REFRESH_SQL)

    print("\nNACHHER:"); print(psql(uri, SIZES, quiet=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
