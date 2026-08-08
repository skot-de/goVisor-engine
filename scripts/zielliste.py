#!/usr/bin/env python3
"""Zielliste für die Erstansprache (govisor-zielliste-spec.md) — INTERNES Vertriebstool.

Priorisiert Zielunternehmen nach nachgewiesenem *Schmerz* (fünf Signale), nicht nach Größe.
Läuft als Batch über ALLE Identitäten (dieselben Aggregate wie #25, nur über den ganzen Bestand).
Zusätzlich ein Ad-hoc-Modus: eine Firma gezielt per Name (+ Stadt) auswerten.

Einheit ist die **Identität** (`entity_identity`, Konzernmutter — keine Doppelansprache).

Aufruf:
  python3 scripts/zielliste.py [--region DEA] [--limit N]      # Batch (Stufe 1: Grundgesamtheit)
  python3 scripts/zielliste.py --name "Klostermann" [--ort Hamm]   # Ad-hoc-Suche

Diese Fassung: Stufe 1 (harte Filter §2) + Grundgesamtheit messen. Signale folgen gestaffelt.
"""
import argparse
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
G = str(ROOT / "data/gold/DE")
SN = str(ROOT / "data/silver/DE/notices/*/*.parquet")

# Harte Filter (§2)
MIN_WINS_36M = 5
MIN_AVG_VALUE = 100_000
MIN_REAL_VALUE_SHARE = 0.50
BELEGT_METHODS = ("handelsregister_exakt", "ted_nationalid")   # ≈ entity_confidence=confirmed (Proxy)

NUTS1 = {"DE1": "Baden-Württemberg", "DE2": "Bayern", "DE3": "Berlin", "DE4": "Brandenburg",
         "DE5": "Bremen", "DE6": "Hamburg", "DE7": "Hessen", "DE8": "Meck.-Vorpommern",
         "DE9": "Niedersachsen", "DEA": "Nordrhein-Westfalen", "DEB": "Rheinland-Pfalz",
         "DEC": "Saarland", "DED": "Sachsen", "DEE": "Sachsen-Anhalt", "DEF": "Schleswig-Holstein",
         "DEG": "Thüringen"}


def con_now(con):
    return con.execute(f"SELECT max(publication_date) FROM read_parquet('{SN}', hive_partitioning=1) "
                       f"WHERE publication_date <= CURRENT_DATE").fetchone()[0]


def clean_name(s):
    """Geparster Adress-Müll im Namen (…Ort:/NUTS-Code:/Postleitzahl:) abschneiden."""
    if not s:
        return s
    import re
    return re.split(r"\s*(?:Ort:|NUTS-Code:|Postleitzahl:|Land:)", s)[0].strip()


def build_population(con, region=None, adhoc=None):
    """Grundgesamtheit nach §2: belegte Identitäten, ≥5 Zuschläge/36M, Ø≥100k, ≥50% echter Wert.

    `region` = NUTS-Präfix des ECHTEN Firmensitzes (eloc; Start NRW=DEA).
    `adhoc` = {name?, plz?, ort?} → Ad-hoc-Suche ohne die harten Batch-Filter.
    Baut TEMP TABLE `pop`; gibt den Stichtag zurück.
    """
    EI = f"read_parquet('{G}/entity_identity.parquet')"
    EN = f"read_parquet('{G}/entities.parquet')"
    PE = f"read_parquet('{G}/party_entity.parquet')"
    QU = f"read_parquet('{G}/quality.parquet')"
    now = con_now(con)

    # belegte Identitäten (mind. eine Entity über HR/national-id aufgelöst)
    con.execute(f"""CREATE OR REPLACE TEMP TABLE belegt AS
      SELECT DISTINCT ei.identity_id
      FROM {EI} ei JOIN {EN} e ON e.entity_id = ei.entity_id
      WHERE e.method IN {BELEGT_METHODS}""")

    # Gewinner-Zuschläge je Identität mit Wert + Region + Datum.
    # Wert = quality.final_value_clean (plausibilitätsbereinigt + EUR, gedeckelt bei 1 Mrd) —
    # die rohe final_value trägt Sentinels/absurde Werte (max 7e19) und würde die Volumen-
    # gewichtung der Signale kippen (Sven: auffällige Aggregate = Warnsignal).
    con.execute(f"""CREATE OR REPLACE TEMP TABLE w AS
      SELECT ei.identity_id, p.notice_id,
             substr(n.performance_nuts,1,3) AS nuts1,
             coalesce(n.award_date, n.publication_date) AS dt,
             q.final_value_clean AS val
      FROM {PE} p
      JOIN {EI} ei ON ei.entity_id = p.entity_id
      JOIN read_parquet('{SN}', hive_partitioning=1) n ON n.notice_id = p.notice_id
      LEFT JOIN {QU} q ON q.notice_id = p.notice_id
      WHERE p.role='winner' AND ei.identity_id IN (SELECT identity_id FROM belegt)""")

    # Aggregate je Identität über die letzten 36 Monate
    con.execute(f"""CREATE OR REPLACE TEMP TABLE agg AS
      SELECT identity_id,
             count(DISTINCT notice_id) FILTER (WHERE dt >= (DATE '{now}' - INTERVAL 36 MONTH)) AS wins36,
             count(*) FILTER (WHERE val IS NOT NULL AND val > 0) AS n_val,
             count(*) AS n_all,
             avg(val) FILTER (WHERE val IS NOT NULL AND val > 0) AS avg_val,
             median(val) FILTER (WHERE val IS NOT NULL AND val > 0) AS med_val,
             sum(val) FILTER (WHERE val IS NOT NULL AND val > 0
                              AND dt >= (DATE '{now}' - INTERVAL 36 MONTH)) AS vol36,
             mode(nuts1) FILTER (WHERE nuts1 LIKE 'DE_') AS haupt_nuts1
      FROM w GROUP BY 1""")

    build_entity_location(con)   # eloc: Sitz-PLZ/Ort/NUTS + Kontakt je Identität

    # Namen + Sitz je Identität (für pop + Ad-hoc-Suche wiederverwendet)
    con.execute(f"""CREATE OR REPLACE TEMP TABLE base AS
      SELECT a.*, en.name AS firmenname,
             el.plz AS sitz_plz, el.ort AS sitz_ort, el.nuts AS sitz_nuts, el.email, el.phone
      FROM agg a
      LEFT JOIN (
        SELECT ei.identity_id, arg_max(e.canonical_name, e.confidence) AS name
        FROM {EI} ei JOIN {EN} e ON e.entity_id=ei.entity_id GROUP BY 1) en
        ON en.identity_id = a.identity_id
      LEFT JOIN eloc el ON el.identity_id = a.identity_id""")

    if adhoc and adhoc.get("plz") and adhoc.get("radius"):
        # Umkreis-Suche: alle Firmen, deren Sitz-PLZ im Radius (km) um die Zentrums-PLZ liegt.
        # Haversine über dim_plz-Zentroide (GeoNames). Name-Filter bleibt optional kombinierbar.
        DP = f"read_parquet('{G}/dim_plz.parquet')"
        plz = "".join(ch for ch in str(adhoc["plz"]) if ch.isdigit())[:5]
        try:
            radius = max(1.0, min(200.0, float(adhoc["radius"])))
        except (TypeError, ValueError):
            radius = 25.0
        center = con.execute(f"SELECT lat, lon FROM {DP} WHERE plz=? LIMIT 1", [plz]).fetchone()
        if not center:
            con.execute("CREATE OR REPLACE TEMP TABLE pop AS SELECT * FROM base WHERE FALSE")
            return now
        clat, clon = float(center[0]), float(center[1])
        hav = (f"6371*acos(least(1.0, sin(radians({clat}))*sin(radians(dp.lat)) + "
               f"cos(radians({clat}))*cos(radians(dp.lat))*cos(radians(dp.lon-({clon})))))")
        name_cond = ""
        if adhoc.get("name"):
            name_cond = f"AND lower(b.firmenname) LIKE '%{adhoc['name'].lower().replace(chr(39), '')}%'"
        con.execute(f"""CREATE OR REPLACE TEMP TABLE pop AS
          SELECT b.* FROM base b JOIN {DP} dp ON dp.plz = b.sitz_plz
          WHERE b.sitz_plz IS NOT NULL AND {hav} <= {radius} {name_cond}""")
    elif adhoc:   # Ad-hoc: Treffer nach Name/PLZ/Ort, OHNE die harten Batch-Filter
        conds = []
        if adhoc.get("name"):
            conds.append(f"lower(firmenname) LIKE '%{adhoc['name'].lower()}%'")
        if adhoc.get("plz"):
            conds.append(f"sitz_plz LIKE '{adhoc['plz']}%'")
        if adhoc.get("ort"):
            # Wortgrenze statt Substring: "Hamm" trifft Hamm / Hamm-Uentrop / "Hamm (Westf.)",
            # aber NICHT Hammelburg / Hamminkeln (Sven: nur der 59er-Raum, nicht 97/46).
            o = adhoc["ort"].lower().replace("'", "''")
            conds.append("(lower(sitz_ort)='" + o + "' OR lower(sitz_ort) LIKE '" + o + "-%'"
                         " OR lower(sitz_ort) LIKE '" + o + " %' OR lower(sitz_ort) LIKE '" + o + "/%'"
                         " OR lower(sitz_ort) LIKE '" + o + "(%')")
        where = " AND ".join(conds) if conds else "TRUE"
        con.execute(f"CREATE OR REPLACE TEMP TABLE pop AS SELECT * FROM base WHERE {where}")
    else:       # Batch: harte Filter §2 + Region auf den Firmensitz
        region_clause = f"AND sitz_nuts LIKE '{region}%'" if region else ""
        con.execute(f"""CREATE OR REPLACE TEMP TABLE pop AS SELECT * FROM base
          WHERE wins36 >= {MIN_WINS_36M} AND avg_val >= {MIN_AVG_VALUE}
            AND n_all > 0 AND (n_val::DOUBLE / n_all) >= {MIN_REAL_VALUE_SHARE} {region_clause}""")
    return now


def build_entity_location(con):
    """`eloc`: Firmensitz (modale PLZ/Ort/NUTS) + Kontakt je Identität, aus silver/notice_parties
    (Gewinner-Party) über party_entity(notice_id,role,seq). 72 % der Gewinner tragen eine PLZ."""
    NP = "read_parquet('" + str(ROOT / "data/silver/DE/notice_parties/*/*.parquet") + "', hive_partitioning=1)"
    PE = f"read_parquet('{G}/party_entity.parquet')"
    EI = f"read_parquet('{G}/entity_identity.parquet')"
    # KONSISTENTES (PLZ,Ort,NUTS)-Paar: das häufigste zusammengehörige Tripel je Identität —
    # NICHT mode() je Spalte einzeln (das mischte PLZ aus einer, Ort aus anderer Notice → "Hamm/10…").
    con.execute(f"""CREATE OR REPLACE TEMP TABLE eloc AS
      WITH wp AS (
        SELECT ei.identity_id, np.postal_code AS plz, np.town AS ort, np.nuts AS nuts,
               np.email, np.phone
        FROM {NP} np
        JOIN {PE} pe ON pe.notice_id = np.notice_id AND pe.role = np.role AND pe.seq = np.seq
        JOIN {EI} ei ON ei.entity_id = pe.entity_id
        WHERE np.role = 'winner' AND np.postal_code IS NOT NULL),
      loc AS (
        SELECT identity_id, plz, ort, nuts, count(*) c,
               row_number() OVER (PARTITION BY identity_id ORDER BY count(*) DESC) rn
        FROM wp GROUP BY 1,2,3,4),
      contact AS (
        SELECT identity_id, any_value(email) FILTER (WHERE email IS NOT NULL) email,
               any_value(phone) FILTER (WHERE phone IS NOT NULL) phone
        FROM wp GROUP BY 1)
      SELECT l.identity_id, l.plz, l.ort, l.nuts, c.email, c.phone
      FROM loc l LEFT JOIN contact c USING (identity_id)
      WHERE l.rn = 1""")


def compute_signals(con, now):
    """S1 (frischer Verlust) + S2 (bevorstehender Auslauf) je Identität der Population.

    S1: war Vorgänger-Gewinner, wurde verdrängt (displaced), Nachfolge-Zuschlag ging an eine ANDERE
        Identität, in den letzten 12 Monaten. Volumengewichtet, Verlust < 3 Monate zählt doppelt.
    S2: hält als Amtsinhaber Verträge, die in 6–18 Monaten auslaufen (lead_export.incumbent_group_id),
        volumengewichtet; kurze Bindung (< 2 J) erhöht.
    """
    PE = f"read_parquet('{G}/party_entity.parquet')"
    EI = f"read_parquet('{G}/entity_identity.parquet')"
    SE = f"read_parquet('{G}/succession_events.parquet')"
    QU = f"read_parquet('{G}/quality.parquet')"
    LE = f"read_parquet('{G}/lead_export.parquet')"

    # ── S1: Verluste je Identität (predecessor-Gewinner der Population, verdrängt) ──
    con.execute(f"""CREATE OR REPLACE TEMP TABLE losses AS
      WITH pred_win AS (   -- Gewinner-Identität des Vorgänger-Zuschlags
        SELECT se.predecessor, se.successor, ei.identity_id AS loser
        FROM {SE} se
        JOIN {PE} pp ON pp.notice_id = se.predecessor AND pp.role='winner'
        JOIN {EI} ei ON ei.entity_id = pp.entity_id
        WHERE se.displaced = TRUE AND ei.identity_id IN (SELECT identity_id FROM pop))
      SELECT pw.loser AS identity_id, pw.successor,
             n.award_date AS loss_date, q.final_value_clean AS loss_val
      FROM pred_win pw
      JOIN read_parquet('{SN}', hive_partitioning=1) n ON n.notice_id = pw.successor
      LEFT JOIN {QU} q ON q.notice_id = pw.successor
      WHERE n.award_date >= (DATE '{now}' - INTERVAL 12 MONTH)
        -- Nachfolge ging NICHT an dieselbe Identität (echter Verlust)
        AND NOT EXISTS (
          SELECT 1 FROM {PE} ps JOIN {EI} es ON es.entity_id = ps.entity_id
          WHERE ps.notice_id = pw.successor AND ps.role='winner' AND es.identity_id = pw.loser)""")

    con.execute(f"""CREATE OR REPLACE TEMP TABLE s1 AS
      SELECT identity_id,
             count(*) AS verlorene_12m,
             sum(coalesce(loss_val,0)) AS verlust_vol,
             sum(coalesce(loss_val,0) * CASE WHEN loss_date >= (DATE '{now}' - INTERVAL 3 MONTH) THEN 2 ELSE 1 END) AS s1_raw,
             max(loss_date) AS letzter_verlust
      FROM losses GROUP BY 1""")

    # ── S2: bevorstehender Auslauf (Amtsinhaber = Identität, Ende in 6–18 Monaten) ──
    con.execute(f"""CREATE OR REPLACE TEMP TABLE s2 AS
      SELECT incumbent_group_id AS identity_id,
             count(*) AS auslauf_n,
             sum(coalesce(value_eur,0)) AS auslauf_vol,
             min(contract_end) AS naechstes_auslaufdatum,
             sum(coalesce(value_eur,0) * CASE WHEN incumbent_since_year >= {now.year - 2} THEN 1.5 ELSE 1 END) AS s2_raw
      FROM {LE}
      WHERE incumbent_group_id IN (SELECT identity_id FROM pop)
        AND months_to_expiry BETWEEN 6 AND 18
      GROUP BY 1""")

    # ── Zusammenführen + perzentil-normalisieren INNERHALB der Population (§4) ──
    con.execute(f"""CREATE OR REPLACE TEMP TABLE scored AS
      WITH j AS (
        SELECT p.*, coalesce(s1.s1_raw,0) AS s1_raw, coalesce(s1.verlorene_12m,0) AS verlorene_12m,
               coalesce(s1.verlust_vol,0) AS verlust_vol, s1.letzter_verlust,
               coalesce(s2.s2_raw,0) AS s2_raw, coalesce(s2.auslauf_n,0) AS auslauf_n,
               coalesce(s2.auslauf_vol,0) AS auslauf_vol, s2.naechstes_auslaufdatum
        FROM pop p
        LEFT JOIN s1 ON s1.identity_id = p.identity_id
        LEFT JOIN s2 ON s2.identity_id = p.identity_id)
      SELECT *,
             CASE WHEN s1_raw>0 THEN percent_rank() OVER (ORDER BY s1_raw) ELSE 0 END AS s1_norm,
             CASE WHEN s2_raw>0 THEN percent_rank() OVER (ORDER BY s2_raw) ELSE 0 END AS s2_norm
      FROM j""")
    # Score (Stufe 2: nur S1+S2; S3–S5 folgen)
    con.execute("""CREATE OR REPLACE TEMP TABLE ranked AS
      SELECT *, round(40*s1_norm + 30*s2_norm, 1) AS score,
             CASE WHEN 40*s1_norm >= 30*s2_norm THEN 'S1_verlust' ELSE 'S2_auslauf' END AS dominant_signal
      FROM scored ORDER BY score DESC""")


def measure(con, region):
    total_belegt = con.execute("SELECT count(*) FROM belegt").fetchone()[0]
    n_pop = con.execute("SELECT count(*) FROM pop").fetchone()[0]
    print(f"Belegte Identitäten gesamt: {total_belegt:,}")
    print(f"Grundgesamtheit nach harten Filtern"
          f"{f' (Region {region}={NUTS1.get(region,region)})' if region else ' (bundesweit)'}: {n_pop:,}")
    print("  (Spec-Ziel: 200–500 belastbare Treffer, < 10.000)")
    print("\nTop 12 nach Volumen 36M (Stichprobe zur Plausibilität):")
    rows = con.execute("""SELECT firmenname, wins36, round(avg_val) avg_val, round(vol36) vol36, haupt_nuts1
                          FROM pop ORDER BY vol36 DESC NULLS LAST LIMIT 12""").fetchall()
    for r in rows:
        nm = (r[0] or "?")[:42]
        print(f"  {nm:44s} {r[1]:>3} Zuschl · Ø {int(r[2] or 0):>10,} € · Vol36 {int(r[3] or 0):>13,} € · {r[4]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="DEA", help="NUTS1-Präfix der Hauptregion (Default DEA=NRW; '' = bundesweit)")
    ap.add_argument("--name", help="Ad-hoc: Firma per Name suchen")
    ap.add_argument("--plz", help="Ad-hoc: Sitz-PLZ (Präfix, z.B. 59071 oder 590)")
    ap.add_argument("--ort", help="Ad-hoc: Sitz-Stadt/Ort")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    con = duckdb.connect(); con.execute("SET threads=4")
    region = args.region or None

    if args.name or args.plz or args.ort:
        now = build_population(con, adhoc={"name": args.name, "plz": args.plz, "ort": args.ort})
        compute_signals(con, now)
        rows = con.execute("""SELECT firmenname, sitz_plz, sitz_ort, wins36, round(avg_val) avg_val,
                                     score, dominant_signal, verlorene_12m, round(verlust_vol) verlust_vol,
                                     auslauf_n, round(auslauf_vol) auslauf_vol, letzter_verlust,
                                     naechstes_auslaufdatum, email, phone, identity_id
                              FROM ranked ORDER BY score DESC, wins36 DESC LIMIT 40""").fetchall()
        q = " ".join(filter(None, [args.name, args.plz, args.ort]))
        print(f"Ad-hoc-Suche '{q}' — {len(rows)} Treffer (Stichtag {now}):\n")
        for r in rows:
            print(f"● {clean_name(r[0])}  [{r[1] or '—'} {r[2] or ''}]")
            print(f"    {r[3]} Zuschläge/36M · Ø {int(r[4] or 0):,} € · Score {r[5]} ({r[6]})")
            if r[7]: print(f"    S1 Verlust: {r[7]} Verträge / {int(r[8] or 0):,} € (letzter {r[11]})")
            if r[9]: print(f"    S2 Auslauf 6–18M: {r[9]} Verträge / {int(r[10] or 0):,} € (nächstes {r[12]})")
            kontakt = " · ".join(filter(None, [r[13], r[14]]))
            if kontakt: print(f"    Kontakt: {kontakt}")
            print(f"    id: {r[15]}")
        return 0

    now = build_population(con, region)
    print(f"Stichtag: {now}\n")
    measure(con, region)
    compute_signals(con, now)

    n_s1 = con.execute("SELECT count(*) FROM scored WHERE s1_raw>0").fetchone()[0]
    n_s2 = con.execute("SELECT count(*) FROM scored WHERE s2_raw>0").fetchone()[0]
    print(f"\nSignal-Abdeckung in der Population: S1 (Verlust) {n_s1} · S2 (Auslauf) {n_s2}")
    print("\nTop 15 nach Score (S1×40 + S2×30):")
    top = con.execute("""SELECT firmenname, score, dominant_signal, verlorene_12m, round(verlust_vol) verlust_vol,
                                auslauf_n, round(auslauf_vol) auslauf_vol
                         FROM ranked LIMIT 15""").fetchall()
    for r in top:
        nm = (r[0] or "?")[:38]
        print(f"  {r[1]:>5}  {nm:40s} {r[2]:11s} · Verlust {r[3]}/{int(r[4] or 0):,}€ · Auslauf {r[5]}/{int(r[6] or 0):,}€")

    out = ROOT / "data" / "zielliste.csv"
    con.execute(f"""COPY (
      SELECT identity_id, firmenname, haupt_nuts1, score, dominant_signal,
             wins36, round(avg_val) avg_wert, round(vol36) volumen_36m,
             verlorene_12m, round(verlust_vol) verlust_volumen, letzter_verlust,
             auslauf_n, round(auslauf_vol) auslauf_volumen_6_18m, naechstes_auslaufdatum
      FROM ranked ORDER BY score DESC {f'LIMIT {args.limit}' if args.limit else ''}
    ) TO '{out}' (HEADER, DELIMITER ',')""")
    n = con.execute("SELECT count(*) FROM ranked").fetchone()[0]
    print(f"\n{n} Zeilen → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
