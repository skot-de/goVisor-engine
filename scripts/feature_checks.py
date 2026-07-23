"""Feature-Verifikation gegen den fertigen final5-Stand (Gold + Silber).

Prüft 5 der zugesagten Features mit echten Queries:
  1. Incumbent-Rate (contract_chains)      — soll 7% → 40–60% springen
  2. Buyer-Profil + Vergabedauer
  3. Los-Analyse IT-Sektor
  4. Firmenprofil + Konsortialquote
  5. Verzögerte Vergaben

Nur Lesen, keine Schreibvorgänge. Aufruf:  python scripts/feature_checks.py
"""
import duckdb

C = "DE"
S = f"data/silver/{C}"
G = f"data/gold/{C}"
NOTICES = f"'{S}/notices/*/*.parquet'"
PARTIES = f"'{S}/notice_parties/*/*.parquet'"
LOTS = f"'{S}/lots/*/*.parquet'"
LOTCPV = f"'{S}/lot_cpv/*/*.parquet'"
AWARDS = f"'{S}/awards/*/*.parquet'"
PE = f"'{G}/party_entity.parquet'"
ENT = f"'{G}/entities.parquet'"
CHAINS = f"'{G}/contract_chains.parquet'"
IT = "('30','32','48','64','72')"   # CPV-Divisionen Sektor IT

con = duckdb.connect()

def hr(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

# ── Check 1: Incumbent-Rate ────────────────────────────────────────────
hr("CHECK 1 — Incumbent-Rate (Wechsel-Prognose-Grundlage)")
w, inc, avg_gap = con.execute(f"""
    SELECT count(*) FILTER (WHERE incumbent_retained IS NOT NULL),
           count(*) FILTER (WHERE incumbent_retained),
           round(avg(gap_days))
    FROM {CHAINS}
""").fetchone()
print(f"Verkettete Verträge mit bewertbarem Nachfolger: {w:,}")
print(f"Amtsinhaber blieb (incumbent_retained): {inc:,}  = {100*inc/max(w,1):.0f}%")
print(f"→ Wechsel-Quote: {100*(w-inc)/max(w,1):.0f}%   Ø Lücke Vorgänger-Ende→Nachfolger-Vergabe: {avg_gap} Tage")
print("Erwartung: Incumbent 40–60% (vorher artefakthaft 7% durch instabile IDs).")

# ── Check 2: Buyer-Profil + Vergabedauer ───────────────────────────────
hr("CHECK 2 — Buyer-Profil + Vergabedauer (Top-Käufer nach Zahl der Vergaben)")
rows = con.execute(f"""
    WITH cans AS (
        SELECT n.notice_id, n.award_date, n.submission_deadline, n.publication_date,
               pe.entity_id, q.final_value_clean
        FROM {NOTICES} n
        JOIN {PE} pe ON pe.notice_id=n.notice_id AND pe.role='buyer'
        LEFT JOIN '{G}/quality.parquet' q ON q.notice_id=n.notice_id
        WHERE n.notice_kind='can'
    )
    SELECT e.canonical_name,
           count(*) AS vergaben,
           round(median(final_value_clean)) AS median_wert,
           round(avg(date_diff('day', submission_deadline, award_date))
                 FILTER (WHERE submission_deadline IS NOT NULL AND award_date IS NOT NULL
                         AND award_date >= submission_deadline)) AS avg_dauer_tage
    FROM cans c JOIN {ENT} e ON e.entity_id=c.entity_id
    WHERE e.canonical_name IS NOT NULL
    GROUP BY 1 ORDER BY vergaben DESC LIMIT 8
""").fetchall()
print(f"{'Käufer':<42}{'Vergaben':>9}{'Median €':>12}{'ØDauer/T':>10}")
for name, v, mw, d in rows:
    print(f"{(name or '')[:41]:<42}{v:>9,}{(f'{mw:,.0f}' if mw else '–'):>12}{(d if d is not None else '–'):>10}")

# ── Check 3: Los-Analyse IT-Sektor ─────────────────────────────────────
hr("CHECK 3 — Los-Analyse IT-Sektor (CPV-Div 30/32/48/64/72)")
n_lots, med_val, med_dur, opt_share, ren_share = con.execute(f"""
    WITH it_lots AS (
        SELECT DISTINCT l.notice_id, l.lot_id, l.value_amount,
               l.duration_months, l.has_options, l.has_renewal
        FROM {LOTS} l
        JOIN {LOTCPV} lc ON lc.notice_id=l.notice_id AND lc.lot_id=l.lot_id
        WHERE substr(lc.cpv_code,1,2) IN {IT}
    )
    SELECT count(*),
           round(median(value_amount) FILTER (WHERE value_amount>=100)),
           median(duration_months) FILTER (WHERE duration_months>0),
           round(100.0*avg(CASE WHEN has_options THEN 1 ELSE 0 END),1),
           round(100.0*avg(CASE WHEN has_renewal THEN 1 ELSE 0 END),1)
    FROM it_lots
""").fetchone()
print(f"IT-Lose gesamt: {n_lots:,}")
print(f"Median Los-Wert (plausibel): {med_val:,.0f} €" if med_val else "Median Los-Wert: –")
print(f"Median Laufzeit: {med_dur} Monate" if med_dur else "Median Laufzeit: –")
print(f"Lose mit Optionen: {opt_share}%   mit Verlängerung: {ren_share}%")
# Bieterwettbewerb im IT-Sektor
comp = con.execute(f"""
    SELECT round(avg(a.num_tenders) FILTER (WHERE a.num_tenders>0),1),
           count(*) FILTER (WHERE a.num_tenders=1)
    FROM {AWARDS} a
    JOIN {LOTCPV} lc ON lc.notice_id=a.notice_id AND lc.lot_id=a.lot_id
    WHERE substr(lc.cpv_code,1,2) IN {IT}
""").fetchone()
print(f"Ø Bieter je IT-Los: {comp[0]}   davon Einzelbieter-Lose (num_tenders=1): {comp[1]:,}")

# ── Check 4: Firmenprofil + Konsortialquote ────────────────────────────
hr("CHECK 4 — Firmenprofil + Konsortialquote (Top-Gewinner)")
rows = con.execute(f"""
    WITH wins AS (
        SELECT pe.entity_id, p.in_consortium
        FROM {PARTIES} p
        JOIN {PE} pe ON pe.notice_id=p.notice_id AND pe.role='winner' AND pe.seq=p.seq
        WHERE p.role='winner'
    )
    SELECT e.canonical_name, count(*) AS gewinne,
           count(*) FILTER (WHERE in_consortium) AS im_konsortium,
           round(100.0*count(*) FILTER (WHERE in_consortium)/count(*),1) AS konsortialquote
    FROM wins w JOIN {ENT} e ON e.entity_id=w.entity_id
    WHERE e.canonical_name IS NOT NULL AND e.entity_id NOT LIKE 'unresolved%'
    GROUP BY 1 ORDER BY gewinne DESC LIMIT 10
""").fetchall()
print(f"{'Firma':<44}{'Gewinne':>8}{'ARGE':>7}{'Quote':>8}")
for name, g, k, q in rows:
    print(f"{(name or '')[:43]:<44}{g:>8,}{k:>7,}{f'{q}%':>8}")

# ── Check 5: Verzögerte Vergaben ───────────────────────────────────────
hr("CHECK 5 — Verzögerte Vergaben (Dauer Frist→Zuschlag)")
buckets = con.execute(f"""
    WITH d AS (
        SELECT date_diff('day', submission_deadline, award_date) AS dur
        FROM {NOTICES}
        WHERE notice_kind='can' AND submission_deadline IS NOT NULL
          AND award_date IS NOT NULL AND award_date >= submission_deadline
    )
    SELECT count(*), round(median(dur)),
           count(*) FILTER (WHERE dur>90), count(*) FILTER (WHERE dur>180),
           count(*) FILTER (WHERE dur>365)
    FROM d
""").fetchone()
tot, med, g90, g180, g365 = buckets
print(f"Vergaben mit Frist+Zuschlagsdatum: {tot:,}   Median-Dauer: {med} Tage")
print(f"> 90 Tage: {g90:,} ({100*g90/max(tot,1):.0f}%)   "
      f"> 180 Tage: {g180:,} ({100*g180/max(tot,1):.0f}%)   "
      f"> 365 Tage: {g365:,} ({100*g365/max(tot,1):.0f}%)")

con.close()
print("\nFertig.")
