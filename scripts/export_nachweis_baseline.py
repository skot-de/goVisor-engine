#!/usr/bin/env python3
"""Ticket #23 Vergabestelle-Brücke: Korpus-Median der Nachweisdichte je Branche.

Über alle Vorgänge mit Volltext (data/docs/DE/doc_text.parquet) zählt `docsignals.nachweis_count`
die distinkten geforderten Nachweis-Arten + Formblätter; der Median je Branche ist das „üblich"
für den Ausschreibungscheck (§B.2): ein hochgeladener Vergabestellen-Entwurf wird dagegen
verglichen. Schreibt web/data/nachweis-median.json {branche: {median, p75, n}, _overall: …}.

Aufruf: python3 scripts/export_nachweis_baseline.py
"""
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor import docsignals  # noqa: E402

SRC = ROOT / "data" / "docs" / "DE" / "doc_text.parquet"
OUT = ROOT / "web" / "data" / "nachweis-median.json"


def _branche_map() -> dict:
    m = {}
    for f in (ROOT / "web" / "data").glob("leads-*.json"):
        br = f.stem.split("leads-")[1]
        for r in json.loads(f.read_text()):
            m[str(r.get("id"))] = br
    return m


def main() -> int:
    if not SRC.exists():
        print(f"FEHLT: {SRC} — erst index-docs laufen lassen."); return 1
    con = duckdb.connect()
    rows = con.execute(
        f"""SELECT notice_id, string_agg(text, '\n') AS full
            FROM read_parquet('{SRC.as_posix()}')
            WHERE status='ok' AND text IS NOT NULL AND length(text) > 200
            GROUP BY notice_id"""
    ).fetchall()
    br = _branche_map()
    per_br = defaultdict(list)
    allvals = []
    for nid, full in rows:
        c = docsignals.nachweis_count(full or "")
        per_br[br.get(nid, "?")].append(c)
        allvals.append(c)

    def summ(vals):
        vals = sorted(vals)
        return {"median": round(st.median(vals)), "p75": vals[int(0.75 * (len(vals) - 1))],
                "n": len(vals)}

    out = {b: summ(v) for b, v in per_br.items() if b != "?" and len(v) >= 5}
    out["_overall"] = summ(allvals)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print("Nachweisdichte-Median je Branche (distinkte Nachweis-Arten + Formblätter):")
    for b, d in sorted(out.items(), key=lambda kv: -(kv[1]["n"])):
        print(f"  {b:12} Median {d['median']:>2} · p75 {d['p75']:>2} · n={d['n']}")
    print(f"→ {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
