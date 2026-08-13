"""Selbstdiagnose des Dokument-Parsers: wo greifen die Regeln zu kurz?

**Die Idee.** Der Parser weiß selbst, wann er etwas verpasst: wenn ein Thema im Dokument
vorkommt (Anker trifft), aber kein Wert herauskommt (Regel trifft nicht). Diese Differenz —
die **Trefferlücke** — ist die Arbeitsliste. Genau so wurde am 2026-08-13 die Bindefrist
gefunden: „Bindefrist" stand in 392 Dokumenten, extrahiert wurde 1 Wert.

**Warum das Skript keine Regeln schreibt.** Ein Parser, der sich selbst erweitert, stürzt bei
einem Fehler nicht ab — er liefert *plausible falsche Zahlen*. „Vertragsstrafe 5 %" statt
0,5 % fällt niemandem auf, bis danach kalkuliert wird; und an diesen Zahlen hängt die
Erfolgsprämie. Außerdem wäre keine frühere Auswertung mehr reproduzierbar. Deshalb:
**das Skript diagnostiziert und schlägt vor, ein Mensch entscheidet.** Dasselbe Muster wie
bei `review_queue` und der handkuratierten Entity-Alias-CSV.

**Was es tut**
  1. Je Signal: wie oft ist das Thema da (Anker), wie oft kommt ein Wert heraus (Regel)?
  2. Für die Fehlschläge: das Textumfeld einsammeln, Ziffern zu ``#`` normalisieren und die
     häufigsten FORMEN zählen. Was oft vorkommt und nicht erfasst wird, ist der nächste
     Regel-Kandidat.
  3. Ausgabe als JSON (maschinenlesbar) + Klartext-Bericht.

Die Anker stehen bewusst in ``govisor/docsignals.py`` neben den Regeln, nicht hier — beim
ersten Anlauf lagen sie getrennt und waren enger als die Regeln, worauf die Metrik negative
Lücken meldete. Man misst sonst den eigenen Messfehler.

Aufruf:  python3 scripts/parser_gaps.py [--country DE] [--top 8] [--min 10]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import docsignals  # noqa: E402  (Pfad muss zuerst stehen)

_FLAGS = re.IGNORECASE | re.DOTALL

# Signale, die DASSELBE beantworten und sich denselben Anker teilen. `binding_days` und
# `binding_until` sind Alternativen — die Bindefrist steht entweder als Tageszahl ODER als
# Datum. Ohne diese Zuordnung zeigte der Bericht für `binding_days` eine dauerhafte Lücke von
# 191, die sich nie schliessen laesst: ein rotes Feld, das man nach zwei Wochen ignoriert.
# Eine Metrik, die immer Alarm gibt, ist keine Metrik.
ALTERNATIVEN: dict[str, tuple[str, ...]] = {
    "binding_days": ("binding_until",),
    "binding_until": ("binding_days",),
}
_UMFELD = 55          # Zeichen links/rechts vom Ankertreffer
_MAX_FUNDE = 6        # je Dokument und Signal — sonst dominiert ein Formularsatz die Statistik


def _form(s: str) -> str:
    """Textstelle → FORM. Ziffern zu ``#``, Weißraum vereinheitlicht.

    So fallen „endet am 03.11.2026" und „endet am 25.09.2026" zu EINER Form zusammen —
    das ist der Punkt: nicht die Werte zählen, sondern die Schreibweisen.
    """
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\d", "#", s)
    return re.sub(r"#+", "#", s)


def analysiere(country: str, top: int, mindest: int) -> dict:
    import duckdb

    src = ROOT / "data" / "docs" / country / "doc_text.parquet"
    if not src.exists():
        print(f"kein {src} — erst `fetch-docs` + `index-docs` laufen lassen.")
        return {}
    con = duckdb.connect()
    docs = con.execute(
        f"""SELECT notice_id, string_agg(text, ' ' ORDER BY file) AS full
            FROM read_parquet('{src.as_posix()}') WHERE status='ok' GROUP BY notice_id""").fetchall()

    erwaehnt: Counter = Counter()
    erkannt: Counter = Counter()
    formen: dict[str, Counter] = {k: Counter() for k in docsignals.ANKER}

    for _nid, text in docs:
        t = text or ""
        sig = docsignals.extract_signals(t)
        for signal, anker in docsignals.ANKER.items():
            treffer = list(re.finditer(anker, t, _FLAGS))
            if not treffer:
                continue
            erwaehnt[signal] += 1
            if sig.get(signal) is not None or any(sig.get(x) is not None for x in ALTERNATIVEN.get(signal, ())):
                erkannt[signal] += 1
                continue
            # Fehlschlag: das Thema steht da, ein Wert kam nicht heraus → Formen sammeln.
            for m in treffer[:_MAX_FUNDE]:
                a, b = max(0, m.start() - _UMFELD), min(len(t), m.end() + _UMFELD)
                formen[signal][_form(t[a:b])] += 1

    bericht = {"country": country, "dokumente": len(docs), "signale": {}}
    for signal in sorted(docsignals.ANKER, key=lambda s: -(erwaehnt[s] - erkannt[s])):
        e, k = erwaehnt[signal], erkannt[signal]
        luecke = e - k
        bericht["signale"][signal] = {
            "erwaehnt": e, "erkannt": k, "luecke": luecke,
            "quote": round(k / e, 3) if e else None,
            "unerkannte_formen": [
                {"form": f, "n": n} for f, n in formen[signal].most_common(top) if n >= mindest
            ],
        }
    return bericht


def main(country: str, top: int, mindest: int) -> int:
    b = analysiere(country, top, mindest)
    if not b:
        return 1
    ziel = ROOT / "data" / "docs" / country / "parser_gaps.json"
    ziel.write_text(json.dumps(b, ensure_ascii=False, indent=1) + "\n")

    print(f"Parser-Selbstdiagnose {country} — {b['dokumente']} Dokumente\n")
    print(f"  {'Signal':<24}{'erwähnt':>9}{'erkannt':>9}{'Lücke':>8}{'Quote':>8}")
    for name, d in b["signale"].items():
        q = f"{d['quote']:.0%}" if d["quote"] is not None else "—"
        print(f"  {name:<24}{d['erwaehnt']:>9}{d['erkannt']:>9}{d['luecke']:>8}{q:>8}")

    print("\nHäufigste NICHT erfasste Formen (Kandidaten für neue Regeln):")
    for name, d in b["signale"].items():
        if not d["unerkannte_formen"]:
            continue
        print(f"\n  ── {name}  (Lücke {d['luecke']})")
        for f in d["unerkannte_formen"]:
            print(f"     {f['n']:>4}×  {f['form'][:118]}")
    print(f"\n→ {ziel.relative_to(ROOT)}")
    print("Hinweis: Vorschläge, keine Regeln. Übernommen wird von Hand — ein selbst "
          "geschriebener Ausdruck liefert im Fehlerfall plausible falsche Zahlen.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="DE")
    ap.add_argument("--top", type=int, default=8, help="Formen je Signal")
    ap.add_argument("--min", dest="mindest", type=int, default=10, help="Mindesthäufigkeit")
    a = ap.parse_args()
    sys.exit(main(a.country, a.top, a.mindest))
