"""Behebung Nacht-Ingest: 2008-05 nachladen, Silber 2004-2009 dedup-Rebuild,
Gold komplett neu, dann Post-Audit (Dubletten/Encoding) + FK-Integrität.

Bronze bleibt unangetastet; alles ist lokaler Recompute.
"""
from __future__ import annotations

import sys
import time
from datetime import date

import duckdb

from govisor import bulk, locales, silver, verify
from govisor.config import Config
from govisor.ingest import ingest_month, is_done

C = "DE"
cfg = Config(countries=(C,), data_dir="data")
locales.use(C)


def log(msg: str) -> None:
    print(f"[{date.today()} {time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---- Schritt 1: fehlenden Monat 2008-05 nachladen -------------------------
log("SCHRITT 1 — 2008-05 nachladen")
pkg = next(p for p in bulk.months((2008, 5), (2008, 5)))
if is_done(cfg, pkg):
    log("  2008-05 Bronze schon vorhanden — übersprungen")
else:
    try:
        stats = ingest_month(cfg, pkg, force=False)
        for country, s in sorted(stats.items()):
            log(f"  2008-05 {country}: {s.kept:,}/{s.scanned:,} behalten")
    except Exception as exc:
        log(f"  FEHLER 2008-05: {exc}")

# ---- Schritt 2: Silber 2004-2009 (+2008-05) dedup-Rebuild -----------------
log("SCHRITT 2 — Silber-Rebuild 2004-2009 (force, dedup)")
months = [f"{y:04d}-{m:02d}" for y in range(2004, 2010) for m in range(1, 13)]
total = 0
for key in months:
    n = silver.build_month(cfg, C, key, force=True)
    if n <= 0:
        log(f"  {key}: {n} (kein Bronze / leer)")
        continue
    total += n
    log(f"  {key}: {n:,} Notices")
log(f"  Silber-Rebuild fertig: {total:,} Notices in 2004-2009")

# ---- Schritt 3: Gold komplett neu -----------------------------------------
log("SCHRITT 3 — Gold komplett neu")
from govisor import gold  # noqa: E402
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

# ---- Schritt 4: Post-Audit ------------------------------------------------
log("SCHRITT 4 — Post-Audit")
con = duckdb.connect()
N = "data/silver/DE/notices/*/*.parquet"
print("\n=== Dubletten & Encoding nach Rebuild (2004-2010) ===", flush=True)
rows = con.execute(f"""
  SELECT year, count(*) n, count(DISTINCT notice_id) uid,
    count(*) FILTER (WHERE title LIKE '%'||chr(65533)||'%'
                      OR description LIKE '%'||chr(65533)||'%') repl
  FROM read_parquet('{N}', hive_partitioning=1)
  WHERE year BETWEEN 2004 AND 2010 GROUP BY year ORDER BY year
""").fetchall()
all_clean = True
for y, n, uid, repl in rows:
    dup = n - uid
    if dup or repl:
        all_clean = False
    print(f"  {y}: rows={n:>8,} uniq_id={uid:>8,} dups={dup:>6,} repl_char={repl:>6,}"
          + ("" if (dup == 0 and repl == 0) else "  <-- REST"), flush=True)

# Coverage-Lücke 2008-05
present = set(f"{yy:04d}-{mm:02d}" for (yy, mm) in con.execute(
    f"SELECT DISTINCT year, month FROM read_parquet('{N}', hive_partitioning=1)").fetchall())
print(f"\n2008-05 vorhanden: {'2008-05' in present}", flush=True)

# FK-Integrität
orphans = verify.gold_integrity(cfg, C)
print(f"Gold FK-Waisen: {orphans if orphans else 'KEINE (sauber)'}", flush=True)

print(f"\nERGEBNIS: {'100% SAUBER' if (all_clean and '2008-05' in present and not orphans) else 'REST-PROBLEME (siehe oben)'}", flush=True)
log("REPAIR_DONE")
