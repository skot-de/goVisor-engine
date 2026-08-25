#!/usr/bin/env python3
"""Ticket #23 — Eval & Kostenmessung (§6a.4 Teil 1 + §16.6).

Teil A (§16.6): **Tokenvolumen der priorisierten Dokumenttypen je Vorgang** — misst, wie viel
des Pakets tatsächlich ans LLM geht (priorisierte Typen), je Branche (GAEB verschiebt den Bau
stark, weil das größte Dokument dort strukturiert geparst wird). Grundlage für die Free-Grenze.

Teil B (§6a.4 Teil 1): **automatischer Abgleich** der extrahierten Angebotsfrist gegen die
TED-Wahrheit über alle analysierten Vorgänge (Trefferquote). Für Wert/Vergabestelle/CPV liegt
die Wahrheit ebenfalls in TED — hier zunächst die Frist als stabilster Anker (§12.2).

Aufruf: python3 scripts/eval_extraction.py
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor import doctypes  # noqa: E402

DOC = ROOT / "data" / "docs" / "DE" / "doc_text.parquet"
ANALYSIS = ROOT / "web" / "data" / "doc-analysis.json"
OUTCSV = ROOT / "data" / "docs" / "study" / "eval_tokenvolumen.csv"
CHARS_PER_TOKEN = 4


def _branche_map() -> dict:
    m = {}
    for f in (ROOT / "web" / "data").glob("leads-*.json"):
        br = f.stem.split("leads-")[1]
        for r in json.loads(f.read_text()):
            m[str(r.get("id"))] = br
    return m


def part_a_tokenvolumen(con) -> None:
    """§16.6 — Tokenvolumen priorisierter vs. übriger Doktypen je Vorgang, je Branche."""
    rows = con.execute(
        f"""SELECT notice_id, file, length(text) AS n FROM read_parquet('{DOC.as_posix()}')
            WHERE status='ok' AND text IS NOT NULL"""
    ).fetchall()
    br = _branche_map()
    prio_chars = defaultdict(int)   # notice -> chars priorisierter Doktypen
    all_chars = defaultdict(int)
    for nid, file, n in rows:
        dt = doctypes.classify(file)
        all_chars[nid] += n or 0
        if doctypes.is_priority(dt):
            prio_chars[nid] += n or 0

    # je Branche aggregieren
    per_br = defaultdict(lambda: {"n": 0, "prio_tok": 0, "all_tok": 0})
    for nid in all_chars:
        b = br.get(nid, "?")
        per_br[b]["n"] += 1
        per_br[b]["prio_tok"] += prio_chars[nid] // CHARS_PER_TOKEN
        per_br[b]["all_tok"] += all_chars[nid] // CHARS_PER_TOKEN

    print("── §16.6 Tokenvolumen: priorisierte Doktypen je Branche ──")
    print(f"{'Branche':14}{'n':>5}{'Ø prio-Tok':>12}{'Ø ges-Tok':>12}{'prio-Anteil':>13}")
    out = [["branche", "n", "avg_prio_tokens", "avg_total_tokens", "prio_share_%"]]
    for b, d in sorted(per_br.items(), key=lambda kv: -kv[1]["n"]):
        if not d["n"]:
            continue
        ap, at = d["prio_tok"] // d["n"], d["all_tok"] // d["n"]
        share = round(100 * d["prio_tok"] / max(d["all_tok"], 1))
        print(f"{b:14}{d['n']:>5}{ap:>12,}{at:>12,}{share:>12}%")
        out.append([b, d["n"], ap, at, share])
    OUTCSV.parent.mkdir(parents=True, exist_ok=True)
    import csv
    with open(OUTCSV, "w", newline="") as fh:
        csv.writer(fh).writerows(out)
    print(f"→ {OUTCSV.relative_to(ROOT)}")


def _extract_deadline(analysis: dict) -> str | None:
    """Angebotsfrist aus der Checkliste (frist-Items) — erstes plausibles Datum."""
    for it in analysis.get("checklist", []):
        if it.get("req_type") == "frist":
            m = re.search(r"\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}|\d{4}-\d{2}-\d{2}", str(it.get("value") or ""))
            if m:
                return re.sub(r"\D", "", m.group(0))
    return None


def part_b_frist_eval(con) -> None:
    """§6a.4 Teil 1 — extrahierte Angebotsfrist gegen TED-Wahrheit (Trefferquote)."""
    if not ANALYSIS.exists():
        print("\n(§6a.4) keine doc-analysis.json — übersprungen"); return
    analyses = json.loads(ANALYSIS.read_text())
    ted = {}
    try:
        for nid, dl in con.execute(
            "SELECT notice_id, deadline_date FROM read_parquet('data/gold/DE/lead_deadline.parquet')"
        ).fetchall():
            ted[str(nid)] = re.sub(r"\D", "", str(dl or ""))[:8]
    except Exception as e:
        print(f"\n(§6a.4) lead_deadline nicht lesbar ({e}) — übersprungen"); return

    checked = hit = has_truth = 0
    for nid, a in analyses.items():
        if not isinstance(a, dict) or "checklist" not in a:
            continue
        truth = ted.get(str(nid))
        if not truth:
            continue
        has_truth += 1
        got = _extract_deadline(a)
        if got:
            checked += 1
            if got[:8] == truth:
                hit += 1
    print("\n── §6a.4 Teil 1: Angebotsfrist extrahiert vs. TED ──")
    print(f"  analysierte Vorgänge mit TED-Frist: {has_truth}")
    print(f"  davon Frist extrahiert:             {checked}")
    print(f"  davon exakt getroffen:              {hit}" + (f"  ({100*hit//max(checked,1)} %)" if checked else ""))
    print("  (kleine Stichprobe — der Wert wächst mit mehr Analysen; Rahmen steht.)")


def main() -> int:
    if not DOC.exists():
        print(f"FEHLT: {DOC}"); return 1
    con = duckdb.connect()
    part_a_tokenvolumen(con)
    part_b_frist_eval(con)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
