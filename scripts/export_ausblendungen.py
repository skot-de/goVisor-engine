#!/usr/bin/env python3
"""Weggeklickte Vorgaenge → `web/data/ausblendungen.json` (anonymisiert, je Vorgang).

⚠ WARUM NICHT EINFACH DIE ZEILEN IN DIE AKTE. Sven am 2026-09-20: „nimm die daten mit in
die akte auf, dann haben wir es da zentral nutzeruebergreifend, aber koennen auch aus der
sicht des nutzers drauf schauen." Beides geht — aber nicht aus derselben Quelle:

  · Die Akte (`web/data/vorgang/*.json`) ist eine STATISCHE Datei. Sie wird im Nachtlauf
    gebaut und ist fuer jeden angemeldeten Nutzer dieselbe. Eine `user_id` darin waere
    fremde Information in einer Datei, die alle lesen.
  · `user_lead_hidden` ist RLS-geschuetzt: jeder sieht nur seine eigenen Zeilen. Genau so
    gehoert die EIGENE Sicht geladen — zur Laufzeit, nicht aus einer Datei.

Dieses Skript baut deshalb nur die nutzeruebergreifende Haelfte, und die ohne Kennungen:
je Vorgang die ANZAHL und die Gruende, keine `user_id`, kein Zeitstempel je Person.

⚠ DIE SCHWELLE IST KEIN GESCHMACK, SONDERN DER DATENSCHUTZ. Bei drei Kunden ist
„1 Nutzer hat weggeklickt: Entfernung" keine Statistik, sondern eine Aussage ueber eine
bestimmte Person — und zwar eine, die dieser Person gehoert. Unterhalb von `--mindestens`
(Vorgabe 5) steht deshalb GAR NICHTS in der Datei, nicht einmal eine Null. goVisor hat
heute keine Kundschaft; genau deshalb muss die Regel jetzt hinein und nicht spaeter.

Aufruf:  python3 scripts/export_ausblendungen.py [--mindestens 5] [--trocken]
Rueckgabe: 0 immer (keine Daten ist kein Fehler)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from collections import Counter, defaultdict

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))


def _dsn() -> str | None:
    a, b = WURZEL / ".secrets" / "supabase.txt", WURZEL / ".secrets" / "supabase_db.txt"
    if not (a.exists() and b.exists()):
        return None
    try:
        ref = a.read_text(encoding="utf-8").splitlines()[0].split("//")[1].split(".")[0]
        return (f"postgresql://postgres:{b.read_text(encoding='utf-8').strip()}"
                f"@db.{ref}.supabase.co:5432/postgres")
    except (IndexError, OSError):
        return None


def hole_zeilen() -> list[tuple[str, str]] | None:
    """(lead_id, grund) — ⚠ OHNE `user_id`. Sie wird hier nicht einmal gelesen, damit sie
    auch bei einem spaeteren Umbau nicht versehentlich in die Ausgabe wandert."""
    dsn = _dsn()
    if not dsn:
        return None
    try:
        from govisor.psql import psql_oder_fehler
        r = subprocess.run(
            [psql_oder_fehler(), dsn, "-At", "-F", "\x1f", "-c",
             "select lead_id, coalesce(grund,'') from public.user_lead_hidden"],
            capture_output=True, text=True, timeout=90)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    raus = []
    for z in r.stdout.splitlines():
        if not z.strip():
            continue
        t = z.split("\x1f")
        if len(t) >= 2:
            raus.append((t[0], t[1]))
    return raus


def _vorgang_je_notice(kennungen: set[str]) -> dict:
    if not kennungen:
        return {}
    try:
        import duckdb
        import glob as _g
        dateien = sorted(_g.glob("data/gold/*/vorgang_notice.parquet"))
        if not dateien:
            return {}
        con = duckdb.connect()
        lst = ",".join("'" + k.replace("'", "") + "'" for k in kennungen)
        return {r[0]: r[1] for r in con.execute(
            f"SELECT notice_id, vorgang_id FROM read_parquet({dateien!r}, union_by_name=true)"
            f" WHERE notice_id IN ({lst})").fetchall()}
    except Exception:
        return {}


def baue(zeilen: list[tuple[str, str]], mindestens: int) -> dict:
    karte = _vorgang_je_notice({lid for lid, _ in zeilen})
    je_vorgang: dict[str, Counter] = defaultdict(Counter)
    zahl: Counter = Counter()
    for lid, grund in zeilen:
        vid = karte.get(lid)
        if not vid:
            continue
        zahl[vid] += 1
        if grund:
            je_vorgang[vid][grund] += 1
    # ⚠ Erst zaehlen, dann schwellen. Wer vorher filtert, verliert die Gesamtzahl und
    # meldet spaeter „2 Ausblendungen" fuer einen Vorgang, den fuenf weggeklickt haben.
    return {vid: {"n": n, "gruende": dict(je_vorgang[vid])}
            for vid, n in zahl.items() if n >= mindestens}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mindestens", type=int, default=5)
    ap.add_argument("--trocken", action="store_true")
    a = ap.parse_args()

    zeilen = hole_zeilen()
    if zeilen is None:
        print("  (kein Zugang zur Datenbank — Datei bleibt, wie sie ist)")
        return 0
    daten = baue(zeilen, a.mindestens)
    print(f"  {len(zeilen):,} Ausblendungen → {len(daten):,} Vorgaenge ueber der Schwelle "
          f"(n >= {a.mindestens})")
    if a.trocken:
        return 0
    ziel = WURZEL / "web" / "data" / "ausblendungen.json"
    teil = ziel.with_suffix(".json.part")
    teil.write_text(json.dumps({"mindestens": a.mindestens, "vorgaenge": daten},
                               ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    teil.replace(ziel)
    print(f"  → {ziel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
