"""Handelsregister-Dump: Freshness-Wächter statt blindem Refresh.

**Befund (2026-07-23, gemessen):** Die Quelle
``https://daten.offeneregister.de/de_companies_ocdata.jsonl.bz2`` ist **eingefroren** —
``Last-Modified: 05 Feb 2019``, und unsere lokale Kopie ist damit **byte-identisch**
(260.455.433 B). Ein zyklischer Download wäre also dauerhaft ein No-Op und würde nur
vortäuschen, die Firmendaten blieben aktuell (Status/Geschäftsführer sind real ~7 Jahre alt).

Deshalb prüft dieser Job per **HEAD** (Größe + Last-Modified) und lädt **nur bei echter
Änderung** — dann atomar getauscht und der HR-Index-Cache invalidiert. Kostet im Normalfall
einen einzigen HTTP-Request. Falls OffeneRegister je wiederbelebt wird, ziehen wir es
automatisch nach.

**Für wirklich frische Registerdaten** führt kein Weg an einer kostenpflichtigen Quelle
vorbei (OpenRegister/handelsregister.ai) — das ist eine Geschäfts-, keine Technikentscheidung.

Aufruf:  python scripts/refresh_register.py [--force]
Exit 0 = unverändert oder erfolgreich getauscht, 1 = Fehler.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from govisor import locales  # noqa: E402

SOURCE = "https://daten.offeneregister.de/de_companies_ocdata.jsonl.bz2"
STATE = ROOT / "data" / "cache" / "register_fingerprint.json"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def _head(url):
    out = subprocess.run(["curl", "-sSI", "--max-time", "40", "-L", url],
                         capture_output=True, text=True)
    size = lastmod = None
    for line in out.stdout.splitlines():
        low = line.lower()
        if low.startswith("content-length:"):
            size = line.split(":", 1)[1].strip()
        elif low.startswith("last-modified:"):
            lastmod = line.split(":", 1)[1].strip()
    return size, lastmod


def main(force: bool) -> int:
    locales.use("DE")
    target = Path(str(locales.active().register_path))
    size, lastmod = _head(SOURCE)
    if size is None:
        log("HEAD lieferte keine Content-Length — Quelle nicht erreichbar?")
        return 1
    log(f"Quelle: {size} B, Last-Modified: {lastmod}")

    local_size = target.stat().st_size if target.exists() else None
    log(f"Lokal : {local_size} B  ({target})")

    try:
        prev = json.loads(STATE.read_text())
    except (FileNotFoundError, ValueError):
        prev = {}
    unchanged = (str(local_size) == size and prev.get("last_modified") in (None, lastmod))

    if unchanged and not force:
        log(f"UNVERÄNDERT — Registerdaten bleiben auf Stand {lastmod}. Kein Download.")
        log("  Hinweis: Status/Geschäftsführer altern weiter; für frische Daten "
            "braucht es eine kostenpflichtige Quelle.")
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({"size": size, "last_modified": lastmod,
                                     "checked": time.strftime("%Y-%m-%d")}))
        return 0

    log("ÄNDERUNG erkannt → lade neuen Dump …")
    tmp = target.with_suffix(".part")
    r = subprocess.run(["curl", "-sS", "--max-time", "1800", "-L", SOURCE, "-o", str(tmp)])
    if r.returncode != 0 or not tmp.exists() or tmp.stat().st_size < 1_000_000:
        log("Download fehlgeschlagen — lokale Datei bleibt unangetastet.")
        tmp.unlink(missing_ok=True)
        return 1
    # Plausibilität: muss als bz2 lesbar sein und JSONL enthalten (sonst nicht tauschen).
    try:
        import bz2
        with bz2.open(tmp, "rt", encoding="utf-8") as fh:
            rec = json.loads(next(fh))
        assert "company_number" in rec
    except Exception as exc:
        log(f"Neue Datei nicht plausibel ({exc}) — Tausch abgebrochen.")
        tmp.unlink(missing_ok=True)
        return 1
    tmp.replace(target)                      # atomar
    cache = ROOT / "data" / "cache" / "hr_index.parquet"
    if cache.exists():
        cache.unlink()                       # HR-Index neu bauen lassen (mtime-gated)
        log("  hr_index-Cache verworfen → wird beim nächsten Gold-Lauf neu gebaut")
    STATE.write_text(json.dumps({"size": size, "last_modified": lastmod,
                                 "checked": time.strftime("%Y-%m-%d")}))
    log(f"FERTIG: Register getauscht (Stand {lastmod}).")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="auch ohne Änderung neu laden")
    sys.exit(main(ap.parse_args().force))
