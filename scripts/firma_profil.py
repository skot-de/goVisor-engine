#!/usr/bin/env python3
"""Feature #25 — Firmenprofil je Identität (JSON auf stdout).

Eine Detailseite, kein Navigationspunkt: erreichbar aus der Wettbewerbstabelle, vom
Amtsinhaber im Lead und vom Gewinner eines Zuschlags (#24). Alle Kennzahlen sind
**gemessen** aus den öffentlichen Vergabedaten — nichts erfunden. Wo die Datenlage dünn
ist, geben wir `null`/Leerwerte zurück; die UI benennt die Lage ehrlich (§ f2 im Prototyp).

Gruppiert über `entity_identity` (identity_id), damit die Varianten einer Firma zu EINEM
Profil verschmelzen (analog scripts/export_suppliers.py).

Aufruf: python3 scripts/firma_profil.py <identity_id>
Ausgabe: eine JSON-Zeile mit dem vollständigen Profil (oder {"error": ...}).
"""
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
G = str(ROOT / "data/gold/DE")
SN = str(ROOT / "data/silver/DE/notices/*/*.parquet")
SA = str(ROOT / "data/silver/DE/attributes/*/*.parquet")

# Marktübliche Verteidigungsquote (gemessen, CLAUDE.md: Incumbent-Retention 28,3 %).
MARKT_VERTEIDIGUNG = 28
BINDUNG_MIN_BELEGE = 3          # unter so wenig Nachfolgen keine Quote


def _con():
    con = duckdb.connect()
    con.execute("SET threads=4")
    return con


def _bindung(wins: int, renewals: int, seit: int, now_year: int) -> str:
    """Bindungs-Stufe je Vergabestelle — gemessen an Aufträgen + Verlängerungen + Dauer."""
    jahre = (now_year - seit) if seit else 0
    if wins >= 5 or renewals >= 3:
        return "sehr fest"
    if wins >= 3 or renewals >= 2 or jahre >= 8:
        return "fest"
    if wins == 2 or renewals >= 1:
        return "mittel"
    return "schwach"


def build(identity_id: str) -> dict:
    con = _con()
    EI = f"read_parquet('{G}/entity_identity.parquet')"
    EN = f"read_parquet('{G}/entities.parquet')"
    PE = f"read_parquet('{G}/party_entity.parquet')"
    CL = f"read_parquet('{G}/dim_cpv_label.parquet')"
    LE = f"read_parquet('{G}/lead_export.parquet')"
    BCH = f"read_parquet('{G}/buyer_contractor_history.parquet')"
    CLOSS = f"read_parquet('{G}/contractor_loss.parquet')"

    # Mitglieder der Identität (Schwester-Entities)
    members = con.execute(
        f"""SELECT ei.entity_id, e.canonical_name, e.method, e.confidence
            FROM {EI} ei JOIN {EN} e ON e.entity_id = ei.entity_id
            WHERE ei.identity_id = ?""", [identity_id]).fetchall()
    if not members:
        return {"error": "unbekannte Identität", "id": identity_id}
    mem_ids = [m[0] for m in members]
    id_list = "(" + ",".join("'" + m.replace("'", "''") + "'" for m in mem_ids) + ")"

    # Repräsentativer Name + Zuordnungs-Konfidenz
    belegt = any(m[2] in ("handelsregister_exakt", "ted_nationalid") for m in members)
    n_namen = len({(m[1] or "").lower() for m in members if m[1]})
    name = max((m for m in members), key=lambda m: (m[3] or 0))[1] or identity_id
    group_size = len(mem_ids)

    # Bezugszeitpunkt = jüngstes plausibles Publikationsdatum (Daten enden ~2026-07).
    # Guard gegen `datum_absurd`-Ausreißer (vereinzelt Zukunftsdaten im XML): auf ≤ heute klemmen.
    now = con.execute(
        f"SELECT max(publication_date) FROM read_parquet('{SN}', hive_partitioning=1) "
        f"WHERE publication_date <= CURRENT_DATE").fetchone()[0]
    now_year = now.year if now else 2026

    # Gewinner-Zuschläge dieser Identität mit CPV/Region/Datum/Wert
    con.execute(f"""CREATE TEMP TABLE w AS
      SELECT DISTINCT p.notice_id,
             substr(n.cpv_main,1,4) AS cpv4,
             substr(n.performance_nuts,1,3) AS nuts1,
             coalesce(n.award_date, n.publication_date) AS dt,
             year(coalesce(n.award_date, n.publication_date)) AS jahr,
             CASE WHEN n.value_currency='EUR' THEN n.final_value END AS val,
             n.title
      FROM {PE} p JOIN read_parquet('{SN}', hive_partitioning=1) n ON n.notice_id = p.notice_id
      WHERE p.role='winner' AND p.entity_id IN {id_list}""")

    total_wins = con.execute("SELECT count(*) FROM w").fetchone()[0]
    if total_wins == 0:
        return {"error": "keine Zuschläge belegt", "id": identity_id, "name": name}

    # ---- KPIs ----
    wins36 = con.execute(
        "SELECT count(*) FROM w WHERE dt >= (?::DATE - INTERVAL 36 MONTH)", [now]).fetchone()[0]
    vol = con.execute(
        "SELECT sum(val), count(val), avg(val), median(val) FROM w WHERE val IS NOT NULL AND val>0").fetchone()
    vol_sum, vol_n, vol_avg, vol_med = vol
    vol_cov = round(100 * vol_n / total_wins) if total_wins else 0

    # Verteidigungsquote aus contractor_loss über die Mitglieder
    vd = con.execute(
        f"SELECT sum(n_defended), sum(n_lost) FROM {CLOSS} WHERE entity_id IN {id_list}").fetchone()
    defended, lost = (vd[0] or 0), (vd[1] or 0)
    vd_base = defended + lost
    verteidigung = round(100 * defended / vd_base) if vd_base >= BINDUNG_MIN_BELEGE else None

    # „Läuft aus ≤18 Monate" — Leads, in denen diese Identität Amtsinhaber ist
    aus18 = con.execute(
        f"""SELECT count(*), sum(value_eur) FROM {LE}
            WHERE incumbent_group_id = ? AND months_to_expiry IS NOT NULL
              AND months_to_expiry >= 0 AND months_to_expiry <= 18""", [identity_id]).fetchone()
    aus18_n, aus18_vol = (aus18[0] or 0), aus18[1]

    # ---- Wo festsitzt: Vergabestellen (buyer_contractor_history) ----
    sits = con.execute(f"""
      WITH bh AS (
        SELECT buyer_entity_id, sum(total_wins) AS wins, max(last_win_year) AS last_year,
               sum(total_renewals) AS renewals
        FROM {BCH} WHERE contractor_entity_id IN {id_list} GROUP BY 1),
      bn AS (SELECT entity_id, canonical_name FROM {EN}),
      -- Leistung + „seit" je Käufer aus den echten Zuschlags-Notices
      bl AS (
        SELECT pb.entity_id AS buyer_entity_id,
               min(w.jahr) AS seit,
               mode(w.cpv4) AS cpv4          -- dominanter (häufigster) CPV je Käufer
        FROM {PE} pb JOIN w ON w.notice_id = pb.notice_id
        WHERE pb.role='buyer' GROUP BY 1)
      SELECT bn.canonical_name AS buyer, cl.label AS leistung, bh.wins, bl.seit, bh.renewals
      FROM bh JOIN bn ON bn.entity_id = bh.buyer_entity_id
      LEFT JOIN bl ON bl.buyer_entity_id = bh.buyer_entity_id
      LEFT JOIN {CL} cl ON cl.cpv_code = bl.cpv4 || '0000'
      WHERE bn.canonical_name IS NOT NULL
      ORDER BY bh.wins DESC, bl.seit ASC LIMIT 12""").fetchall()
    sits_out = []
    for (buyer, leistung, wins, seit, renewals) in sits:
        sits_out.append({
            "buyer": buyer, "leistung": leistung or "—",
            "auftraege": int(wins), "seit": int(seit) if seit else None,
            "bindung": _bindung(int(wins), int(renewals or 0), int(seit) if seit else 0, now_year),
        })
    n_vergabestellen = con.execute(
        f"SELECT count(DISTINCT buyer_entity_id) FROM {BCH} WHERE contractor_entity_id IN {id_list}").fetchone()[0]

    # ---- Was ausläuft (Pro) — Leads mit diesem Amtsinhaber, Ende ≤24 M ----
    exp = con.execute(f"""
      SELECT slug, title, buyer_name, value_eur, contract_end, months_to_expiry,
             incumbent_since_year, incumbent_confidence
      FROM {LE}
      WHERE incumbent_group_id = ? AND months_to_expiry IS NOT NULL
        AND months_to_expiry >= 0 AND months_to_expiry <= 24
      ORDER BY months_to_expiry ASC LIMIT 10""", [identity_id]).fetchall()
    exp_out = []
    for (slug, title, buyer, val, end, mte, since, conf) in exp:
        jahre = (now_year - since) if since else None
        if jahre is not None and jahre <= 4:
            bind = "Bindung schwach — kurze Historie"
        elif jahre is not None and jahre <= 8:
            bind = "Bindung mittel"
        else:
            bind = "Bindung fest — lange Historie"
        exp_out.append({
            "leadId": slug, "titel": title, "buyer": buyer,
            "vol": float(val) if val else None,
            "ende": end.strftime("%m/%Y") if end else None,
            "mte": int(mte), "bindung": bind, "soon": mte <= 18,
        })

    # ---- Wo stark: CPV-Felder + Regionen (Anteile) ----
    # Anteil an ALLEN Aufträgen (nicht nur den Top-5) — konsistent mit export_firma_profiles.py
    f_tot = con.execute("SELECT count(*) FROM w WHERE cpv4 IS NOT NULL AND cpv4<>''").fetchone()[0] or 1
    felder = con.execute(f"""
      WITH c AS (SELECT cpv4, count(*) n FROM w WHERE cpv4 IS NOT NULL AND cpv4<>'' GROUP BY 1)
      SELECT c.cpv4, cl.label, c.n FROM c LEFT JOIN {CL} cl ON cl.cpv_code = c.cpv4||'0000'
      ORDER BY c.n DESC LIMIT 5""").fetchall()
    felder_out = [{"label": (lbl or code), "pct": round(100 * n / f_tot)} for (code, lbl, n) in felder]

    r_tot = con.execute("SELECT count(*) FROM w WHERE nuts1 LIKE 'DE_'").fetchone()[0] or 1
    regionen = con.execute("""
      SELECT nuts1, count(*) n FROM w WHERE nuts1 LIKE 'DE_' GROUP BY 1 ORDER BY 2 DESC LIMIT 5""").fetchall()
    NUTS1 = {"DE1": "Baden-Württemberg", "DE2": "Bayern", "DE3": "Berlin", "DE4": "Brandenburg",
             "DE5": "Bremen", "DE6": "Hamburg", "DE7": "Hessen", "DE8": "Meck.-Vorpommern",
             "DE9": "Niedersachsen", "DEA": "Nordrhein-Westfalen", "DEB": "Rheinland-Pfalz",
             "DEC": "Saarland", "DED": "Sachsen", "DEE": "Sachsen-Anhalt", "DEF": "Schleswig-Holstein",
             "DEG": "Thüringen"}
    regionen_out = [{"label": NUTS1.get(code, code), "pct": round(100 * n / r_tot)} for (code, n) in regionen]

    # ---- Weitere Signale ----
    # Unterauftragsvergabe geregelt: Zuschläge mit belegtem Subcontracting-Feld
    subc = con.execute(f"""
      SELECT count(DISTINCT a.notice_id) FROM read_parquet('{SA}', hive_partitioning=1) a
      JOIN w ON w.notice_id = a.notice_id
      WHERE a.path ILIKE '%ubcontract%'""").fetchone()[0]
    # Bietergemeinschaften: Zuschläge mit ≥2 Gewinner-Entities
    arge = con.execute(f"""
      SELECT count(*) FROM (
        SELECT p.notice_id FROM {PE} p JOIN w ON w.notice_id = p.notice_id
        WHERE p.role='winner' GROUP BY 1 HAVING count(DISTINCT p.entity_id) >= 2)""").fetchone()[0]

    return {
        "id": identity_id,
        "name": name,
        "confidence": "belegt" if belegt else "unsicher",
        "aehnliche_namen": n_namen if not belegt else None,
        "group_size": group_size,
        "schwerpunkt": felder_out[0]["label"] if felder_out else None,
        "hauptregion": regionen_out[0]["label"] if regionen_out else None,
        "now_year": now_year,
        "kpi": {
            "wins36": int(wins36),
            "wins_total": int(total_wins),
            "vol_sum": float(vol_sum) if vol_sum else None,
            "vol_cov": vol_cov,
            "vol_avg": float(vol_avg) if vol_avg else None,
            "vol_median": float(vol_med) if vol_med else None,
            "verteidigung": verteidigung,
            "verteidigung_base": int(vd_base),
            "markt_verteidigung": MARKT_VERTEIDIGUNG,
            "aus18_n": int(aus18_n),
            "aus18_vol": float(aus18_vol) if aus18_vol else None,
        },
        "sits": sits_out,
        "n_vergabestellen": int(n_vergabestellen),
        "expiring": exp_out,
        "felder": felder_out,
        "regionen": regionen_out,
        "signale": {
            "subcontracting": int(subc),
            "subcontracting_total": int(total_wins),
            "bietergemeinschaften": int(arge),
            "netzwerk": "nicht beigetreten",
        },
    }


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "identity_id fehlt"})); return 0
    try:
        print(json.dumps(build(sys.argv[1]), ensure_ascii=False, default=str))
    except Exception as e:  # noqa: BLE001 — Fehler ehrlich ans Frontend
        print(json.dumps({"error": str(e)[:200]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
