"""Silber 2023–2026 neu bauen (eForms-Gewinner-Fix greift beim Re-Parse), dann
voller Gold-Rebuild via CLI, dann Verifikation der zurückgeholten Gewinner.
"""
import subprocess
import time

from govisor import silver, locales
from govisor.config import Config

cfg = Config(countries=("DE",), data_dir="data")
locales.use("DE")


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


log("SCHRITT 1 — Silber 2023–2026 neu (--force, eForms-Fix)")
months = [f"{y:04d}-{m:02d}" for y in range(2023, 2027) for m in range(1, 13)]
tot = 0
for key in months:
    n = silver.build_month(cfg, "DE", key, force=True)
    if n > 0:
        tot += n
log(f"  Silber-Rebuild fertig: {tot:,} Notices in 2023–2026")

log("SCHRITT 2 — voller Gold-Rebuild (python -m govisor.cli gold)")
r = subprocess.run(["python3", "-m", "govisor.cli", "gold"], capture_output=True, text=True)
print(r.stdout[-2000:], flush=True)
if r.returncode != 0:
    print("GOLD-FEHLER:", r.stderr[-1500:], flush=True)

log("SCHRITT 3 — Verifikation der zurückgeholten Gewinner")
import duckdb
c = duckdb.connect(); c.execute("SET threads=4")
N = "data/silver/DE/notices/*/*.parquet"; Q = "data/gold/DE/quality.parquet"
after = c.execute(f"SELECT count(*) FROM read_parquet('{N}',hive_partitioning=1) n "
                  f"JOIN read_parquet('{Q}') q ON q.notice_id=n.notice_id "
                  f"WHERE q.verfahren_status='unbekannt' AND n.schema_gen='eforms'").fetchone()[0]
print(f"NACHHER: eForms unbekannt: {after:,} (war 14.999 → {14999-after:+,} zurückgeholt)", flush=True)
# Bellersheim als Stichprobe: hat es jetzt einen Gewinner in party_entity?
b = c.execute("""SELECT e.canonical_name FROM read_parquet('data/gold/DE/party_entity.parquet') pe
  JOIN read_parquet('data/gold/DE/entities.parquet') e ON e.entity_id=pe.entity_id
  WHERE pe.notice_id='00444521_2024' AND pe.role='winner'""").fetchall()
print(f"Stichprobe 00444521_2024 Gewinner: {[x[0] for x in b]}", flush=True)
from govisor import verify
print("FK:", verify.gold_integrity(cfg, "DE") or "KEINE (sauber)", flush=True)
log("REBUILD_A2_DONE")
