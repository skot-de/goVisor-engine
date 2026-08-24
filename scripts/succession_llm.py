"""LLM-Adjudikation der mehrdeutigen Nachfolge-Kandidaten (Stufe C).

Liest die LLM-Queue, reichert Titel an, fragt ein günstiges Modell über OpenRouter,
schreibt bestätigte Kanten. Key kommt aus $OPENROUTER_KEY_FILE (nie im Code/Repo).

Aufruf: LIMIT=20 python scripts/succession_llm.py   (Pilot)
        LIMIT=0  python scripts/succession_llm.py   (alle)
"""
import os, re, json, time, duckdb

# Der Schluessel wird nicht mehr hier gelesen — `govisor.llm` holt ihn selbst.
# Seit 2026-08-24 läuft dieses Skript über `govisor.llm.chat()` und damit unter allen
# Bremsen: Reserve, Lauf- und Tagesdeckel, Schonung, Gesamtfrist, Anbieterboden — und jeder
# Aufruf steht mit Preis im Kostenbuch, unter dem Zweck „nachfolge".
# `python scripts/…` setzt sys.path[0] auf scripts/, nicht auf die Wurzel — ohne die
# naechste Zeile scheitert der Import mit ModuleNotFoundError.
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from govisor import llm as _llm  # noqa: E402
from govisor.llm import mit_boden as _mit_boden  # noqa: E402

# ⚠ HIER STAND `google/gemini-2.0-flash-001` FEST EINGEBAUT — und das Modell gibt es im
# OpenRouter-Katalog nicht mehr. Jeder Aufruf lief in ein HTTP 404, wurde vom damaligen
# `except` geschluckt und als „Batch-Fehler" gemeldet; das Skript lieferte seit dem Rückzug
# des Modells stumm null Verdikte. Ein fest eingetragener Modellname ist eine Zeitbombe mit
# unbekannter Zündschnur.
#
# Jetzt gilt dieselbe Wahl wie in der Analyse: `llm.DEFAULT_MODEL` folgt `OR_MODEL` und dem
# Anbieterboden, und wenn der Prüfstand irgendwann ein anderes Modell freigibt, zieht dieses
# Skript automatisch mit.
MODEL = _mit_boden(os.environ.get("OR_MODEL") or _llm.DEFAULT_MODEL)
LIMIT = int(os.environ.get("LIMIT", "20"))
BATCH = int(os.environ.get("BATCH", "10"))
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
    messages = [{"role": "system", "content": SYS},
                {"role": "user", "content": "\n".join(lines)}]
    # ⚠ FRUEHER STAND HIER EIN EIGENES `requests.post`. Damit lief dieses Skript an ALLEM
    # vorbei, was Geld absichert: keine Reserve, kein Lauf- und Tagesdeckel, keine
    # Schonung, keine Gesamtfrist — und keine Zeile im Kostenbuch, also eine unerklaerte
    # Luecke im Abgleich. Mit `LIMIT` war der Schaden begrenzt, `LIMIT=0` haette ungebremst
    # Geld ausgegeben. Ueber `llm.chat()` gelten alle Bremsen, und der Verbrauch taucht
    # unter dem Zweck „nachfolge" im Buch auf.
    try:
        with _llm.kontext(zweck="nachfolge"):
            txt = _llm.chat(messages, model=MODEL, temperature=0, timeout=90, max_retries=4)
    except _llm.BudgetErschoepft as e:
        print(f"  Geldwache: {e}", flush=True)
        return [], {}
    except Exception as e:                               # noqa: BLE001
        print(f"  Batch-Fehler: {type(e).__name__}: {str(e)[:80]}", flush=True)
        return [], {}
    txt = re.sub(r"^```json|^```|```$", "", (txt or "").strip(), flags=re.M).strip()
    try:
        verdikte = json.loads(txt).get("v", [])
    except json.JSONDecodeError:
        print("  Antwort war kein lesbares JSON — Batch verworfen.", flush=True)
        return [], {}
    # Tokenzahlen kommen jetzt aus dem Kostenbuch statt aus der rohen Antwort.
    v = _llm.letzter_verbrauch()
    return verdikte, {"kosten_usd": v.get("kosten_usd")}


# ⚠ FRUEHER WURDEN HIER TOKEN GEZAEHLT UND DIE KOSTEN GESCHAETZT — mit fest eingebauten
# 0,10 / 0,40 $ je Mio, also den Preisen eines Modells, das es nicht mehr gibt. Eine
# geschaetzte Zahl, die nach einer gemessenen aussieht, ist schlimmer als gar keine.
# Jetzt wird der tatsaechlich abgerechnete Betrag aus dem Kostenbuch summiert.
verdicts, kosten_usd = {}, 0.0
batches = [rows[i:i + BATCH] for i in range(0, len(rows), BATCH)]
WORKERS = int(os.environ.get("WORKERS", "10"))
if WORKERS > 1:
    from concurrent.futures import ThreadPoolExecutor
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for vs, usage in ex.map(ask, batches):
            for v in vs:
                verdicts[v.get("id")] = v.get("verdict")
            kosten_usd += usage.get("kosten_usd") or 0.0
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(batches)} Batches · {kosten_usd:.4f} $", flush=True)
else:
    for batch in batches:
        vs, usage = ask(batch)
        for v in vs:
            verdicts[v.get("id")] = v.get("verdict")
        kosten_usd += usage.get("kosten_usd") or 0.0

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

print(f"\nVerdikte: {dict(dist)}")
print(f"Bestätigte Vorgänger: {len(edges):,} von {len(rows):,} ({100*len(edges)/max(1,len(rows)):.0f}%)")
print(f"Kosten laut Kostenbuch: ${kosten_usd:.4f} (abgerechnet, nicht geschätzt)")
if LIMIT == 0:
    # nur beim Voll-Lauf zurückschreiben
    con.execute("CREATE TEMP TABLE le(successor VARCHAR, predecessor VARCHAR)")
    con.executemany("INSERT INTO le VALUES (?,?)", edges)
    con.execute(f"COPY (SELECT * FROM le) TO '{G}/succession_llm_edges.parquet' (FORMAT PARQUET)")
    print(f"→ geschrieben: {G}/succession_llm_edges.parquet")
print("DONE", flush=True)
