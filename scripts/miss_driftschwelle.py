#!/usr/bin/env python3
"""Wie viel Drift entsteht allein durch Zufall? — Messung zur Schwelle MAX_DRIFT.

    python3 scripts/miss_driftschwelle.py

⚠ Liest `data/docs/DE/doc_text.parquet` und rechnet die Absatz-Anteile neu (rund 2 min).
Schreibt NICHTS. Vor einem Lauf `scripts/laeuft_was.sh` fragen, wie ueberall.

Der Drift-Test vergleicht den Median der flach gelesenen Vorgaenge (1-7 Dateien) mit dem
der tief gelesenen (>=8) und verwirft ein Band, wenn das Verhaeltnis 1,5 reisst. Das ist
ein VERHAELTNIS, und ein Verhaeltnis ist skalenabhaengig: bei Medianen um 9 % bewegt ein
einziger Prozentpunkt es um 0,11, bei 44 % nur um 0,02.

Die ehrliche Gegenfrage ist deshalb nicht „ist 1,5 zu eng", sondern: welches Verhaeltnis
entsteht, wenn man ZUFAELLIG teilt statt nach Lesetiefe? Diese Nullverteilung sagt, ab
wann ein Wert ueberhaupt etwas bedeutet.
"""
import random, statistics, sys, duckdb
from pathlib import Path
sys.path.insert(0, ".")
import importlib.util
spec = importlib.util.spec_from_file_location("es", "scripts/export_standardtext.py")
es = importlib.util.module_from_spec(spec); spec.loader.exec_module(es)

ROOT = Path(".").resolve()
RUNDEN = 400
random.seed(20260918)

def drift(a, b):
    ma, mb = statistics.median(a), statistics.median(b)
    return max(ma, mb) / max(min(ma, mb), 1e-9), ma, mb

con = duckdb.connect()
for land in es._laender():
    T = f"read_parquet('{(ROOT/'data'/'docs'/land/'doc_text.parquet').as_posix()}')"
    A = ROOT/"data"/"gold"/land/"doc_analysis.parquet"
    anteil = es._anteile(con, T)
    if not anteil or land != "DE":
        continue
    umfang = dict(con.execute(f"select notice_id, sum(n_chars) from {T} where status='ok' group by 1").fetchall())
    tiefe = dict(con.execute(f"select notice_id, n_parsed_files from read_parquet('{A.as_posix()}')").fetchall()) if A.exists() else {}
    gruppen = {}
    for nid, v in anteil.items():
        b = es._band(int(umfang.get(nid) or 0))
        if b: gruppen.setdefault(b, []).append((v, tiefe.get(nid) or 0))

    print(f"\n{'Band':<8} {'n':>6} {'flach':>6} {'tief':>6} {'Drift':>6} {'Δ Pkt':>6} "
          f"{'Zufall p50':>11} {'Zufall p95':>11} {'Urteil':>22}")
    print("  " + "-" * 92)
    for b in ("klein", "mittel", "gross"):
        werte = gruppen.get(b, [])
        flach = [v for v, t in werte if 1 <= t <= es.FLACH]
        tief  = [v for v, t in werte if t >= es.TIEF]
        if len(flach) < es.MIND_BAND or len(tief) < es.MIND_BAND:
            print(f"  {b:<8} {len(werte):>6}  Driftpruefung zu duenn ({len(flach)}/{len(tief)})")
            continue
        d, mf, mt = drift(flach, tief)
        # ── Nullverteilung: DIESELBEN Zahlen, aber zufaellig geteilt statt nach Tiefe.
        #    Gleiche Gruppengroessen, damit die Streuung vergleichbar bleibt.
        alle = flach + tief
        nf = len(flach)
        null = []
        for _ in range(RUNDEN):
            random.shuffle(alle)
            null.append(drift(alle[:nf], alle[nf:])[0])
        null.sort()
        p50, p95 = null[len(null)//2], null[int(len(null)*0.95)]
        urteil = ("Signal" if d > p95 else "nicht von Zufall trennbar")
        print(f"  {b:<8} {len(werte):>6} {mf*100:>5.1f}% {mt*100:>5.1f}% {d:>6.2f} "
              f"{(mt-mf)*100:>+6.1f} {p50:>11.2f} {p95:>11.2f} {urteil:>22}")
