"""Stichwortsuche (`govisor.search`) — lokal auf Parquet, ohne Index."""
import os

import pytest

pytest.importorskip("duckdb")

from govisor.config import Config  # noqa: E402

G = "data/gold/DE"
pytestmark = pytest.mark.skipif(
    not os.path.exists(f"{G}/lead_export.parquet") or not os.path.exists(f"{G}/lead_lot.parquet"),
    reason="Gold nicht gebaut")


@pytest.fixture(scope="module")
def cfg():
    return Config(countries=("DE",), data_dir="data")


def test_finds_compound_words(cfg):
    """Teilstring-Semantik: Komposita mit dem Suchwort HINTEN muessen gefunden werden.

    Genau das kann die Postgres-Volltextsuche im Frontend nicht (der deutsche Stemmer
    zerlegt keine Komposita) — hier lokal ist es der Normalfall und der Grund, warum
    dieses Modul `ILIKE` statt eines Index nutzt.
    """
    from govisor.search import search_count
    assert search_count(cfg, "DE", "großwärmepumpe") > 0
    # Das Kompositum ist eine echte Teilmenge des Grundworts.
    assert search_count(cfg, "DE", "wärmepumpe") > search_count(cfg, "DE", "großwärmepumpe")


def test_searches_lot_level_too(cfg):
    """Zwei Drittel des Freitexts liegen auf der Los-Ebene — die Suche muss dort greifen."""
    from govisor.search import search_count
    import duckdb
    con = duckdb.connect()
    nur_lead = con.execute(
        f"SELECT count(*) FROM read_parquet('{G}/lead_export.parquet') "
        f"WHERE title ILIKE '%wärmepumpe%' OR description ILIKE '%wärmepumpe%'").fetchone()[0]
    assert search_count(cfg, "DE", "wärmepumpe") > nur_lead


def test_all_terms_must_match(cfg):
    """Mehrwortsuche ist UND, nicht ODER."""
    from govisor.search import search_count
    a = search_count(cfg, "DE", "photovoltaik")
    both = search_count(cfg, "DE", "photovoltaik dach")
    assert 0 < both < a


def test_title_hits_rank_first(cfg):
    """Ein Treffer im Titel muss vor einem in einer Los-Fussnote stehen."""
    from govisor.search import search
    rows = search(cfg, "DE", "wärmepumpe", limit=25)
    ranks = [r[-1] for r in rows]
    assert ranks == sorted(ranks), "Feld-Rang muss aufsteigend sortiert sein"
    assert ranks[0] == 0, "bester Treffer sollte ein Titeltreffer sein"


def test_filters_narrow_the_result(cfg):
    from govisor.search import search_count
    total = search_count(cfg, "DE", "wärmepumpe")
    offen = search_count(cfg, "DE", "wärmepumpe", phase="open")
    assert 0 < offen <= total


def test_query_is_parameterised_not_interpolated(cfg):
    """Suchbegriffe kommen vom Nutzer — ein Quote darf nichts kaputt machen."""
    from govisor.search import search_count
    assert search_count(cfg, "DE", "'; drop table x; --") == 0


def test_empty_query_returns_nothing(cfg):
    from govisor.search import search, search_count
    assert search(cfg, "DE", "   ") == []
    assert search_count(cfg, "DE", "") == 0
