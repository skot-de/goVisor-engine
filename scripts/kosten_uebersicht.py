"""LLM-Kosten-Uebersicht fuers Admin-Portal (Bereich 6) — kompaktes JSON aus dem Kostenbuch
(`data/llm_kosten.jsonl`, geschrieben von govisor/kostenbuch.py). Nur lesend.

    python3 scripts/kosten_uebersicht.py
"""
from __future__ import annotations
import glob, json, collections, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    dateien = sorted(glob.glob(str(ROOT / "data" / "llm_kosten*.jsonl")))
    tot = 0.0; n = 0; abgebrochen = 0; leer = 0; seit = None
    mod = collections.Counter(); zweck = collections.Counter()
    tage = collections.Counter()
    heute = dt.date.today()
    for f in dateien:
        for line in open(f, encoding="utf-8"):
            try: d = json.loads(line)
            except Exception: continue
            n += 1
            k = float(d.get("kosten_usd") or 0)
            tot += k
            mod[d.get("modell") or "?"] += k
            zweck[d.get("zweck") or "?"] += k
            if d.get("abgebrochen"): abgebrochen += 1
            if d.get("leer"): leer += 1
            ts = str(d.get("ts") or "")[:10]
            if ts:
                if seit is None or ts < seit: seit = ts
                try:
                    tag = dt.date.fromisoformat(ts)
                    if (heute - tag).days < 14: tage[ts] += k
                except ValueError: pass
    top = lambda c: [{"name": k2, "usd": round(v, 4)} for k2, v in c.most_common(8)]
    out = {
        "gesamt_usd": round(tot, 2), "aufrufe": n, "seit": seit,
        "abgebrochen": abgebrochen, "leer": leer,
        "je_modell": top(mod), "je_zweck": top(zweck),
        "letzte_tage": [{"tag": t, "usd": round(v, 4)} for t, v in sorted(tage.items())],
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
