"""Volltextsuche für `gov_leads` — deutsches `tsvector` + GIN, inklusive Los-Texten.

**Warum überhaupt.** Bisher war ein Lead nur über Titel und CPV auffindbar. Gemessen
(2026-07-23) bringt die Suche über Beschreibung **und** Lostexte je nach Gewerk das 1,2-
bis 20-fache an Treffern — „Wärmepumpe" geht von 35 auf 699 Leads. Ohne Index wäre das
ein `ILIKE '%…%'`-Full-Scan über ~190 MB Text; mit Index sind es Millisekunden.

**Warum eine eigene Spalte statt `GENERATED ALWAYS`.** Das Suchdokument zieht Text aus
**zwei** Tabellen (`gov_leads` + `gov_lead_lots`). Eine generierte Spalte darf in Postgres
nur auf die eigene Zeile zugreifen — geht also nicht. Deshalb ein expliziter Refresh, den
`export_supabase.py` nach jedem Push aufruft. Wer `gov_lead_lots` ändert, ohne danach zu
refreshen, hat einen veralteten Index; `--verify` meldet das.

**Warum `strip()`.** Der Positions-Anteil eines `tsvector` ist der grösste Brocken und
wird nur für Phrasensuche (`<->`) gebraucht. Die brauchen wir nicht — `strip()` spart
grob die Hälfte, und der Free-Tier hat 500 MB.

**Kein Feld-Ranking im Dokument.** `setweight` + `strip` schliessen sich aus (Gewichte
hängen an Positionen). Das Ranking „Titel schlägt Los-Fussnote" macht die Abfrage, nicht
der Index — s. `docs/volltextsuche.md`.

Abfrage aus dem Frontend (PostgREST kann Volltext direkt):
    GET /rest/v1/gov_leads?search_doc=wfts(german).waermepumpe&select=slug,title
`wfts` = `websearch_to_tsquery` — versteht `"exakte phrase"`, `oder`, `-ausschluss`.

Aufruf:  python3 scripts/build_search_index.py [--verify] [--drop]
Braucht `SUPABASE_DB_URL` **oder** `.secrets/supabase.txt` + `.secrets/supabase_db.txt`.
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

# KEIN setweight hier — bewusst. `strip()` entfernt Positionen **und Gewichte** (so
# dokumentiert Postgres es auch), Gewichte werden naemlich pro Position gespeichert. Ein
# `setweight(...)` vor dem `strip()` ist also wirkungsloser Code, der nur so aussieht, als
# gaebe es ein Feld-Ranking. (Genau diesen Fehler hatte die erste Fassung: A/B/C gesetzt,
# gestrippt, und `search_doc::text ~ ':[ABC]'` war anschliessend `false`.)
#
# Die Alternative — Gewichte behalten und auf `strip()` verzichten — kostet grob das
# Doppelte an Spaltengroesse (64 MB → ~120 MB). Bei 500 MB Free-Tier ist das nicht drin.
# Feld-Ranking macht deshalb die ABFRAGE, siehe `docs/volltextsuche.md`:
#     order by (title ilike '%'||:q||'%') desc, ts_rank(search_doc, :tsq) desc
REFRESH_SQL = """
alter table gov_leads add column if not exists search_doc tsvector;

with lot as (
  select lead_id,
         string_agg(coalesce(lot_title,''), ' ')       as titles,
         string_agg(coalesce(lot_description,''), ' ') as descrs
    from gov_lead_lots group by lead_id
)
update gov_leads l set search_doc = strip(to_tsvector('german',
        coalesce(l.title,'')       || ' ' || coalesce(l.description,'') || ' ' ||
        coalesce(lot.titles,'')    || ' ' || coalesce(lot.descrs,'')))
  from lot where lot.lead_id = l.lead_id;

-- Leads ohne Lose: nur die eigenen Felder (sonst blieben sie NULL und unauffindbar).
update gov_leads l set search_doc = strip(to_tsvector('german',
        coalesce(l.title,'') || ' ' || coalesce(l.description,'')))
 where l.search_doc is null;

create index if not exists gov_leads_search_idx on gov_leads using gin (search_doc);
analyze gov_leads;
"""

VERIFY_SQL = """
select count(*) as leads,
       count(search_doc) as mit_index,
       count(*) filter (where search_doc is null) as ohne_index
  from gov_leads;
select pg_size_pretty(pg_total_relation_size('gov_leads')) as tabelle_gesamt,
       pg_size_pretty(pg_relation_size('gov_leads_search_idx')) as gin_index,
       pg_size_pretty(pg_database_size(current_database())) as db_gesamt;
"""


def db_url() -> str:
    if os.environ.get("SUPABASE_DB_URL"):
        return os.environ["SUPABASE_DB_URL"]
    # `.secrets/supabase.txt` haelt URL UND Key in ZWEI Zeilen — nicht blind einlesen.
    url = next((ln.strip() for ln in (ROOT / ".secrets" / "supabase.txt").read_text().splitlines()
                if ln.startswith("https://")), None)
    pw = (ROOT / ".secrets" / "supabase_db.txt").read_text().strip()
    if not (url and pw):
        raise SystemExit("Keine DB-Credentials — SUPABASE_DB_URL setzen.")
    ref = url.split("//", 1)[1].split(".", 1)[0]
    return f"postgresql://postgres:{pw}@db.{ref}.supabase.co:5432/postgres"


def psql(uri: str, sql: str, stop_on_error=True) -> str:
    env = {**os.environ, "PGCONNECT_TIMEOUT": "20"}
    cmd = ["psql", uri, "-P", "pager=off"]
    if stop_on_error:
        cmd += ["-v", "ON_ERROR_STOP=1"]
    out = subprocess.run(cmd, input=sql, capture_output=True, text=True, env=env)
    if out.returncode != 0:
        raise SystemExit(f"psql fehlgeschlagen:\n{out.stderr[:800]}")
    return out.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="nur pruefen, nicht neu bauen")
    ap.add_argument("--drop", action="store_true",
                    help="Index UND Spalte entfernen (falls der Free-Tier eng wird)")
    args = ap.parse_args()
    uri = db_url()

    if args.drop:
        print("Entferne Suchindex + Spalte …")
        print(psql(uri, "drop index if exists gov_leads_search_idx;\n"
                        "alter table gov_leads drop column if exists search_doc;\n"
                        "vacuum full gov_leads;"))
        return 0

    if not args.verify:
        print("Baue Suchdokument (Titel A · Beschreibung B · Lostitel B · Losbeschr. C) …")
        t = time.time()
        psql(uri, REFRESH_SQL)
        print(f"  fertig in {time.time()-t:.0f}s")

    print(psql(uri, VERIFY_SQL))
    return 0


if __name__ == "__main__":
    sys.exit(main())
