#!/usr/bin/env python3
"""Archive zum erneuten Auslesen freigeben, wenn ein Leser dazugekommen ist.

**Das Problem, das dieses Skript loest.** `index-docs` ueberspringt jedes Archiv, das schon
im Index steht (gemessen am 2026-08-18: 4.626 von 4.879 uebersprungen). Das ist richtig, es
spart Stunden. Es heisst aber auch: ein neuer Leser wirkt NUR auf frisch heruntergeladene
Archive. Alles, was schon einmal als `unknown_type` durchlief, bleibt fuer immer
`unknown_type` — der Fortschritt kaeme nie beim Bestand an, und niemandem fiele es auf.

`--neu-aufbauen` waere die Holzhammer-Antwort: alle 4.879 Archive noch einmal, 125 GB,
Stunden. Hier werden stattdessen genau die Vorgaenge freigegeben, in denen eine Datei der
neuen Typen liegt.

**Wie die Freigabe funktioniert.** Der Index IST die Ueberspringen-Liste. Wir schreiben ihn
ohne die betroffenen Vorgaenge neu; beim naechsten `index-docs` fehlen sie und werden
geholt. Geschrieben wird daneben und dann umbenannt, damit ein Abbruch keinen halben Index
hinterlaesst.

⚠️ NICHT waehrend eines laufenden `index-docs` benutzen. `scripts/laeuft_was.sh` fragen.

Aufruf::

    scripts/reindex_typen.py --probe                    # nur zeigen, was passieren wuerde
    scripts/reindex_typen.py .doc .xls .aidf .aiform .aidoc
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("typen", nargs="*", default=[".doc", ".xls", ".aidf", ".aiform", ".aidoc"])
    ap.add_argument("--country", default="DE")
    ap.add_argument("--probe", action="store_true", help="nur rechnen, nichts schreiben")
    a = ap.parse_args()

    import duckdb

    quelle = ROOT / "data/docs" / a.country / "doc_text.parquet"
    if not quelle.exists():
        print(f"  ✖ {quelle} fehlt.", file=sys.stderr)
        return 1

    con = duckdb.connect()
    liste = ", ".join(f"'{t}'" for t in a.typen)
    q = quelle.as_posix()
    betroffen = con.execute(
        f"""SELECT count(DISTINCT notice_id) FROM read_parquet('{q}')
            WHERE filetype IN ({liste})""").fetchone()[0]
    dateien = con.execute(
        f"""SELECT count(*) FROM read_parquet('{q}') WHERE filetype IN ({liste})""").fetchone()[0]
    gesamt = con.execute(f"SELECT count(DISTINCT notice_id) FROM read_parquet('{q}')").fetchone()[0]
    print(f"  {betroffen:,} von {gesamt:,} Vorgaengen enthalten {dateien:,} Dateien der Typen "
          f"{' '.join(a.typen)}")
    if a.probe:
        print("  (Probe — nichts geschrieben)")
        return 0
    if not betroffen:
        return 0

    # Sicherung, bevor der Index angefasst wird. Er ist das Ergebnis von Stunden Rechenzeit;
    # ihn ohne Netz zu ueberschreiben waere das eine Mal zu viel.
    sicherung = quelle.with_suffix(".parquet.vor_reindex")
    shutil.copy2(quelle, sicherung)

    temp = quelle.with_suffix(".parquet.neu")
    # ⚠ `IS NOT NULL` im Subselect ist kein Zierrat. `x NOT IN (…, NULL)` ist fuer JEDES x
    # niemals wahr, die Bedingung waehlt dann NICHTS aus — und die naechste Zeile schiebt
    # das leere Ergebnis ueber den Index. Heute traegt `notice_id` 0 NULL; der Schutz soll
    # nicht davon abhaengen, dass das so bleibt.
    con.execute(f"""COPY (SELECT * FROM read_parquet('{q}')
                          WHERE notice_id NOT IN (
                            SELECT DISTINCT notice_id FROM read_parquet('{q}')
                            WHERE filetype IN ({liste}) AND notice_id IS NOT NULL))
                    TO '{temp.as_posix()}' (FORMAT PARQUET)""")

    # ⚠ ERST NACHRECHNEN, DANN ERSETZEN. Bisher wurde das Ergebnis ungesehen ueber den
    # Index geschoben, und die Erfolgsmeldung darunter rechnet `gesamt - rest`: bei einem
    # leeren Ergebnis haette dort „✓ freigegeben: 7.860 Vorgaenge" gestanden — die
    # Vernichtung des Index als Erfolg gemeldet. Der Index ist Stunden Rechenzeit; die
    # Sicherung daneben hilft nur, wenn jemand merkt, dass er sie braucht.
    #
    # Erwartet wird genau `gesamt - betroffen`. Weicht es ab, bleibt der alte Index stehen.
    neu_zahl = con.execute(
        f"SELECT count(DISTINCT notice_id) FROM read_parquet('{temp.as_posix()}')").fetchone()[0]
    if neu_zahl != gesamt - betroffen:
        temp.unlink(missing_ok=True)
        print(f"  ⛔ Ergebnis unplausibel: {neu_zahl:,} Vorgaenge statt erwarteter "
              f"{gesamt - betroffen:,}. Index NICHT ersetzt.", file=sys.stderr)
        return 1
    temp.replace(quelle)
    rest = con.execute(f"SELECT count(DISTINCT notice_id) FROM read_parquet('{q}')").fetchone()[0]
    print(f"  ✓ freigegeben: {gesamt - rest:,} Vorgaenge · Index jetzt {rest:,}")
    print(f"    Sicherung: {sicherung.relative_to(ROOT)}")
    print("    Der naechste `index-docs`-Lauf liest sie neu ein (der Arbeiter tut das von selbst).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
