"""Feature #25 — Firmenprofile VORBERECHNEN → web/data/firma-profiles.json (deploy-fähig).

Die On-Demand-Route scripts/firma_profil.py spawnt Python und liest Parquet — das läuft auf
Vercel-Serverless nicht. Dieses Skript rechnet dieselben Profile für den kompletten
erreichbaren Firmenset (Picker-Suchraum `suppliers.json` + Zuschlags-Gewinner aus
`awards-*.json`) in wenigen Group-by-Durchläufen und legt sie als eine statische, nach
`identity_id` verschlüsselte JSON ab. Die Route liest daraus (kein Python im Deploy).

Feldkontrakt identisch zu scripts/firma_profil.py::build (Frontend unverändert).

Aufruf: python3 scripts/export_firma_profiles.py [--limit N]
"""
import glob
import json
import pathlib
import sys

import duckdb

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "web/data"
G = str(ROOT / "data/gold/DE")
SN = str(ROOT / "data/silver/DE/notices/*/*.parquet")
SA = str(ROOT / "data/silver/DE/attributes/*/*.parquet")

MARKT_VERTEIDIGUNG = 28
BINDUNG_MIN_BELEGE = 3
NUTS1 = {"DE1": "Baden-Württemberg", "DE2": "Bayern", "DE3": "Berlin", "DE4": "Brandenburg",
         "DE5": "Bremen", "DE6": "Hamburg", "DE7": "Hessen", "DE8": "Meck.-Vorpommern",
         "DE9": "Niedersachsen", "DEA": "Nordrhein-Westfalen", "DEB": "Rheinland-Pfalz",
         "DEC": "Saarland", "DED": "Sachsen", "DEE": "Sachsen-Anhalt", "DEF": "Schleswig-Holstein",
         "DEG": "Thüringen"}


def bindung(wins, renewals, seit, now_year):
    jahre = (now_year - seit) if seit else 0
    if wins >= 5 or renewals >= 3:
        return "sehr fest"
    if wins >= 3 or renewals >= 2 or jahre >= 8:
        return "fest"
    if wins == 2 or renewals >= 1:
        return "mittel"
    return "schwach"


def target_ids():
    ids = set()
    try:
        for s in json.load(open(OUT / "suppliers.json")):
            if s.get("id"):
                ids.add(s["id"])
    except Exception:
        pass
    for f in glob.glob(str(OUT / "awards-*.json")):
        try:
            for a in json.load(open(f)):
                w = (a.get("award") or {}).get("winnerId")
                if w:
                    ids.add(w)
        except Exception:
            pass
    return sorted(ids)


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    ids = target_ids()
    if limit:
        ids = ids[:limit]
    if not ids:
        print("keine Ziel-Identitäten (suppliers.json / awards-*.json fehlen?)"); return 1

    con = duckdb.connect(); con.execute("SET threads=4")
    EI = f"read_parquet('{G}/entity_identity.parquet')"
    EN = f"read_parquet('{G}/entities.parquet')"
    PE = f"read_parquet('{G}/party_entity.parquet')"
    CL = f"read_parquet('{G}/dim_cpv_label.parquet')"
    LE = f"read_parquet('{G}/lead_export.parquet')"
    BCH = f"read_parquet('{G}/buyer_contractor_history.parquet')"
    CLOSS = f"read_parquet('{G}/contractor_loss.parquet')"

    con.execute("CREATE TEMP TABLE targets(identity_id VARCHAR)")
    con.executemany("INSERT INTO targets VALUES (?)", [[i] for i in ids])

    now = con.execute(f"SELECT max(publication_date) FROM read_parquet('{SN}', hive_partitioning=1) "
                      f"WHERE publication_date <= CURRENT_DATE").fetchone()[0]
    now_year = now.year if now else 2026

    # Mitglieder (Schwester-Entities) der Ziel-Identitäten
    con.execute(f"""CREATE TEMP TABLE members AS
      SELECT ei.entity_id, ei.identity_id, e.canonical_name, e.method, e.confidence
      FROM {EI} ei JOIN {EN} e ON e.entity_id = ei.entity_id
      WHERE ei.identity_id IN (SELECT identity_id FROM targets)""")

    # Gewinner-Zuschläge je Identität (Basis für KPIs, Felder, Regionen, Signale)
    con.execute(f"""CREATE TEMP TABLE w AS
      SELECT DISTINCT m.identity_id, p.notice_id,
             substr(n.cpv_main,1,4) AS cpv4,
             substr(n.performance_nuts,1,3) AS nuts1,
             coalesce(n.award_date, n.publication_date) AS dt,
             year(coalesce(n.award_date, n.publication_date)) AS jahr,
             CASE WHEN n.value_currency='EUR' THEN n.final_value END AS val
      FROM {PE} p JOIN members m ON m.entity_id = p.entity_id
      JOIN read_parquet('{SN}', hive_partitioning=1) n ON n.notice_id = p.notice_id
      WHERE p.role='winner'""")

    # ---- Kopf/Name/Konfidenz je Identität ----
    head = {r[0]: r for r in con.execute("""
      SELECT identity_id,
             arg_max(canonical_name, confidence) AS name,
             max(CASE WHEN method IN ('handelsregister_exakt','ted_nationalid') THEN 1 ELSE 0 END) AS belegt,
             count(DISTINCT lower(canonical_name)) AS n_namen,
             count(*) AS group_size
      FROM members GROUP BY 1""").fetchall()}

    # ---- KPIs ----
    kpi = {r[0]: r for r in con.execute(f"""
      SELECT identity_id,
             count(*) AS wins_total,
             count(*) FILTER (WHERE dt >= (DATE '{now}' - INTERVAL 36 MONTH)) AS wins36,
             sum(val) AS vol_sum, count(val) AS vol_n, avg(val) AS vol_avg, median(val) AS vol_med
      FROM w WHERE val IS NULL OR val > 0 GROUP BY 1""").fetchall()}
    # Zähler getrennt (count(*) inkl. val=NULL für Coverage)
    wtot = {r[0]: r[1] for r in con.execute("SELECT identity_id, count(*) FROM w GROUP BY 1").fetchall()}

    vd = {r[0]: r for r in con.execute(f"""
      SELECT m.identity_id, sum(c.n_defended) AS defended, sum(c.n_lost) AS lost
      FROM {CLOSS} c JOIN members m ON m.entity_id = c.entity_id GROUP BY 1""").fetchall()}

    aus18 = {r[0]: r for r in con.execute(f"""
      SELECT incumbent_group_id, count(*) AS n, sum(value_eur) AS vol FROM {LE}
      WHERE incumbent_group_id IN (SELECT identity_id FROM targets)
        AND months_to_expiry BETWEEN 0 AND 18 GROUP BY 1""").fetchall()}

    # ---- Felder (Top5 CPV) + Regionen (Top5 NUTS1) ----
    felder = {}
    for iid, cpv4, label, n, pct in con.execute(f"""
      WITH c AS (SELECT identity_id, cpv4, count(*) n FROM w WHERE cpv4 IS NOT NULL AND cpv4<>'' GROUP BY 1,2),
      t AS (SELECT identity_id, sum(n) tot FROM c GROUP BY 1),
      rk AS (SELECT c.*, round(100.0*c.n/t.tot) pct, row_number() OVER (PARTITION BY c.identity_id ORDER BY c.n DESC) rn
             FROM c JOIN t USING(identity_id))
      SELECT rk.identity_id, rk.cpv4, cl.label, rk.n, rk.pct FROM rk
      LEFT JOIN {CL} cl ON cl.cpv_code = rk.cpv4 || '0000' WHERE rk.rn <= 5 ORDER BY rk.identity_id, rk.n DESC""").fetchall():
        felder.setdefault(iid, []).append({"label": label or cpv4, "pct": int(pct)})

    regionen = {}
    for iid, nuts1, n, pct in con.execute("""
      WITH c AS (SELECT identity_id, nuts1, count(*) n FROM w WHERE nuts1 LIKE 'DE_' GROUP BY 1,2),
      t AS (SELECT identity_id, sum(n) tot FROM c GROUP BY 1),
      rk AS (SELECT c.*, round(100.0*c.n/t.tot) pct, row_number() OVER (PARTITION BY c.identity_id ORDER BY c.n DESC) rn
             FROM c JOIN t USING(identity_id))
      SELECT identity_id, nuts1, n, pct FROM rk WHERE rn <= 5 ORDER BY identity_id, n DESC""").fetchall():
        regionen.setdefault(iid, []).append({"label": NUTS1.get(nuts1, nuts1), "pct": int(pct)})

    # ---- Signale: Subcontracting (distinkte Zuschläge mit Feld) + Bietergemeinschaften ----
    subc = {r[0]: r[1] for r in con.execute(f"""
      SELECT w.identity_id, count(DISTINCT w.notice_id) FROM w
      WHERE EXISTS (SELECT 1 FROM read_parquet('{SA}', hive_partitioning=1) a
                    WHERE a.notice_id = w.notice_id AND a.path ILIKE '%ubcontract%') GROUP BY 1""").fetchall()}
    arge = {r[0]: r[1] for r in con.execute(f"""
      WITH nwin AS (SELECT p.notice_id, count(DISTINCT p.entity_id) c FROM {PE} p WHERE p.role='winner' GROUP BY 1)
      SELECT w.identity_id, count(DISTINCT w.notice_id) FROM w JOIN nwin ON nwin.notice_id = w.notice_id
      WHERE nwin.c >= 2 GROUP BY 1""").fetchall()}

    # ---- Wo festsitzt (Top12 Vergabestellen) ----
    n_stellen = {r[0]: r[1] for r in con.execute(f"""
      SELECT m.identity_id, count(DISTINCT b.buyer_entity_id) FROM {BCH} b
      JOIN members m ON m.entity_id = b.contractor_entity_id GROUP BY 1""").fetchall()}
    # Leistung (modaler CPV) + seit je (identity, buyer) aus den Gewinner-Notices
    con.execute(f"""CREATE TEMP TABLE wb AS
      SELECT w.identity_id, pb.entity_id AS buyer_entity_id, w.cpv4, w.jahr
      FROM w JOIN {PE} pb ON pb.notice_id = w.notice_id AND pb.role='buyer'""")
    sits = {}
    for iid, buyer, leistung, wins, seit, renew in con.execute(f"""
      WITH bh AS (
        SELECT m.identity_id, b.buyer_entity_id, sum(b.total_wins) wins,
               max(b.last_win_year) last_year, sum(b.total_renewals) renew
        FROM {BCH} b JOIN members m ON m.entity_id = b.contractor_entity_id GROUP BY 1,2),
      bl AS (SELECT identity_id, buyer_entity_id, mode(cpv4) cpv4, min(jahr) seit FROM wb GROUP BY 1,2),
      rk AS (SELECT bh.*, bl.cpv4, bl.seit,
                    row_number() OVER (PARTITION BY bh.identity_id ORDER BY bh.wins DESC, bl.seit ASC) rn
             FROM bh LEFT JOIN bl ON bl.identity_id=bh.identity_id AND bl.buyer_entity_id=bh.buyer_entity_id)
      SELECT rk.identity_id, en.canonical_name AS buyer, cl.label AS leistung, rk.wins, rk.seit, rk.renew
      FROM rk JOIN {EN} en ON en.entity_id = rk.buyer_entity_id
      LEFT JOIN {CL} cl ON cl.cpv_code = rk.cpv4 || '0000'
      WHERE rk.rn <= 12 AND en.canonical_name IS NOT NULL ORDER BY rk.identity_id, rk.wins DESC""").fetchall():
        sits.setdefault(iid, []).append({
            "buyer": buyer, "leistung": leistung or "—", "auftraege": int(wins),
            "seit": int(seit) if seit else None,
            "bindung": bindung(int(wins), int(renew or 0), int(seit) if seit else 0, now_year)})

    # ---- Was ausläuft (Top10, ≤24 Monate) ----
    expiring = {}
    for iid, slug, title, buyer, val, end, mte, since in con.execute(f"""
      WITH e AS (SELECT *, row_number() OVER (PARTITION BY incumbent_group_id ORDER BY months_to_expiry ASC) rn
                 FROM {LE} WHERE incumbent_group_id IN (SELECT identity_id FROM targets)
                   AND months_to_expiry BETWEEN 0 AND 24)
      SELECT incumbent_group_id, slug, title, buyer_name, value_eur, contract_end, months_to_expiry, incumbent_since_year
      FROM e WHERE rn <= 10 ORDER BY incumbent_group_id, months_to_expiry ASC""").fetchall():
        jahre = (now_year - since) if since else None
        bind = ("Bindung schwach — kurze Historie" if jahre is not None and jahre <= 4
                else "Bindung mittel" if jahre is not None and jahre <= 8
                else "Bindung fest — lange Historie")
        expiring.setdefault(iid, []).append({
            "leadId": slug, "titel": title, "buyer": buyer,
            "vol": float(val) if val else None,
            "ende": end.strftime("%m/%Y") if end is not None and hasattr(end, "strftime") else None,
            "mte": int(mte), "bindung": bind, "soon": mte <= 18})

    # ---- Zusammenbau ----
    out = {}
    for iid in ids:
        h = head.get(iid)
        if not h:
            continue
        name, belegt, n_namen, gsize = h[1] or iid, bool(h[2]), int(h[3]), int(h[4])
        tot = int(wtot.get(iid, 0))
        if tot == 0:
            continue
        k = kpi.get(iid)
        vol_sum = float(k[3]) if k and k[3] else None
        vol_n = int(k[4]) if k and k[4] else 0
        d, lo = (int(vd[iid][1] or 0), int(vd[iid][2] or 0)) if iid in vd else (0, 0)
        base = d + lo
        vert = round(100 * d / base) if base >= BINDUNG_MIN_BELEGE else None
        a18 = aus18.get(iid)
        fl = felder.get(iid, [])
        rg = regionen.get(iid, [])
        out[iid] = {
            "id": iid, "name": name,
            "confidence": "belegt" if belegt else "unsicher",
            "aehnliche_namen": n_namen if not belegt else None,
            "group_size": gsize,
            "schwerpunkt": fl[0]["label"] if fl else None,
            "hauptregion": rg[0]["label"] if rg else None,
            "now_year": now_year,
            "kpi": {
                "wins36": int(k[2]) if k else 0, "wins_total": tot,
                "vol_sum": vol_sum, "vol_cov": round(100 * vol_n / tot) if tot else 0,
                "vol_avg": float(k[5]) if k and k[5] else None,
                "vol_median": float(k[6]) if k and k[6] else None,
                "verteidigung": vert, "verteidigung_base": base,
                "markt_verteidigung": MARKT_VERTEIDIGUNG,
                "aus18_n": int(a18[1]) if a18 else 0,
                "aus18_vol": float(a18[2]) if a18 and a18[2] else None,
            },
            "sits": sits.get(iid, []), "n_vergabestellen": int(n_stellen.get(iid, 0)),
            "expiring": expiring.get(iid, []), "felder": fl, "regionen": rg,
            "signale": {
                "subcontracting": int(subc.get(iid, 0)), "subcontracting_total": tot,
                "bietergemeinschaften": int(arge.get(iid, 0)), "netzwerk": "nicht beigetreten",
            },
        }

    (OUT / "firma-profiles.json").write_text(json.dumps(out, ensure_ascii=False, default=str))
    print(f"{len(out)} Firmenprofile → web/data/firma-profiles.json ({(OUT/'firma-profiles.json').stat().st_size/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
