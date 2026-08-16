#!/usr/bin/env python3
"""Feature #11 §7 — nächtliche Vorberechnung der Lücken-Wirkung (user_gap_effects).

Für jeden Nutzer mit Profil: wie viele seiner OFFENEN Leads sind von einer fehlenden Angabe
betroffen. Immer „betrifft N Leads" (§7.1), rückwärts gegen die aktuelle Lead-Schicht gerechnet.
Ersetzt die On-Demand-Rechnung im Frontend (die als Fallback bleibt).

Lücken (aus gemessenen Gold-Signalen):
  · buergschaft — Leads mit guarantee_required, Bürgschaftsrahmen nicht hinterlegt
  · maxAlleine  — Leads über 2 Mio €, Alleingrenze nicht hinterlegt

Liest user_profiles + schreibt user_gap_effects via psql (Creds wie daily_leads.sh: SUPABASE_URL
für die Ref, .secrets/supabase_db.txt fürs Passwort). Idempotent (Upsert je user_id,gap_key).

Aufruf:  python3 scripts/gap_effects.py
"""
import csv
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
LE = str(ROOT / "data/gold/DE/lead_export.parquet")
SCHWELLE_GROSS = 2_000_000

def _db():
    url = os.environ.get("SUPABASE_URL", "")
    m = re.match(r"https?://([a-z0-9]+)\.supabase\.co", url)
    if not m:
        return None
    ref = m.group(1)
    pw_file = ROOT / ".secrets/supabase_db.txt"
    pw = os.environ.get("PGPASSWORD") or (pw_file.read_text().strip() if pw_file.exists() else "")
    if not pw:
        return None
    return {"host": f"db.{ref}.supabase.co", "pw": pw}


def _psql_pfad() -> str:
    """`psql`-Pfad — NICHT der blosse Name.

    Am 2026-08-16 fielen zwei Tageslauf-Schritte mit `FileNotFoundError: 'psql'` aus. Das
    Programm ist installiert (`/opt/homebrew/bin`), aber der PATH, den launchd einem
    Agenten gibt, kennt Homebrew nicht. Aus dem Terminal lief alles — der Fehler tritt nur
    im geplanten Lauf auf, also dort, wo niemand zusieht.
    """
    import sys as _sys, pathlib as _pl
    _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))
    from govisor.psql import psql_oder_fehler
    return psql_oder_fehler()


def _psql(db, sql, capture=True):
    env = dict(os.environ, PGPASSWORD=db["pw"])
    cmd = [_psql_pfad(), "-h", db["host"], "-p", "5432", "-U", "postgres", "-d", "postgres",
           "-v", "ON_ERROR_STOP=1", "-t", "-A", "-F", ",", "-c", sql]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:300])
    return r.stdout


def load_profiles(db):
    """user_profiles → [{id, cpv_fields[], buergschaft_set, maxalleine_set}] (nur mit Schwerpunkten)."""
    out = _psql(db, "select id, coalesce(array_to_string(cpv_fields,'|'),''), "
                    "(profile->>'buergschaft'), (profile->>'maxAlleine') from user_profiles;")
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split(",")
        uid = parts[0]
        cpv = [c for c in (parts[1].split("|") if len(parts) > 1 and parts[1] else []) if c]
        buerg = parts[2] if len(parts) > 2 else ""
        maxa = parts[3] if len(parts) > 3 else ""
        if not cpv:
            continue   # ohne Schwerpunkte keine Relevanz-Rechnung (§14 Leerzustand)
        rows.append({"id": uid, "cpv": cpv,
                     "buerg_set": buerg not in ("", "null"),
                     "maxa_set": maxa not in ("", "null")})
    return rows


def affected(con, cpv4_list, extra_sql):
    quoted = ",".join("'" + c.replace("'", "''") + "'" for c in cpv4_list)
    return con.execute(
        f"SELECT count(*) FROM read_parquet('{LE}') "
        f"WHERE phase='open' AND substr(cpv_code,1,4) IN ({quoted}) AND {extra_sql}").fetchone()[0]


def main() -> int:
    db = _db()
    if not db:
        print("gap_effects: keine DB-Creds (SUPABASE_URL / supabase_db.txt) — übersprungen.")
        return 0
    try:
        profiles = load_profiles(db)
    except Exception as e:  # noqa: BLE001
        print(f"gap_effects: user_profiles nicht lesbar ({str(e)[:120]}) — übersprungen.")
        return 0
    if not profiles:
        print("gap_effects: keine Profile mit Schwerpunkten.")
        return 0

    con = duckdb.connect(); con.execute("SET threads=4")
    values = []
    for p in profiles:
        eff = {}
        if not p["buerg_set"]:
            eff["buergschaft"] = affected(con, p["cpv"], "guarantee_required = true")
        if not p["maxa_set"]:
            eff["maxAlleine"] = affected(con, p["cpv"], f"value_eur > {SCHWELLE_GROSS}")
        for k, n in eff.items():
            values.append((p["id"], k, int(n)))

    if not values:
        print("gap_effects: keine offenen Lücken.")
        return 0

    # Upsert in einem Rutsch.
    vals_sql = ",".join(
        f"('{uid}','{k}',{n},now())" for (uid, k, n) in values
        if re.match(r"^[0-9a-fA-F-]{36}$", uid))
    sql = ("insert into user_gap_effects (user_id, gap_key, affected_leads, computed_at) "
           f"values {vals_sql} "
           "on conflict (user_id, gap_key) do update set "
           "affected_leads = excluded.affected_leads, computed_at = excluded.computed_at;")
    _psql(db, sql, capture=False)
    print(f"gap_effects: {len(values)} Lücken-Wirkungen für {len(profiles)} Profile vorberechnet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
