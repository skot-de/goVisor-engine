"""TED-CHE Historie ab 2016 — jahresweise, wiederaufnehmbar, für den Nachtlauf.

**Warum jahresweise.** Rund 90.000 Notices bei gemessenen ~0,5 s je Stück (TED antwortet ab
etwa drei Anfragen pro Sekunde mit HTTP 429) sind 12–15 Stunden. Ein einziger Aufruf über
den ganzen Zeitraum würde bei jedem Abbruch alles verwerfen; je Jahr bleibt der Fortschritt
erhalten.

**Wiederaufnahme.** Zwei Ebenen, beide ohne Zustandsdatei:
  1. `fetch_ted_live.py` cached jedes Roh-XML unter `data/raw_live/CH/<monat>/` — ein zweiter
     Lauf lädt nur, was fehlt. Auch ein Parser-Fix später braucht keine neuen Requests.
  2. Ein Jahr gilt hier als fertig, wenn seine Silber-Dateien existieren UND mindestens
     `MIN_ANTEIL` der laut TED-API erwarteten Notices enthalten. Nur „Datei da" wäre zu
     schwach — ein abgebrochenes Jahr hinterlässt eine halbe Datei.

**Warum die Search-API erst ab 2016.** Sie indiziert nicht weiter zurück (s. verify.py,
`API_COVERAGE_START`). 2016 ist keine Wahl, sondern die Untergrenze der Quelle.

Aufruf:  python scripts/backfill_ted_ch.py [--von 2016] [--bis 2026] [--neu-pruefen]
Fortschritt:  tail -f data/logs/backfill-ted-ch.log
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import verify  # noqa: E402  (Pfad muss zuerst stehen)

LOG_DIR = ROOT / "data" / "logs"
LOG = LOG_DIR / "backfill-ted-ch.log"
MIN_ANTEIL = 0.90        # ab hier gilt ein Jahr als vollständig genug


def log(msg: str) -> None:
    zeile = f"[{dt.datetime.now():%F %T}] {msg}"
    print(zeile, flush=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as fh:
        fh.write(zeile + "\n")


def vorhanden(jahr: int) -> int:
    """Wie viele CH-Notices dieses Jahres liegen bereits in Silber?"""
    import duckdb

    muster = f"data/silver/CH/notices/year={jahr}/*.parquet"
    try:
        con = duckdb.connect()
        n = con.execute(
            f"SELECT count(*) FROM read_parquet('{muster}', hive_partitioning=1) "
            f"WHERE schema_gen <> 'simap'").fetchone()[0]
        con.close()
        return int(n)
    except Exception:
        return 0


def erwartet(jahr: int) -> int | None:
    """Soll-Zahl laut TED-API — der einzige ehrliche Vollständigkeits-Maßstab."""
    gesamt = 0
    for monat in range(1, 13):
        n = verify.api_count(jahr, monat, country="CHE")
        if n is None:
            return None
        gesamt += n
        time.sleep(0.2)
    return gesamt


def hole_jahr(jahr: int) -> bool:
    heute = dt.date.today()
    bis = min(dt.date(jahr, 12, 31), heute)
    if dt.date(jahr, 1, 1) > heute:
        return True
    cmd = [sys.executable, "scripts/fetch_ted_live.py", "--country", "CH",
           "--since", f"{jahr}-01-01", "--until", bis.isoformat(), "--workers", "3"]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    for zeile in (p.stdout or "").splitlines()[-3:]:
        log(f"    {zeile}")
    if p.returncode != 0:
        log(f"    FEHLER (exit {p.returncode}): {(p.stderr or '')[-300:]}")
    return p.returncode == 0


def main(von: int, bis: int, neu_pruefen: bool) -> int:
    log(f"═══ TED-CHE Backfill {von}–{bis} ═══")
    fertig, uebersprungen = 0, 0
    for jahr in range(von, bis + 1):
        da = vorhanden(jahr)
        soll = erwartet(jahr)
        if soll and da >= soll * MIN_ANTEIL and not neu_pruefen:
            log(f"{jahr}: {da:,} von ~{soll:,} bereits da → übersprungen")
            uebersprungen += 1
            continue
        log(f"{jahr}: {da:,} da, ~{soll if soll else '?'} erwartet → hole")
        t0 = time.time()
        ok = hole_jahr(jahr)
        danach = vorhanden(jahr)
        quote = f"{100*danach/soll:.0f} %" if soll else "?"
        log(f"{jahr}: {'fertig' if ok else 'MIT FEHLER'} — {danach:,} Notices "
            f"({quote} des Solls) in {(time.time()-t0)/60:.0f} min")
        fertig += 1
    log(f"═══ Backfill beendet: {fertig} Jahre geholt, {uebersprungen} übersprungen ═══")
    log("Danach nötig: `gold --country CH` (bzw. CH-Brücke) und der Quellenabgleich "
        "`python3 -m govisor.dedupe --country CH --ab-jahr 2024 --alle-arten`.")
    return fertig


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--von", type=int, default=2016,
                    help="Startjahr (2016 = Untergrenze der TED-Search-API)")
    ap.add_argument("--bis", type=int, default=dt.date.today().year)
    ap.add_argument("--neu-pruefen", dest="neu_pruefen", action="store_true",
                    help="auch scheinbar vollständige Jahre erneut holen")
    a = ap.parse_args()
    sys.exit(0 if main(a.von, a.bis, a.neu_pruefen) >= 0 else 1)
