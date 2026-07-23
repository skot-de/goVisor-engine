"""Gestufter Nachfolge-Scorer (Machbarkeit + Präzisionsmessung).

Trichter:
  A) Eckdaten-Filter (Behörde + CPV + Zeitfenster) → Kandidatenkreis
  B) Inhalts-Score (Titel-Token-Ähnlichkeit ohne Boilerplate + CPV-Bonus) → bestes Paar
  C) (nur beziffert) mehrdeutige Reste → LLM-Queue

Misst, wie viel Stufe B sauber eindeutig löst und wie groß der LLM-Rest wäre.
Schreibt nichts — reine Messung mit Stichproben zum Nachsehen.
"""
import re, duckdb
from collections import defaultdict

con = duckdb.connect()
con.execute("SET threads=3; SET memory_limit='3GB'")
PE = "data/gold/DE/party_entity.parquet"
N = "data/silver/DE/notices/*/*.parquet"
L = "data/gold/DE/leads.parquet"

# --- Titel-Normalisierung: Vergabe-Boilerplate + Stoppwörter raus, Domänenwörter behalten
STOP = set("""rahmenvertrag rahmenvereinbarung rahmen vereinbarung vertrag vertraege
vergabe ausschreibung eu euweit weit weite offenes offene verfahren oeffentliche
lieferung lieferungen liefern leistung leistungen erbringung beschaffung bereitstellung
ueber von und der die das fuer zur zum im in den des dem einer eines eine ein sowie bzw
div diverse divers verschiedene an auf mit als per pro nr los teil teillos gemaess
dienstleistung dienstleistungen durchfuehrung durchführung erbringung wartung
""".split())


def toks(title: str) -> set:
    t = (title or "").lower()
    t = t.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return {w for w in t.split() if len(w) > 3 and w not in STOP}


def jac(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# Award-Historie (CAN)
con.execute(f"""
CREATE TEMP TABLE hist AS
SELECT n.notice_id, bpe.entity_id buyer, n.cpv_main, substr(n.cpv_main,1,4) cpv4,
       CAST(coalesce(year(n.award_date), n.year) AS INT) yr, n.title, n.final_value
FROM read_parquet('{N}', hive_partitioning=1) n
JOIN read_parquet('{PE}') bpe ON bpe.notice_id=n.notice_id AND bpe.role='buyer'
WHERE n.notice_kind='can' AND n.cpv_main IS NOT NULL AND bpe.entity_id IS NOT NULL AND n.title IS NOT NULL
""")
# Rahmenvertrags-Anker
con.execute(f"""
CREATE TEMP TABLE anchor AS
SELECT lead_id, buyer_entity buyer, cpv_main, substr(cpv_main,1,4) cpv4,
       CAST(year(vergabe_datum) AS INT) yr, titel, value_band
FROM read_parquet('{L}')
WHERE contract_kind='rahmenvertrag' AND buyer_entity IS NOT NULL
  AND cpv_main IS NOT NULL AND vergabe_datum IS NOT NULL AND titel IS NOT NULL
""")
na = con.execute("SELECT count(*) FROM anchor").fetchone()[0]

# Stufe A: Kandidaten (gleiche Behörde + CPV4 + 1..10 J früher)
pairs = con.execute("""
SELECT a.lead_id, a.titel, a.cpv_main, a.yr,
       h.notice_id, h.title, h.cpv_main, h.yr
FROM anchor a
JOIN hist h ON h.buyer=a.buyer AND h.cpv4=a.cpv4 AND h.yr < a.yr AND h.yr >= a.yr-10
""").fetchall()

# Stufe B: Inhalts-Score je Paar, bestes je Anker
by_anchor = defaultdict(list)
for lid, atit, acpv, ayr, hid, htit, hcpv, hyr in pairs:
    s = jac(toks(atit), toks(htit))
    if acpv == hcpv:
        s += 0.30                      # exakt gleiches CPV-8 = starkes Zusatzsignal
    by_anchor[lid].append((min(s, 1.0), atit, htit, hyr, ayr, acpv == hcpv))

CONF, AMB = 0.45, 0.25                  # Schwellen: eindeutig / mehrdeutig
buckets = {"eindeutig": 0, "mehrdeutig_llm": 0, "kein_match": 0}
conf_samples, amb_samples = [], []
for lid, cands in by_anchor.items():
    cands.sort(reverse=True)
    best = cands[0][0]
    second = cands[1][0] if len(cands) > 1 else 0.0
    if best >= CONF and (best - second) >= 0.15:
        buckets["eindeutig"] += 1
        if len(conf_samples) < 15:
            conf_samples.append(cands[0])
    elif best >= AMB:
        buckets["mehrdeutig_llm"] += 1
        if len(amb_samples) < 12:
            amb_samples.append((cands[0], cands[1] if len(cands) > 1 else None))
    else:
        buckets["kein_match"] += 1

anchors_with_cand = len(by_anchor)
no_cand = na - anchors_with_cand

print(f"Rahmenvertrags-Anker: {na:,}")
print(f"  ohne Kandidat (Stufe A leer): {no_cand:,} ({100*no_cand/na:.1f}%)")
print(f"  mit Kandidat: {anchors_with_cand:,} ({100*anchors_with_cand/na:.1f}%)\n")
print("=== Stufe B — Auflösung der Kandidaten-Anker ===")
for k, v in buckets.items():
    print(f"  {k:16s} {v:>6,}  ({100*v/anchors_with_cand:.1f}% der Kandidaten-Anker · {100*v/na:.1f}% aller)")

print("\n=== EINDEUTIG (Stufe B) — Präzisions-Stichprobe: Anker → Vorgänger ===")
for s, atit, htit, hyr, ayr, cpv_eq in conf_samples:
    print(f"\n  score {s:.2f}{'  [CPV=]' if cpv_eq else ''}")
    print(f"    {ayr}: {atit[:72]}")
    print(f"    {hyr}: {htit[:72]}")

print("\n=== MEHRDEUTIG → LLM-Queue: Anker + Top-2 Kandidaten (die harten Fälle) ===")
for top, second in amb_samples:
    s1, atit, h1, hy1, ay, e1 = top
    print(f"\n  {ay}: {atit[:70]}")
    print(f"    K1 {hy1} (s={s1:.2f}): {h1[:64]}")
    if second:
        s2, _, h2, hy2, _, e2 = second
        print(f"    K2 {hy2} (s={s2:.2f}): {h2[:64]}")

llm = buckets["mehrdeutig_llm"]
print(f"\n=== LLM-Last (Stufe C): {llm:,} Anker × ~2-4 Kandidaten ≈ {llm*3:,} Titelvergleiche ===")
print("DONE")
