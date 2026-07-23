"""🔴-KPIs auf dem konfidenten Nachfolge-Kern (contract_succession).

Anreichert jede Nachfolge mit Incumbent (Vorgänger-Gewinner) + Challenger (Nachfolger-
Gewinner) → Verdrängung. Daraus: Retention/Switch-Rate, loss_rate, head_to_head,
buyer_loyalty. Validierungslauf: druckt v. a. die Retention-Rate (vs 7 % Artefakt).
"""
import duckdb

con = duckdb.connect(); con.execute("SET threads=3; SET memory_limit='4GB'")
G = "data/gold/DE"
S = f"{G}/contract_succession.parquet"
PE = f"{G}/party_entity.parquet"
EN = f"{G}/entities.parquet"


def copy_to(sql, name):
    con.execute(f"COPY ({sql}) TO '{G}/{name}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    return con.execute(f"SELECT count(*) FROM read_parquet('{G}/{name}')").fetchone()[0]


# Primär-Gewinner je Notice (kleinste seq)
con.execute(f"""
CREATE TEMP TABLE win AS
SELECT notice_id, arg_min(entity_id, seq) AS winner
FROM read_parquet('{PE}') WHERE role='winner' GROUP BY notice_id
""")

# Nachfolge-Ereignisse anreichern
con.execute(f"""
CREATE TEMP TABLE ev AS
SELECT s.successor, s.predecessor, s.buyer_entity, s.cpv_class, s.gap_years, s.confidence,
       pw.winner AS incumbent, sw.winner AS challenger,
       (pw.winner IS NOT NULL AND sw.winner IS NOT NULL AND pw.winner <> sw.winner) AS displaced,
       (pw.winner IS NOT NULL AND sw.winner IS NOT NULL AND pw.winner = sw.winner) AS retained
FROM read_parquet('{S}') s
LEFT JOIN win pw ON pw.notice_id = s.predecessor
LEFT JOIN win sw ON sw.notice_id = s.successor
""")
n_ev = con.execute("SELECT count(*) FROM ev").fetchone()[0]
resolved = con.execute("SELECT count(*) FROM ev WHERE incumbent IS NOT NULL AND challenger IS NOT NULL").fetchone()[0]
ret = con.execute("SELECT count(*) FROM ev WHERE retained").fetchone()[0]
dis = con.execute("SELECT count(*) FROM ev WHERE displaced").fetchone()[0]

print(f"Nachfolge-Ereignisse: {n_ev:,}")
print(f"  mit beidseitig aufgelöstem Gewinner: {resolved:,}")
print(f"\n>>> INCUMBENT-RETENTION: {100*ret/resolved:.1f}%  (Verdrängung {100*dis/resolved:.1f}%)")
print(f"    (Artefakt-Rate war 7% Incumbent — jetzt an inhaltlich verifizierten Nachfolgen)")

# succession_events materialisieren (Basis für alle 🔴-KPIs)
copy_to("SELECT * FROM ev", "succession_events.parquet")

# head_to_head: A verdrängt B
n_h2h = copy_to("""
  SELECT challenger AS winner_entity, incumbent AS loser_entity,
         count(*) AS displacements, round(avg(confidence),2) AS avg_conf
  FROM ev WHERE displaced GROUP BY challenger, incumbent
""", "head_to_head.parquet")

# market_switch_rate je cpv_class (n mitgeben)
copy_to("""
  SELECT cpv_class, count(*) AS n_successions,
         round(count(*) FILTER (WHERE displaced)*1.0/count(*),3) AS switch_rate
  FROM ev WHERE incumbent IS NOT NULL AND challenger IS NOT NULL GROUP BY cpv_class
""", "market_switch_rate.parquet")

# buyer_loyalty je Behörde
copy_to("""
  SELECT buyer_entity, count(*) AS n_successions,
         round(count(*) FILTER (WHERE retained)*1.0/count(*),3) AS incumbent_loyalty
  FROM ev WHERE incumbent IS NOT NULL AND challenger IS NOT NULL GROUP BY buyer_entity
""", "buyer_loyalty.parquet")

# contractor_loss je Incumbent: von seinen auslaufenden (als Vorgänger) wie viele verloren
n_loss = copy_to("""
  SELECT incumbent AS entity_id,
         count(*) AS n_defended,
         count(*) FILTER (WHERE displaced) AS n_lost,
         round(count(*) FILTER (WHERE displaced)*1.0/count(*),3) AS loss_rate
  FROM ev WHERE incumbent IS NOT NULL AND challenger IS NOT NULL GROUP BY incumbent
""", "contractor_loss.parquet")

print(f"\nsuccession_events : {n_ev:,}")
print(f"head_to_head      : {n_h2h:,} Paarungen")
print(f"contractor_loss   : {n_loss:,} Incumbents mit Verteidigungs-Bilanz")

# Plausibilität: Top-Verdränger-Paarungen
print("\n=== Top head_to_head (wer verdrängt wen am häufigsten) ===")
for w, l, d, c in con.execute(f"""
  SELECT ew.canonical_name, el.canonical_name, h.displacements, h.avg_conf
  FROM read_parquet('{G}/head_to_head.parquet') h
  JOIN read_parquet('{EN}') ew ON ew.entity_id=h.winner_entity
  JOIN read_parquet('{EN}') el ON el.entity_id=h.loser_entity
  ORDER BY h.displacements DESC LIMIT 8""").fetchall():
    print(f"  {(w or '?')[:34]:34s} verdrängt {(l or '?')[:30]:30s} {d}× (conf {c})")
print("\nDONE")
