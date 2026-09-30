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
    ap.add_argument("--merges", type=int, default=0,
                    help="statt der Uebersicht: bis zu N Merge-Urteile als Liste (fuers Verdrahten der Buttons)")
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

    # Merge-Liste fuer Bereich 2 (Buttons): die adjudizierten Urteile mit lesbaren Namen +
    # den Entity-Kennungen, die entity_merge_anwenden.py verwendet. Menschlich schon
    # entschiedene Paare (curated/<L>_entity_merge_entscheidung.csv) werden markiert. Sortiert:
    # was ein menschliches Urteil am ehesten braucht, zuerst (unsicher, dann verschieden).
    if a.merges:
        if not da("entity_merge_urteil"):
            print(json.dumps({"country": land, "merge_liste": [], "fehler": "kein entity_merge_urteil"})); return 0
        import csv as _csv
        entschieden: dict = {}
        ent_csv = ROOT / "curated" / f"{land}_entity_merge_entscheidung.csv"
        if ent_csv.exists():
            with ent_csv.open(newline="", encoding="utf-8") as fh:
                for r in _csv.DictReader(fh):
                    entschieden[(r.get("entity_a", ""), r.get("entity_b", ""))] = r.get("entscheidung", "")
        n = max(1, min(500, a.merges))
        rows = con.execute(f"""
            select entity_a, entity_b, name_a, name_b, urteil, einig, regel_grund, kandidaten
            from {rp('entity_merge_urteil')}
            order by case urteil when 'unsicher' then 0 when 'verschieden' then 1 else 2 end,
                     kandidaten desc
            limit {n}""").fetchall()
        liste = [{"entity_a": r[0], "entity_b": r[1], "name_a": r[2], "name_b": r[3],
                  "urteil": r[4], "einig": bool(r[5]), "regel_grund": r[6], "kandidaten": r[7],
                  "entschieden": entschieden.get((r[0], r[1]))} for r in rows]
        gesamt = con.execute(f"select count(*) from {rp('entity_merge_urteil')}").fetchone()[0]
        print(json.dumps({"country": land, "merge_liste": liste, "gesamt": gesamt,
                          "entschieden_n": len(entschieden)}, ensure_ascii=False))
        return 0

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
