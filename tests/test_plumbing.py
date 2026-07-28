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
# Der Vertrag ist durchgehend ENGLISCH — Spalten UND Werte. (Diese Liste stand noch auf
# den deutschen Namen und war seit der Umstellung rot.)
_EXPORT_VOCAB = {
    "phase": {"expiring", "open", "planned"},
    "contract_nature": {"services", "supplies", "works"},
    "contract_nature_source": {"actual", "estimated"},
    "value_source": {"actual", "estimated", "unknown"},
    "timing_source": {"actual", "estimated", "uncertain", "unknown"},
    "incumbent_source": {"actual", "uncertain", None},
    "switch_chance": {"high", "medium", "low", "na"},
    "competition_level": {"low", "medium", "high", "na"},
    "competition_source": {"actual", "unknown", "na"},
    # Kontext aus dem `attributes`-Sammelfeld (eForms-Codes + Legacy-Labels auf EIN
    # englisches Vokabular gemappt). Waechst das Mapping, muss es hier mitwachsen —
    # sonst rutscht ein roher eForms-Code wie `cga-mun` ins Frontend.
    "regulatory_regime": {"vgv", "vob", "uvgo", "sektvo", "vsvgv", "konzvgv",
                          "eu_classic", None},
    "buyer_type": {"local_authority", "regional_authority", "regional_or_local",
                   "central_government", "body_public_law", "public_undertaking",
                   "subsidised_entity", "utility", "eu_institution",
                   "international_org", "other", None},
    "buyer_activity": {"general_public", "health", "economic_affairs", "transport",
                       "education", "environment", "defence", "social_protection",
                       "recreation_culture", "public_order", "utilities", "other", None},
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
    """band_source='default' → value_eur NULL (Frontend zeigt '—', schätzt nicht)."""
    con = duckdb.connect()
    bad = con.execute(
        f"SELECT count(*) FROM read_parquet('{G}/lead_export.parquet') "
        f"WHERE value_source='unknown' AND value_eur IS NOT NULL").fetchone()[0]
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
        f"WHERE slug LIKE 'd%' AND buyer_name IS NULL").fetchone()[0]
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


def test_cli_gold_builders_exist():
    """Jeder `gold.build_*`, den die CLI aufruft, muss es auch geben.

    Regression: `build_lead_cpv` wurde einmal versehentlich **ueber**
    `build_doe_buyer_profile` geschrieben. Der Aufruf blieb in `cli.py` stehen, und der
    Gold-Lauf brach danach jedes Mal mitten in der Pipeline mit `AttributeError` ab —
    nach `lead-export`, also erst wenn schon eine Stunde Rechenzeit verbrannt war.
    Dieser Test kostet Millisekunden und faengt genau das ab.
    """
    import re
    from pathlib import Path

    from govisor import gold

    src = Path(__file__).resolve().parent.parent / "govisor" / "cli.py"
    called = sorted(set(re.findall(r"\bgold\.(build_\w+)", src.read_text())))
    assert called, "cli.py ruft keine Gold-Builder auf — Regex kaputt?"
    missing = [n for n in called if not hasattr(gold, n)]
    assert not missing, f"cli.py ruft nicht existierende Builder: {missing}"


# ---- lead_lot: Inhalts-Layer --------------------------------------------------
@pytest.mark.skipif(not _has("lead_lot"), reason="lead_lot nicht gebaut")
def test_lead_lot_primary_key_is_complete():
    """(lead_id, lot_id) ist der Supabase-PK — beide non-null, Paar eindeutig.

    450 Lose tragen im Quell-XML keine LotID; `build_lead_lot` vergibt dort einen
    Ordinal-Fallback. Ohne den kippt das Upsert (PK darf nicht NULL sein).
    """
    con = duckdb.connect()
    tot, nulls, uni = con.execute(
        f"SELECT count(*), count(*) FILTER (WHERE lead_id IS NULL OR lot_id IS NULL), "
        f"count(DISTINCT concat(lead_id,'|',lot_id)) FROM read_parquet('{G}/lead_lot.parquet')"
    ).fetchone()
    assert nulls == 0, "PK-Spalten duerfen nie NULL sein"
    assert tot == uni, f"{tot-uni} doppelte (lead_id, lot_id) — Upsert waere mehrdeutig"


@pytest.mark.skipif(not (_has("lead_lot") and _has("lead_export")), reason="nicht gebaut")
def test_lead_lot_has_no_orphans():
    """Jedes Los muss auf einen existierenden Lead zeigen (FK ins Frontend)."""
    con = duckdb.connect()
    orphan = con.execute(
        f"SELECT count(*) FROM read_parquet('{G}/lead_lot.parquet') l "
        f"WHERE NOT EXISTS (SELECT 1 FROM read_parquet('{G}/lead_export.parquet') e "
        f"                  WHERE e.lead_id = l.lead_id)").fetchone()[0]
    assert orphan == 0


@pytest.mark.skipif(not (_has("lead_lot") and _has("lead_export")), reason="nicht gebaut")
def test_detailed_description_flag_counts_both_levels():
    """`has_detailed_description` muss Notice- UND Los-Text zaehlen.

    Gemessen: nur auf Notice-Ebene waeren 14,6 % „reich", mit Losen 32,9 %. Ein Flag,
    das die Los-Ebene ignoriert, versteckt im UI bei jedem 5. Lead vorhandenen Inhalt.
    """
    con = duckdb.connect()
    bad = con.execute(f"""
        SELECT count(*) FROM read_parquet('{G}/lead_export.parquet') e
        LEFT JOIN (SELECT lead_id, sum(coalesce(lot_description_length,0)) c
                   FROM read_parquet('{G}/lead_lot.parquet') GROUP BY 1) l USING (lead_id)
        WHERE e.has_detailed_description
              <> (coalesce(e.description_length,0) + coalesce(l.c,0) >= 1000)""").fetchone()[0]
    assert bad == 0, "Flag deckt sich nicht mit Notice+Los-Textlaenge"


def test_supabase_paging_respects_the_1000_row_cap():
    """`stale_ids` darf nie mehr als 1.000 Zeilen pro Request anfordern.

    Supabase/PostgREST deckelt eine Antwort bei 1.000 Zeilen (`db-max-rows`), unabhaengig
    vom Range-Header. Mit groesserer Schrittweite kaeme *immer* eine „kurze" Seite zurueck,
    die Paging-Schleife braeche nach der ersten ab — und der Abgleich meldete faelschlich
    „keine verwaisten Zeilen", statt abgelaufene Leads zu finden. Genau so ist es passiert.
    """
    import re
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "scripts" / "export_supabase.py").read_text()
    body = src.split("def stale_ids", 1)[1].split("\ndef ", 1)[0]
    steps = [int(m.replace("_", "")) for m in re.findall(r"step\s*,?[^=\n]*=\s*([\d_]+)", body)]
    assert steps, "keine Schrittweite in stale_ids gefunden — Regex kaputt?"
    assert max(steps) <= 1000, f"Schrittweite {max(steps)} > 1000 → Paging bricht ab"


def test_wikidata_population_is_current_not_historic():
    """Einwohnerzahlen muessen aktuell sein, nicht aus historischen Volkszaehlungen.

    Wikidata haelt zu deutschen Gemeinden 20–30 Einwohner-Statements zurueck bis 1871,
    und zum selben Ortsnamen oft ZWEI Items am selben Punkt: die Gemeinde (gepflegt,
    aktuell) und einen Ortsteil-Stub (nur Zensus 1987). Die erste Fassung nahm den
    naechstgelegenen und schrieb fuer Neusaess **139** statt 22.904 — 27 % aller
    angereicherten Kaeufer landeten unter 2.000 Einwohnern.

    Der Fix sortiert nach Stichtag VOR Entfernung. Dieser Test haelt das fest.
    """
    import duckdb
    path = "data/reference/buyer_external.parquet"
    if not os.path.exists(path):
        pytest.skip("buyer_external nicht gebaut")
    con = duckdb.connect()
    n, alt, ohne_datum = con.execute(
        f"SELECT count(population), "
        f"       count(*) FILTER (WHERE population_date < '2015'), "
        f"       count(*) FILTER (WHERE population IS NOT NULL AND population_date IS NULL) "
        f"FROM read_parquet('{path}')").fetchone()
    assert n > 0
    assert alt / n < 0.05, f"{alt} von {n} Einwohnerzahlen sind aelter als 2015"
    assert ohne_datum / n < 0.05, f"{ohne_datum} Einwohnerzahlen ohne Stichtag"


@pytest.mark.skipif(not _has("lead_export"), reason="lead_export nicht gebaut")
def test_lead_export_documents_url_is_a_link():
    """`documents_url` ersetzt fuer offene Leads unser schwaches `portal_url` (96,6 % vs
    44,5 %, DÖE 0 %). Wenn dort etwas anderes als eine http-URL landet, ist das Mapping
    auf den falschen `attributes`-Pfad gelaufen."""
    con = duckdb.connect()
    bad, total = con.execute(f"""
        SELECT count(*) FILTER (WHERE documents_url NOT LIKE 'http%'),
               count(*) FILTER (WHERE documents_url IS NOT NULL)
        FROM read_parquet('{G}/lead_export.parquet')""").fetchone()
    assert total > 0, "documents_url komplett leer — Pfad-Mapping gebrochen"
    assert bad == 0, f"{bad} documents_url ohne http-Schema"


@pytest.mark.skipif(not _has("lead_export"), reason="lead_export nicht gebaut")
def test_is_nationwide_never_null():
    """Das Flag steuert einen FILTER (geo.nationwide_clause). NULL wuerde dort still zu
    „nicht bundesweit" — deshalb ist es im Export hart auf true/false normiert."""
    con = duckdb.connect()
    n = con.execute(f"SELECT count(*) FROM read_parquet('{G}/lead_export.parquet') "
                    f"WHERE is_nationwide IS NULL").fetchone()[0]
    assert n == 0


def test_notice_id_normalization_unifies_archive_and_live():
    """notice_id-Waisen-Bug: Archiv (00450024_2026) und Live (450024-2026) derselben
    TED-Notice müssen auf DIESELBE kanonische ID abbilden — sonst verwaisen Gold-Zeilen
    am Monatswechsel. publication_number muss TED-korrekt bleiben."""
    from govisor.schema import normalize_notice_id as nz, publication_number_from_id as pub
    assert nz("00450024_2026") == nz("450024-2026") == "450024_2026"
    assert nz(nz("450024-2026")) == nz("450024-2026")          # idempotent
    assert pub(nz("00450024_2026")) == "450024-2026"           # TED-Publikationsnummer intakt
    assert nz("nicht-eine-notice") == "nicht-eine-notice"      # Unbekanntes unverändert
