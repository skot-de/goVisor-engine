"""goVisor — Auslauf-Radar (lokales Streamlit-Dashboard, #3).

Rudimentäre, lokale Sicht auf die Leads: Filtern, sortieren, Detail/Kontakt.
Kein Server, kein Supabase — liest direkt data/gold/<Land>/leads.parquet.

Start:  streamlit run app/dashboard.py
"""
import sys
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from govisor import locales   # noqa: E402  — Länder-Profil (NUTS→Region etc.)

COUNTRY = "DE"
LEADS = ROOT / "data" / "gold" / COUNTRY / "leads.parquet"
MODEL = ROOT / "data" / "gold" / COUNTRY / "dim_displaceability.parquet"

VALUE_ORDER = ["<50k", "50-200k", "200k-1M", "1-5M", ">5M", "unbekannt"]
BAND_ORDER = ["hoch", "mittel", "niedrig"]

st.set_page_config(page_title="goVisor — Auslauf-Radar", layout="wide")


ENTITY_GROUP = ROOT / "data" / "gold" / COUNTRY / "entity_group.parquet"
DIM_GROUP = ROOT / "data" / "gold" / COUNTRY / "dim_company_group.parquet"

# NUTS-1 → Region: fakt-basierter Käufer-Rollup (buyer_nuts zu 100% vorhanden),
# im Gegensatz zur redaktionellen Firmengruppe. Bedient „Käufergruppe Region X".
# Quelle ist das Länder-Profil (locales) — beim Onboarding folgt es COUNTRY automatisch.
NUTS_BUNDESLAND = dict(locales.get(COUNTRY).nuts_region)


@st.cache_data
def load_leads() -> pd.DataFrame:
    con = duckdb.connect()
    # Redaktionelle Firmengruppe für Amtsinhaber UND Käufer anreichern
    # (entity → entity_group → dim_company_group). Roll-up „alle Leads der Gruppe X".
    if ENTITY_GROUP.exists() and DIM_GROUP.exists():
        df = con.execute(f"""
            SELECT l.*, g.label AS incumbent_gruppe, gb.label AS buyer_gruppe
            FROM '{LEADS.as_posix()}' l
            LEFT JOIN '{ENTITY_GROUP.as_posix()}' eg ON eg.entity_id = l.incumbent_entity
            LEFT JOIN '{DIM_GROUP.as_posix()}' g ON g.group_id = eg.group_id
            LEFT JOIN '{ENTITY_GROUP.as_posix()}' egb ON egb.entity_id = l.buyer_entity
            LEFT JOIN '{DIM_GROUP.as_posix()}' gb ON gb.group_id = egb.group_id
        """).df()
    else:
        df = con.execute(f"SELECT * FROM '{LEADS.as_posix()}'").df()
    if "buyer_nuts" in df.columns:
        df["kaeufer_bundesland"] = df["buyer_nuts"].str[:3].map(NUTS_BUNDESLAND)
    return df


@st.cache_data
def load_model() -> pd.DataFrame:
    if not MODEL.exists():
        return pd.DataFrame()
    return duckdb.connect().execute(
        f"SELECT contract_kind, branche, bucket, n, displ FROM '{MODEL.as_posix()}' "
        f"WHERE lvl='art_branche_bieter' ORDER BY n DESC"
    ).df()


REVIEW = ROOT / "data" / "gold" / COUNTRY / "review_queue.parquet"


@st.cache_data
def load_review() -> pd.DataFrame:
    if not REVIEW.exists():
        return pd.DataFrame()
    return duckdb.connect().execute(f"SELECT * FROM '{REVIEW.as_posix()}'").df()


SUCC = ROOT / "data" / "gold" / COUNTRY / "contract_successions.parquet"


@st.cache_resource
def load_successions() -> dict:
    """Nachfolge-Kanten, indiziert nach successor und predecessor (für den Ketten-Walk).

    cache_resource (nicht cache_data): der Index enthält nicht-serialisierbare
    Pandas-Rows und wird als Laufzeit-Objekt gehalten, nicht gepickelt.
    """
    if not SUCC.exists():
        return {"by_succ": {}, "by_pred": {}}
    df = duckdb.connect().execute(
        f"SELECT predecessor, successor, incumbent_name, successor_name, incumbent_retained, "
        f"predecessor_award, successor_award, contract_kind FROM '{SUCC.as_posix()}'").df()
    return {"by_succ": {r.successor: r for r in df.itertuples()},
            "by_pred": {r.predecessor: r for r in df.itertuples()}}


if not LEADS.exists():
    st.error(f"Keine Leads gefunden: {LEADS}\n\nBaue sie mit:  python -m govisor.cli gold --country DE")
    st.stop()

df = load_leads()

st.title("goVisor — Auslauf-Radar")
st.caption(
    "Kommende Re-Vergaben aus auslaufenden Verträgen. **Verdrängbarkeit** ist ein "
    "*relatives* Ranking (nach Bieterzahl × Branche), keine kalibrierte Gewinn-Wahrscheinlichkeit "
    "— hoch = Amtsinhaber angreifbar, niedrig = fest im Sattel. Werte fehlen bei ~60 % (dann „unbekannt“)."
)

# ── Filter ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filter")
    branchen = sorted(b for b in df["branche"].dropna().unique())
    f_branche = st.multiselect("Branche", branchen, default=[])

    KIND_LABEL = {"rahmenvertrag": "Rahmenvertrag", "wiederkehrend": "wiederkehrend",
                  "sonstiges": "sonstiges", "einmal_werk": "Einmal-Werk", "werk_sonstig": "Bau sonstig"}
    if "contract_kind" in df.columns:
        arten = [k for k in KIND_LABEL if k in set(df["contract_kind"].dropna().unique())]
        f_art_lbl = st.multiselect("Vertragsart", [KIND_LABEL[k] for k in arten], default=[],
                                   help="Stärkster Verdrängbarkeits-Treiber — Rahmenverträge (~90% Wechsel) sind die besten Ziele.")
        f_art = [k for k in arten if KIND_LABEL[k] in f_art_lbl]
    else:
        f_art = []

    if "incumbent_gruppe" in df.columns:
        gruppen = sorted(g for g in df["incumbent_gruppe"].dropna().unique())
        f_gruppe = st.multiselect(
            "Gruppe (Amtsinhaber)", gruppen, default=[],
            help="Firmengruppe des aktuellen Anbieters — z. B. alle Leads der Gruppe BECHTLE.")
    else:
        f_gruppe = []

    if "kaeufer_bundesland" in df.columns:
        laender = sorted(x for x in df["kaeufer_bundesland"].dropna().unique())
        f_land = st.multiselect("Bundesland (Käufer)", laender, default=[],
                                help="Aus buyer_nuts abgeleitet (100% Abdeckung) — „Käufergruppe Land X“.")
    else:
        f_land = []

    if "buyer_gruppe" in df.columns and df["buyer_gruppe"].notna().any():
        bgruppen = sorted(g for g in df["buyer_gruppe"].dropna().unique())
        f_bgruppe = st.multiselect(
            "Gruppe (Käufer)", bgruppen, default=[],
            help="Firmengruppe des Käufers (nur kommerzielle Käufer; öffentliche → Bundesland).")
    else:
        f_bgruppe = []

    # Slider-Obergrenze aus den plausiblen Leads (unplausible Fälligkeiten sind
    # Datenfehler → Review-Queue unten, nicht im Sales-Radar).
    plaus = df["termin_plausibel"] if "termin_plausibel" in df.columns else pd.Series(True, index=df.index)
    mmax = int(df.loc[plaus, "months_to_expiry"].max())
    f_months = st.slider("Auslauf in … Monaten", 0, mmax, (0, min(24, mmax)))
    f_incl_bad = st.checkbox("⚠ Unplausible Fälligkeit einbeziehen", value=False,
                             help="Datenfehler (Ende > Vergabe+25 J). Standard: aus. "
                                  "Zum Abarbeiten siehe Review-Queue unten.")
    f_hauptlos = st.checkbox("Nur Hauptlos je Projekt", value=True,
                             help="Mehrfach-Lose desselben Projekts (gleicher Käufer/"
                                  "Amtsinhaber/Ende/CPV) zu einem Eintrag zusammenfassen.")

    f_band = st.multiselect("Verdrängbarkeit", BAND_ORDER, default=[])
    vbands = [v for v in VALUE_ORDER if v in set(df["value_band"].dropna().unique())]
    f_value = st.multiselect("Wert-Band", vbands, default=[])

    f_conf = st.slider("Mindest-Score-Konfidenz (n dahinter)", 0, 500, 0, step=25,
                       help="score_support: wie viele echte Nachfolgen den Score tragen. "
                            "0 = alle (auch Global-Backoff).")
    f_src = st.slider("Mindest-Quellen-Konfidenz (Entity-Auflösung)", 0.0, 1.0, 0.0, 0.05)
    f_arge = st.checkbox("Nur ARGE-Amtsinhaber", value=False)
    f_search = st.text_input("Suche (Betreff / Amtsinhaber / Käufer)", "")

    st.header("Sortierung")
    SORTS = {
        "Nächste Ausschreibung (bald → spät)": ("months_to_expiry", True),
        "Verdrängbarkeit (hoch → niedrig)": ("displaceability", False),
        "Wert (hoch → niedrig)": ("value_real_2020", False),
    }
    f_sort = st.radio("Sortieren nach", list(SORTS), index=0)

# ── Anwenden ───────────────────────────────────────────────────────────
m = pd.Series(True, index=df.index)
if "termin_plausibel" in df.columns and not f_incl_bad:
    m &= df["termin_plausibel"]
if "ist_hauptlos" in df.columns and f_hauptlos:
    m &= df["ist_hauptlos"]
if f_branche:
    m &= df["branche"].isin(f_branche)
if f_art:
    m &= df["contract_kind"].isin(f_art)
if f_gruppe:
    m &= df["incumbent_gruppe"].isin(f_gruppe)
if f_land:
    m &= df["kaeufer_bundesland"].isin(f_land)
if f_bgruppe:
    m &= df["buyer_gruppe"].isin(f_bgruppe)
m &= df["months_to_expiry"].between(*f_months)
if f_band:
    m &= df["displ_band"].isin(f_band)
if f_value:
    m &= df["value_band"].isin(f_value)
m &= df["score_support"] >= f_conf
m &= df["source_confidence"] >= f_src
if f_arge:
    m &= df["in_consortium"]
if f_search:
    s = f_search.lower()
    m &= (df["incumbent_name"].str.lower().str.contains(s, na=False)
          | df["buyer_name"].str.lower().str.contains(s, na=False)
          | df["titel"].str.lower().str.contains(s, na=False))

fdf = df[m].copy()

# ── KPIs ───────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Leads", f"{len(fdf):,}")
c2.metric("Ø Verdrängbarkeit", f"{fdf['displaceability'].mean():.2f}" if len(fdf) else "–")
c3.metric("Anteil 'hoch'", f"{100*(fdf['displ_band'] == 'hoch').mean():.0f}%" if len(fdf) else "–")
known = fdf[fdf["value_band"] != "unbekannt"]
c4.metric("Median Wert (bekannt)",
          f"{known['value_clean'].median():,.0f} €" if len(known) else "–")

if not len(fdf):
    st.info("Keine Leads für diese Filter.")
    st.stop()

# ── Tabelle ────────────────────────────────────────────────────────────
def _status(m):
    return "🔥 akut (<6M)" if m <= 6 else ("⚡ bald (6–18M)" if m <= 18 else "📋 Vorlauf (>18M)")


fdf = fdf.assign(status=fdf["months_to_expiry"].apply(_status))
if "contract_kind" in fdf.columns:
    fdf = fdf.assign(vertragsart=fdf["contract_kind"].map(KIND_LABEL).fillna(fdf["contract_kind"]))

sort_col, sort_asc = SORTS[f_sort]
# Spalten in Anlehnung an die goVisor X-RAY (+ Verdrängbarkeits-Score als Mehrwert).
cols = ["status", "titel", "buyer_name", "kaeufer_bundesland", "incumbent_name",
        "incumbent_gruppe", "in_consortium", "lose_im_cluster", "value_clean", "vergabe_datum",
        "contract_end", "months_to_expiry", "faellig_basis", "displaceability", "displ_band",
        "score_driver", "num_tenders", "vertragsart", "branche", "source_confidence", "ted_url"]
cols = [col for col in cols if col in fdf.columns]
view = (fdf.sort_values(sort_col, ascending=sort_asc, na_position="last")
        [cols].reset_index(drop=True))
view.index = view.index + 1

st.subheader(f"{len(fdf):,} Leads · sortiert nach: {f_sort}")
st.caption("Spalten ausblenden/anordnen: Menü ⋮ oben rechts an der Tabelle → „Show/hide columns“.")
st.dataframe(
    view, use_container_width=True, height=460,
    column_config={
        "status": st.column_config.TextColumn("Status", width="small"),
        "titel": st.column_config.TextColumn("Auftragsgegenstand", width="large"),
        "buyer_name": "Auftraggeber",
        "kaeufer_bundesland": "Bundesland",
        "incumbent_name": "Akt. Dienstleister",
        "incumbent_gruppe": "Gruppe",
        "in_consortium": st.column_config.CheckboxColumn("ARGE"),
        "lose_im_cluster": st.column_config.NumberColumn("Lose", help="Anzahl Lose desselben Projekts"),
        "value_clean": st.column_config.NumberColumn("Volumen", format="€ %.0f"),
        "vergabe_datum": "Vergabe",
        "contract_end": "Fällig",
        "months_to_expiry": "in Mon.",
        "faellig_basis": "Fällig-Basis",
        "displaceability": st.column_config.ProgressColumn(
            "Verdrängbarkeit", min_value=0.0, max_value=1.0, format="%.2f"),
        "displ_band": "Band",
        "score_driver": "Treiber",
        "num_tenders": "Bieter",
        "vertragsart": "Vertragsart",
        "branche": "Branche",
        "source_confidence": st.column_config.NumberColumn("Konf.", format="%.2f"),
        "ted_url": st.column_config.LinkColumn("TED", display_text="öffnen"),
    },
)

# ── Gruppen-Übersicht (Roll-up) ────────────────────────────────────────
if "incumbent_gruppe" in fdf.columns and fdf["incumbent_gruppe"].notna().any():
    with st.expander("Firmengruppen im aktuellen Filter (Amtsinhaber-Roll-up)"):
        gv = (fdf.dropna(subset=["incumbent_gruppe"])
              .groupby("incumbent_gruppe")
              .agg(leads=("lead_id", "size"),
                   verdraengbarkeit=("displaceability", "mean"),
                   volumen=("value_clean", "sum"))
              .sort_values("leads", ascending=False).reset_index().head(25))
        st.caption("Redaktionelle Firmengruppen (editierbar: data/curated/DE_company_groups.csv). "
                   "Tipp: Gruppe links im Filter wählen, um nur ihre Leads zu sehen.")
        st.dataframe(
            gv, use_container_width=True, hide_index=True,
            column_config={
                "incumbent_gruppe": "Gruppe",
                "leads": "Leads",
                "verdraengbarkeit": st.column_config.NumberColumn("Ø Verdrängb.", format="%.2f"),
                "volumen": st.column_config.NumberColumn("Σ Volumen (bekannt)", format="€ %.0f"),
            },
        )

# ── Detail / Kontakt ───────────────────────────────────────────────────
st.subheader("Lead-Detail")
top = fdf.sort_values(sort_col, ascending=sort_asc, na_position="last")
labels = {
    f"[{int(r.months_to_expiry)}M] {str(r.titel)[:60]} — {str(r.incumbent_name)[:24]}": r.lead_id
    for r in top.head(300).itertuples()
}
pick = st.selectbox(f"Lead wählen (Top 300 nach: {f_sort})", list(labels))
if pick:
    row = fdf[fdf["lead_id"] == labels[pick]].iloc[0]
    st.markdown(f"### {row.titel}")
    if pd.notna(row.beschreibung) and row.beschreibung:
        st.markdown(f"> {row.beschreibung}")
    a, b = st.columns(2)
    with a:
        _grp = getattr(row, "incumbent_gruppe", None)
        st.markdown(f"**Akt. Dienstleister:** {row.incumbent_name}"
                    + (f" · Gruppe {_grp}" if pd.notna(_grp) and _grp else "")
                    + (" · ARGE" if row.in_consortium else "") + "  \n"
                    f"**Auftraggeber:** {row.buyer_name} ({row.buyer_town or '—'}"
                    + (f", {row.kaeufer_bundesland}" if getattr(row, "kaeufer_bundesland", None)
                       and pd.notna(row.kaeufer_bundesland) else "") + ")  \n"
                    f"**Branche:** {row.branche} · CPV {row.cpv_main}  \n"
                    f"**Vergabe:** {row.vergabe_datum}  \n"
                    f"**Fällig:** {row.contract_end} (in {row.months_to_expiry} Monaten, "
                    f"{row.faellig_basis})  \n"
                    f"**Volumen:** {row.value_band}"
                    + (f" (~{row.value_clean:,.0f} €)" if pd.notna(row.value_clean) else "")
                    + f"  \n**TED:** {row.ted_url or '—'}")
    with b:
        _d = (f"{row.displaceability:.2f} ({row.displ_band})"
              if pd.notna(row.displaceability) else f"— ({row.displ_band})")
        st.markdown(f"**Verdrängbarkeit:** {_d}  \n"
                    f"**Treiber:** {row.score_driver}  \n"
                    f"**Score-Basis:** {row.score_basis} (n={row.score_support})  \n"
                    f"**Bieter:** {row.num_tenders} · ARGE: {'ja' if row.in_consortium else 'nein'}  \n"
                    f"**Kontakt:** {row.buyer_email or '—'} · {row.buyer_url or '—'}")
    st.caption("Kontakt = Käufer aus der Bekanntmachung (nicht der Entscheider). "
               "`reachable` ist deshalb kein Priorisierungssignal.")

    # ── Vorgänger/Nachfolge-Kette (echte Vertrags-Historie) ────────────
    st.markdown("**Vorgänger / Nachfolge**")
    _sx = load_successions()
    by_succ, by_pred = _sx["by_succ"], _sx["by_pred"]
    lead_id = row.lead_id
    nodes = [(row.vergabe_datum, str(row.incumbent_name))]   # aktueller Vertrag
    node, seen = lead_id, set()
    while node in by_succ and node not in seen:               # rückwärts: Vorgänger
        seen.add(node)
        e = by_succ[node]
        nodes.append((e.predecessor_award, str(e.incumbent_name)))
        node = e.predecessor
    nodes.reverse()                                          # ältester → aktueller
    fwd = by_pred.get(lead_id)                               # schon neu vergeben? (selten)

    if len(nodes) == 1 and fwd is None:
        st.caption("Keine Vorgänger-Kette rekonstruiert — Erstvergabe oder Nachfolge nicht "
                   "über Titel-Scope auffindbar. (Basis: contract_successions.)")
    else:
        lines = []
        for i, (d, w) in enumerate(nodes):
            mark = ""
            if i > 0:
                prev_w = nodes[i - 1][1]
                mark = "  ⟶ **Wechsel**" if w != prev_w else "  ⟶ _gehalten_"
            cur = "  ← **dieser Lead**" if i == len(nodes) - 1 and fwd is None else ""
            lines.append(f"- `{d}`  {w[:40]}{mark}{cur}")
        if fwd is not None:                                  # bereits erfolgte Neuvergabe
            w = str(fwd.successor_name)
            mark = "  ⟶ **Wechsel**" if not bool(fwd.incumbent_retained) else "  ⟶ _gehalten_"
            lines.append(f"- `{fwd.successor_award}`  {w[:40]}{mark}  ← **dieser Lead**")
        else:
            lines.append(f"- `{row.contract_end}`  **Neuvergabe erwartet** (in {row.months_to_expiry} Monaten)")
        st.markdown("\n".join(lines))
        st.caption("Rekonstruiert über Titel-/Scope-Ähnlichkeit (contract_successions) — "
                   "echte wiederkehrende Verträge, keine Einmal-Werke.")

# ── Modell (Transparenz) ───────────────────────────────────────────────
with st.expander("Modell: Verdrängbarkeit je Vertragsart × Branche × Bieter (worauf der Score beruht)"):
    mdl = load_model()
    if len(mdl):
        st.dataframe(mdl.rename(columns={"contract_kind": "Vertragsart", "branche": "Branche",
                                         "bucket": "Bieter", "n": "n (echte Nachfolgen)",
                                         "displ": "Verdrängbarkeit"}),
                     use_container_width=True, hide_index=True)
        st.caption("Gelernt auf ECHTEN Vertrag→Neuvergabe-Ketten (contract_successions, Titel-Scope). "
                   "Kreuzvalidiert: AUC 0,767 (Stand 2026-07-23). Kuratierbar: dim_displaceability.parquet.")
    else:
        st.info("dim_displaceability.parquet fehlt — Score wurde noch nicht gebaut.")

# ── Review-Queue: Datenfehler zum Abarbeiten (nicht gelöscht, markiert) ─
rq = load_review()
with st.expander(f"⚠ Review-Queue: {len(rq):,} Datenfehler zum Abarbeiten"):
    st.caption("Harte, korrigierbare Fehler (unplausible Laufzeit, Ende vor Vergabe, "
               "absurd hoher Wert). Nichts gelöscht — Silber bleibt intakt, die Notice "
               "zählt normal; hier liegt sie zum Prüfen mit Beleg-Link. Quelle: "
               "data/gold/DE/review_queue.parquet.")
    if len(rq):
        rq = rq.copy()
        rq["quality_flags"] = rq["quality_flags"].apply(
            lambda x: ", ".join(x) if isinstance(x, (list, tuple)) else str(x))
        st.dataframe(
            rq, use_container_width=True, height=320, hide_index=True,
            column_config={
                "notice_id": "Notice-ID",
                "quality_flags": "Fehler",
                "titel": st.column_config.TextColumn("Auftragsgegenstand", width="medium"),
                "award_date": "Vergabe",
                "end_date": "Ende (roh)",
                "duration_months": "Laufzeit (Mon.)",
                "final_value": st.column_config.NumberColumn("Wert (roh)", format="%.0f"),
                "value_currency": "Währung",
                "ted_url": st.column_config.LinkColumn("TED", display_text="öffnen"),
            },
        )
    else:
        st.info("review_queue.parquet fehlt — mit `python -m govisor.cli gold` bauen.")
