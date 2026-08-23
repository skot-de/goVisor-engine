#!/usr/bin/env python3
"""Was hat das LLM wirklich gekostet — je Modell, Weg, Endpunkt und Zweck.

**Warum es das gibt.** Der Kontostand sagt, dass Geld weg ist. Er sagt nicht, wofür. Diese
Auswertung liest das Kostenbuch (`govisor/kostenbuch.py`), das seit dem 2026-08-23 jeden
Aufruf mit dem von OpenRouter abgerechneten Betrag mitschreibt.

**Die eine Frage, für die es gebaut wurde:** bringt der Anbieterboden etwas? `:floor` soll
den Flex-Endpunkt treffen und damit den halben Listenpreis zahlen (0,150/1,250 statt
0,300/2,500 $/Mio bei `google/gemini-2.5-flash`). Ob er ihn trifft, sieht man nur an den
abgerechneten Beträgen — deshalb `--boden`.

⚠ **Was `--boden` NICHT ist: ein sauberer Versuch.** Verglichen werden Aufrufe, die zu
verschiedenen Zeiten an verschiedenen Vergaben liefen. Beim **Preis** je Mio Token ist das
belanglos: der Tarif hängt nicht am Dokument. Bei der **Dauer** ist es das nicht — Flex ist
die niedrigere Dienstgüte, und ob sie langsamer ist, lässt sich hier nur ahnen, solange
nicht dieselben Vorgänge über beide Wege liefen. Die Spalte steht als Hinweis da, nicht als
Beweis. Wer es genau wissen will, fährt eine Zeit lang mit `OR_BODEN=aus` gegen.

Aufruf::

    scripts/kostenbericht.py                      # je Modell/Weg/Endpunkt
    scripts/kostenbericht.py --nach zweck         # wofür ging das Geld
    scripts/kostenbericht.py --boden              # Boden gegen ohne Boden
    scripts/kostenbericht.py --seit 2026-08-23
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import kostenbuch  # noqa: E402

FELDER = ("modell", "weg", "endpunkt", "zweck", "anbieter", "vorgang")


def _zeilen(seit: str | None, mit_alt: bool):
    for z in kostenbuch.lies(mit_alt=mit_alt):
        if seit and (z.get("ts") or "") < seit:
            continue
        yield z


def _tabelle(gruppen: dict, schluessel: tuple[str, ...]) -> None:
    kopf = " / ".join(schluessel)
    breite = max([len(kopf)] + [len(" / ".join(k)) for k in gruppen] + [20])
    print(f"\n  {kopf:<{breite}} {'Aufrufe':>8} {'USD':>10} {'USD/Aufruf':>11} "
          f"{'USD/Mio Tok':>12} {'Sek/Aufruf':>11}")
    print("  " + "─" * (breite + 56))
    for k, g in sorted(gruppen.items(), key=lambda x: -x[1]["kosten_usd"]):
        name = " / ".join(x or "—" for x in k)
        print(f"  {name:<{breite}} {g['n']:>8,} {g['kosten_usd']:>10.4f} "
              f"{g['je_aufruf']:>11.5f} {g['usd_je_mio_token']:>12.4f} "
              f"{g['sekunden'] / max(g['n'], 1):>11.1f}")
    n = sum(g["n"] for g in gruppen.values())
    usd = sum(g["kosten_usd"] for g in gruppen.values())
    ohne = sum(g["ohne_kosten"] for g in gruppen.values())
    print("  " + "─" * (breite + 56))
    print(f"  {'zusammen':<{breite}} {n:>8,} {usd:>10.4f}")
    if ohne:
        # Kein stilles Weglassen: eine Zeile ohne Preis ist ein Loch in der Summe, und wer
        # das nicht sieht, haelt eine zu kleine Zahl fuer die Wahrheit.
        wort = "Aufruf" if ohne == 1 else "Aufrufe"
        fehl = "fehlt er" if ohne == 1 else "fehlen sie"
        print(f"  ⚠ {ohne:,} {wort} ohne mitgelieferten Preis — in der Summe {fehl}.")


def _boden(zeilen) -> int:
    je = kostenbuch.zusammenfassung(("modell", "weg"), zeilen)
    modelle = sorted({k[0] for k in je})
    print(f"\n  {'Modell':<34} {'Weg':>8} {'Aufrufe':>8} {'USD/Mio Tok':>12} {'Sek':>7}")
    print("  " + "─" * 74)
    gefunden = False
    for m in modelle:
        mit = je.get((m, "floor"))
        ohne = je.get((m, ""))
        for weg, g in (("floor", mit), ("(ohne)", ohne)):
            if g:
                print(f"  {m:<34} {weg:>8} {g['n']:>8,} {g['usd_je_mio_token']:>12.4f} "
                      f"{g['sekunden'] / max(g['n'], 1):>7.1f}")
        if mit and ohne and ohne["usd_je_mio_token"] > 0:
            gefunden = True
            q = mit["usd_je_mio_token"] / ohne["usd_je_mio_token"]
            print(f"  {'→ Boden zahlt':<34} {q:>8.0%} des Preises ohne Boden "
                  f"({(1 - q) * 100:.0f} % gespart)")
        print()
    if not gefunden:
        print("  Noch kein Vergleich möglich: es fehlen Aufrufe OHNE Boden.")
        print("  Eine Zeit lang mit `OR_BODEN=aus` fahren, dann erneut auswerten.\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nach", default="modell,weg,endpunkt",
                    help=f"Gruppierung, komma-getrennt aus: {', '.join(FELDER)}")
    ap.add_argument("--seit", help="nur Zeilen ab diesem Zeitstempel (z. B. 2026-08-23)")
    ap.add_argument("--boden", action="store_true", help="Boden gegen ohne Boden")
    ap.add_argument("--mit-alt", action="store_true", help="umgehängte Generation mitlesen")
    a = ap.parse_args()

    if not kostenbuch.PFAD.exists():
        print(f"  Kein Kostenbuch unter {kostenbuch.PFAD}.\n"
              f"  Es entsteht beim ersten LLM-Aufruf von selbst.", file=sys.stderr)
        return 1

    zeilen = list(_zeilen(a.seit, a.mit_alt))
    if not zeilen:
        print("  Keine Zeilen im gewählten Zeitraum.", file=sys.stderr)
        return 1
    wort = "Aufruf" if len(zeilen) == 1 else "Aufrufe"
    print(f"\n  {len(zeilen):,} {wort} · {zeilen[0]['ts']} bis {zeilen[-1]['ts']}")

    if a.boden:
        return _boden(zeilen)

    schluessel = tuple(x.strip() for x in a.nach.split(",") if x.strip())
    unbekannt = [x for x in schluessel if x not in FELDER]
    if unbekannt:
        print(f"  Unbekannte Felder: {', '.join(unbekannt)}. Erlaubt: {', '.join(FELDER)}",
              file=sys.stderr)
        return 2
    _tabelle(kostenbuch.zusammenfassung(schluessel, zeilen), schluessel)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
