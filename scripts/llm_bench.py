#!/usr/bin/env python3
"""Welches Modell analysiert Vergabeunterlagen am besten? Gemessen, nicht geglaubt.

**Warum es das gibt.** Seit dem 2026-08-18 haengen fuenf Anbieter in der Kette, und welcher
drankommt, entschied bis dahin das Guthaben. Das ist die falsche Reihenfolge: gemessen findet
Cerebras' gpt-oss-120b rund ein Drittel weniger Pruefpunkte als Gemini (34 statt 53) und
verwirft fast doppelt so viele Zitate (19 % statt 11 %). Sven: „mach es so das die qualitaet
bei der analyse hoch bleibt." Dafuer muss man wissen, wer wie gut ist.

**Wie gemessen wird.** Dieselben Vorgaenge durch jedes Modell, danach drei Zahlen:

  * **Punkte** — verifizierte Checklisten-Eintraege. Mehr ist besser, aber nur, wenn belegt.
  * **Verwerfungsquote** — Anteil der Aussagen, die die Zitatpruefung wegwarf, weil das
    Zitat nicht woertlich im Dokument stand. Hoch heisst: das Modell erfindet Formulierungen.
  * **Sekunden** — bei 4.200 wartenden Vorgaengen entscheidet das ueber Stunden.

Die Verwerfungsquote ist die ehrlichste der drei: sie misst nicht Fleiss, sondern Genauigkeit.
Ein Modell mit vielen Punkten UND hoher Verwerfung hat viel behauptet und wenig belegt.

Aufruf::

    scripts/llm_bench.py                 # Vorgabe: 4 Vorgaenge, alle Kandidaten
    scripts/llm_bench.py --n 8
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor import llm  # noqa: E402
from govisor.docpipe import SQL_BRAUCHBAR  # noqa: E402

# Kandidaten: je Anbieter das staerkste Modell, das schnell genug antwortet. Was zu langsam
# war, steht mit Messwert dabei — damit niemand es „mal wieder probiert".
KANDIDATEN = [
    # OpenRouter-Auswahl, 2026-08-21. Alle koennen erzwungene Schema-Ausgabe; Preise je
    # Mio Token (Eingabe/Ausgabe) aus dem OpenRouter-Katalog, `:batch` waere jeweils halb
    # so teuer und fuer diesen Stapelbetrieb die richtige Wahl.
    ("openrouter", "google/gemini-2.5-flash"),      # 0,30 / 2,50 — der gemessene Titelverteidiger
    ("openrouter", "google/gemini-3.6-flash"),      # 0,75 / 3,75 — neuere Generation
    ("openrouter", "openai/gpt-5-mini"),            # 0,25 / 2,00 — guenstigste Alternative
    ("openrouter", "anthropic/claude-haiku-4.5"),   # 1,00 / 5,00 — Woertlichkeits-Hypothese
    ("openrouter", "anthropic/claude-sonnet-5"),    # 2,00 /10,00 — dieselbe, eine Klasse hoeher
    # Ausgeschieden, mit Messwert, damit es niemand „mal wieder probiert":
    #   sambanova/DeepSeek-V3.2   180 s Timeout
    #   sambanova/DeepSeek-V3.1    78 s fuer eine triviale Frage
    #   xai/grok-3-mini             8,7 s, keine bessere Ausbeute
    #   xai/grok-4.5               40,7 s bei 9,0 Punkten — langsam UND schwaecher
    #   together/Qwen2.5-72B       HTTP 400 „non-serverless mode" (eigener Endpunkt noetig)
]


def lade_analyse_modul():
    spec = importlib.util.spec_from_file_location("ad", ROOT / "scripts/analyze_docs.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4, help="Vorgaenge je Modell")
    a = ap.parse_args()

    ad = lade_analyse_modul()
    import duckdb

    con = duckdb.connect()
    # Bewusst Vorgaenge MIT vorhandener Gemini-Analyse: so steht der bisherige Bestand als
    # Vergleichsmass daneben, statt dass jedes Modell an einer anderen Aufgabe gemessen wird.
    bestand = json.loads((ROOT / "web/data/doc-analysis.json").read_text(encoding="utf-8"))
    referenz = [k for k, v in bestand.items() if not v.get("provider")][: a.n]
    if not referenz:
        print("  Kein Gemini-Bestand als Vergleich vorhanden.", file=sys.stderr)
        return 1

    src = (ROOT / "data/docs/DE/doc_text.parquet").as_posix()
    texte: dict[str, list] = {}
    for nid in referenz:
        rows = con.execute(
            f"""SELECT file, text FROM read_parquet('{src}')
                WHERE notice_id = ? AND {SQL_BRAUCHBAR} AND length(text) > 120""",
            [nid]).fetchall()
        if rows:
            texte[nid] = rows

    print(f"\n  {len(texte)} Vorgaenge je Modell\n")
    print(f"  {'Anbieter/Modell':<46} {'Punkte':>7} {'verworfen':>10} {'Sek/Vorgang':>12}   je Vorgang")
    print("  " + "─" * 78)

    # Referenz zuerst: der Bestand, gegen den verglichen wird.
    # NUR Modell-Eintraege zaehlen: alles mit `parser` (gaeb/xlsx/pdf_fields) stammt aus
    # einem deterministischen Leser und darf keinem Modell gutgeschrieben werden. Die erste
    # Fassung zaehlte sie mit — bei 15 % Parser-Anteil verschiebt das jede Rangfolge.
    def _modellpunkte(res):
        return sum(1 for e in (res.get("checklist") or [])
                   if not e.get("parser") and e.get("marking") == "Zitat")

    ref_pkt = sum(_modellpunkte(bestand[n]) for n in texte) / max(len(texte), 1)
    ref_vw = sum(bestand[n].get("rejected_items", 0) for n in texte) / max(len(texte), 1)
    print(f"  {'(Bestand) google/gemini-2.5-flash':<46} {ref_pkt:7.1f} "
          f"{ref_vw / max(ref_pkt + ref_vw, 1):9.0%} {'—':>12}")

    echt = llm._anbieter
    for anbieter, modell in KANDIDATEN:
        eintrag = next((x for x in echt() if x["name"] == anbieter), None)
        if not eintrag or not eintrag["keys"]:
            print(f"  {anbieter + '/' + modell:<46} {'kein Schluessel':>30}")
            continue
        # Kein Monkeypatch mehr (s. llm.chat): hier laeuft zwar nur ein Faden, aber ein
        # Muster, das an einer Stelle bricht, gehoert auch an der anderen weg.
        ad.MODEL = modell
        punkte = verworfen = 0
        je_vorgang = []
        t0 = time.time()
        gemacht = 0
        for nid, rows in texte.items():
            try:
                res = ad.analyze_notice(rows, structured=ad.structured_for_notice(nid))
            except Exception as ex:                        # noqa: BLE001
                print(f"  {anbieter + '/' + modell:<46} ✖ {type(ex).__name__}: {str(ex)[:28]}")
                gemacht = 0
                break
            _p = _modellpunkte(res)
            je_vorgang.append(_p)
            punkte += _p
            verworfen += res.get("rejected_items", 0)
            gemacht += 1
        if gemacht:
            quote = verworfen / max(punkte + verworfen, 1)
            print(f"  {anbieter + '/' + modell:<46} {punkte / gemacht:7.1f} {quote:9.0%} "
                  f"{(time.time() - t0) / gemacht:12.1f}   "
                  + " ".join(str(x) for x in je_vorgang))
    llm._anbieter = echt
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
