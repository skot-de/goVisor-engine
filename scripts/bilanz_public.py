#!/usr/bin/env python3
"""Feature #28 §2 — öffentliche Bilanz-Grundlage je Identität (JSON auf stdout).

Die *sichtbaren* Gewinne (öffentliche Zuschläge) + das über die Jahre BERECHNETE
Auftragsvolumen (AC6: berechnet, nicht abgefragt) + die Menge der Vergabestellen, bei denen
die Firma bereits gewonnen hat (für „bekannte vs. neue Stellen", §2.3). Die *echte* Quote
entsteht erst im Frontend durch Verschnitt mit den eigenen Meldungen (user_outcomes, #11).

Aufruf:  python3 scripts/bilanz_public.py <identity_id>
Ausgabe: eine JSON-Zeile (oder {"error": ...}).
"""
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
G = str(ROOT / "data/gold/DE")
SN = str(ROOT / "data/silver/DE/notices/*/*.parquet")


def build(identity_id: str) -> dict:
    con = duckdb.connect()
    con.execute("SET threads=4")
    EI = f"read_parquet('{G}/entity_identity.parquet')"
    EN = f"read_parquet('{G}/entities.parquet')"
    PE = f"read_parquet('{G}/party_entity.parquet')"

    members = con.execute(f"SELECT entity_id FROM {EI} WHERE identity_id = ?", [identity_id]).fetchall()
    if not members:
        return {"error": "unbekannte Identität", "id": identity_id}
    id_list = "(" + ",".join("'" + m[0].replace("'", "''") + "'" for m in members) + ")"

    con.execute(f"""CREATE TEMP TABLE w AS
      SELECT DISTINCT n.notice_id,
             year(coalesce(n.award_date, n.publication_date)) AS jahr,
             CASE WHEN n.value_currency='EUR' THEN n.final_value END AS val
      FROM {PE} p JOIN read_parquet('{SN}', hive_partitioning=1) n ON n.notice_id = p.notice_id
      WHERE p.role='winner' AND p.entity_id IN {id_list}""")
    total = con.execute("SELECT count(*) FROM w").fetchone()[0]
    if total == 0:
        return {"error": "keine Zuschläge belegt", "id": identity_id, "wins_total": 0, "wins_by_year": [], "buyers_worked": []}

    # Zuschläge + berechnetes EUR-Volumen je Jahr (nur plausible EUR-Werte, Rest bleibt ehrlich unbeziffert).
    by_year = con.execute("""
      SELECT jahr, count(*) AS wins, sum(val) AS vol, count(val) AS vol_n
      FROM w WHERE jahr IS NOT NULL GROUP BY 1 ORDER BY 1""").fetchall()
    wins_by_year = [{"jahr": int(j), "wins": int(w), "volumen": float(v) if v else None, "vol_belegt": int(vn)} for (j, w, v, vn) in by_year]

    # Vergabestellen, bei denen bereits gewonnen wurde (für §2.3 bekannte vs. neue Stellen).
    buyers = con.execute(f"""
      SELECT DISTINCT e.canonical_name
      FROM w JOIN {PE} p ON p.notice_id = w.notice_id AND p.role='buyer'
             JOIN {EN} e ON e.entity_id = p.entity_id
      WHERE e.canonical_name IS NOT NULL""").fetchall()
    buyers_worked = sorted({b[0] for b in buyers})

    return {
        "id": identity_id,
        "wins_total": int(total),
        "wins_by_year": wins_by_year,
        "buyers_worked": buyers_worked,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "identity_id fehlt"})); return 0
    try:
        print(json.dumps(build(sys.argv[1]), ensure_ascii=False, default=str))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": str(e)[:200]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
