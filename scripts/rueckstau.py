#!/usr/bin/env python3
"""Rückstau abarbeiten — EINEN Dokument-Abrufer bis zum Ende durchziehen.

**Warum es das gibt.** Der Tageslauf holt je Abrufer 60 Vorgänge pro Nacht. Gemessen am
2026-08-17 liegen aber **7.649 Vorgänge** im Rückstau, bei einem Zulauf von rund 796 neuen
Bekanntmachungen am Tag. Die Nacht arbeitet damit nicht das Tagesdelta ab, sondern greift
sich eine Scheibe aus einem Berg — und welche 60 das sind, entscheidet die Sortierung.

Genau daher kommt die Unberechenbarkeit: ein Vorgang ist gemessen alles zwischen 0 und
636 MB (Median 8,1), 60 Stück sind je nach Zusammensetzung 0,6 bis 3,3 GB. Der Tageslauf
schwankte deshalb zwischen 55 und 719 Minuten, obwohl Quelle und Verfahren gleich blieben.

Sven am 2026-08-17: „dann müssen wir läufe manuell anstoßen und am besten connector für
connector isoliert, bis das backlog abgearbeitet ist und dann haben wir bei den tagesläufen
nur noch das delta von gestern zu heute."

**Was dieses Werkzeug NICHT tut: selbst herunterladen.** Es ruft in Runden den vorhandenen
Abrufer auf. Der kennt sein Portal, seine Höflichkeitspausen, seine Deckel und seine
Warteschlange — das hier noch einmal zu bauen hiesse, dreizehn Sonderfälle zu verdoppeln
und beim nächsten Portalwechsel zwei Stellen zu pflegen.

**Wiederaufnahme ist geschenkt.** Die Abrufer sind idempotent: bereits geholte Vorgänge
stehen als ``exists`` im Manifest und werden übersprungen. Ein Abbruch kostet also nur die
angefangene Runde. Aus demselben Grund braucht es keinen eigenen Fortschrittsspeicher —
der Reststand steht in den Daten, nicht in einer Datei daneben.

Aufruf::

    scripts/rueckstau.py --zeigen
    scripts/rueckstau.py --connector netserver --stunden 4
    scripts/rueckstau.py --connector evergabe --stunden 2 --limit 40
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import sources as S  # noqa: E402

LOCK = ROOT / "data" / ".daily_leads.lock"

# Die Abrufer melden ihren Reststand selbst, in einer über alle dreizehn einheitlichen
# Zeile: „<Portal>: N Vergaben zu holen (von M offenen Leads)". Das ist der Stand NACH
# ihrem eigenen Warteschlangen-Filter, also genau die Zahl, die zählt. Sie hier neu
# auszurechnen hiesse, ihre Filterlogik ein zweites Mal zu schreiben.
_REST = re.compile(r"(\d[\d.,]*)\s+Vergaben zu holen")


def _zahl(s: str) -> int:
    return int(s.replace(".", "").replace(",", ""))


def abrufer() -> dict[str, str]:
    """Kurzname → Python-Modul, aus der Registry statt aus einer zweiten Liste."""
    out = {}
    for q in S.DOC_REGISTRY:
        if not q.modul:
            continue
        out[q.modul.rsplit(".", 1)[-1].replace("docfetch_", "").replace("docfetch", "cosinex")] = q.modul
    return out


def frei() -> tuple[bool, str]:
    """Läuft der Tageslauf? Dann NICHT starten.

    Beide würden in dieselben Manifeste und denselben Dokumentenbaum schreiben. Der
    Tageslauf schützt sich per Lock; Aufrufe von Hand tun das nicht, und genau die sind
    im Projekt schon einmal kollidiert.
    """
    if LOCK.exists():
        return False, f"Tageslauf aktiv ({LOCK.name})"
    return True, ""


def eine_runde(modul: str, limit: int) -> tuple[int, str]:
    """Ein Abrufer-Aufruf. Gibt (Reststand vor der Runde, Rohausgabe) zurück."""
    p = subprocess.run([sys.executable, "-m", modul, "--limit", str(limit)],
                       cwd=ROOT, capture_output=True, text=True)
    aus = (p.stdout or "") + (p.stderr or "")
    m = _REST.search(aus)
    return (_zahl(m.group(1)) if m else -1), aus


def abarbeiten(name: str, modul: str, stunden: float, limit: int) -> int:
    ende = time.time() + stunden * 3600
    runde, vorher = 0, None
    print(f"\n══ {name} ({modul}) — bis zu {stunden:g} h, {limit} je Runde")
    while time.time() < ende:
        runde += 1
        t0 = time.time()
        rest, aus = eine_runde(modul, limit)
        dauer = time.time() - t0

        if rest < 0:
            print(f"  Runde {runde}: kein Reststand gemeldet — Abrufer sagt:")
            for z in [z for z in aus.splitlines() if z.strip()][-4:]:
                print(f"      {z[:96]}")
            return 1

        geholt = (vorher - rest) if vorher is not None else 0
        tempo = geholt / (dauer / 60) if dauer > 30 else 0
        rest_h = (rest / tempo / 60) if tempo > 0 else None
        print(f"  Runde {runde:>3}: noch {rest:>6,} offen"
              + (f" · {geholt:>4} geschafft in {dauer/60:>5.1f} min" if vorher is not None else "")
              + (f" · {tempo:>5.1f}/min · Rest ~{rest_h:.1f} h" if rest_h else ""), flush=True)

        if rest == 0:
            print(f"  ✓ {name} ist leer.")
            return 0
        # KEIN FORTSCHRITT heisst aufhoeren, nicht weiterprobieren. Wenn eine Runde nichts
        # bewegt, liegt es am Portal (Sperre, Konto, alles dauerhaft aussichtslos) und
        # nicht daran, dass zu wenig Runden gelaufen sind. Weiterlaufen hiesse, dieselbe
        # Absage stundenlang zu wiederholen.
        if vorher is not None and rest >= vorher:
            print(f"  ⏹ keine Bewegung ({vorher:,} → {rest:,}) — hier ist Schluss.")
            for z in [z for z in aus.splitlines() if z.strip()][-3:]:
                print(f"      {z[:96]}")
            return 2
        vorher = rest
    print(f"  ⏱ Zeitgrenze von {stunden:g} h erreicht, noch {vorher or '?'} offen. "
          f"Erneut aufrufen setzt fort.")
    return 3


def main(argv=None) -> int:
    reg = abrufer()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--zeigen", action="store_true", help="verfügbare Abrufer auflisten")
    ap.add_argument("--connector", help=f"einer von: {', '.join(sorted(reg))}")
    ap.add_argument("--stunden", type=float, default=4.0)
    ap.add_argument("--limit", type=int, default=60, help="Vorgänge je Runde")
    ap.add_argument("--trotzdem", action="store_true",
                    help="auch bei laufendem Tageslauf starten (nur wenn man weiss, warum)")
    a = ap.parse_args(argv)

    if a.zeigen or not a.connector:
        print("Dokument-Abrufer:")
        for k, m in sorted(reg.items()):
            print(f"  {k:<20} {m}")
        print("\n  scripts/rueckstau.py --connector <name> [--stunden 4] [--limit 60]")
        return 0

    if a.connector not in reg:
        print(f"Unbekannt: {a.connector}. Bekannt: {', '.join(sorted(reg))}", file=sys.stderr)
        return 1

    ok, grund = frei()
    if not ok and not a.trotzdem:
        print(f"⛔ {grund} — nicht gestartet. Mit --trotzdem erzwingen.", file=sys.stderr)
        return 75

    os.environ.setdefault("GOVISOR_VORGANG_FRIST", "480")
    return abarbeiten(a.connector, reg[a.connector], a.stunden, a.limit)


if __name__ == "__main__":
    raise SystemExit(main())
