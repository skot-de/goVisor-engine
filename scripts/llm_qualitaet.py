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
sys.path.insert(0, str(ROOT))
QUELLE = ROOT / "web" / "data" / "doc-analysis.json"

from govisor import kostenbuch  # noqa: E402


def kosten_je_vorgang() -> dict[str, float]:
    """Was jede Vergabe an LLM-Geld gekostet hat — aus dem Kostenbuch, je Vorgang.

    **Warum exakt und nicht geschätzt.** `scripts/analyze_docs.py` setzt seit dem
    2026-08-23 den Rahmen ``llm.kontext(zweck="analyse", vorgang=nid)``; jede Zeile im
    Kostenbuch trägt deshalb die Vergabe, für die sie bezahlt wurde. Damit lässt sich der
    Preis der Zeile genau dem Ergebnis zuordnen, statt Tagessummen über Modelle zu verteilen.

    ⚠ **Das Buch ist jünger als der Bestand.** Es beginnt am 2026-08-23; alles davor
    analysierte hat keinen Preis und darf deshalb auch nicht in einen Durchschnitt
    einfließen. Die Auswertung unten zählt nur Vorgänge, für die tatsächlich eine Buchung
    vorliegt, und schreibt dazu, wie viele das sind. Ein Preis über einen unbekannten Nenner
    wäre schlimmer als gar keiner.
    """
    aus: dict[str, float] = {}
    for z in kostenbuch.lies():
        nid = z.get("vorgang")
        if not nid or z.get("zweck") != "analyse" or z.get("kosten_usd") is None:
            continue
        aus[nid] = aus.get(nid, 0.0) + float(z["kosten_usd"])
    return aus


def zeitpunkt_je_vorgang() -> dict[str, str]:
    """Wann wurde eine Vergabe analysiert? Datensatzfeld zuerst, sonst das Kostenbuch.

    ``analysiert_am`` gibt es seit dem 2026-08-23. Für alles davor liefert das Kostenbuch
    kein Ersatzdatum (es ist genauso jung), und **das wird auch nicht geschätzt**: eine
    erfundene Einordnung in der Zeitreihe wäre schlimmer als eine Lücke, weil sie wie ein
    Messwert aussieht.
    """
    aus: dict[str, str] = {}
    for z in kostenbuch.lies():
        nid, ts = z.get("vorgang"), z.get("ts") or ""
        if nid and ts and z.get("zweck") == "analyse":
            # ⚠ `ts[:10]` waere der UTC-Tag; `analysiert_am` steht in Ortszeit. Ein
            # roher Praefix haette beide Basen gemischt (s. `kostenbuch.lokaler_tag`).
            aus.setdefault(nid, kostenbuch.lokaler_tag(z) or ts[:10])
    return aus


def _woche(tag: str) -> str:
    import datetime as dt
    try:
        d = dt.date.fromisoformat(tag)
    except ValueError:
        return "?"
    j, w, _ = d.isocalendar()
    return f"{j}-KW{w:02d}"


def zeitreihe(daten: dict, je: str = "woche") -> int:
    """Die Kennzahlen über die Zeit — damit Abdriften sichtbar wird, statt sich zu mitteln."""
    from collections import defaultdict
    ersatz = zeitpunkt_je_vorgang()
    preise = kosten_je_vorgang()
    eimer = defaultdict(lambda: defaultdict(lambda: {"n": 0, "zitat": 0, "verworfen": 0,
                                                     "usd": 0.0, "usd_n": 0}))
    ohne_datum = 0
    for nid, v in daten.items():
        tag = v.get("analysiert_am") or ersatz.get(nid)
        if not tag:
            ohne_datum += 1
            continue
        schl = _woche(tag) if je == "woche" else tag
        g = eimer[schl][v.get("model") or "(nicht erfasst)"]
        cl = v.get("checklist") or []
        z = sum(1 for e in cl if not e.get("parser") and e.get("marking") == "Zitat")
        vw = v.get("rejected_items") or 0
        g["n"] += 1
        g["zitat"] += z
        g["verworfen"] += vw if isinstance(vw, int) else len(vw)
        if nid in preise:
            g["usd"] += preise[nid]
            g["usd_n"] += 1

    if not eimer:
        print(f"\nZeitreihe: noch keine datierten Analysen.\n"
              f"  `analysiert_am` wird seit dem 2026-08-23 geschrieben; ältere Datensätze\n"
              f"  tragen kein Datum und werden bewusst NICHT geschätzt.\n"
              f"  {ohne_datum:,} Vorgänge ohne Datum.\n".replace(",", "."))
        return 0

    print(f"\nZeitreihe je {je.capitalize()} — Abdriften wird hier sichtbar, im "
          f"Gesamtdurchschnitt nicht\n")
    print(f"{'Zeitraum':<12}{'Modell':<38}{'Vorg.':>7}{'Zitate':>8}{'verw.':>7}"
          f"{'USD/Vorg':>10}{'USD/Zitat':>11}")
    print("─" * 100)
    verlauf = defaultdict(list)
    for schl in sorted(eimer):
        for modell, g in sorted(eimer[schl].items()):
            zit_je = g["zitat"] / g["n"]
            quote = g["verworfen"] / max(g["zitat"] + g["verworfen"], 1)
            usd_v = g["usd"] / g["usd_n"] if g["usd_n"] else 0.0
            usd_z = g["usd"] / g["zitat"] if g["zitat"] and g["usd_n"] else 0.0
            print(f"{schl:<12}{modell:<38}{g['n']:>7,}{zit_je:>8.1f}{quote:>6.0%}"
                  f"{usd_v:>10.4f}{usd_z:>11.5f}".replace(",", "."))
            verlauf[modell].append((schl, zit_je, quote))

    # ── Abdriftwarnung ───────────────────────────────────────────────────────────────
    # Der jüngste Zeitraum gegen den Median der vorherigen. Median, nicht Mittelwert:
    # ein einzelner Ausreisser soll die Messlatte nicht verschieben.
    print()
    for modell, reihe in verlauf.items():
        if len(reihe) < 3:
            continue
        *vorher, (schl, zit, quote) = reihe
        m_zit = st.median([x[1] for x in vorher])
        m_q = st.median([x[2] for x in vorher])
        warnung = []
        if m_zit > 0 and zit < m_zit * 0.85:
            warnung.append(f"Ausbeute {zit:.1f} statt sonst {m_zit:.1f} (−{(1-zit/m_zit):.0%})")
        if quote > m_q + 0.05:
            warnung.append(f"Verwerfung {quote:.0%} statt sonst {m_q:.0%}")
        if warnung:
            print(f"⚠ {modell} in {schl}: " + " · ".join(warnung))
            print("  Ein Modell kann sich ändern, ohne dass es jemand ankündigt "
                  "(Quantisierung, Endpunkt). Prüfen: scripts/llm_bench.py --n 15")
    if ohne_datum:
        print(f"\n{ohne_datum:,} Vorgänge ohne Datum (vor dem 2026-08-23) sind nicht "
              f"enthalten.".replace(",", "."))
    print()
    return 0


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--zeitreihe", action="store_true",
                    help="Kennzahlen über die Zeit statt über den Gesamtbestand")
    ap.add_argument("--je", choices=("woche", "tag"), default="woche")
    a = ap.parse_args()

    if not QUELLE.exists():
        raise SystemExit(f"{QUELLE} fehlt — erst `scripts/analyze_docs.py` laufen lassen.")
    daten = json.loads(QUELLE.read_text(encoding="utf-8"))
    if a.zeitreihe:
        return zeitreihe(daten, a.je)

    preise = kosten_je_vorgang()
    je = defaultdict(lambda: {"n": 0, "zitat": [], "verworfen": [], "token": [],
                              "doctypes": [], "ampel": defaultdict(int), "fehlend": 0,
                              "gekuerzt": 0, "leer": 0, "usd": 0.0, "usd_n": 0,
                              "usd_zitate": 0})
    for nid, v in daten.items():
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
        if nid in preise:                    # nur Vorgaenge MIT Buchung, s. kosten_je_vorgang
            s["usd"] += preise[nid]
            s["usd_n"] += 1
            s["usd_zitate"] += zitate

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
            "usd": s["usd"], "usd_n": s["usd_n"],
            "usd_je_vorgang": s["usd"] / s["usd_n"] if s["usd_n"] else 0.0,
            "usd_je_zitat": s["usd"] / s["usd_zitate"] if s["usd_zitate"] else 0.0,
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
          "zeigen,\n  ob die Modelle vergleichbares Material gesehen haben.")
    print("  Für einen sauberen Vergleich derselben Vorgänge: scripts/llm_bench.py\n")

    belegt = [r for r in zeilen if r["usd_n"]]
    if belegt:
        print(f"{'Anbieter / Modell':<52}{'mit Preis':>11}{'USD gesamt':>12}"
              f"{'USD/Vorgang':>13}{'USD/Zitat':>11}")
        print("─" * 100)
        for r in sorted(belegt, key=lambda x: -x["usd"]):
            print(f"{r['anbieter'] + '/' + r['modell']:<52}"
                  f"{r['usd_n']:>8,} /{r['n']:>6,}".replace(",", ".")
                  + f"{r['usd']:>12.4f}{r['usd_je_vorgang']:>13.4f}{r['usd_je_zitat']:>11.5f}")
        gesamt_n = sum(r["usd_n"] for r in belegt)
        print(f"\n  Grundlage: {gesamt_n:,} von {sum(r['n'] for r in zeilen):,} Vorgängen haben "
              f"eine Buchung.".replace(",", "."))
        print("  Das Kostenbuch beginnt am 2026-08-23; ältere Analysen tragen keinen Preis.\n")
    else:
        print(f"Kosten: noch keine Buchungen für Vorgänge aus diesem Bestand "
              f"({kostenbuch.PFAD.name}).\n"
              f"  Sie entstehen ab dem nächsten Analyse-Lauf von selbst.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
