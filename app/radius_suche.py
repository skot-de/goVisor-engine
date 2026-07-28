"""goVisor — Umkreis- & Regionssuche (Namens-Autocomplete, lokal).

Tippe eine Stadt (Radius) und/oder eine Region (Name → NUTS-Autocomplete), wähle die
Achse (Auftraggeber vs. Leistungsort) — und sieh die Leads auf Karte + Liste.

Start:  streamlit run app/radius_suche.py
Liest direkt data/gold/DE/*.parquet + nutzt govisor.geo — kein Server.
"""
import sys
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor import geo  # noqa: E402
from govisor.config import Config  # noqa: E402

G = ROOT / "data" / "gold" / "DE"
LG = (G / "lead_geo.parquet").as_posix()
LD = (G / "lead_detail.parquet").as_posix()
cfg = Config(countries=("DE",), data_dir=str(ROOT / "data"))

st.set_page_config(page_title="goVisor — Umkreissuche", layout="wide")


def de_eur_band(b) -> str:
    return "—" if b is None or (isinstance(b, float) and pd.isna(b)) else str(b)


@st.cache_data
def autocomplete(query: str, level):
    if len(query.strip()) < 2:
        return []
    return geo.nuts_autocomplete(cfg, "DE", query.strip(), level=level, limit=25)


@st.cache_data
def geocode(city: str):
    return geo.geocode_city(cfg, "DE", city.strip()) if city.strip() else None


def run_query(lat, lon, radius_km, nuts_codes, axis):
    """Gibt (echte_anzahl, dataframe_gekappt) zurück — Karte/Liste zeigen max. 2000."""
    latcol, loncol, nutscol = geo._AXIS[axis]
    where = []
    dist_sel = "NULL"
    if lat is not None and radius_km:
        dist = geo._haversine(lat, lon, latcol, loncol)
        # dist_km NULL bei gesetztem Radius = bundesweit erbringbar (s. geo.nationwide_clause)
        dist_sel = f"CASE WHEN {dist} <= {radius_km} THEN round({dist}, 1) END"
        where.append(f"g.{latcol} IS NOT NULL AND {dist} <= {radius_km}")
    nc = geo._nuts_clause(nuts_codes, f"g.{nutscol}")
    if nc:
        where.append(nc)
    # Ortsunabhaengige Leistungen kommen an jedem Ortsfilter vorbei — sonst fallen 4.144
    # Leads aus jeder Suche, obwohl sie zu jedem Standort passen.
    nationwide = geo.nationwide_clause(cfg, "DE", "g.lead_id")
    clause = (f" WHERE (({' AND '.join(where)}) OR {nationwide})") if where else ""
    order = (f" ORDER BY coalesce(dist_km, {radius_km})" if dist_sel != "NULL"
             else " ORDER BY d.titel")
    con = duckdb.connect()
    base = (f"FROM read_parquet('{LG}') g JOIN read_parquet('{LD}') d "
            f"ON d.lead_id = g.lead_id{clause}")
    total = con.execute(f"SELECT count(*) {base}").fetchone()[0]
    df = con.execute(f"""
        SELECT g.{latcol} AS lat, g.{loncol} AS lon, g.{nutscol} AS nuts, g.geo_source,
               {dist_sel} AS dist_km,
               d.titel, d.buyer_name, d.band_effektiv, d.band_source,
               d.deadline_date, d.contract_end_eff, d.lead_id
        {base}{order} LIMIT 2000
    """).df()
    return total, df


# ─────────────────────────── UI ───────────────────────────
st.title("📍 goVisor — Umkreis- & Regionssuche")

with st.sidebar:
    st.header("Suche")
    axis_label = st.radio("Achse", ["Auftraggeber (fein)", "Leistungsort (grob)"],
                          help="Auftraggeber = wo sitzt die Behörde (feine PLZ). "
                               "Leistungsort = wo wird gearbeitet (NUTS-3-grob).")
    axis = "buyer" if axis_label.startswith("Auftraggeber") else "performance"

    st.subheader("Umkreis")
    city = st.text_input("Stadt", placeholder="z. B. München")
    radius_km = st.select_slider("Radius (km)", [5, 10, 25, 50, 100], value=25)
    use_radius = bool(city.strip())   # Umkreis aktiv, sobald eine Stadt getippt ist

    st.subheader("Region (NUTS)")
    lvl_label = st.selectbox("Ebene", ["alle", "Bundesland", "Regierungsbezirk", "Landkreis/Stadt"])
    level = {"alle": None, "Bundesland": 1, "Regierungsbezirk": 2, "Landkreis/Stadt": 3}[lvl_label]
    region_q = st.text_input("Region-Name", placeholder="z. B. Oberbayern, München, Bayern")
    matches = autocomplete(region_q, level)
    opts = {f"{nm}  ·  {c} (Ebene {lv})": c for c, nm, lv, _ in matches}
    picked = st.multiselect("Treffer wählen", list(opts.keys()))
    nuts_codes = [opts[p] for p in picked]

# Suchpunkt
pt = geocode(city) if (use_radius and city.strip()) else None
lat = pt[0] if pt else None
lon = pt[1] if pt else None
active_radius = radius_km if (pt and use_radius) else None

if city.strip() and use_radius and pt is None:
    st.warning(f"Stadt '{city}' nicht gefunden – bitte anders schreiben.")

if active_radius is None and not nuts_codes:
    st.info("Gib eine **Stadt** (Umkreis) und/oder wähle eine **Region** links, um zu suchen.")
    st.stop()

total, df = run_query(lat, lon, active_radius, nuts_codes, axis)

# Kopfzeile
bits = []
if active_radius:
    bits.append(f"{active_radius} km um **{city}**")
if nuts_codes:
    names = [k.split("  ·  ")[0] for k in picked]
    bits.append("Region " + ", ".join(names))
st.subheader(f"{total:,} Leads" + (" — " + " ∩ ".join(bits) if bits else ""))
if total > len(df):
    st.caption(f"(zeige die ersten {len(df):,} auf Karte/Liste)")
st.caption(f"Achse: {axis_label}" + ("  ·  Radius auf Leistungsort ist Landkreis-grob" if axis == "performance" and active_radius else ""))

if df.empty:
    st.stop()

# Karte
mp = df.dropna(subset=["lat", "lon"])[["lat", "lon"]]
if not mp.empty:
    st.map(mp, size=40)

# Liste
show = df.copy()
show["Entfernung"] = show["dist_km"].apply(lambda d: "—" if pd.isna(d) else f"{d:.1f} km")
show["Volumen"] = show.apply(lambda r: f"{de_eur_band(r['band_effektiv'])} ({r['band_source']})", axis=1)
show = show.rename(columns={"titel": "Titel", "buyer_name": "Auftraggeber", "nuts": "NUTS",
                            "deadline_date": "Angebotsfrist", "contract_end_eff": "Vertragsende"})
st.dataframe(
    show[["Titel", "Auftraggeber", "NUTS", "Volumen", "Angebotsfrist", "Vertragsende", "Entfernung"]],
    use_container_width=True, hide_index=True, height=520)
