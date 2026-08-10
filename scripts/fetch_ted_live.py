"""TED **tagesaktuell** nachziehen — schließt die Lücke der Monatspakete.

TED veröffentlicht laufend, aber `packages/monthly/` erscheint erst nach Monatsende →
unser Bestand hinkte strukturell ~1 Monat nach. Ausgerechnet bei den hochwertigen
oberschwelligen Leads, wo Angebotsfristen zeitkritisch sind.

Dieses Script holt über die **TED Search API v3** (kein Auth) alle DE-Notices, die nach dem
letzten vollständigen Monatspaket erschienen sind, lädt je Notice das XML und schreibt sie
mit dem NORMALEN Parser ins Silber — als ``year=YYYY/YYYY-MM-live.parquet``.

**Verhältnis zu den Monatspaketen:** die Live-Datei ist eine Vorab-Ergänzung. Sobald das
echte Monatspaket ingested wird, entfernt ``silver.build_month`` die ``-live``-Datei desselben
Monats (das Paket ist die vollständige Wahrheit). So gibt es nie Dubletten.

Aufruf:  python scripts/fetch_ted_live.py [--since 2026-07-01] [--limit N] [--workers 8]
"""
import argparse
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from govisor import locales, model, normalize, schema  # noqa: E402
from govisor.config import Config  # noqa: E402

SEARCH = "https://api.ted.europa.eu/v3/notices/search"
NOTICE_XML = "https://ted.europa.eu/en/notice/{pub}/xml"
PAGE = 250


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def _curl(url, data=None, binary=False, timeout=60):
    cmd = ["curl", "-sS", "-L", "--max-time", str(timeout), url]
    if data is not None:
        cmd += ["-X", "POST", "-H", "Content-Type: application/json", "-d", json.dumps(data)]
    out = subprocess.run(cmd, capture_output=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode()[:150])
    return out.stdout if binary else out.stdout.decode("utf-8", "replace")


def _curl_json(url, data, tries=5):
    """Search-API mit Backoff — TED antwortet unter Last mit HTML (429) statt JSON."""
    for attempt in range(tries):
        text = _curl(url, data)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            time.sleep(2.0 * (2 ** attempt))
    raise RuntimeError("Search API liefert dauerhaft kein JSON (Rate-Limit?)")


BRONZE = Path("data/raw_live")   # Roh-XML je Notice — Verlustfreiheit + inkrementeller Cache


def _bronze_path(pub: str, ym: str) -> Path:
    return BRONZE / "DE" / ym / f"{pub}.xml"


LAND3 = {"DE": "DEU", "AT": "AUT", "CH": "CHE"}   # TED nutzt ISO-alpha-3


def list_notices(since: str, until: str, limit: int | None, country: str = "DE") -> list[str]:
    """Publikationsnummern aller Notices des Landes im Zeitraum (Search API, paginiert)."""
    q = (f"buyer-country={LAND3.get(country.upper(), 'DEU')} AND publication-date>={since.replace('-', '')} "
         f"AND publication-date<={until.replace('-', '')}")
    pubs, page = [], 1
    while True:
        d = _curl_json(SEARCH, {"query": q, "fields": ["publication-number"],
                                "limit": PAGE, "page": page})
        batch = [n.get("publication-number") for n in (d.get("notices") or [])]
        pubs += [p for p in batch if p]
        total = d.get("totalNoticeCount")
        if page == 1:
            log(f"  {total:,} Notices im Zeitraum {since}…{until}")
        if not batch or (limit and len(pubs) >= limit) or len(pubs) >= (total or 0):
            break
        page += 1
    return pubs[:limit] if limit else pubs


def main(since: str, until: str, limit: int | None, workers: int, country: str = "DE") -> int:
    cfg = Config(countries=(country,), data_dir="data")
    # Ohne Locale würden deutsche Heuristiken (Freemail-Domains, Bundes-Käufer,
    # Rechtsformen) auf fremde Daten angewandt — lieber ehrlich abbrechen. AT und CH
    # kommen bis dahin über ihre eigenen Connectoren (ingest-atverg / ingest-simap),
    # die den unterschwelligen Markt ohnehin besser abdecken als TED.
    if country not in locales.LOCALES:
        log(f"FEHLER: keine Locale für {country} — TED-Live ist bislang DE-only. "
            f"Für {country} den eigenen Connector nutzen.")
        return 0
    locales.use(country)
    log(f"TED-Live: suche {country}-Notices ab {since}")
    pubs = list_notices(since, until, limit, country)
    log(f"  {len(pubs):,} Notices zu holen")
    if not pubs:
        return 0

    by_month = defaultdict(lambda: {name: [] for name in model.TABLES})
    fails = 0

    def _fetch_xml(pub, tries=5):
        """Roh-XML holen — mit Bronze-Cache und Backoff (TED rate-limitet, HTTP 429).

        Das Roh-XML landet unter ``data/raw_live/DE/<YYYY-MM>/<pub>.xml``. Damit bleibt die
        **Verlustfreiheit** gewahrt (ein späterer Parser-Fix läuft über lokale Dateien statt
        13k neuer Requests) UND der tägliche Lauf wird idempotent: schon geholte Notices
        werden übersprungen.
        """
        ym_guess = since[:7]
        cached = _bronze_path(pub, ym_guess)
        if cached.exists() and cached.stat().st_size > 500:
            return cached.read_bytes()
        for attempt in range(tries):
            raw = _curl(NOTICE_XML.format(pub=pub), binary=True)
            head = raw[:400].lstrip()
            if head.startswith(b"<?xml") or b"TED_EXPORT" in head or b"Notice" in head:
                cached.parent.mkdir(parents=True, exist_ok=True)
                tmp = cached.with_suffix(".part")
                tmp.write_bytes(raw)
                tmp.replace(cached)                # atomar → nie halbe Dateien im Bronze
                return raw
            time.sleep(1.5 * (2 ** attempt))       # 429 → warten und erneut
        return None

    def work(pub):
        try:
            raw = _fetch_xml(pub)
            if raw is None:
                return pub, None, None
            # KANONISCHE ID — sonst schreibt der Live-Pfad `540447-2026`, während das
            # Monatsarchiv `540447_2026` schreibt. Genau dieser Drift ist 2026-07-29
            # schon einmal repariert worden (s. CLAUDE.md); er entsteht hier neu, weil
            # dieses Script Silber direkt schreibt und `silver.py` gar nicht durchläuft.
            return pub, schema.parse(raw, schema.normalize_notice_id(pub)), raw
        except Exception:
            return pub, None, None

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for pub, notice, raw in pool.map(work, pubs):
            done += 1
            if notice is None:
                fails += 1
                continue
            pd = notice.publication_date or since
            year, month = int(pd[:4]), int(pd[5:7])
            rows = normalize.rows(notice, raw, "DE", year, month)
            for table, table_rows in rows.items():
                by_month[(year, month)][table].extend(table_rows)
            if done % 500 == 0:
                log(f"    {done:,}/{len(pubs):,} geholt")

    written = 0
    for (year, month), buckets in sorted(by_month.items()):
        key = f"{year:04d}-{month:02d}"
        for table, table_schema in model.TABLES.items():
            base = cfg.silver_table_path(table, "DE", key)
            out = base.with_name(f"{key}-live.parquet")
            out.parent.mkdir(parents=True, exist_ok=True)
            arrow = pa.Table.from_pylist(buckets[table], schema=table_schema)
            tmp = out.with_suffix(".part")
            pq.write_table(arrow, tmp, compression="zstd")
            tmp.replace(out)
        n = len(buckets["notices"])
        written += n
        log(f"  {key}-live: {n:,} Notices")
    log(f"FERTIG: {written:,} Notices live ergänzt ({fails} Fehlschläge). Jetzt `gold` rebuilden.")
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="ab YYYY-MM-DD (Default: 1. des laufenden Monats)")
    ap.add_argument("--until", help="bis YYYY-MM-DD (Default: heute)")
    ap.add_argument("--limit", type=int, help="nur N Notices (zum Testen)")
    ap.add_argument("--workers", type=int, default=3,
                    help="TED rate-limitet — mehr als 3 provoziert HTTP 429")
    ap.add_argument("--country", default="DE", choices=("DE", "AT", "CH"),
                    help="Käuferland; TED liefert AT/CH über dieselbe API")
    a = ap.parse_args()
    today = time.strftime("%Y-%m-%d")
    main(a.since or today[:8] + "01", a.until or today, a.limit, a.workers, a.country)
