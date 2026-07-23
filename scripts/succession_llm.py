"""LLM-Adjudikation der mehrdeutigen Nachfolge-Kandidaten (Stufe C).

Liest die LLM-Queue, reichert Titel an, fragt ein günstiges Modell über OpenRouter,
schreibt bestätigte Kanten. Key kommt aus $OPENROUTER_KEY_FILE (nie im Code/Repo).

Aufruf: LIMIT=20 python scripts/succession_llm.py   (Pilot)
        LIMIT=0  python scripts/succession_llm.py   (alle)
"""
import os, re, json, time, duckdb, requests

KEY = open(os.environ.get("OPENROUTER_KEY_FILE", ".secrets/openrouter.key")).read().strip()
MODEL = os.environ.get("OR_MODEL", "google/gemini-2.0-flash-001")
LIMIT = int(os.environ.get("LIMIT", "20"))
BATCH = int(os.environ.get("BATCH", "10"))
URL = "https://openrouter.ai/api/v1/chat/completions"
G = "data/gold/DE"

con = duckdb.connect(); con.execute("SET threads=3; SET memory_limit='4GB'")
N = "data/silver/DE/notices/*/*.parquet"
lim = "" if LIMIT == 0 else f"USING SAMPLE {LIMIT} ROWS (reservoir, 7)"
rows = con.execute(f"""
  WITH s AS (SELECT * FROM read_parquet('{G}/contract_succession_llm_queue.parquet') {lim})
  SELECT s.successor, na.title, na.year,
         s.cand1, n1.title, n1.year,
         s.cand2, n2.title, n2.year
  FROM s
  JOIN read_parquet('{N}',hive_partitioning=1) na ON na.notice_id=s.successor
  LEFT JOIN read_parquet('{N}',hive_partitioning=1) n1 ON n1.notice_id=s.cand1
  LEFT JOIN read_parquet('{N}',hive_partitioning=1) n2 ON n2.notice_id=s.cand2
""").fetchall()
print(f"Fälle: {len(rows):,} · Modell {MODEL} · Batch {BATCH}", flush=True)

SYS = ("Du prüfst Vertrags-Nachfolge in öffentlichen Ausschreibungen (DE). Pro Fall: ist cand1 oder "
       "cand2 der echte unmittelbare Vorgänger DESSELBEN wiederkehrenden Bedarfs bei derselben "
       "Behörde? Anderer Gegenstand trotz ähnlicher Wörter (anderer Wirkstoff, anderer Bauabschnitt) "
       "→ 'neither'. cand1/cand2 offensichtlich derselbe Auftrag (fast identisch, gleiches Jahr) → "
       "'duplicate'. Nur JSON zurück: {\"v\":[{\"id\":\"..\",\"verdict\":\"cand1|cand2|duplicate|neither|uncertain\"}]}")


def ask(batch):
    lines = []
    for r in batch:
        c2 = f' | cand2={r[6]}: "{(r[7] or "")[:80]}"' if r[6] else ""
        lines.append(f'id={r[0]} anchor={r[2]}: "{(r[1] or "")[:80]}" | '
                     f'cand1={r[5]}: "{(r[4] or "")[:80]}"{c2}')
    body = {"model": MODEL, "temperature": 0,
            "messages": [{"role": "system", "content": SYS},
                         {"role": "user", "content": "\n".join(lines)}]}
    for attempt in range(4):
        try:
            resp = requests.post(URL, headers={"Authorization": f"Bearer {KEY}",
                                 "Content-Type": "application/json"}, json=body, timeout=90)
            if resp.status_code == 200:
                j = resp.json()
                txt = j["choices"][0]["message"]["content"]
                txt = re.sub(r"^```json|^```|```$", "", txt.strip(), flags=re.M).strip()
                return json.loads(txt).get("v", []), j.get("usage", {})
        except Exception as e:
            if attempt == 3:
                print(f"  Batch-Fehler: {type(e).__name__}: {str(e)[:80]}", flush=True)
        time.sleep(2 * (attempt + 1))
    return [], {}


verdicts, in_tok, out_tok = {}, 0, 0
batches = [rows[i:i + BATCH] for i in range(0, len(rows), BATCH)]
WORKERS = int(os.environ.get("WORKERS", "10"))
if WORKERS > 1:
    from concurrent.futures import ThreadPoolExecutor
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for vs, usage in ex.map(ask, batches):
            for v in vs:
                verdicts[v.get("id")] = v.get("verdict")
            in_tok += usage.get("prompt_tokens", 0); out_tok += usage.get("completion_tokens", 0)
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(batches)} Batches · tok in {in_tok:,} out {out_tok:,}", flush=True)
else:
    for batch in batches:
        vs, usage = ask(batch)
        for v in vs:
            verdicts[v.get("id")] = v.get("verdict")
        in_tok += usage.get("prompt_tokens", 0); out_tok += usage.get("completion_tokens", 0)

# bestätigte Kanten: cand1/cand2/duplicate → Vorgänger; row-lookup
by_id = {r[0]: r for r in rows}
edges = []
from collections import Counter
dist = Counter()
for sid, verd in verdicts.items():
    dist[verd] += 1
    r = by_id.get(sid)
    if not r:
        continue
    pred = None
    if verd in ("cand1", "duplicate"):
        pred = r[3]
    elif verd == "cand2" and r[6]:
        pred = r[6]
    if pred:
        edges.append((sid, pred))

# Kostenschätzung (gemini-flash ~ $0.10/M in, $0.40/M out)
cost = in_tok/1e6*0.10 + out_tok/1e6*0.40
print(f"\nVerdikte: {dict(dist)}")
print(f"Bestätigte Vorgänger: {len(edges):,} von {len(rows):,} ({100*len(edges)/max(1,len(rows)):.0f}%)")
print(f"Tokens: in {in_tok:,} out {out_tok:,} · geschätzte Kosten ${cost:.4f}")
if LIMIT == 0:
    # nur beim Voll-Lauf zurückschreiben
    con.execute("CREATE TEMP TABLE le(successor VARCHAR, predecessor VARCHAR)")
    con.executemany("INSERT INTO le VALUES (?,?)", edges)
    con.execute(f"COPY (SELECT * FROM le) TO '{G}/succession_llm_edges.parquet' (FORMAT PARQUET)")
    print(f"→ geschrieben: {G}/succession_llm_edges.parquet")
print("DONE", flush=True)
