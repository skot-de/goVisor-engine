#!/usr/bin/env python3
"""Welcher Anbieter, welches Modell liefert die beste Dokumentenanalyse — am Produktivbestand.

**Warum nicht der Benchmark.** `scripts/llm_bench.py` misst vier Vorgaenge je Modell. Hier
werden **alle bisher analysierten Vergaben** ausgewertet: jeder Datensatz in
`web/data/doc-analysis.json` traegt seit dem 18.08. `provider` und `model`.

**Die drei Zahlen, und warum gerade diese:**

* **Zitat-Eintraege** — Checklistenpunkte, die das Modell mit einem woertlichen Beleg aus
  dem Dokument gefunden hat (`marking = "Zitat"`). Das ist der Ertrag.
* **Verwerfungsquote** — Anteil der Aussagen, die die Zitatpruefung wegwarf, weil das Zitat
  nicht woertlich im Dokument stand. Das ist die Genauigkeit, und die ehrlichere Zahl:
  viele Punkte bei hoher Verwerfung heisst viel behauptet, wenig belegt.
* **Ausbeute je 10k Token** — normiert auf die Textmenge, die das Modell gesehen hat.

⚠ **ZWEI FALLEN, die das Ergebnis verfaelschen wuerden, wenn man sie nicht behandelt:**

1. **Nicht jeder Checklisteneintrag stammt vom Modell.** 16.596 von 110.297 kommen aus den
   deterministischen Parsern (`parser` = gaeb/xlsx/pdf_fields) — Leistungsverzeichnisse,
   Formularfelder. Wer sie mitzaehlt, schreibt einem Modell die Arbeit des GAEB-Parsers gut.
   Gezaehlt werden deshalb nur Eintraege **ohne** `parser`.
2. **Die Zuteilung war NICHT zufaellig.** Welches Modell drankam, entschied das Guthaben des
   jeweiligen Anbieters. Die Modelle haben also verschiedene Vergaben gesehen, nicht
   dieselben. Deshalb stehen Tokenmenge und Dokumentzahl je Modell mit in der Tabelle: erst
   sie zeigen, ob ueberhaupt Vergleichbares verglichen wird.

Aufruf:  python3 scripts/llm_qualitaet.py
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUELLE = ROOT / "web" / "data" / "doc-analysis.json"


def main() -> int:
    if not QUELLE.exists():
        raise SystemExit(f"{QUELLE} fehlt — erst `scripts/analyze_docs.py` laufen lassen.")
    daten = json.loads(QUELLE.read_text(encoding="utf-8"))

    je = defaultdict(lambda: {"n": 0, "zitat": [], "verworfen": [], "token": [],
                              "doctypes": [], "ampel": defaultdict(int), "fehlend": 0,
                              "gekuerzt": 0, "leer": 0})
    for v in daten.values():
        p, m = v.get("provider"), v.get("model")
        s = je[(p or "—", m or "(nicht erfasst)")]
        s["n"] += 1
        cl = v.get("checklist") or []
        # NUR Modell-Eintraege: alles mit `parser` stammt aus einem deterministischen Leser.
        zitate = sum(1 for e in cl if not e.get("parser") and e.get("marking") == "Zitat")
        verworfen = v.get("rejected_items") or 0
        if not isinstance(verworfen, int):
            verworfen = len(verworfen)
        s["zitat"].append(zitate)
        s["verworfen"].append(verworfen)
        if zitate == 0:
            s["leer"] += 1
        if v.get("token_cost"):
            s["token"].append(v["token_cost"])
        s["doctypes"].append(len(v.get("doctypes_seen") or []))
        s["ampel"][v.get("ampel") or "—"] += 1
        if v.get("missing_expected"):
            s["fehlend"] += 1
        if v.get("truncated_doctypes"):
            s["gekuerzt"] += 1

    zeilen = []
    for (p, m), s in je.items():
        zit, verw = sum(s["zitat"]), sum(s["verworfen"])
        quote = verw / (zit + verw) if (zit + verw) else 0.0
        tok = st.mean(s["token"]) if s["token"] else 0
        zeilen.append({
            "anbieter": p, "modell": m, "n": s["n"],
            "zitat_je": zit / s["n"], "verwerfung": quote,
            "token": tok, "doctypes": st.mean(s["doctypes"]) if s["doctypes"] else 0,
            "je10k": (zit / s["n"]) / (tok / 10000) if tok else 0,
            "leer_pct": s["leer"] / s["n"], "gruen": s["ampel"].get("gruen", 0) / s["n"],
            "fehlend_pct": s["fehlend"] / s["n"],
        })
    zeilen.sort(key=lambda r: r["zitat_je"], reverse=True)

    print(f"\nDokumentenanalyse — {sum(r['n'] for r in zeilen):,} Vorgänge im Bestand\n"
          .replace(",", "."))
    print(f"{'Anbieter / Modell':<52}{'Vorg.':>7}{'Zitate':>8}{'verw.':>7}"
          f"{'je 10k Tok':>11}{'Ø Token':>9}{'ohne':>6}")
    print("─" * 100)
    for r in zeilen:
        name = f"{r['anbieter']}/{r['modell']}"
        print(f"{name:<52}{r['n']:>7,}{r['zitat_je']:>8.1f}{r['verwerfung']:>6.0%}"
              f"{r['je10k']:>11.1f}{r['token']:>9,.0f}{r['leer_pct']:>6.0%}".replace(",", "."))
    print("\nSpalten: Zitate = belegte Checklistenpunkte je Vorgang (nur Modell, ohne Parser) · "
          "verw. = Anteil verworfener Aussagen\nje 10k Tok = Ausbeute normiert auf Textmenge · "
          "ohne = Vorgänge, bei denen das Modell KEINEN belegten Punkt fand\n")
    print(f"{'Anbieter / Modell':<52}{'Ø Doktypen':>12}{'grün':>7}{'unvollständig':>15}")
    print("─" * 100)
    for r in zeilen:
        print(f"{r['anbieter'] + '/' + r['modell']:<52}{r['doctypes']:>12.1f}"
              f"{r['gruen']:>7.0%}{r['fehlend_pct']:>15.0%}")
    print("\n⚠ Die Zuteilung war nicht zufällig (Guthaben entschied). Ø Doktypen und Ø Token "
          "zeigen,\n  ob die Modelle vergleichbares Material gesehen haben.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
