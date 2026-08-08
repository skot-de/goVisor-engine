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


# Vertragsart-Marker: Rahmen/wiederkehrend = wiederkehrendes Volumen (wertvoll für Ansprache),
# Einmalauftrag = nach Auslauf erledigt (Sven: "Heizung aufbauen — da kann man nichts draus machen").
_ART = {"framework": "Rahmen", "recurring": "wiederkehrend", "one_off_works": "Einmalauftrag"}


def art_of(kind):
    return _ART.get(kind)


def search(plz=None, ort=None, name=None):
    if not (plz or ort or name):
        return {"error": "Bitte PLZ, Ort oder Name angeben"}
    con = _con()
    now = Z.build_population(con, adhoc={"plz": plz, "ort": ort, "name": name})
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
    comp = con.execute(f"""
      WITH mine AS (SELECT entity_id FROM {EI} WHERE identity_id=?)
      SELECT wi.identity_id FROM {HH} h JOIN {EI} wi ON wi.entity_id=h.winner_entity
      WHERE h.loser_entity IN (SELECT entity_id FROM mine) AND wi.identity_id<>?
        AND wi.identity_id IN {belegt}
      GROUP BY 1 ORDER BY sum(h.displacements) DESC LIMIT 1""", [identity_id, identity_id]).fetchone()
    if not comp:
        dom = con.execute(f"""SELECT cs.cpv_class FROM {CS} cs JOIN {EI} ei ON ei.entity_id=cs.entity_id
          WHERE ei.identity_id=? GROUP BY 1 ORDER BY sum(cs.total_wins) DESC LIMIT 1""", [identity_id]).fetchone()
        comp = con.execute(f"""SELECT ei.identity_id FROM {CS} cs JOIN {EI} ei ON ei.entity_id=cs.entity_id
          WHERE cs.cpv_class=? AND ei.identity_id<>? AND ei.identity_id IN {belegt}
          GROUP BY 1 ORDER BY sum(cs.total_wins) DESC LIMIT 1""",
          [dom[0], identity_id]).fetchone() if dom else None
    wett = None
    if comp:
        wid = comp[0]
        wname = con.execute(f"SELECT arg_max(e.canonical_name, e.confidence) FROM {EI} ei JOIN {EN} e ON e.entity_id=ei.entity_id WHERE ei.identity_id=? AND e.canonical_name NOT LIKE '%@%'", [wid]).fetchone()[0]
        wexp = con.execute(f"""SELECT le.title, le.buyer_name, le.value_eur, le.contract_end, le.contract_kind, n.ted_url
          FROM {LE} le LEFT JOIN read_parquet('{SN}', hive_partitioning=1) n ON n.notice_id=le.lead_id
          WHERE le.incumbent_group_id=? AND le.months_to_expiry BETWEEN 0 AND 24
          ORDER BY (le.contract_kind IN ('framework','recurring')) DESC, le.months_to_expiry LIMIT 8""", [wid]).fetchall()
        wett = {"name": Z.clean_name(wname), "id": wid,
                "expiring": [{"titel": w[0], "buyer": w[1], "vol": float(w[2]) if w[2] else None,
                              "ende": w[3].strftime("%m/%Y") if w[3] and hasattr(w[3], "strftime") else None,
                              "art": art_of(w[4]), "url": w[5]} for w in wexp]}
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
    return {
        "id": identity_id, "name": Z.clean_name(prof[0]), "plz": prof[1], "ort": prof[2],
        "email": prof[3], "phone": prof[4], "wins36": int(prof[5] or 0),
        "website": meta[0] if meta else None, "kmu": bool(meta[1]) if meta else False,
        "segment": Z.clean_name(seg[0]) if seg and seg[0] else None,
        "topBuyers": [{"name": Z.clean_name(t[0]), "wins": int(t[1]), "letztes": int(t[2]) if t[2] else None} for t in topbuyers],
        "expiring": [{"titel": e[0], "buyer": e[1], "vol": float(e[2]) if e[2] else None,
                      "ende": e[3].strftime("%m/%Y") if e[3] and hasattr(e[3], "strftime") else None,
                      "mte": int(e[4]) if e[4] is not None else None,
                      "vsrc": e[5], "art": art_of(e[6]), "url": e[7],
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
