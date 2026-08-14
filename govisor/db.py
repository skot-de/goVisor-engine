"""Eine Stelle für DuckDB-Verbindungen — mit Speicher- und Auslagerungs-Grenzen.

**Warum es das gibt.** Am 2026-08-14 musste der Rechner neu gestartet werden, weil der
interne Speicher volllief. Die Ursachen lagen an drei Stellen, und zwei davon sind
Einstellungen, die niemand je gesetzt hat:

* **DuckDB nimmt sich per Vorgabe ~80 % des RAM** — auf dieser Maschine 12,7 von 16 GB.
  Daneben laufen acht Index-Arbeiter und das Betriebssystem. Reicht es nicht, weicht macOS
  auf Swap aus, und der liegt auf der INTERNEN Platte (2 GB). Ein Grenzwert, der DuckDB zum
  Auslagern zwingt, ist deshalb *besser* als einer, der es in den System-Swap treibt: die
  Auslagerung geht auf die grosse Platte, der Swap nicht.
* **Die Auslagerung selbst** landete unter ``.tmp`` relativ zum Arbeitsverzeichnis — und das
  Repo liegt intern, während die 2-TB-SSD extern hängt.

**Warum nicht überall.** Das Projekt hat 125 ``duckdb.connect()``-Stellen. Sie alle
umzustellen wäre unverhältnismässig; die Auslagerung ist deshalb zusätzlich über einen
Symlink (``.tmp`` → ``data/.tmp``) global gelöst, der ohne Code-Änderung für alle greift.
Dieser Helfer ist für die SCHWEREN Verbraucher gedacht — Gold, Firewall, Index, Marktpuls —,
wo der Speicher tatsächlich knapp wird.

Wer eine neue schwere Abfrage schreibt, nimmt ``db.connect()`` statt ``duckdb.connect()``.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Wieviel RAM DuckDB nehmen darf. Bewusst deutlich unter der Vorgabe: es muss Platz bleiben
# für die Python-Prozesse daneben (der Index faehrt acht Arbeiter) und fuer das System.
# Ueberschreitet eine Abfrage die Grenze, laeuft sie trotzdem — DuckDB lagert dann auf die
# Platte aus, und die ist dank `.tmp` die grosse externe.
#
# Ueber `GOVISOR_DB_MEM` ueberschreibbar, falls die Maschine wechselt.
SPEICHER = os.environ.get("GOVISOR_DB_MEM", "6GB")

# Threads: DuckDB nimmt sonst alle Kerne. Laeuft parallel ein Arbeiter-Pool (Index), streiten
# sie sich; die Vorgabe laesst deshalb zwei Kerne fuer alles andere frei.
FAEDEN = os.environ.get("GOVISOR_DB_THREADS", "")


def temp_verzeichnis() -> Path:
    """Auslagerung auf die grosse Platte, nicht auf die Systemplatte."""
    p = ROOT / "data" / ".tmp"
    p.mkdir(parents=True, exist_ok=True)
    return p


def connect(*, speicher: str | None = None, faeden: str | None = None):
    """DuckDB-Verbindung mit gesetzten Grenzen. Sonst wie ``duckdb.connect()``."""
    import duckdb

    con = duckdb.connect()
    con.execute(f"SET memory_limit='{speicher or SPEICHER}'")
    con.execute(f"SET temp_directory='{temp_verzeichnis().as_posix()}'")
    f = faeden or FAEDEN
    if f:
        con.execute(f"SET threads={int(f)}")
    return con
