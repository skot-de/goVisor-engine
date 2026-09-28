"""Heruntergeladene Vergabeunterlagen auf Malware pruefen und Treffer quarantaenieren.

⚠ WARUM. Das Auslieferungs-Tor (`lead_dokumente.hole`) scannt eine Datei erst, wenn jemand
sie oeffnet. Dieser Lauf geht proaktiv ueber den ganzen Baum `data/docs/**/*.zip`, damit ein
infiziertes Archiv gar nicht erst liegen bleibt, bis es jemand anklickt. ClamAV entpackt ZIPs
selbst; gescannt wird also das Archiv als Ganzes.

Ein Treffer wird ueber `govisor.clamav.quarantaene` aus dem Datenbaum verschoben und
protokolliert (`data/quarantaene/`). Fehlt ClamAV, wird nichts gescannt und der Lauf sagt es
(Exit 0 — kein Fehler, nur nichts zu tun).

Gedacht fuer den Nachtlauf (nach dem Dokumentenabruf) und fuer den Aufruf von Hand::

    python3 scripts/scan_docs.py [--country DE] [--limit N] [--still]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor import clamav  # noqa: E402

DOCS = ROOT / "data" / "docs"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--country", default=None, help="nur ein Land, sonst alle")
    p.add_argument("--limit", type=int, default=0, help="hoechstens N Archive (0 = alle)")
    p.add_argument("--still", action="store_true")
    a = p.parse_args(argv)

    def sag(*x):
        if not a.still:
            print(*x)

    if not clamav.verfuegbar():
        sag("ClamAV nicht installiert — nichts gescannt. "
            "Installieren (brew install clamav) und `freshclam` laufen lassen.")
        return 0

    wurzel = DOCS / a.country if a.country else DOCS
    if not wurzel.exists():
        sag(f"kein Verzeichnis: {wurzel}")
        return 0

    archive = sorted(wurzel.rglob("*.zip"))
    if a.limit:
        archive = archive[: a.limit]

    geprueft = infiziert = ungeprueft = 0
    for zp in archive:
        urteil, sig = clamav.scan_datei(zp)
        geprueft += 1
        if urteil == clamav.INFIZIERT:
            infiziert += 1
            ziel = clamav.quarantaene(zp, sig)
            sag(f"  ⛔ INFIZIERT {zp.name}: {sig} → Quarantaene {ziel}")
        elif urteil == clamav.UNGEPRUEFT:
            ungeprueft += 1
            sag(f"  ⚠ ungeprueft {zp.name}: {sig}")

    sag(f"\n{geprueft} Archive gescannt · {infiziert} quarantaeniert · {ungeprueft} ungeprueft")
    # Ein Fund ist kein Fehler des Laufs — er ist der Zweck. Exit 0.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
