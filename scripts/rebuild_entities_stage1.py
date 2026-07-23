"""Stufe-1-Entity-Härtung: Gold neu bauen (mit PLZ-belegter Konsolidierung),
dann Entity-Metriken vorher/nachher + FK-Integrität messen.
"""
from __future__ import annotations
import time
import duckdb
from govisor import gold, locales, verify
from govisor.config import Config

C = "DE"
cfg = Config(countries=(C,), data_dir="data")
locales.use(C)
EN = f"data/gold/DE/entities.parquet"


def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def metrics(tag):
    con = duckdb.connect()
    rows = con.execute(f"""SELECT method, count(*) n, avg(confidence) c
        FROM read_parquet('{EN}') GROUP BY 1 ORDER BY n DESC""").fetchall()
    tot = sum(n for _, n, _ in rows)
    withid = con.execute(f"SELECT count(*) FROM read_parquet('{EN}') WHERE national_id IS NOT NULL AND national_id<>''").fetchone()[0]
    avgc = con.execute(f"SELECT avg(confidence) FROM read_parquet('{EN}')").fetchone()[0]
    con.close()
    print(f"\n=== Entity-Metriken [{tag}] ===", flush=True)
    for m, n, c in rows:
        print(f"  {m:22s} {n:>8,}  Ø-conf {c:.2f}", flush=True)
    print(f"  GESAMT {tot:>8,}  national_id-Quote {100*withid/tot:.1f}%  Ø-conf {avgc:.3f}", flush=True)
    return tot, withid, avgc


log("VORHER-Snapshot")
b_tot, b_id, b_conf = metrics("VORHER")

log("Gold-Rebuild (mit Stufe-1-Konsolidierung) ...")
print("procedures  :", f"{gold.build_procedures(cfg, C):,}", flush=True)
print("dim_cpv     :", gold.build_dim_cpv(cfg, C), flush=True)
print("dim_deflator:", gold.build_dim_deflator(cfg, C), flush=True)
log("HR-Index laden ...")
hr = gold.build_hr_index()
log(f"  {len(hr):,} Firmen")
e, l = gold.build_entities(cfg, C, hr_index=hr)
print(f"entities    : {e:,} Entitäten, {l:,} Verknüpfungen", flush=True)
del hr
tg, added = gold.seed_groups(cfg, C)
g, gl = gold.build_entity_groups(cfg, C)
print(f"gruppen     : {g:,} Gruppen, {gl:,} Zuordnungen", flush=True)
print("quality     :", f"{gold.build_quality(cfg, C):,}", flush=True)
nq, byflag = gold.build_review_queue(cfg, C)
print(f"review-queue: {nq:,}", flush=True)
print("chains      :", f"{gold.build_contract_chains(cfg, C):,}", flush=True)
ns, sk = gold.build_contract_successions(cfg, C)
print(f"successions : {ns:,}", flush=True)
print("leads       :", f"{gold.build_leads(cfg, C):,}", flush=True)
nm, nl = gold.build_displaceability(cfg, C)
print(f"displaceab. : {nm} Zeilen, {nl:,} gescort", flush=True)

log("NACHHER-Snapshot")
a_tot, a_id, a_conf = metrics("NACHHER")

# candidates + FK
con = duckdb.connect()
cand = con.execute("SELECT reason, count(*) FROM read_parquet('data/gold/DE/entity_merge_candidates.parquet') GROUP BY 1 ORDER BY 2 DESC").fetchall()
con.close()
print(f"\n=== Merge-Kandidaten (geflaggt, NICHT gemerged) ===", flush=True)
for r, n in cand: print(f"  {r:20s} {n:,}", flush=True)

orphans = verify.gold_integrity(cfg, C)
print(f"\nGold FK-Waisen: {orphans if orphans else 'KEINE (sauber)'}", flush=True)
print(f"\n=== DELTA ===", flush=True)
print(f"  Entitäten:        {b_tot:,} -> {a_tot:,}  ({a_tot-b_tot:+,})", flush=True)
print(f"  national_id-Quote {100*b_id/b_tot:.1f}% -> {100*a_id/a_tot:.1f}%", flush=True)
print(f"  Ø-Konfidenz:      {b_conf:.3f} -> {a_conf:.3f}  ({a_conf-b_conf:+.3f})", flush=True)
log("STAGE1_DONE")
