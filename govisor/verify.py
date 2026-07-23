"""Vollständigkeitsprüfung gegen eine unabhängige Referenz.

Monate untereinander zu vergleichen findet nur Ausreißer. Fehlen in *jedem*
Monat 10.000 Notices, ist die Kurve glatt und plausibel — und falsch. Deshalb
prüfen wir gegen die TED Search API, die unabhängig zählt, wie viele Notices
ein Monat hat.

Kalibriert an DE 2023-06: die API meldet 69.655 Notices für alle Länder, das
Paket enthält exakt 69.655. Für DE meldet sie 13.720, unser Bronze hält 13.716
— die Differenz von 4 stammt aus Notices, deren Länderzuordnung wir anders
lesen (die API nutzt `buyer-country`, wir das `ISO_COUNTRY` der Notice).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import requests

from . import bulk
from .config import Config

def gold_integrity(cfg: Config, country: str = "DE") -> list[tuple[str, int]]:
    """Referenz-Integrität der Gold-Tabellen — jeder FK muss auflösen.

    Der Fall, der das nötig macht: ``build_entities`` schreibt ``entities`` und
    ``party_entity`` nacheinander. Stirbt der Prozess dazwischen (z. B. RAM),
    zeigt ``party_entity`` auf entity_ids, die es in ``entities`` nicht mehr gibt
    — Waisen, die Leads still verschwinden lassen. Jeder Rebuild muss hier 0
    liefern. Gibt (Beschreibung, Anzahl) je Verstoß zurück (leer = sauber).
    """
    import duckdb

    g = cfg.gold_dir / country
    def q(path):
        return f"'{(g / path).as_posix()}'"
    # (Beschreibung, Kind-Tabelle, Kind-Spalte, Eltern-Tabelle, Eltern-Spalte)
    checks = [
        ("party_entity → entities", "party_entity.parquet", "entity_id", "entities.parquet", "entity_id"),
        ("leads.buyer_entity → entities", "leads.parquet", "buyer_entity", "entities.parquet", "entity_id"),
        ("leads.incumbent_entity → entities", "leads.parquet", "incumbent_entity", "entities.parquet", "entity_id"),
        ("leads.lead_id → quality", "leads.parquet", "lead_id", "quality.parquet", "notice_id"),
        ("contract_chains.incumbent → entities", "contract_chains.parquet", "incumbent", "entities.parquet", "entity_id"),
        ("buyer_stats.buyer → entities", "buyer_stats.parquet", "buyer_entity_id", "entities.parquet", "entity_id"),
        ("contractor_stats.entity → entities", "contractor_stats.parquet", "entity_id", "entities.parquet", "entity_id"),
        ("buyer_contractor_history.contractor → entities", "buyer_contractor_history.parquet", "contractor_entity_id", "entities.parquet", "entity_id"),
        ("contract_succession.successor → quality", "contract_succession.parquet", "successor", "quality.parquet", "notice_id"),
        ("contract_succession.predecessor → quality", "contract_succession.parquet", "predecessor", "quality.parquet", "notice_id"),
        ("award_tender_link.award → quality", "award_tender_link.parquet", "award_notice_id", "quality.parquet", "notice_id"),
        ("award_tender_link.tender → quality", "award_tender_link.parquet", "tender_notice_id", "quality.parquet", "notice_id"),
        ("value_anchor.notice → quality", "value_anchor.parquet", "notice_id", "quality.parquet", "notice_id"),
        ("lead_deadline.notice → quality", "lead_deadline.parquet", "notice_id", "quality.parquet", "notice_id"),
        ("lead_duration.notice → quality", "lead_duration.parquet", "notice_id", "quality.parquet", "notice_id"),
        ("lead_detail.lead_id → leads", "lead_detail.parquet", "lead_id", "leads.parquet", "lead_id"),
        ("entity_identity.entity_id → entities", "entity_identity.parquet", "entity_id", "entities.parquet", "entity_id"),
        ("lead_geo.lead_id → leads", "lead_geo.parquet", "lead_id", "leads.parquet", "lead_id"),
        ("lead_export.lead_id → leads", "lead_export.parquet", "lead_id", "leads.parquet", "lead_id"),
        ("doe_buyer_profile.buyer_entity → entities", "doe_buyer_profile.parquet", "buyer_entity",
         "entities.parquet", "entity_id"),
        ("buyer_profile.buyer_entity → entities", "buyer_profile.parquet", "buyer_entity",
         "entities.parquet", "entity_id"),
        ("buyer_recent_awards.lead_id → leads", "buyer_recent_awards.parquet", "lead_id",
         "leads.parquet", "lead_id"),
    ]
    con = duckdb.connect()
    out: list[tuple[str, int]] = []
    for label, child, ckey, parent, pkey in checks:
        if not (g / child).exists() or not (g / parent).exists():
            continue
        n = con.execute(
            f"SELECT count(*) FROM {q(child)} c "
            f"LEFT JOIN {q(parent)} p ON p.{pkey}=c.{ckey} "
            f"WHERE c.{ckey} IS NOT NULL AND p.{pkey} IS NULL"
        ).fetchone()[0]
        if n:
            out.append((label, n))
    con.close()
    return out


API_URL = "https://api.ted.europa.eu/v3/notices/search"
# Die Search API indiziert erst ab 2016, und 2016 nur teilweise.
API_COVERAGE_START = (2016, 1)

_MONTH_END = {1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30,
              7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}


@dataclass
class MonthCheck:
    key: str
    bronze_notices: int | None = None     # tatsächlich gelesen, nicht aus dem Log
    bronze_readable: bool | None = None
    api_country: int | None = None
    api_total: int | None = None
    error: str | None = None

    @property
    def delta(self) -> int | None:
        if self.bronze_notices is None or self.api_country is None:
            return None
        return self.bronze_notices - self.api_country

    @property
    def delta_pct(self) -> float | None:
        if self.delta is None or not self.api_country:
            return None
        return 100.0 * self.delta / self.api_country


def api_count(year: int, month: int, country: str | None = None,
              attempts: int = 3) -> int | None:
    """Wie viele Notices hat TED für diesen Monat? None, wenn nicht abfragbar."""
    end = _MONTH_END[month]
    query = f"publication-date>={year}{month:02d}01 AND publication-date<={year}{month:02d}{end}"
    if country:
        query += f" AND buyer-country={country}"
    for attempt in range(attempts):
        try:
            response = requests.post(
                API_URL,
                json={"query": query, "fields": ["publication-number"], "limit": 1},
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=90,
            )
            if response.status_code == 200:
                return response.json().get("totalNoticeCount")
        except requests.RequestException:
            pass
        time.sleep(3 * (attempt + 1))
    return None


def count_bronze(path: Path) -> tuple[int | None, bool, str | None]:
    """Notices im Archiv zählen, indem es komplett gelesen wird.

    Kein Blick auf die Dateigröße: ein abgeschnittenes Archiv hat eine
    plausible Größe. Nur der vollständige Durchlauf beweist Lesbarkeit.
    """
    if not path.exists():
        return None, False, "fehlt"
    try:
        return sum(1 for _ in bulk.iter_notices(path)), True, None
    except Exception as exc:
        return None, False, f"{type(exc).__name__}: {exc}"


def check_month(cfg: Config, country: str, key: str, with_api: bool = True) -> MonthCheck:
    year, month = (int(p) for p in key.split("-"))
    check = MonthCheck(key=key)
    check.bronze_notices, check.bronze_readable, check.error = count_bronze(
        cfg.raw_path(country, key)
    )
    if with_api and (year, month) >= API_COVERAGE_START:
        alpha3 = _alpha3(country)
        check.api_country = api_count(year, month, alpha3)
        check.api_total = api_count(year, month)
    return check


def _alpha3(country: str) -> str:
    from . import countries
    return countries.resolve(country).alpha3
