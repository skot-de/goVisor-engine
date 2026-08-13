"""Prüfstein für den Flat-Leser: dieselbe Ausschreibung in beiden GAEB-Formaten.

**Warum es diesen Prüfstein gibt.** Ein Parser für ein Format mit festen Spaltenbreiten
scheitert nicht laut. Er verrutscht um zwei Stellen und liefert ab da plausible falsche
Mengen — 600 statt 0,6, und niemand merkt es, bis jemand danach kalkuliert. Beim Preisblatt
konnte ich das nur stichprobenhaft prüfen; hier geht es besser.

**Die Gelegenheit.** 174 Vorgänge liefern ihr Leistungsverzeichnis in BEIDEN Formaten mit —
als X8x (vom bewährten XML-Leser geparst) und zusätzlich als D8x. Damit lässt sich der neue
Leser gegen den alten rechnen, an echten Daten statt an Testfixtures. (Nach Dateiendung wären
es 248; in 74 davon ist die Flat-Datei leer, unvollständig oder kein DA-90-Kopf.)

**Ergebnis des ersten vollen Laufs (2026-08-13):** 99,3 % der Paare (Menge, Einheit) stimmen
überein, bei den Mengen allein 99,7 %, Median je Vorgang 100 %. Die beiden Vorgänge unter
50 % sind erklärt und KEIN Parser-Fehler: einmal enthalten die zwei Dateien verschiedene Lose
(28 gegen 92 Positionen), einmal kürzt das D8x-Format die Einheit auf vier Zeichen („Stüc"),
während die XML-Fassung sie ausschreibt („Stück") — die Mengen stimmen dort exakt.

**Verglichen wird das Mengengerüst, nicht die Reihenfolge.** Die beiden Formate ordnen
Positionen unterschiedlich und stellen die Ordnungszahl anders dar; ein Vergleich Zeile für
Zeile würde Unterschiede melden, die keine sind. Aussagekräftig ist die **Multimenge der
Paare (Menge, Einheit)**: enthält das Flat-LV dieselben Mengen in denselben Einheiten wie
das XML-LV? Wenn der Parser um Stellen verrutscht, bricht genau das zusammen.

Ein Rest an Abweichung ist normal und kein Fehler: die beiden Dateien eines Vorgangs sind
nicht immer derselbe Leistungsstand (Nachträge, andere Lose).

Aufruf: python3 scripts/validate_gaeb_flat.py [--country DE] [--zeige 8]
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import docparse  # noqa: E402

FLAT = {".d81", ".d83", ".p83"}
XML = {".x81", ".x83", ".x86"}
_MAX = 60 * 1024 * 1024


def _mengen(positionen) -> Counter:
    """Multimenge (Menge, Einheit) — Positionen ohne beides tragen nichts zum Vergleich bei.

    ZAHL, nicht Zeichenkette. Der erste Anlauf verglich die Rohtexte und meldete 0,1 %
    Übereinstimmung — dabei stand dort ``'1.000'`` gegen ``'1'``, also derselbe Wert in
    zwei Schreibweisen. Der Prüfstein hätte damit einen Parser-Fehler gemeldet, den es
    nicht gab; auffällig war nur, dass die Positionszahlen exakt übereinstimmten.
    Ein Prüfstein, der die eigene Formatierung misst, prüft nichts.
    """
    c: Counter = Counter()
    for p in positionen:
        roh, u = (p.get("qty") or "").strip(), (p.get("unit") or "").strip().lower()
        if not roh or not u:
            continue
        try:
            menge = float(roh.replace(",", "."))
        except ValueError:
            continue
        c[(round(menge, 3), u)] += 1
    return c


def sammle(country: str):
    root = ROOT / "data" / "docs" / country
    for v in sorted(p for p in root.iterdir() if p.is_dir()):
        xml_pos, flat_pos = [], []
        for z in v.glob("*.zip"):
            try:
                zf = zipfile.ZipFile(z)
            except Exception:
                continue
            with zf:
                for i in zf.infolist():
                    e = Path(i.filename).suffix.lower()
                    if e not in XML | FLAT or i.file_size > _MAX:
                        continue
                    try:
                        d = zf.read(i)
                    except Exception:
                        continue
                    r = docparse.parse_gaeb(d)
                    if not r:
                        continue
                    (flat_pos if r["parser"] == "gaeb-flat" else xml_pos).extend(r["positions"])
        if xml_pos and flat_pos:
            yield v.name, xml_pos, flat_pos


def main(country: str, zeige: int) -> int:
    gesamt = uebereinstimmung = nur_menge = 0
    quoten: list[tuple[float, str, int, int]] = []
    for nid, xp, fp in sammle(country):
        x, f = _mengen(xp), _mengen(fp)
        if not x or not f:
            continue
        gemeinsam = sum((x & f).values())
        quote = gemeinsam / max(sum(f.values()), 1)
        quoten.append((quote, nid, len(fp), len(xp)))
        gesamt += sum(f.values())
        uebereinstimmung += gemeinsam
        # Zweite Kennzahl: Mengen ohne Einheit. Trennt echte Zahlenfehler (Spaltenversatz)
        # von blossen Schreibweise-Unterschieden bei der Einheit.
        xm = Counter(k[0] for k in x.elements()); fm = Counter(k[0] for k in f.elements())
        nur_menge += sum((xm & fm).values())

    if not quoten:
        print("Keine Vorgänge mit beiden Formaten gefunden.")
        return 1
    quoten.sort()
    n = len(quoten)
    median = quoten[n // 2][0]
    perfekt = sum(1 for q, *_ in quoten if q >= 0.99)
    schlecht = [q for q in quoten if q[0] < 0.5]

    print(f"Prüfstein GAEB-Flat gegen GAEB-XML — {n} Vorgänge mit beiden Formaten\n")
    print(f"  Mengen-Paare im Flat-LV insgesamt:      {gesamt:,}")
    print(f"  davon auch im XML-LV vorhanden:         {uebereinstimmung:,} "
          f"({100 * uebereinstimmung / gesamt:.1f} %)")
    print(f"  Median-Übereinstimmung je Vorgang:      {median:.1%}")
    print(f"  Vorgänge mit ≥99 % Übereinstimmung:     {perfekt} von {n}")
    print(f"  Vorgänge unter 50 %:                    {len(schlecht)}")
    print(f"\n  Nur die MENGEN, ohne Einheit:           {100 * nur_menge / gesamt:.1f} %")
    print("  Das ist die Zahl, auf die es ankommt. Verrutschte Spalten erzeugen "
          "Faktor-1000-Fehler;\n  eine abweichende Einheiten-SCHREIBWEISE ist dagegen "
          "harmlos — das D8x-Format kürzt\n  die Einheit auf vier Zeichen („Stüc\"), "
          "die XML-Fassung schreibt sie aus („Stück\").")

    if schlecht:
        print(f"\n  Die schwächsten {min(zeige, len(schlecht))} — hier lohnt der Blick "
              f"(unterschiedlicher Leistungsstand ODER Parser-Fehler):")
        for q, nid, nf, nx in quoten[:zeige]:
            print(f"     {q:6.1%}  {nid:<14} flat {nf:>5} Pos. / xml {nx:>5} Pos.")

    print("\nVerglichen wird die Multimenge (Menge, Einheit) als ZAHL, nicht die Reihenfolge —"
          "\ndie Formate ordnen anders und stellen die Ordnungszahl anders dar.")
    return 0 if median >= 0.9 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="DE")
    ap.add_argument("--zeige", type=int, default=8)
    a = ap.parse_args()
    sys.exit(main(a.country, a.zeige))
