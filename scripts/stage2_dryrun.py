"""Stufe-2-Trockenlauf: Fuzzy-HR-Matching messen, NICHTS schreiben.

Baut entity_of wie ein echter Rebuild (mit Fuzzy-Lookup + Stufe-1-Konsolidierung),
schreibt aber kein Parquet. Meldet die projizierte Methoden-Verteilung, den Zugewinn
durch Fuzzy und eine Präzisions-Stichprobe zum Nachsehen.
"""
from __future__ import annotations
import time, duckdb
from govisor import gold, locales
from govisor.config import Config
from govisor.gold import Method, resolve_supplier

C = "DE"
cfg = Config(countries=(C,), data_dir="data")
locales.use(C)


def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


log("HR-Index laden (fuzzy-fähig) ...")
hr = gold.build_hr_index()
log(f"  {len(hr):,} Firmen, {len(hr._by_plz):,} PLZ-Blöcke")

con = duckdb.connect()
parties = con.execute(f"""
    SELECT name, national_id, postal_code
    FROM '{cfg.silver_table_glob("notice_parties", C)}'
    WHERE name IS NOT NULL
""").fetchall()
log(f"Parteien: {len(parties):,}")

entity_of, plz_of = {}, {}
fuzzy_samples = []            # (ted_name, plz, hr_name, hr_nr)
fuzzy_party_hits = 0
fuzzy_from_nameonly = 0      # hätte ohne Fuzzy nur-Name ergeben (kein echtes national_id)
for i, (name, nid, plz) in enumerate(parties):
    r = resolve_supplier(name, national_id=nid, postal_code=plz, hr_lookup=hr.get)
    entity_of.setdefault(r.entity_id, r)
    if plz and plz.strip():
        plz_of.setdefault(r.entity_id, set()).add(plz.strip())
    if r.method == Method.HR_FUZZY_PLZ:
        fuzzy_party_hits += 1
        had_real_id = bool((nid or "").strip()) and not gold._RE_UUID_ID.match((nid or "").strip())
        if not had_real_id:
            fuzzy_from_nameonly += 1
        if len(fuzzy_samples) < 40 and (i % 7 == 0):
            fuzzy_samples.append((name, plz, r.canonical_name, r.national_id))

merge_map, flagged = gold._consolidate_by_national_id(entity_of, plz_of)
for old_id, new_id in merge_map.items():
    entity_of.pop(old_id, None)

# projizierte Methoden-Verteilung
from collections import Counter
meth = Counter(e.method for e in entity_of.values())
conf_sum = sum(e.confidence for e in entity_of.values())
withid = sum(1 for e in entity_of.values() if e.national_id)
tot = len(entity_of)

print("\n=== PROJIZIERT nach Stufe 2 (Fuzzy + Stufe-1-Konsolidierung) ===", flush=True)
for m, n in meth.most_common():
    print(f"  {m:26s} {n:>8,}", flush=True)
print(f"  GESAMT {tot:>8,}  national_id-Quote {100*withid/tot:.1f}%  Ø-conf {conf_sum/tot:.3f}", flush=True)
print(f"\nFuzzy-Treffer (Parteien): {fuzzy_party_hits:,}", flush=True)
print(f"  davon vorher nur-Name (echter Zugewinn): {fuzzy_from_nameonly:,}", flush=True)
print(f"  distinkte Fuzzy-Entitäten: {meth.get(Method.HR_FUZZY_PLZ,0):,}", flush=True)

print("\n=== PRÄZISIONS-STICHPROBE (TED-Name @ PLZ  →  HR-Name [HRB]) ===", flush=True)
for ted, plz, hrn, nr in fuzzy_samples:
    print(f"  '{(ted or '')[:42]:42s}' @{plz}  →  '{(hrn or '')[:42]:42s}' [{nr}]", flush=True)
log("DRYRUN_DONE")
