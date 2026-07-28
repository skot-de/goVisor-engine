"""Quelle CH — simap.ch Downloader (Bronze).

Offene JSON-REST-API, kein Key/Login (Kontrakt: ``docs/quellen-simap-api.md``). Zwei Endpoints:
Such-Endpoint (Cursor-Paginierung über ``pagination.lastItem``) + Detail je Publikation.

**Bronze = rohes JSON je Monat als JSONL** (``data/raw_simap/<country>/YYYY-MM.jsonl``), eine Zeile
je Publikation ``{"summary": <such-obj>, "detail": <detail-obj|null>}``. Verlustfreiheit liegt wie
bei TED/DÖE in Bronze: ein Parser-Fix (Silber, Schritt 3) kostet einen Re-Run über die lokalen
JSONL, keinen erneuten Download. Monats-Bucket = ``base.publicationDate`` (bzw. ``publicationDate``
aus der Trefferliste).

Idempotent: pro Monat wird mit vorhandenem File gemerged, dedupliziert über ``publicationId``.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

from .config import Config

BASE = "https://www.simap.ch"
SEARCH = BASE + "/rest/publications/v2/project/project-search"
DETAIL = BASE + "/rest/publications/v1/project/{pid}/publication-details/{pubid}"
# Länder-Filter der Suche: false = auch Aufträge mit ausländischem Erfüllungsort (die CH-Stelle
# zählt trotzdem). Sprachen: alle, damit fr/it/de-Titel vollständig kommen.
_SEARCH_Q = {"lang": ["de", "fr", "it", "en"], "orderAddressCountryOnlySwitzerland": "false"}
_UA = "govisor-ingest/1.0 (public procurement research)"
_ctx: ssl.SSLContext | None = None


def _get(url: str) -> dict:
    """GET → JSON. Verifiziert; fällt bei Proxy-Cert (Dev-Maschine) auf unverifiziert zurück.

    Nur öffentliche Lesezugriffe, keine Secrets im Request → unverifizierter Fallback vertretbar.
    """
    global _ctx
    if _ctx is None:
        _ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ctx) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as e:
        # SSL-Verifikation scheitert auf Dev-Maschinen hinter einem Proxy mit eigenem Root-Cert
        # (der Fehler kommt als URLError mit SSLCertVerificationError als reason). Einmalig auf
        # unverifiziert umschalten und erneut versuchen — nur öffentliche Lesezugriffe.
        if not isinstance(getattr(e, "reason", None), ssl.SSLError):
            raise
        _ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=30, context=_ctx) as r:
            return json.loads(r.read().decode("utf-8"))


def _search_url(cursor: str | None) -> str:
    q = dict(_SEARCH_Q)
    if cursor:
        q["lastItem"] = cursor
    return SEARCH + "?" + urllib.parse.urlencode(q, doseq=True)


def _iter_projects(max_pages: int | None, delay: float):
    """Trefferliste seitenweise (neueste zuerst) über den lastItem-Cursor. Yieldet Projekte."""
    cursor: str | None = None
    seen_cursors: set[str] = set()
    pages = 0
    while max_pages is None or pages < max_pages:
        data = _get(_search_url(cursor))
        projects = data.get("projects") or []
        if not projects:
            break
        for p in projects:
            yield p
        pages += 1
        cursor = (data.get("pagination") or {}).get("lastItem")
        if not cursor or cursor in seen_cursors:
            break                       # Ende (kein/looping Cursor)
        seen_cursors.add(cursor)
        if delay:
            time.sleep(delay)


def _month_of(p: dict) -> str:
    d = p.get("publicationDate") or ""
    return d[:7] if len(d) >= 7 else "unknown"


def _raw_dir(cfg: Config, country: str) -> Path:
    return cfg.data_dir / "raw_simap" / country


def _merge_month(path: Path, records: list[dict], force: bool) -> int:
    """JSONL je Monat schreiben, dedupliziert über publicationId (neuer Satz gewinnt).

    ``force`` überschreibt das Monatsfile komplett; sonst wird mit dem Bestand gemerged.
    """
    by_id: dict[str, dict] = {}
    if path.exists() and not force:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                by_id[r["summary"]["publicationId"]] = r
            except Exception:
                continue
    for r in records:
        by_id[r["summary"]["publicationId"]] = r
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in by_id.values():
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return len(by_id)


def download(cfg: Config, country: str = "CH", max_pages: int | None = None,
             delay: float = 0.15, force: bool = False) -> int:
    """simap.ch → Bronze. Gibt die Zahl frisch geholter Publikationen zurück.

    ``max_pages`` begrenzt den Lauf (je Seite 20; None = ganze Historie, neueste zuerst).
    Für jede Publikation wird die Detailseite geholt (schlägt sie fehl, bleibt ``detail=None`` —
    die Trefferliste allein trägt schon Kern-Lead + Geo).
    """
    buckets: dict[str, list[dict]] = defaultdict(list)
    n_detail_ok = n_total = 0
    for p in _iter_projects(max_pages, delay):
        n_total += 1
        detail = None
        try:
            detail = _get(DETAIL.format(pid=p["id"], pubid=p["publicationId"]) + "?lang=de")
            n_detail_ok += 1
        except Exception:
            pass
        buckets[_month_of(p)].append({"summary": p, "detail": detail})
        if delay:
            time.sleep(delay)
    for month, records in buckets.items():
        total = _merge_month(_raw_dir(cfg, country) / f"{month}.jsonl", records, force)
        print(f"  {country} {month}: +{len(records)} → {total} gesamt")
    print(f"simap {country}: {n_total} Publikationen geladen "
          f"({n_detail_ok} mit Detail), {len(buckets)} Monate")
    return n_total


def available_months(cfg: Config, country: str = "CH") -> list[str]:
    d = _raw_dir(cfg, country)
    return sorted(p.stem for p in d.glob("*.jsonl")) if d.exists() else []
