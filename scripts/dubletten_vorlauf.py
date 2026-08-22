#!/usr/bin/env python3
"""Wiederkehrende Dokumente EINMAL auswerten, damit alle ihre Kopien es erben.

    python3 scripts/dubletten_vorlauf.py --budget-usd 1.00 [--trocken]

**Warum.** 6.324 Dokumente priorisierter Typen kommen mehrfach vor und haben noch keinen
Master — zusammen **18.321 sparbare Auswertungen**. Ohne Vorlauf wärmt sich der Wall nur
aus den 33 % der Fälle, in denen ein Doktyp aus genau einem Dokument besteht.

⚠ **Nach Nutzen je Aufwand sortiert, nicht nach Häufigkeit.** Ein 200-Zeichen-Formular, das
50-mal vorkommt, ist mehr wert als ein 60.000-Zeichen-Vertrag, der 60-mal vorkommt. Gemessen
2026-08-22 ergibt das eine sehr steile Kurve:

        N     Kosten   gespart
      100      0,04 $    26 %
      500      0,18 $    44 %
    2.000      0,99 $    68 %
    6.324     14,70 $   100 %

**1 $ bringt gut zwei Drittel.** Deshalb ein Budget statt einer Stückzahl — der Lauf nimmt,
was hineinpasst, und der Rest wartet auf den nächsten.

⚠ Der Vorlauf schreibt NICHT nach `doc-analysis.json`. Dort stehen Auswertungen von
VORGÄNGEN; ein einzeln ausgewertetes Formular gehört keinem Vorgang. Es liegt in
`gold/<L>/document_master_items.parquet`, mit der Prompt-Version als Verfallsdatum.
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor import doctypes, docextract, docpipe, dokdubletten as dd, llm  # noqa: E402

MODELL = "google/gemini-2.5-flash"
DECKEL = 60_000


def kandidaten(country: str = "DE") -> list[tuple]:
    """[(doctype, pruefsumme, text, datei, zahl_der_kopien)] — bestes Verhältnis zuerst."""
    import duckdb

    src = ROOT / "data" / "docs" / country / "doc_text.parquet"
    rows = duckdb.sql(f"""select notice_id, file, text from '{src.as_posix()}'
                          where {docpipe.SQL_BRAUCHBAR} and length(text) > 120""").fetchall()
    je = collections.defaultdict(list)
    for n, f, t in rows:
        je[n].append((f, t))
    gruppen = collections.defaultdict(list)
    for nid, dat in je.items():
        raus = docpipe.ueberholte(f for f, _ in dat)
        for f, t in dat:
            if f in raus:
                continue
            dt = doctypes.classify(f, t)
            if doctypes.is_priority(dt):
                gruppen[(dt, dd.pruefsumme(t))].append((f, t))
    haben = set(dd.karte(country)) | set(dd.master_items(country))
    aus = []
    for (dt, h), v in gruppen.items():
        if len(v) < 2 or (dt, h) in haben:
            continue
        f, t = v[0]
        aus.append((dt, h, t, f, len(v)))
    # Nutzen je Aufwand: gesparte Auswertungen pro gesendetem Zeichen.
    aus.sort(key=lambda x: -(x[4] - 1) / max(min(len(x[2]), DECKEL), 1))
    return aus


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--budget-usd", type=float, default=1.0)
    p.add_argument("--country", default="DE")
    p.add_argument("--trocken", action="store_true", help="nur zeigen, nichts auswerten")
    a = p.parse_args(argv)

    kand = kandidaten(a.country)
    print(f"{len(kand):,} wiederkehrende Dokumente ohne Master", flush=True)
    if not kand:
        return 0

    # Auswahl nach Budget. Grob gerechnet: Eingabe + Ausgabe ≈ 1,8× Eingabe.
    gewaehlt, zeichen = [], 0
    for k in kand:
        z = min(len(k[2]), DECKEL)
        if (zeichen + z) / 4 / 1e6 * 0.30 * 1.8 > a.budget_usd:
            break
        gewaehlt.append(k)
        zeichen += z
    spart = sum(k[4] - 1 for k in gewaehlt)
    print(f"  {len(gewaehlt):,} passen in {a.budget_usd:.2f} $ · sparen {spart:,} Auswertungen",
          flush=True)
    if a.trocken:
        for dt, h, t, f, n in gewaehlt[:8]:
            print(f"    {n:>4}×  {dt:<22} {len(t):>7,} Z.  {f.split('/')[-1][:44]}")
        return 0

    neu, fehler = {}, 0
    for i, (dt, h, t, f, n) in enumerate(gewaehlt, 1):
        try:
            r = docextract.extract(dt, t[:DECKEL], f, model=MODELL)
        except llm.BudgetErschoepft as e:
            print(f"  ⛔ {e}", flush=True)
            break
        except Exception as e:                                # noqa: BLE001
            fehler += 1
            continue
        items = r.get("items", [])
        if items:
            neu[(dt, h)] = [{k_: v_ for k_, v_ in it.items() if k_ != "source_file"}
                            for it in items]
        if i % 25 == 0 or i == len(gewaehlt):
            dd.schreibe_master_items(neu, a.country)          # zwischendurch sichern
            print(f"  [{i}/{len(gewaehlt)}] {len(neu):,} Master · {fehler} Fehler", flush=True)
    if neu:
        z = dd.schreibe_master_items(neu, a.country)
        print(f"→ {z}", flush=True)
    print(f"fertig: {len(neu):,} neue Master, {fehler} Fehler", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
