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
import os
import sys
from datetime import datetime, timezone
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


MARKE = ROOT / "data" / ".llm_abgleich.json"


def _gesamtverbrauch() -> float | None:
    """OpenRouters kumulierter Verbrauch (`total_usage`). Steigt nur, nie zurück."""
    import json as _json
    import subprocess
    schluessel = os.environ.get("OPENROUTER_API_KEY")
    if not schluessel:
        pfad = ROOT / ".secrets" / "openrouter.key"
        if not pfad.exists():
            return None
        schluessel = pfad.read_text(encoding="utf-8").strip()
    try:
        roh = subprocess.run(
            ["curl", "-s", "--max-time", "20", "-H", f"Authorization: Bearer {schluessel}",
             "https://openrouter.ai/api/v1/credits"],
            capture_output=True, text=True, timeout=30).stdout
        return float(_json.loads(roh)["data"]["total_usage"])
    except Exception:                                    # noqa: BLE001
        return None


def abgleich(marke_neu: bool = False) -> int:
    """Buch gegen OpenRouters eigene Abrechnung. Die Lücke ist eine Messgröße, kein Fehler.

    **Warum `total_usage` und nicht der Kontostand.** Die erste Fassung verglich den
    Kontostand vom Tagesbeginn mit dem jetzigen. Das funktioniert genau so lange, bis
    jemand **auflädt** — dann steigt der Stand, die Differenz wird negativ und der Abgleich
    meldet Unsinn. `total_usage` ist der kumulierte Verbrauch: er steigt nur, und eine
    Aufladung rührt ihn nicht an.

    **Warum das Buch nie vollständig sein kann.** Gebucht wird, was in einer Antwort steht.
    Zwei Wege bleiben daran vorbei:

    * **Client-Timeout** — oben verarbeitet und abgerechnet, wir haben die Antwort nie
      gesehen. Prinzipiell nicht buchbar.
    * **Alles, was `govisor.llm.chat()` umgeht** — `scripts/succession_llm.py` postet
      direkt mit `requests`, ohne Geldwache und ohne Buch.

    Ein Buch, das seine eigene Lücke ausweist, ist ehrlicher als eines, das Vollständigkeit
    vortäuscht. Und die Lücke ist selbst ein Signal: wächst sie, geht an einer Stelle Geld
    weg, die wir nicht sehen.
    """
    import json as _json
    jetzt = _gesamtverbrauch()
    if jetzt is None:
        print("  Gesamtverbrauch nicht abrufbar (Schlüssel? Netz?).", file=sys.stderr)
        return 1
    buch_jetzt = sum(float(z["kosten_usd"]) for z in kostenbuch.lies()
                     if z.get("kosten_usd") is not None)

    if marke_neu or not MARKE.exists():
        MARKE.parent.mkdir(parents=True, exist_ok=True)
        MARKE.write_text(_json.dumps(
            {"gesetzt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "total_usage": jetzt, "buch": buch_jetzt}, indent=1), encoding="utf-8")
        print(f"\n  Marke gesetzt: OpenRouter-Gesamtverbrauch {jetzt:.5f} $, "
              f"Buch {buch_jetzt:.5f} $.")
        print(f"  Ab jetzt wird die Differenz beider Zuwächse gemessen.\n")
        return 0

    m = _json.loads(MARKE.read_text(encoding="utf-8"))
    d_konto = jetzt - float(m["total_usage"])
    d_buch = buch_jetzt - float(m["buch"])
    luecke = d_konto - d_buch
    anteil = luecke / d_konto if d_konto > 0 else 0.0

    print(f"\n  Abgleich seit {m['gesetzt']}\n")
    print(f"    OpenRouter abgerechnet {d_konto:>10.5f} $")
    print(f"    Kostenbuch gebucht     {d_buch:>10.5f} $")
    print(f"    → ungebucht            {luecke:>10.5f} $   ({anteil:.0%})")

    zeilen = list(kostenbuch.lies())
    leer = sum(1 for z in zeilen if z.get("leer"))
    ohne = sum(1 for z in zeilen if z.get("kosten_usd") is None)
    if leer:
        print(f"\n    {leer} leere Antwort(en) im Buch — bezahlt, ohne Ertrag")
    if ohne:
        print(f"    {ohne} Zeile(n) ohne mitgelieferten Preis")

    if d_konto <= 0:
        print(f"\n  Seit der Marke wurde nichts abgerechnet.")
    elif anteil > 0.10:
        print(f"\n  ⚠ Mehr als 10 % ungebucht. Verdächtig, in dieser Reihenfolge:")
        print(f"    · Client-Timeouts (oben abgerechnet, Antwort nie gesehen)")
        print(f"    · etwas umgeht govisor.llm.chat() — z. B. scripts/succession_llm.py")
        print(f"    · ein zweiter Prozess auf demselben Schlüssel")
    else:
        print(f"\n  ✓ Buch und Abrechnung stimmen im Rahmen überein.")
    print()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nach", default="modell,weg,endpunkt",
                    help=f"Gruppierung, komma-getrennt aus: {', '.join(FELDER)}")
    ap.add_argument("--seit", help="nur Zeilen ab diesem Zeitstempel (z. B. 2026-08-23)")
    ap.add_argument("--boden", action="store_true", help="Boden gegen ohne Boden")
    ap.add_argument("--abgleich", action="store_true",
                    help="Buch gegen OpenRouters Abrechnung — wie viel wurde NICHT gebucht?")
    ap.add_argument("--marke-neu", action="store_true",
                    help="Abgleichsmarke auf den heutigen Stand setzen")
    ap.add_argument("--mit-alt", action="store_true", help="umgehängte Generation mitlesen")
    a = ap.parse_args()

    if a.abgleich or a.marke_neu:
        return abgleich(marke_neu=a.marke_neu)

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
