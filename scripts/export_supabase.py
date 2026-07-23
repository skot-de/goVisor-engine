"""Export `lead_export` nach Supabase (Frontend-Tabelle `gov_leads`).

Zwei Schritte:
  1. **DDL** (`CREATE TABLE gov_leads …`) → schreibt `docs/supabase_gov_leads.sql`.
     Einmalig im **Supabase-Dashboard → SQL Editor** ausführen (DDL geht nicht über die
     REST-API — s. Projekt-Memory: „DDL-Migrations via Dashboard").
  2. **Upsert** der Zeilen via REST-API (merge-duplicates auf lead_id). Braucht Env:
        SUPABASE_URL=https://<ref>.supabase.co
        SUPABASE_SERVICE_KEY=<service-role-key>
     Ohne Creds schreibt das Script nur die DDL + einen NDJSON-Export (import-ready) und
     erklärt, was zu tun ist. (Pooler scheitert auf dieser Maschine → REST-API.)

Aufruf:  python scripts/export_supabase.py [--table gov_leads] [--dry-run]
"""
import argparse
import html
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import duckdb  # noqa: E402

EXPORT = "data/gold/DE/lead_export.parquet"

# Postgres-DDL (Spalten = Frontend-Feld-Vertrag). Indizes = die Explorer-Facetten.
DDL = """-- goVisor Frontend-Tabelle: eine Zeile je Lead (aus gold.build_lead_export).
-- Einmalig im Supabase-Dashboard → SQL Editor ausführen.
create table if not exists {table} (
  lead_id           text primary key,
  slug              text unique not null,   -- permanente Kurz-ID für Shareable-Links
  titel             text,
  buyer             text,
  buyer_town        text,
  cpv               text,
  cpv_label         text,
  nuts_full         text,
  nuts1             text,
  region            text,
  art               text,
  phase             text,          -- auslauf | f02 | f01
  neu               boolean,
  natur_kat         text,          -- dienst | liefer | bau
  natur_src         text,          -- echt (TED BT-23) | geschaetzt (CPV-Fallback)
  volumen_wert      double precision,
  volumen_band      text,
  volumen_src       text,          -- echt | schaetz | unbekannt
  months_to_expiry  integer,
  faellig_basis     text,
  timing_warn       boolean,
  timing_src        text,          -- echt | schaetz | unsicher | unbekannt
  incumbent_name    text,
  incumbent_seit    integer,
  incumbent_conf    real,
  incumbent_src     text,          -- echt | unsicher
  wechsel           text,          -- hoch | mittel | niedrig | na
  num_tenders       integer,
  single_bidder     boolean,
  konk_stufe        text,          -- gering | mittel | hoch | na
  konk_src          text,
  ted_url           text,
  has_cmp           boolean,
  has_contracts     boolean,
  updated_at        timestamptz default now()
);
create index if not exists {table}_slug_idx   on {table} (slug);   -- Permalink-Lookup
create index if not exists {table}_phase_idx  on {table} (phase);
create index if not exists {table}_nuts1_idx  on {table} (nuts1);
create index if not exists {table}_nuts_idx   on {table} (nuts_full);
create index if not exists {table}_natur_idx  on {table} (natur_kat);
create index if not exists {table}_band_idx   on {table} (volumen_band);
-- Row Level Security: Frontend liest nur; aktivieren + Read-Policy je nach Auth-Setup.
alter table {table} enable row level security;
"""


# Textfelder mit HTML-Entities aus dem TED-XML (&amp;, &#92;n, &quot; …) → Klartext.
_TEXT_COLS = {"titel", "buyer", "buyer_town", "cpv_label", "region", "incumbent_name"}
_WS = re.compile(r"\s+")


def _clean_text(s: str) -> str:
    s = html.unescape(s)
    s = s.replace("\\n", " ").replace("\\t", " ")  # literale \n aus dem Quell-Feed
    return _WS.sub(" ", s).strip()


def rows_from_parquet():
    con = duckdb.connect()
    cols = [c[0] for c in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{EXPORT}')").fetchall()]
    for rec in con.execute(f"SELECT * FROM read_parquet('{EXPORT}')").fetchall():
        d = dict(zip(cols, rec))
        # NaN/inf → None; numpy-Typen → Python (json-serialisierbar); Text entschärfen
        clean = {}
        for k, v in d.items():
            if v is None:
                clean[k] = None
            elif isinstance(v, float) and (v != v or v in (float("inf"), float("-inf"))):
                clean[k] = None
            elif hasattr(v, "item"):
                clean[k] = v.item()
            elif k in _TEXT_COLS and isinstance(v, str):
                clean[k] = _clean_text(v)
            else:
                clean[k] = v
        yield clean


def push(url, key, table, batch=500):
    import urllib.request

    endpoint = f"{url.rstrip('/')}/rest/v1/{table}?on_conflict=lead_id"
    headers = {
        "apikey": key, "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    buf, total = [], 0

    def flush():
        nonlocal total
        if not buf:
            return
        body = json.dumps(buf).encode()
        req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            if resp.status not in (200, 201, 204):
                raise RuntimeError(f"HTTP {resp.status}: {resp.read()[:300]}")
        total += len(buf)
        print(f"  … {total:,} Zeilen upserted", flush=True)
        buf.clear()

    for rec in rows_from_parquet():
        buf.append(rec)
        if len(buf) >= batch:
            flush()
    flush()
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default="gov_leads")
    ap.add_argument("--dry-run", action="store_true", help="nur DDL + NDJSON, kein Push")
    args = ap.parse_args()

    if not os.path.exists(EXPORT):
        print(f"{EXPORT} fehlt — erst `python -m govisor.cli gold` (baut lead_export).")
        return 1

    ddl_path = ROOT / "docs" / f"supabase_{args.table}.sql"
    ddl_path.write_text(DDL.format(table=args.table))
    print(f"DDL geschrieben: {ddl_path}  → einmalig im Supabase-Dashboard ausführen.")

    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")
    if args.dry_run or not (url and key):
        nd = ROOT / "data" / "export" / f"{args.table}.ndjson"
        nd.parent.mkdir(parents=True, exist_ok=True)
        n = 0
        with nd.open("w") as fh:
            for rec in rows_from_parquet():
                fh.write(json.dumps(rec, default=str) + "\n"); n += 1
        print(f"NDJSON-Export ({n:,} Zeilen): {nd}")
        if not (url and key):
            print("Kein SUPABASE_URL / SUPABASE_SERVICE_KEY gesetzt → kein Push.\n"
                  "Setze beide und ruf ohne --dry-run erneut auf, um zu upserten.")
        return 0

    print(f"Upsert nach {url} · Tabelle {args.table} …")
    t = time.time()
    n = push(url, key, args.table)
    print(f"FERTIG: {n:,} Zeilen in {time.time()-t:.0f}s upserted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
