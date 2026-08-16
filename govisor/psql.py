"""`psql` finden — an einer Stelle, für alle Aufrufer.

**Warum es das gibt.** Am 2026-08-16 meldete der Tageslauf zweimal
``FileNotFoundError: 'psql'``: die Supabase-Schema-Migration und die nächtliche
``gap_effects``-Vorberechnung liefen beide nicht. `psql` ist installiert — unter
``/opt/homebrew/bin`` —, aber der PATH, den **launchd** einem Agenten gibt, kennt Homebrew
nicht. Aus dem Terminal lief alles, weil dort Homebrew im PATH steht.

Genau diese Diskrepanz ist die Falle: der Fehler tritt NUR im geplanten Lauf auf, also
dort, wo niemand zusieht. Die Shell-Seite hatte deshalb schon eine eigene Suche
(`scripts/daily_leads.sh`); die Python-Seite verliess sich weiter auf den PATH.

**Warum hier und nicht in jedem Skript.** Drei Nachbauten derselben Liste laufen beim
ersten neuen Installationsort auseinander — und zwar lautlos, weil jeder Aufrufer seinen
eigenen „übersprungen"-Zweig hat.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

# Reihenfolge = Wahrscheinlichkeit auf einem Entwickler-Mac. `PSQL` steht vorn, damit ein
# abweichender Aufbau ohne Codeänderung versorgt werden kann.
KANDIDATEN = (
    "/opt/homebrew/bin/psql",                 # Homebrew, Apple Silicon
    "/usr/local/bin/psql",                    # Homebrew, Intel
    "/opt/homebrew/opt/libpq/bin/psql",       # nur Client-Bibliothek (kein Server)
    "/usr/local/opt/libpq/bin/psql",
    "/Applications/Postgres.app/Contents/Versions/latest/bin/psql",
)


def finde_psql() -> str | None:
    """Pfad zu `psql` oder ``None``. Sucht Umgebungsvariable → PATH → bekannte Orte."""
    aus_umgebung = os.environ.get("PSQL")
    if aus_umgebung and Path(aus_umgebung).is_file() and os.access(aus_umgebung, os.X_OK):
        return aus_umgebung
    im_pfad = shutil.which("psql")
    if im_pfad:
        return im_pfad
    for k in KANDIDATEN:
        if Path(k).is_file() and os.access(k, os.X_OK):
            return k
    # Postgres.app kann versionierte Ordner statt `latest` haben.
    for verz in sorted(Path("/Applications/Postgres.app/Contents/Versions").glob("*/bin/psql"),
                       reverse=True):
        if os.access(verz, os.X_OK):
            return str(verz)
    return None


def psql_oder_fehler() -> str:
    """Wie `finde_psql`, aber mit einer Meldung, die sagt, was zu tun ist.

    Ein blankes `FileNotFoundError: 'psql'` im Log eines nächtlichen Laufs beantwortet die
    einzige wichtige Frage nicht: fehlt das Programm, oder findet es nur dieser Lauf nicht?
    """
    p = finde_psql()
    if p:
        return p
    raise FileNotFoundError(
        "psql nicht gefunden. Gesucht in $PSQL, im PATH und unter: "
        + ", ".join(KANDIDATEN)
        + ". Unter launchd fehlt Homebrew im PATH — installieren mit `brew install libpq` "
          "oder den Pfad per Umgebungsvariable PSQL setzen."
    )
