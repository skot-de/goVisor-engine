"""Datenqualitaets-Uebersicht fuer das Admin-Portal (Bereich 2) — kompaktes JSON aus den
Gold-QA-Parquets. Nur LESEND, nur Aggregate; die Web-App hat kein DuckDB, deshalb hier.

    python3 scripts/qa_uebersicht.py --country DE
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="DE")
    a = ap.parse_args(argv)
    land = "".join(c for c in a.country.upper() if c.isalpha())[:3] or "DE"
    G = ROOT / "data" / "gold" / land
    if not G.is_dir():
        print(json.dumps({"country": land, "fehler": "kein Gold-Verzeichnis"})); return 0
    import duckdb
    con = duckdb.connect()
    rp = lambda n: f"read_parquet('{(G / (n + '.parquet')).as_posix()}')"
    da = lambda n: (G / (n + ".parquet")).exists()
    out: dict = {"country": land}

    if da("review_queue"):
        total = con.execute(f"select count(*) from {rp('review_queue')}").fetchone()[0]
        flags = con.execute(f"select flag,count(*) n from (select unnest(quality_flags) flag "
                            f"from {rp('review_queue')}) group by 1 order by 2 desc limit 8").fetchall()
        out["review_queue"] = {"total": total, "flags": [{"flag": f, "n": n} for f, n in flags]}

    if da("quality"):
        tot = con.execute(f"select count(*) from {rp('quality')}").fetchone()[0]
        mit = con.execute(f"select count(*) from {rp('quality')} where len(quality_flags)>0").fetchone()[0]
        flags = con.execute(f"select flag,count(*) n from (select unnest(quality_flags) flag "
                            f"from {rp('quality')}) group by 1 order by 2 desc limit 10").fetchall()
        out["quality"] = {"total": tot, "mit_flag": mit, "flags": [{"flag": f, "n": n} for f, n in flags]}

    if da("entity_merge_candidates"):
        out["merge_kandidaten"] = con.execute(f"select count(*) from {rp('entity_merge_candidates')}").fetchone()[0]
    if da("entity_merge_urteil"):
        urt = con.execute(f"select urteil,count(*) n from {rp('entity_merge_urteil')} group by 1 order by 2 desc").fetchall()
        out["merge_urteile"] = [{"urteil": u, "n": n} for u, n in urt]

    if da("notice_duplicates"):
        nd = con.execute(f"select count(*) from {rp('notice_duplicates')}").fetchone()[0]
        beleg = con.execute(f"select beleg,count(*) n from {rp('notice_duplicates')} group by 1 order by 2 desc limit 8").fetchall()
        out["notice_dubletten"] = {"total": nd, "beleg": [{"beleg": b, "n": n} for b, n in beleg]}
    if da("document_duplicates"):
        out["dok_dubletten"] = con.execute(f"select count(*) from {rp('document_duplicates')}").fetchone()[0]

    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
