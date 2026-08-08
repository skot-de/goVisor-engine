#!/usr/bin/env python3
"""Outreach-Log (Vertrieb, Spec §10) — wer wurde wann in welchem Segment mit welchem Ausgang
angesprochen. Zwei Zwecke:

  1. Doppelansprache verhindern — 12-Monats-Sperre, SEGMENTÜBERGREIFEND (Einheit = identity_id).
  2. Trefferquote je Segment messen — welches Segment konvertiert wirklich (Spec: nach ~50 Ansprachen
     die §8-Priorisierung nachjustieren).

Ablage: `data/outreach_log.csv` (Kontakt-/Vertriebsdaten → data/ ist Symlink aufs externe Volume,
NICHT git-getrackt). Append-only; Korrekturen über eine neue Zeile mit gleichem identity_id.

CLI:
  python3 scripts/outreach_log.py --log --id <identity_id> [--name .. --segment C --outcome interessiert]
  python3 scripts/outreach_log.py --cooldown [--months 12]   → JSON {identity_id: letztes_datum}
  python3 scripts/outreach_log.py --trefferquote             → JSON je Segment
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "outreach_log.csv"
FIELDS = ["identity_id", "firmenname", "segment", "angesprochen_am", "kanal", "outcome", "notiz"]
COOLDOWN_MONTHS = 12
# Vertrieb-Ausgang: 'angesprochen' = Erstkontakt; die drei folgenden speisen die Trefferquote.
OUTCOMES = ("angesprochen", "interessiert", "gewonnen", "kein_interesse", "kein_kontakt")
_POSITIV = ("interessiert", "gewonnen")


def _read():
    if not LOG.exists():
        return []
    with open(LOG, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _shift_months(d, months):
    """d um `months` verschoben (negativ = zurück, positiv = vor); Tag auf ≤28 gekappt."""
    total = (d.year * 12 + (d.month - 1)) + int(months)
    return date(total // 12, total % 12 + 1, min(d.day, 28))


def _minus_months(d, months):
    return _shift_months(d, -int(months))


def log_outreach(identity_id, firmenname="", segment="", kanal="", outcome="angesprochen", notiz="", am=None):
    if not identity_id:
        raise ValueError("identity_id fehlt")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG.exists()
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            wr.writeheader()
        wr.writerow({
            "identity_id": identity_id, "firmenname": firmenname, "segment": segment,
            "angesprochen_am": am or date.today().isoformat(), "kanal": kanal,
            "outcome": outcome if outcome in OUTCOMES else "angesprochen", "notiz": notiz,
        })
    return True


def cooldown_map(months=COOLDOWN_MONTHS, ref=None):
    """identity_id → letztes Ansprache-Datum, sofern innerhalb der Sperrfrist (segmentübergreifend)."""
    ref = ref or date.today()
    cutoff = _minus_months(ref, months)
    last = {}
    for r in _read():
        iid = r.get("identity_id")
        try:
            d = date.fromisoformat(r.get("angesprochen_am", ""))
        except ValueError:
            continue
        if iid and d >= cutoff and (iid not in last or d > last[iid]):
            last[iid] = d
    return {k: v.isoformat() for k, v in last.items()}


def trefferquote():
    """Je Segment: Zahl der Ansprachen + Ausgänge + Konversionsquote (interessiert+gewonnen)/n."""
    agg = defaultdict(lambda: defaultdict(int))
    for r in _read():
        seg = r.get("segment") or "?"
        oc = r.get("outcome") or "angesprochen"
        agg[seg][oc] += 1
        agg[seg]["_n"] += 1
    out = {}
    for seg, d in sorted(agg.items()):
        n = d["_n"]
        pos = sum(d.get(o, 0) for o in _POSITIV)
        out[seg] = {"n": n, "quote": round(pos / n * 100) if n else 0,
                    **{o: d.get(o, 0) for o in OUTCOMES}}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", action="store_true")
    ap.add_argument("--cooldown", action="store_true")
    ap.add_argument("--trefferquote", action="store_true")
    ap.add_argument("--months", type=int, default=COOLDOWN_MONTHS)
    ap.add_argument("--id"); ap.add_argument("--name", default=""); ap.add_argument("--segment", default="")
    ap.add_argument("--kanal", default=""); ap.add_argument("--outcome", default="angesprochen")
    ap.add_argument("--notiz", default="")
    a = ap.parse_args()
    try:
        if a.log:
            log_outreach(a.id, a.name, a.segment, a.kanal, a.outcome, a.notiz)
            out = {"ok": True, "id": a.id, "gesperrt_bis": _minus_months(date.today(), -a.months).isoformat()}
        elif a.cooldown:
            out = cooldown_map(a.months)
        elif a.trefferquote:
            out = trefferquote()
        else:
            out = {"error": "kein Modus (--log/--cooldown/--trefferquote)"}
    except Exception as e:  # noqa: BLE001
        out = {"error": str(e)[:200]}
    print(json.dumps(out, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
