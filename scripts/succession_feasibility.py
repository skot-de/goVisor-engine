"""Machbarkeitsstudie Nachfolge-Modell (leichtgewichtig, nur Silber/Gold lesen).

Ansatz (Svens): Rahmenvertrag als Anker → Behörde + Scope filtern → Vorgänger-
Kandidaten rückwärts. Kernfrage: Wie klein ist der Kandidatenkreis? Lässt sich
mit Behörde + CPV-Klasse + Zeitfenster (+ Wert) eindeutig ein Vorgänger finden?
"""
import duckdb

con = duckdb.connect()
con.execute("SET threads=3; SET memory_limit='3GB'")

PE = "data/gold/DE/party_entity.parquet"
N = "data/silver/DE/notices/*/*.parquet"
L = "data/gold/DE/leads.parquet"

# 1) Award-Historie: jede CAN-Notice → Buyer-Entity, Gewinner-Entity, CPV-Klasse, Jahr, Wert, Titel
con.execute(f"""
CREATE TEMP TABLE hist AS
SELECT n.notice_id,
       bpe.entity_id AS buyer_entity,
       wpe.entity_id AS winner_entity,
       substr(n.cpv_main,1,4) AS cpv4,
       CAST(coalesce(year(n.award_date), n.year) AS INT) AS yr,
       n.final_value, n.title
FROM read_parquet('{N}', hive_partitioning=1) n
JOIN read_parquet('{PE}') bpe ON bpe.notice_id=n.notice_id AND bpe.role='buyer'
LEFT JOIN read_parquet('{PE}') wpe ON wpe.notice_id=n.notice_id AND wpe.role='winner'
WHERE n.notice_kind='can' AND n.cpv_main IS NOT NULL AND bpe.entity_id IS NOT NULL
""")
nh = con.execute("SELECT count(*) FROM hist").fetchone()[0]
print(f"CAN-Award-Historie: {nh:,} Zeilen")

# 2) Anker: Rahmenvertrags-Leads (buyer_entity, cpv_class, Vergabejahr)
con.execute(f"""
CREATE TEMP TABLE anchor AS
SELECT lead_id, buyer_entity, buyer_name, substr(cpv_main,1,4) AS cpv4,
       CAST(year(vergabe_datum) AS INT) AS yr, incumbent_entity, incumbent_name,
       titel, value_band
FROM read_parquet('{L}')
WHERE contract_kind='rahmenvertrag' AND buyer_entity IS NOT NULL
  AND cpv_main IS NOT NULL AND vergabe_datum IS NOT NULL
""")
na = con.execute("SELECT count(*) FROM anchor").fetchone()[0]
print(f"Rahmenvertrags-Anker: {na:,}\n")

# 3) Kandidaten-Vorgänger: gleiche Behörde + CPV4 + 1..10 Jahre früher (nicht dieselbe Notice)
con.execute("""
CREATE TEMP TABLE cand AS
SELECT a.lead_id, count(*) AS n_cand
FROM anchor a
JOIN hist h ON h.buyer_entity=a.buyer_entity AND h.cpv4=a.cpv4
           AND h.yr < a.yr AND h.yr >= a.yr-10
GROUP BY a.lead_id
""")

print("=== Kandidatenkreis-Größe pro Rahmenvertrags-Anker ===")
dist = con.execute("""
  WITH j AS (
    SELECT a.lead_id, coalesce(c.n_cand,0) AS n FROM anchor a LEFT JOIN cand c USING(lead_id)
  )
  SELECT CASE WHEN n=0 THEN '0 (kein TED-Vorgänger)'
              WHEN n=1 THEN '1 (eindeutig)'
              WHEN n=2 THEN '2'
              WHEN n<=5 THEN '3-5'
              ELSE '6+' END AS bucket, count(*) c
  FROM j GROUP BY 1 ORDER BY min(n)
""").fetchall()
for b, c in dist:
    print(f"  {b:24s} {c:>6,}  ({100*c/na:.1f}%)")

uniq = con.execute("SELECT count(*) FROM cand WHERE n_cand=1").fetchone()[0]
some = con.execute("SELECT count(*) FROM cand").fetchone()[0]
print(f"\nAnker mit genau 1 Vorgänger (sofort eindeutig): {uniq:,} ({100*uniq/na:.1f}% aller Anker)")
print(f"Anker mit ≥1 Vorgänger: {some:,} ({100*some/na:.1f}%)")

# 4) Enger: hilft Wert-Band-Übereinstimmung, die Mehrdeutigen zu entschärfen?
con.execute(f"""
CREATE TEMP TABLE cand_v AS
SELECT a.lead_id, count(*) AS n_cand
FROM anchor a
JOIN hist h ON h.buyer_entity=a.buyer_entity AND h.cpv4=a.cpv4
           AND h.yr < a.yr AND h.yr >= a.yr-10
LEFT JOIN read_parquet('{L}') lv ON lv.lead_id=a.lead_id
GROUP BY a.lead_id
""")

# 5) Konkrete Beispiele: Anker → eindeutiger Vorgänger (Titel-Vergleich zum Nachsehen)
print("\n=== BEISPIELE: Anker  →  eindeutiger Vorgänger (Titel zum Inhaltsvergleich) ===")
ex = con.execute("""
SELECT a.buyer_name, a.yr, a.titel, h.yr AS pyr, h.title AS ptitle, h.winner_entity
FROM anchor a
JOIN cand c ON c.lead_id=a.lead_id AND c.n_cand=1
JOIN hist h ON h.buyer_entity=a.buyer_entity AND h.cpv4=a.cpv4
           AND h.yr < a.yr AND h.yr >= a.yr-10
WHERE a.titel IS NOT NULL AND h.title IS NOT NULL
LIMIT 12
""").fetchall()
for buyer, yr, titel, pyr, ptitle, wpe in ex:
    print(f"\n  [{buyer[:40] if buyer else '?'}]")
    print(f"    Anker  {yr}: {(titel or '')[:70]}")
    print(f"    Vorg.  {pyr}: {(ptitle or '')[:70]}")

print("\nDONE")
