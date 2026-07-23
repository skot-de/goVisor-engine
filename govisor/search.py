"""Stichwortsuche über Leads — lokal auf Parquet, ohne Index.

**Warum ohne Index.** Gemessen 2026-07-23 an 85.947 Leads + 140.568 Losen: ein
`ILIKE`-Scan über alle Freitextfelder braucht **~320 ms** (DuckDB, 4 Threads). Das ist
für die lokale Entwicklung schnell genug — und liefert **vollständige Teilstring-
Semantik**, also mehr als die Postgres-Volltextsuche im späteren Frontend:

| Suchwort | hier (`ILIKE`) | Supabase (`tsvector` + `:*`) |
|---|---:|---:|
| photovoltaik | 628 | 625 |
| wärmepumpe | 699 | 605 |
| großwärmepumpe | **15** | **0** |

Der letzte Fall ist der Punkt: Deutsch ist eine Kompositasprache, und der Postgres-
Stemmer zerlegt Komposita nicht. „Großwärmepumpe" findet dort selbst mit Präfix-Operator
niemand. Wer die Zahlen aus diesem Modul gegen die Supabase-Suche hält, vergleicht also
zwei verschiedene Verfahren — nicht zwei Datenstände. Details: `docs/volltextsuche.md`.

Gesucht wird über **vier** Felder, weil der Inhalt verteilt liegt (s. `docs/data-sources.md`,
„Wie viel Inhalt steht wirklich drin?"): `title`, `description` und je Los `lot_title`,
`lot_description`. Zwei Drittel des Freitexts stehen auf der Los-Ebene.

Rangfolge: Titeltreffer zuerst, dann Beschreibung, dann Los — sonst rankt eine Fussnote
in Los 37 gleichauf mit dem Titel.

    from govisor.search import search
    hits = search(cfg, "DE", "wärmepumpe", phase="open", limit=20)
"""
from __future__ import annotations

import duckdb

from .config import Config

# Felder in Rang-Reihenfolge: (Spalte, Tabelle, Rang). Rang 0 = bester Treffer.
_FIELDS = [("title", "e", 0), ("description", "e", 1),
           ("lot_title", "l", 2), ("lot_description", "l", 3)]


def _like_clause(terms: list[str]) -> tuple[str, list]:
    """UND-Verknüpfung über die Suchbegriffe, ODER über die vier Felder.

    Parametrisiert (`?`), nicht interpoliert — Suchbegriffe kommen vom Nutzer.
    """
    cols = [f"coalesce({tbl}.{col}, '')" for col, tbl, _ in _FIELDS]
    haystack = " || ' ' || ".join(cols)
    parts, params = [], []
    for t in terms:
        parts.append(f"{haystack} ILIKE ?")
        params.append(f"%{t}%")
    return " AND ".join(parts), params


def _rank_expr(terms: list[str]) -> tuple[str, list]:
    """Kleinster Feld-Rang, in dem ALLE Begriffe vorkommen (0 = Titel)."""
    cases, params = [], []
    for col, tbl, rank in _FIELDS:
        conds = " AND ".join([f"coalesce({tbl}.{col},'') ILIKE ?"] * 1 * len(terms))
        cases.append(f"WHEN {conds} THEN {rank}")
        params += [f"%{t}%" for t in terms]
    return "CASE " + " ".join(cases) + " ELSE 9 END", params


def search(cfg: Config, country: str, query: str, *, phase: str | None = None,
           nuts: str | None = None, contract_nature: str | None = None,
           value_band: str | None = None, limit: int = 50) -> list[tuple]:
    """Leads zu einem Suchbegriff, beste Treffer zuerst.

    `query` wird an Leerzeichen zerlegt; alle Teile müssen vorkommen (UND).
    `nuts` filtert per Präfix auf den **Leistungsort** (`market_nuts3`), nicht auf den
    Behördensitz — s. `build_lead_export`.
    """
    terms = [t for t in query.split() if t]
    if not terms:
        return []
    g = cfg.gold_dir / country
    E = (g / "lead_export.parquet").as_posix()
    L = (g / "lead_lot.parquet").as_posix()

    where, params = _like_clause(terms)
    rank_sql, rank_params = _rank_expr(terms)
    extra = []
    if phase:
        extra.append("e.phase = ?"); params.append(phase)
    if nuts:
        extra.append("e.market_nuts3 LIKE ?"); params.append(f"{nuts}%")
    if contract_nature:
        extra.append("e.contract_nature = ?"); params.append(contract_nature)
    if value_band:
        extra.append("e.value_band = ?"); params.append(value_band)
    cond = " AND ".join([where] + extra)

    con = duckdb.connect()
    con.execute("SET threads=4")
    # Rang-Parameter kommen VOR den WHERE-Parametern (SELECT steht vorne).
    rows = con.execute(f"""
        SELECT e.slug, e.title, e.buyer_name, e.value_eur, e.deadline_date,
               e.phase, e.market_region_name, e.n_lots,
               min({rank_sql}) AS feld_rang
          FROM read_parquet('{E}') e
          LEFT JOIN read_parquet('{L}') l ON l.lead_id = e.lead_id
         WHERE {cond}
         GROUP BY ALL
         ORDER BY feld_rang, e.deadline_date NULLS LAST
         LIMIT {int(limit)}
    """, rank_params + params).fetchall()
    con.close()
    return rows


def search_count(cfg: Config, country: str, query: str, **filters) -> int:
    """Trefferzahl ohne die Zeilen zu holen (für Facetten/Paging)."""
    terms = [t for t in query.split() if t]
    if not terms:
        return 0
    g = cfg.gold_dir / country
    E = (g / "lead_export.parquet").as_posix()
    L = (g / "lead_lot.parquet").as_posix()
    where, params = _like_clause(terms)
    extra = []
    for key, col in [("phase", "e.phase"), ("contract_nature", "e.contract_nature"),
                     ("value_band", "e.value_band")]:
        if filters.get(key):
            extra.append(f"{col} = ?"); params.append(filters[key])
    if filters.get("nuts"):
        extra.append("e.market_nuts3 LIKE ?"); params.append(f"{filters['nuts']}%")
    cond = " AND ".join([where] + extra)
    con = duckdb.connect()
    con.execute("SET threads=4")
    n = con.execute(f"""
        SELECT count(DISTINCT e.lead_id)
          FROM read_parquet('{E}') e
          LEFT JOIN read_parquet('{L}') l ON l.lead_id = e.lead_id
         WHERE {cond}""", params).fetchone()[0]
    con.close()
    return n
