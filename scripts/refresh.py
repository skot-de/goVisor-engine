"""Regelmäßiger Refresh — für einen täglichen Cron/launchd-Job.

**Mehrquellen- und mehrländerfähig.** Der Lauf hat zwei Phasen:

  1. Je (Quelle × Land) Bronze/Silber auffrischen — jede Quelle weiß selbst, was „frisch"
     heißt (TED: laufendes + voriges Monatspaket via HEAD-Fingerprint; künftige Quellen:
     eigene Logik). Eine Quelle, die scheitert, bricht die anderen NICHT ab.
  2. Danach EIN gemeinsamer Gold-Rebuild + FK-Verifikation **je Land, aber nur für Länder
     mit frischem Silber** — Gold vereint alle Quellen eines Landes.

Neue Quelle hinzufügen = eine `refresh_*`-Funktion schreiben und in `SOURCES` eintragen.
Neues Land = in `COUNTRIES` ergänzen (und bei den Quellen, die es tragen, in `countries`).

TED liefert nur Monatspakete (`ted.europa.eu/packages/monthly/YYYY-MM`); das laufende Paket
wächst während des Monats → laufenden + vorigen Monat neu ziehen. Idempotent und robust:
fehlt das laufende Paket noch (Monatsanfang), wird der Fehler geloggt und weitergemacht.

**KEINE LLM-/API-Kosten** — die Nachfolge-Adjudikation (`scripts/succession_llm.py`) ist ein
separater, selteren Lauf; der Gold-Rebuild merged nur die gecachten Kanten.

Aufruf:  python scripts/refresh.py           (aus dem Repo-Root)
Exit 0 = alles sauber, 1 = Ingest-/Gold-/FK-Fehler (für den Scheduler auswertbar).
"""
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date
from typing import Callable

# Von überall lauffähig machen (Scheduler): Repo-Root auf den Pfad + als cwd, damit
# `from govisor …` importiert und `data/` relativ auflöst.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)

from govisor import bulk, silver, locales, verify  # noqa: E402
from govisor.ingest import ingest_month  # noqa: E402
from govisor.config import Config  # noqa: E402

# ------------------------------------------------------------------ Konfiguration
# Erweitern = hier eine Zeile. Länder gelten global; welche Quelle welches Land trägt,
# steht je Quelle in `Source.countries`.
COUNTRIES = ["DE"]                      # künftig z. B. ["DE", "AT", "FR"]


def log(m: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {m}", flush=True)


def prev_month(y: int, m: int) -> tuple[int, int]:
    return (y - 1, 12) if m == 1 else (y, m - 1)


# ------------------------------------------------------------------ Fingerprint-Cache
# Ein Cache-File, Schlüssel pro Quelle+Land+Monat namespaced (`ted:DE:2024-01`), damit
# mehrere Quellen/Länder sich nicht überschreiben.
FP_PATH = os.path.join("data", "cache", "ingest_fingerprints.json")


def _load_fp() -> dict:
    try:
        with open(FP_PATH) as fh:
            return json.load(fh)
    except (FileNotFoundError, ValueError):
        return {}


def _save_fp(fp: dict) -> None:
    os.makedirs(os.path.dirname(FP_PATH), exist_ok=True)
    with open(FP_PATH, "w") as fh:
        json.dump(fp, fh)


# ------------------------------------------------------------------ Quellen
# Vertrag einer Quelle: `refresh(cfg, country, fp) -> bool`. Frischt Bronze/Silber für
# das Land auf und gibt True zurück, wenn Silber verändert wurde (→ Gold-Rebuild nötig).
# Ausnahmen dürfen fliegen — main() fängt sie je Quelle ab und macht weiter.

def refresh_ted(cfg: Config, country: str, fp: dict) -> bool:
    """TED-Monatspakete: laufender Monat immer (wächst), Vormonat nur bei HEAD-Änderung."""
    today = date.today()
    cur = (today.year, today.month)
    months = [prev_month(*cur), cur]
    fresh: list[tuple[int, int]] = []

    log(f"  [ted/{country}] Ingest {[f'{y:04d}-{m:02d}' for y, m in months]}")
    for y, m in months:
        pkg = bulk.Package(y, m)
        key = f"ted:{country}:{pkg.key}"
        is_current = (y, m) == cur
        if not is_current:
            try:
                code, clen, lmod = bulk.head(pkg)
                if code in (403, 404, 410):
                    log(f"    {pkg.key}: HEAD {code} → übersprungen")
                    continue
                if code == 200 and fp.get(key) == f"{clen}|{lmod}":
                    log(f"    {pkg.key}: unverändert (HEAD) → Re-Download übersprungen")
                    continue
            except Exception as exc:
                log(f"    {pkg.key}: HEAD-Fehler ({exc}) → ingest zur Sicherheit")
        try:
            stats = ingest_month(cfg, pkg, force=True, evict=True)
            for c, s in sorted(stats.items()):
                log(f"    {pkg.key} {c}: {s.kept:,}/{s.scanned:,} behalten | {s.lots:,} Lose")
            fresh.append((y, m))
            if not is_current:
                try:
                    code, clen, lmod = bulk.head(pkg)
                    if code == 200:
                        fp[key] = f"{clen}|{lmod}"
                except Exception:
                    pass
        except Exception as exc:
            log(f"    {pkg.key}: übersprungen ({exc})")

    for y, m in fresh:
        key = f"{y:04d}-{m:02d}"
        n = silver.build_month(cfg, country, key, force=True)
        log(f"    Silber {key}: {n:,} Notices" if n >= 0 else f"    Silber {key}: kein Bronze")
    return bool(fresh)


def refresh_doe(cfg: Config, country: str, fp: dict) -> bool:
    """DÖE (oeffentlichevergabe.de) — unterschwellige Vergaben, eForms-DE.

    Laufenden + vorigen Monat als ``eforms.zip`` ziehen (idempotent, Notices sind
    versioniert), Silber neu bauen (nur ``de-*``). Fingerprint = ZIP-Größe je Monat,
    damit unveränderte Monate nicht neu geparst werden.
    """
    from govisor import doe

    today = date.today()
    cur = (today.year, today.month)
    months = [prev_month(*prev_month(*cur)), prev_month(*cur), cur]   # laufender + 2 vorige
    fresh = []
    for y, m in months:
        key = f"{y:04d}-{m:02d}"
        is_current = (y, m) == cur
        try:
            size = doe.fetch_month(cfg, key, country=country, force=is_current)
        except Exception as exc:
            log(f"  [doe/{country}] {key}: Download übersprungen ({exc})")
            continue
        if not size:
            continue
        fpkey = f"doe:{country}:{key}"
        if not is_current and fp.get(fpkey) == str(size):
            log(f"  [doe/{country}] {key}: unverändert (Größe) → übersprungen")
            continue
        n = silver.build_month_doe(cfg, key, force=True, country=country)
        if n >= 0:
            log(f"  [doe/{country}] {key}: {n:,} Notices (unterschwellig, Staging)")
            fresh.append(key)
            fp[fpkey] = str(size)
    if fresh:
        dedup = silver.consolidate_doe(cfg, country)   # Cross-Monat-Dedup ins Silber
        log(f"  [doe/{country}] konsolidiert auf {dedup:,} Notices")
    return bool(fresh)


def refresh_ted_live(cfg: Config, country: str, fp: dict) -> bool:
    """TED **tagesaktuell** — schließt die Lücke bis zum nächsten Monatspaket.

    Zieht über die TED-Search-API die DE-Notices des laufenden Monats. Der Bronze-Cache
    (``data/raw_live/``) macht den Lauf idempotent: schon geholte Notices werden übersprungen,
    ein Tageslauf holt real nur die ~500 neuen. Sobald das Monatspaket kommt, ersetzt
    ``silver.build_month`` die ``-live``-Datei (kein Dubletten-Risiko).
    """
    if country != "DE":                       # Search-API-Query ist derzeit DE-spezifisch
        return False
    from datetime import date as _date

    from scripts.fetch_ted_live import main as ted_live
    today = _date.today().isoformat()
    n = ted_live(today[:8] + "01", today, None, workers=3)
    log(f"  [ted_live/{country}] {n:,} Notices im laufenden Monat")
    return n > 0


def refresh_register(cfg: Config, country: str, fp: dict) -> bool:
    """Handelsregister-Dump: **selbst-drosselnder** Freshness-Check (max. alle 30 Tage).

    Die Quelle (OffeneRegister) ist seit 02/2019 eingefroren — ein täglicher Download wäre
    sinnlos und würde Aktualität vortäuschen. Der Check kostet einen HTTP-HEAD; getauscht
    (und damit `True` = Gold-Rebuild) wird nur bei echter Änderung.
    """
    if country != "DE":
        return False
    key = f"register:{country}:last_check"
    today = date.today().toordinal()
    last = int(fp.get(key, 0))
    if today - last < 30:
        return False                          # innerhalb des Intervalls: nichts tun
    fp[key] = str(today)
    from scripts.refresh_register import main as reg_main
    changed_before = os.path.getmtime(str(locales.active().register_path)) \
        if os.path.exists(str(locales.active().register_path)) else 0
    rc = reg_main(force=False)
    changed_after = os.path.getmtime(str(locales.active().register_path)) \
        if os.path.exists(str(locales.active().register_path)) else 0
    if rc != 0:
        log(f"  [register/{country}] Check fehlgeschlagen (rc={rc})")
        return False
    swapped = changed_after != changed_before
    log(f"  [register/{country}] {'NEU getauscht' if swapped else 'unverändert'}")
    return swapped


@dataclass
class Source:
    name: str
    refresh: Callable[[Config, str, dict], bool]   # -> True wenn Silber verändert
    countries: tuple[str, ...] = ("DE",)
    enabled: bool = True


# Registry — Reihenfolge = Ausführungsreihenfolge. Neue Quelle: Funktion + Zeile hier.
SOURCES = [
    Source("ted", refresh_ted, countries=("DE",), enabled=True),
    Source("ted_live", refresh_ted_live, countries=("DE",), enabled=True),
    Source("doe", refresh_doe, countries=("DE",), enabled=True),
    Source("register", refresh_register, countries=("DE",), enabled=True),
]


# ------------------------------------------------------------------ Orchestrierung
def main() -> int:
    fp = _load_fp()
    failed = False
    changed: set[str] = set()          # Länder mit frischem Silber → Gold-Rebuild nötig

    # Phase 1 — je Land alle aktiven Quellen auffrischen.
    for country in COUNTRIES:
        cfg = Config(countries=(country,), data_dir="data")
        if country in locales.LOCALES:
            locales.use(country)
        for src in SOURCES:
            if not src.enabled or country not in src.countries:
                continue
            log(f"QUELLE {src.name} / {country}")
            try:
                if src.refresh(cfg, country, fp):
                    changed.add(country)
            except Exception as exc:
                log(f"  [{src.name}/{country}] FEHLER: {exc}")
                failed = True
    _save_fp(fp)

    # Phase 2 — Gold-Rebuild + FK je Land, aber nur wo Silber frisch ist. Gold vereint
    # alle Quellen eines Landes, darum genau EIN Rebuild pro betroffenem Land.
    if not changed:
        log("PHASE 2 — keine frischen Daten, Gold unverändert")
    for country in sorted(changed):
        cfg = Config(countries=(country,), data_dir="data")
        log(f"PHASE 2 — Gold-Rebuild {country}")
        r = subprocess.run([sys.executable, "-m", "govisor.cli", "gold", "--country", country],
                           capture_output=True, text=True)
        print(r.stdout[-1800:], flush=True)
        if r.returncode != 0:
            log(f"  GOLD-FEHLER {country}: {r.stderr[-1200:]}")
            failed = True
            continue
        issues = verify.gold_integrity(cfg, country)
        if issues:
            log(f"  FK-VERSTÖSSE {country}: {issues}")
            failed = True
        else:
            log(f"  FK sauber {country}")

    log("REFRESH FERTIG — " + ("mit FEHLERN" if failed else "OK"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
