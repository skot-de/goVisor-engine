#!/usr/bin/env python3
"""Outreach-Landing-Generator (govisor-token-landing.html, Screen 1) → web/data/outreach.json

Je Zielfirma eine personalisierte, token-adressierte Auswertung: der Befund (S2-Auslauf-Headline),
KPIs, die laufenden Verträge (öffentlich) und der Hauptwettbewerber (gegatet). Vorberechnet und
statisch abgelegt → die Landing `/t/<token>` ist serverless-fähig und öffentlich (kein Python im Deploy).

Aufruf:
  python3 scripts/export_outreach.py --name Klostermann [--ort Hamm]   # Ziel(e) per Name/Ort/PLZ
  python3 scripts/export_outreach.py --id solo:hr:R2404_HRB6313
Token = sha1(identity_id)[:10] (deterministisch, unraerbar genug; Sven steuert, wer den Link bekommt).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import zielliste as Z  # noqa: E402

G = str(ROOT / "data/gold/DE")
SN = str(ROOT / "data/silver/DE/notices/*/*.parquet")
OUT = ROOT / "web" / "data" / "outreach.json"
MARKT_SWITCH = 28  # marktübliche Wechselquote (gemessen)


def token_of(identity_id):
    return hashlib.sha1(identity_id.encode()).hexdigest()[:10]


def eur(v):
    if v is None:
        return None
    v = float(v)
    if v >= 1e6:
        return f"{v/1e6:.1f}".replace(".", ",") + " Mio €"
    return f"{int(round(v)):,}".replace(",", ".") + " €"


def target_ids(con, args):
    if args.id:
        return [args.id]
    Z.build_population(con, adhoc={"name": args.name, "plz": args.plz, "ort": args.ort})
    return [r[0] for r in con.execute("SELECT identity_id FROM pop").fetchall()]


def contracts_for(con, identity_id, now, limit=6):
    LE = f"read_parquet('{G}/lead_export.parquet')"
    rows = con.execute(f"""
      SELECT title, buyer_name, value_eur, value_source, contract_end, months_to_expiry
      FROM {LE} WHERE incumbent_group_id=? AND months_to_expiry BETWEEN 0 AND 24
      ORDER BY months_to_expiry LIMIT {limit}""", [identity_id]).fetchall()
    return [{"titel": r[0], "buyer": r[1], "vol": eur(r[2]),
             "geschaetzt": r[3] != "actual", "ende": r[4].strftime("%m/%Y") if r[4] and hasattr(r[4], "strftime") else None,
             "soon": (r[5] is not None and r[5] <= 18)} for r in rows]


def hauptwettbewerber(con, identity_id, now):
    """Firma, die diese Identität am häufigsten verdrängt hat (head_to_head); sonst None."""
    EI = f"read_parquet('{G}/entity_identity.parquet')"
    HH = f"read_parquet('{G}/head_to_head.parquet')"
    EN = f"read_parquet('{G}/entities.parquet')"
    CS = f"read_parquet('{G}/contractor_stats.parquet')"
    row = con.execute(f"""
      WITH mine AS (SELECT entity_id FROM {EI} WHERE identity_id=?)
      SELECT wi.identity_id, sum(h.displacements) disp
      FROM {HH} h
      JOIN {EI} wi ON wi.entity_id = h.winner_entity
      WHERE h.loser_entity IN (SELECT entity_id FROM mine)
        AND wi.identity_id <> ?
      GROUP BY 1 ORDER BY 2 DESC LIMIT 1""", [identity_id, identity_id]).fetchone()
    if row:
        wid = row[0]
    else:
        # Fallback: Top-Anbieter im dominanten CPV-Feld der Firma (ihr echter Wettbewerber)
        dom = con.execute(f"""SELECT cs.cpv_class FROM {CS} cs JOIN {EI} ei ON ei.entity_id=cs.entity_id
          WHERE ei.identity_id=? GROUP BY 1 ORDER BY sum(cs.total_wins) DESC LIMIT 1""", [identity_id]).fetchone()
        if not dom:
            return None
        fb = con.execute(f"""SELECT ei.identity_id FROM {CS} cs JOIN {EI} ei ON ei.entity_id=cs.entity_id
          WHERE cs.cpv_class=? AND ei.identity_id<>? GROUP BY 1 ORDER BY sum(cs.total_wins) DESC LIMIT 1""",
          [dom[0], identity_id]).fetchone()
        if not fb:
            return None
        wid = fb[0]
    name = con.execute(f"SELECT arg_max(e.canonical_name, e.confidence) FROM {EI} ei JOIN {EN} e ON e.entity_id=ei.entity_id WHERE ei.identity_id=?", [wid]).fetchone()[0]
    # Größe des Wettbewerbers + seine auslaufenden Verträge (gegatet)
    wins = con.execute(f"""SELECT count(DISTINCT p.notice_id)
      FROM read_parquet('{G}/party_entity.parquet') p JOIN {EI} ei ON ei.entity_id=p.entity_id
      WHERE p.role='winner' AND ei.identity_id=?""", [wid]).fetchone()[0]
    return {"name": Z.clean_name(name), "wins": int(wins or 0),
            "vertraege": contracts_for(con, wid, now, limit=4)}


def build_payload(con, identity_id, now):
    b = con.execute("SELECT firmenname, wins36, vol36, avg_val, sitz_nuts FROM base WHERE identity_id=?",
                    [identity_id]).fetchone()
    if not b:
        return None
    name = Z.clean_name(b[0])
    # Volumen = 36-Monats-Summe der plausiblen Werte (b[2]=vol36) — glaubwürdig; die All-Time-Summe
    # ist durch Framework-Nennwerte absurd inflationiert (Klostermann 4,1 Mrd vs. 41 Mio in 36M).
    vol36 = float(b[2]) if b[2] else None
    aus = con.execute(f"""SELECT count(*), sum(value_eur) FROM read_parquet('{G}/lead_export.parquet')
      WHERE incumbent_group_id=? AND months_to_expiry BETWEEN 0 AND 18""", [identity_id]).fetchone()
    vertraege = contracts_for(con, identity_id, now, limit=6)
    wett = hauptwettbewerber(con, identity_id, now)
    # Befund-Headline aus S2 (Auslauf)
    if aus[0]:
        em = eur(aus[1]) if aus[1] else f"{aus[0]}"
        headline = (f"{aus[0]} Ihrer Verträge über {em} laufen in den nächsten 18 Monaten aus."
                    if aus[1] else f"{aus[0]} Ihrer Verträge laufen in den nächsten 18 Monaten aus.")
    else:
        headline = f"{int(b[1] or 0)} Zuschläge in 36 Monaten — Ihr öffentliches Vergabeprofil auf einen Blick."
        em = None
    return {
        "id": identity_id, "name": name, "stand": str(now),
        "finding": {"headline": headline, "em": em},
        "kpi": {
            "wins36": int(b[1] or 0),
            "volSum": eur(vol36),
            "aus18N": int(aus[0] or 0), "aus18Vol": eur(aus[1]) if aus[1] else None,
        },
        "vertraege": vertraege,
        "wettbewerber": wett,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name"); ap.add_argument("--plz"); ap.add_argument("--ort"); ap.add_argument("--id")
    a = ap.parse_args()
    if not (a.name or a.plz or a.ort or a.id):
        print("Bitte --name/--plz/--ort oder --id angeben", file=sys.stderr); return 1

    con = duckdb.connect(); con.execute("SET threads=4")
    now = Z.build_population(con, adhoc={"name": None, "plz": None, "ort": None})  # base + eloc
    ids = target_ids(con, a)
    if a.id and not con.execute("SELECT 1 FROM base WHERE identity_id=?", [a.id]).fetchone():
        print("Firma nicht in belegten Zuschlägen", file=sys.stderr); return 1

    store = {}
    if OUT.exists():
        try:
            store = json.loads(OUT.read_text())
        except Exception:
            store = {}
    added = []
    for iid in ids:
        p = build_payload(con, iid, now)
        if not p:
            continue
        tok = token_of(iid)
        store[tok] = p
        added.append((tok, p["name"]))
    OUT.write_text(json.dumps(store, ensure_ascii=False))
    print(f"{len(added)} Landing(s) → {OUT} (gesamt {len(store)})")
    for tok, nm in added[:20]:
        print(f"  /t/{tok}   {nm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
