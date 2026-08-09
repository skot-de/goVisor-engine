#!/usr/bin/env python3
"""Feature #11 §9 — Aggregation der Ergebnismeldungen (DORMANT bis zur Kartellprüfung).

Rechnet aus user_outcomes anonyme Wettbewerbs-Aggregate JE VERGABESTELLE — aber nur unter den
kartellrechtlichen Leitplanken (§9.1):
  · nur ab 5 BEITRAGENDEN FIRMEN je Stelle (AC13), sonst kein Eintrag,
  · ohne Anbieterbezug, ohne Preise (AC14),
  · rückwärtsgewandt (entschiedene Verfahren).

⚠️ Läuft NUR mit AGGREGATE_ENABLED=1 und ist NICHT im Tageslauf verdrahtet. Vor dem ersten echten
Lauf ist die kartellrechtliche Prüfung (§9.1, offener Punkt) einzuholen. Ohne das Flag: sofortiger,
folgenloser Abbruch.

Aufruf:  AGGREGATE_ENABLED=1 python3 scripts/aggregate_outcomes.py
"""
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_FIRMS = 5   # §9 / AC13 — harte Untergrenze, eher erhöhen als senken

def _db():
    url = os.environ.get("SUPABASE_URL", "")
    m = re.match(r"https?://([a-z0-9]+)\.supabase\.co", url)
    if not m:
        return None
    pw_file = ROOT / ".secrets/supabase_db.txt"
    pw = os.environ.get("PGPASSWORD") or (pw_file.read_text().strip() if pw_file.exists() else "")
    return {"host": f"db.{m.group(1)}.supabase.co", "pw": pw} if pw else None


def _psql(db, sql):
    env = dict(os.environ, PGPASSWORD=db["pw"])
    cmd = ["psql", "-h", db["host"], "-p", "5432", "-U", "postgres", "-d", "postgres",
           "-v", "ON_ERROR_STOP=1", "-t", "-A", "-F", "\t", "-c", sql]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:300])
    return r.stdout


def norm_buyer(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9äöüß ]", " ", (name or "").lower())).strip()


def main() -> int:
    if os.environ.get("AGGREGATE_ENABLED") != "1":
        print("aggregate_outcomes: DORMANT — AGGREGATE_ENABLED≠1. Kein Lauf (kartellrechtliche Prüfung offen, §9.1).")
        return 0
    db = _db()
    if not db:
        print("aggregate_outcomes: keine DB-Creds — Abbruch."); return 0

    # Nur beworbene, entschiedene, plausible Meldungen (usable_for_aggregate).
    rows = _psql(db, "select user_id, buyer_name, result, rank, loss_reason from user_outcomes "
                     "where usable_for_aggregate = true and buyer_name is not null;")
    per = defaultdict(lambda: {"firms": set(), "part": 0, "ranks": Counter(), "loss": Counter(), "name": None})
    for line in rows.splitlines():
        if not line.strip():
            continue
        uid, buyer, result, rank, loss = (line.split("\t") + ["", "", "", "", ""])[:5]
        key = norm_buyer(buyer)
        if not key:
            continue
        e = per[key]
        e["firms"].add(uid); e["part"] += 1; e["name"] = e["name"] or buyer
        if rank and rank != "": e["ranks"][rank] += 1
        if loss and loss != "": e["loss"][loss] += 1

    kept = {k: v for k, v in per.items() if len(v["firms"]) >= MIN_FIRMS}   # §9 Mindestzahl
    if not kept:
        print(f"aggregate_outcomes: keine Stelle mit ≥{MIN_FIRMS} beitragenden Firmen — nichts geschrieben.")
        return 0

    vals = []
    for key, v in kept.items():
        vals.append("(" + ",".join([
            "'" + key.replace("'", "''") + "'",
            "'" + (v["name"] or "").replace("'", "''") + "'",
            str(len(v["firms"])), str(v["part"]),
            "'" + json.dumps(dict(v["ranks"])).replace("'", "''") + "'::jsonb",
            "'" + json.dumps(dict(v["loss"])).replace("'", "''") + "'::jsonb",
            "now()",
        ]) + ")")
    sql = ("insert into agg_buyer_outcomes (buyer_key, buyer_name, n_firms, n_participations, rank_dist, loss_reasons, computed_at) "
           f"values {','.join(vals)} on conflict (buyer_key) do update set "
           "buyer_name=excluded.buyer_name, n_firms=excluded.n_firms, n_participations=excluded.n_participations, "
           "rank_dist=excluded.rank_dist, loss_reasons=excluded.loss_reasons, computed_at=excluded.computed_at;")
    _psql(db, sql)
    print(f"aggregate_outcomes: {len(kept)} Stellen aggregiert (≥{MIN_FIRMS} Firmen).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
