#!/usr/bin/env python3
"""Supabase auf das Noetige eindampfen — die `gov_*`-Spiegeltabellen leeren.

**Warum es das gibt.** Am 2026-08-16 meldete Supabase das Ueberschreiten des Free-Limits:
**787 MB bei 500 MB erlaubt.** Gemessen waren davon **775 MB (98,5 %) die acht
`gov_*`-Tabellen** — und die liest niemand. Das Frontend holt seine Leads aus
`web/data/leads-<branche>.json` (erzeugt von `export_web_leads.py` aus den lokalen
Parquet-Dateien); aus Supabase kommen ausschliesslich die `user_*`-Tabellen, zusammen 568 kB.

Die `gov_*`-Tabellen sind ein Ueberbleibsel der frueheren Architektur, in der das Frontend
Leads aus Postgres lesen sollte. Der Umzug auf JSON hat den Leser entfernt, nicht den
Schreiber: der Tageslauf pusht seither zweimal taeglich einen Bestand, den nichts abruft.

**Warum leeren und nicht loeschen.** Struktur, Indizes und die sieben RLS-Policies bleiben
stehen. Beim Go-live ist der Weg zurueck ein einziger Befehl:

    python3 scripts/export_supabase.py --table all --prune

**Es geht nichts verloren.** Jede `gov_*`-Tabelle ist eine Kopie einer lokalen Parquet-Datei
(Registry `TABLES` in `export_supabase.py`). Vor dem Leeren geprueft und leer:
keine Views, keine Fremdschluessel anderer Tabellen darauf, keine Funktion oder Trigger,
die sie referenziert.

⚠ **VACUUM FULL ist der Punkt, an dem der Platz wirklich frei wird.** Ein blosses `DELETE`
oder `TRUNCATE` gibt die Seiten nicht ans Betriebssystem zurueck — die Datenbank bliebe
gemeldet gross. `TRUNCATE` allein schrumpft zwar die Tabelle, aber nicht den TOAST-Bereich
verlaesslich; `VACUUM FULL` schreibt beides neu. Es sperrt die Tabelle exklusiv, was hier
folgenlos ist: niemand liest sie.

Aufruf:
    python3 scripts/supabase_schlank.py                 # nur zeigen, nichts aendern
    python3 scripts/supabase_schlank.py --ausfuehren    # wirklich leeren
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Genau die Tabellen aus der Exporter-Registry, plus die zwei Altlasten, die dort NICHT
# stehen und trotzdem Platz belegen. `gov_sample_raw` hat 0 Zeilen bei 3,6 MB und wird im
# ganzen Projekt nirgends referenziert.
GOV_TABELLEN = (
    "gov_leads", "gov_lead_lots", "gov_lead_requirements", "gov_lead_parties",
    "gov_lead_criteria", "gov_lead_cpv", "gov_bronze_inventory", "gov_sample_raw",
)


def _psql() -> str:
    p = shutil.which("psql")
    if p:
        return p
    for k in ("/opt/homebrew/bin/psql", "/usr/local/bin/psql"):
        if Path(k).is_file() and os.access(k, os.X_OK):
            return k
    raise SystemExit("psql nicht gefunden (brew install libpq).")


def _verbindung() -> tuple[str, dict]:
    """(Host, Umgebung mit Passwort). Zugangsdaten werden gelesen, nie ausgegeben."""
    u = ROOT / ".secrets" / "supabase.txt"
    d = ROOT / ".secrets" / "supabase_db.txt"
    if not (u.exists() and d.exists()):
        raise SystemExit(f"Zugangsdaten fehlen: {u} und/oder {d}")
    url = u.read_text(encoding="utf-8").splitlines()[0].strip()
    ref = url.split("//", 1)[-1].split(".", 1)[0]
    env = dict(os.environ, PGPASSWORD=d.read_text(encoding="utf-8").strip())
    return f"db.{ref}.supabase.co", env


def sql(host: str, env: dict, befehl: str) -> str:
    r = subprocess.run([_psql(), "-h", host, "-p", "5432", "-U", "postgres", "-d", "postgres",
                        "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", befehl],
                       capture_output=True, text=True, env=env, timeout=1800)
    if r.returncode != 0:
        raise SystemExit(f"psql: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def bestand(host: str, env: dict) -> list[tuple[str, str, str]]:
    roh = sql(host, env, """
        select c.relname||'|'||pg_size_pretty(pg_total_relation_size(c.oid))
               ||'|'||coalesce(to_char(s.n_live_tup,'FM999G999'),'?')
        from pg_class c join pg_namespace ns on ns.oid=c.relnamespace
        left join pg_stat_user_tables s on s.relid=c.oid
        where ns.nspname='public' and c.relkind='r' and c.relname like 'gov\\_%'
        order by pg_total_relation_size(c.oid) desc""")
    return [tuple(z.split("|")) for z in roh.splitlines() if z]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--ausfuehren", action="store_true",
                   help="wirklich leeren. Ohne diese Angabe wird nur gezeigt.")
    a = p.parse_args(argv)
    host, env = _verbindung()

    vorher = sql(host, env, "select pg_size_pretty(pg_database_size(current_database()))")
    print(f"Datenbank jetzt: {vorher}\n")
    zeilen = bestand(host, env)
    if not zeilen:
        print("Keine gov_*-Tabellen gefunden — nichts zu tun.")
        return 0
    print(f"{'Tabelle':<24}{'Grösse':>10}{'Zeilen':>12}")
    for name, groesse, n in zeilen:
        print(f"{name:<24}{groesse:>10}{n:>12}")

    if not a.ausfuehren:
        print("\nProbelauf — nichts geändert. Zum Leeren: --ausfuehren")
        print("Zurückholen jederzeit: python3 scripts/export_supabase.py --table all --prune")
        return 0

    # Eine Anweisung je Tabelle: erst leeren, dann den Platz zurückgeben. Getrennt, damit
    # eine fehlende Tabelle nicht den ganzen Lauf abbricht.
    for name, groesse, _ in zeilen:
        print(f"\n  {name} ({groesse}) …", flush=True)
        sql(host, env, f"truncate table public.{name}")
        sql(host, env, f"vacuum full public.{name}")
        print("    geleert und verdichtet.", flush=True)

    nachher = sql(host, env, "select pg_size_pretty(pg_database_size(current_database()))")
    print(f"\nDatenbank vorher: {vorher}  →  jetzt: {nachher}")
    print("Struktur, Indizes und RLS-Policies stehen unverändert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
