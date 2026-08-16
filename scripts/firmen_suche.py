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
sys.path.insert(0, str(ROOT))
import zielliste as Z  # noqa: E402
from govisor.gold import _kind_sql  # noqa: E402  — Vertragsart-Klassifikator (Titel+CPV), wie in lead_export

# Rahmen-/wiederkehrend-Werte des Klassifikators (der Rest = Einmal/Werk/Sonstiges)
_RAHMEN_KINDS = "('rahmenvertrag','wiederkehrend')"

G = str(ROOT / "data/gold/DE")
SN = str(ROOT / "data/silver/DE/notices/*/*.parquet")


def _con():
    con = duckdb.connect(); con.execute("SET threads=4")
    return con


# Vertragsart-Label je contract_kind. Kategorie steuert Farbe/Bedeutung in der UI:
#   rahmen  = wiederkehrendes Volumen (wird neu ausgeschrieben → lohnt Dranbleiben)
#   einmal  = einmalige Leistung (nach Fertigstellung erledigt)
#   neutral = Vergabeart unbestimmt (Klassifikator konnte sie nicht sicher zuordnen)
_ART = {
    "framework":     ("Rahmenvertrag", "rahmen"),
    "recurring":     ("Wiederkehrend", "rahmen"),
    "one_off_works": ("Einmalauftrag", "einmal"),
    "works_other":   ("Bauleistung", "einmal"),
    "other":         ("Einzelvergabe", "neutral"),
}


def art_of(kind):
    """(label, kategorie) je contract_kind — beide fürs Frontend."""
    return _ART.get(kind, (None, None))


def search(plz=None, ort=None, name=None, radius=None):
    if not (plz or ort or name):
        return {"error": "Bitte PLZ, Ort oder Name angeben"}
    con = _con()
    now = Z.build_population(con, adhoc={"plz": plz, "ort": ort, "name": name, "radius": radius})
    Z.compute_signals(con, now)
    rows = con.execute("""
      SELECT identity_id, firmenname, sitz_plz, sitz_ort, sitz_nuts, wins36, med_val, vol36,
             verlorene_12m, verlust_vol, letzter_verlust, auslauf_n, auslauf_vol,
             naechstes_auslaufdatum, dominant_signal, email, phone
      FROM ranked ORDER BY (coalesce(verlust_vol,0)+coalesce(auslauf_vol,0)) DESC, wins36 DESC
      LIMIT 100""").fetchall()
    firmen = [{
        "id": r[0], "name": Z.clean_name(r[1]), "plz": r[2], "ort": r[3], "nuts": r[4],
        "wins36": int(r[5] or 0), "medWert": float(r[6]) if r[6] else None,   # Median (robust ggü. Framework-Nennwerten)
        "vol36": float(r[7]) if r[7] else None,
        "s1": {"n": int(r[8] or 0), "vol": float(r[9]) if r[9] else None, "letzter": str(r[10]) if r[10] else None},
        "s2": {"n": int(r[11] or 0), "vol": float(r[12]) if r[12] else None, "naechstes": str(r[13]) if r[13] else None},
        "dominant": r[14], "email": r[15], "phone": r[16],
    } for r in rows]
    return {"stichtag": str(now), "n": len(firmen), "firmen": firmen}


# Konsortien / ARGE aus den deutschlandweiten Ranglisten fernhalten — das sind keine ansprechbaren
# Einzelfirmen, und ihre Zusammensetzung wechselt je Projekt (verzerrt jeden Trend).
_KONSORTIUM = ("firmenname NOT LIKE 'BG %' AND firmenname NOT LIKE '%ARGE%' "
               "AND lower(firmenname) NOT LIKE '%arbeitsgemeinschaft%' AND firmenname NOT LIKE '% / %'")


# Vertriebsziel-Segmente A–G (govisor-vertriebsziele-spec.md) — deutschlandweite Kohorten.
# Reihenfolge = Ansprache-Priorität §8 (F akutester Schmerz zuerst, B größte/kälteste Gruppe zuletzt).
SEGMENTS = {
    "F": ("Frische Verlierer", "Verlust ≤6 Monate. Akut, kürzestes Zeitfenster"),
    "E": ("Verteidiger unter Druck", "Bestand läuft in 6 bis 18 Monaten aus (≥250k)"),
    "C": ("Absteiger", "Zuschlagszahl fällt über 3 Jahre"),
    "A": ("High Roller", "≥24 Zuschläge in 12 Monaten. Verdrängungsverkauf"),
    "D": ("Aussteiger", "früher aktiv, ≥18 Monate kein Zuschlag mehr"),
    "G": ("Aufsteiger", "Zuschlagszahl steigt ≥40 % über 3 Jahre"),
    "B": ("Gelegenheitsbieter", "1 bis 5 Zuschläge in 24 Monaten, größte Gruppe"),
}


# §8 Ansprache-Priorität (höchste zuerst) + Kurzname je Segment für „weitere_segmente"
_PRIORITY = ["F", "E", "C", "A", "D", "G", "B"]
_SEG_TAB = {k: SEGMENTS[k][0] for k in SEGMENTS}


def _eur(v):
    if not v:
        return "—"
    v = float(v)
    return f"{v/1e6:.1f} Mio €".replace(".", ",") if v >= 1e6 else f"{round(v):,} €".replace(",", ".")


def _rq(rahmen_vol, tot):  # Rahmen-Quote in % (None ohne bewertbares Volumen)
    return round((rahmen_vol or 0) / tot * 100) if tot else None


# Einstellbare Knöpfe je Segment (Frontend rendert daraus die Filter-Regler; def = Spec-Vorgabe).
_CONTROLS = {
    "A": [{"k": "min_wins", "label": "min. Zuschläge", "def": 24, "step": 1},
          {"k": "months", "label": "Fenster (Monate)", "def": 12, "step": 6}],
    "B": [{"k": "lo", "label": "min. Zuschläge", "def": 1, "step": 1},
          {"k": "hi", "label": "max. Zuschläge", "def": 5, "step": 1},
          {"k": "months", "label": "Fenster (Monate)", "def": 24, "step": 6}],
    "C": [{"k": "min_base", "label": "min. Zuschläge (3J)", "def": 6, "step": 1},
          {"k": "decline", "label": "Rückgang % ≥", "def": 40, "step": 5},
          {"k": "market", "label": "nur gegen Markttrend", "def": 1, "type": "toggle"}],
    "D": [{"k": "still", "label": "Stillstand ≥ Monate", "def": 18, "step": 3},
          {"k": "hist", "label": "min. Historie", "def": 3, "step": 1},
          {"k": "market", "label": "Feld aktiv ≥ Vergaben/18M", "def": 10, "step": 5}],
    "E": [{"k": "min_vol", "label": "min. Auslauf €", "def": 250000, "step": 50000},
          {"k": "switch", "label": "Wechselquote % ≥", "def": 40, "step": 5},
          {"k": "lo", "label": "Auslauf ab Monat", "def": 6, "step": 3},
          {"k": "hi", "label": "bis Monat", "def": 18, "step": 3}],
    "F": [{"k": "min_vol", "label": "min. Verlust €", "def": 100000, "step": 50000},
          {"k": "months", "label": "Fenster (Monate)", "def": 6, "step": 3}],
    "G": [{"k": "min_base", "label": "min. Zuschläge (3J)", "def": 6, "step": 1},
          {"k": "rise", "label": "Anstieg % ≥", "def": 40, "step": 5}],
}
# Universeller Regler: Mindest-Rahmen-Quote (Anteil wiederkehrenden Volumens) — gilt in JEDEM Segment.
_RAHMEN_CTRL = {"k": "min_rahmen", "label": "min. Rahmen %", "def": 0, "step": 10}


def segment(seg="F", limit=100, params=None, geo=None):
    """Eine Vertriebsziel-Kohorte (belegte Einzelfirmen, Konsortien gefiltert).

    A/B/C/D/G aus einer Jahres-Zuschlags-Aggregation; E aus auslaufenden Verträgen, F aus frischen
    Verlusten. `params` überschreibt die Spec-Schwellen (s. _CONTROLS). Ehrlichkeitschecks §3:
      C — nur behalten, wenn die Firma STÄRKER fällt als ihr CPV-Markt (sonst schrumpft der Markt).
      D — nur, wenn das Feld noch aktiv ist (≥N Vergaben im CPV in 18 Monaten).
      E — nur in Segmenten mit hoher Wechselquote (market_switch_rate ≥ Schwelle).
    `geo` = {plz, radius, ort, nuts} schränkt auf den FIRMENSITZ ein (deutschlandweit, wenn leer).
    Der Markt-Trend (C/D) bleibt national — nur die Firmenauswahl wird regional. badge + line + metric.
    """
    seg = (seg or "F").upper()
    if seg not in SEGMENTS:
        return {"error": f"unbekanntes Segment {seg}"}
    params = params or {}

    def gp(k, d):  # get numeric param with default
        try:
            return float(params[k]) if k in params else float(d)
        except (TypeError, ValueError):
            return float(d)

    con = _con()
    now = Z.con_now(con)
    EI = f"read_parquet('{G}/entity_identity.parquet')"; EN = f"read_parquet('{G}/entities.parquet')"
    PE = f"read_parquet('{G}/party_entity.parquet')"; QU = f"read_parquet('{G}/quality.parquet')"
    LE = f"read_parquet('{G}/lead_export.parquet')"; SE = f"read_parquet('{G}/succession_events.parquet')"
    MS = f"read_parquet('{G}/market_switch_rate.parquet')"; DP = f"read_parquet('{G}/dim_plz.parquet')"
    Z.build_entity_location(con)

    # ── Geo-Filter auf den Firmensitz (eloc) — schränkt `belegt` ein, alles Downstream folgt ──
    geo = geo or {}
    geo_label, belegt_geo = None, ""
    gplz = "".join(c for c in str(geo.get("plz") or "") if c.isdigit())[:5]
    gort = (geo.get("ort") or "").strip().replace("'", "")
    gnuts = (geo.get("nuts") or "").strip().upper()
    if gplz and geo.get("radius"):
        try:
            radius = max(1.0, min(200.0, float(geo["radius"])))
        except (TypeError, ValueError):
            radius = 25.0
        center = con.execute(f"SELECT lat, lon FROM {DP} WHERE plz=? LIMIT 1", [gplz]).fetchone()
        if center:
            clat, clon = float(center[0]), float(center[1])
            hav = (f"6371*acos(least(1.0, sin(radians({clat}))*sin(radians(dp.lat)) + "
                   f"cos(radians({clat}))*cos(radians(dp.lat))*cos(radians(dp.lon-({clon})))))")
            con.execute(f"""CREATE OR REPLACE TEMP TABLE geoids AS
              SELECT DISTINCT el.identity_id FROM eloc el JOIN {DP} dp ON dp.plz = el.plz
              WHERE el.plz IS NOT NULL AND {hav} <= {radius}""")
            geo_label = f"{gplz} +{int(radius)} km"
        else:
            con.execute("CREATE OR REPLACE TEMP TABLE geoids AS SELECT identity_id FROM eloc WHERE FALSE")
            geo_label = f"{gplz} (PLZ unbekannt)"
    elif gplz:
        con.execute(f"CREATE OR REPLACE TEMP TABLE geoids AS SELECT identity_id FROM eloc WHERE plz LIKE '{gplz}%'")
        geo_label = f"PLZ {gplz}"
    elif gort:
        o = gort.lower()
        con.execute(f"""CREATE OR REPLACE TEMP TABLE geoids AS SELECT identity_id FROM eloc
          WHERE lower(ort)='{o}' OR lower(ort) LIKE '{o}-%' OR lower(ort) LIKE '{o} %'
             OR lower(ort) LIKE '{o}/%' OR lower(ort) LIKE '{o}(%'""")
        geo_label = gort
    elif gnuts.startswith("DE"):
        con.execute(f"CREATE OR REPLACE TEMP TABLE geoids AS SELECT identity_id FROM eloc WHERE nuts LIKE '{gnuts}%'")
        geo_label = f"Region {gnuts}"
    if geo_label:
        belegt_geo = "AND ei.identity_id IN (SELECT identity_id FROM geoids)"

    con.execute(f"""CREATE OR REPLACE TEMP TABLE belegt AS SELECT DISTINCT ei.identity_id
      FROM {EI} ei JOIN {EN} e ON e.entity_id=ei.entity_id
      WHERE e.method IN {Z.BELEGT_METHODS} {belegt_geo}""")
    nm = (f"(SELECT arg_max(e.canonical_name,e.confidence) FROM {EI} ei JOIN {EN} e ON e.entity_id=ei.entity_id "
          "WHERE ei.identity_id=x.identity_id)")

    def base(id_, name):
        return {"id": id_, "name": Z.clean_name(name), "s1": {"n": 0, "vol": None, "letzter": None},
                "s2": {"n": 0, "vol": None, "naechstes": None}, "dominant": None, "nuts": None,
                "vol36": None, "wins36": 0}

    def w(m):
        return f"DATE '{now}'-INTERVAL {int(m)} MONTH"

    dedup = gp("dedup", 1) >= 1          # §8-Einmalzuordnung (Firma nur im höchstprior. Segment)
    fetch = int(limit) * 5 if dedup else int(limit)
    mA, mB, still = int(gp("months", 12)), int(gp("months", 24)), int(gp("still", 18))

    # ── Immer bauen: Zuschlags-Aggregation + Markt-Trend + E/F-Sets + Membership (für §8-Zuordnung) ──
    con.execute(f"""CREATE OR REPLACE TEMP TABLE win AS
      SELECT ei.identity_id, pw.notice_id nid, coalesce(n.award_date,n.publication_date) dt,
             q.final_value_clean val, substr(n.cpv_main,1,4) cpv4,
             {_kind_sql('n.title','n.cpv_main')} AS kind
      FROM {PE} pw JOIN {EI} ei ON ei.entity_id=pw.entity_id
      JOIN read_parquet('{SN}',hive_partitioning=1) n ON n.notice_id=pw.notice_id
      LEFT JOIN {QU} q ON q.notice_id=pw.notice_id
      WHERE pw.role='winner' AND ei.identity_id IN (SELECT identity_id FROM belegt)
        AND coalesce(n.award_date,n.publication_date) > {w(72)}""")
    con.execute(f"""CREATE OR REPLACE TEMP TABLE sa AS
      SELECT identity_id,
        count(DISTINCT nid) FILTER(WHERE dt>{w(12)}) v3,
        count(DISTINCT nid) FILTER(WHERE dt<={w(12)} AND dt>{w(24)}) v2,
        count(DISTINCT nid) FILTER(WHERE dt<={w(24)} AND dt>{w(36)}) v1,
        count(DISTINCT nid) FILTER(WHERE dt>{w(24)}) v24d,
        count(DISTINCT nid) FILTER(WHERE dt<={w(18)} AND dt>{w(60)}) v_old18,
        count(DISTINCT nid) FILTER(WHERE dt>{w(18)}) v_last18,
        count(DISTINCT nid) FILTER(WHERE dt>{w(mA)}) vA,
        count(DISTINCT nid) FILTER(WHERE dt>{w(mB)}) vB,
        count(DISTINCT nid) FILTER(WHERE dt<={w(still)} AND dt>{w(60)}) v_old,
        count(DISTINCT nid) FILTER(WHERE dt>{w(still)}) v_last,
        count(DISTINCT nid) FILTER(WHERE dt>{w(36)}) awards36,
        median(val) FILTER(WHERE val>0 AND dt>{w(36)}) med36,
        -- Rahmen-Quote je Firma: Anteil wiederkehrenden Volumens an allen Gewinnen (36M)
        sum(val) FILTER(WHERE val>0 AND dt>{w(36)} AND kind IN {_RAHMEN_KINDS}) rahmen_vol,
        sum(val) FILTER(WHERE val>0 AND dt>{w(36)}) tot_vol36,
        mode(cpv4) FILTER(WHERE cpv4 IS NOT NULL) cpv4, max(dt) last_award
      FROM win GROUP BY 1""")
    con.execute(f"""CREATE OR REPLACE TEMP TABLE mkt AS
      SELECT substr(n.cpv_main,1,4) cpv4,
        count(DISTINCT pw.notice_id) FILTER(WHERE coalesce(n.award_date,n.publication_date)>{w(12)}) sy3,
        count(DISTINCT pw.notice_id) FILTER(WHERE coalesce(n.award_date,n.publication_date)<={w(24)}
                                             AND coalesce(n.award_date,n.publication_date)>{w(36)}) sy1,
        count(DISTINCT pw.notice_id) FILTER(WHERE coalesce(n.award_date,n.publication_date)>{w(18)}) n_recent
      FROM {PE} pw JOIN read_parquet('{SN}',hive_partitioning=1) n ON n.notice_id=pw.notice_id
      WHERE pw.role='winner' AND n.cpv_main IS NOT NULL
        AND coalesce(n.award_date,n.publication_date) > {w(36)}
      GROUP BY 1""")
    # E/F-Zugehörigkeit mit Default-Schwellen — Basis der §8-Priorisierung (unabhängig vom aktiven Tab)
    con.execute(f"""CREATE OR REPLACE TEMP TABLE eset AS
      SELECT a.identity_id FROM (
        SELECT incumbent_group_id identity_id, sum(coalesce(value_eur,0)) vol, mode(substr(cpv_code,1,4)) cpv4
        FROM {LE} WHERE incumbent_group_id IN (SELECT identity_id FROM belegt) AND months_to_expiry BETWEEN 6 AND 18
        GROUP BY 1 HAVING sum(coalesce(value_eur,0))>=250000) a
      LEFT JOIN {MS} sr ON sr.cpv_class=a.cpv4 WHERE coalesce(sr.switch_rate,0)>=0.40""")
    con.execute(f"""CREATE OR REPLACE TEMP TABLE fset AS
      WITH pred AS (SELECT se.successor, ei.identity_id loser FROM {SE} se
          JOIN {PE} pp ON pp.notice_id=se.predecessor AND pp.role='winner'
          JOIN {EI} ei ON ei.entity_id=pp.entity_id
          WHERE se.displaced=TRUE AND ei.identity_id IN (SELECT identity_id FROM belegt))
      SELECT DISTINCT pr.loser identity_id
      FROM pred pr JOIN read_parquet('{SN}',hive_partitioning=1) n ON n.notice_id=pr.successor
      LEFT JOIN {QU} q ON q.notice_id=pr.successor
      WHERE n.award_date > {w(6)} AND coalesce(q.final_value_clean,0) >= 100000
        AND NOT EXISTS(SELECT 1 FROM {PE} ps JOIN {EI} es ON es.entity_id=ps.entity_id
                       WHERE ps.notice_id=pr.successor AND ps.role='winner' AND es.identity_id=pr.loser)""")
    con.execute(f"""CREATE OR REPLACE TEMP TABLE mem AS
      SELECT s.identity_id,
        (ff.identity_id IS NOT NULL) fF,
        (ee.identity_id IS NOT NULL) fE,
        ((s.v1+s.v2+s.v3)>=6 AND ((s.v1>s.v2 AND s.v2>s.v3) OR s.v3<=0.6*s.v1)
           AND m.sy1>=5 AND ((m.sy3-m.sy1)::DOUBLE/m.sy1) > ((s.v3-s.v1)::DOUBLE/nullif(s.v1,0))) fC,
        (s.v3>=24) fA,
        (s.v_old18>=3 AND s.v_last18=0 AND coalesce(m.n_recent,0)>=10) fD,
        ((s.v1+s.v2+s.v3)>=6 AND s.v1>=1 AND s.v3>=1.4*s.v1 AND s.v3>s.v1) fG,
        (s.v24d BETWEEN 1 AND 5
           AND NOT (s.v_old18>=3 AND s.v_last18=0 AND coalesce(m.n_recent,0)>=10)
           AND NOT ((s.v1+s.v2+s.v3)>=6 AND ((s.v1>s.v2 AND s.v2>s.v3) OR s.v3<=0.6*s.v1))) fB
      FROM sa s LEFT JOIN mkt m ON m.cpv4=s.cpv4
        LEFT JOIN eset ee ON ee.identity_id=s.identity_id
        LEFT JOIN fset ff ON ff.identity_id=s.identity_id""")

    firmen = []
    if seg in ("A", "B", "C", "D", "G"):
        dec = 1 - gp("decline", 40) / 100.0   # C: v3 <= dec*v1
        rise = 1 + gp("rise", 40) / 100.0      # G: v3 >= rise*v1
        cond = {
            "A": (f"vA>={int(gp('min_wins',24))}", "vA DESC"),
            "B": (f"vB BETWEEN {int(gp('lo',1))} AND {int(gp('hi',5))} AND NOT (v_old>={int(gp('hist',3))} AND v_last=0)"
                  f" AND NOT ((v1+v2+v3)>={int(gp('min_base',6))} AND ((v1>v2 AND v2>v3) OR v3<={dec}*v1))", "med36 DESC NULLS LAST"),
            "C": (f"(v1+v2+v3)>={int(gp('min_base',6))} AND ((v1>v2 AND v2>v3) OR v3<={dec}*v1)", "(v1-v3) DESC"),
            "D": (f"v_old>={int(gp('hist',3))} AND v_last=0", "v_old DESC"),
            "G": (f"(v1+v2+v3)>={int(gp('min_base',6))} AND v1>=1 AND v3>={rise}*v1 AND v3>v1", "(v3-v1) DESC"),
        }[seg]
        rows = con.execute(f"""
          WITH named AS (SELECT x.*, {nm} firmenname,
                           el.plz, el.ort, el.email, el.phone, m.sy1, m.sy3, m.n_recent
                         FROM sa x LEFT JOIN eloc el ON el.identity_id=x.identity_id
                         LEFT JOIN mkt m ON m.cpv4 = x.cpv4)
          SELECT identity_id, firmenname, plz, ort, email, phone,
                 v1,v2,v3, vA, vB, v_old, awards36, med36, last_award, cpv4, sy1, sy3, n_recent,
                 rahmen_vol, tot_vol36
          FROM named WHERE firmenname IS NOT NULL AND {_KONSORTIUM} AND ({cond[0]})
          ORDER BY {cond[1]} LIMIT {fetch}""").fetchall()
        mkt_min = int(gp("market", 10)) if seg == "D" else None
        market_on = seg == "C" and gp("market", 1) >= 1
        for r in rows:
            (v1, v2, v3, vA, vB, v_old, aw36, med36, last, cpv4, sy1, sy3, n_recent) = r[6:19]
            v1, v2, v3 = int(v1 or 0), int(v2 or 0), int(v3 or 0)
            f = base(r[0], r[1]); f.update({"plz": r[2], "ort": r[3], "email": r[4], "phone": r[5],
                                            "medWert": float(med36) if med36 else None, "wins36": int(aw36 or 0),
                                            "rahmenQuote": _rq(r[19], r[20])})
            spark = f"{v1} → {v2} → {v3}"
            if seg == "A":
                f["badge"] = {"label": f"⚡ {int(vA)} Zuschläge", "cls": "aktiv", "spark": spark}
                f["line"] = f"{int(vA)} Zuschläge/{mA}M · Median {_eur(med36)}"; f["metric"] = int(vA)
            elif seg == "B":
                band = "B1" if (med36 or 0) >= 5e5 else "B2" if (med36 or 0) >= 1e5 else "B3"
                f["badge"] = {"label": f"{band} · Median {_eur(med36)}", "cls": "s2"}
                f["line"] = f"{int(vB)} Zuschläge/{mB}M · Median {_eur(med36)}"; f["metric"] = float(med36 or 0)
            elif seg == "C":
                # Relativer Vergleich Firma↔CPV-Markt. Der RELATIVE Abstand ist robust gegen den
                # Publikations-Lag (jüngste Fenster marktweit untererfasst — trifft Firma & Markt gleich),
                # die absolute Marktzahl wäre Lag-verseucht → wir zeigen nur den relativen Abstand.
                firm_pct = (v3 - v1) / v1 if v1 else 0.0
                seg_pct = ((sy3 or 0) - (sy1 or 0)) / sy1 if sy1 else None
                if market_on:  # nur behalten, wenn Firma stärker fällt als ihr Markt (§3)
                    if seg_pct is None or (sy1 or 0) < 5 or seg_pct <= firm_pct:
                        continue
                mk = (f" · fällt {round((seg_pct - firm_pct) * 100)} pp stärker als der Markt"
                      if seg_pct is not None else " · Markttrend unbekannt")
                f["badge"] = {"label": f"▼ −{v1-v3} Zuschläge", "cls": "s1", "spark": spark}
                f["line"] = f"{int(aw36)} Zuschläge/3J{mk}"; f["metric"] = v1 - v3
            elif seg == "D":
                if (n_recent or 0) < mkt_min:  # Feld muss noch aktiv sein (§4)
                    continue
                mo = con.execute(f"SELECT date_diff('month', DATE '{last}', DATE '{now}')").fetchone()[0] if last else None
                f["badge"] = {"label": f"⏸ seit {mo} Mon. still" if mo else "⏸ inaktiv", "cls": "none"}
                f["line"] = f"früher {int(v_old)} Zuschläge · zuletzt {str(last)[:7] if last else '?'} · Feld aktiv: {int(n_recent or 0)}/18M"
                f["metric"] = int(mo or 0)
            elif seg == "G":
                f["badge"] = {"label": f"▲ +{v3-v1} Zuschläge", "cls": "aktiv", "spark": spark}
                f["line"] = f"{int(aw36)} Zuschläge/3J · Median {_eur(med36)}"; f["metric"] = v3 - v1
            firmen.append(f)

    elif seg == "E":  # Verteidiger unter Druck — Auslauf lo–hi Monate, Summe ≥ min_vol, Wechselquote ≥ switch
        lo, hi = int(gp("lo", 6)), int(gp("hi", 18))
        min_vol, switch = gp("min_vol", 250000), gp("switch", 40) / 100.0
        # Rahmen-Quote = Anteil des auslaufenden VOLUMENS aus Rahmen-/wiederkehrenden Verträgen
        # (wiederkehrend = wird neu ausgeschrieben → echte Chance; Einmalauftrag ist danach weg).
        rows = con.execute(f"""
          WITH agg AS (
            SELECT incumbent_group_id identity_id, count(*) n, sum(coalesce(value_eur,0)) vol,
                   min(contract_end) naechstes, mode(substr(cpv_code,1,4)) cpv4,
                   sum(coalesce(value_eur,0)) FILTER(WHERE contract_kind IN ('framework','recurring')) rahmen_vol
            FROM {LE} WHERE incumbent_group_id IN (SELECT identity_id FROM belegt)
              AND months_to_expiry BETWEEN {lo} AND {hi}
            GROUP BY 1 HAVING sum(coalesce(value_eur,0)) >= {min_vol}),
          named AS (SELECT x.identity_id, x.n, x.vol, x.naechstes, x.cpv4, x.rahmen_vol, sr.switch_rate,
                           sx.rahmen_vol AS ov_rahmen, sx.tot_vol36 AS ov_tot,
                           {nm} firmenname, el.plz, el.ort, el.email, el.phone
                    FROM agg x LEFT JOIN eloc el ON el.identity_id=x.identity_id
                    LEFT JOIN {MS} sr ON sr.cpv_class = x.cpv4
                    LEFT JOIN sa sx ON sx.identity_id = x.identity_id)
          SELECT identity_id, firmenname, plz, ort, email, phone, n, vol, naechstes, switch_rate, rahmen_vol, ov_rahmen, ov_tot
          FROM named WHERE firmenname IS NOT NULL AND {_KONSORTIUM} AND coalesce(switch_rate,0) >= {switch}
          ORDER BY vol DESC LIMIT {fetch}""").fetchall()
        for r in rows:
            f = base(r[0], r[1]); f.update({"plz": r[2], "ort": r[3], "email": r[4], "phone": r[5],
                                            "medWert": None, "wins36": 0, "rahmenQuote": _rq(r[11], r[12])})
            nd = r[8].strftime("%m/%Y") if r[8] and hasattr(r[8], "strftime") else "?"
            sr = f" · Wechselquote {round((r[9] or 0)*100)}%" if r[9] is not None else ""
            rq_exp = round((r[10] or 0) / r[7] * 100) if r[7] else 0   # Rahmen-Anteil am AUSLAUF-Volumen
            f["badge"] = {"label": f"◷ {_eur(r[7])} Auslauf · {rq_exp}% Rahmen", "cls": "s2"}
            f["line"] = f"{r[6]} Verträge laufen aus · nächstes {nd}{sr}"; f["metric"] = float(r[7] or 0)
            firmen.append(f)

    elif seg == "F":  # Frische Verlierer — Verlust ≤ months, ≥ min_vol
        months, min_vol = int(gp("months", 6)), gp("min_vol", 100000)
        rows = con.execute(f"""
          WITH pred AS (SELECT se.predecessor, se.successor, ei.identity_id loser FROM {SE} se
              JOIN {PE} pp ON pp.notice_id=se.predecessor AND pp.role='winner'
              JOIN {EI} ei ON ei.entity_id=pp.entity_id
              WHERE se.displaced=TRUE AND ei.identity_id IN (SELECT identity_id FROM belegt)),
          loss AS (
            SELECT pr.loser identity_id, n.award_date dt, q.final_value_clean val, n.title,
              (SELECT arg_max(e.canonical_name,e.confidence) FROM {PE} pw JOIN {EN} e ON e.entity_id=pw.entity_id
               WHERE pw.notice_id=pr.successor AND pw.role='winner') gewinner
            FROM pred pr JOIN read_parquet('{SN}',hive_partitioning=1) n ON n.notice_id=pr.successor
            LEFT JOIN {QU} q ON q.notice_id=pr.successor
            WHERE n.award_date > {w(months)} AND coalesce(q.final_value_clean,0) >= {min_vol}
              AND NOT EXISTS(SELECT 1 FROM {PE} ps JOIN {EI} es ON es.entity_id=ps.entity_id
                             WHERE ps.notice_id=pr.successor AND ps.role='winner' AND es.identity_id=pr.loser)),
          best AS (SELECT identity_id, max(val) val, arg_max(gewinner,val) gewinner,
                          arg_max(title,val) titel, count(*) n, max(dt) dt FROM loss GROUP BY 1),
          named AS (SELECT x.*, {nm} firmenname, el.plz, el.ort, el.email, el.phone,
                           sx.rahmen_vol AS ov_rahmen, sx.tot_vol36 AS ov_tot
                    FROM best x LEFT JOIN eloc el ON el.identity_id=x.identity_id
                    LEFT JOIN sa sx ON sx.identity_id = x.identity_id)
          SELECT identity_id, firmenname, plz, ort, email, phone, val, gewinner, titel, n, dt, ov_rahmen, ov_tot
          FROM named WHERE firmenname IS NOT NULL AND {_KONSORTIUM}
          ORDER BY val DESC LIMIT {fetch}""").fetchall()
        for r in rows:
            f = base(r[0], r[1]); f.update({"plz": r[2], "ort": r[3], "email": r[4], "phone": r[5],
                                            "medWert": None, "wins36": 0, "rahmenQuote": _rq(r[11], r[12])})
            f["badge"] = {"label": f"▼ {_eur(r[6])} verloren", "cls": "s1"}
            f["line"] = f"an {Z.clean_name(r[7]) if r[7] else '?'}" + (f" · +{int(r[9])-1} weitere" if r[9] and r[9] > 1 else "")
            f["metric"] = float(r[6] or 0)
            firmen.append(f)

    # ── §8 Einmalzuordnung: Firma erscheint nur im höchstprior. Segment; Rest als „weitere_segmente".
    # Membership der ANDEREN Segmente aus `mem` (Default-Schwellen); das aktive Segment gilt als erfüllt,
    # weil die Firma bereits Kandidat ist. Fällt sie auch in ein höherpriorisiertes Segment → dort zeigen.
    ids = [f["id"] for f in firmen]
    memd = {}
    if ids:
        mrows = con.execute(
            "SELECT identity_id, fF,fE,fC,fA,fD,fG,fB FROM mem WHERE identity_id IN (SELECT unnest(?::VARCHAR[]))",
            [ids]).fetchall()
        memd = {r[0]: dict(zip(["F", "E", "C", "A", "D", "G", "B"], r[1:])) for r in mrows}
    min_rahmen = int(gp("min_rahmen", 0))
    out = []
    for f in firmen:
        if min_rahmen > 0 and (f.get("rahmenQuote") is None or f["rahmenQuote"] < min_rahmen):
            continue  # universeller Rahmen-Quote-Filter (gilt in jedem Segment)
        fl = dict(memd.get(f["id"], {}))
        fl[seg] = True  # Kandidat des aktiven Segments
        primary = next((k for k in _PRIORITY if fl.get(k)), seg)
        if dedup and primary != seg:
            continue
        f["weitere"] = [{"key": k, "label": _SEG_TAB[k]} for k in _PRIORITY if fl.get(k) and k != seg]
        out.append(f)
        if len(out) >= int(limit):
            break
    firmen = out

    return {"stichtag": str(now), "segment": seg, "label": SEGMENTS[seg][0],
            "hint": SEGMENTS[seg][1], "controls": _CONTROLS[seg] + [_RAHMEN_CTRL], "geo": geo_label,
            "n": len(firmen), "firmen": firmen}


def detail(identity_id):
    con = _con()
    now = Z.build_population(con, adhoc={"name": None, "plz": None, "ort": None})  # baut base/eloc + Signal-Quellen
    # base enthält alle belegten Identitäten (kein Filter) → identity muss darin sein
    prof = con.execute("SELECT firmenname, sitz_plz, sitz_ort, email, phone, wins36 FROM base WHERE identity_id=?",
                       [identity_id]).fetchone()
    if not prof:
        return {"error": "Firma nicht gefunden (keine belegten Zuschläge)", "id": identity_id}
    LE = f"read_parquet('{G}/lead_export.parquet')"
    # Auslaufende Verträge (Amtsinhaber) — der konkrete Gesprächsaufhänger. Rahmen/wiederkehrend
    # zuerst (wertvoll), + TED-Link zur offiziellen Bekanntmachung zum Nachschauen.
    exp = con.execute(f"""
      SELECT le.title, le.buyer_name, le.value_eur, le.contract_end, le.months_to_expiry,
             le.value_source, le.contract_kind, n.ted_url, le.incumbent_since_year
      FROM {LE} le LEFT JOIN read_parquet('{SN}', hive_partitioning=1) n ON n.notice_id = le.lead_id
      WHERE le.incumbent_group_id=? AND le.months_to_expiry BETWEEN 0 AND 24
      ORDER BY (le.contract_kind IN ('framework','recurring')) DESC, le.months_to_expiry LIMIT 25""",
      [identity_id]).fetchall()
    # Jüngste Verluste (aus den in compute_signals gebauten losses — hier direkt neu, mit Käufer)
    PE = f"read_parquet('{G}/party_entity.parquet')"
    EI = f"read_parquet('{G}/entity_identity.parquet')"
    EN = f"read_parquet('{G}/entities.parquet')"
    SE = f"read_parquet('{G}/succession_events.parquet')"
    QU = f"read_parquet('{G}/quality.parquet')"
    DP = f"read_parquet('{G}/dim_plz.parquet')"
    LG = f"read_parquet('{G}/lead_geo.parquet')"

    # ── Regionalität: Sitz-Koordinate + Konzentration der Gewinne. Eine Firma, die fast nur in EINER
    # Region gewinnt (z. B. Bauunternehmen), soll regionale Leads/Wettbewerber sehen — kein Stuttgart
    # für einen Betrieb aus Hamm. Firmen mit breitem Footprint bleiben deutschlandweit.
    seat = con.execute(f"SELECT dp.lat, dp.lon, el.nuts FROM eloc el JOIN {DP} dp ON dp.plz = el.plz "
                       f"WHERE el.identity_id=? LIMIT 1", [identity_id]).fetchone()
    seat_lat = float(seat[0]) if seat and seat[0] is not None else None
    seat_lon = float(seat[1]) if seat and seat[1] is not None else None
    regrow = con.execute(f"""SELECT substr(n.performance_nuts,1,3) n1, count(*) c
      FROM {PE} p JOIN {EI} ei ON ei.entity_id=p.entity_id
      JOIN read_parquet('{SN}', hive_partitioning=1) n ON n.notice_id=p.notice_id
      WHERE p.role='winner' AND ei.identity_id=? AND n.performance_nuts LIKE 'DE%'
      GROUP BY 1 ORDER BY 2 DESC""", [identity_id]).fetchall()
    tot_reg = sum(r[1] for r in regrow)
    top_nuts1 = regrow[0][0] if regrow else None
    top_share = (regrow[0][1] / tot_reg) if tot_reg else 0.0
    is_regional = bool(seat_lat is not None and tot_reg >= 5 and top_share >= 0.55)
    RADIUS_KM = 150

    def _hav(lat_col, lon_col):  # Haversine vom Firmensitz zur (Leistungs-)Koordinate
        # WICHTIG: bei fehlender Koordinate NULL zurückgeben — sonst macht DuckDBs least(1.0, NULL)=1.0
        # daraus acos(1)=0, und Leads ohne Geo würden als „0 km" fälschlich in den Umkreis rutschen.
        inner = (f"sin(radians({seat_lat}))*sin(radians({lat_col})) + "
                 f"cos(radians({seat_lat}))*cos(radians({lat_col}))*cos(radians({lon_col}-({seat_lon})))")
        return f"(CASE WHEN {lat_col} IS NULL OR {lon_col} IS NULL THEN NULL ELSE 6371*acos(least(1.0, {inner})) END)"

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
    # Jüngste Zuschläge — damit das Detail auch ohne akutes Signal nie leer ist ("was macht die Firma")
    recent = con.execute(f"""
      SELECT n.title, q.final_value_clean, year(coalesce(n.award_date, n.publication_date)) AS jahr,
             (SELECT arg_max(e.canonical_name, e.confidence) FROM {PE} pb JOIN {EN} e ON e.entity_id=pb.entity_id
              WHERE pb.notice_id=p.notice_id AND pb.role='buyer') AS buyer, n.ted_url
      FROM {PE} p JOIN {EI} ei ON ei.entity_id=p.entity_id
      JOIN read_parquet('{SN}', hive_partitioning=1) n ON n.notice_id=p.notice_id
      LEFT JOIN {QU} q ON q.notice_id=p.notice_id
      WHERE p.role='winner' AND ei.identity_id=?
      ORDER BY coalesce(n.award_date, n.publication_date) DESC LIMIT 12""", [identity_id]).fetchall()

    # Hauptwettbewerber (INTERN unverblurrt — "gib mir die Pro-Infos frei"): wer verdrängt die Firma
    # am häufigsten (head_to_head), sonst Top-Anbieter im dominanten CPV-Feld. Mit seinen Auslauf-Verträgen.
    HH = f"read_parquet('{G}/head_to_head.parquet')"
    CS = f"read_parquet('{G}/contractor_stats.parquet')"
    # Nur BELEGTE Identitäten als Wettbewerber (HR/nationale Kennung) — sonst landet
    # Namens-Rauschen wie "Info@sbs-Business.com" als "Hauptwettbewerber".
    belegt = (f"(SELECT DISTINCT ei2.identity_id FROM {EI} ei2 JOIN {EN} e2 ON e2.entity_id=ei2.entity_id "
              "WHERE e2.method IN ('handelsregister_exakt','ted_nationalid') "
              "AND e2.canonical_name NOT LIKE '%@%' AND length(e2.canonical_name) > 4)")
    # 1. Echter Wettbewerber: hat die Firma real verdrängt (head_to_head) — geografieunabhängig belastbar.
    comp = con.execute(f"""
      WITH mine AS (SELECT entity_id FROM {EI} WHERE identity_id=?)
      SELECT wi.identity_id FROM {HH} h JOIN {EI} wi ON wi.entity_id=h.winner_entity
      WHERE h.loser_entity IN (SELECT entity_id FROM mine) AND wi.identity_id<>?
        AND wi.identity_id IN {belegt}
      GROUP BY 1 ORDER BY sum(h.displacements) DESC LIMIT 1""", [identity_id, identity_id]).fetchone()
    comp_basis = "head_to_head" if comp else None
    if not comp:
        # 2. Fallback = Top-Anbieter im Kern-CPV. **Auf CPV-6 geschärft** (nicht CPV-4/cpv_class):
        # sonst gilt eine Aufzugsfirma als „Konkurrent" eines Elektrikers, nur weil beide in CPV 4531
        # liegen. Dominante CPV-6 der Firma (ohne Divisions-Sammelcodes), dann Anbieter, die genau
        # diese CPV-6 gewonnen haben — bei REGIONALEN Firmen im selben Bundesland (NUTS1).
        dom6 = con.execute(f"""SELECT substr(n.cpv_main,1,6) c FROM {PE} p JOIN {EI} ei ON ei.entity_id=p.entity_id
          JOIN read_parquet('{SN}', hive_partitioning=1) n ON n.notice_id=p.notice_id
          WHERE p.role='winner' AND ei.identity_id=? AND n.cpv_main IS NOT NULL AND substr(n.cpv_main,3,4)<>'0000'
          GROUP BY 1 ORDER BY count(*) DESC LIMIT 1""", [identity_id]).fetchone()
        region = top_nuts1 if is_regional else None

        def _comp6(with_region):
            reg_clause = "AND substr(el.nuts,1,3)=?" if with_region else ""
            reg_join = "JOIN eloc el ON el.identity_id=ei.identity_id" if with_region else ""
            params = [dom6[0], identity_id] + ([region] if with_region else [])
            return con.execute(f"""SELECT ei.identity_id FROM {PE} p JOIN {EI} ei ON ei.entity_id=p.entity_id
              JOIN read_parquet('{SN}', hive_partitioning=1) n ON n.notice_id=p.notice_id {reg_join}
              WHERE p.role='winner' AND substr(n.cpv_main,1,6)=? AND ei.identity_id<>? AND ei.identity_id IN {belegt}
                {reg_clause}
              GROUP BY 1 ORDER BY count(DISTINCT n.notice_id) DESC LIMIT 1""", params).fetchone()

        if dom6 and region:
            comp = _comp6(True)
            comp_basis = "region" if comp else None
            if not comp:                       # kein regionaler CPV-6-Wettbewerber → national, ehrlich beschriftet
                comp = _comp6(False); comp_basis = "cpv_national" if comp else None
        elif dom6:                             # breit aufgestellte Firma → nationaler CPV-6-Top-Anbieter
            comp = _comp6(False)
            comp_basis = "cpv_national" if comp else None
    wett = None
    if comp:
        wid = comp[0]
        wname = con.execute(f"SELECT arg_max(e.canonical_name, e.confidence) FROM {EI} ei JOIN {EN} e ON e.entity_id=ei.entity_id WHERE ei.identity_id=? AND e.canonical_name NOT LIKE '%@%'", [wid]).fetchone()[0]
        wexp = con.execute(f"""SELECT le.title, le.buyer_name, le.value_eur, le.contract_end, le.contract_kind, n.ted_url
          FROM {LE} le LEFT JOIN read_parquet('{SN}', hive_partitioning=1) n ON n.notice_id=le.lead_id
          WHERE le.incumbent_group_id=? AND le.months_to_expiry BETWEEN 0 AND 24
          ORDER BY (le.contract_kind IN ('framework','recurring')) DESC, le.months_to_expiry LIMIT 8""", [wid]).fetchall()
        wett = {"name": Z.clean_name(wname), "id": wid, "basis": comp_basis,
                "expiring": [{"titel": w[0], "buyer": w[1], "vol": float(w[2]) if w[2] else None,
                              "ende": w[3].strftime("%m/%Y") if w[3] and hasattr(w[3], "strftime") else None,
                              "art": art_of(w[4])[0], "artcat": art_of(w[4])[1], "url": w[5]} for w in wexp]}
    # Ansprache-Kontext: Segment/Feld, KMU-Flag, Website, Schlüsselkunden (Top-Vergabestellen)
    NP = "read_parquet('" + str(ROOT / "data/silver/DE/notice_parties/*/*.parquet") + "', hive_partitioning=1)"
    BCH = f"read_parquet('{G}/buyer_contractor_history.parquet')"
    CL = f"read_parquet('{G}/dim_cpv_label.parquet')"
    meta = con.execute(f"""
      SELECT any_value(np.url) FILTER (WHERE np.url IS NOT NULL AND np.url NOT LIKE '%@%'),
             bool_or(coalesce(np.is_sme, FALSE))
      FROM {NP} np JOIN {PE} pe ON pe.notice_id=np.notice_id AND pe.role=np.role AND pe.seq=np.seq
      JOIN {EI} ei ON ei.entity_id=pe.entity_id WHERE np.role='winner' AND ei.identity_id=?""", [identity_id]).fetchone()
    seg = con.execute(f"""SELECT cl.label FROM {CS} cs JOIN {EI} ei ON ei.entity_id=cs.entity_id
      LEFT JOIN {CL} cl ON cl.cpv_code = cs.cpv_class || '0000'
      WHERE ei.identity_id=? GROUP BY 1 ORDER BY sum(cs.total_wins) DESC LIMIT 1""", [identity_id]).fetchone()
    topbuyers = con.execute(f"""SELECT en.canonical_name, sum(b.total_wins) w, max(b.last_win_year) ly
      FROM {BCH} b JOIN {EI} m ON m.entity_id=b.contractor_entity_id AND m.identity_id=?
      JOIN {EN} en ON en.entity_id=b.buyer_entity_id WHERE en.canonical_name IS NOT NULL
      GROUP BY 1 ORDER BY 2 DESC LIMIT 4""", [identity_id]).fetchall()

    # Top-Potenzial-Leads: OFFENE Ausschreibungen in den KERN-Feldern der Firma. Match auf CPV-6-Steller
    # (scharf), NICHT nur CPV-4 — und ohne die Divisions-Sammelcodes (XX000000, z. B. 45000000
    # „Bauarbeiten"), sonst matcht ein Tiefbauer auf „Holztüren", nur weil beide generisch 45000000
    # getaggt sind. Gewichtet nach Kompetenz-Zentralität; CPV-4-Fachbereich nur als Auffüll-Fallback.
    CL2 = f"read_parquet('{G}/dim_cpv_label.parquet')"
    NONGEN = "substr(n.cpv_main,3,4) <> '0000'"   # keine reinen Divisions-Sammelcodes
    cpv6 = con.execute(f"""SELECT substr(n.cpv_main,1,6) c, count(*) w FROM {PE} p
      JOIN {EI} ei ON ei.entity_id=p.entity_id
      JOIN read_parquet('{SN}', hive_partitioning=1) n ON n.notice_id=p.notice_id
      WHERE p.role='winner' AND ei.identity_id=? AND n.cpv_main IS NOT NULL AND {NONGEN}
      GROUP BY 1 HAVING count(*) >= 1 ORDER BY 2 DESC LIMIT 12""", [identity_id]).fetchall()
    cpv4 = con.execute(f"""SELECT substr(n.cpv_main,1,4) c, count(*) w FROM {PE} p
      JOIN {EI} ei ON ei.entity_id=p.entity_id
      JOIN read_parquet('{SN}', hive_partitioning=1) n ON n.notice_id=p.notice_id
      WHERE p.role='winner' AND ei.identity_id=? AND n.cpv_main IS NOT NULL
      GROUP BY 1 HAVING count(*) >= 2 ORDER BY 2 DESC LIMIT 6""", [identity_id]).fetchall()

    def _fit(rows):
        return ",".join(f"('{r[0].replace(chr(39),'')}',{int(r[1])})" for r in rows) if rows else None
    cpv6_vals, cpv4_vals = _fit(cpv6), _fit(cpv4)

    def _leads_query(regional, level, fit_vals):
        dist = _hav("coalesce(lg.perf_lat,lg.lat)", "coalesce(lg.perf_lon,lg.lon)") if seat_lat is not None else "NULL"
        where = f"AND {dist} <= {RADIUS_KM}" if regional else ""
        order = (f"fit.w DESC, {dist} ASC NULLS LAST, le.value_eur DESC NULLS LAST" if regional
                 else "fit.w DESC, le.value_eur DESC NULLS LAST")
        return con.execute(f"""
          WITH fit(c, w) AS (VALUES {fit_vals})
          SELECT le.title, le.buyer_name, le.buyer_town, le.value_eur, le.deadline_date, le.days_to_deadline,
                 coalesce(nt.ted_url, le.documents_url, le.source_url) AS url, le.contract_kind, cl.label AS seg,
                 {dist} AS dist_km, nt.ted_url AS ted, le.documents_url AS doku
          FROM {LE} le JOIN fit ON fit.c = substr(le.cpv_code,1,{int(level)})
          LEFT JOIN {CL2} cl ON cl.cpv_code = substr(le.cpv_code,1,4) || '0000'
          LEFT JOIN {LG} lg ON lg.lead_id = le.lead_id
          LEFT JOIN read_parquet('{SN}', hive_partitioning=1) nt ON nt.notice_id = le.lead_id
          WHERE le.phase='open' AND (le.days_to_deadline IS NULL OR le.days_to_deadline >= 0) {where}
          QUALIFY row_number() OVER (PARTITION BY lower(trim(le.title))
                                     ORDER BY le.value_eur DESC NULLS LAST) = 1
          ORDER BY {order} LIMIT 5""").fetchall()

    # Priorität für REGIONALE Firmen: NÄHE vor Feldschärfe —
    #   CPV6 im Umkreis → CPV4 im Umkreis → CPV6 national → CPV4 national.
    # Ein Regionalbetrieb sieht lieber „etwas breiteres Feld vor der Haustür" als „exaktes Feld 400 km weg".
    # Breit aufgestellte Firmen (kein Sitz/keine Konzentration) gehen direkt national. Erste mit ≥3, sonst größte.
    plan = []
    if is_regional:
        if cpv6_vals: plan.append((6, cpv6_vals, True))
        if cpv4_vals: plan.append((4, cpv4_vals, True))
        if cpv6_vals: plan.append((6, cpv6_vals, False))
        if cpv4_vals: plan.append((4, cpv4_vals, False))
    else:
        if cpv6_vals: plan.append((6, cpv6_vals, False))
        if cpv4_vals: plan.append((4, cpv4_vals, False))
    leads, best_meta = [], None
    for lvl, vals, regional in plan:
        r = _leads_query(regional, lvl, vals)
        if len(r) >= 3:
            leads, best_meta = r, (lvl, regional); break
        if len(r) > len(leads):
            leads, best_meta = r, (lvl, regional)
    if best_meta:
        lvl, regional = best_meta
        geo = f"Umkreis {RADIUS_KM} km" if regional else "deutschlandweit"
        leads_scope = f"{geo} · {'CPV-6-genau' if lvl == 6 else 'Fachbereich (CPV-4)'}"
    else:
        leads_scope = "deutschlandweit"
    return {
        "id": identity_id, "name": Z.clean_name(prof[0]), "plz": prof[1], "ort": prof[2],
        "email": prof[3], "phone": prof[4], "wins36": int(prof[5] or 0),
        "website": meta[0] if meta else None, "kmu": bool(meta[1]) if meta else False,
        "segment": Z.clean_name(seg[0]) if seg and seg[0] else None,
        "topBuyers": [{"name": Z.clean_name(t[0]), "wins": int(t[1]), "letztes": int(t[2]) if t[2] else None} for t in topbuyers],
        "leadsScope": leads_scope,
        "leads": [{"titel": l[0], "buyer": l[1], "ort": l[2],
                   "vol": float(l[3]) if l[3] else None,
                   "frist": l[4].strftime("%d.%m.%Y") if l[4] and hasattr(l[4], "strftime") else None,
                   "tage": int(l[5]) if l[5] is not None else None, "url": l[6],
                   "art": art_of(l[7])[0], "artcat": art_of(l[7])[1], "seg": l[8],
                   "dist": round(l[9]) if l[9] is not None else None,
                   "ted": l[10], "doku": l[11]} for l in leads],
        "expiring": [{"titel": e[0], "buyer": e[1], "vol": float(e[2]) if e[2] else None,
                      "ende": e[3].strftime("%m/%Y") if e[3] and hasattr(e[3], "strftime") else None,
                      "mte": int(e[4]) if e[4] is not None else None,
                      "vsrc": e[5], "art": art_of(e[6])[0], "artcat": art_of(e[6])[1], "url": e[7],
                      "seit": int(e[8]) if e[8] else None} for e in exp],
        "losses": [{"titel": l[0], "vol": float(l[1]) if l[1] else None,
                    "datum": str(l[2]) if l[2] else None, "gewinner": Z.clean_name(l[3]) if l[3] else None}
                   for l in losses],
        "recent": [{"titel": r[0], "vol": float(r[1]) if r[1] else None,
                    "jahr": int(r[2]) if r[2] else None, "buyer": r[3], "url": r[4]} for r in recent],
        "wettbewerber": wett,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", action="store_true")
    ap.add_argument("--detail")
    ap.add_argument("--segment", choices=list(SEGMENTS.keys()))
    ap.add_argument("--params", help="Kohorten-Knöpfe als k:v,k:v (überschreibt _CONTROLS-Defaults)")
    ap.add_argument("--plz"); ap.add_argument("--ort"); ap.add_argument("--name"); ap.add_argument("--radius"); ap.add_argument("--nuts")
    a = ap.parse_args()
    try:
        if a.segment:
            pd = {}
            if a.params:
                for kv in a.params.split(","):
                    if ":" in kv:
                        k, v = kv.split(":", 1); pd[k.strip()] = v.strip()
            geo = {"plz": a.plz, "radius": a.radius, "ort": a.ort, "nuts": a.nuts}
            out = segment(a.segment, params=pd, geo=geo)
        else:
            out = detail(a.detail) if a.detail else search(a.plz, a.ort, a.name, a.radius)
    except Exception as e:  # noqa: BLE001
        out = {"error": str(e)[:300]}
    print(json.dumps(out, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
