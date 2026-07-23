"""Radius-Suche: Stadt/Koordinate → Leads im Umkreis.

Haversine-Distanz über ``lead_geo`` (Geo-Koordinate je Lead, aus ``build_lead_geo``).
Der Sucheinstieg ist ein Stadtname → Koordinate (``geocode_city`` über ``dim_plz``),
danach ein reiner Distanzfilter. Bei ~74k Leads ist das trivial schnell; für viel
größere Bestände wäre eine Bounding-Box-Vorfilterung (lat/lon ± r/111 km) oder PostGIS
der nächste Schritt.
"""
from __future__ import annotations

import duckdb

from .config import Config

# Achsen: 'buyer' (feine PLZ-Koordinate, buyer_nuts) vs 'performance' (Leistungsort,
# NUTS-3-grober Zentroid, performance_nuts). Spaltennamen je Achse:
_AXIS = {"buyer": ("lat", "lon", "nuts"), "performance": ("perf_lat", "perf_lon", "perf_nuts")}


def _haversine(lat: float, lon: float, latcol: str = "lat", loncol: str = "lon") -> str:
    """Haversine-Distanz (km) zwischen Suchpunkt (lat/lon, Konstante) und Lead-Spalten."""
    return (
        f"2 * 6371 * asin(sqrt("
        f"pow(sin(radians({latcol} - {lat}) / 2), 2) + "
        f"cos(radians({lat})) * cos(radians({latcol})) * pow(sin(radians({loncol} - {lon}) / 2), 2)))"
    )


def geocode_city(cfg: Config, country: str, city: str) -> tuple[float, float] | None:
    """Stadtname → (lat, lon) als Zentroid der zugehörigen PLZ. None, wenn unbekannt."""
    g = cfg.gold_dir / country
    con = duckdb.connect()
    r = con.execute(
        f"SELECT avg(lat), avg(lon) FROM read_parquet('{(g / 'dim_plz.parquet').as_posix()}') "
        f"WHERE lower(ort) = lower(?)", [city]).fetchone()
    con.close()
    return (round(r[0], 5), round(r[1], 5)) if r and r[0] is not None else None


def radius_search(cfg: Config, country: str, lat: float, lon: float,
                  radius_km: float, limit: int | None = None) -> list[tuple]:
    """Leads im Umkreis ``radius_km`` um (lat, lon), nach Distanz sortiert.

    Rückgabe: (lead_id, ort, plz, geo_source, dist_km). ``geo_source`` sagt ehrlich,
    ob die Lead-Koordinate aus PLZ (fein) oder nur Ort (grob) stammt.
    """
    g = cfg.gold_dir / country
    dist = _haversine(lat, lon)
    con = duckdb.connect()
    q = (f"SELECT lead_id, ort, plz, geo_source, round({dist}, 1) AS dist_km "
         f"FROM read_parquet('{(g / 'lead_geo.parquet').as_posix()}') "
         f"WHERE lat IS NOT NULL AND {dist} <= {radius_km} ORDER BY dist_km")
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = con.execute(q).fetchall()
    con.close()
    return rows


def radius_count(cfg: Config, country: str, lat: float, lon: float, radius_km: float) -> int:
    """Nur die Anzahl der Leads im Umkreis (für Facetten/Badges)."""
    g = cfg.gold_dir / country
    dist = _haversine(lat, lon)
    con = duckdb.connect()
    n = con.execute(
        f"SELECT count(*) FROM read_parquet('{(g / 'lead_geo.parquet').as_posix()}') "
        f"WHERE lat IS NOT NULL AND {dist} <= {radius_km}").fetchone()[0]
    con.close()
    return n


import re as _re

_NUTS_RE = _re.compile(r"^[A-Z]{2}[A-Z0-9]{0,3}$")   # DE / DE2 / DE21 / DE212


def _nuts_clause(nuts: list[str] | None, col: str = "nuts") -> str:
    """NUTS-Präfix-Filter (beliebige Ebene): Lead matcht, wenn ``col`` mit einem der
    Codes BEGINNT. Codes werden validiert (nur Buchstaben/Ziffern) — kein Injection-Risiko."""
    if not nuts:
        return ""
    codes = [c.strip().upper() for c in nuts if _NUTS_RE.match(c.strip().upper())]
    if not codes:
        return ""
    ors = " OR ".join(f"{col} LIKE '{c}%'" for c in codes)
    return f"({ors})"


def nuts_autocomplete(cfg: Config, country: str, query: str,
                      level: int | None = None, limit: int = 20) -> list[tuple]:
    """Regions-Autocomplete: Name-Substring → NUTS-Codes (§5.1 des NUTS-Tickets).

    Rückgabe: (nuts_code, name, level, parent). Optional auf eine Ebene beschränkt
    (0=Land, 1=Bundesland, 2=Regierungsbezirk, 3=Landkreis).
    """
    g = cfg.gold_dir / country
    dn = f"'{(g / 'dim_nuts.parquet').as_posix()}'"
    q = (f"SELECT nuts_code, name, level, parent FROM read_parquet({dn}) "
         f"WHERE lower(name) LIKE '%' || lower(?) || '%'")
    params: list = [query]
    if level is not None:
        q += " AND level = ?"
        params.append(int(level))
    q += " ORDER BY level, name LIMIT ?"
    params.append(int(limit))
    con = duckdb.connect()
    rows = con.execute(q, params).fetchall()
    con.close()
    return rows


def nuts_children(cfg: Config, country: str, parent: str) -> list[tuple]:
    """Direkte Unter-Regionen eines NUTS-Codes **mit Lead-Anzahl** (§5.2, Drill-down).

    Rückgabe: (nuts_code, name, level, lead_count) — lead_count zählt alle Leads,
    deren NUTS mit dem Code beginnt (hierarchisch).
    """
    if not _NUTS_RE.match((parent or "").strip().upper()):
        return []
    parent = parent.strip().upper()
    g = cfg.gold_dir / country
    dn = f"'{(g / 'dim_nuts.parquet').as_posix()}'"
    lg = f"'{(g / 'lead_geo.parquet').as_posix()}'"
    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT d.nuts_code, d.name, d.level,
               (SELECT count(*) FROM read_parquet({lg}) l WHERE l.nuts LIKE d.nuts_code || '%') AS lead_count
        FROM read_parquet({dn}) d
        WHERE d.parent = ? ORDER BY lead_count DESC, d.name
    """, [parent]).fetchall()
    con.close()
    return rows


def search(cfg: Config, country: str, *, city: str | None = None,
           lat: float | None = None, lon: float | None = None,
           radius_km: float | None = None, nuts: list[str] | None = None,
           axis: str = "buyer", limit: int | None = None) -> list[tuple]:
    """Kombinierte Standort-Suche: **Radius UND/ODER NUTS-Regionsfilter**.

    - ``city`` (+ ``radius_km``) oder direkt ``lat``/``lon`` (+ ``radius_km``) → Umkreis.
    - ``nuts`` = Liste von NUTS-Codes beliebiger Ebene (``['DE21']`` = Oberbayern,
      ``['DE212','DE21H']`` = zwei Landkreise) → Präfix-Match.
    - ``axis`` = **`'buyer'`** (Auftraggeber, feine PLZ-Koordinate, `nuts`) oder
      **`'performance'`** (Leistungsort — wo gearbeitet wird —, NUTS-3-grober Zentroid,
      `perf_nuts`). Radius auf `performance` ist Landkreis-grob (nur NUTS-3 vorhanden).
    Beide Filter sind UND-verknüpft; jeder ist optional. Rückgabe:
    (lead_id, ort, plz, nuts, geo_source, dist_km) — dist_km None ohne Radius; ``nuts``
    ist die Spalte der gewählten Achse.
    """
    latcol, loncol, nutscol = _AXIS.get(axis, _AXIS["buyer"])
    g = cfg.gold_dir / country
    lg = f"'{(g / 'lead_geo.parquet').as_posix()}'"
    where = []
    dist_expr = "NULL"
    if city and lat is None:
        pt = geocode_city(cfg, country, city)
        if pt is None:
            return []
        lat, lon = pt
    if lat is not None and lon is not None and radius_km is not None:
        dist_expr = _haversine(lat, lon, latcol, loncol)
        where.append(f"{latcol} IS NOT NULL AND {dist_expr} <= {radius_km}")
    nc = _nuts_clause(nuts, nutscol)
    if nc:
        where.append(nc)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    order = " ORDER BY dist_km" if dist_expr != "NULL" else " ORDER BY lead_id"
    con = duckdb.connect()
    q = (f"SELECT lead_id, ort, plz, {nutscol} AS nuts, geo_source, "
         f"CASE WHEN {dist_expr} IS NULL THEN NULL ELSE round({dist_expr},1) END AS dist_km "
         f"FROM read_parquet({lg}){clause}{order}")
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = con.execute(q).fetchall()
    con.close()
    return rows
