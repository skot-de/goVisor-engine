"""Live-Nachzügler in eine bereits abgeschlossene Monatsdatei einfalten.

**Das Problem.** Der Live-Abruf sortiert eine Notice nach dem `publication_date` aus ihrem
XML ein. Die TED-Search-API dagegen findet sie über die OJS-Ausgabe, und die läuft dem
XML-Datum nach: gemessen an AT tragen Notices, die erst über die Juli-Facette auftauchen,
im XML den 30. Juni. Der Abruf schreibt sie folglich nach `2026-06-live.parquet` — neben
ein `2026-06.parquet`, das längst fertig ist.

**Warum das nicht einfach nebeneinander stehen darf.** Der Silber-Glob liest beide Dateien.
Ob das doppelt zählt oder korrekt vereinigt, hängt allein davon ab, ob sich die Notices
überschneiden — und darauf darf sich nichts verlassen. Genau diese Konstellation hat einmal
128 Notices zu 220.756 statt 77.746 Lead-Zeilen aufgeblasen. `tests/test_plumbing.py::
test_silver_month_files_do_not_shadow_each_other` verbietet sie seitdem pauschal.

**Die Auflösung.** Nicht den Guard aufweichen, sondern den Zustand herstellen, den er
verlangt: EINE Datei je Monat. Übernommen wird aus der Live-Datei, was die Monatsdatei
nicht kennt (Schlüssel `notice_id`, in jeder der neun Tabellen vorhanden). Bei Kollision
gewinnt das Archiv — es ist die vollständigere Quelle.

Sicherungen, weil hier eine bestehende Datei überschrieben wird:
  · Die Notice-Menge des Archivs kann nur wachsen, nie schrumpfen — sonst Abbruch.
  · Geschrieben wird über `.part` + `rename` (atomar), erst danach fällt die Live-Datei.
  · `--dry-run` zeigt die Bilanz je Tabelle, ohne etwas anzufassen.

Aufruf:  python scripts/merge_live_into_month.py --country AT --month 2026-06 [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import model  # noqa: E402  (Pfad muss zuerst stehen)

SILBER = ROOT / "data" / "silver"


def merge(country: str, monat: str, dry: bool) -> int:
    jahr = monat[:4]
    con = duckdb.connect()
    bilanz, paare = [], []

    for tabelle in model.TABLES:
        basis = SILBER / country / tabelle / f"year={jahr}"
        archiv, live = basis / f"{monat}.parquet", basis / f"{monat}-live.parquet"
        if not live.exists():
            continue
        if not archiv.exists():
            # Nichts einzufalten — die Live-Datei IST hier die Monatsdatei.
            bilanz.append((tabelle, 0, 0, "kein Archiv, Live-Datei bleibt"))
            continue

        a_ids = f"(SELECT DISTINCT notice_id FROM read_parquet('{archiv.as_posix()}'))"
        neu = con.execute(f"""
            SELECT count(*) FROM read_parquet('{live.as_posix()}')
            WHERE notice_id NOT IN {a_ids}""").fetchone()[0]
        alt = con.execute(f"SELECT count(*) FROM read_parquet('{archiv.as_posix()}')").fetchone()[0]
        bilanz.append((tabelle, alt, neu, ""))
        paare.append((tabelle, archiv, live, alt, neu))

    breite = max((len(t) for t, *_ in bilanz), default=10)
    print(f"{country} {monat}:")
    for t, alt, neu, hinweis in bilanz:
        print(f"  {t:{breite}s}  {alt:8,} + {neu:6,} neu" + (f"   ({hinweis})" if hinweis else ""))
    if dry:
        print("\n--dry-run: nichts geschrieben.")
        return 0

    for tabelle, archiv, live, alt, neu in paare:
        a_ids = f"(SELECT DISTINCT notice_id FROM read_parquet('{archiv.as_posix()}'))"
        tmp = archiv.with_suffix(".part")
        con.execute(f"""
            COPY (
                SELECT * FROM read_parquet('{archiv.as_posix()}')
                UNION ALL BY NAME
                SELECT * FROM read_parquet('{live.as_posix()}') WHERE notice_id NOT IN {a_ids}
            ) TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)""")
        danach = con.execute(f"SELECT count(*) FROM read_parquet('{tmp.as_posix()}')").fetchone()[0]
        if danach < alt:
            tmp.unlink(missing_ok=True)
            print(f"  ABBRUCH {tabelle}: {danach:,} < {alt:,} — die Monatsdatei würde schrumpfen.")
            return 1
        tmp.replace(archiv)          # atomar: erst wenn die neue Datei vollständig ist
        live.unlink()                # danach erst darf die Live-Datei fallen
        print(f"  ✓ {tabelle}: {alt:,} → {danach:,}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", required=True)
    ap.add_argument("--month", required=True, help="YYYY-MM der abgeschlossenen Monatsdatei")
    ap.add_argument("--dry-run", dest="dry", action="store_true")
    a = ap.parse_args()
    sys.exit(merge(a.country, a.month, a.dry))
