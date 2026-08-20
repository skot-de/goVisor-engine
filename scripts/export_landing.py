#!/usr/bin/env python3
"""Zahlen für die öffentliche Startseite → ``web/data/landing.json``.

**Warum eine eigene Datei und keine Konstanten im Seitencode.** Eine Startseite, die „über
100.000 Vergaben" behauptet, veraltet in dem Moment, in dem jemand sie tippt — und niemand
merkt es, weil eine Zahl im JSX wie eine Tatsache aussieht. Hier kommen die Zahlen aus
demselben Bestand, den die Anwendung ausliefert, und tragen ihren Stand mit.

**Bewusst wenige.** Was hier steht, muss ein Besucher in fünf Sekunden einordnen können:
wie viel, aus welchen Ländern, wie tief ausgewertet. Alles Weitere ist Produkt, nicht
Werbung.

Aufruf::  scripts/export_landing.py
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZIEL = ROOT / "web/data/landing.json"


def main() -> int:
    import duckdb

    con = duckdb.connect()
    laender: dict[str, dict] = {}
    gesamt = offen = 0
    for land in ("DE", "AT", "CH"):
        p = ROOT / "data/gold" / land / "lead_export.parquet"
        if not p.exists():
            continue
        n, o = con.execute(
            f"SELECT count(*), count(*) FILTER (WHERE phase='open') FROM '{p.as_posix()}'"
        ).fetchone()
        laender[land] = {"gesamt": n, "offen": o}
        gesamt += n
        offen += o

    # Vergabestellen und Fachgebiete nur aus DE: für AT/CH ist die Entitäten-Auflösung
    # schwächer, und eine Zahl, die zwei verschiedene Qualitäten mischt, ist keine Zahl.
    de = (ROOT / "data/gold/DE/lead_export.parquet").as_posix()
    stellen, cpv = con.execute(
        f"SELECT count(DISTINCT buyer_name), count(DISTINCT cpv_code) FROM '{de}'").fetchone()

    def zaehle(name: str) -> int:
        p = ROOT / "web/data" / name
        try:
            return len(json.loads(p.read_text(encoding="utf-8")))
        except Exception:                                      # noqa: BLE001
            return 0

    daten = {
        "stand": date.today().isoformat(),
        "vergaben": gesamt,
        "offen": offen,
        "laender": laender,
        "vergabestellen_de": stellen,
        "fachgebiete_de": cpv,
        "unterlagen_volltext": zaehle("doc-text-index.json"),
        "unterlagen_analysiert": zaehle("doc-analysis.json"),
    }
    ZIEL.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    print(f"  Startseite: {gesamt:,} Vergaben ({offen:,} offen) aus {len(laender)} Ländern "
          f"→ {ZIEL.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
