#!/usr/bin/env python3
"""Welches Modell analysiert Vergabeunterlagen am besten — je Euro? Gemessen, nicht geglaubt.

**Warum es das gibt.** Seit dem 2026-08-18 hing die Modellwahl am Guthaben statt an der
Güte. Sven: „mach es so das die qualitaet bei der analyse hoch bleibt." Dafür muss man
wissen, wer wie gut ist — und seit dem 2026-08-23 auch: zu welchem Preis.

**Wie gemessen wird: gepaart.** Jedes Modell bekommt **dieselben** Vorgänge. Das ist der
ganze Trick. Vergaben unterscheiden sich um ein Vielfaches dessen, was Modelle sich
unterscheiden; wer zwei Modelle an verschiedenen Vergaben misst, misst die Vergaben. Genau
dieser Fehler steckt im Produktivbestand (`scripts/llm_qualitaet.py` sagt es selbst: die
Zuteilung war nicht zufällig), und deshalb gibt es diesen Lauf daneben.

**Vier Zahlen:**

* **Punkte** — verifizierte Checklisten-Einträge. Der Ertrag.
* **Verwerfungsquote** — Anteil der Aussagen, die die Zitatprüfung wegwarf, weil das Zitat
  nicht wörtlich im Dokument stand. Die ehrlichste der vier: sie misst nicht Fleiß, sondern
  Genauigkeit. Viele Punkte bei hoher Verwerfung heißt viel behauptet, wenig belegt.
* **USD je belegtem Punkt** — erst diese Zahl macht „effizient" messbar. Ein Modell, das
  20 % mehr findet und dreimal so viel kostet, ist keine Verbesserung.
* **Vorzeichentest** — gewinnt der Kandidat den Vergleich Vorgang für Vorgang, oder
  schwankt es nur? Bei vier Vorgängen ist jeder Unterschied Rauschen; das stand in der
  ersten Fassung nicht dabei und lud zu genau der falschen Schlussfolgerung ein.

⚠ **Der Titelverteidiger läuft MIT.** Die erste Fassung verglich Kandidaten gegen den
gespeicherten Bestand. Das mischt zwei Ursachen: seither haben sich Doktyp-Erkennung,
Prompts und Dublettenlogik geändert. Ein Kandidat hätte gewinnen können, weil die *Pipeline*
besser wurde. Heute läuft das amtierende Modell frisch mit, unter identischen Bedingungen;
der gespeicherte Bestand steht nur noch als Plausibilitätsanker daneben.

⚠ **Inkrementell gesichert, nach JEDEM Vorgang.** Am 2026-08-23 gingen 1,27 $ verloren,
weil ein Lauf seine Ergebnisse erst am Ende schreiben wollte und vorher starb. Zweimal am
selben Tag. Der Zwischenstand liegt in ``data/analyse/modellvergleich.json``; ``--fortsetzen``
nimmt ihn auf und überspringt, was schon gemessen ist.

Aufruf::

    scripts/llm_bench.py --n 12 --budget-usd 2.00
    scripts/llm_bench.py --modelle openai/gpt-5-mini --n 20 --fortsetzen
    scripts/llm_bench.py --bericht            # nur auswerten, nichts ausgeben
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import kostenbuch, llm, pruefstand  # noqa: E402
from govisor.docpipe import SQL_BRAUCHBAR  # noqa: E402

STAND = ROOT / "data" / "analyse" / "modellvergleich.json"
ZWECK = "bench"

# Der Titelverteidiger. Er steht zuerst und laeuft immer mit — gegen ihn wird verglichen.
AMTIEREND = "google/gemini-2.5-flash"

# Kandidaten: je Anbieter das staerkste Modell, das schnell genug antwortet. Was zu langsam
# war, steht mit Messwert dabei — damit niemand es „mal wieder probiert".
KANDIDATEN = [
    # OpenRouter-Auswahl, 2026-08-21. Preise je Mio Token (Eingabe/Ausgabe) aus dem
    # Katalog; sie sind Listenpreise. Was wirklich abgerechnet wurde, steht im Kostenbuch —
    # seit dem Anbieterboden (`:floor`) liegt es bei Gemini rund halb so hoch.
    "google/gemini-3.6-flash",      # 0,75 / 3,75 — neuere Generation
    "openai/gpt-5-mini",            # 0,25 / 2,00 — guenstigste Alternative
    "anthropic/claude-haiku-4.5",   # 1,00 / 5,00 — Woertlichkeits-Hypothese
    "anthropic/claude-sonnet-5",    # 2,00 /10,00 — dieselbe, eine Klasse hoeher
    # Ausgeschieden, mit Messwert, damit es niemand „mal wieder probiert":
    #   sambanova/DeepSeek-V3.2   180 s Timeout
    #   sambanova/DeepSeek-V3.1    78 s fuer eine triviale Frage
    #   xai/grok-3-mini             8,7 s, keine bessere Ausbeute
    #   xai/grok-4.5               40,7 s bei 9,0 Punkten — langsam UND schwaecher
    #   together/Qwen2.5-72B       HTTP 400 „non-serverless mode" (eigener Endpunkt noetig)
]


# ── Statistik ────────────────────────────────────────────────────────────────────────

def vorzeichentest(gewinne: int, verluste: int) -> float:
    """Zweiseitiger Vorzeichentest. Unentschiedene zaehlen nicht mit (uebliche Konvention).

    Gibt die Wahrscheinlichkeit, ein mindestens so schiefes Ergebnis zu sehen, wenn beide
    Modelle gleich gut waeren. Klein heisst: der Unterschied ist wohl echt.
    """
    n = gewinne + verluste
    if n == 0:
        return 1.0
    k = min(gewinne, verluste)
    p = 2 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(p, 1.0)


# ── Zwischenstand ────────────────────────────────────────────────────────────────────

def lade_stand() -> dict:
    if STAND.exists():
        try:
            return json.loads(STAND.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  ⚠ {STAND} unlesbar — es wird neu begonnen.", file=sys.stderr)
    return {"vorgaenge": [], "ergebnis": {}}


def sichere(stand: dict) -> None:
    STAND.parent.mkdir(parents=True, exist_ok=True)
    tmp = STAND.with_suffix(".json.teil")
    tmp.write_text(json.dumps(stand, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STAND)


# ── Messung ──────────────────────────────────────────────────────────────────────────

def lade_analyse_modul():
    spec = importlib.util.spec_from_file_location("ad", ROOT / "scripts/analyze_docs.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def modellpunkte(res: dict) -> int:
    """NUR Modell-Eintraege. Alles mit `parser` (gaeb/xlsx/pdf_fields) stammt aus einem
    deterministischen Leser und darf keinem Modell gutgeschrieben werden — bei 15 %
    Parser-Anteil verschiebt das jede Rangfolge."""
    return sum(1 for e in (res.get("checklist") or [])
               if not e.get("parser") and e.get("marking") == "Zitat")


def messe(ad, modell: str, vorgaenge: dict, stand: dict, budget: float | None) -> str | None:
    """Ein Modell durch alle Vorgaenge. Gibt einen Abbruchgrund zurueck, sonst None.

    Die eigentliche Schleife steht in `govisor.pruefstand.messe_reihe` — EINE bezahlte
    Schleife fuer Handbetrieb und Automatik, s. dort.
    """
    # Was die ANDEREN Modelle schon gekostet haben; die eigenen Vorkosten zaehlt
    # `messe_reihe` selbst dazu.
    ausgegeben = sum(v.get("kosten_usd") or 0
                     for mm, je in stand["ergebnis"].items() if mm != modell
                     for v in je.values())
    rest = None if budget is None else max(budget - ausgegeben, 0)
    ergebnisse, grund = pruefstand.messe_reihe(
        analyse=ad, llm=llm, kostenbuch=kostenbuch, modell=modell, vorgaenge=vorgaenge,
        zweck=ZWECK, vorhanden=stand["ergebnis"].get(modell),
        budget=rest,
        nach_vorgang=lambda e: (stand["ergebnis"].__setitem__(modell, e), sichere(stand)),
        ausgeben=lambda z: print(z, flush=True))
    stand["ergebnis"][modell] = ergebnisse
    sichere(stand)
    return grund


# ── Bericht ──────────────────────────────────────────────────────────────────────────

def bericht(stand: dict) -> None:
    erg = stand["ergebnis"]
    if not erg:
        print("  Noch nichts gemessen.", file=sys.stderr)
        return
    basis = erg.get(AMTIEREND, {})
    print(f"\n  {'Modell':<32} {'Vorg':>5} {'Punkte':>7} {'verw.':>6} {'USD/Vorg':>9} "
          f"{'USD/Punkt':>10} {'Sek':>6}  gegen {AMTIEREND.split('/')[-1]}")
    print("  " + "─" * 116)
    for modell, je in sorted(erg.items(), key=lambda x: x[0] != AMTIEREND):
        gut = {k: v for k, v in je.items() if "punkte" in v}
        if not gut:
            print(f"  {modell:<32} {'— nur Fehler —':>40}")
            continue
        n = len(gut)
        pkt = sum(v["punkte"] for v in gut.values()) / n
        vw = sum(v["verworfen"] for v in gut.values())
        quote = vw / max(sum(v["punkte"] for v in gut.values()) + vw, 1)
        usd = sum(v["kosten_usd"] or 0 for v in gut.values())
        sek = sum(v["sekunden"] for v in gut.values()) / n
        je_punkt = usd / max(sum(v["punkte"] for v in gut.values()), 1)
        # Gepaart: nur Vorgaenge, die BEIDE gemessen haben.
        paare = [(v["punkte"], basis[k]["punkte"]) for k, v in gut.items()
                 if k in basis and "punkte" in basis[k]]
        if modell == AMTIEREND or not paare:
            urteil = "—"
        else:
            g = sum(1 for a, b in paare if a > b)
            v_ = sum(1 for a, b in paare if a < b)
            p = vorzeichentest(g, v_)
            zeichen = "✓" if p < 0.05 else "·"
            urteil = f"{g}:{v_} von {len(paare)}  p={p:.3f} {zeichen}"
        print(f"  {modell:<32} {n:>5} {pkt:>7.1f} {quote:>5.0%} {usd / n:>9.4f} "
              f"{je_punkt:>10.5f} {sek:>6.1f}  {urteil}")
    print("  " + "─" * 116)
    fehlt = sum(v.get("ohne_preis") or 0 for je in erg.values() for v in je.values())
    if fehlt:
        wort = "Aufruf" if fehlt == 1 else "Aufrufe"
        print(f"  ⚠ {fehlt} {wort} ohne mitgelieferten Preis — die USD-Spalten sind zu niedrig.")
    print("  ✓ = Unterschied auf 5 %-Niveau abgesichert (Vorzeichentest, gepaart).")
    print("  · = kann Rauschen sein. Bei weniger als ~10 Vorgängen ist fast alles Rauschen.\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4, help="Vorgaenge je Modell")
    ap.add_argument("--modelle", help="komma-getrennt; Vorgabe: der eingebaute Katalog")
    ap.add_argument("--budget-usd", type=float, default=None, help="harte Obergrenze")
    ap.add_argument("--fortsetzen", action="store_true", help="Zwischenstand aufnehmen")
    ap.add_argument("--bericht", action="store_true", help="nur auswerten, nichts ausgeben")
    a = ap.parse_args()

    stand = lade_stand() if (a.fortsetzen or a.bericht) else {"vorgaenge": [], "ergebnis": {}}
    if a.bericht:
        bericht(stand)
        return 0

    import duckdb
    con = duckdb.connect()
    bestand = json.loads((ROOT / "web/data/doc-analysis.json").read_text(encoding="utf-8"))
    # Vorgaenge mit vorhandener Analyse: so steht der gespeicherte Bestand als Anker daneben.
    kandidaten_ids = stand["vorgaenge"] or [k for k in bestand][: a.n]
    # Vorgabe DE: AT und CH haben 0 % Dokumentabdeckung, s. docs/laender/03.
    land = __import__("os").environ.get("GOVISOR_PRUEFLAND", "DE")
    src = (ROOT / f"data/docs/{land}/doc_text.parquet").as_posix()
    vorgaenge: dict[str, list] = {}
    for nid in kandidaten_ids[: a.n]:
        rows = con.execute(
            f"""SELECT file, text FROM read_parquet('{src}')
                WHERE notice_id = ? AND {SQL_BRAUCHBAR} AND length(text) > 120""",
            [nid]).fetchall()
        if rows:
            vorgaenge[nid] = rows
    if not vorgaenge:
        print("  Keine Vorgaenge mit brauchbarem Text gefunden.", file=sys.stderr)
        return 1
    stand["vorgaenge"] = list(vorgaenge)

    modelle = [AMTIEREND] + (
        [m.strip() for m in a.modelle.split(",") if m.strip()] if a.modelle else KANDIDATEN)
    modelle = list(dict.fromkeys(modelle))             # Reihenfolge halten, Dubletten weg

    print(f"\n  {len(vorgaenge)} Vorgänge × {len(modelle)} Modelle"
          + (f" · Budget {a.budget_usd:.2f} $" if a.budget_usd else "")
          + f" · Zwischenstand {STAND.relative_to(ROOT)}\n")
    ad = lade_analyse_modul()
    for modell in modelle:
        print(f"  {modell}")
        grund = messe(ad, modell, vorgaenge, stand, a.budget_usd)
        if grund:
            print(f"\n  ⏹ Abgebrochen: {grund}. Gemessenes ist gesichert; "
                  f"weiter mit --fortsetzen.\n", file=sys.stderr)
            break
    bericht(stand)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
