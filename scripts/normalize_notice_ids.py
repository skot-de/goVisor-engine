#!/usr/bin/env python3
"""Einmal-Migration: interne ``notice_id``/``lead_id``-Spalten in Silber + Gold kanonisieren.

**Root-Cause** ist im Ingest gefixt (``schema.normalize_notice_id`` in ``silver.py`` an beiden
Pfaden verdrahtet). Dieses Skript heilt den **Vor-Fix-Bestand**: 290k IDs wurden vor dem Fix in
zwei Formen geschrieben — ``00450024_2026`` (Archiv, zero-padded, ``_``) und ``450024-2026``
(Live/DÖE, ``-``). Solange ein Monat nicht neu ingestet wird, sind Silber und Gold intern
konsistent; beim nächsten Re-Ingest schreibt der Ingest die **kanonische** Form → alle Gold-Zeilen
auf der Alt-Form verwaisen. Diese Migration bringt den ganzen Bestand auf die kanonische Form
``<zahl>_<jahr>`` (führende Nullen weg, Trenner ``_``), damit Re-Ingest nie wieder verwaisen kann.

Reine, **uniforme Umbenennung des Join-Keys** (0 Kollisionen gemessen) — es wird KEINE Analytik
neu abgeleitet, nur die ID-Spalte umgeschrieben. Datei-weise atomarer Rewrite (kein Voll-Backup
nötig, platzsparend). **Idempotent** (nochmal laufen lassen = No-Op).

NICHT angefasst — der **TED-öffentliche** ID-Raum, in dem der Bindestrich kanonisch ist und in
Award-Link-Joins (``publication_number = ref_publication_number``, gold.py) sowie TED-URLs steckt:
``publication_number``, ``ref_publication_number``, ``tender_publication_number``, ``procedure_id``.

Aufruf::

    python3 scripts/normalize_notice_ids.py            # Dry-Run (zeigt, was sich ändern würde)
    python3 scripts/normalize_notice_ids.py --apply    # schreibt

Die 551 aktuellen leads-Waisen (source=f02, laufender Monat) sind KEIN Formatproblem — es sind
Live-Notices, die das Teilmonats-Archiv (noch) nicht enthält; ihre kanonische Form fehlt in Silber
(nachgemessen). Sie verschwinden beim nächsten Voll-Gold-Rebuild, nicht durch diese Migration.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

import duckdb

# Interner notice_id-Raum → kanonisieren. Bewusst per SpaltenNAME (nicht per Wertmuster), damit
# der TED-publication_number-Raum garantiert unberührt bleibt.
NORMALIZE_COLS = {
    "notice_id", "lead_id",                 # Haupt-Join-Keys (Silber + Gold)
    "predecessor", "successor",             # Nachfolge-Kanten (sind notice_ids)
    "cand1", "cand2",                       # LLM-Queue-Kandidaten (notice_ids)
    "award_notice_id", "tender_notice_id",  # Award↔Ausschreibung-Verknüpfung (notice_ids)
}
# Defensive Sperrliste — diese Namen NIE anfassen, auch wenn sie das Muster tragen.
PROTECTED = {"publication_number", "ref_publication_number",
             "tender_publication_number", "procedure_id"}

# Muss schema.normalize_notice_id exakt spiegeln (verifiziert): 0*(\d+)[-_](\d{4}) → \1_\2.
CANON = r"regexp_replace({c}, '^0*([0-9]+)[-_]([0-9]{{4}})$', '\1_\2')"


def _cols(con, path):
    return [c[0] for c in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{path}')").fetchall()]


def _targets(cols):
    hit = [c for c in cols if c in NORMALIZE_COLS]
    assert not (set(cols) & PROTECTED & NORMALIZE_COLS), "Sperrliste/Allow-Liste überschneiden sich"
    return hit


def process(con, path, apply):
    cols = _cols(con, path)
    targets = _targets(cols)
    if not targets:
        return 0, 0
    # Wie viele Werte würden sich real ändern?
    changed = con.execute(
        f"SELECT count(*) FROM read_parquet('{path}') WHERE " +
        " OR ".join(f"{c} <> {CANON.format(c=c)}" for c in targets)
    ).fetchone()[0]
    if apply and changed:
        select = ", ".join(f"{CANON.format(c=c)} AS {c}" if c in targets else c for c in cols)
        tmp = path + ".tmp"
        con.execute(f"COPY (SELECT {select} FROM read_parquet('{path}')) "
                    f"TO '{tmp}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        os.replace(tmp, path)   # atomar
    return changed, len(targets)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="schreibt (sonst Dry-Run)")
    ap.add_argument("--data-dir", default="data")
    args = ap.parse_args()

    con = duckdb.connect()
    silver = sorted(glob.glob(f"{args.data_dir}/silver/DE/**/*.parquet", recursive=True))
    gold = sorted(glob.glob(f"{args.data_dir}/gold/DE/*.parquet"))
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== notice_id-Kanonisierung [{mode}] — {len(silver)} Silber- + {len(gold)} Gold-Dateien ===\n")

    total_changed = 0
    per_table: dict[str, list] = {}
    for path in silver + gold:
        try:
            changed, ntarget = process(con, path, args.apply)
        except Exception as e:
            print(f"  ✗ {path}: {e}")
            continue
        if ntarget == 0:
            continue
        # Silber nach Tabelle gruppieren, Gold je Datei
        if "/silver/" in path:
            key = "silver/" + path.split("/silver/DE/")[1].split("/")[0]
        else:
            key = "gold/" + os.path.basename(path)
        c, f = per_table.setdefault(key, [0, 0])
        per_table[key] = [c + changed, f + 1]
        total_changed += changed

    for key in sorted(per_table):
        c, f = per_table[key]
        mark = "" if c else "  (schon kanonisch)"
        print(f"  {key:34} geändert={c:>8,}  dateien={f}{mark}")
    print(f"\n  Summe geänderter ID-Werte: {total_changed:,}")

    if not args.apply:
        print("\n  Dry-Run — nichts geschrieben. Mit --apply ausführen.")
        return 0

    # Verifikation nach dem Schreiben. Präzise: eine TED-Format-ID (<zahl><trenner><jahr>), die
    # NICHT kanonisch ist. DÖE-IDs (UUID / reine Zahl) sind ein eigener Namensraum und matchen
    # das Muster gar nicht — sie dürfen (und müssen) unangetastet bleiben, nicht mitzählen.
    print("\n=== Verifikation ===")
    N = f"{args.data_dir}/silver/DE/notices/*/*.parquet"
    canon = CANON.format(c="notice_id")
    rest = con.execute(
        f"SELECT count(*) FROM read_parquet('{N}', hive_partitioning=1) "
        f"WHERE regexp_matches(notice_id, '^0*[0-9]+[-_][0-9]{{4}}$') AND notice_id <> {canon}"
    ).fetchone()[0]
    print(f"  Silber-notices im TED-Format, aber nicht kanonisch (muss 0 sein): {rest:,}")
    orph = con.execute(
        f"SELECT count(*) FROM read_parquet('{args.data_dir}/gold/DE/leads.parquet') l "
        f"WHERE NOT EXISTS (SELECT 1 FROM read_parquet('{N}', hive_partitioning=1) n "
        f"WHERE n.notice_id = l.lead_id)").fetchone()[0]
    print(f"  leads-Waisen (echter Datengap, unverändert ~551 erwartet): {orph:,}")
    return 0 if rest == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
