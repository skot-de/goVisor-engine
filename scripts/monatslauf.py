#!/usr/bin/env python3
"""Monatslauf (Vertrieb, Spec §10) — erzeugt je fälligem Segment die Zielliste des Monats,
schließt kürzlich Angesprochene aus (12-Monats-Sperre aus dem outreach_log) und legt CSVs ab.

Neuberechnungs-Kadenz (§10):
  F, E        → jeden Monat        (kurzes Zeitfenster / wandernde Auslauftermine)
  C, D, G     → quartalsweise      (Jan/Apr/Jul/Okt)
  A, B        → halbjährlich       (Jan/Jul)

Aufruf: python3 scripts/monatslauf.py [--month YYYY-MM] [--limit 300] [--all] [--segments C,E]
Ausgabe: data/zielliste/<YYYY-MM>/<SEG>.csv  (+ Trefferquote-Report auf stdout).
"""
import argparse
import csv
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import firmen_suche as FS  # noqa: E402
import outreach_log as OL  # noqa: E402

# Fälligkeit je Segment: (Kadenz-Monate, Anker) — Monat fällig, wenn (monat-anker) % kadenz == 0
CADENCE = {
    "F": 1, "E": 1,          # monatlich
    "C": 3, "D": 3, "G": 3,  # quartalsweise (Jan/Apr/Jul/Okt)
    "A": 6, "B": 6,          # halbjährlich (Jan/Jul)
}
OUT_FIELDS = ["identity_id", "firmenname", "segment", "signal", "kontext", "weitere_segmente",
              "rahmen_quote_pct", "plz", "ort", "telefon", "email"]


def due_segments(month):
    """Segmente, die im gegebenen Monat (1–12) neu zu rechnen sind."""
    return [s for s, cad in CADENCE.items() if (month - 1) % cad == 0]


def run(month_str=None, limit=300, only=None, force_all=False):
    today = date.today()
    if month_str:
        y, m = (int(x) for x in month_str.split("-"))
    else:
        y, m = today.year, today.month
    tag = f"{y:04d}-{m:02d}"
    segs = only or (list(CADENCE) if force_all else due_segments(m))
    cooldown = OL.cooldown_map()               # identity_id → letztes Datum (12-Monats-Sperre)
    outdir = ROOT / "data" / "zielliste" / tag
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Monatslauf {tag} — fällige Segmente: {', '.join(segs) or '(keine)'}")
    print(f"12-Monats-Sperre: {len(cooldown)} Identitäten aktuell gesperrt\n")
    summary = []
    for seg in segs:
        res = FS.segment(seg, limit=limit)
        firmen = res.get("firmen", [])
        frisch = [f for f in firmen if f["id"] not in cooldown]
        gesperrt = len(firmen) - len(frisch)
        path = outdir / f"{seg}.csv"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            wr = csv.DictWriter(fh, fieldnames=OUT_FIELDS)
            wr.writeheader()
            for f in frisch:
                wr.writerow({
                    "identity_id": f["id"], "firmenname": f["name"], "segment": seg,
                    "signal": (f.get("badge") or {}).get("label", ""), "kontext": f.get("line", ""),
                    "weitere_segmente": " / ".join(w["label"] for w in f.get("weitere", [])),
                    "rahmen_quote_pct": f.get("rahmenQuote", ""),
                    "plz": f.get("plz") or "", "ort": f.get("ort") or "",
                    "telefon": f.get("phone") or "", "email": f.get("email") or "",
                })
        summary.append((seg, res.get("label", seg), len(frisch), gesperrt))
        print(f"  {seg} {res.get('label',''):24} {len(frisch):>4} frische Ziele "
              f"(− {gesperrt} in Sperrfrist) → {path.relative_to(ROOT)}")

    # Trefferquote-Report (Spec: nach ~50 Ansprachen die Priorisierung nachjustieren)
    tq = OL.trefferquote()
    if tq:
        print("\nTrefferquote je Segment (aus outreach_log):")
        for seg, d in tq.items():
            print(f"  {seg}: {d['n']:>3} Ansprachen · Quote {d['quote']:>3}% "
                  f"(interessiert {d['interessiert']}, gewonnen {d['gewonnen']}, "
                  f"kein Interesse {d['kein_interesse']})")
    else:
        print("\nTrefferquote: noch keine Ansprachen protokolliert.")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", help="YYYY-MM (Default: aktueller Monat)")
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--all", action="store_true", help="alle 7 Segmente, unabhängig von der Kadenz")
    ap.add_argument("--segments", help="Komma-Liste, z. B. C,E (überschreibt die Kadenz)")
    a = ap.parse_args()
    only = [s.strip().upper() for s in a.segments.split(",")] if a.segments else None
    run(a.month, a.limit, only, a.all)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
