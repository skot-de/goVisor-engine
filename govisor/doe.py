"""DÖE — Datenservice Öffentlicher Einkauf (oeffentlichevergabe.de).

Bezug der eForms-Monatspakete (Bronze) für die **unterschwellige** zweite Lead-Quelle.
CC0-Lizenz, keine Auth. Endpunkt::

    GET /api/notice-exports?pubMonth=YYYY-MM&format=eforms.zip     (auch pubDay=YYYY-MM-DD)

Lädt nach ``data/raw_doe/<country>/<key>.eforms.zip``. Das Parsen/Filtern (nur ``de-*``)
macht ``silver.build_month_doe``. Hintergrund/Messung: ``docs/spike-doe-datenquelle.md``.
Nutzt ``requests`` (certifi-CA) wie ``bulk.py`` — urllib scheitert hier am SSL-Cert.
"""
from __future__ import annotations

import requests

from .config import Config

_API = "https://oeffentlichevergabe.de/api/notice-exports"
_HEADERS = {"User-Agent": "govisor/1.0 (+lead-intelligence)"}


def fetch_month(cfg: Config, key: str, country: str = "DE", force: bool = False) -> int:
    """Lädt den DÖE-Monat als eForms-ZIP nach ``raw_doe/``. Gibt die Bytegröße zurück
    (0 = leeres/fehlendes Paket). Idempotent: vorhandene Datei wird ohne ``force`` behalten.
    Das laufende Monatspaket wächst — dafür ``force=True`` übergeben.
    """
    dest = cfg.data_dir / "raw_doe" / country / f"{key}.eforms.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1000 and not force:
        return dest.stat().st_size
    tmp = dest.with_suffix(".part")
    with requests.get(_API, params={"pubMonth": key, "format": "eforms.zip"},
                      headers=_HEADERS, stream=True, timeout=600) as r:
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} für {key}")
        with open(tmp, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
    if tmp.stat().st_size <= 1000:                 # leerer/ungültiger Monat
        tmp.unlink()
        return 0
    tmp.replace(dest)
    return dest.stat().st_size
