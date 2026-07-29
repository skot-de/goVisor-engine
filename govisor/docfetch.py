"""Dokument-Fetcher für cosinex/DTVP-Portale — login-frei, §41 VgV.

Holt die **Vergabeunterlagen** (das ZIP mit Leistungsbeschreibung, Vertragsbedingungen,
Formblättern …) von cosinex-Vergabemarktplatz-Portalen, **ohne Registrierung/Login**. cosinex
betreibt ~32 % der DE-Dokument-Links (dtvp.de + viele Landes-/Kommunalportale unter
``/Satellite/`` bzw. ``/VMPSatellite/``) — ein Fetcher deckt sie alle ab.

**Reverse-engineert + validiert** (2026-07-29) an echten offenen Ausschreibungen:

* Die ``documents_url`` (``…/Satellite/notice/<CX>/documents``) ist eine Landingpage; der Aufruf
  setzt per 302 ein **Session-Cookie** und landet auf ``…/public/company/project/<CX>/de/overview``.
* Die Seite zeigt zwar „Um Zugriff auf dieses Modul zu erhalten müssen Sie am Verfahren teilnehmen"
  — das gilt aber nur für **Kommunikation/Angebotsabgabe**. Die Unterlagen selbst hängen an einem
  **öffentlichen Archiv-Endpoint**, der mit dem Session-Cookie **anonym** ein echtes ZIP liefert:

      <host>/<base>/public/company/project/<CX>/de/documents/archive/Vergabeunterlagen_<CX>.zip

  (``<base>`` = ``Satellite`` oder ``VMPSatellite``, je Portal.) Verifiziert: HTTP 200,
  ``application/zip``, mehrere PDFs (Leistungsbeschreibung etc.).

**Höflich by design:** nur URLs, die wir ohnehin haben (kein Crawlen); Rate-Limit zwischen
Requests; idempotent (bereits geladene Vorgänge werden übersprungen); gegatete/leere Vorgänge
werden geflaggt, nicht als Fehler behandelt. CAPTCHA/Anti-Bot → sauberer Abbruch für den Vorgang
(fällt dann in den „du lieferst"-Pfad).

Speicher-Layout: ``<data>/docs/<country>/<notice_id>/Vergabeunterlagen_<CX>.zip`` + ein Manifest
``<data>/docs/<country>/_manifest.parquet`` (notice_id, cx, portal, status, bytes, n_files, ts).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import requests

from .config import Config

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120 Safari/537.36")
# cosinex-URL: Host + Base (Satellite|VMPSatellite) + CX-Projekt-ID aus notice/<CX> oder project/<CX>.
_COSINEX_RE = re.compile(
    r"^(?P<origin>https?://[^/]+)/(?P<base>V?MPSatellite|Satellite)/"
    r"(?:public/company/project|notice)/(?P<cx>[A-Z0-9]+)", re.I)


def is_cosinex(url: str) -> bool:
    return bool(url and _COSINEX_RE.match(url))


@dataclass
class FetchResult:
    notice_id: str
    cx: str | None
    portal: str | None
    status: str          # "downloaded" | "exists" | "gated" | "empty" | "error"
    bytes: int
    n_files: int
    path: str | None
    note: str = ""


def _zip_url(origin: str, base: str, cx: str) -> str:
    return (f"{origin}/{base}/public/company/project/{cx}/de/documents/"
            f"archive/Vergabeunterlagen_{cx}.zip")


def fetch_one(documents_url: str, notice_id: str, out_root: Path,
              session: requests.Session | None = None, timeout: int = 60) -> FetchResult:
    """Ein cosinex-Vorgang → Vergabeunterlagen-ZIP auf die Platte. Idempotent."""
    import zipfile

    m = _COSINEX_RE.match(documents_url or "")
    if not m:
        return FetchResult(notice_id, None, None, "error", 0, 0, None, "keine cosinex-URL")
    origin, base, cx = m.group("origin"), m.group("base"), m.group("cx")
    portal = origin.split("//", 1)[-1]
    dest_dir = out_root / notice_id
    dest = dest_dir / f"Vergabeunterlagen_{cx}.zip"
    if dest.exists() and dest.stat().st_size > 0:
        return FetchResult(notice_id, cx, portal, "exists", dest.stat().st_size, 0, str(dest))

    s = session or requests.Session()
    s.headers.update({"User-Agent": _UA, "Accept-Language": "de-DE,de;q=0.9"})
    try:
        # 1) Session-Cookie setzen (Landingpage besuchen).
        s.get(f"{origin}/{base}/notice/{cx}/documents", timeout=timeout, allow_redirects=True)
        # 2) Archiv-ZIP anonym ziehen.
        r = s.get(_zip_url(origin, base, cx), timeout=timeout, allow_redirects=True)
    except requests.RequestException as e:
        return FetchResult(notice_id, cx, portal, "error", 0, 0, None, f"{type(e).__name__}: {e}"[:150])

    ctype = r.headers.get("content-type", "").lower()
    if r.status_code != 200 or "zip" not in ctype:
        # kein ZIP → gegated (Teilnahme/Login) oder nicht (mehr) verfügbar.
        note = f"http {r.status_code}, {ctype[:40]}"
        return FetchResult(notice_id, cx, portal, "gated", 0, 0, None, note)
    if not r.content or len(r.content) < 64:
        return FetchResult(notice_id, cx, portal, "empty", len(r.content or b""), 0, None)

    dest_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(r.content)
    # Integrität + Dateizahl prüfen.
    try:
        with zipfile.ZipFile(tmp) as z:
            n_files = sum(1 for i in z.infolist() if not i.is_dir())
    except zipfile.BadZipFile:
        tmp.unlink(missing_ok=True)
        return FetchResult(notice_id, cx, portal, "error", len(r.content), 0, None, "defektes ZIP")
    tmp.replace(dest)
    return FetchResult(notice_id, cx, portal, "downloaded", dest.stat().st_size, n_files, str(dest))


def fetch_batch(cfg: Config, country: str = "DE", limit: int | None = None,
                delay: float = 1.5) -> dict:
    """Alle offenen Leads mit cosinex-``documents_url`` → Unterlagen ziehen (höflich, idempotent).

    Liest ``gold/<country>/lead_export.parquet``, filtert auf cosinex-Vorgänge, lädt je Vorgang das
    ZIP mit ``delay`` s Pause. Schreibt Manifest. Gibt eine Status-Zusammenfassung zurück.
    """
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq

    G = cfg.gold_dir / country
    out_root = cfg.data_dir / "docs" / country
    out_root.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    rows = con.execute(
        f"""SELECT lead_id, documents_url FROM read_parquet('{(G / 'lead_export.parquet').as_posix()}')
            WHERE phase='open' AND documents_url IS NOT NULL
              AND regexp_matches(documents_url, '/(V?MP)?Satellite/')
            ORDER BY deadline_date DESC NULLS LAST""").fetchall()
    if limit:
        rows = rows[:limit]

    s = requests.Session()
    results: list[FetchResult] = []
    counts: dict[str, int] = {}
    for i, (lead_id, url) in enumerate(rows, 1):
        res = fetch_one(url, lead_id, out_root, session=s)
        results.append(res)
        counts[res.status] = counts.get(res.status, 0) + 1
        if res.status in ("downloaded", "exists"):
            tag = f"{res.n_files} Dateien" if res.status == "downloaded" else "vorhanden"
            print(f"  [{i}/{len(rows)}] {res.status:10} {lead_id}  {res.bytes/1024:.0f} KB  {tag}", flush=True)
        else:
            print(f"  [{i}/{len(rows)}] {res.status:10} {lead_id}  ({res.note})", flush=True)
        if res.status == "downloaded" and delay:
            time.sleep(delay)   # nur nach echtem Download drosseln

    if results:
        pq.write_table(pa.Table.from_pylist([asdict(r) for r in results]),
                       out_root / "_manifest.parquet", compression="zstd")
    total_mb = sum(r.bytes for r in results if r.status == "downloaded") / 1e6
    print(f"\ncosinex-Fetch {country}: {len(rows)} Vorgänge | " +
          " | ".join(f"{k}={v}" for k, v in sorted(counts.items())) +
          f" | {total_mb:.1f} MB neu")
    return {"total": len(rows), "counts": counts, "mb": round(total_mb, 1)}
