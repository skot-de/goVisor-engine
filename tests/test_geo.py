"""Radius-Suche: dim_plz + lead_geo + Haversine-Query."""
import os

import pytest

from govisor import geo
from govisor.config import Config

pytest.importorskip("duckdb")
import duckdb  # noqa: E402

G = "data/gold/DE"
cfg = Config(countries=("DE",), data_dir="data")


def _has(name):
    return os.path.exists(f"{G}/{name}.parquet")


@pytest.mark.skipif(not _has("dim_plz"), reason="dim_plz nicht gebaut")
def test_geocode_muenchen_is_plausible():
    pt = geo.geocode_city(cfg, "DE", "München")
    assert pt is not None
    lat, lon = pt
    assert 48.0 < lat < 48.3 and 11.4 < lon < 11.8, f"München-Koordinate abwegig: {pt}"
    assert geo.geocode_city(cfg, "DE", "Nichtexistentortxyz") is None


@pytest.mark.skipif(not _has("lead_geo"), reason="lead_geo nicht gebaut")
def test_lead_geo_is_one_to_one_with_leads():
    con = duckdb.connect()
    dup = con.execute(
        f"SELECT count(*) - count(DISTINCT lead_id) FROM read_parquet('{G}/lead_geo.parquet')").fetchone()[0]
    assert dup == 0
    # geo_source ehrlich: 'none' MUSS ohne Koordinate sein (kein erfundener Punkt)
    leaked = con.execute(
        f"SELECT count(*) FROM read_parquet('{G}/lead_geo.parquet') "
        f"WHERE geo_source='none' AND lat IS NOT NULL").fetchone()[0]
    assert leaked == 0


@pytest.mark.skipif(not _has("lead_geo"), reason="lead_geo nicht gebaut")
def test_radius_count_is_monotone():
    pt = geo.geocode_city(cfg, "DE", "München")
    counts = [geo.radius_count(cfg, "DE", pt[0], pt[1], r) for r in (5, 10, 25, 50, 100)]
    assert counts == sorted(counts), f"Radius-Counts nicht monoton: {counts}"
    assert counts[0] > 0


@pytest.mark.skipif(not _has("lead_geo"), reason="lead_geo nicht gebaut")
def test_combined_radius_and_nuts_is_intersection():
    # Kombiniert (Radius UND NUTS) darf nie mehr treffen als jeder Einzelfilter.
    rad = len(geo.search(cfg, "DE", city="München", radius_km=25))
    nut = len(geo.search(cfg, "DE", nuts=["DE21"]))
    both = len(geo.search(cfg, "DE", city="München", radius_km=25, nuts=["DE21"]))
    assert both <= rad and both <= nut and both > 0


@pytest.mark.skipif(not _has("lead_geo"), reason="lead_geo nicht gebaut")
def test_nuts_prefix_hierarchy_and_no_radius():
    # Elternebene (DE21) enthält ≥ Kindebene (DE212).
    parent = len(geo.search(cfg, "DE", nuts=["DE21"]))
    child = len(geo.search(cfg, "DE", nuts=["DE212"]))
    assert parent >= child > 0
    # Ohne Radius: dist_km None, und jeder Treffer beginnt mit dem NUTS-Präfix.
    rows = geo.search(cfg, "DE", nuts=["DE212"], limit=50)
    assert all(d is None for *_, d in rows)
    assert all(str(nuts).startswith("DE212") for _, _, _, nuts, _, _ in rows)


@pytest.mark.skipif(not _has("lead_geo"), reason="lead_geo nicht gebaut")
def test_nuts_filter_rejects_injection():
    # Nicht-Code-Eingaben werden verworfen (kein SQL-Injection über NUTS).
    assert geo._nuts_clause(["DE21'; DROP TABLE"]) == ""
    assert geo._nuts_clause(["'; --"]) == ""


@pytest.mark.skipif(not _has("dim_nuts"), reason="dim_nuts nicht gebaut")
def test_nuts_autocomplete_finds_muenchen():
    rows = geo.nuts_autocomplete(cfg, "DE", "münch")
    codes = {c for c, *_ in rows}
    assert "DE212" in codes and "DE21H" in codes
    # Ebenen-Filter: nur Bundesland (Ebene 1)
    lvl1 = geo.nuts_autocomplete(cfg, "DE", "bayern", level=1)
    assert all(lv == 1 for _, _, lv, _ in lvl1)
    assert any(c == "DE2" for c, *_ in lvl1)


@pytest.mark.skipif(not (_has("dim_nuts") and _has("lead_geo")), reason="nicht gebaut")
def test_nuts_children_have_counts():
    kids = geo.nuts_children(cfg, "DE", "DE21")
    assert kids, "Oberbayern sollte Landkreise haben"
    assert all(lv == 3 and cnt >= 0 for _, _, lv, cnt in kids)
    assert any(c == "DE212" for c, *_ in kids)
    # nach Lead-Zahl absteigend sortiert
    counts = [cnt for *_, cnt in kids]
    assert counts == sorted(counts, reverse=True)
    assert geo.nuts_children(cfg, "DE", "'; DROP") == []   # Injection-Schutz


@pytest.mark.skipif(not _has("lead_geo"), reason="lead_geo nicht gebaut")
def test_performance_axis_is_a_distinct_signal():
    buyer = len(geo.search(cfg, "DE", nuts=["DE21"], axis="buyer"))
    perf = len(geo.search(cfg, "DE", nuts=["DE21"], axis="performance"))
    assert buyer > 0 and perf > 0
    # performance-Suche filtert auf perf_nuts und gibt diese zurück
    rows = geo.search(cfg, "DE", nuts=["DE212"], axis="performance", limit=20)
    assert all(str(n).startswith("DE212") for _, _, _, n, _, _ in rows)
    # Radius auf der performance-Achse liefert Treffer (grob, aber funktional)
    assert geo.search(cfg, "DE", city="München", radius_km=25, axis="performance")


@pytest.mark.skipif(not _has("lead_geo"), reason="lead_geo nicht gebaut")
def test_haversine_matches_known_distance():
    # München–Hamburg Luftlinie ~ 600 km — grobe Plausibilität der Formel.
    muc = geo.geocode_city(cfg, "DE", "München")
    ham = geo.geocode_city(cfg, "DE", "Hamburg")
    # Distanz München→Hamburg: Hamburg-Koordinaten als „Spalten"-Literale einsetzen.
    dist = geo._haversine(muc[0], muc[1], latcol=str(ham[0]), loncol=str(ham[1]))
    d = duckdb.connect().execute(f"SELECT {dist}").fetchone()[0]
    assert 560 < d < 640, f"München–Hamburg-Distanz unplausibel: {d:.0f} km"
