"""goVisor — Marktchancen-Explorer (White-Space Radar, lokal).

Klickbare Sicht auf `market_opportunity` + `retender_signal`: wo trifft Nachfrage
auf dünnen Wettbewerb, welche Firmen dominieren (Buy-Longlist), und welche Bedarfe
werden seit Jahren erfolglos ausgeschrieben (Verzweiflungs-Chronik).

Start:  streamlit run app/marktchancen.py
Liest direkt data/gold/DE/*.parquet — kein Server.
"""
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor import geo  # noqa: E402
from govisor.config import Config  # noqa: E402

G = ROOT / "data" / "gold" / "DE"
MO = G / "market_opportunity.parquet"
RS = G / "retender_signal.parquet"
EN = G / "entities.parquet"
PE = G / "party_entity.parquet"
Q = G / "quality.parquet"
AD = G / "cpv_adjacency.parquet"
DP = G / "dim_plz.parquet"
NG = (ROOT / "data" / "silver" / "DE" / "notices" / "*" / "*.parquet").as_posix()
AG = (ROOT / "data" / "silver" / "DE" / "awards" / "*" / "*.parquet").as_posix()
NP = (ROOT / "data" / "silver" / "DE" / "notice_parties" / "*" / "*.parquet").as_posix()
cfg = Config(countries=("DE",), data_dir=str(ROOT / "data"))

st.set_page_config(page_title="goVisor — Marktchancen-Radar", layout="wide")


def de_eur(v) -> str:
    """Deutsche Euro-Formatierung mit Tausenderpunkt: 1.355.000 €."""
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.0f} €".replace(",", ".")


@st.cache_data
def geo_ac(query: str):
    return geo.nuts_autocomplete(cfg, "DE", query.strip(), limit=25) if len(query.strip()) >= 2 else []


@st.cache_data
def geo_pt(city: str):
    return geo.geocode_city(cfg, "DE", city.strip()) if city.strip() else None


def geo_filter_sidebar():
    """Sidebar-Regional-Filter (Achse, Region-Autocomplete, Umkreis). Gibt einen Kontext zurück."""
    with st.sidebar:
        st.header("📍 Regional-Filter")
        st.caption("Filtert die konkreten Aufträge im Segment-Detail (Tab 1).")
        axis = "performance" if st.radio(
            "Achse", ["Leistungsort", "Auftraggeber"],
            help="Leistungsort = wo wird gearbeitet (performance_nuts). "
                 "Auftraggeber = wo sitzt die Behörde (buyer_nuts + Umkreis).") == "Leistungsort" else "buyer"
        region_q = st.text_input("Region-Name", placeholder="z. B. Oberbayern, München, Bayern")
        opts = {f"{nm} · {c} (E{lv})": c for c, nm, lv, _ in geo_ac(region_q)}
        nuts = [opts[p] for p in st.multiselect("Region wählen", list(opts))]
        st.markdown("**Umkreis** (nur Auftraggeber-Achse)")
        city = st.text_input("um Stadt", placeholder="z. B. München", disabled=(axis != "buyer"))
        radius = st.select_slider("Radius (km)", [5, 10, 25, 50, 100], value=25, disabled=(axis != "buyer"))
    pt = geo_pt(city) if (axis == "buyer" and city.strip()) else None
    labels = [p.split(" · ")[0] for p in [k for k, v in opts.items() if v in nuts]]
    return {"axis": axis, "nuts": nuts, "pt": pt, "radius": radius if pt else None,
            "city": city, "labels": labels}


def apply_geo(df: pd.DataFrame, ctx: dict) -> pd.DataFrame:
    """Wendet den Regional-Filter auf ein Awards-DataFrame an (NUTS-Präfix + optional Umkreis)."""
    nutscol = "perf_nuts" if ctx["axis"] == "performance" else "buyer_nuts"
    m = pd.Series(True, index=df.index)
    if ctx["nuts"]:
        m &= df[nutscol].fillna("").apply(lambda s: any(s.startswith(c) for c in ctx["nuts"]))
    if ctx["pt"] and ctx["radius"]:
        lat, lon = ctx["pt"]
        la, lo = np.radians(lat), np.radians(lon)
        bla, blo = np.radians(df["blat"].astype(float)), np.radians(df["blon"].astype(float))
        d = 2 * 6371 * np.arcsin(np.sqrt(
            np.sin((bla - la) / 2) ** 2 + np.cos(la) * np.cos(bla) * np.sin((blo - lo) / 2) ** 2))
        m &= df["blat"].notna() & (d <= ctx["radius"])
    return df[m]


@st.cache_data
def load_segments() -> pd.DataFrame:
    con = duckdb.connect()
    return con.execute(f"""
        SELECT opportunity_score, cpv4, segment_label, struktur, n_awards,
               erfolglos_pct, single_bidder_pct, avg_bidders, median_value,
               total_value_known, n_contractors, chronic_needs, max_fail_years,
               last_award_year, window_start, window_end, top3_share, hhi, top_dominators
        FROM read_parquet('{MO.as_posix()}')
    """).df()


@st.cache_data
def load_retender() -> pd.DataFrame:
    con = duckdb.connect()
    return con.execute(f"""
        SELECT e.canonical_name AS behoerde, r.cpv_class, r.need_title,
               r.fail_attempts, r.fail_years, r.first_fail_year, r.last_fail_year,
               r.span_years, r.still_open
        FROM read_parquet('{RS.as_posix()}') r
        LEFT JOIN read_parquet('{EN.as_posix()}') e ON e.entity_id = r.buyer_entity
    """).df()


@st.cache_data
def load_adjacency() -> pd.DataFrame:
    con = duckdb.connect()
    return con.execute(f"SELECT cpv_a, cpv_b, cond_prob FROM read_parquet('{AD.as_posix()}')").df()


@st.cache_data
def load_segment_awards(cpv4: str, win_start: int) -> pd.DataFrame:
    """Die konkreten CAN-Aufträge eines Segments — damit sichtbar wird, was der Markt verlangt."""
    con = duckdb.connect()
    return con.execute(f"""
        WITH buy AS (SELECT notice_id, arg_min(entity_id,seq) eid FROM read_parquet('{PE.as_posix()}')
                     WHERE role='buyer' GROUP BY 1),
             win AS (SELECT notice_id, arg_min(entity_id,seq) eid FROM read_parquet('{PE.as_posix()}')
                     WHERE role='winner' GROUP BY 1),
             aw  AS (SELECT notice_id, max(num_tenders) nt FROM read_parquet('{AG}') WHERE num_tenders>0 GROUP BY 1),
             bmeta AS (SELECT notice_id,
                        any_value(regexp_extract(postal_code,'([0-9]{{5}})',1)) plz,
                        any_value(nuts) bnuts
                      FROM read_parquet('{NP}', hive_partitioning=1) WHERE role='buyer' GROUP BY 1)
        SELECT CAST(coalesce(year(n.award_date), n.year) AS INT) AS jahr,
               n.title AS titel, be.canonical_name AS behoerde,
               we.canonical_name AS gewinner, q.final_value_clean AS wert,
               aw.nt AS bieter, q.verfahren_status AS status, n.ted_url,
               n.notice_id, n.performance_nuts AS perf_nuts, bmeta.bnuts AS buyer_nuts,
               dp.lat AS blat, dp.lon AS blon
        FROM read_parquet('{NG}', hive_partitioning=1) n
        LEFT JOIN read_parquet('{Q.as_posix()}') q ON q.notice_id=n.notice_id
        LEFT JOIN buy ON buy.notice_id=n.notice_id
        LEFT JOIN read_parquet('{EN.as_posix()}') be ON be.entity_id=buy.eid
        LEFT JOIN win ON win.notice_id=n.notice_id
        LEFT JOIN read_parquet('{EN.as_posix()}') we ON we.entity_id=win.eid
        LEFT JOIN aw ON aw.notice_id=n.notice_id
        LEFT JOIN bmeta ON bmeta.notice_id=n.notice_id
        LEFT JOIN read_parquet('{DP.as_posix()}') dp ON dp.plz=bmeta.plz
        WHERE n.notice_kind='can' AND substr(n.cpv_main,1,4)='{cpv4}'
          AND CAST(n.year AS INT) >= {win_start}
        ORDER BY q.final_value_clean DESC NULLS LAST, jahr DESC
    """).df()


if not MO.exists():
    st.error(f"{MO} fehlt — erst `python -m govisor.cli gold` laufen lassen.")
    st.stop()

seg = load_segments()
ret = load_retender()

st.title("🎯 goVisor — Marktchancen-Radar")
win = f"{int(seg['window_start'].iloc[0])}–{int(seg['window_end'].iloc[0])}"
st.caption(f"Wo trifft Nachfrage auf dünnen Wettbewerb? · Datenfenster {win} · "
           f"{len(seg):,} Segmente · {int((ret['still_open']).sum()):,} aktuell chronische Fehl-Bedarfe")

geo_ctx = geo_filter_sidebar()

tab1, tab2, tab3 = st.tabs(["📊 Segment-Chancen", "🔥 Verzweiflungs-Chronik", "🎯 Für dich"])

# ---- Tab 1: Segment-Explorer ------------------------------------------------
with tab1:
    c = st.columns(5)
    strukt = c[0].multiselect("Struktur", ["fragmentiert", "moderat", "oligopol"],
                              default=["fragmentiert", "moderat", "oligopol"])
    min_score = c[1].slider("Min. Score", 0, 100, 60)
    min_val = c[2].select_slider("Min. Median-Wert",
                                 options=[0, 50_000, 200_000, 1_000_000, 5_000_000], value=200_000,
                                 format_func=lambda v: f"{v/1e6:.2f}M €" if v else "0")
    only_chronic = c[3].checkbox("Nur mit chronischen Bedarfen")
    suche = c[4].text_input("Segment suchen")

    f = seg[seg["struktur"].isin(strukt) & (seg["opportunity_score"] >= min_score)
            & (seg["median_value"].fillna(0) >= min_val)].copy()
    if only_chronic:
        f = f[f["chronic_needs"] > 0]
    if suche:
        f = f[f["segment_label"].str.contains(suche, case=False, na=False)]
    f = f.sort_values("opportunity_score", ascending=False)

    view = f[["opportunity_score", "cpv4", "segment_label", "struktur", "n_awards",
              "erfolglos_pct", "single_bidder_pct", "median_value", "n_contractors",
              "chronic_needs", "last_award_year"]].copy()
    view["median_value"] = view["median_value"].map(de_eur)
    view = view.rename(columns={
        "opportunity_score": "Score", "cpv4": "CPV", "segment_label": "Segment",
        "struktur": "Struktur", "n_awards": "Vergaben", "erfolglos_pct": "erfolglos %",
        "single_bidder_pct": "1-Bieter %", "median_value": "Median €",
        "n_contractors": "Firmen", "chronic_needs": "chron. Bedarfe", "last_award_year": "letzte"})
    st.dataframe(view, use_container_width=True, hide_index=True,
                 column_config={"Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d")})

    st.markdown("### 🔎 Segment-Detail")
    if len(f):
        options = f["cpv4"] + " · " + f["segment_label"].fillna("?")
        pick = st.selectbox("Segment wählen", options.tolist())
        row = f[f["cpv4"] == pick.split(" · ")[0]].iloc[0]
        m = st.columns(4)
        m[0].metric("Opportunity-Score", int(row["opportunity_score"]))
        m[1].metric("Struktur", row["struktur"])
        m[2].metric("Median-Wert", de_eur(row["median_value"]))
        m[3].metric("1-Bieter-Anteil", f"{row['single_bidder_pct'] or 0:.0f}%")
        strat = {"fragmentiert": "🟢 **Make** (selbst aufbauen) oder **Buy** (Regionalplayer kaufen)",
                 "moderat": "🟡 **Buy** oder **Partner**",
                 "oligopol": "🔴 **Buy-Spezialist** oder **Partner** (Einstieg hart)"}.get(row["struktur"], "")
        st.info(f"Strategie-Hinweis: {strat}")

        st.markdown("**🏢 Top-Firmen im Segment = Buy-/Partner-Kandidaten**")
        doms = row["top_dominators"]
        if doms is not None and len(doms):
            dd = pd.DataFrame(list(doms))
            dd["share"] = (dd["share"] * 100).round(0).astype(int).astype(str) + " %"
            st.dataframe(dd.rename(columns={"name": "Firma", "wins": "Wins", "share": "Anteil"})[
                ["Firma", "Wins", "Anteil"]], use_container_width=True, hide_index=True)

        chron = ret[(ret["cpv_class"] == row["cpv4"]) & ret["still_open"]].sort_values(
            "fail_years", ascending=False)
        if len(chron):
            st.markdown(f"**🔥 Chronische Fehl-Bedarfe in diesem Segment ({len(chron)})**")
            for _, r in chron.head(15).iterrows():
                st.write(f"- **{r['fail_attempts']}× erfolglos über {r['span_years']} Jahre** "
                         f"({r['first_fail_year']}–{r['last_fail_year']}) · "
                         f"*{r['behoerde']}*: {r['need_title']}")

        st.markdown("**📋 Konkrete Aufträge in diesem Segment — was der Markt verlangt**")
        aw = load_segment_awards(row["cpv4"], int(row["window_start"]))
        if geo_ctx["nuts"] or geo_ctx["pt"]:
            n_before = len(aw)
            aw = apply_geo(aw, geo_ctx)
            bits = []
            if geo_ctx["nuts"]:
                bits.append(", ".join(geo_ctx["labels"]))
            if geo_ctx["pt"]:
                bits.append(f"{geo_ctx['radius']} km um {geo_ctx['city']}")
            achse = "Leistungsort" if geo_ctx["axis"] == "performance" else "Auftraggeber"
            st.success(f"📍 Regional gefiltert ({achse}): **{len(aw):,} von {n_before:,}** Aufträgen "
                       f"— {' ∩ '.join(bits)}")
        only_erf = st.checkbox("Nur erfolglose (offene Chancen)", key="only_erf")
        awv = (aw[aw["status"] == "erfolglos"] if only_erf else aw).copy()
        awv["wert"] = awv["wert"].map(de_eur)
        st.caption(f"{len(awv):,} Aufträge ({int(row['window_start'])}–{int(row['window_end'])}) · "
                   f"nach Wert sortiert — Titel zeigt, welche Leistung gefragt ist")
        awd = awv[["jahr", "titel", "behoerde", "gewinner", "wert", "bieter", "status", "ted_url"]].rename(
            columns={"jahr": "Jahr", "titel": "Titel/Leistung", "behoerde": "Behörde",
                     "gewinner": "Gewinner", "wert": "Wert", "bieter": "Bieter",
                     "status": "Status", "ted_url": "TED"})
        st.dataframe(awd, use_container_width=True, hide_index=True, height=430,
                     column_config={"TED": st.column_config.LinkColumn("TED", display_text="↗")})

# ---- Tab 2: Verzweiflungs-Chronik ------------------------------------------
with tab2:
    st.caption("Bedarfe, die eine Behörde seit Jahren mehrfach erfolglos ausschreibt — "
               "verzweifelter Käufer, kaum Wettbewerb. Inhaltsgeclustert (ein Bedarf, nicht Lose).")
    c = st.columns(3)
    min_years = c[0].slider("Min. Fehl-Jahre", 2, 10, 3)
    nur_offen = c[1].checkbox("Nur aktuell relevante", value=True)
    suche2 = c[2].text_input("Bedarf/Behörde suchen")
    rr = ret[ret["fail_years"] >= min_years].copy()
    if nur_offen:
        rr = rr[rr["still_open"]]
    if suche2:
        rr = rr[rr["need_title"].str.contains(suche2, case=False, na=False)
                | rr["behoerde"].str.contains(suche2, case=False, na=False)]
    rr = rr.sort_values(["fail_years", "span_years"], ascending=False)
    st.caption(f"{len(rr):,} Bedarfe")
    st.dataframe(rr[["fail_attempts", "fail_years", "span_years", "first_fail_year", "last_fail_year",
                     "behoerde", "need_title"]].rename(columns={
        "fail_attempts": "Anläufe", "fail_years": "Fehl-Jahre", "span_years": "Spanne (J)",
        "first_fail_year": "seit", "last_fail_year": "letzter", "behoerde": "Behörde",
        "need_title": "Bedarf"}), use_container_width=True, hide_index=True)

# ---- Tab 3: Für dich (personalisiert via CPV-Adjacency) ---------------------
with tab3:
    st.caption("Wähle, was du schon lieferst — dann zeigen wir die offenen Märkte, die am nächsten "
               "an deinen Fähigkeiten liegen (Nähe = wie oft Firmen mit deinem Skill auch dort gewinnen).")
    adj = load_adjacency()
    seg_opts = (seg["cpv4"] + " · " + seg["segment_label"].fillna("?")).sort_values().tolist()
    picks = st.multiselect("Deine CPV-Segmente (was du bereits kannst)", seg_opts,
                           help="Mehrfachauswahl — z.B. dein aktuelles Geschäft.")
    footprint = [p.split(" · ")[0] for p in picks]
    if not footprint:
        st.info("Wähle oben ein oder mehrere Segmente, die du bereits bedienst "
                "(z.B. 7200 IT-Dienste) — dann erscheinen die dazu passenden offenen Märkte.")
    else:
        rel = adj[adj["cpv_a"].isin(footprint)]
        if len(rel):
            near = rel.loc[rel.groupby("cpv_b")["cond_prob"].idxmax()].rename(
                columns={"cpv_b": "cpv4", "cond_prob": "naehe", "cpv_a": "bruecke"})
        else:
            near = pd.DataFrame(columns=["cpv4", "naehe", "bruecke"])
        lbl = dict(zip(seg["cpv4"], seg["segment_label"].fillna("")))
        m = seg.merge(near[["cpv4", "naehe", "bruecke"]], on="cpv4", how="left")
        m = m[~m["cpv4"].isin(footprint)].copy()
        m["naehe"] = m["naehe"].fillna(0.0)
        m["personal_fit"] = (m["opportunity_score"] * m["naehe"]).round()
        m["bruecke_label"] = m["bruecke"].map(
            lambda x: f"{x} {lbl.get(x, '')[:22]}" if pd.notna(x) else "")
        min_naehe = st.slider("Min. Nähe zu deinen Fähigkeiten", 0.0, 1.0, 0.15, 0.05)
        f3 = m[m["naehe"] >= min_naehe].sort_values("personal_fit", ascending=False)
        st.caption(f"{len(f3):,} erreichbare Chancen-Segmente · Fit = Chance × Nähe")
        v = f3[["personal_fit", "opportunity_score", "naehe", "cpv4", "segment_label", "struktur",
                "single_bidder_pct", "chronic_needs", "median_value", "bruecke_label"]].copy()
        v["median_value"] = v["median_value"].map(de_eur)
        v["naehe"] = (v["naehe"] * 100).round().astype(int).astype(str) + " %"
        st.dataframe(v.rename(columns={
            "personal_fit": "Fit", "opportunity_score": "Chance", "naehe": "Nähe", "cpv4": "CPV",
            "segment_label": "Segment", "struktur": "Struktur", "single_bidder_pct": "1-Bieter %",
            "chronic_needs": "chron.", "median_value": "Median €", "bruecke_label": "erreichbar über"}),
            use_container_width=True, hide_index=True, column_config={
                "Fit": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d")})
