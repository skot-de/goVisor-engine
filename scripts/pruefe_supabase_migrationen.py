#!/usr/bin/env python3
"""Welche Migration steht in `supabase/`, ist aber nie in der Datenbank angekommen?

⚠ WARUM DAS EINE EIGENE SONDE BRAUCHT. Der Ausfall ist LAUTLOS, in beide Richtungen. Die
Client-Module fangen jeden Fehler ab und tun dann nichts:

    } catch { /* no-op: Ausblenden darf nie eine Fehlermeldung erzeugen */ }

Das ist richtig so — ein Klick in der Liste darf nie eine rote Meldung erzeugen. Die Folge
ist aber, dass eine fehlende Tabelle sich genau wie ein erfolgreicher Klick anfuehlt: der
Knopf reagiert, die Oberflaeche merkt sich den Zustand, und beim naechsten Laden ist er weg.
Und von der anderen Seite schweigt es ebenso: alle Tests sind gruen, denn sie pruefen den
Code, nicht die Datenbank.

⚠ GEFUNDEN AM 2026-09-19, nebenbei. Beim Anlegen von `user_lead_status` (0023) fiel beim
Blick auf die Live-Tabellen auf, dass auch **0021 (Ausblenden)** und **0022 (gespeicherte
Filter)** nicht angewandt waren. Zwei fertig gebaute, getestete Funktionen, die seit ihrem
Bau nichts speichern — und niemandem ist es aufgefallen, weil nichts davon je einen Fehler
zeigt.

Aufruf:  python3 scripts/pruefe_supabase_migrationen.py [--still]
Rueckgabe: 0 alles angewandt · 1 etwas fehlt · 2 keine Auskunft moeglich (kein Zugang)
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

WURZEL = pathlib.Path(__file__).resolve().parent.parent
# ⚠ Als Skript aufgerufen ist sys.path[0] das `scripts`-Verzeichnis, nicht die Wurzel —
# ohne diese Zeile scheitert `import govisor.psql`, und die Sonde meldet ehrlich, aber
# falsch „Datenbank nicht erreichbar".
sys.path.insert(0, str(WURZEL))


def _dsn() -> str | None:
    """Zugangsdaten aus `.secrets/`. Fehlt etwas, gibt es keine Auskunft — keinen Fehler."""
    a, b = WURZEL / ".secrets" / "supabase.txt", WURZEL / ".secrets" / "supabase_db.txt"
    if not (a.exists() and b.exists()):
        return None
    try:
        ref = a.read_text(encoding="utf-8").splitlines()[0].split("//")[1].split(".")[0]
        pw = b.read_text(encoding="utf-8").strip()
    except (IndexError, OSError):
        return None
    return f"postgresql://postgres:{pw}@db.{ref}.supabase.co:5432/postgres"


def erwartete_tabellen(ordner: pathlib.Path | None = None) -> dict[str, list[str]]:
    """Migration → die Tabellen, die sie anlegt.

    ⚠ Kommentare vorher raus. Eine AUSKOMMENTIERTE `create table`-Zeile ist keine Tabelle,
    die jemand erwartet — sie steht da, weil sie verworfen wurde. Ohne Strippen meldet die
    Sonde sie jede Nacht als fehlend, und ein Bericht mit Rauschen wird nicht gelesen (F13:
    der Waechter liest seinen eigenen Kommentar).

    `ordner` ist nur fuer den Test da: sonst liesse sich dieser Fall nicht nachstellen,
    ohne eine Wegwerf-Migration in `supabase/` abzulegen.
    """
    raus: dict[str, list[str]] = {}
    for f in sorted((ordner or (WURZEL / "supabase")).glob("0*.sql")):
        txt = "\n".join(z.split("--")[0] for z in f.read_text(encoding="utf-8").splitlines())
        t = sorted(set(re.findall(r"create table if not exists public\.(\w+)", txt)))
        if t:
            raus[f.name] = t
    return raus


def live_tabellen(dsn: str) -> set[str] | None:
    try:
        from govisor.psql import psql_oder_fehler
        r = subprocess.run(
            [psql_oder_fehler(), dsn, "-At", "-c",
             "select table_name from information_schema.tables where table_schema='public'"],
            capture_output=True, text=True, timeout=60)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    return set(r.stdout.split())


def main() -> int:
    still = "--still" in sys.argv
    dsn = _dsn()
    if not dsn:
        if not still:
            print("  (keine Zugangsdaten in .secrets/ — keine Auskunft)")
        return 2
    live = live_tabellen(dsn)
    if live is None:
        if not still:
            print("  (Datenbank nicht erreichbar — keine Auskunft)")
        return 2

    fehlend = {}
    for name, tabellen in erwartete_tabellen().items():
        fehlt = [t for t in tabellen if t not in live]
        if fehlt:
            fehlend[name] = fehlt

    if not fehlend:
        if not still:
            print(f"  ✓ alle Migrationen angewandt ({len(live)} Tabellen live)")
        return 0

    print(f"  ⛔ {len(fehlend)} Migration(en) nicht angewandt:\n")
    for name, fehlt in fehlend.items():
        print(f"     {name:<34} fehlt: {', '.join(fehlt)}")
    print("\n  Was das bedeutet: die zugehoerigen Funktionen speichern NICHTS und melden")
    print("  auch nichts. Anwenden mit:")
    print("     psql \"$DSN\" -f supabase/<datei>.sql")
    return 1


if __name__ == "__main__":
    sys.exit(main())
