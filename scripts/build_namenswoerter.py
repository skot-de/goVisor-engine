#!/usr/bin/env python3
"""Häufigkeitstabelle der Wörter in Firmennamen — Grundlage des Impressum-Prüfers.

**Wozu.** `govisor.impressum` entscheidet über das *Trägerwort*: das seltenste Wort eines
Firmennamens muss im Impressum stehen, sonst zählt der Treffer nicht. Ohne diese Tabelle
kennt der Prüfer keine Seltenheit, hält jedes Wort für gleich unterscheidend und lässt
wieder durch, was am 2026-08-17 gemessen 5,5 % Fehlbestätigungen verursachte: „BFT Planung
GmbH" passte über das Wort ``planung`` zu 100 % auf `man.eu`.

**Warum gemessen und nicht geschrieben.** Eine Stoppwortliste von Hand wäre am Tag ihrer
Entstehung veraltet, gälte nur für Deutsch und träfe die Fälle nicht: ``tech`` (172 Namen)
ist seltener als ``zublin`` (185) — welches Wort trägt, sieht man erst an den Daten. Die
Tabelle wächst automatisch mit dem Bestand und mit jedem neuen Land.

**Warum sie in den Tageslauf gehört.** Sie leitet sich aus `entities.parquet` ab und
veraltet mit ihm. Bleibt sie stehen, während der Bestand wächst, halten neue Allerweltswörter
sich für selten — der Prüfer wird schleichend nachlässiger, ohne dass etwas rot wird.

Gespeichert werden nur Wörter ab ``--ab`` Vorkommen. Alles Seltenere fehlt bewusst und gilt
damit automatisch als unterscheidend; das hält die Datei klein genug fürs Frontend-Bundle
(gemessen 7.300 Wörter, 112 KB statt 158.527 Wörter).

Aufruf::

    scripts/build_namenswoerter.py
    scripts/build_namenswoerter.py --ab 20 --pruefen
"""
from __future__ import annotations

import argparse
import collections
import json
import shutil
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor.impressum import falte  # noqa: E402

QUELLE = ROOT / "data" / "gold" / "DE" / "entities.parquet"
ZIEL = ROOT / "data" / "reference" / "namenswoerter.json"
# Zweitschrift fuers Frontend: `web/` wird als eigenes Paket deployt und kann nicht auf
# `data/` zugreifen (Symlink, ausserhalb des Repos). Beide Zwillinge brauchen aber
# dieselbe Tabelle, sonst urteilt der Deploy anders als der Stapelbetrieb.
ZIEL_WEB = ROOT / "web" / "data" / "namenswoerter.json"


def bauen(ab: int) -> dict:
    if not QUELLE.exists():
        raise SystemExit(f"fehlt: {QUELLE} — erst `gold` bauen")
    con = duckdb.connect()
    namen = [r[0] for r in con.execute(
        f"SELECT DISTINCT canonical_name FROM '{QUELLE}' "
        "WHERE canonical_name IS NOT NULL").fetchall()]
    z: collections.Counter[str] = collections.Counter()
    for n in namen:
        z.update(set(falte(n).split()) - {""})
    return {"n_namen": len(namen), "schwelle": ab,
            "zaehler": {w: k for w, k in z.items() if k >= ab}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ab", type=int, default=20, help="ab wie vielen Vorkommen speichern")
    ap.add_argument("--pruefen", action="store_true", help="nur prüfen, nichts schreiben")
    a = ap.parse_args(argv)

    tab = bauen(a.ab)
    n = len(tab["zaehler"])
    if a.pruefen:
        alt = json.loads(ZIEL.read_text(encoding="utf-8")) if ZIEL.exists() else {"zaehler": {}}
        print(f"  neu {n:,} Wörter · bisher {len(alt['zaehler']):,}")
        return 0

    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    ZIEL_WEB.parent.mkdir(parents=True, exist_ok=True)
    # Erst daneben schreiben, dann umbenennen. Ein Abbruch mitten im Schreiben hinterliesse
    # sonst eine halbe JSON-Datei, und der Pruefer faellt bei kaputter Tabelle lautlos auf
    # „alles gleich haeufig" zurueck — also genau in den Zustand mit 5,5 % Fehlbestaetigungen.
    tmp = ZIEL.with_suffix(".json.neu")
    tmp.write_text(json.dumps(tab, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    tmp.replace(ZIEL)
    shutil.copy(ZIEL, ZIEL_WEB)
    print(f"  ✓ {n:,} Wörter aus {tab['n_namen']:,} Firmennamen "
          f"({ZIEL.stat().st_size/1024:.0f} KB) → {ZIEL.name} + web/data/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
