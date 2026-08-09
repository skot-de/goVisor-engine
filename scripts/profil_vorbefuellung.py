#!/usr/bin/env python3
"""Feature #27 §7.1 — Profil-Vorbefüllung aus der eigenen Zuschlagshistorie (JSON auf stdout).

Kein leeres Formular: aus `party_entity`/`entity_identity` (Gruppe = Identität) werden die
eigenen Zuschläge als Referenz-Kandidaten gezogen, dazu CPV-Schwerpunkte, Regionen und eine
Umsatz-Näherung. Alle Werte sind **abgeleitet** (§8) — sie zählen erst nach Bestätigung im
Frontend (§7.1/§15). Zusätzlich die Entity-Mitglieder für die Zuordnungs-Korrektur (§7.3).

Aufruf:  python3 scripts/profil_vorbefuellung.py <identity_id>
Ausgabe: eine JSON-Zeile (oder {"error": ...}).
"""
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
G = str(ROOT / "data/gold/DE")
SN = str(ROOT / "data/silver/DE/notices/*/*.parquet")

NUTS1 = {"DE1": "Baden-Württemberg", "DE2": "Bayern", "DE3": "Berlin", "DE4": "Brandenburg",
         "DE5": "Bremen", "DE6": "Hamburg", "DE7": "Hessen", "DE8": "Meck.-Vorpommern",
         "DE9": "Niedersachsen", "DEA": "Nordrhein-Westfalen", "DEB": "Rheinland-Pfalz",
         "DEC": "Saarland", "DED": "Sachsen", "DEE": "Sachsen-Anhalt", "DEF": "Schleswig-Holstein",
         "DEG": "Thüringen"}

MAX_REFS = 20


def build(identity_id: str) -> dict:
    con = duckdb.connect()
    con.execute("SET threads=4")
    EI = f"read_parquet('{G}/entity_identity.parquet')"
    EN = f"read_parquet('{G}/entities.parquet')"
    PE = f"read_parquet('{G}/party_entity.parquet')"
    CL = f"read_parquet('{G}/dim_cpv_label.parquet')"

    members = con.execute(
        f"""SELECT ei.entity_id, e.canonical_name, e.method, e.confidence
            FROM {EI} ei JOIN {EN} e ON e.entity_id = ei.entity_id
            WHERE ei.identity_id = ? ORDER BY e.confidence DESC NULLS LAST""", [identity_id]).fetchall()
    if not members:
        return {"error": "unbekannte Identität", "id": identity_id}
    mem_ids = [m[0] for m in members]
    id_list = "(" + ",".join("'" + m.replace("'", "''") + "'" for m in mem_ids) + ")"
    belegt = any(m[2] in ("handelsregister_exakt", "ted_nationalid") for m in members)
    name = (max(members, key=lambda m: (m[3] or 0))[1]) or identity_id

    # Gewinner-Zuschläge dieser Identität + Käufer (für „Auftraggeber" der Referenz).
    con.execute(f"""CREATE TEMP TABLE w AS
      SELECT DISTINCT n.notice_id,
             n.title,
             substr(n.cpv_main,1,4) AS cpv4,
             substr(n.performance_nuts,1,3) AS nuts1,
             coalesce(n.award_date, n.publication_date) AS dt,
             year(coalesce(n.award_date, n.publication_date)) AS jahr,
             CASE WHEN n.value_currency='EUR' THEN n.final_value END AS val
      FROM {PE} p JOIN read_parquet('{SN}', hive_partitioning=1) n ON n.notice_id = p.notice_id
      WHERE p.role='winner' AND p.entity_id IN {id_list}""")
    total = con.execute("SELECT count(*) FROM w").fetchone()[0]
    if total == 0:
        return {"error": "keine Zuschläge belegt", "id": identity_id, "name": name,
                "confidence": "belegt" if belegt else "unsicher"}

    # Käufername je Zuschlag (dominanter Buyer der Notice).
    buyers = dict(con.execute(f"""
      SELECT w.notice_id, any_value(e.canonical_name)
      FROM w JOIN {PE} p ON p.notice_id = w.notice_id AND p.role='buyer'
             JOIN {EN} e ON e.entity_id = p.entity_id
      GROUP BY 1""").fetchall())

    # Referenz-Kandidaten: jüngste, werthaltigste Zuschläge zuerst.
    refs = con.execute("""
      SELECT notice_id, title, cpv4, jahr, val
      FROM w WHERE title IS NOT NULL
      ORDER BY (val IS NOT NULL) DESC, val DESC NULLS LAST, jahr DESC NULLS LAST
      LIMIT ?""", [MAX_REFS]).fetchall()
    cpv_labels = dict(con.execute(
        f"SELECT cpv_code, label FROM {CL}").fetchall())
    references = []
    for (nid, title, cpv4, jahr, val) in refs:
        references.append({
            "notice_id": nid,
            "projekt": (title or "")[:200],
            "auftraggeber": buyers.get(nid),
            "wert": float(val) if val else None,
            "von": int(jahr) if jahr else None,
            "bis": int(jahr) if jahr else None,
            "cpv": cpv4,
            "cpv_label": cpv_labels.get((cpv4 or "") + "0000"),
        })

    # CPV-Schwerpunkte (Anteil an allen Zuschlägen).
    f_tot = con.execute("SELECT count(*) FROM w WHERE cpv4 IS NOT NULL AND cpv4<>''").fetchone()[0] or 1
    felder = con.execute("""
      SELECT cpv4, count(*) n FROM w WHERE cpv4 IS NOT NULL AND cpv4<>'' GROUP BY 1
      ORDER BY 2 DESC LIMIT 8""").fetchall()
    cpv_schwerpunkte = [{"code": c, "label": cpv_labels.get((c or "") + "0000", c),
                         "pct": round(100 * n / f_tot)} for (c, n) in felder]

    # Regionen (NUTS1-Anteil).
    r_tot = con.execute("SELECT count(*) FROM w WHERE nuts1 LIKE 'DE_'").fetchone()[0] or 1
    regs = con.execute("SELECT nuts1, count(*) n FROM w WHERE nuts1 LIKE 'DE_' GROUP BY 1 ORDER BY 2 DESC LIMIT 6").fetchall()
    regionen = [{"code": c, "label": NUTS1.get(c, c), "pct": round(100 * n / r_tot)} for (c, n) in regs]

    # Umsatz-Näherung (§7.1 „näherungsweise"): median. Jahres-Auftragsvolumen der letzten 3 belegten Jahre.
    # Bewusst grob & transparent: Auftragsvolumen ≠ Umsatz (Coverage, Rahmenverträge, Mehrjahres-Läufe).
    yr = con.execute("""
      SELECT jahr, sum(val) FROM w WHERE val IS NOT NULL AND val>0 AND jahr IS NOT NULL
      GROUP BY 1 ORDER BY 1 DESC LIMIT 3""").fetchall()
    umsatz_naeherung = None
    vol_cov = round(100 * (con.execute("SELECT count(val) FROM w WHERE val>0").fetchone()[0]) / total)
    if yr:
        sums = sorted(float(s) for (_, s) in yr if s)
        if sums:
            mid = len(sums) // 2
            umsatz_naeherung = sums[mid] if len(sums) % 2 else (sums[mid - 1] + sums[mid]) / 2

    return {
        "id": identity_id,
        "name": name,
        "confidence": "belegt" if belegt else "unsicher",
        "wins_total": int(total),
        "references": references,
        "cpv_schwerpunkte": cpv_schwerpunkte,
        "regionen": regionen,
        "umsatz_naeherung": umsatz_naeherung,
        "umsatz_coverage": vol_cov,
        # Entity-Mitglieder für die Korrektur (§7.3) — Anzeige der zusammengeführten Gesellschaften.
        "entity_members": [
            {"entity_id": m[0], "name": m[1], "method": m[2], "confidence": float(m[3]) if m[3] is not None else None,
             "belegt": m[2] in ("handelsregister_exakt", "ted_nationalid")}
            for m in members
        ],
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
