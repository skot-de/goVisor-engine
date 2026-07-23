"""Nachfolge-Modell — gestufter, inhaltsbasierter Scorer über die CAN-Historie.

Stufe A: Kandidaten = gleiche Behörde + CPV-Klasse, 1..10 J früher.
Stufe B: „unmittelbarer Vorgänger" = jüngster Kandidat mit Inhalts-Score >= Schwelle.
         Score = Titel-Token-Jaccard (+ CPV-8-Bonus + Laufzeit-Timing).
         Refinement 1: gleiche oj_ref/Publikation ausschließen (Same-Verfahren).
         Refinement 2: Laufzeit-Timing (Vorgänger ≈ eine Laufzeit zurück).
Stufe C: mehrdeutige (Top-2 dicht) → LLM-Queue (hier nur materialisiert + beziffert).

Schreibt data/gold/DE/contract_succession.parquet + ..._llm_queue.parquet, misst Verteilung.
"""
import re, duckdb
from collections import defaultdict
from govisor import gold, locales
locales.use("DE")

con = duckdb.connect(); con.execute("SET threads=3; SET memory_limit='4GB'")
G = "data/gold/DE"
PE, EN = f"{G}/party_entity.parquet", f"{G}/entities.parquet"
N = "data/silver/DE/notices/*/*.parquet"
LOTS = "data/silver/DE/lots/*/*.parquet"

STOP = set("""rahmenvertrag rahmenvereinbarung rahmen vereinbarung vertrag vertraege vergabe
ausschreibung bekanntmachung vergabebekanntmachung aufhebung berichtigung eu euweit weit weite
offenes offene verfahren oeffentliche lieferung lieferungen liefern leistung leistungen erbringung
beschaffung bereitstellung durchfuehrung durchführung wartung ueber von und der die das fuer zur
zum los teillos gemaess im in den des dem einer eines eine sowie bzw div diverse verschiedene""".split())


def toks(t):
    t = (t or "").lower().replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss")
    return {w for w in re.sub(r"[^a-z0-9]+"," ",t).split() if len(w) > 3 and w not in STOP}


def jac(a, b):
    return len(a & b)/len(a | b) if a and b else 0.0


# CAN-Historie mit Buyer-Entity, Laufzeit, Vertragsart. Refinement 3 (aufgedeckt beim
# Messen): NUR ketten-würdige Verträge — nicht-Rahmen-Bauprojekte (CPV 45, einmal_werk/
# werk_sonstig) sind PROJEKTbasiert, keine Nachfolge. Sonst paart der Scorer Bau-Gewerke
# (Sanitär, Heizung) verschiedener Gebäude als falsche Nachfolge. `chain_worthy` im Code.
KIND = gold._kind_sql("n.title", "n.cpv_main")
rows = con.execute(f"""
SELECT n.notice_id, bpe.entity_id buyer, n.cpv_main, substr(n.cpv_main,1,4) cpv4,
       CAST(coalesce(year(n.award_date),n.year) AS INT) yr, n.title, n.oj_ref,
       (SELECT max(l.duration_months) FROM read_parquet('{LOTS}') l WHERE l.notice_id=n.notice_id) dur
FROM read_parquet('{N}', hive_partitioning=1) n
JOIN read_parquet('{PE}') bpe ON bpe.notice_id=n.notice_id AND bpe.role='buyer'
WHERE n.notice_kind='can' AND n.cpv_main IS NOT NULL AND bpe.entity_id IS NOT NULL AND n.title IS NOT NULL
  AND ({KIND}) NOT IN ('einmal_werk','werk_sonstig')
""").fetchall()
print(f"Ketten-würdige CAN-Anker: {len(rows):,}")

# gruppieren nach (buyer, cpv4); Tokens vorberechnen
groups = defaultdict(list)
tok = {}
meta = {}
for nid, buyer, cpv, cpv4, yr, title, ojref, dur in rows:
    groups[(buyer, cpv4)].append(nid)
    tok[nid] = toks(title)
    meta[nid] = dict(buyer=buyer, cpv=cpv, cpv4=cpv4, yr=yr, title=title, ojref=ojref, dur=dur)

CONF, AMB = 0.45, 0.30
edges = []          # (successor, predecessor, buyer, cpv4, gap, score, confidence, method)
llm_queue = []      # (successor, cand1, cand2, s1, s2)
buckets = {"eindeutig": 0, "mehrdeutig_llm": 0, "kein_vorgaenger": 0}
conf_samples = []

for key, ids in groups.items():
    ids.sort(key=lambda i: meta[i]["yr"])
    for anchor in ids:
        ay, adur = meta[anchor]["yr"], meta[anchor]["dur"]
        scored = []
        for cand in ids:
            cy = meta[cand]["yr"]
            if not (ay-10 <= cy < ay):                       # Stufe A: 1..10 J früher
                continue
            if meta[cand]["ojref"] and meta[cand]["ojref"] == meta[anchor]["ojref"]:
                continue                                     # R1: Same-Verfahren raus
            s = jac(tok[anchor], tok[cand])
            if meta[cand]["cpv"] == meta[anchor]["cpv"]:
                s += 0.30                                     # exakt CPV-8
            if adur:                                          # R2: Timing (Vorgänger ≈ 1 Laufzeit zurück)
                exp = max(1, round(adur/12))
                s += 0.10 * max(0, 1 - abs((ay-cy) - exp)/5)
            scored.append((min(s,1.0), cy, cand))
        if not scored:
            buckets["kein_vorgaenger"] += 1; continue
        # Kandidaten über Schwelle → jüngster = unmittelbarer Vorgänger
        above = [x for x in scored if x[0] >= CONF]
        scored.sort(reverse=True)
        if above:
            above.sort(key=lambda x: (x[1], x[0]), reverse=True)   # jüngster, dann bester
            best = above[0]
            # Mehrdeutig, wenn ein zweiter im selben Jahr fast gleich stark ist
            rivals = [x for x in above if x[1] == best[1] and x[2] != best[2] and abs(x[0]-best[0]) < 0.12]
            if rivals:
                buckets["mehrdeutig_llm"] += 1
                llm_queue.append((anchor, best[2], rivals[0][2], best[0], rivals[0][0]))
                continue
            conf = round(0.55 + 0.4*min(1.0,(best[0]-CONF)/(1-CONF)), 2)
            edges.append((anchor, best[2], meta[anchor]["buyer"], meta[anchor]["cpv4"],
                          ay-best[1], round(best[0],3), conf, "content_unique"))
            buckets["eindeutig"] += 1
            if len(conf_samples) < 12:
                conf_samples.append((meta[anchor], meta[best[2]], best[0], conf))
        elif scored[0][0] >= AMB:
            buckets["mehrdeutig_llm"] += 1
            second = scored[1] if len(scored) > 1 else (0,0,None)
            llm_queue.append((anchor, scored[0][2], second[2], scored[0][0], second[0]))
        else:
            buckets["kein_vorgaenger"] += 1

# materialisieren
con.execute("CREATE TEMP TABLE e(successor VARCHAR, predecessor VARCHAR, buyer VARCHAR, cpv_class VARCHAR, gap_years INT, content_score DOUBLE, confidence DOUBLE, method VARCHAR)")
con.executemany("INSERT INTO e VALUES (?,?,?,?,?,?,?,?)", edges)
con.execute(f"COPY (SELECT * FROM e) TO '{G}/contract_succession.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)")
con.execute("CREATE TEMP TABLE q(successor VARCHAR, cand1 VARCHAR, cand2 VARCHAR, score1 DOUBLE, score2 DOUBLE)")
con.executemany("INSERT INTO q VALUES (?,?,?,?,?)", llm_queue)
con.execute(f"COPY (SELECT * FROM q) TO '{G}/contract_succession_llm_queue.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)")

tot = sum(buckets.values())
print(f"\n=== Auflösung über {tot:,} CAN-Anker ===")
for k, v in buckets.items():
    print(f"  {k:18s} {v:>8,}  ({100*v/tot:.1f}%)")
print(f"\ncontract_succession.parquet: {len(edges):,} konfidente Nachfolge-Kanten")
print(f"LLM-Queue: {len(llm_queue):,} mehrdeutige Anker")

print("\n=== Stichprobe konfidente Nachfolgen (Anker → Vorgänger) ===")
for a, p, s, c in conf_samples:
    print(f"\n  score {s:.2f} conf {c} · gap {a['yr']-p['yr']}J")
    print(f"    {a['yr']}: {(a['title'] or '')[:66]}")
    print(f"    {p['yr']}: {(p['title'] or '')[:66]}")
print("\nDONE")
