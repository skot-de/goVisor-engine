#!/usr/bin/env python3
"""Referenzliste einer Firma — ihre gewonnenen Zuschlaege, je Vorgang eine Zeile.

Quelle sind die oeffentlichen TED-Zuschlaege der Identitaet (party_entity role=winner), mit
Titel, Auftraggeber, Jahr, Wert. Belegt, keine Selbstauskunft — genau das, was eine
Referenzliste in einem Angebot braucht.

⚠ ON-DEMAND, wie scripts/firma_profil.py: liest Gold/Silber (DuckDB) und gibt JSON auf stdout.
Laeuft lokal/auf dem Worker, NICHT auf Vercel-Serverless (dort braeuchte es einen Export wie
firma-profiles.json — bewusst nicht gebaut, bis das Volumen es rechtfertigt).

Aufruf:  python3 scripts/firma_referenzen.py --id <identity_id> [--limit N]
Ausgabe: {"identity_id": ..., "referenzen": [{titel, auftraggeber, jahr, wert, cpv, land, notice_id}], "gesamt": N}
"""
import argparse
import json
import pathlib
import sys

import duckdb

ROOT = pathlib.Path(__file__).resolve().parent.parent
G = str(ROOT / "data/gold/DE")


def _union(tabelle: str) -> str:
    weitere = sorted(str(x) for x in (ROOT / "data/gold").glob(f"*/{tabelle}.parquet")
                     if x.parent.name != "DE")
    lst = ", ".join(f"'{d}'" for d in [f"{G}/{tabelle}.parquet"] + weitere)
    return f"read_parquet([{lst}], union_by_name=true)"


def _silber_union(tabelle: str) -> str:
    muster = [str(ROOT / f"data/silver/{x.parent.name}/{tabelle}/*/*.parquet")
              for x in sorted((ROOT / "data/silver").glob(f"*/{tabelle}"))
              if list(x.glob("*/*.parquet"))]
    lst = ", ".join(f"'{m}'" for m in muster)
    return f"read_parquet([{lst}], union_by_name=true)"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="identity_id der Firma")
    ap.add_argument("--limit", type=int, default=500)
    a = ap.parse_args(argv)
    ident = a.id
    limit = max(1, min(2000, a.limit))

    try:
        con = duckdb.connect()
        EI, PE, EN, SN = _union("entity_identity"), _union("party_entity"), _union("entities"), _silber_union("notices")
        # Mitglieder (Schwester-Entities) der Identitaet
        con.execute(f"CREATE TEMP TABLE members AS SELECT entity_id FROM {EI} WHERE identity_id = ?", [ident])
        # Gewonnene Zuschlaege je Vorgang (eine Zeile), + ein Kaeufername je Notice
        con.execute(f"""CREATE TEMP TABLE w AS
          SELECT DISTINCT p.notice_id, n.title AS titel, n.country AS land,
                 substr(n.cpv_main, 1, 4) AS cpv,
                 year(coalesce(n.award_date, n.publication_date)) AS jahr,
                 CASE WHEN n.value_currency = 'EUR' THEN n.final_value END AS wert
          FROM {PE} p JOIN members m ON m.entity_id = p.entity_id
          JOIN {SN} n ON n.notice_id = p.notice_id
          WHERE p.role = 'winner'""")
        con.execute(f"""CREATE TEMP TABLE buyer AS
          SELECT pb.notice_id, min(en.canonical_name) AS auftraggeber
          FROM {PE} pb JOIN {EN} en ON en.entity_id = pb.entity_id
          WHERE pb.role = 'buyer' AND pb.notice_id IN (SELECT notice_id FROM w)
          GROUP BY 1""")
        rows = con.execute(f"""
          SELECT w.titel, b.auftraggeber, w.jahr, w.wert, w.cpv, w.land, w.notice_id
          FROM w LEFT JOIN buyer b ON b.notice_id = w.notice_id
          WHERE w.titel IS NOT NULL
          ORDER BY w.jahr DESC NULLS LAST, w.wert DESC NULLS LAST
          LIMIT {limit}""").fetchall()
        gesamt = con.execute("SELECT count(*) FROM w").fetchone()[0]
        ref = [{"titel": r[0], "auftraggeber": r[1], "jahr": r[2],
                "wert": float(r[3]) if r[3] is not None else None,
                "cpv": r[4], "land": r[5], "notice_id": r[6]} for r in rows]
        print(json.dumps({"identity_id": ident, "referenzen": ref, "gesamt": gesamt}, ensure_ascii=False))
        return 0
    except Exception as e:  # noqa: BLE001 — die Route macht daraus eine saubere Meldung
        print(json.dumps({"identity_id": ident, "referenzen": [], "fehler": str(e)[:200]}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
