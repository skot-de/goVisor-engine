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
import datetime as dt
import html
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(ROOT)

import duckdb  # noqa: E402

# Registry der Frontend-Tabellen. Vorher war nur `gov_leads` fest verdrahtet und die
# Begleittabellen wurden von Hand gepusht — dabei driftet zwangslaeufig etwas.
# Wert: (Parquet, Konflikt-Schluessel fuer das Upsert = Primary Key).
TABLES = {
    "gov_leads":     ("data/gold/DE/lead_export.parquet", ("lead_id",)),
    "gov_lead_cpv":  ("data/gold/DE/lead_cpv.parquet",    ("lead_id", "cpv_code")),
    "gov_lead_lots": ("data/gold/DE/lead_lot.parquet",    ("lead_id", "lot_id")),
    # Zuschlagskriterien: kein natuerlicher Schluessel (ein Los kann zwei gleichnamige
    # Kriterien tragen) → `criterion_no` wird im Builder als laufende Nummer vergeben.
    "gov_lead_criteria": ("data/gold/DE/lead_criteria.parquet",
                          ("lead_id", "lot_id", "criterion_no")),
    "gov_lead_requirements": ("data/gold/DE/lead_requirement.parquet",
                              ("lead_id", "lot_id", "requirement_no")),
    "gov_lead_parties": ("data/gold/DE/lead_party.parquet",
                         ("lead_id", "party_role", "party_no")),
    # Feld-Inventar der Rohdaten — klein und rein informativ, aber die einzige Antwort
    # auf „welche Felder stecken eigentlich im XML?". Kein lead_id → kein Prune-Abgleich.
    "gov_bronze_inventory": ("data/gold/DE/bronze_inventory.parquet",
                             ("schema_gen", "path")),
}
# Tabellen ohne lead_id: der Verwaisten-Abgleich (`--prune`) greift dort nicht.
NO_LEAD_ID = {"gov_bronze_inventory"}
EXPORT = TABLES["gov_leads"][0]      # Rueckwaertskompatibler Default

# DDL wird AUS DEM PARQUET-SCHEMA abgeleitet — nicht hartcodiert. Vorher lief die
# handgepflegte Liste regelmaessig aus dem Ruder (fehlende Spalten fielen erst beim
# Import auf). Typ-Mapping DuckDB -> Postgres:
_PG_TYPE = {
    "VARCHAR": "text", "BIGINT": "bigint", "INTEGER": "integer", "HUGEINT": "numeric",
    "DOUBLE": "double precision", "FLOAT": "real", "BOOLEAN": "boolean",
    "DATE": "date", "TIMESTAMP": "timestamptz", "SMALLINT": "smallint",
}

# Spalten, die einen Index bekommen (die Explorer-Facetten + Permalink-Lookup).
_INDEXED = ["slug", "phase", "market_nuts3", "buyer_nuts1", "contract_nature",
            "value_band", "deadline_date", "incumbent_group_id",
            "has_detailed_description"]


def build_ddl(table: str, parquet: str, pk=("lead_id",)) -> str:
    if isinstance(pk, str):
        pk = (pk,)
    con = duckdb.connect()
    cols = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{parquet}')").fetchall()
    lines = []
    for name, dtype, *_ in cols:
        pg = _PG_TYPE.get(str(dtype).split("(")[0], "text")
        # NOT NULL auf den PK-Spalten: sonst kippt das Upsert erst zur Laufzeit.
        extra = " not null" if name in pk else (" unique" if name == "slug" else "")
        lines.append(f"  {name:<24} {pg}{extra},")
    lines.append(f"  updated_at               timestamptz default now(),")
    lines.append(f"  primary key ({', '.join(pk)})")
    ddl = [f"-- {table}: generiert aus {parquet} (nicht von Hand pflegen).",
           f"create table if not exists {table} (", "\n".join(lines), ");"]
    # MIGRATION: `create table if not exists` ist bei einer BESTEHENDEN Tabelle ein No-Op —
    # neue Spalten kaemen nie an (und der Upsert scheitert dann mit PGRST204). Deshalb
    # zusaetzlich je Spalte ein idempotentes ADD COLUMN. Damit ist dieselbe Datei sowohl
    # Erst-Anlage als auch Migration; mehrfaches Ausfuehren ist gefahrlos.
    ddl.append(f"-- Migration bestehender Tabellen (idempotent, neue Spalten nachziehen):")
    for name, dtype, *_ in cols:
        pg = _PG_TYPE.get(str(dtype).split("(")[0], "text")
        ddl.append(f"alter table {table} add column if not exists {name} {pg};")
    # …und derselbe Fall fuer den PRIMARY KEY: eine Tabelle, die frueher ad hoc (ohne PK)
    # angelegt wurde, behaelt ihn nie — das Upsert scheitert dann mit 42P10 „no unique or
    # exclusion constraint matching the ON CONFLICT specification". Genau so lag
    # `gov_lead_cpv` da. Der DO-Block legt den PK nur an, wenn noch keiner existiert;
    # einen *abweichenden* bestehenden PK fasst er bewusst nicht an (das waere ein
    # stiller Datenumbau und gehoert von Hand entschieden).
    ddl += [
        "do $$ begin",
        f"  if not exists (select 1 from pg_constraint",
        f"                  where conrelid = '{table}'::regclass and contype = 'p') then",
        f"    alter table {table} add primary key ({', '.join(pk)});",
        "  end if;",
        "end $$;",
    ]
    have = {c[0] for c in cols}
    for c in _INDEXED:
        # `slug` traegt bereits UNIQUE — das legt in Postgres selbst einen Index an. Ein
        # zweiter waere reine Platzverschwendung (gemessen 4,6 MB doppelt) und wird nie
        # benutzt, weil der Planner den Unique-Index nimmt.
        if c in have and not (c == "slug" and " unique" in "".join(lines)):
            ddl.append(f"create index if not exists {table}_{c}_idx on {table} ({c});")
    ddl.append(f"drop index if exists {table}_slug_idx;   -- Dublette zu {table}_slug_key")
    ddl += [
        "-- RLS: Registrierung schaltet Leads frei; Analysen liegen hinter der Paywall",
        "-- (die bekommen bewusst KEINE Policy und sind nur serverseitig lesbar).",
        f"alter table {table} enable row level security;",
        f"drop policy if exists {table}_read_authenticated on {table};",
        f"create policy {table}_read_authenticated on {table}",
        "  for select to authenticated using (true);",
        "-- PostgREST cached das Schema. Eine NEU angelegte Tabelle ist ueber die REST-API",
        "-- sonst nicht sichtbar (PGRST205: table not found in the schema cache),",
        "-- obwohl sie in Postgres laengst existiert. Kostet nichts, wenn nichts neu ist.",
        "notify pgrst, 'reload schema';",
    ]
    return "\n".join(ddl) + "\n"


# Textfelder mit HTML-Entities aus dem TED-XML (&amp;, &#92;n, &quot; …) → Klartext.
# ACHTUNG: die Namen sind die des ENGLISCHEN Export-Vertrags (frueher standen hier noch
# die deutschen — dadurch lief `title` ungereinigt durch).
_TEXT_COLS = {"title", "buyer_name", "buyer_town", "buyer_region_name",
              "market_region_name", "incumbent_name"}
_WS = re.compile(r"[ \t]*\n[ \t\n]*")     # Leerzeilen/Einrueckung um Umbrueche kappen
_SPACE = re.compile(r"[ \t]{2,}")


def _clean_text(s: str) -> str:
    s = html.unescape(s)
    s = s.replace("\\n", " ").replace("\\t", " ")  # literale \n aus dem Quell-Feed
    return re.sub(r"\s+", " ", s).strip()


def _clean_longtext(s: str) -> str:
    """Wie `_clean_text`, aber **Absaetze bleiben erhalten** — bei Beschreibungen mit
    1.000+ Zeichen ist die Struktur (Aufzaehlungen, Absaetze) Teil der Information."""
    s = html.unescape(s).replace("\\n", "\n").replace("\\t", " ")
    return _SPACE.sub(" ", _WS.sub("\n", s)).strip()


_LONGTEXT = {"description", "lot_description", "options_description",
             "renewal_description", "lot_title"}


def rows_from_parquet(parquet: str = None):
    parquet = parquet or EXPORT
    con = duckdb.connect()
    cols = [c[0] for c in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{parquet}')").fetchall()]
    for rec in con.execute(f"SELECT * FROM read_parquet('{parquet}')").fetchall():
        d = dict(zip(cols, rec))
        # NaN/inf → None; numpy-Typen → Python (json-serialisierbar); Text entschärfen
        clean = {}
        for k, v in d.items():
            if v is None:
                clean[k] = None
            elif isinstance(v, float) and (v != v or v in (float("inf"), float("-inf"))):
                clean[k] = None
            elif isinstance(v, (dt.date, dt.datetime)):
                clean[k] = v.isoformat()      # JSON kennt keine Date-Objekte
            elif hasattr(v, "item"):
                clean[k] = v.item()
            elif k in _LONGTEXT and isinstance(v, str):
                clean[k] = _clean_longtext(v)
            elif k in _TEXT_COLS and isinstance(v, str):
                clean[k] = _clean_text(v)
            else:
                clean[k] = v
        yield clean


def push(url, key, table, batch=500, parquet=None, pk=("lead_id",)):
    """Upsert via PostgREST. **curl statt urllib** — das python.org-Python auf dieser
    Maschine hat keine CA-Bundle-Anbindung (SSL: CERTIFICATE_VERIFY_FAILED)."""
    import subprocess
    import tempfile

    endpoint = f"{url.rstrip('/')}/rest/v1/{table}?on_conflict={','.join(pk)}"
    buf, total = [], 0

    def flush():
        nonlocal total
        if not buf:
            return
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(buf, fh)
            tmp = fh.name
        try:
            out = subprocess.run(
                ["curl", "-sS", "--max-time", "180", "-X", "POST", endpoint,
                 "-H", f"apikey: {key}", "-H", f"Authorization: Bearer {key}",
                 "-H", "Content-Type: application/json",
                 "-H", "Prefer: resolution=merge-duplicates,return=minimal",
                 "--data-binary", f"@{tmp}", "-w", "%{http_code}"],
                capture_output=True, text=True)
        finally:
            os.unlink(tmp)
        body = out.stdout.strip()
        code = body[-3:] if body[-3:].isdigit() else "???"
        # `000` heisst: curl kam gar nicht bis zu einer Antwort — hier die `--max-time 180`.
        # Der Ausstieg 28 ist curls Zeitgrenze; beide bedeuten dasselbe wie ein
        # Statement-Timeout, nur ohne Antworttext, in dem `57014` stehen koennte.
        zeitueberschreitung = code == "000" or out.returncode == 28
        if code not in ("200", "201", "204"):
            # STATEMENT-TIMEOUT IST KEIN FEHLER, SONDERN EINE MENGENFRAGE.
            #
            # Gemessen 2026-08-14: der Upsert schaffte 11.500 Zeilen, dann brach ein Stapel
            # mit `57014 canceling statement due to statement timeout` ab — und riss den
            # GESAMTEN Upload mit, obwohl 11.500 Zeilen schon drin waren. Der Grund ist
            # nicht ein kaputter Satz: je voller die Tabelle, desto teurer wird jedes
            # `ON CONFLICT` (Index-Pflege). Das Problem waechst also mit dem Bestand und
            # wird von allein wiederkommen.
            #
            # Antwort: denselben Stapel halbiert erneut schicken, bis er durchgeht oder zu
            # klein zum Halbieren ist. Ein Timeout heisst „zu viel auf einmal", nicht
            # „geht nicht" — und ein halber Stapel ist in aller Regel schnell genug.
            # DIESELBE URSACHE, ZWEI SYMPTOME — und bisher nur eines behandelt.
            #
            # Ist der Stapel zu gross, kann die Datenbank ihn abbrechen (`57014`, mit
            # Antworttext) ODER so lange brauchen, dass curl vorher aufgibt (`000`, ohne
            # Antworttext). Der Halbierungs-Zweig kannte nur den ersten Fall; der zweite
            # riss den ganzen Lauf ab — gemessen am 2026-08-15 UND 2026-08-16, beide Male
            # endete der Tageslauf „MIT Fehler beim Supabase-Upload".
            #
            # Ein Timeout heisst „zu viel auf einmal", nicht „geht nicht" — unabhaengig
            # davon, wer zuerst aufgibt.
            if ("57014" in body or zeitueberschreitung) and len(buf) > 1:
                haelfte = len(buf) // 2
                woher = "curl" if zeitueberschreitung else "Datenbank"
                print(f"  ⚠ Zeitgrenze ({woher}) bei {len(buf)} Zeilen — halbiert erneut", flush=True)
                rest, buf[:] = buf[haelfte:], buf[:haelfte]
                flush()
                buf.extend(rest)
                flush()
                return
            # Fehlermeldung von curl MITGEBEN. Vorher stand im Log nur „HTTP 000: 000" —
            # das sagt nicht, ob es die Zeitgrenze, ein Netzfehler oder ein Zertifikat war,
            # und genau diese Unterscheidung braucht man beim naechsten Mal.
            hinweis = (out.stderr or "").strip()[:200]
            raise RuntimeError(
                f"HTTP {code} (curl-Ausstieg {out.returncode}): {body[:200]}"
                + (f" | curl: {hinweis}" if hinweis else ""))
        total += len(buf)
        print(f"  … {total:,} Zeilen upserted", flush=True)
        buf.clear()

    for rec in rows_from_parquet(parquet):
        buf.append(rec)
        if len(buf) >= batch:
            flush()
    flush()
    return total


def stale_ids(url, key, table, parquet, pk_col="lead_id"):
    """IDs, die in Supabase stehen, im aktuellen Export aber **nicht mehr** vorkommen.

    Das Upsert ist additiv — es entfernt nichts. Leads, deren Angebotsfrist abgelaufen
    ist, fallen aus dem Export, blieben in der Tabelle aber stehen und wuerden im
    Frontend als offene Ausschreibung weiterleben. Deshalb einmal abgleichen.
    """
    import subprocess

    have = set()
    # PostgREST/Supabase deckelt eine Antwort bei **1.000 Zeilen** (`db-max-rows`), egal
    # was der Range-Header anfordert. Mit einer groesseren Schrittweite kaeme immer eine
    # „kurze" Seite zurueck, die Schleife braeche nach der ersten ab und der Abgleich
    # meldete faelschlich „keine verwaisten Zeilen" — genau so ist es einmal passiert.
    step, off, page = 1_000, 0, 0
    while True:
        out = subprocess.run(
            ["curl", "-sS", "--max-time", "120",
             f"{url.rstrip('/')}/rest/v1/{table}?select={pk_col}&order={pk_col}",
             "-H", f"apikey: {key}", "-H", f"Authorization: Bearer {key}",
             "-H", f"Range: {off}-{off+step-1}"], capture_output=True, text=True)
        chunk = json.loads(out.stdout or "[]")
        if not chunk:
            break
        have.update(r[pk_col] for r in chunk)
        off += len(chunk)
        page += 1
        if page % 25 == 0:
            print(f"  … {off:,} IDs gelesen", flush=True)
        if len(chunk) < step:
            break
    con = duckdb.connect()
    live = {r[0] for r in con.execute(
        f"SELECT DISTINCT {pk_col} FROM read_parquet('{parquet}')").fetchall()}
    return sorted(have - live)


def prune(url, key, table, ids, pk_col="lead_id", batch=200):
    import subprocess

    done = 0
    for i in range(0, len(ids), batch):
        chunk = ids[i:i + batch]
        lst = ",".join('"%s"' % s.replace('"', '') for s in chunk)
        out = subprocess.run(
            ["curl", "-sS", "--max-time", "120", "-X", "DELETE",
             f"{url.rstrip('/')}/rest/v1/{table}?{pk_col}=in.({lst})",
             "-H", f"apikey: {key}", "-H", f"Authorization: Bearer {key}",
             "-H", "Prefer: return=minimal", "-w", "%{http_code}"],
            capture_output=True, text=True)
        code = out.stdout.strip()[-3:]
        if code not in ("200", "204"):
            raise RuntimeError(f"DELETE HTTP {code}: {out.stdout[:300]}")
        done += len(chunk)
        print(f"  … {done:,}/{len(ids):,} entfernt", flush=True)
    return done


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default="all", choices=["all", *TABLES],
                    help="einzelne Tabelle oder 'all' (Default)")
    ap.add_argument("--dry-run", action="store_true", help="nur DDL + NDJSON, kein Push")
    ap.add_argument("--ddl-only", action="store_true",
                    help="NUR die Migrations-DDL schreiben (für psql-Apply im Tages-Runner) — kein NDJSON, kein Push")
    ap.add_argument("--prune", action="store_true",
                    help="nach dem Upsert Zeilen loeschen, die der Export nicht mehr "
                         "enthaelt (abgelaufene Fristen). Ohne den Schalter wird nur "
                         "gezaehlt und gemeldet — Loeschen ist nie stillschweigend.")
    ap.add_argument("--no-search-index", action="store_true",
                    help="den tsvector-Refresh nach dem Push ueberspringen")
    ap.add_argument("--prune-only", action="store_true",
                    help="nur abgleichen/loeschen, kein Upsert (spart den vollen Push, "
                         "wenn die Daten schon oben sind). Impliziert --prune.")
    args = ap.parse_args()

    todo = list(TABLES) if args.table == "all" else [args.table]
    missing = [t for t in todo if not os.path.exists(TABLES[t][0])]
    if missing:
        print(f"Parquet fehlt fuer {', '.join(missing)} — erst `python3 -m govisor.cli gold`.")
        return 1

    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")
    ddl_all = []
    for table in todo:
        parquet, pk = TABLES[table]
        ddl_all.append(build_ddl(table, parquet, pk))
    ddl_path = ROOT / "docs" / ("supabase_schema.sql" if args.table == "all"
                                else f"supabase_{args.table}.sql")
    ddl_path.write_text("\n\n".join(ddl_all))
    print(f"DDL geschrieben: {ddl_path}  → im Supabase-Dashboard ausführen "
          f"(idempotent, legt an UND migriert).")
    if args.ddl_only:
        return 0
    # PostgREST laedt sein Schema nach `NOTIFY pgrst` **asynchron** nach. Wer direkt
    # danach pusht, faengt sich PGRST204 („column not found in the schema cache"),
    # obwohl die Spalte laengst existiert. Zwei Sekunden reichen.
    if url and key and not args.dry_run:
        time.sleep(2)

    if args.dry_run or not (url and key):
        for table in todo:
            parquet, _ = TABLES[table]
            nd = ROOT / "data" / "export" / f"{table}.ndjson"
            nd.parent.mkdir(parents=True, exist_ok=True)
            n = 0
            with nd.open("w") as fh:
                for rec in rows_from_parquet(parquet):
                    fh.write(json.dumps(rec, default=str) + "\n"); n += 1
            print(f"NDJSON-Export {table} ({n:,} Zeilen): {nd}")
        if not (url and key):
            print("Kein SUPABASE_URL / SUPABASE_SERVICE_KEY gesetzt → kein Push.\n"
                  "Setze beide und ruf ohne --dry-run erneut auf, um zu upserten.")
        return 0

    if args.prune_only:
        args.prune = True
    for table in todo:
        parquet, pk = TABLES[table]
        if not args.prune_only:
            print(f"Upsert nach {url} · Tabelle {table} (PK {'+'.join(pk)}) …")
            t = time.time()
            n = push(url, key, table, parquet=parquet, pk=pk)
            print(f"  FERTIG: {n:,} Zeilen in {time.time()-t:.0f}s upserted.")
        else:
            print(f"Abgleich {table} (kein Upsert) …")
        # Abgleich gegen den Export — Kind-Tabellen haengen per lead_id am Lead.
        if table in NO_LEAD_ID:
            print("  Abgleich: uebersprungen (keine lead_id).")
            continue
        old = stale_ids(url, key, table, parquet, "lead_id")
        if not old:
            print("  Abgleich: keine verwaisten Zeilen.")
        elif args.prune:
            print(f"  Abgleich: {len(old):,} verwaiste lead_id → loesche …")
            prune(url, key, table, old, "lead_id")
        else:
            print(f"  Abgleich: {len(old):,} verwaiste lead_id (nicht mehr im Export) — "
                  f"bleiben stehen. Mit --prune entfernen.")

    # Das Suchdokument zieht Text aus gov_leads UND gov_lead_lots — es kann darum keine
    # GENERATED-Spalte sein und muss nach jedem Push neu gerechnet werden. Ohne diesen
    # Schritt sucht das Frontend still auf dem Stand des letzten Laufs.
    if not args.no_search_index and "gov_leads" in todo:
        print("Suchindex aktualisieren (tsvector + GIN) …")
        try:
            import build_search_index as bsi
            t = time.time()
            bsi.psql(bsi.db_url(), bsi.REFRESH_SQL)
            print(f"  fertig in {time.time()-t:.0f}s")
        except SystemExit as exc:
            print(f"  uebersprungen: {exc}\n"
                  f"  → separat nachziehen: python3 scripts/build_search_index.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
