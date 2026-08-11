"""`notice_text`/`lead_text`: Spalten `feld`/`wert` → `field`/`value`.

**Warum.** Alle zehn Silber-Tabellen führen englische Spaltennamen — `notice_id`,
`publication_date`, `winner_name`, `cpv_code`, und in `attributes` sogar schon
`path`/`value`. `notice_text` war die einzige Ausnahme: dort standen `feld` und `wert`
neben `language` und `notice_id`. Das war keine Konvention, sondern ein Ausrutscher beim
Anlegen der Tabelle — und er fällt genau dann auf, wenn man eine Abfrage schreibt und
raten muss, welche Sprache die Spalte gerade spricht.

Deutsch bleibt, wo es hingehört: in der Oberfläche und in den JSON-Schlüsseln der
Frontend-Exporte (`wert`, `titel`, `frist`). Die Silber-Schicht ist ein Datenvertrag und
spricht durchgehend Englisch — dieselbe Regel gilt bereits für den Supabase-Export.

Betroffen sind 691 Dateien mit 36,6 Mio. Zeilen (silver/{DE,AT,CH,EU}/notice_text) plus
die drei `gold/*/lead_text.parquet`.

Sicherungen wie in `normalize_languages.py`: `.part` + `rename` (atomar), Zeilenzahl muss
erhalten bleiben, `--dry-run` zeigt die Bilanz. Idempotent — ein zweiter Lauf findet
nichts mehr, weil er auf die Alt-Namen prüft.

Aufruf:  python scripts/rename_notice_text_columns.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
UMBENENNUNG = {"feld": "field", "wert": "value"}


def _dateien() -> list[Path]:
    aus: list[Path] = []
    for land in ("DE", "AT", "CH", "EU"):
        aus += sorted((ROOT / "data" / "silver" / land / "notice_text").glob("*/*.parquet"))
        p = ROOT / "data" / "gold" / land / "lead_text.parquet"
        if p.exists():
            aus.append(p)
    return aus


def main(dry: bool) -> int:
    con = duckdb.connect()
    dateien = _dateien()
    print(f"{len(dateien)} Dateien gefunden")
    geaendert = uebersprungen = zeilen = 0
    for f in dateien:
        q = f.as_posix()
        spalten = [d[0] for d in con.execute(
            f"SELECT * FROM read_parquet('{q}') LIMIT 0").description]
        if not (set(spalten) & set(UMBENENNUNG)):
            uebersprungen += 1
            continue                                    # schon migriert
        n0 = con.execute(f"SELECT count(*) FROM read_parquet('{q}')").fetchone()[0]
        sel = ", ".join(f'"{s}" AS "{UMBENENNUNG[s]}"' if s in UMBENENNUNG else f'"{s}"'
                        for s in spalten)
        geaendert += 1
        zeilen += n0
        if dry:
            continue
        tmp = f.with_suffix(".part")
        con.execute(f"COPY (SELECT {sel} FROM read_parquet('{q}')) "
                    f"TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        n1 = con.execute(f"SELECT count(*) FROM read_parquet('{tmp.as_posix()}')").fetchone()[0]
        if n1 != n0:
            tmp.unlink(missing_ok=True)
            raise SystemExit(f"ABBRUCH {f}: {n1} statt {n0} Zeilen")
        tmp.replace(f)
    print(f"\n{geaendert} Dateien, {zeilen:,} Zeilen"
          + (" — dry-run" if dry else " umbenannt")
          + (f"; {uebersprungen} bereits kanonisch" if uebersprungen else ""))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", dest="dry", action="store_true")
    a = ap.parse_args()
    sys.exit(main(a.dry))
