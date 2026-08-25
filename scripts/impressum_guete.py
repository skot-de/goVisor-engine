#!/usr/bin/env python3
"""Wie zuverlässig ist der Impressum-Prüfer? — an echten Paaren gemessen.

**Warum das Prüfmaterial neu gebaut wird.** Die erste Messung (25 Firmen) benutzte
Mailadressen aus `notice_parties`. Die sind aber selbst verunreinigt: 7,5 % der
Gewinner-Mails sind in Wahrheit die Portaladresse des Auftraggebers. Wer damit die
Güte misst, misst die Verunreinigung mit und weiss hinterher nicht, welche der beiden
Zahlen er in der Hand hat.

Hier ist die Grundwahrheit deshalb die **selbst angegebene Website** (`notice_parties.url`,
13.561 distinkte Firma/Domain-Paare). Die trägt eine Firma für sich selbst ein.

**Zwei Fragen, nicht eine.** Beide zählen, und die zweite mehr:

1. *Empfindlichkeit* — bestätigt er echte Paare? Was er verpasst, kostet Bequemlichkeit:
   der Kunde geht den kalten Weg.
2. *Trennschärfe* — bestätigt er jemals ein falsches Paar? Das kostet Sicherheit, denn
   genau darauf stützt sich die Freischaltung eines fremden Firmenprofils.

Die Gegenprobe entsteht durch Verwürfeln: Firma A bekommt die Domain von Firma B. Jedes
``belegt`` darin ist ein Fehlurteil, und zwar das teure.

Aufruf::

    scripts/impressum_guete.py --n 150
    scripts/impressum_guete.py --n 300 --gleichzeitig 8
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import impressum as I  # noqa: E402

SRC = f"'{ROOT}/data/silver/DE/notice_parties/**/*.parquet'"


def paare(n: int, seed: int) -> list[tuple[str, str]]:
    """(Firmenname, selbst angegebene Domain) — die Grundwahrheit."""
    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT name,
               lower(regexp_extract(url, '^(?:https?://)?(?:www\\.)?([^/:?]+)', 1)) AS dom,
               count(*) AS n
        FROM {SRC}
        WHERE (role ILIKE '%win%' OR role ILIKE '%contract%')
          AND url IS NOT NULL AND url <> '' AND name IS NOT NULL AND length(name) >= 6
        GROUP BY 1, 2
        HAVING dom LIKE '%.%' AND dom NOT LIKE '%@%'
    """).fetchall()
    # Eine Firma kann mehrere Domains angegeben haben (Umzug, Konzern). Fuer die
    # Grundwahrheit zaehlt die haeufigste — sonst prueften wir gegen eine tote Altdomain
    # und schrieben das Ergebnis dem Pruefer an.
    beste: dict[str, tuple[str, int]] = {}
    for name, dom, k in rows:
        if name not in beste or k > beste[name][1]:
            beste[name] = (dom, k)
    alle = sorted((nm, d) for nm, (d, _) in beste.items())
    random.Random(seed).shuffle(alle)
    return alle[:n]


def lauf(fall: tuple[str, str, str]) -> dict:
    art, firma, dom = fall
    b = I.pruefe(dom, firma)
    return {"art": art, "firma": firma, "domain": dom,
            "urteil": b.urteil, "quote": b.quote, "sek": b.sekunden}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, default=150, help="Paare je Gruppe")
    ap.add_argument("--gleichzeitig", type=int, default=6)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--raus", default="data/logs/impressum-guete.json")
    a = ap.parse_args(argv)

    echt = paare(a.n, a.seed)
    if len(echt) < 10:
        print("zu wenig Grundwahrheit gefunden", file=sys.stderr)
        return 1

    # Gegenprobe: Domains um eine Position rotieren. Rotation statt Zufall, weil sie
    # garantiert, dass KEINE Firma ihre eigene Domain zurueckbekommt — beim Ziehen mit
    # Zufall passiert genau das gelegentlich und faelscht die Trennschaerfe nach unten.
    falsch = [(echt[i][0], echt[(i + 1) % len(echt)][1]) for i in range(len(echt))]

    faelle = ([("echt", f, d) for f, d in echt] + [("falsch", f, d) for f, d in falsch])
    print(f"  {len(echt)} echte Paare + {len(falsch)} verwürfelte, "
          f"{a.gleichzeitig} gleichzeitig\n")

    erg = []
    with ThreadPoolExecutor(max_workers=a.gleichzeitig) as ex:
        for i, r in enumerate(ex.map(lauf, faelle), 1):
            erg.append(r)
            if i % 25 == 0:
                print(f"    {i}/{len(faelle)} …", flush=True)

    Path(a.raus).parent.mkdir(parents=True, exist_ok=True)
    Path(a.raus).write_text(json.dumps(erg, ensure_ascii=False, indent=1))

    for art, titel in (("echt", "ECHTE Paare (Firma + ihre eigene Website)"),
                       ("falsch", "VERWÜRFELTE Paare (fremde Domain)")):
        g = [r for r in erg if r["art"] == art]
        z = Counter(r["urteil"] for r in g)
        print(f"\n  ── {titel}   n={len(g)}")
        for u in (I.BELEGT, I.WIDERLEGT, I.NICHT_PRUEFBAR):
            k = z.get(u, 0)
            marke = ""
            if art == "echt" and u == I.WIDERLEGT:
                marke = "  ← Fehlurteil: sperrt einen echten Kunden aus"
            if art == "falsch" and u == I.BELEGT:
                marke = "  ← Fehlurteil: lässt einen Fremden auf ein Profil"
            print(f"     {u:<15} {k:>4}  {k/len(g):>6.1%}{marke}")

    sek = sorted(r["sek"] for r in erg)
    print(f"\n  Zeit   Median {sek[len(sek)//2]:.2f}s · "
          f"p90 {sek[int(len(sek)*0.9)]:.2f}s · max {sek[-1]:.2f}s")

    e = [r for r in erg if r["art"] == "echt"]
    f = [r for r in erg if r["art"] == "falsch"]
    fp = sum(1 for r in f if r["urteil"] == I.BELEGT)
    fn = sum(1 for r in e if r["urteil"] == I.WIDERLEGT)
    print(f"\n  Falsch bestätigt (gefährlich):     {fp}/{len(f)} = {fp/len(f):.2%}")
    print(f"  Falsch widerlegt (ärgerlich):      {fn}/{len(e)} = {fn/len(e):.2%}")
    print(f"  Bestätigungsquote echter Paare:    "
          f"{sum(1 for r in e if r['urteil']==I.BELEGT)/len(e):.1%}")
    print(f"\n  Rohdaten: {a.raus}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
