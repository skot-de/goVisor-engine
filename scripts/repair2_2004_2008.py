"""Behebung Teil 2: 2004-Encoding (cp1252-Fallback) + 2008-05 (INTERNAL_OJS-Parser).

1) 2008-05 ingest (Parser erkennt jetzt OJS/'D-' → ~3.232 DE-Notices ins Bronze)
2) Silber-Rebuild 2004 (alle Monate, cp1252-Recovery) + 2008-05
3) Gold komplett neu
4) Post-Audit
"""
from __future__ import annotations

import time
from datetime import date

import duckdb

from govisor import bulk, gold, locales, silver, verify
from govisor.config import Config
from govisor.ingest import ingest_month

C = "DE"
cfg = Config(countries=(C,), data_dir="data")
locales.use(C)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---- 1: 2008-05 ingest ----------------------------------------------------
log("SCHRITT 1 — 2008-05 ingest (INTERNAL_OJS)")
pkg = next(bulk.months((2008, 5), (2008, 5)))
try:
    stats = ingest_month(cfg, pkg, force=True)   # force: Cache nutzen, Bronze neu schreiben
    for country, s in sorted(stats.items()):
        log(f"  2008-05 {country}: {s.kept:,}/{s.scanned:,} behalten | {s.queued} zur Prüfung")
except Exception as exc:
    log(f"  FEHLER 2008-05: {exc}")

# ---- 2: Silber 2004 (+2008-05) --------------------------------------------
log("SCHRITT 2 — Silber-Rebuild 2004 (cp1252) + 2008-05")
keys = [f"2004-{m:02d}" for m in range(1, 13)] + ["2008-05"]
for key in keys:
    n = silver.build_month(cfg, C, key, force=True)
    log(f"  {key}: {n:,} Notices" if n > 0 else f"  {key}: {n}")

# ---- 3: Gold komplett neu -------------------------------------------------
log("SCHRITT 3 — Gold komplett neu")
print("procedures  :", f"{gold.build_procedures(cfg, C):,}", flush=True)
print("dim_cpv     :", gold.build_dim_cpv(cfg, C), flush=True)
print("dim_deflator:", gold.build_dim_deflator(cfg, C), flush=True)
log("HR-Index laden ...")
hr = gold.build_hr_index()
log(f"  {len(hr):,} Firmen")
e, l = gold.build_entities(cfg, C, hr_index=hr)
print(f"entities    : {e:,} Entitäten, {l:,} Verknüpfungen", flush=True)
del hr
pe_orphans = [n for lbl, n in verify.gold_integrity(cfg, C) if lbl.startswith("party_entity")]
if pe_orphans:
    raise RuntimeError(f"party_entity Waisen: {pe_orphans[0]:,}")
tg, added = gold.seed_groups(cfg, C)
print(f"gruppen-seed: {tg:,} ({added:,} neu)", flush=True)
g, gl = gold.build_entity_groups(cfg, C)
print(f"gruppen     : {g:,} Gruppen, {gl:,} Zuordnungen", flush=True)
print("quality     :", f"{gold.build_quality(cfg, C):,} markiert", flush=True)
nq, byflag = gold.build_review_queue(cfg, C)
print(f"review-queue: {nq:,} ({byflag})", flush=True)
print("chains      :", f"{gold.build_contract_chains(cfg, C):,}", flush=True)
ns, sk = gold.build_contract_successions(cfg, C)
print(f"successions : {ns:,} ({sk} übersprungen)", flush=True)
print("leads       :", f"{gold.build_leads(cfg, C):,}", flush=True)
nm, nl = gold.build_displaceability(cfg, C)
print(f"displaceab. : {nm} Zeilen, {nl:,} gescort", flush=True)

# ---- 4: Post-Audit --------------------------------------------------------
log("SCHRITT 4 — Post-Audit")
con = duckdb.connect()
N = "data/silver/DE/notices/*/*.parquet"
print("\n=== Dubletten & Encoding (2004-2010) ===", flush=True)
clean = True
for y, n, uid, repl in con.execute(f"""
  SELECT year, count(*) n, count(DISTINCT notice_id) uid,
    count(*) FILTER (WHERE title LIKE '%'||chr(65533)||'%'
                      OR description LIKE '%'||chr(65533)||'%') repl
  FROM read_parquet('{N}', hive_partitioning=1)
  WHERE year BETWEEN 2004 AND 2010 GROUP BY year ORDER BY year""").fetchall():
    if (n - uid) or repl:
        clean = False
    print(f"  {y}: rows={n:>8,} uniq_id={uid:>8,} dups={n-uid:>5,} repl_char={repl:>6,}", flush=True)

# 2008-05 present + quality
row = con.execute(f"""
  SELECT count(*) n,
    count(*) FILTER (WHERE country='DE') de,
    count(*) FILTER (WHERE cpv_main IS NOT NULL) cpv,
    count(*) FILTER (WHERE title IS NOT NULL) title,
    count(*) FILTER (WHERE final_value IS NOT NULL) val
  FROM read_parquet('{N}', hive_partitioning=1) WHERE year=2008 AND month=5""").fetchone()
print(f"\n2008-05: rows={row[0]:,} DE={row[1]:,} mit_cpv={row[2]:,} mit_titel={row[3]:,} mit_wert={row[4]:,}", flush=True)

present = con.execute(f"""SELECT count(DISTINCT year||'-'||lpad(month::varchar,2,'0'))
  FROM read_parquet('{N}', hive_partitioning=1)""").fetchone()[0]
print(f"Monate gesamt in Silber: {present}", flush=True)

orphans = verify.gold_integrity(cfg, C)
print(f"Gold FK-Waisen: {orphans if orphans else 'KEINE (sauber)'}", flush=True)

ok = clean and row[1] > 2000 and not orphans
print(f"\nERGEBNIS: {'100% SAUBER' if ok else 'PRÜFEN (siehe oben)'}", flush=True)
log("REPAIR2_DONE")
