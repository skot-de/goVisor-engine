#!/usr/bin/env python3
"""Interne Firmen-Suche (Vertrieb) → JSON. Backend der internen Web-Seite /intern.

Zwei Modi (nutzt die Zielliste-Logik aus scripts/zielliste.py wieder):
  --search  --plz/--ort/--name  → Trefferliste mit Sitz + Schmerz-Signalen (S1/S2) + Kontakt
  --detail  <identity_id>        → auslaufende Verträge + jüngste Verluste + Kontakt (Ansprache-Details)

NUR intern (enthält Kontaktdaten) — die Route blockiert den Zugriff in Production.
"""
import argparse
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import zielliste as Z  # noqa: E402

G = str(ROOT / "data/gold/DE")
SN = str(ROOT / "data/silver/DE/notices/*/*.parquet")


def _con():
    con = duckdb.connect(); con.execute("SET threads=4")
    return con


def search(plz=None, ort=None, name=None):
    if not (plz or ort or name):
        return {"error": "Bitte PLZ, Ort oder Name angeben"}
    con = _con()
    now = Z.build_population(con, adhoc={"plz": plz, "ort": ort, "name": name})
    Z.compute_signals(con, now)
    rows = con.execute("""
      SELECT identity_id, firmenname, sitz_plz, sitz_ort, sitz_nuts, wins36, avg_val, vol36,
             verlorene_12m, verlust_vol, letzter_verlust, auslauf_n, auslauf_vol,
             naechstes_auslaufdatum, dominant_signal, email, phone
      FROM ranked ORDER BY (coalesce(verlust_vol,0)+coalesce(auslauf_vol,0)) DESC, wins36 DESC
      LIMIT 100""").fetchall()
    firmen = [{
        "id": r[0], "name": Z.clean_name(r[1]), "plz": r[2], "ort": r[3], "nuts": r[4],
        "wins36": int(r[5] or 0), "avgWert": float(r[6]) if r[6] else None,
        "vol36": float(r[7]) if r[7] else None,
        "s1": {"n": int(r[8] or 0), "vol": float(r[9]) if r[9] else None, "letzter": str(r[10]) if r[10] else None},
        "s2": {"n": int(r[11] or 0), "vol": float(r[12]) if r[12] else None, "naechstes": str(r[13]) if r[13] else None},
        "dominant": r[14], "email": r[15], "phone": r[16],
    } for r in rows]
    return {"stichtag": str(now), "n": len(firmen), "firmen": firmen}


def detail(identity_id):
    con = _con()
    now = Z.build_population(con, adhoc={"name": None, "plz": None, "ort": None})  # baut base/eloc + Signal-Quellen
    # base enthält alle belegten Identitäten (kein Filter) → identity muss darin sein
    prof = con.execute("SELECT firmenname, sitz_plz, sitz_ort, email, phone, wins36 FROM base WHERE identity_id=?",
                       [identity_id]).fetchone()
    if not prof:
        return {"error": "Firma nicht gefunden (keine belegten Zuschläge)", "id": identity_id}
    LE = f"read_parquet('{G}/lead_export.parquet')"
    # Auslaufende Verträge (Amtsinhaber) — der konkrete Gesprächsaufhänger
    exp = con.execute(f"""
      SELECT title, buyer_name, value_eur, contract_end, months_to_expiry, value_source
      FROM {LE} WHERE incumbent_group_id=? AND months_to_expiry BETWEEN 0 AND 24
      ORDER BY months_to_expiry LIMIT 25""", [identity_id]).fetchall()
    # Jüngste Verluste (aus den in compute_signals gebauten losses — hier direkt neu, mit Käufer)
    PE = f"read_parquet('{G}/party_entity.parquet')"
    EI = f"read_parquet('{G}/entity_identity.parquet')"
    EN = f"read_parquet('{G}/entities.parquet')"
    SE = f"read_parquet('{G}/succession_events.parquet')"
    QU = f"read_parquet('{G}/quality.parquet')"
    losses = con.execute(f"""
      WITH mine AS (SELECT entity_id FROM {EI} WHERE identity_id=?)
      SELECT n.title, coalesce(q.final_value_clean, n.final_value) AS val, n.award_date,
             (SELECT arg_max(e.canonical_name, e.confidence)
              FROM {PE} pw JOIN {EN} e ON e.entity_id=pw.entity_id
              WHERE pw.notice_id=se.successor AND pw.role='winner') AS gewinner
      FROM {SE} se
      JOIN {PE} pp ON pp.notice_id=se.predecessor AND pp.role='winner' AND pp.entity_id IN (SELECT entity_id FROM mine)
      JOIN read_parquet('{SN}', hive_partitioning=1) n ON n.notice_id=se.successor
      LEFT JOIN {QU} q ON q.notice_id=se.successor
      WHERE se.displaced=TRUE AND n.award_date >= (DATE '{now}' - INTERVAL 24 MONTH)
        AND NOT EXISTS (SELECT 1 FROM {PE} ps WHERE ps.notice_id=se.successor AND ps.role='winner'
                        AND ps.entity_id IN (SELECT entity_id FROM mine))
      ORDER BY n.award_date DESC LIMIT 25""",
      [identity_id]).fetchall()
    return {
        "id": identity_id, "name": Z.clean_name(prof[0]), "plz": prof[1], "ort": prof[2],
        "email": prof[3], "phone": prof[4], "wins36": int(prof[5] or 0),
        "expiring": [{"titel": e[0], "buyer": e[1], "vol": float(e[2]) if e[2] else None,
                      "ende": e[3].strftime("%m/%Y") if e[3] and hasattr(e[3], "strftime") else None,
                      "mte": int(e[4]) if e[4] is not None else None,
                      "vsrc": e[5]} for e in exp],
        "losses": [{"titel": l[0], "vol": float(l[1]) if l[1] else None,
                    "datum": str(l[2]) if l[2] else None, "gewinner": Z.clean_name(l[3]) if l[3] else None}
                   for l in losses],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", action="store_true")
    ap.add_argument("--detail")
    ap.add_argument("--plz"); ap.add_argument("--ort"); ap.add_argument("--name")
    a = ap.parse_args()
    try:
        out = detail(a.detail) if a.detail else search(a.plz, a.ort, a.name)
    except Exception as e:  # noqa: BLE001
        out = {"error": str(e)[:300]}
    print(json.dumps(out, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
