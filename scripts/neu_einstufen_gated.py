#!/usr/bin/env python3
"""Alte `gated`-Sätze nach ihrer Notiz neu einstufen.

**Warum.** `gated` war bis zum 2026-08-22 ein Sammeltopf. Gemessen an den 406 Sätzen im
cosinex-Manifest steckten darin drei verschiedene Lagen:

    257  http 200 + HTML     wirklich ein Anmeldetor  → bleibt `gated`
     54  http 404 / 410      das Dokument ist WEG     → `weg` (dauerhaft, kein Nachfassen)
     94  keine Dokumentliste unser Parser liest die Seite nicht → `kein_listenlayout`

Die Abrufer schreiben seit dem 22.08. die richtigen Klassen. Dieses Skript holt die
Vergangenheit nach — sonst warten 148 Vorgänge weiter auf einen Zugang, der ihnen nicht
hilft, und die 94 erreichbaren Seiten tauchen in keiner Arbeitsliste auf.

⚠ SCHREIBT IN `data/` — vorher `scripts/laeuft_was.sh`. Ein Abrufer, der dasselbe Manifest
gerade fortschreibt, verliert sonst seine Zeilen.

    python3 scripts/neu_einstufen_gated.py --probe     # nur zeigen
    python3 scripts/neu_einstufen_gated.py
"""
import argparse
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MANIFESTE = sorted((ROOT / "data" / "docs").glob("*/_manifest*.parquet"))


def neue_klasse(note: str) -> str | None:
    """Nur eindeutige Faelle umschreiben. Wer nicht sicher ist, laesst es."""
    n = (note or "").strip()
    if n.startswith(("http 404", "http 410")):
        return "weg"
    if n.startswith("keine Dokumentliste"):
        return "kein_listenlayout"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="nichts schreiben, nur zaehlen")
    a = ap.parse_args()

    gesamt = 0
    for p in MANIFESTE:
        try:
            zeilen = pq.read_table(p).to_pylist()
        except Exception as e:                                   # noqa: BLE001
            print(f"  ✖ {p.name}: {e}")
            continue
        if not zeilen or "status" not in zeilen[0]:
            continue
        geaendert = 0
        for z in zeilen:
            if z.get("status") != "gated":
                continue
            neu = neue_klasse(z.get("note"))
            if neu:
                z["status"] = neu
                geaendert += 1
        if not geaendert:
            continue
        gesamt += geaendert
        print(f"  {p.name:36} {geaendert:>4} neu eingestuft")
        if not a.probe:
            tmp = p.with_suffix(".part")
            pq.write_table(pa.Table.from_pylist(zeilen), tmp, compression="zstd")
            tmp.replace(p)
    print(f"  {'(Probe) ' if a.probe else ''}{gesamt:,} Saetze insgesamt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
