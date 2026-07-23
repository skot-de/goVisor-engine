"""🟢-Aggregat-Views (Ticket #3, machbar ohne Nachfolge-Modell).

Baut vier materialisierte Views über die CAN-Award-Historie (5-Jahres-Fenster).
Nur nachfolge-freie KPIs; jede Zahl trägt Coverage/`n`. Validierungslauf —
schreibt nach data/gold/DE/, druckt Kennzahlen + Stichproben.
"""
import duckdb
from datetime import date

con = duckdb.connect()
con.execute("SET threads=3; SET memory_limit='4GB'")
G = "data/gold/DE"
PE = f"{G}/party_entity.parquet"
EN = f"{G}/entities.parquet"
N = "data/silver/DE/notices/*/*.parquet"
LOTS = "data/silver/DE/lots/*/*.parquet"
AS_OF = date.today().year
W = AS_OF - 5                      # 5-Jahres-Fenster


def copy_to(sql, path):
    con.execute(f"COPY ({sql}) TO '{G}/{path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    return con.execute(f"SELECT count(*) FROM read_parquet('{G}/{path}')").fetchone()[0]


# Award-Basis: CAN + Buyer-Entity + Gewinner-Entity + CPV-Klasse + Jahr + NUTS-1 + Wert
con.execute(f"""
CREATE TEMP TABLE aw AS
SELECT n.notice_id,
       bpe.entity_id AS buyer,
       be.canonical_name AS buyer_name,
       wpe.entity_id AS winner,
       we.canonical_name AS winner_name,
       we.confidence AS winner_conf,
       substr(n.cpv_main,1,4) AS cpv_class,
       CAST(coalesce(year(n.award_date), n.year) AS INT) AS yr,
       coalesce(upper(substr(n.performance_nuts,1,3)), 'DE') AS nuts1,
       n.final_value AS value
FROM read_parquet('{N}', hive_partitioning=1) n
JOIN read_parquet('{PE}') bpe ON bpe.notice_id=n.notice_id AND bpe.role='buyer'
LEFT JOIN read_parquet('{EN}') be ON be.entity_id=bpe.entity_id
LEFT JOIN read_parquet('{PE}') wpe ON wpe.notice_id=n.notice_id AND wpe.role='winner'
LEFT JOIN read_parquet('{EN}') we ON we.entity_id=wpe.entity_id
WHERE n.notice_kind='can' AND n.cpv_main IS NOT NULL AND bpe.entity_id IS NOT NULL
  AND CAST(coalesce(year(n.award_date), n.year) AS INT) >= {W}
""")
naw = con.execute("SELECT count(*) FROM aw").fetchone()[0]
print(f"Award-Basis (CAN, {W}-{AS_OF}): {naw:,} Zeilen\n")

# 1) buyer_stats
con.execute("""
CREATE TEMP TABLE _bt AS
SELECT buyer, list(struct_pack(entity_id:=winner, name:=winner_name, wins:=wins)
                   ORDER BY wins DESC) FILTER (WHERE rn<=3) AS top_contractors
FROM (SELECT buyer, winner, any_value(winner_name) winner_name, count(*) wins,
             row_number() OVER (PARTITION BY buyer ORDER BY count(*) DESC) rn
      FROM aw WHERE winner IS NOT NULL GROUP BY buyer, winner)
GROUP BY buyer
""")
con.execute("""
CREATE TEMP TABLE _bc AS
SELECT buyer, list(cpv_class ORDER BY c DESC) FILTER (WHERE rn<=3) AS top_cpvs
FROM (SELECT buyer, cpv_class, count(*) c,
             row_number() OVER (PARTITION BY buyer ORDER BY count(*) DESC) rn
      FROM aw GROUP BY buyer, cpv_class)
GROUP BY buyer
""")
n1 = copy_to(f"""
SELECT a.buyer AS buyer_entity_id, any_value(a.buyer_name) AS buyer_name,
       count(DISTINCT a.notice_id) AS total_awards,
       count(DISTINCT a.winner) AS distinct_contractors,
       bc.top_cpvs, bt.top_contractors, {AS_OF} AS window_end, 5 AS window_years
FROM aw a LEFT JOIN _bt bt ON bt.buyer=a.buyer LEFT JOIN _bc bc ON bc.buyer=a.buyer
GROUP BY a.buyer, bc.top_cpvs, bt.top_contractors
""", "buyer_stats.parquet")
print(f"buyer_stats            : {n1:,} Behörden")

# 2) contractor_stats (entity × cpv_class): wins, volume+coverage, rank/share by wins, trend
n2 = copy_to(f"""
WITH base AS (
  SELECT winner AS entity_id, cpv_class,
         count(*) AS total_wins,
         count(value) AS wins_with_value,
         sum(value) FILTER (WHERE value IS NOT NULL) AS total_volume_known,
         count(*) FILTER (WHERE yr = {AS_OF}) AS wins_last_year,
         count(*) FILTER (WHERE yr = {AS_OF}-1) AS wins_prev_year
  FROM aw WHERE winner IS NOT NULL GROUP BY winner, cpv_class
)
SELECT entity_id, cpv_class, total_wins, total_volume_known,
       round(wins_with_value*1.0/total_wins, 2) AS volume_coverage,
       rank() OVER (PARTITION BY cpv_class ORDER BY total_wins DESC) AS market_rank,
       round(total_wins*1.0/sum(total_wins) OVER (PARTITION BY cpv_class), 4) AS market_share_by_wins,
       CASE WHEN wins_prev_year>0 THEN round((wins_last_year-wins_prev_year)*1.0/wins_prev_year,2) END AS trend_yoy
FROM base
""", "contractor_stats.parquet")
print(f"contractor_stats       : {n2:,} (Entität × CPV-Klasse)")

# 3) market_stats (cpv_class × nuts1): active contractors, awards, avg duration (aus lots)
con.execute(f"""
CREATE TEMP TABLE _dur AS
SELECT a.cpv_class, a.nuts1, avg(l.duration_months) AS avg_dur,
       count(l.duration_months) AS n_dur, count(*) AS n_tot
FROM aw a LEFT JOIN read_parquet('{LOTS}') l ON l.notice_id=a.notice_id
GROUP BY a.cpv_class, a.nuts1
""")
n3 = copy_to(f"""
SELECT a.cpv_class, a.nuts1,
       count(DISTINCT a.winner) AS active_contractors,
       count(DISTINCT a.notice_id) AS total_awards,
       round(d.avg_dur) AS avg_contract_duration_months,
       round(d.n_dur*1.0/d.n_tot, 2) AS duration_coverage
FROM aw a LEFT JOIN _dur d ON d.cpv_class=a.cpv_class AND d.nuts1=a.nuts1
GROUP BY a.cpv_class, a.nuts1, d.avg_dur, d.n_dur, d.n_tot
""", "market_stats.parquet")
print(f"market_stats           : {n3:,} (CPV-Klasse × NUTS-1)")

# 4) buyer_contractor_history: wins, last_win, renewals (aus lots has_renewal)
con.execute(f"""
CREATE TEMP TABLE _ren AS
SELECT a.buyer, a.winner, a.notice_id,
       max(CASE WHEN l.has_renewal THEN 1 ELSE 0 END) AS renewed
FROM aw a LEFT JOIN read_parquet('{LOTS}') l ON l.notice_id=a.notice_id
WHERE a.winner IS NOT NULL GROUP BY a.buyer, a.winner, a.notice_id
""")
n4 = copy_to(f"""
SELECT a.buyer AS buyer_entity_id, a.winner AS contractor_entity_id,
       any_value(a.winner_name) AS contractor_name,
       count(DISTINCT a.notice_id) AS total_wins,
       max(a.yr) AS last_win_year,
       coalesce(sum(r.renewed), 0) AS total_renewals
FROM aw a LEFT JOIN _ren r ON r.buyer=a.buyer AND r.winner=a.winner AND r.notice_id=a.notice_id
WHERE a.winner IS NOT NULL
GROUP BY a.buyer, a.winner
""", "buyer_contractor_history.parquet")
print(f"buyer_contractor_history: {n4:,} (Behörde × Contractor)")

# --- Stichproben zum Nachsehen
print("\n=== Beispiel buyer_stats (Top-Behörde) ===")
for row in con.execute(f"""
  SELECT buyer_name, total_awards, top_cpvs, top_contractors
  FROM read_parquet('{G}/buyer_stats.parquet') ORDER BY total_awards DESC LIMIT 3""").fetchall():
    print(f"  {row[0][:45] if row[0] else '?'} | {row[1]} Vergaben | CPVs {row[2]}")
    for tc in (row[3] or [])[:3]:
        print(f"      → {tc['name'][:40] if tc['name'] else '?'}: {tc['wins']} Wins")

print("\n=== Beispiel contractor_stats (Marktführer je CPV) ===")
for row in con.execute(f"""
  SELECT entity_id, cpv_class, total_wins, market_rank, market_share_by_wins, volume_coverage
  FROM read_parquet('{G}/contractor_stats.parquet') WHERE market_rank=1 ORDER BY total_wins DESC LIMIT 5""").fetchall():
    print(f"  CPV {row[1]} | Rang {row[3]} | {row[2]} Wins | Anteil {100*row[4]:.0f}% | Vol-Coverage {100*row[5]:.0f}%")

print("\nDONE")
