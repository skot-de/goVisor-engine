"""P0-Gold-Plumbing: award_tender_link + value_anchor — Kern-Invarianten.

Integrationstest gegen die gebaute Gold-Ebene; skippt sauber, wo die Daten fehlen
(z. B. frische CI ohne Ingest).
"""
import os

import pytest

pytest.importorskip("duckdb")
import duckdb  # noqa: E402

G = "data/gold/DE"
PRICING_BANDS = {"<100k", "100-250k", "250-500k", "500k-1,3M", "1,3-5M", "5-25M", ">25M"}


def _has(name):
    return os.path.exists(f"{G}/{name}.parquet")


@pytest.mark.skipif(not _has("award_tender_link"), reason="award_tender_link nicht gebaut")
def test_award_tender_link_is_unique_per_award():
    con = duckdb.connect()
    dup = con.execute(
        f"SELECT count(*) - count(DISTINCT award_notice_id) "
        f"FROM read_parquet('{G}/award_tender_link.parquet')").fetchone()[0]
    assert dup == 0, "jeder Zuschlag darf nur EINE Ausschreibung verlinken"


@pytest.mark.skipif(not _has("value_anchor"), reason="value_anchor nicht gebaut")
def test_value_anchor_bands_are_valid_pricing_bands():
    con = duckdb.connect()
    bands = {r[0] for r in con.execute(
        f"SELECT DISTINCT anchor_band FROM read_parquet('{G}/value_anchor.parquet') "
        f"WHERE anchor_source <> 'none'").fetchall()}  # ohne Anker -> 'unbekannt', legitim
    # anchor_band muss exakt zu pricing.SCHEDULE passen (sonst greift der Waechter ins Leere)
    assert bands <= PRICING_BANDS, f"unerwartete Bänder: {bands - PRICING_BANDS}"


@pytest.mark.skipif(not _has("value_anchor"), reason="value_anchor nicht gebaut")
def test_value_anchor_covers_the_no_value_awards():
    # Der Waechter muss genau dort greifen, wo der echte Wert fehlt.
    con = duckdb.connect()
    tot, withanchor = con.execute(
        f"SELECT count(*), count(*) FILTER (WHERE anchor_source <> 'none') "
        f"FROM read_parquet('{G}/value_anchor.parquet') WHERE NOT has_real_value").fetchone()
    assert tot > 0
    assert withanchor / tot > 0.9, "Anker-Abdeckung im wertlosen Drittel zu niedrig"


@pytest.mark.skipif(not _has("lead_deadline"), reason="lead_deadline nicht gebaut")
def test_every_open_tender_has_a_deadline():
    # Der Frist-Flip funktioniert nur, wenn JEDE offene Ausschreibung eine Frist hat
    # (echt oder belastbar geschaetzt) — sonst kein Alert.
    con = duckdb.connect()
    nulls = con.execute(
        f"SELECT count(*) FROM read_parquet('{G}/lead_deadline.parquet') "
        f"WHERE deadline_date IS NULL").fetchone()[0]
    assert nulls == 0


@pytest.mark.skipif(not _has("lead_duration"), reason="lead_duration nicht gebaut")
def test_lead_duration_sources_are_honest():
    # Quellen muessen die Herkunft ehrlich trennen (echt vs. geschaetzt vs. unbekannt).
    con = duckdb.connect()
    srcs = {r[0] for r in con.execute(
        f"SELECT DISTINCT duration_source FROM read_parquet('{G}/lead_duration.parquet')").fetchall()}
    assert srcs <= {"echt", "geschaetzt_start", "geschaetzt_award", "unbekannt"}
    # 'unbekannt' MUSS ein leeres contract_end haben (keine erfundenen Daten)
    leaked = con.execute(
        f"SELECT count(*) FROM read_parquet('{G}/lead_duration.parquet') "
        f"WHERE duration_source='unbekannt' AND contract_end IS NOT NULL").fetchone()[0]
    assert leaked == 0


@pytest.mark.skipif(not _has("lead_detail"), reason="lead_detail nicht gebaut")
def test_lead_detail_is_one_to_one_with_leads():
    # Die UI-View darf Leads nicht vervielfachen (sonst doppelte Zeilen im Frontend).
    con = duckdb.connect()
    dup = con.execute(
        f"SELECT count(*) - count(DISTINCT lead_id) "
        f"FROM read_parquet('{G}/lead_detail.parquet')").fetchone()[0]
    assert dup == 0
    # Jeder Lead trägt eine band_source (nie „unbekannt" — Gebühren-Basis ist immer da)
    missing = con.execute(
        f"SELECT count(*) FROM read_parquet('{G}/lead_detail.parquet') "
        f"WHERE band_source IS NULL").fetchone()[0]
    assert missing == 0


@pytest.mark.skipif(not _has("entity_identity"), reason="entity_identity nicht gebaut")
def test_every_entity_has_exactly_one_identity():
    # Jede Entity braucht genau EINE identity_id — sonst ist Winner-Matching mehrdeutig.
    con = duckdb.connect()
    tot, distinct_ent, nullid = con.execute(
        f"SELECT count(*), count(DISTINCT entity_id), count(*) FILTER (WHERE identity_id IS NULL) "
        f"FROM read_parquet('{G}/entity_identity.parquet')").fetchone()
    assert tot == distinct_ent, "Entity darf nur eine Zeile/Identität haben"
    assert nullid == 0, "identity_id nie NULL (solo:<id> als Fallback)"


@pytest.mark.skipif(not _has("entity_identity"), reason="entity_identity nicht gebaut")
def test_solo_entities_are_their_own_identity():
    # Nicht-gruppierte Entities bekommen 'solo:<entity_id>' und group_size 1.
    con = duckdb.connect()
    bad = con.execute(
        f"SELECT count(*) FROM read_parquet('{G}/entity_identity.parquet') "
        f"WHERE NOT in_group AND (identity_id NOT LIKE 'solo:%' OR group_size <> 1)").fetchone()[0]
    assert bad == 0


# ---- lead_export: Frontend-Feld-Vertrag ---------------------------------------
_EXPORT_VOCAB = {
    "phase": {"auslauf", "f02", "f01"},
    "natur_kat": {"dienst", "liefer", "bau"},
    "natur_src": {"echt", "geschaetzt"},
    "volumen_src": {"echt", "schaetz", "unbekannt"},
    "timing_src": {"echt", "schaetz", "unsicher", "unbekannt"},
    "incumbent_src": {"echt", "unsicher", None},
    "wechsel": {"hoch", "mittel", "niedrig", "na"},
    "konk_stufe": {"gering", "mittel", "hoch", "na"},
    "konk_src": {"echt", "unbekannt", "na"},
}


@pytest.mark.skipif(not _has("lead_export"), reason="lead_export nicht gebaut")
@pytest.mark.parametrize("col,allowed", list(_EXPORT_VOCAB.items()))
def test_lead_export_vocabulary(col, allowed):
    """Jede Herkunfts-/Band-Spalte darf nur Frontend-erwartete Werte tragen."""
    con = duckdb.connect()
    seen = {r[0] for r in con.execute(
        f"SELECT DISTINCT {col} FROM read_parquet('{G}/lead_export.parquet')").fetchall()}
    assert seen <= allowed, f"{col}: unerwartete Werte {seen - allowed}"


@pytest.mark.skipif(not _has("lead_export"), reason="lead_export nicht gebaut")
def test_lead_export_is_1to1_with_lead_detail():
    con = duckdb.connect()
    a = con.execute(f"SELECT count(*), count(DISTINCT lead_id) FROM read_parquet('{G}/lead_export.parquet')").fetchone()
    b = con.execute(f"SELECT count(*) FROM read_parquet('{G}/lead_detail.parquet')").fetchone()[0]
    assert a[0] == a[1], "lead_id muss eindeutig sein (Supabase-PK)"
    assert a[0] == b, "lead_export muss 1:1 zu lead_detail stehen"


@pytest.mark.skipif(not _has("lead_export"), reason="lead_export nicht gebaut")
def test_lead_export_default_value_is_hidden():
    """band_source='default' → volumen_wert NULL (Frontend zeigt '—', schätzt nicht)."""
    con = duckdb.connect()
    bad = con.execute(
        f"SELECT count(*) FROM read_parquet('{G}/lead_export.parquet') "
        f"WHERE volumen_src='unbekannt' AND volumen_wert IS NOT NULL").fetchone()[0]
    assert bad == 0


@pytest.mark.skipif(not _has("lead_export"), reason="lead_export nicht gebaut")
def test_lead_export_slug_is_unique_and_wellformed():
    """slug = permanente Kurz-ID: eindeutig, non-null, Quellen-Prefix + base62."""
    import re
    con = duckdb.connect()
    tot, uni, nn = con.execute(
        f"SELECT count(*), count(DISTINCT slug), count(slug) FROM read_parquet('{G}/lead_export.parquet')"
    ).fetchone()
    assert tot == uni, "slug muss eindeutig sein (Permalink)"
    assert tot == nn, "slug darf nie NULL sein"
    bad = con.execute(
        rf"SELECT count(*) FROM read_parquet('{G}/lead_export.parquet') "
        rf"WHERE NOT regexp_matches(slug, '^[td][0-9A-Za-z]+$')").fetchone()[0]
    assert bad == 0, "slug = Quellen-Prefix (t/d) + base62"


# ---- DÖE-Ingest (zweite Quelle, unterschwellig) -------------------------------
def _silver_glob(table):
    return f"data/silver/DE/{table}/*/*.parquet"


@pytest.mark.skipif(not os.path.exists("data/silver/DE/notices/year=2026"),
                    reason="Silber nicht gebaut")
def test_doe_silver_is_notice_unique():
    """Cross-Monat-Dedup: DÖE re-exportiert Notices über Monate — im Silber darf jede
    notice_id nur EINMAL stehen (sonst Join-Fan-out im Gold)."""
    con = duckdb.connect()
    tot, uni = con.execute(
        f"SELECT count(*), count(DISTINCT notice_id) FROM read_parquet('{_silver_glob('notices')}', "
        f"hive_partitioning=1) WHERE schema_gen='doe'").fetchone()
    assert tot == uni, f"DÖE-Silber hat {tot-uni} Cross-Monat-Dubletten"


@pytest.mark.skipif(not _has("lead_export"), reason="lead_export nicht gebaut")
def test_doe_leads_have_d_prefix_and_buyer():
    """DÖE-Leads: Slug-Prefix 'd' und immer ein Käufer (Parser-Fallback greift)."""
    con = duckdb.connect()
    n = con.execute(f"SELECT count(*) FROM read_parquet('{G}/lead_export.parquet') WHERE slug LIKE 'd%'").fetchone()[0]
    if n == 0:
        pytest.skip("keine DÖE-Leads geladen")
    no_buyer = con.execute(
        f"SELECT count(*) FROM read_parquet('{G}/lead_export.parquet') "
        f"WHERE slug LIKE 'd%' AND buyer IS NULL").fetchone()[0]
    assert no_buyer == 0, "jeder DÖE-Lead muss einen Käufer haben"


# ---- DÖE-Analyse-KPIs ---------------------------------------------------------
@pytest.mark.skipif(not _has("doe_buyer_profile"), reason="doe_buyer_profile nicht gebaut")
def test_doe_buyer_profile_is_entity_unique_and_linked():
    con = duckdb.connect()
    tot, uni = con.execute(
        f"SELECT count(*), count(DISTINCT buyer_entity) FROM read_parquet('{G}/doe_buyer_profile.parquet')").fetchone()
    assert tot == uni, "je Käufer-Entität genau eine Profilzeile"
    orphan = con.execute(
        f"SELECT count(*) FROM read_parquet('{G}/doe_buyer_profile.parquet') b "
        f"LEFT JOIN read_parquet('{G}/entities.parquet') e ON e.entity_id=b.buyer_entity "
        f"WHERE e.entity_id IS NULL").fetchone()[0]
    assert orphan == 0, "buyer_entity muss in entities auflösen"


@pytest.mark.skipif(not _has("doe_demand"), reason="doe_demand nicht gebaut")
def test_doe_demand_grain_is_unique():
    con = duckdb.connect()
    tot, uni = con.execute(
        f"SELECT count(*), count(DISTINCT (cpv_div, nuts3, year)) FROM read_parquet('{G}/doe_demand.parquet')").fetchone()
    assert tot == uni, "eine Zeile je (CPV-Division, NUTS-3, Jahr)"


# ---- Vergabestelle-Analyse ----------------------------------------------------
@pytest.mark.skipif(not _has("buyer_profile"), reason="buyer_profile nicht gebaut")
def test_buyer_profile_is_entity_unique_and_honest():
    con = duckdb.connect()
    tot, uni = con.execute(
        f"SELECT count(*), count(DISTINCT buyer_entity) FROM read_parquet('{G}/buyer_profile.parquet')").fetchone()
    assert tot == uni, "je Käufer genau eine Profilzeile"
    # Konzentration nur aus erlaubtem Vokabular
    conc = {r[0] for r in con.execute(
        f"SELECT DISTINCT concentration FROM read_parquet('{G}/buyer_profile.parquet') "
        f"WHERE concentration IS NOT NULL").fetchall()}
    assert conc <= {"oligopol", "moderat", "fragmentiert"}
    # Wettbewerbs-Ampel nur aus erlaubtem Vokabular
    amp = {r[0] for r in con.execute(
        f"SELECT DISTINCT competition_flag FROM read_parquet('{G}/buyer_profile.parquet') "
        f"WHERE competition_flag IS NOT NULL").fetchall()}
    assert amp <= {"gruen", "gelb", "rot"}
    # value_coverage ist der Ehrlichkeits-Flag: 0..100
    bad = con.execute(
        f"SELECT count(*) FROM read_parquet('{G}/buyer_profile.parquet') "
        f"WHERE value_coverage < 0 OR value_coverage > 100").fetchone()[0]
    assert bad == 0


@pytest.mark.skipif(not _has("buyer_recent_awards"), reason="buyer_recent_awards nicht gebaut")
def test_buyer_recent_awards_capped_at_20():
    con = duckdb.connect()
    over = con.execute(
        f"SELECT count(*) FROM (SELECT buyer_entity, count(*) c "
        f"FROM read_parquet('{G}/buyer_recent_awards.parquet') GROUP BY 1 HAVING c > 20)").fetchone()[0]
    assert over == 0, "max. 20 jüngste Awards je Käufer"


@pytest.mark.skipif(not _has("buyer_profile"), reason="buyer_profile nicht gebaut")
def test_buyer_external_enrichment_is_consistent():
    """Wikidata-Anreicherung: is_enriched ⇔ wikidata_id vorhanden (schema-stabil auch ohne Cache)."""
    con = duckdb.connect()
    bad = con.execute(
        f"SELECT count(*) FROM read_parquet('{G}/buyer_profile.parquet') "
        f"WHERE is_enriched <> (wikidata_id IS NOT NULL)").fetchone()[0]
    assert bad == 0


@pytest.mark.skipif(not _has("region_kpi"), reason="region_kpi nicht gebaut")
def test_region_kpi_grain_and_sanity():
    """Eine Zeile je NUTS-3; Intensität ist eine UNTERGRENZE (Wert-Coverage!) und darf
    nicht negativ sein."""
    con = duckdb.connect()
    tot, uni = con.execute(
        f"SELECT count(*), count(DISTINCT nuts_code) FROM read_parquet('{G}/region_kpi.parquet')").fetchone()
    assert tot == uni, "je Region genau eine Zeile"
    bad = con.execute(
        f"SELECT count(*) FROM read_parquet('{G}/region_kpi.parquet') "
        f"WHERE intensitaet_pct < 0 OR volumen_coverage > 100").fetchone()[0]
    assert bad == 0
