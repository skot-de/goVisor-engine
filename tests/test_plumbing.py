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


def test_simap_downloader_wired_and_cursor_encoded():
    """simap-Downloader: CLI verdrahtet, Modul-API da, und der Paginierungs-Cursor wird
    URL-kodiert. Regression: der lastItem-Cursor enthält ein '|' (z. B. '20260728|33405') —
    unkodiert liefert die API leer, die Schleife bricht nach Seite 1 ab (kein Backfill)."""
    from govisor import cli, simap

    parser = cli.build_parser()
    args = parser.parse_args(["ingest-simap", "--max-pages", "2"])
    assert args.command == "ingest-simap" and args.country == "CH" and args.max_pages == 2

    for fn in ("download", "available_months"):
        assert hasattr(simap, fn), f"simap.{fn} fehlt"

    url = simap._search_url("20260728|33405")
    assert "%7C" in url and "|" not in url, "lastItem-Cursor nicht URL-kodiert"
    assert simap._search_url(None).count("lastItem") == 0  # Seite 1 ohne Cursor
    assert simap._month_of({"publicationDate": "2026-07-28"}) == "2026-07"


def test_simap_parser_maps_award_richness():
    """simap-Parser: Gewinner/Preis/Bieterzahl in die Standard-Slots, CH-Spezifika nach
    attributes (Catch-all → speist l.extras). Locks das Feld-Mapping ohne Netz."""
    from govisor import simap

    rec = {
        "summary": {"id": "proj-1", "publicationId": "pub-1", "publicationNumber": "42-02",
                    "pubType": "award", "publicationDate": "2026-07-10",
                    "title": {"de": "Testbau Zürich"}},
        "detail": {
            "base": {"title": {"de": "Testbau Zürich"}, "publicationDate": "2026-07-10",
                     "publicationNumber": "42-02", "projectId": "proj-1", "creationLanguage": "de",
                     "publicationTed": True, "stateContractArea": True},
            "procurement": {"cpvCode": {"code": "45000000"}, "orderType": "construction",
                            "orderDescription": {"de": "<p>Neubau</p>"},
                            "additionalCpvCodes": [{"code": "45210000"}],
                            "bkpCodes": [{"code": "214", "label": {"de": "Holzbau"}}],
                            "orderAddress": {"cantonId": "ZH", "postalCode": "8001"}},
            "decision": {"numberOfSubmissions": 4, "awardDecisionDate": "2026-06-01",
                         "vendors": [{"vendorName": "Muster AG", "vendorId": "v1",
                                      "price": {"price": 152652.35, "currency": "chf"},
                                      "vendorAddress": {"cantonId": "LU", "city": "Horw"}}]},
        },
    }
    t = simap.parse_publication(rec)
    n = t["notices"][0]
    assert n["notice_id"] == "pub-1" and n["country"] == "CH" and n["schema_gen"] == "simap"
    assert n["notice_kind"] == "can" and n["cpv_main"] == "45000000"
    assert n["contract_nature"] == "works" and n["performance_nuts"] == "ZH"
    assert n["final_value"] == 152652.35 and n["value_currency"] == "CHF"
    assert t["awards"][0]["winner_name"] == "Muster AG" and t["awards"][0]["num_tenders"] == 4
    assert any(p["role"] == "winner" and p["name"] == "Muster AG" for p in t["notice_parties"])
    assert {c["cpv_code"] for c in t["notice_cpv"]} == {"45000000", "45210000"}
    paths = {a["path"] for a in t["attributes"]}
    assert "simap/publicationTed" in paths and "simap/bkp" in paths and "simap/stateContractArea" in paths


def test_simap_gold_bridge_wired():
    """CH-Gold-Brücke: CLI --gold verdrahtet, build_ch_gold da, tender→'cn' Mapping (nur
    offene Ausschreibungen werden Leads, nicht Zuschläge)."""
    from govisor import cli, simap

    args = cli.build_parser().parse_args(["ingest-simap", "--max-pages", "0", "--gold"])
    assert args.gold is True and args.command == "ingest-simap"
    assert hasattr(simap, "build_ch_gold")
    # notice_kind-Mapping: Ausschreibung → cn (wird Lead), Zuschlag → can (kein Lead)
    assert simap._KIND["tender"] == "cn" and simap._KIND["award"] == "can"


def test_at_bridge_wired_and_dim_plz_country_keyed():
    """AT-Gold-Brücke (build_at_gold) + CLI `gold --bridge` da; dim_plz nach (country, plz)
    verschlüsselt, damit AT/CH-4-stellige PLZ nicht kollidieren (1010 = Wien AT / Lausanne CH)."""
    import glob
    import duckdb
    from govisor import cli, gold

    assert hasattr(gold, "build_at_gold")
    args = cli.build_parser().parse_args(["gold", "--country", "AT", "--bridge"])
    assert args.bridge is True and args.country == "AT"

    dp = glob.glob("data/gold/DE/dim_plz.parquet")
    if dp:   # nur wenn dim_plz gebaut ist
        cols = [c[0] for c in duckdb.connect().execute(
            f"describe select * from read_parquet('{dp[0]}')").fetchall()]
        assert "country" in cols, "dim_plz braucht country-Spalte (AT/CH-PLZ-Kollision)"


@pytest.mark.skipif(not os.path.exists("data/gold/DE/dim_plz.parquet"),
                    reason="dim_plz nicht gebaut")
def test_at_gold_osb_dedup(tmp_path):
    """build_at_gold: atverg-OSB-Notices (oberschwellig, geflaggt via attributes 'atverg/schwelle'
    = 'OSB') werden ausgeschlossen (TED-AT deckt oberschwellig ab → Doppel-Leads vermeiden);
    TED-AT + atverg-USB bleiben. Ohne atverg-attributes ist der Filter ein No-op."""
    import shutil
    from datetime import date
    import pyarrow as pa
    import pyarrow.parquet as pq
    import duckdb
    from govisor import model, gold
    from govisor.config import Config

    FUT = date(2099, 1, 1)

    def notice(nid, gen):
        r = {f.name: None for f in model.TABLES["notices"]}
        r.update(notice_id=nid, title=f"x {nid}", schema_gen=gen, country="AT",
                 buyer_countries=["AT"], notice_kind="cn", submission_deadline=FUT,
                 cpv_main="45000000", year=2026, month=1)
        return r

    def write(table, rows):
        out = tmp_path / "silver" / "AT" / table / "year=2026" / "2026-x.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist(rows, schema=model.TABLES[table]), out)

    write("notices", [notice("123456_2026", "eforms"), notice("atv-1", "atverg"),
                      notice("atv-2", "atverg")])
    parties = []
    for nid in ("123456_2026", "atv-1", "atv-2"):
        p = {f.name: None for f in model.TABLES["notice_parties"]}
        p.update(notice_id=nid, role="buyer", seq=0, name="Stadt Wien", country="AT")
        parties.append(p)
    write("notice_parties", parties)
    write("awards", [])
    write("attributes", [{"notice_id": "atv-1", "path": "atverg/schwelle", "value": "OSB"},
                         {"notice_id": "atv-2", "path": "atverg/schwelle", "value": "USB"}])
    (tmp_path / "gold" / "DE").mkdir(parents=True, exist_ok=True)
    shutil.copy("data/gold/DE/dim_plz.parquet", tmp_path / "gold" / "DE" / "dim_plz.parquet")

    cfg = Config(countries=("AT",), data_dir=tmp_path)
    gold.build_at_gold(cfg, "AT")
    con = duckdb.connect()
    LE = (tmp_path / "gold" / "AT" / "lead_export.parquet").as_posix()
    ids = {r[0] for r in con.execute(f"SELECT lead_id FROM read_parquet('{LE}')").fetchall()}
    assert ids == {"123456_2026", "atv-2"}, f"OSB-Dedup falsch: {ids}"

    # No-op ohne attributes → OSB bleibt
    shutil.rmtree(tmp_path / "silver" / "AT" / "attributes")
    gold.build_at_gold(cfg, "AT")
    ids2 = {r[0] for r in con.execute(f"SELECT lead_id FROM read_parquet('{LE}')").fetchall()}
    assert "atv-1" in ids2, "ohne attributes muss der Filter No-op sein"


def test_source_registry_is_wellformed():
    """Quellen-Registry (govisor/sources.py): eindeutige IDs, gültige Connector/Status,
    Kennzahlen konsistent. Reiner Unit-Test — treibt CLI `sources` + Web-Quellen-Panel."""
    from govisor import sources
    ids = [s.id for s in sources.REGISTRY]
    assert len(ids) == len(set(ids)), "Quellen-IDs müssen eindeutig sein"
    for s in sources.REGISTRY:
        # Seit 2026-08-15 zwei Ebenen: Bekanntmachungen und Vergabeunterlagen. Jede benutzt
        # IHREN Connector-Namensraum — ein Doc-Abrufer unter CONNECTORS wuerde die
        # Connector-Zahl aufblaehen, ohne eine Bekanntmachung mehr zu liefern.
        erlaubt = sources.DOC_CONNECTORS if s.ebene == "unterlagen" else sources.CONNECTORS
        assert s.connector in erlaubt, f"{s.id}: unbekannter Connector {s.connector}"
        assert s.status in sources.STATUSES, f"{s.id}: unbekannter Status {s.status}"
        assert s.tier in ("oberschwellig", "unterschwellig", "beides"), f"{s.id}: Tier {s.tier}"
        assert s.ebene in ("bekanntmachung", "unterlagen"), f"{s.id}: Ebene {s.ebene}"
    summ = sources.summary()
    assert summ["connectors"] == len(sources.CONNECTORS)
    # ⚠ gegen die BEKANNTMACHUNGS-Ebene pruefen, nicht gegen by_status() — das spannt jetzt
    # beide Ebenen. Waere das hier nicht nachgezogen, zaehlte `quellen_live` die Abrufer mit.
    assert summ["quellen_live"] == len([s for s in sources.bekanntmachungen()
                                        if s.status == "live"])
    # DACH-Matrix: DE + CH beide Schwellen abgedeckt, AT ist die offene Arbeit
    dach = {(cc, tier): status for cc, tier, _, status in sources.dach_matrix()}
    assert dach[("DE", "oberschwellig")] == "live" and dach[("DE", "unterschwellig")] == "live"
    assert dach[("CH", "oberschwellig")] == "live" and dach[("CH", "unterschwellig")] == "live"
    assert dach[("AT", "unterschwellig")] in ("candidate", "prepared", "live")
    # Die Live-Quellen. ⚠ Die Registry hinkt dem Tageslauf hinterher: `govisor.dtvp` laeuft
    # dort und schreibt Silber, steht aber in KEINEM Registry-Eintrag; `atverg` steht auf
    # "prepared", obwohl `ingest-atverg` taeglich laeuft. Beides ist beim Eintragen von
    # NetServer aufgefallen und bewusst nicht mit-korrigiert — der Status einer fremden
    # Quelle ist eine Produktaussage, keine Aufraeumarbeit nebenbei.
    live_ids = {s.id for s in sources.bekanntmachungen() if s.status == "live"}
    assert live_ids == {"ted-de", "doe-de", "simap-ch", "netserver-de"}
    # AT ist als Brücke vorbereitet (deckt sich mit build_at_gold)
    assert any(s.id == "ted-at" and s.status == "prepared" for s in sources.REGISTRY)


def test_muni_key_ags_matching():
    """Municipality-Merge (AGS-artig): kommunale Behörden-Fragmente → EIN Gemeinde-Schlüssel;
    Stadt vs. Landkreis getrennt; verschiedene Gemeinden getrennt; Firmen/PLZ-lose → None."""
    from govisor.gold import _muni_key
    pk = {"80331": ("Bayern", "Kreisfreie Stadt München"),
          "85540": ("Bayern", "Landkreis München"), "01067": ("Sachsen", "Kreisfreie Stadt Dresden")}
    k_muc = _muni_key("Stadt München", {"80331"}, pk)
    assert k_muc and k_muc == _muni_key("Landeshauptstadt München", {"80331"}, pk) \
        == _muni_key("STADT MÜNCHEN, Baureferat", {"80331"}, pk)   # Fragmente → ein Key
    assert _muni_key("Landkreis München", {"85540"}, pk) != k_muc  # Kreis ≠ Stadt
    assert _muni_key("Gemeinde Haar", {"85540"}, pk) != k_muc      # andere Gemeinde
    assert _muni_key("Stadt Dresden", {"01067"}, pk) != k_muc      # andere Stadt
    assert _muni_key("Müller GmbH", {"80331"}, pk) is None         # keine Behörde
    assert _muni_key("Stadt Neustadt", set(), pk) is None          # ohne PLZ keine Disambiguierung


def test_normalize_national_id_leitweg():
    """national_id-Normalisierung: Leitweg-ID (mit/ohne Schema-Präfix) → EIN Schlüssel;
    USt-IdNr normalisiert; Müll (UUID/TED-intern/Kurzzahl/Bindestrich) → None (Name-Fallback)."""
    from govisor.gold import normalize_national_id as N
    # Leitweg-ID: Präfix-Varianten fallen auf denselben Schlüssel
    assert N("0204:991-00199-39") == N("991-00199-39") == "leitweg:991-00199-39"
    assert N("08-A9866-40") == "leitweg:08-A9866-40"
    # Grobadressierung mit vollem AGS/Regionalschlüssel (4–12 Stellen), nicht nur 2–3:
    assert N("09162000-ZRE1000000-09") == "leitweg:09162000-ZRE1000000-09"   # AGS München
    assert N("2660:05111-32003-71") == N("05111-32003-71") == "leitweg:05111-32003-71"  # Düsseldorf
    assert N("161000000000-1000-50") == "leitweg:161000000000-1000-50"        # voller 12-Stellen-RS
    # USt-IdNr (Leerzeichen egal)
    assert N("DE311803096") == N("DE 311803096") == "vat:DE311803096"
    # Müll → None
    for junk in ("t:053418393542", "-", "6850", "2f383c64-f0b3-49a4-a9c3-8030a816c4fd", "", None):
        assert N(junk) is None, junk
    # sonstige Register-ID bleibt (nur Whitespace weg)
    assert N("HRB 12345") == "HRB12345"


def test_consolidate_by_shared_name_plz():
    """Clean-Name-Merge (PLZ-gegated): nur-Name-Fragmente öffentlicher Stellen mit gleichem norm UND
    geteilter PLZ verschmelzen; verschiedene PLZ (zwei Städte) NICHT; `already`-Entities übersprungen."""
    from govisor.gold import ResolvedEntity, Method, _consolidate_by_shared_name_plz

    def E(eid, norm, method=Method.NAME_ONLY):
        return ResolvedEntity(entity_id=eid, canonical_name=norm.upper(), method=method,
                              confidence=0.4, national_id=None, source_names=(norm,), norm=norm)
    ents = {e.entity_id: e for e in [
        E("a1", "ochtumverband"), E("a2", "ochtumverband"), E("a3", "ochtumverband"),
        E("b1", "stadtwerke"), E("b2", "stadtwerke"),
        E("c1", "amt fuer hochbau", Method.HR_EXACT),   # Register-Anker → nicht nur_name
    ]}
    plz = {"a1": {"28844"}, "a2": {"28844"}, "a3": {"12345"},   # a1+a2 gleiche PLZ, a3 andere
           "b1": {"80331"}, "b2": {"50667"}}                    # zwei Städte → getrennt
    mm = _consolidate_by_shared_name_plz(ents, plz, already=set())
    assert mm.get("a2") == "a1", "gleicher Name + PLZ → merge"
    assert "a3" not in mm, "andere PLZ → kein merge"
    assert "b2" not in mm and "b1" not in mm, "zwei Städte gleichen Namens bleiben getrennt"
    assert "c1" not in mm, "Register-Entity ist kein nur_name-Merge-Kandidat"
    # `already` (schon per ID verschmolzen) wird übersprungen
    mm2 = _consolidate_by_shared_name_plz(ents, plz, already={"a1", "a2"})
    assert "a2" not in mm2


def test_consolidate_by_leitweg():
    """Leitweg-Anker: Entitäten mit derselben (nicht-generischen, eindeutigen) Leitweg-ID mergen;
    register-getragenes Ziel bevorzugt; generischer Platzhalter (>80 Namen) + mehrdeutige raus."""
    from govisor.gold import ResolvedEntity, Method, _consolidate_by_leitweg

    def E(eid, norm, method=Method.NAME_ONLY):
        return ResolvedEntity(entity_id=eid, canonical_name=norm.upper(), method=method,
                              confidence=0.4, national_id=None, source_names=(norm,), norm=norm)
    L = "leitweg:05111-31001-70"       # Düsseldorf
    M = "leitweg:14713000-SV01-88"     # Leipzig
    GEN = "leitweg:991-1405-10"        # generischer Platzhalter
    ents = {e.entity_id: e for e in [
        E("d1", "landeshauptstadt duesseldorf"),
        E("d2", "stadtkaemmerei duesseldorf"),
        E("d3", "amt fuer umwelt duesseldorf", Method.TED_NATIONAL_ID),  # Register-Anker → Ziel
        E("x1", "irgendwas"),          # mehrdeutig: zwei Leitwegs → überspringen
        E("g1", "stadt a"), E("g2", "stadt b"),   # nur unter generischem Platzhalter
        E("s1", "einzelamt leipzig"),  # allein unter M → kein Merge (Cluster <2)
    ]}
    leitweg_of = {
        "d1": {L}, "d2": {L}, "d3": {L},
        "x1": {L, M},                  # mehrdeutig
        "g1": {GEN}, "g2": {GEN},
        "s1": {M},
    }
    # GEN künstlich generisch machen: >80 distinkte Namen vortäuschen
    for i in range(90):
        eid = f"gen{i}"
        ents[eid] = E(eid, f"behoerde nr {i}")
        leitweg_of[eid] = {GEN}

    mm, dropped = _consolidate_by_leitweg(ents, leitweg_of, already=set())
    assert mm.get("d1") == "d3" and mm.get("d2") == "d3", "Register-Anker d3 ist Ziel"
    assert "d3" not in mm, "Ziel selbst wird nicht gemappt"
    assert "x1" not in mm, "mehrdeutige Entität (2 Leitwegs) übersprungen"
    assert "g1" not in mm and "g2" not in mm, "generischer Platzhalter mergt nicht"
    assert "s1" not in mm, "Einzel-Cluster (<2) mergt nicht"
    assert any(lw == GEN for lw, _ in dropped), "generischer Platzhalter wird protokolliert"
    # `already` schützt bereits verschmolzene Entitäten
    mm2, _ = _consolidate_by_leitweg(ents, leitweg_of, already={"d1"})
    assert "d1" not in mm2


def test_consolidate_by_vat():
    """USt-IdNr-Anker mit Token-Guard: gleiche VAT + gemeinsamer signifikanter Namens-Token → merge;
    geteilte VG-VAT (fremde Gemeinden, kein gemeinsamer Token) übersprungen; register-Ziel bevorzugt."""
    from govisor.gold import ResolvedEntity, Method, _consolidate_by_vat

    def E(eid, norm, method=Method.NAME_ONLY):
        return ResolvedEntity(entity_id=eid, canonical_name=norm.upper(), method=method,
                              confidence=0.4, national_id=None, source_names=(norm,), norm=norm)
    V1 = "vat:DE143296597"   # Heidelberg (gemeinsamer Token 'heidelberg')
    V2 = "vat:DE309506861"   # geteilte VG-VAT: drei verschiedene Gemeinden
    V4 = "vat:DE111111111"   # Treuhänder-Fall: register-Agent + nur-Name-Basis-Behörde
    ents = {e.entity_id: e for e in [
        E("h1", "heidelberg"), E("h2", "heidelberg tiefbauamt"),
        E("v1", "bous"), E("v2", "eurasburg"), E("v3", "langerringen"),  # kein gemeinsamer Token
        E("a1", "musterstadt"),                                          # Basis-Behörde (nur-Name)
        E("a2", "treuhand verwaltung musterstadt", Method.TED_NATIONAL_ID),  # register-Verwalter
        E("x1", "solo"),
    ]}
    vat_of = {"h1": {V1}, "h2": {V1},
              "v1": {V2}, "v2": {V2}, "v3": {V2},
              "a1": {V4}, "a2": {V4},
              "x1": {V1, V4}}                       # mehrdeutig
    mm, skipped = _consolidate_by_vat(ents, vat_of, already=set())
    assert mm.get("h2") == "h1", "gleiche VAT + Token 'heidelberg' → merge"
    assert "v1" not in mm and "v2" not in mm and "v3" not in mm, "geteilte VG-VAT ohne Token → kein merge"
    assert skipped >= 1, "geteilte VAT wird gezählt"
    assert "x1" not in mm, "mehrdeutige Entität (2 VATs) übersprungen"
    # Treuhänder-Fall: register-Agent a2 bleibt Merge-Ziel (behält national_id), aber das ANZEIGE-
    # Label kommt aus der knappsten Basis-Behörde a1 → nicht der Verwalter ist das Gesicht.
    assert mm.get("a1") == "a2", "Basis-Behörde merged in register-Ziel"
    assert ents["a2"].canonical_name == ents["a1"].canonical_name, "Label = Basis-Behörde, nicht Verwalter"
    mm2, _ = _consolidate_by_vat(ents, vat_of, already={"h2"})
    assert "h2" not in mm2, "already schützt"


def test_compress_merge_map_chains():
    """Ketten-Kompression: A→B→C wird zu A→C, B→C (verhindert party_entity-Waisen, wenn ein
    Merge-Ziel selbst später Quelle wird). Zyklus hängt nicht auf."""
    from govisor.gold import _compress_merge_map
    out = _compress_merge_map({"A": "B", "B": "C", "X": "Y"})
    assert out == {"A": "C", "B": "C", "X": "Y"}
    # kein Wert ist noch ein Key (sonst Waise beim einstufigen Apply)
    assert not (set(out.values()) & set(out.keys()))
    cyc = _compress_merge_map({"A": "B", "B": "A"})   # darf nur nicht aufhängen
    assert set(cyc.keys()) == {"A", "B"}


def test_lead_predecessor_wired():
    """build_lead_predecessor (offene Leads → Vorgänger-Zuschlag → Incumbent+Kette) existiert + im
    Gold-Lauf verdrahtet. Wo gebaut: Schema + chain_depth≥1 + Konfidenz gesetzt."""
    from govisor import gold
    assert hasattr(gold, "build_lead_predecessor")
    # im cmd_gold-Lauf aufgeführt
    import inspect
    from govisor import cli
    assert "build_lead_predecessor" in inspect.getsource(cli)
    lp = "data/gold/DE/lead_predecessor.parquet"
    if os.path.exists(lp):
        con = duckdb.connect()
        cols = [c[0] for c in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{lp}')").fetchall()]
        for need in ("lead_id", "incumbent_name", "n_bidders", "competition_level",
                     "chain_depth", "incumbent_since_year", "incumbent_confidence"):
            assert need in cols, f"lead_predecessor fehlt Spalte {need}"
        bad = con.execute(f"SELECT count(*) FROM read_parquet('{lp}') "
                          f"WHERE chain_depth < 1 OR incumbent_name IS NULL").fetchone()[0]
        assert bad == 0, "jede Zeile braucht Incumbent + chain_depth>=1"


def test_clean_display_name():
    """Anzeige-Namen-Bereinigung: generische Hoheits-Präfixe → vertretene Stelle auflösen,
    spezifische Präfixe behalten, KOMPLETT-GROSS → Titel-Schreibung, idempotent, konservativ."""
    from govisor.names import clean_display_name as C
    # Generischer Hoheits-Träger → vertretene Stelle (führender Artikel weg)
    assert C("Bundesrepublik Deutschland, vertreten durch das Bundesministerium für Gesundheit") \
        == "Bundesministerium für Gesundheit"
    assert C("Land Berlin, vertreten durch die Senatsverwaltung für Stadtentwicklung") \
        == "Senatsverwaltung für Stadtentwicklung"
    # Vertretungskette gekappt (erste Stelle nach dem Hoheits-Träger)
    assert C("Bundesrepublik Deutschland vertreten durch: Deutscher Bundestag vertreten durch: BBR") \
        == "Deutscher Bundestag"
    # Spezifischer Präfix → Präfix behalten, Vertretung droppen
    assert C("DB Netz AG, vertreten durch die DB Netz AG Regionalbereich Südost") == "DB Netz AG"
    # Casing: KOMPLETT GROSS → Titel; Rechtsform + Partikel korrekt
    assert C("STADT KÖLN") == "Stadt Köln"
    assert C("LANDESHAUPTSTADT STUTTGART, AMT FÜR HOCHBAU UND GEBÄUDEWIRTSCHAFT") \
        == "Landeshauptstadt Stuttgart, Amt für Hochbau und Gebäudewirtschaft"
    assert C("MUSTER BAU GMBH") == "Muster Bau GmbH"
    # gemischte Schreibweise bleibt unangetastet
    assert C("Max-Planck-Gesellschaft zur Förderung der Wissenschaften e.V.") \
        == "Max-Planck-Gesellschaft zur Förderung der Wissenschaften e.V."
    assert C("Stadt München") == "Stadt München"
    # idempotent + robust gegen None/leer
    assert C(C("BUNDESREPUBLIK DEUTSCHLAND, VERTRETEN DURCH DAS BMI")) \
        == C("BUNDESREPUBLIK DEUTSCHLAND, VERTRETEN DURCH DAS BMI")
    assert C(None) is None and C("") == ""


def test_docsignals_extraction():
    """Dokument-Signal-Extraktion (Vergabeunterlagen-Volltext → Aufwand-Signale): Bürgschaft,
    Bindefrist (beide Wortstellungen), Eignung+Zertifikate, Zuschlagsgewichte, Nebenangebote."""
    from govisor.docsignals import extract_signals as X
    s = X("Die Bieter haben eine Vertragserfüllungsbürgschaft in Höhe von 5 % vorzulegen. "
          "Die Angebote sind für 60 Kalendertage gebunden. Vorzulegen sind Referenzen, eine "
          "Eigenerklärung zur Zuverlässigkeit und ein Zertifikat nach DIN EN ISO 9001. "
          "Der Preis wird mit 70 % und die Qualität mit 30 % gewichtet. Nebenangebote sind nicht "
          "zugelassen. Es handelt sich um eine Rahmenvereinbarung.")
    assert s["guarantee_required"] is True
    assert s["binding_days"] == 60
    assert s["eligibility_count"] >= 3 and "ISO 9001" in s["certificates"]
    assert s["award_weights"] == {"preis": 70, "qualität": 30}
    assert s["variants_allowed"] is False and s["framework"] is True
    # Verzicht sticht: explizites Nein → False, nicht True
    assert X("Auf eine Sicherheitsleistung wird verzichtet.")["guarantee_required"] is False
    # leerer/nichtssagender Text → keine erfundenen Signale
    assert X("Guten Tag, anbei die Datei.") == {}
    assert X("") == {}


def test_docpipe_extracts_and_recurses(tmp_path):
    """Dokument-Pipeline: Text aus TXT/HTML/DOCX, Rekursion durch verschachtelte ZIPs, Status-Flags.
    Reiner Unit-Test mit synthetischem ZIP (kein Netz, keine echten Dokumente nötig)."""
    import io
    import zipfile
    from govisor import docpipe, cli

    # DOCX = ZIP mit word/document.xml
    docx = io.BytesIO()
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr("word/document.xml", "<w:p>Leistungs<w:t>beschreibung</w:t> Bau</w:p>")
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("tief.txt", "verschachtelter Text")
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as z:
        z.writestr("a.txt", "Angebotsfrist 2026")
        z.writestr("b.html", "<html><body>Eignung <b>Kriterien</b></body></html>")
        z.writestr("c.docx", docx.getvalue())
        z.writestr("nested.zip", inner.getvalue())
        z.writestr("scan.pdf", b"%PDF-1.4 kein Text")   # unlesbare "PDF" → image_only/empty
    p = tmp_path / "Vergabeunterlagen_CX1.zip"
    p.write_bytes(outer.getvalue())

    rows = {r["file"].split("::")[-1]: r for r in docpipe.process_zip(p)}
    assert "verschachteltes Text" in rows["tief.txt"]["text"] or "verschachtelter" in rows["tief.txt"]["text"]
    assert "Angebotsfrist" in rows["a.txt"]["text"]
    assert "Kriterien" in rows["b.html"]["text"]
    assert "beschreibung" in rows["c.docx"]["text"]
    assert rows["a.txt"]["status"] == "ok"
    # scan.pdf ohne Textebene → nicht "ok"
    assert rows["scan.pdf"]["status"] in ("image_only", "empty")
    args = cli.build_parser().parse_args(["index-docs", "--country", "DE"])
    assert args.command == "index-docs"


def test_docfetch_cosinex_url_parsing():
    """cosinex/DTVP-Dokument-Fetcher: URL-Erkennung + Archiv-ZIP-Endpoint (reverse-engineert,
    login-frei). Host/Base(Satellite|VMPSatellite)/CX korrekt extrahiert; Nicht-cosinex abgelehnt."""
    from govisor import docfetch, cli
    assert docfetch.is_cosinex("https://www.dtvp.de/Satellite/notice/CXP4Y6YMYCG/documents")
    assert docfetch.is_cosinex("https://vergabemarktplatz.brandenburg.de/VMPSatellite/notice/CX9/documents")
    assert not docfetch.is_cosinex("https://www.subreport.de/E13767982")
    assert not docfetch.is_cosinex("https://www.evergabe.de/unterlagen/x")
    m = docfetch._COSINEX_RE.match("https://www.dtvp.de/Satellite/notice/CXP4Y6YMYCG/documents")
    assert m.group("origin") == "https://www.dtvp.de" and m.group("base") == "Satellite"
    assert m.group("cx") == "CXP4Y6YMYCG"
    assert docfetch._zip_url("https://www.dtvp.de", "Satellite", "CXP4Y6YMYCG") == (
        "https://www.dtvp.de/Satellite/public/company/project/CXP4Y6YMYCG/de/"
        "documents/archive/Vergabeunterlagen_CXP4Y6YMYCG.zip")
    # VMPSatellite-Portale (Landes-/Kommunalportale) nutzen denselben Endpoint mit ihrem Base
    assert "/VMPSatellite/public/company/project/CX9/" in docfetch._zip_url(
        "https://vergabemarktplatz.brandenburg.de", "VMPSatellite", "CX9")
    args = cli.build_parser().parse_args(["fetch-docs", "--limit", "10"])
    assert args.command == "fetch-docs" and args.limit == 10


def test_atverg_connector_wired():
    """OffeneVergaben.at-Connector (govisor/atverg.py): CLI `ingest-atverg` + notice_kind-Mapping
    (Kerndaten-art → cn/can) + contract_nature-Vokabular. Reiner Unit-Test."""
    from govisor import atverg, cli
    assert hasattr(atverg, "download") and hasattr(atverg, "build_silver")
    args = cli.build_parser().parse_args(["ingest-atverg", "--silver"])
    assert args.command == "ingest-atverg" and args.country == "AT" and args.silver is True
    # contract_nature-Mapping deckt die gemessenen auftragsart-Werte ab
    assert atverg._NATURE["Bauauftrag"] == "works"
    assert atverg._NATURE["Dienstleistungsauftrag"] == "services"
    assert atverg._NATURE["Lieferauftrag"] == "supplies"
    # ZIP-Link-Regex trifft das gemessene URL-Muster (Zeitstempel+Hash)
    assert atverg._ZIP_RE.search(
        "x https://offenevergaben.at/tmp/kerndaten_dailydump_202607282230_wnldvvr2.zip y")


def test_normalize_notice_id_canonical_and_idempotent():
    """Beide Ingest-Formen (Archiv zero-padded ``_``, Live/DÖE ``-``) müssen auf DIESELBE
    kanonische Form fallen, sonst verwaisen Gold-Zeilen beim Monatswechsel. Reiner Unit-Test."""
    from govisor.schema import normalize_notice_id as N
    assert N("00450024_2026") == "450024_2026"     # Archiv (zero-padded, Unterstrich)
    assert N("450024-2026") == "450024_2026"        # Live (Bindestrich)
    assert N("450024_2026") == "450024_2026"        # schon kanonisch
    assert N(N("00450024_2026")) == N("00450024_2026")  # idempotent
    # DÖE-Namensraum (UUID / reine Zahl) bleibt unangetastet — sonst Kollision mit TED
    assert N("2f383c64-f0b3-49a4-a9c3-8030a816c4fd") == "2f383c64-f0b3-49a4-a9c3-8030a816c4fd"
    assert N("19572346") == "19572346"


@pytest.mark.skipif(not os.path.exists("data/silver/DE/notices"),
                    reason="Silber nicht gebaut")
def test_silver_gold_notice_ids_are_canonical():
    """Nach der Migration (scripts/normalize_notice_ids.py) darf KEINE TED-Format-ID
    (``<zahl><trenner><jahr>``) in nicht-kanonischer Form (Bindestrich / führende Null) in
    Silber-notices oder Gold-leads stehen. DÖE-UUIDs matchen das Muster nicht → ausgenommen."""
    con = duckdb.connect()
    canon = r"regexp_replace({c}, '^0*([0-9]+)[-_]([0-9]{{4}})$', '\1_\2')"
    pat = "'^0*[0-9]+[-_][0-9]{4}$'"
    bad_sil = con.execute(
        f"SELECT count(*) FROM read_parquet('data/silver/DE/notices/*/*.parquet', hive_partitioning=1) "
        f"WHERE regexp_matches(notice_id, {pat}) AND notice_id <> {canon.format(c='notice_id')}"
    ).fetchone()[0]
    assert bad_sil == 0, f"{bad_sil} nicht-kanonische TED-notice_ids in Silber (Migration erneut laufen lassen)"
    if _has("leads"):
        bad_g = con.execute(
            f"SELECT count(*) FROM read_parquet('{G}/leads.parquet') "
            f"WHERE regexp_matches(lead_id, {pat}) AND lead_id <> {canon.format(c='lead_id')}"
        ).fetchone()[0]
        assert bad_g == 0, f"{bad_g} nicht-kanonische lead_ids in Gold"

def test_silver_month_files_do_not_shadow_each_other():
    """Pro Monat und Tabelle darf es NICHT gleichzeitig `<monat>.parquet` und
    `<monat>-live.parquet` geben.

    Der Silber-Glob liest beide; enthalten sie dieselben Notices, stehen alle Zeilen
    doppelt — und zwar erst in Gold sichtbar, wo der Käufer-Join fan-out erzeugt.
    Genau so passiert am 2026-08-10: eine Testdatei `2026-08.parquet` blieb neben dem
    echten `2026-08-live.parquet` liegen (nur die notices-Tabelle war aufgeräumt worden,
    die anderen acht nicht). Ergebnis: 128 Notices mit doppelter Käufer-Partei, daraus
    220.756 statt 77.746 lead_export-Zeilen. Silber selbst war dabei fehlerfrei — die
    Dublette entstand erst durch das Nebeneinander zweier Dateien.

    Dieser Test kostet Millisekunden und fängt das ab, bevor eine Stunde Gold-Rechenzeit
    darauf verschwendet wird.
    """
    from pathlib import Path

    root = Path("data/silver")
    if not root.exists():
        pytest.skip("Silber nicht gebaut")
    kollisionen = []
    for tabelle in sorted(root.glob("*/*")):
        if not tabelle.is_dir():
            continue
        for jahr in tabelle.glob("year=*"):
            monate = {p.stem for p in jahr.glob("*.parquet")}
            for m in monate:
                if m.endswith("-live") and m[:-5] in monate:
                    kollisionen.append(f"{jahr}/{m[:-5]}(.parquet + -live.parquet)")
    assert not kollisionen, (
        "Monatsdatei und -live-Datei nebeneinander → doppelte Zeilen im Silber-Glob:\n  "
        + "\n  ".join(kollisionen[:10]))


def test_tageslauf_baut_gold_fuer_jedes_land_das_er_holt():
    """Jede Quelle, die der Tageslauf holt, muss auch ihr Gold neu bauen.

    Gefunden am 2026-08-10: der Runner holte AT (OffeneVergaben, TED-AT) und CH (simap,
    TED-CHE) TÄGLICH ins Silber, baute aber nur DE-Gold. Die österreichischen und
    Schweizer Leads im Frontend hingen damit an dem Zeitpunkt, an dem zuletzt jemand die
    Brücke von Hand gestartet hatte — während das Silber darunter weiterlief. Von aussen
    sah beides frisch aus.

    Dieselbe Fehlerklasse hat am selben Tag zweimal zugeschlagen (export_strategie ohne
    Aufruf, ted_dedup ohne Leser). Der Test nagelt die Kopplung fest: wer ingested, baut.
    """
    from pathlib import Path

    runner = (Path(__file__).resolve().parent.parent / "scripts" / "daily_leads.sh").read_text()
    # Seit 2026-08-13 baut `build_dach_gold.py` beide Länder mit der vollen Pipeline; die
    # schmalen Brücken (`gold --bridge` / `build_ch_gold`) sind Alt-Pfade und stehen nicht
    # mehr im Tageslauf. Die Kopplung „wer ingested, baut" gilt unverändert — nur der Bauer
    # heisst anders.
    for land, ingest, goldbau in [
        ("AT", "ingest-atverg", "build_dach_gold.py"),
        ("CH", "ingest-simap", "build_dach_gold.py"),
    ]:
        if ingest not in runner:
            continue                     # Quelle nicht (mehr) im Tageslauf → nichts zu bauen
        assert goldbau in runner, (
            f"{land} wird im Tageslauf geholt ({ingest}), aber sein Gold nie neu gebaut "
            f"({goldbau} fehlt) — die {land}-Leads frieren still ein.")


def test_dubletten_filter_kommt_im_gold_an():
    """Der Dublettenfilter muss im Gold ankommen, nicht nur eine Datei erzeugen.

    `dedupe_ch_sources.py` schrieb wochenlang `ted_dedup.parquet`, das kein einziger
    Konsument las — der Filter lief, wirkte aber nicht. Beide Quellskripte sind seit
    2026-08-13 geloescht und durch die zentrale Firewall ersetzt; die Verdrahtung ihrer
    Nachfolger ist hier festgenagelt, damit die Fehlerklasse nicht zurueckkommt.

    Der atverg-Wertetransfer ist dabei bewusst ENTFALLEN. Seine Begruendung („69,8 % gegen
    11,0 % Wertabdeckung") ist ueber alle Bekanntmachungsarten gerechnet und wird von den
    ZUSCHLAEGEN getragen: nachgemessen fuehrt atverg bei `can` 98,4 % Werte, bei `cn`
    **0,0 %**. Fuer offene Ausschreibungen kann atverg also gar nichts beisteuern.
    """
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent

    for datei, funktion in (("govisor/gold.py", "def build_at_gold"),
                            ("govisor/simap.py", "def build_ch_gold")):
        quelle = (root / datei).read_text(encoding="utf-8")
        kopf = quelle[quelle.index(funktion):]
        # `build_ch_gold` ist die letzte Funktion in simap.py — dann bis Dateiende.
        ende = kopf.find("\ndef ", 10)
        kopf = kopf[:ende] if ende > 0 else kopf
        assert "notice_duplicates.parquet" in kopf, f"{funktion} liest die Firewall nicht"
        # Seit 2026-08-14 ueber den gemeinsamen Helfer, nicht als eigene SQL-Kopie: die
        # Bruecken hatten den Ausschluss OHNE die Master-Bedingung, also die gefaehrliche
        # Haelfte der Regel. Der Test prueft die Verdrahtung, nicht den Wortlaut.
        assert ("duplicate_id" in kopf or "_redundante_zweitquelle_sql" in kopf), \
            f"{funktion} schliesst keine Dubletten aus"
        # Die Belegstufe steht seit der Zusammenfuehrung im Helfer; wer ihn ruft, hat sie.
        if "_redundante_zweitquelle_sql" not in kopf:
            assert "kaeufer_und_titel" in kopf, f"{funktion} prueft die Belegstufe nicht"

    mp = (root / "scripts" / "build_marktpuls.py").read_text(encoding="utf-8")
    assert "notice_duplicates.parquet" in mp, "Marktpuls liest die Firewall nicht"
    # Nur der CODE zaehlt — im Docstring bleiben die alten Namen als Herkunftsnotiz stehen,
    # und die ist der Grund, warum jemand die Umstellung spaeter noch nachvollziehen kann.
    import ast
    fn = next(n for n in ast.walk(ast.parse(mp))
              if isinstance(n, ast.FunctionDef) and n.name == "_dedup_ids")
    rumpf = ast.unparse(ast.Module(body=[x for x in fn.body
                                         if not (isinstance(x, ast.Expr)
                                                 and isinstance(x.value, ast.Constant))],
                                   type_ignores=[]))
    for tot in ("atverg_dedup", "ted_dedup"):
        assert tot not in rumpf, f"Marktpuls haengt noch an {tot}"
    assert not (root / "scripts" / "dedupe_at_sources.py").exists()
    assert not (root / "scripts" / "dedupe_ch_sources.py").exists()

def test_live_write_merges_instead_of_overwriting(tmp_path):
    """Ein zweiter Live-Lauf darf den Monatsbestand NICHT ersetzen.

    Der teuerste Datenverlust dieses Projekts kam aus einer Zeile: `fetch_ted_live.py`
    schrieb `<monat>-live.parquet` bedingungslos neu. Der Monat einer Notice folgt ihrem
    XML-`publication_date`, das Suchfenster der TED-Facette — beide laufen auseinander, also
    erzeugt JEDER Lauf ein paar Zeilen für den Vormonat und ersetzte damit dessen komplette
    Datei durch diese Handvoll.

    Gemessen am 2026-08-11: DE 2026-07 hatte noch 845 von 15.628 Notices (5,4 %),
    CH 2025-12 noch 4 von 941. Der Backfill meldete trotzdem „100 % des Solls" — er misst
    direkt nach seinem eigenen Lauf, zerstört hat es erst der nächste.
    """
    import importlib.util
    import pathlib as _pl

    import pyarrow as pa
    import pyarrow.parquet as pq

    spec = importlib.util.spec_from_file_location(
        "_ftl", _pl.Path(__file__).resolve().parent.parent / "scripts" / "fetch_ted_live.py")
    ftl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ftl)

    schema = pa.schema([("notice_id", pa.string()), ("title", pa.string())])
    out = tmp_path / "2026-07-live.parquet"
    pq.write_table(pa.table({"notice_id": ["a_2026", "b_2026", "c_2026"],
                             "title": ["A", "B", "C"]}, schema=schema), out)

    # Zweiter Lauf bringt eine NEUE Notice und eine bereits vorhandene in frischer Fassung.
    neu = pa.table({"notice_id": ["c_2026", "d_2026"], "title": ["C-neu", "D"]}, schema=schema)
    zusammen = ftl._mit_bestand(out, neu, schema, {"c_2026", "d_2026"})

    ids = sorted(zusammen.column("notice_id").to_pylist())
    assert ids == ["a_2026", "b_2026", "c_2026", "d_2026"], (
        f"Bestand ging verloren: {ids}")
    titel = dict(zip(zusammen.column("notice_id").to_pylist(),
                     zusammen.column("title").to_pylist()))
    assert titel["c_2026"] == "C-neu", "neu geholte Notice muss die alte Fassung ersetzen"
    assert titel["a_2026"] == "A", "nicht geholte Notices müssen unverändert bleiben"

    # Idempotenz: derselbe Lauf nochmal darf nichts verdoppeln.
    nochmal = ftl._mit_bestand(out, neu, schema, {"c_2026", "d_2026"})
    assert len(nochmal.column("notice_id").to_pylist()) == len(set(
        nochmal.column("notice_id").to_pylist()))


def test_city_index_filter_keeps_places_and_drops_organisations():
    """Der Stadt-Index darf keine Firmen als Orte anbieten — und keine Orte verlieren.

    GeoNames traegt bei **Grossempfaenger-Postleitzahlen** (eigene PLZ wegen hohem
    Postaufkommen) den Organisationsnamen in die Ort-Spalte. Gemessen sind das 8.247 von
    23.297 Zeilen; erkennbar an leerer `accuracy`, waehrend echte Staedte durchgaengig 4
    oder 6 tragen.

    Nicht hart nach `accuracy` gefiltert wird, weil dort auch echte kleine Orte und
    Stadtteile liegen (Travenbrueck, Uetz, Kummersdorf-Alexanderdorf) — rund 1.350 gingen
    verloren. Nach „HUK-Coburg" sucht in einer Umkreissuche niemand; ein fehlendes Dorf ist
    dagegen ein echter Funktionsverlust.

    Der Fall, der die Balance zeigt: „Brand" stand als Marker in der Liste (fuer „Daimler
    Brand und IP Management GmbH") und warf dabei die echten Orte Brand (Oberpfalz) und
    Neunkirchen am Brand weg.
    """
    import importlib.util
    import pathlib as _pl

    spec = importlib.util.spec_from_file_location(
        "_bci", _pl.Path(__file__).resolve().parent.parent / "scripts" / "build_city_index.py")
    bci = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bci)

    for organisation in ("Kreissparkasse Ludwigsburg", "Bosch - Betriebskrankenkasse",
                         "LBS Süd Landesbausparkasse Süd", "RTS Rieger Team, Werbeagentur",
                         "Agentur für Arbeit Freising", "Finanzamt Kiel-Nord",
                         "Amtsgericht München", "Mercedes-Benz Versicherung AG"):
        assert bci._JUNK.search(organisation), f"nicht gefiltert: {organisation}"

    for ort in ("München", "Brand", "Neunkirchen am Brand", "Travenbrück", "Uetz",
                "Gießen", "Fürstenfeldbruck", "Kummersdorf-Alexanderdorf",
                "Bad Homburg vor der Höhe", "Sankt Augustin"):
        assert not bci._JUNK.search(ort), f"echter Ort faelschlich gefiltert: {ort}"


def test_city_index_gazetteer_gate_only_for_grossempfaenger():
    """Die Gazetteer-Positivliste darf nur die Grossempfaenger-Zeilen pruefen.

    Der Wortfilter allein kam nicht weiter: gegen Markennamen ohne sprachlichen Marker
    (ARAG, AVM, Adecco, Alusuisse, Airbus) hilft kein Muster. Die Loesung ist eine
    Positivliste echter Ortsnamen aus dem GeoNames-Gazetteer statt immer neuer
    Negativmuster.

    Zwei Feinheiten, beide gemessen:
      · Nur der PRAEFIX zaehlt als Ortsbeleg, nicht das Ende. Die PLZ-Tabelle klebt
        Gemeinde und Ortsteil zusammen ("Allendorf (Eder) Battenfeld"), der Gazetteer
        fuehrt sie getrennt — ohne Praefix-Pruefung fielen 583 echte Orte durch. Das Ende
        zu pruefen waere falsch: "ARGE Stadt Kaiserslautern" endet auf einen echten Ort.
      · Zeilen MIT gesetzter accuracy werden gar nicht gegengeprueft, sie sind von der
        Quelle als Ort belegt. Sonst fielen fuenf echte Orte heraus, die der Gazetteer
        unter anderem Namen fuehrt (Leinefelde, Mainz-Kostheim, Neualbenreuth,
        Elmenhorst-Lichtenhagen, Schneefernerhaus).
    """
    import importlib.util
    import pathlib as _pl

    spec = importlib.util.spec_from_file_location(
        "_bci2", _pl.Path(__file__).resolve().parent.parent / "scripts" / "build_city_index.py")
    bci = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bci)

    bekannt = {"allendorf (eder)", "kaiserslautern", "münchen"}
    assert bci._ist_ort("Allendorf (Eder) Battenfeld", bekannt)   # Gemeinde + Ortsteil
    assert bci._ist_ort("München", bekannt)
    assert not bci._ist_ort("ARGE Stadt Kaiserslautern", bekannt)  # Ort NUR am Ende
    assert not bci._ist_ort("Adecco", bekannt)

    # Fehlt der Gazetteer, faellt der Filter auf den Wortfilter zurueck statt abzubrechen —
    # der Index enthaelt dann wieder Organisationen, aber keine Stadt verschwindet.
    assert bci._lade_ortsnamen.__doc__ and "leere Menge" in bci._lade_ortsnamen.__doc__


def test_gehoert_zu_land_trennt_eu_einrichtungen():
    """Die Laenderzuordnung folgt dem Kaeuferland, nicht der Abfrage, die die Notice fand.

    Weder die TED-Search-API noch die Monatspakete trennen sauber: gemessen liefern
    `buyer-country=DEU` und `buyer-country=AUT` teils dieselbe Bekanntmachung. 121 Notices
    lagen in DE und AT zugleich, 116 davon gehoerten zu keinem von beiden (Kaeuferland
    Belgien 51, Niederlande 43, Italien 8, Luxemburg 6) - EU-Einrichtungen, die TED unter
    der Facette jedes Mitgliedstaats ausliefert.

    Der Fallstrick, der beim Bauen zugeschlagen hat: `notice.buyer_countries` klingt nach
    der Antwort, ist es aber nicht. Das Feld listet ALLE in der Bekanntmachung genannten
    Laender - bei der Moebel-Ausschreibung der EU-Kommission 14 Stueck inklusive DE und AT.
    Wer es mitzaehlt, baut eine Regel, die ausnahmslos zustimmt.
    """
    from govisor import normalize
    from govisor.schema import Notice, Party

    def notice(land, nuts=None, buyer_countries=(), nid="x_2026"):
        return Notice(notice_id=nid, schema="eforms", form_type="cn", country=land,
                      language="de", title="t", description=None, description_field=None,
                      cpv_main="79635000",
                      parties=[Party(role="buyer", name="X", country=land, nuts=nuts)],
                      buyer_countries=list(buyer_countries))

    # EIOPA Frankfurt: Kaeuferland DE -> gehoert nach DE, nicht nach AT.
    eiopa = notice("DE", "DE712", ["DE", "AT", "BE", "NL"])
    assert normalize.gehoert_zu_land(eiopa, "DE")
    assert not normalize.gehoert_zu_land(eiopa, "AT")

    # EU-Kommission Bruessel: gehoert in keines der DACH-Silber, trotz DE/AT in der Liste.
    kommission = notice("BE", "BE100", ["BE", "DE", "AT", "LU"])
    assert not normalize.gehoert_zu_land(kommission, "DE")
    assert not normalize.gehoert_zu_land(kommission, "AT")

    # NUTS faengt auf, wenn das Kaeuferland fehlt (am heutigen Bestand 0 Faelle, aber die
    # Klausel ist der Grund, warum die Regel "Kaeuferland ODER Sitz-NUTS" heisst).
    ohne_land = Notice(notice_id="y_2026", schema="eforms", form_type="cn", country=None,
                       language="de", title="t", description=None, description_field=None,
                       cpv_main="45000000",
                       parties=[Party(role="buyer", name="Y", country=None, nuts="DE300")])
    assert normalize.gehoert_zu_land(ohne_land, "DE")
    assert not normalize.gehoert_zu_land(ohne_land, "AT")

    # Ist gar nichts bekannt, bleibt die Notice drin - kein stiller Datenverlust.
    blind = Notice(notice_id="z_2026", schema="eforms", form_type="cn", country=None,
                   language="de", title="t", description=None, description_field=None,
                   cpv_main="45000000", parties=[Party(role="buyer", name="Z")])
    assert normalize.gehoert_zu_land(blind, "DE")


def test_notice_text_haelt_alle_sprachfassungen_gepaart():
    """Mehrsprachige Vergaben behalten jede Fassung — mit der richtigen Sprache daneben.

    `notices` fuehrt genau EINEN Titel; der Parser nahm die erste Fassung im XML und
    verwarf den Rest. Bei der belgischen Elia-Ausschreibung 161098_2024 (EN, FR, NL)
    landete so der FRANZOESISCHE Titel in der Zeile, waehrend `language` NLD meldete -
    Text und Etikett widersprachen sich.

    Die Sprache haengt im XML als Attribut am selben Element wie der Text
    (`<cbc:Name languageID="FRA">`), die Zuordnung ist beim Parsen also eindeutig. Erst der
    `attributes`-Flattener riss sie auseinander: dort werden Text und Sprachcode zu
    getrennten Zeilen ohne Positionsindex, in wechselnder Reihenfolge - nachtraeglich nicht
    mehr paarbar. Genau deshalb braucht es eine eigene Tabelle und nicht `attributes`.
    """
    import xml.etree.ElementTree as ET

    from govisor import schema

    xml = """<ContractNotice xmlns:cbc="urn:cbc" xmlns:cac="urn:cac">
      <cac:ProcurementProject>
        <cbc:Name languageID="FRA">Marche de fournitures</cbc:Name>
        <cbc:Name languageID="NLD">Opdracht voor leveringen</cbc:Name>
        <cbc:Name languageID="ENG">Supply contract</cbc:Name>
        <cbc:Description languageID="FRA">Description francaise</cbc:Description>
        <cbc:Description languageID="NLD">Nederlandse beschrijving</cbc:Description>
      </cac:ProcurementProject>
    </ContractNotice>"""
    root = ET.fromstring(xml)

    project = next(c for c in root if schema._local(c) == "ProcurementProject")
    titel = schema._child_texts_by_language(project, ("Name",))
    # Kleingeschriebenes ISO-639-1, nicht der Rohcode aus dem XML: die Quelle mischt
    # `FRA` (eForms) und `FR` (Legacy) fuer dieselbe Sprache — s. govisor/languages.py.
    assert titel == [("fr", "Marche de fournitures"),
                     ("nl", "Opdracht voor leveringen"),
                     ("en", "Supply contract")], titel

    beschr = schema._child_texts_by_language(project, ("Description",))
    assert [s for s, _ in beschr] == ["fr", "nl"]

    # Ohne Sprachangabe geht die Fassung NICHT verloren, sie bekommt nur kein Etikett.
    ohne = ET.fromstring('<P xmlns:cbc="urn:cbc"><cbc:Name>Kein Etikett</cbc:Name></P>')
    assert schema._child_texts_by_language(ohne, ("Name",)) == [(None, "Kein Etikett")]


def test_notice_text_landet_in_der_silber_tabelle():
    """Die Sprachfassungen muessen den Weg bis in die Zeilen finden, nicht nur ins Objekt."""
    from govisor import model, normalize, schema

    assert "notice_text" in model.TABLES, "Tabelle nicht registriert"
    assert model.TABLES["notice_text"].names == [
        "notice_id", "lot_id", "field", "language", "value"]

    notice = schema.Notice(
        notice_id="x_2026", schema="eforms", form_type="cn", country="BE",
        language="NLD", title="Marche", description=None, description_field=None,
        cpv_main="45000000",
        texts=[(None, "title", "FRA", "Marche"), (None, "title", "NLD", "Opdracht"),
               ("LOT-1", "description", "ENG", "Supply")])
    r = normalize.rows(notice, b"<x/>", "BE", 2026, 3)
    assert len(r["notice_text"]) == 3
    assert {z["language"] for z in r["notice_text"]} == {"FRA", "NLD", "ENG"}
    lot = [z for z in r["notice_text"] if z["lot_id"] == "LOT-1"][0]
    assert lot["field"] == "description" and lot["value"] == "Supply"


def test_notice_text_ids_sind_kanonisch():
    """`notice_text` muss dieselben notice_ids fuehren wie `notices` — sonst ist es Ballast.

    Der Backfill zieht aus zwei Quellen: den Monatspaketen (Dateiname `00370795_2024`) und
    dem Live-Cache (Dateiname `370795-2024`). Nur der Archiv-Zweig kanonisierte; im Live-
    Zweig fehlte der Schritt, und damit waren beim ersten Lauf ALLE 88.486 CH-Zeilen
    Waisen - technisch fehlerfrei geschrieben, fachlich wertlos, weil kein Join greift.
    """
    import pathlib as _pl

    import duckdb

    from govisor import schema

    assert schema.normalize_notice_id("370795-2024") == "370795_2024"
    assert schema.normalize_notice_id("00370795_2024") == "370795_2024"

    wurzel = _pl.Path("data/silver")
    if not wurzel.exists():
        return                      # ohne Datenplatte nur die reine Funktion pruefen
    con = duckdb.connect()
    for land in ("DE", "AT", "CH", "EU"):
        d = wurzel / land / "notice_text"
        if not any(d.glob("*/*.parquet")):
            continue
        waisen = con.execute(f"""
            SELECT count(*) FROM (
              SELECT DISTINCT notice_id FROM read_parquet(
                '{d.as_posix()}/*/*.parquet', hive_partitioning=1)
              EXCEPT
              SELECT DISTINCT notice_id FROM read_parquet(
                '{(wurzel/land/'notices').as_posix()}/*/*.parquet', hive_partitioning=1))
        """).fetchone()[0]
        # Eine Handvoll bleibt: Notices, die spaeter aus dem Laender-Silber gewandert sind.
        assert waisen < 100, f"{land}: {waisen} notice_text-Waisen — ID-Format geprueft?"


def test_sprachcodes_sind_kanonisch():
    """Eine Sprache, ein Code. Gemessen waren es 56 Codes fuer 24 Sprachen.

    Die Quelle mischt drei Systeme: die Legacy-Formulare fuehren ISO-639-1 im LG-Attribut
    (`DE`, 2,25 Mio.), eForms ISO-639-2/T in languageID (`DEU`, 2,20 Mio.), einzelne Pfade
    liefern Kleinschreibung (`de`). Fuer eine Sprachumschaltung ist das unbrauchbar - wer
    nach `de` filtert, verliert die Haelfte.

    Zielsystem ist ISO-639-1 klein, nicht aus Geschmack: das ist der Code im
    Accept-Language-Header, im HTML-lang-Attribut und in jeder i18n-Bibliothek.
    """
    import duckdb

    from govisor import languages

    assert languages.normalize("DEU") == "de"
    assert languages.normalize("DE") == "de"
    assert languages.normalize("de") == "de"
    assert languages.normalize("FRA") == "fr"
    assert languages.normalize("SPA") == "es"       # nicht "sp"
    assert languages.normalize("SWE") == "sv"       # nicht "sw"
    # Zweisprachige Vergaben (Suedtirol) behalten BEIDE Sprachen — das ist eine Tatsache
    # ueber die Vergabe, kein Formatfehler.
    assert languages.normalize("DE;IT") == "de;it"
    assert languages.normalize("DE IT") == "de;it"
    assert languages.normalize("DE;DE") == "de"
    # Fehlende Angabe bleibt fehlend, statt zu einer erfundenen Sprache zu werden.
    assert languages.normalize(None) is None and languages.normalize("") is None
    # Unbekanntes bleibt stehen (nur klein) — verwerfen wuerde die Luecke verstecken.
    assert languages.normalize("XYZ") == "xyz"

    import pathlib as _pl

    wurzel = _pl.Path("data/silver")
    if not wurzel.exists():
        return
    con = duckdb.connect()
    for land in ("DE", "AT", "CH", "EU"):
        for tabelle in ("notices", "notice_text"):
            d = wurzel / land / tabelle
            if not any(d.glob("*/*.parquet")):
                continue
            roh = con.execute(f"""
                SELECT DISTINCT language FROM read_parquet(
                  '{d.as_posix()}/*/*.parquet', hive_partitioning=1)
                WHERE language IS NOT NULL""").fetchall()
            schlecht = [r[0] for r in roh if r[0] != languages.normalize(r[0])]
            assert not schlecht, f"{land}/{tabelle}: nicht kanonisch — {schlecht[:5]}"


def test_lead_text_reicht_sprachfassungen_bis_zum_frontend():
    """Die Kette Silber → Gold → JSON muss halten, sonst nuetzt notice_text nichts.

    `lead_export` fuehrt genau EINEN Titel. Solange nur der exportiert wird, kann die
    Oberflaeche keine Dokumentsprache anbieten, obwohl 35,3 Mio. Fassungen im Silber
    liegen. `build_lead_text` filtert sie auf die Lead-Auswahl (ungefiltert waere die
    Tabelle rund zwanzigmal so gross wie noetig).

    Der Export sagt eine Sprachwahl nur an, wo es wirklich eine gibt: eine einzige Fassung
    ist keine Wahl, sondern nur die Sprache der Veroeffentlichung.
    """
    import pathlib as _pl

    from govisor import gold

    assert hasattr(gold, "build_lead_text"), "Builder fehlt"
    quelle = _pl.Path("govisor/cli.py").read_text()
    assert "build_lead_text" in quelle, "Builder nicht in die CLI-Gold-Kette verdrahtet"
    exporter = _pl.Path("scripts/export_web_leads.py").read_text()
    assert "sprachfassungen" in exporter, "Sprachfassungen erreichen den Frontend-Export nicht"

    import json
    for f in sorted(_pl.Path("web/data").glob("leads-*.json")):
        for lead in json.loads(f.read_text()):
            sp = lead.get("sprachen")
            if sp is not None:
                assert len(sp) > 1, f"{lead['id']}: Sprachwahl mit nur {sp}"
                assert all(s == s.lower() and len(s) == 2 for s in sp), sp


# ── Oberflächen-Sprachen ───────────────────────────────────────────────────────

def _flach_kataloge():
    import json
    from pathlib import Path
    m = Path(__file__).resolve().parent.parent / "web" / "lib" / "i18n" / "messages"
    return (json.loads((m / "flat.en.json").read_text()),
            json.loads((m / "flat.fr.json").read_text()))


def test_flache_sprachkataloge_sind_deckungsgleich():
    """EN und FR muessen dieselben Schluessel fuehren — sonst faellt eine Sprache
    stillschweigend auf Deutsch zurueck und niemand merkt es.

    Der Schluessel IST der deutsche Satz (s. `web/lib/i18n/index.tsx`). Deshalb gibt es
    keinen `de`-Katalog: dort waere jeder Eintrag seine eigene Antwort.
    """
    en, fr = _flach_kataloge()
    assert set(en) == set(fr), (
        f"nur in EN: {sorted(set(en) - set(fr))[:5]} · nur in FR: {sorted(set(fr) - set(en))[:5]}")
    assert not [k for k, v in {**en, **fr}.items() if not v.strip()], "leere Uebersetzung"


def test_platzhalter_bleiben_in_jeder_sprache_erhalten():
    """`{n}`/`{b}` sind Einsetzstellen. Faellt einer beim Uebersetzen weg, fehlt dem Nutzer
    die Zahl — und zwar lautlos, weil der Satz sonst sinnvoll aussieht."""
    import re
    en, fr = _flach_kataloge()
    muster = re.compile(r"\{(\w+)\}")
    for katalog, name in ((en, "en"), (fr, "fr")):
        for schluessel, wert in katalog.items():
            assert set(muster.findall(schluessel)) == set(muster.findall(wert)), \
                f"{name}: Platzhalter weichen ab bei {schluessel!r} → {wert!r}"


def test_verdrahtete_texte_sind_uebersetzt():
    """Jeder deutsche Literal-Schluessel, der im Code durch `t(...)` laeuft, muss im
    Katalog stehen. Sonst ist die Stelle zwar verdrahtet, bleibt aber auf Deutsch —
    genau die Art halbfertiger Zustand, die man am Bildschirm uebersieht.

    Geprueft werden nur `t("…")`-Aufrufe mit einem deutschen Literal (Umlaut oder
    deutsches Funktionswort); Punkt-Schluessel wie `nav.akquise` bedienen den
    strukturierten Katalog und sind hier nicht gemeint.
    """
    import re
    from pathlib import Path
    web = Path(__file__).resolve().parent.parent / "web"
    en, fr = _flach_kataloge()
    deutsch = re.compile(r"[äöüÄÖÜß]|\b(der|die|das|und|oder|nicht|kein|keine|mit|von|bei|"
                         r"für|aus|auf|ist|sind|wie|was|wo|wenn|nur|alle|eine|zum|zur|im|am)\b")
    fehlend: list[str] = []
    dateien = (sorted(web.glob("components/**/*.tsx")) + sorted(web.glob("app/**/*.tsx"))
               + sorted(web.glob("lib/**/*.js")) + sorted(web.glob("lib/**/*.tsx")))
    for p in dateien:
        # `t(...)` in React, `tk(...)` in den Prototyp-Renderern — dieselben Kataloge.
        for m in re.finditer(r'\bt[k]?\(\s*"((?:[^"\\]|\\.)*)"', p.read_text()):
            # Quelltext-Escapes aufloesen: im Katalog steht der Satz, nicht `\\"`.
            k = m.group(1).replace('\\"', '"').replace("\\\\", "\\")
            if "." in k and " " not in k:
                continue                      # strukturierter Punkt-Schluessel
            if deutsch.search(k) and k not in en:
                fehlend.append(f"{p.relative_to(web)}: {k!r}")
    assert not fehlend, "verdrahtet, aber nicht uebersetzt:\n  " + "\n  ".join(fehlend[:12])


def test_texttabellen_hinter_t_sind_uebersetzt():
    """Wie der Guard darueber — aber fuer Saetze, die ueber eine KONSTANTE laufen.

    Der Test oben sieht nur `t("deutscher Satz")` direkt im Aufruf. Es gibt aber ein zweites,
    ebenso richtiges Muster: die Saetze stehen in einer Tabelle und gehen erst beim Rendern
    durch `t()` — `t(TXT.titel)`, `t(LAND_LABEL[k])`, `t(MONAT_LANG[i])`. Dieses Muster ist
    sogar noetig, wo `t()` beim Import ausgewertet wuerde und damit die Sprache einfroere
    (siehe die 37 Modulkonstanten, die genau so schon einmal auf Deutsch stehen blieben).

    Gemessen am 2026-08-13: `web/components/Marktpuls.tsx` fuehrte 53 Saetze so — und blieb
    in EN/FR vollstaendig deutsch, ohne dass ein Test anschlug. Der Zustand war nicht falsch
    gebaut, nur unbewacht.

    Geprueft werden ausschliesslich Konstanten, die IRGENDWO als `t(NAME…)` verwendet werden.
    Ohne diese Einschraenkung schlaegt der Test bei jeder beliebigen Zeichenketten-Tabelle an
    (Vokabular, CSS-Klassen, SQL) — und ein Test, der bei allem anschlaegt, wird abgeschaltet.
    """
    import re
    from pathlib import Path
    web = Path(__file__).resolve().parent.parent / "web"
    en, _fr = _flach_kataloge()
    deutsch = re.compile(r"[äöüÄÖÜß]|\b(der|die|das|und|oder|nicht|kein|keine|mit|von|bei|"
                         r"für|aus|auf|ist|sind|wie|was|wo|wenn|nur|alle|eine|zum|zur|im|am)\b")
    # `t(NAME.feld)` oder `t(NAME[…])` — der Punkt bzw. die Klammer unterscheidet die
    # Tabellen-Nutzung vom Literal-Aufruf, den der Guard darueber schon abdeckt.
    nutzung = re.compile(r"\bt[k]?\(\s*([A-Z][A-Z0-9_]{2,})\s*[.\[]")
    fehlend: list[str] = []
    dateien = (sorted(web.glob("components/**/*.tsx")) + sorted(web.glob("app/**/*.tsx"))
               + sorted(web.glob("lib/**/*.js")) + sorted(web.glob("lib/**/*.tsx")))
    for p in dateien:
        quelle = p.read_text()
        namen = set(nutzung.findall(quelle))
        for name in sorted(namen):
            # Objekt- ODER Array-Literal (MONAT_LANG ist ein Array).
            m = re.search(rf"\b(?:const|let|var)\s+{name}\b[^=]*=\s*([\{{\[])", quelle)
            if not m:
                continue                       # Import aus einer anderen Datei — dort geprueft
            zu, auf = ("}", "{") if m.group(1) == "{" else ("]", "[")
            start = m.end() - 1
            tiefe, instr, esc, ende = 0, False, False, None
            for i in range(start, len(quelle)):
                c = quelle[i]
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c in ('"', "'", "`"):
                    instr = not instr
                elif instr:
                    pass
                elif c == auf:
                    tiefe += 1
                elif c == zu:
                    tiefe -= 1
                    if tiefe == 0:
                        ende = i
                        break
            if ende is None:
                continue
            for w in re.findall(r'"((?:[^"\\]|\\.)*)"', quelle[start:ende]):
                k = w.replace('\\"', '"').replace("\\\\", "\\")
                if len(k) < 3 or ("." in k and " " not in k):
                    continue
                if deutsch.search(k) and k not in en:
                    fehlend.append(f"{p.relative_to(web)} · {name}: {k!r}")
    assert not fehlend, ("Texttabelle laeuft durch t(), Satz fehlt im Katalog:\n  "
                         + "\n  ".join(fehlend[:12]))


def test_uebersetzung_faellt_nicht_auf_prototyp_eigenschaften_zurueck():
    """`tk("constructor")` darf nicht die Funktion `Object` liefern.

    Importiertes JSON traegt die Object-Prototyp-Kette. Ohne Typ-Pruefung landete
    `function Object() { [native code] }` in der Seite — gemessen, nicht vermutet.
    Erreichbar ist das ueber daten-abgeleitete Schluessel (`tk(k.zustand)`, `tk(l.seen)`):
    heute trifft kein Vokabular diese Namen, aber die Annahme stand nirgends geschrieben.
    """
    from pathlib import Path
    quelle = (Path(__file__).resolve().parent.parent / "web" / "lib" / "i18n" / "index.tsx").read_text()
    assert 'typeof roh === "string"' in quelle, "Typ-Pruefung im Flach-Zweig fehlt"


def test_rec26_block_escapt_seine_labels():
    """Der Empfehlungs-Block schreibt in `dangerouslySetInnerHTML`. Jeder DATEN-abgeleitete
    Wert muss durch `esc()`; der Datenpfad fuehrt heute nur ueber ein geschlossenes
    Zertifikats-Vokabular, aber das ist eine Eigenschaft der Daten, nicht des Codes.

    Statische Literale (`tk("Naechster Schritt:")`) bleiben bewusst UNgeescaped: der
    Katalog traegt an einigen Stellen absichtlich HTML-Entities (`&mdash;`, `&rarr;`),
    die `esc()` zu sichtbarem `&amp;mdash;` verstuemmeln wuerde. Die Regel lautet also
    „Daten escapen, Konstanten nicht" — nicht „alles escapen".
    """
    import re
    from pathlib import Path
    quelle = (Path(__file__).resolve().parent.parent / "web" / "lib" / "explorerCore.js").read_text()
    block = re.search(r'const rec = recommend\(.*?</div>`;\n      \}\)\(\)\}', quelle, re.S)
    assert block, "rec26-Block nicht gefunden — Test an den Code anpassen"
    # `tk(` mit einem Bezeichner statt eines Literals = daten-abgeleitet.
    roh = re.findall(r'\$\{(?!esc\()(tk\(\s*[A-Za-z_$][^)]*\)|[ab]\.gruende[^}]*|hint)\}', block.group(0))
    assert not roh, f"ungeescapte Datenausgabe im rec26-Block: {roh}"


def test_keine_uebersetzung_in_modul_konstanten():
    """`tk()` in einer Modul-Konstanten wird beim IMPORT ausgewertet — die Sprache waere
    beim ersten Laden eingefroren und wechselte danach nie mehr.

    Gemessen war das kein theoretisches Risiko: ein automatischer Verdrahtungslauf hat
    37 solcher Aufrufe hineingeschrieben (`LAND_LABEL`, `SRC_TEXT`, `EMPF_GRUND`, die
    Orts-Map). Uebersetzt wird an der AUSGABESTELLE, nie an der Definition.
    """
    import re
    from pathlib import Path
    quelle = (Path(__file__).resolve().parent.parent / "web" / "lib" / "explorerCore.js").read_text()
    tiefe, in_const, treffer = 0, False, []
    for nr, zeile in enumerate(quelle.split("\n"), 1):
        if re.match(r"^(const|let|var)\s+[A-Z_a-z]", zeile) and not re.search(r"=>|function", zeile):
            in_const, tiefe = True, 0
        if in_const:
            tiefe += zeile.count("{") + zeile.count("[") - zeile.count("}") - zeile.count("]")
            if "tk(" in zeile:
                treffer.append(f"{nr}: {zeile.strip()[:70]}")
            if tiefe <= 0 and zeile.rstrip().endswith((";", "};", "];")):
                in_const = False
    assert not treffer, "tk() in Modul-Konstante (Sprache eingefroren):\n  " + "\n  ".join(treffer[:8])


# ── Dubletten-Firewall: die beiden Trennregeln, die an echten Daten gemessen wurden ──
#
# Beide Regeln entstanden aus Zufallsstichproben ueber die erzeugte `notice_duplicates`
# (2026-08-13). Sie haben zusammen 22.000 Falsch-Paare entfernt — DE 6.794→6.116,
# AT 5.715→5.421, CH 18.676→2.874. Ohne Test faellt jede von ihnen bei der naechsten
# Umformulierung lautlos wieder heraus, und die Anreicherung traegt fremde Fristen ins
# Produkt, ohne dass es jemand sieht.

def test_dedupe_zahlen_sieht_kurze_losnummern():
    """`worte()` verwirft Tokens unter drei Zeichen — die Losnummer darf nicht mitgehen.

    Gemessen: „26.39 / 26.40 / 26.30 - Grundschulerweiterung MZH" standen als Dubletten
    in der Tabelle, weil beide Ziffernpaare zweistellig sind und komplett aus dem
    Wortsatz fielen. Die Los-Sperre las damals `w`, sah keine Zahl und liess durch.
    """
    from govisor.dedupe import worte, zahlen
    assert not {x for x in worte("26.39 - Grundschulerweiterung") if x.isdigit()}
    assert zahlen("26.39 - Grundschulerweiterung") == frozenset({"26", "39"})
    assert zahlen("26.39 - Grundschulerweiterung") != zahlen("26.40 - Grundschulerweiterung")
    # Fuehrende Nullen sind Schreibweise, keine andere Losnummer.
    assert zahlen("Winterdienst Auftrag Nr. 06") == zahlen("Winterdienst Auftrag Nr. 6")
    # Ohne Zahl auf einer Seite greift die Sperre nicht (sie fordert beidseitig Zahlen).
    assert zahlen("Rahmenvertrag Reinigung") == frozenset()


def test_dedupe_geschwister_lose_werden_getrennt_belegt():
    """Beidseitig eigene Woerter = Geschwister-Lose, nicht dieselbe Vergabe.

    Ein Bauprojekt wird gewerkeweise ausgeschrieben; der gemeinsame Projektname ist lang,
    das trennende Gewerk kurz — die Enthaltung liegt deshalb ueber der Schwelle. Bei einer
    echten Dublette ist hoechstens EINE Seite laenger (Zusatz/Umformulierung), bei
    Geschwistern haben beide ein eigenes Inhaltswort.
    """
    from govisor.dedupe import worte
    a = worte("Bertha-von-Suttner-Gymnasium, Erweiterung Anbau - Trockenbauarbeiten")
    b = worte("Bertha-von-Suttner-Gymnasium, Erweiterung Anbau - Stahlbauarbeiten")
    assert (a - b) and (b - a), "Geschwister-Lose: beide Seiten tragen ein eigenes Wort"

    # Echte Dublette: die eine Seite ist Teilmenge der anderen (DOeE ergaenzt eine Abteilung).
    m = worte("Magistrat der Stadt Bad Hersfeld")
    d = worte("Magistrat der Stadt Bad Hersfeld - Stadt- und Kreisarchiv")
    assert not (m - d), "Dublette: nur eine Seite hat Zusatzwoerter"


def test_dedupe_anreicherung_haengt_an_der_belegstufe():
    """Die Anreicherung muss auf `beleg`, nicht auf `gleicher_kaeufer` filtern.

    Geschwister-Lose teilen sich per Definition den Kaeufer. Ein Filter auf
    `gleicher_kaeufer` waere dort wahr und haette die Gewerke-Sperre lautlos unterlaufen —
    die Frist des Nachbargewerks waere als „echt_aus_dublette" ins Produkt gewandert.
    """
    from pathlib import Path
    quelle = (Path(__file__).resolve().parent.parent / "govisor" / "dedupe.py").read_text(
        encoding="utf-8")
    anr = quelle.split("def anreichern")[1]
    assert "d.beleg = 'kaeufer_und_titel'" in anr
    assert "WHERE d.gleicher_kaeufer" not in anr


def test_lead_deadline_verlaengerung_schlaegt_die_eigene_frist():
    """`echt_verlaengert` steht VOR `echt` im Wasserfall — als einzige Stufe.

    Alle uebrigen Dubletten-Werte fuellen nur Luecken. Die Fristverlaengerung korrigiert
    einen vorhandenen, aber ueberholten Wert: TED und die nationale Quelle veroeffentlichen
    dieselbe Vergabe, die Frist wird verschoben, nur eine Quelle bekommt es mit. Steht die
    Stufe hinter `echt`, greift sie nie und der Lead bleibt faelschlich abgelaufen.
    """
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "govisor" / "gold.py").read_text(
        encoding="utf-8")
    block = src.split("def build_lead_deadline")[1].split("def ")[0]
    i_v = block.index("'echt_verlaengert'")
    i_e = block.index("THEN 'echt'")
    assert i_v < i_e, "die Verlaengerung muss vor der eigenen Frist geprueft werden"


def test_export_meldet_dubletten_fristen_nicht_als_schaetzung():
    """`echt_aus_dublette` und `echt_verlaengert` sind veroeffentlichte Daten.

    Der Export prueft `starts_with(deadline_source,'echt')`. Eine Gleichheitspruefung auf
    `'echt'` (so stand es bis 2026-08-13) meldet beide neuen Stufen als `estimated` — eine
    Untertreibung, die dem Kunden eine belegte Frist als Modellwert verkauft.
    """
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "govisor" / "gold.py").read_text(
        encoding="utf-8")
    assert "starts_with(d.deadline_source, 'echt')" in src
    assert "d.deadline_source='echt' THEN 'actual'" not in src


def test_tageslauf_reihenfolge_quellen_firewall_gold():
    """Quellen-Import → Dubletten-Firewall → Gold. Beide Pfeile sind Pflicht.

    Die Firewall liest Silber und schreibt `notice_enrichment`/`notice_duplicates`. Laeuft
    ein Quellen-Import DANACH, sieht sie dessen Saetze erst am Folgetag — der Ausschluss
    greift einen Lauf zu spaet, also genau dann, wenn die Dubletten schon im Produkt stehen.
    Laeuft der Gold-Rebuild VOR ihr, fehlen die uebernommenen und verlaengerten Fristen.

    Genau diese Reihenfolge ist beim Verdrahten schon einmal falsch gewesen: der DTVP-Block
    stand urspruenglich im Dokumenten-Abschnitt, also hinter dem Gold-Rebuild.
    """
    from pathlib import Path
    r = (Path(__file__).resolve().parent.parent / "scripts" / "daily_leads.sh").read_text()
    i_dtvp = r.index("govisor.dtvp")
    i_ns = r.index("govisor.netserver")
    i_fw = r.index("govisor.dedupe")
    i_gold = r.index("build_dach_gold.py")
    assert i_dtvp < i_fw, "DTVP-Import muss vor der Firewall laufen"
    assert i_ns < i_fw, "NetServer-Import muss vor der Firewall laufen"
    assert i_fw < i_gold, "Firewall muss vor dem Gold-Rebuild laufen"
    # `--neu-einlesen` holt ALLES neu und gehoert nicht in den taeglichen Lauf. Geprueft
    # werden nur AUSFUEHRBARE Zeilen — im Kommentar steht der Schalter absichtlich, samt
    # Begruendung, wann er von Hand gebraucht wird.
    befehle = [z for z in r.splitlines() if z.strip() and not z.lstrip().startswith("#")]
    assert not [z for z in befehle if "--neu-einlesen" in z], \
        "Voll-Neueinlesen gehoert nicht in den Tageslauf"


def test_zweitquellen_ausschluss_prueft_den_master():
    """Der einzige loeschende Pfad darf nur bei LAUFENDEM Master greifen.

    Ohne die Master-Bedingung ist es der Ausschluss, der beim ersten Entwurf gemessen und
    verworfen wurde: 64 gueltige Leads gegen 6 echte Dubletten. Und die Frist des Masters
    muss so gelesen werden, wie das Produkt sie zeigt — sonst wirft die Firewall eine Zeile
    weg, deren Information sie selbst gerade uebertragen hat.
    """
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "govisor" / "gold.py").read_text(
        encoding="utf-8")
    b = src.split("def _redundante_zweitquelle_sql")[1].split("\ndef ")[0]
    assert "d.beleg = 'kaeufer_und_titel'" in b
    # Der Stichtag ist parametrisiert: er MUSS derselbe sein wie die Lead-Zugehoerigkeit,
    # sonst laufen Ausschluss und Zugehoerigkeit bei einem `--as-of` auseinander und die
    # Vergabe verschwindet ganz. `current_date` bleibt nur die Rueckfallebene ohne Stichtag.
    assert "{_ST}" in b, "Stichtag nicht parametrisiert"
    assert 'DATE \'{stichtag}\'' in b and "current_date" in b
    for feld in ("submission_deadline_verlaengert", "submission_deadline"):
        assert feld in b, f"{feld} fehlt in der Master-Frist"


def test_lead_zugehoerigkeit_und_frist_nutzen_dieselbe_definition():
    """Eine Frist-Definition fuer Zugehoerigkeit UND Anzeige — sonst laufen sie auseinander.

    Gemessen 2026-08-13, als sie es taten: `build_lead_deadline` rechnete den vollen
    Wasserfall, `build_prospective_leads` entschied die ZUGEHOERIGKEIT an der rohen
    Silber-Frist. Von 40 Bekanntmachungen mit korrigierter (verlaengerter) Frist standen
    **0** in `leads.parquet` — die Korrektur landete in einer Tabelle, die ueber die
    Zugehoerigkeit nicht entscheidet. Dieselbe Divergenz haette den Zweitquellen-Ausschluss
    180 gueltige Leads kosten lassen (AT 156, CH 18, DE 6), deren Master seine Frist nur
    aus der Anreicherung traegt und deshalb selbst nicht lead-faehig war.
    """
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "govisor" / "gold.py").read_text(
        encoding="utf-8")
    b = src.split("def build_prospective_leads")[1].split("\ndef ")[0]
    assert "_FRIST_EFF" in b, "Lead-Zugehoerigkeit muss die effektive Frist benutzen"
    assert "n.submission_deadline::DATE >= DATE" not in b, "rohe Silber-Frist als Schwelle"
    # Reihenfolge im Wasserfall: Verlaengerung schlaegt eigene Frist schlaegt uebernommene.
    eff = src.split("_FRIST_EFF = ")[1].split("\n\n")[0]
    assert eff.index("vrlq") < eff.index("n.submission_deadline") < eff.index("anrq")


def test_dedupe_paart_keine_verschiedenen_verfahrensstufen():
    """Vorinformation und Bekanntmachung sind zwei Schritte, keine Dublette.

    Sie tragen denselben Titel und denselben Kaeufer und rutschten deshalb durch: gemessen
    2026-08-13 waren 189 Paare stufen-gemischt (DE 33, AT 156). Mit geladenen Zuschlaegen
    (`--alle-arten`, die Veroeffentlichungs-Sicht fuer Marktpuls) waere der Fehler gross
    geworden — ein `can` haette gegen das `cn` derselben Vergabe gepaart.
    """
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "govisor" / "dedupe.py").read_text(
        encoding="utf-8")
    # Der eigentliche Abgleich sitzt seit dem Zeitscheiben-Umbau in `_paare_finden`;
    # `finde` laedt nur noch und verteilt. Der Test folgt der Logik, nicht dem Namen.
    b = src.split("def _paare_finden")[1].split("\ndef ")[0]
    assert 's["art"] != t["art"]' in b, "Stufen-Sperre fehlt"


def test_dedupe_kennt_die_veroeffentlichungs_sicht():
    """`--alle-arten` existiert und ist NICHT der Standard.

    Zwei Sichten, EINE Pruefung: Ausschreibungen (`cn`/`pin`) fuer die Lead-Logik,
    alle Arten fuer Marktpuls, der Publikationen je Jahr zaehlt. Daraus zwei Skripte zu
    machen waere der Rueckfall in genau das, was dieses Modul abgeloest hat.
    """
    from govisor import dedupe
    import inspect
    assert "alle_arten" in inspect.signature(dedupe.finde).parameters
    assert inspect.signature(dedupe.finde).parameters["alle_arten"].default is False
    assert "--alle-arten" in (dedupe.main.__doc__ or "") or "alle-arten" in inspect.getsource(
        dedupe.main)


def test_dedupe_zeitscheiben_sind_zuschnitt_unabhaengig():
    """Die Worthäufigkeit für die Seed-Wahl muss GLOBAL sein, nicht je Zeitscheibe.

    Der Abgleich läuft jahrgangsweise (mit FENSTER_TAGE Rand), weil ein Paar per Definition
    binnen dieses Fensters liegt — ohne die Aufteilung schaffte AT die volle Historie nicht
    (>45 min Abbruch, mit Scheiben 40 s). Zählt aber jede Scheibe die Wörter selbst, ist ein
    Wort in einem kleinen Ausschnitt seltener, die Seeds fallen anders aus und das Ergebnis
    hängt am Zuschnitt statt an den Daten. Gemessen, als es so war: CH ab 2024 fand 18.144
    statt 18.146 Paaren.
    """
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "govisor" / "dedupe.py").read_text(
        encoding="utf-8")
    z = src.split("def _in_zeitscheiben")[1].split("\ndef ")[0]
    assert "haeufigkeit" in z, "globale Wortstatistik fehlt"
    assert "_paare_finden(scheibe, haeufigkeit)" in z, "Scheibe bekommt sie nicht"
    # Rand um den Jahrgang ist Pflicht, sonst zerschneidet der Jahreswechsel echte Paare.
    assert "FENSTER_TAGE" in z, "Rand um den Jahrgang fehlt"
    # Sätze ohne Datum können mit allem paaren und müssen in jeder Scheibe mitlaufen.
    assert "ohne_datum" in z


def test_uebernommener_wert_traegt_seine_waehrung():
    """Ein Schätzwert aus dem Zwilling darf nur MIT geprüfter Währung einfliessen.

    Das abgelöste `dedupe_at_sources.py` übertrug bewusst nur EUR, „damit keine
    Fremdwährung stillschweigend als Euro gilt". Beim Umzug in die zentrale Firewall wäre
    diese Sperre fast verlorengegangen: `anreichern()` sammelte den Wert ohne Währung ein.
    Sie wandert jetzt als eigene Zeile aus DEMSELBEN Quellsatz mit — die Kopplung über
    `quelle_notice_id` ist der Kern, sonst gehörte die Währung zu einem anderen Wert.

    Warum es zählt: `atverg` führt den Schätzwert zu 69,8 %, TED-AT nur zu 11,0 %.
    Gemessen 2026-08-14 sinkt „Wert unbekannt" in AT von 2.346 auf 2.004.
    """
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    ded = (root / "govisor" / "dedupe.py").read_text(encoding="utf-8")
    assert "estimated_value_waehrung" in ded, "Währung wird nicht mitgesammelt"

    gold = (root / "govisor" / "gold.py").read_text(encoding="utf-8")
    j = gold.split("def _frist_joins_sql")[1].split("\ndef ")[0]
    assert "c.quelle_notice_id = w.quelle_notice_id" in j, \
        "Wert und Währung müssen aus demselben Quellsatz stammen"
    # Beide Lead-Bauer prüfen die Währung des übernommenen Wertes.
    for bauer in ("def build_leads", "def build_prospective_leads"):
        b = gold.split(bauer)[1].split("\ndef ")[0]
        assert "wrtq.waehrung='EUR'" in b, f"{bauer}: Währungssperre fehlt"


def test_skripte_finden_govisor_ohne_pythonpath():
    """Jedes Skript, das `govisor` importiert, muss den Projektpfad selbst setzen.

    `python3 scripts/x.py` legt **`scripts/`** auf `sys.path`, nicht die Projektwurzel.
    Ein Skript ohne eigene `sys.path`-Zeile laeuft deshalb nur, wenn der Aufrufer
    zufaellig `PYTHONPATH` gesetzt hat — aus einer interaktiven Shell also meistens,
    unter `launchd` nie.

    Das ist keine Theorie: `build_marktpuls.py` starb am 2026-08-15 im Tageslauf genau
    daran. Weil der Aufruf im Shell-Skript ein `|| echo ⚠` traegt, lief der Lauf weiter
    und `marktpuls.json` blieb **still** auf dem Vortagesstand — die teuerste Sorte
    Fehler, weil nichts rot wird.
    """
    import pathlib
    import re

    wurzel = pathlib.Path(__file__).resolve().parent.parent
    fehlend = []
    for f in sorted((wurzel / "scripts").glob("*.py")):
        text = f.read_text(encoding="utf-8", errors="replace")
        if not re.search(r"^(from|import) govisor", text, re.M):
            continue
        if "sys.path" not in text:
            fehlend.append(f.name)
    assert not fehlend, (
        "Skripte importieren `govisor`, setzen aber den Projektpfad nicht — sie brechen "
        f"unter launchd ab: {fehlend}")


def test_ertragsbericht_misst_den_trichter_nicht_nur_summen():
    """Die Frage ist nicht „wie viel", sondern „wo reisst es ab".

    Gemessen 2026-08-16: 92,3 % der Dateien sind lesbar, aber nur 21,6 % der offenen Leads
    haben ueberhaupt Unterlagen. Zwei Zahlen, die einzeln beide harmlos aussehen und
    zusammen die eigentliche Schwaeche zeigen — die REICHWEITE, nicht die Ausbeute.
    """
    import pathlib
    quelle = (pathlib.Path(__file__).resolve().parent.parent / "govisor" / "ertrag.py"
              ).read_text(encoding="utf-8")
    for stufe in ("offene Leads", "mit Archiv", "mit lesbarem Text", "mit Signalen"):
        assert stufe in quelle, f"Trichterstufe fehlt: {stufe}"
    assert "blockiert_nach_grund" in quelle, "die Reichweiten-Arbeitsliste fehlt"


def test_ertragsbericht_trennt_gewollte_grenzen_von_luecken():
    """`.zip` steht mit 0 % lesbar in der Statistik — aber alle 1.021 sind
    `datei_zu_gross`, also die eigene 10-MB-Grenze und kein fehlender Parser.

    Beides in einer Liste zu zeigen las sich als „.zip koennen wir nicht". Der Bericht
    muss unterscheiden, sonst erzeugt er Arbeitslisten, auf denen nichts zu tun ist.
    """
    import pathlib
    quelle = (pathlib.Path(__file__).resolve().parent.parent / "govisor" / "ertrag.py"
              ).read_text(encoding="utf-8")
    assert "GEWOLLT" in quelle and "datei_zu_gross" in quelle
    assert "FEHLENDE PARSER" in quelle and "BEWUSST AUSGESCHLOSSEN" in quelle


def test_ertragsbericht_kennt_das_vokabular_jedes_feldes():
    """Jedes `*_source`-Feld hat ein EIGENES Vokabular. Beim ersten Anlauf habe ich
    ueberall `actual` erwartet und bekam „Wert 0 %, Kategorie 0 %" — was nach Totalausfall
    aussah und in Wahrheit ein Messfehler war (`category_source` heisst `cpv`).

    `competition_source` fehlt bewusst: bei offenen Vergaben ist es strukturell `na`, eine
    Kennzahl die immer 0 % zeigt erzieht dazu, den Block zu ueberlesen.
    """
    import pathlib
    quelle = (pathlib.Path(__file__).resolve().parent.parent / "govisor" / "ertrag.py"
              ).read_text(encoding="utf-8")
    assert '"category_source", ("cpv",)' in quelle, "Kategorie braucht ihr eigenes Vokabular"
    assert '"competition_source"' not in quelle.split("belegt_pct")[1].split("# ──")[0], \
        "competition_source gehoert nicht in die Belegt-Quote offener Leads"


def test_kein_skript_ruft_psql_ueber_den_blossen_namen():
    """`psql` liegt unter `/opt/homebrew/bin` — und der PATH, den **launchd** einem Agenten
    gibt, kennt Homebrew nicht.

    Am 2026-08-16 fielen dadurch ZWEI Tageslauf-Schritte aus: die Supabase-Schema-Migration
    und die nächtliche `gap_effects`-Vorberechnung, beide mit `FileNotFoundError: 'psql'`.
    Aus dem Terminal lief alles — der Fehler trat nur im geplanten Lauf auf, also dort, wo
    niemand zusieht. Genau deshalb braucht es einen Test statt eines guten Vorsatzes.
    """
    import pathlib
    import re

    wurzel = pathlib.Path(__file__).resolve().parent.parent
    treffer = []
    for f in list((wurzel / "scripts").glob("*.py")) + list((wurzel / "govisor").glob("*.py")):
        if f.name == "psql.py":
            continue                                # die Fundstelle selbst
        text = f.read_text(encoding="utf-8", errors="replace")
        # Nur der AUFRUF zählt (`["psql", …]`), nicht Wort-Erwähnungen in Kommentaren.
        if re.search(r'\[\s*"psql"\s*,', text):
            treffer.append(f.name)
    assert not treffer, (
        "rufen `psql` über den blossen Namen auf und scheitern unter launchd: " + ", ".join(treffer))


def test_psql_wird_auch_ohne_homebrew_im_pfad_gefunden():
    """Gegenprobe zum Test darüber: die Suche muss den echten Ort kennen, nicht nur den PATH."""
    import os
    import sys
    import pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from govisor.psql import KANDIDATEN, finde_psql

    assert "/opt/homebrew/bin/psql" in KANDIDATEN, "der Homebrew-Pfad ist der Regelfall auf diesem Mac"
    alt = os.environ.get("PATH")
    try:
        os.environ["PATH"] = "/usr/bin:/bin"        # so sieht launchd es
        os.environ.pop("PSQL", None)
        # Nur prüfen, WENN psql installiert ist — auf einer frischen CI gibt es keins.
        if any(os.path.exists(k) for k in KANDIDATEN):
            assert finde_psql(), "psql liegt auf der Platte, wird aber nicht gefunden"
    finally:
        if alt is not None:
            os.environ["PATH"] = alt


def test_dichte_regel_ist_eine_quelle_und_wird_beim_klick_festgehalten():
    """Die Dichte muss im MOMENT des Klicks gespeichert werden, nicht beim Auswerten.

    Sie ändert sich, sobald die Unterlagen eines Leads ankommen — wer sie später berechnet,
    misst den Stand von heute gegen einen Klick von letzter Woche. Genau deshalb reicht es
    nicht, `lead_id` zu speichern und die Dichte hinterher zu joinen.

    Hintergrund: gemessen 2026-08-16 sind **58 % der Leads dünn** (nur Kopfdaten). Ob das
    jemanden stört, weiss NIEMAND — die Interaktionstabelle hatte 3 Zeilen. Statt ein Symbol
    gegen ein vermutetes Problem zu bauen, wird erst gemessen.
    """
    web = ROOT_WEB()
    a = (web / "lib" / "analytics.ts").read_text(encoding="utf-8")
    assert "dichte: d, merkmale: m" in a, "Dichte muss mit in die Interaktionszeile"
    assert "recordLeadClick(leadId: string, lead?" in a, "der Lead selbst muss uebergeben werden"
    shell = (web / "components" / "explorer" / "ExplorerShell.tsx").read_text(encoding="utf-8")
    assert "recordLeadClick(id, l)" in shell, "die Aufrufstelle gibt den Lead nicht mit"


def test_dichte_zaehlt_nicht_einfach_vorhandene_felder():
    """Ein naives Zählen führt in die Irre — und das ist gemessen, nicht vermutet.

    Einen Unterlagen-LINK haben 74,6 % der Leads, Lose 56,0 % — beides sagt nichts darüber,
    ob man die Vergabe beurteilen kann. Das einzige Merkmal, das das bedeutet, ist „Signale
    aus den Unterlagen gelesen": 20,5 %. Eine Punktzahl hätte diese eine wichtige
    Eigenschaft unter fünf billigen begraben.
    """
    d = (ROOT_WEB() / "lib" / "dichte.ts").read_text(encoding="utf-8")
    assert "unterlagenAusgewertet" in d, "die entscheidende Frage braucht einen eigenen Namen"
    # `unterlagen` (der blosse Link) darf die Stufe NICHT bestimmen.
    kern = d.split("export function dichte")[1].split("export function merkmale")[0]
    assert "unterlagen" not in kern.replace("unterlagenAusgewertet", ""), \
        "der Unterlagen-LINK darf die Dichte nicht bestimmen — er sagt nichts ueber den Inhalt"


def ROOT_WEB():
    import pathlib
    return pathlib.Path(__file__).resolve().parent.parent / "web"


def test_outreach_landing_fuehrt_ins_onboarding():
    """Die Knöpfe der Vertriebs-Landing dürfen nicht auf die Anmeldeseite zeigen.

    Sie zeigten auf ``/login?t=<token>`` — eine Seite, die den Parameter gar nicht liest
    und „Willkommen zurück" sagt. Ein kalter Kontakt, der noch nie ein Konto hatte, landete
    also im Wiedersehen. Derselbe Fehler wie damals bei ``?modus=registrieren``: ein Link
    auf einen Parameter, den das Ziel nicht kennt. Das fällt beim Lesen des Codes nicht auf,
    weil beide Seiten für sich korrekt sind — nur die Verbindung stimmt nicht.
    """
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "web/app/t/[token]/LandingView.tsx"
    quelle = p.read_text(encoding="utf-8")
    assert "/onboarding?t=${encodeURIComponent(token)}" in quelle
    # Nur echte Verlinkungen prüfen — der Kommentar nennt den alten Pfad absichtlich.
    code = "\n".join(z for z in quelle.splitlines() if not z.lstrip().startswith("//"))
    assert "/login?t=" not in code


def test_onboarding_verwirft_token_vorbelegung_nicht():
    """Der Domain-Stamm darf die Firma aus dem Outreach-Token nicht überschreiben.

    ``erkennen()`` läuft direkt nach der Konto-Anlage und leitete die Firma bis dahin
    ausschliesslich aus der E-Mail-Domain ab. Bei gesetztem Token hätte das die aufgelöste
    Entität gegen eine aus der Adresse geschnittene Zeichenkette getauscht — und zwar
    lautlos, weil beide Wege denselben Screen erreichen.
    """
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "web/app/onboarding/page.tsx"
    quelle = p.read_text(encoding="utf-8")
    assert "/api/outreach-firma?t=" in quelle, "Vorbelegung wird gar nicht erst geholt"
    assert "const ausToken = vomToken" in quelle, "Weiche in erkennen() fehlt"
    assert "const frage = ausToken ? eingabe.trim() : domainStamm(email)" in quelle

    # Die unbelegbare Behauptung darf nicht zurückkehren: wir kennen namentlich nur
    # GEWINNER (1.233.126 in `notice_parties`), keinen einzigen unterlegenen Bieter.
    # „Noch nie geboten" ist aus unseren Daten grundsätzlich nicht feststellbar.
    # Auf den VERDRAHTETEN Text prüfen, nicht auf das Vorkommen der Wörter: der Kommentar
    # daneben nennt die alte Fassung absichtlich beim Namen. Ein Test, der die eigene
    # Begründung als Verstoss liest, zwingt dazu, die Begründung zu löschen.
    assert 't("Wir haben noch nie öffentlich geboten")' not in quelle
    assert 't("Wir sind noch nicht in eurer Datenbank")' in quelle


def test_landing_klassen_sind_praefixiert():
    """Jede CSS-Klasse der Outreach-Landing traegt `lg-`.

    Grund, zweimal am selben Tag gelernt: kurze Klassennamen kollidieren mit dem
    App-Stylesheet, und zwar LAUTLOS. `.einstieg` war in `explorer.css` schon der
    Einstiegs-Kasten der Lead-Ansicht (gruener Rahmen ums Anmeldeformular). `.lb` ist
    dort ein Layout-Container mit `max-width:1560px` und `padding:var(--s6)` — als
    Beschriftung im Trichter benutzt, blies er jede Zeile von 39 auf 92 Pixel auf.

    Beide Male sah der Code richtig aus und das Ergebnis falsch, und beide Male war die
    Ursache erst nach dem Ausmessen im Browser zu sehen. Ein Praefix kostet nichts und
    macht die ganze Fehlerklasse unmoeglich.
    """
    from pathlib import Path
    import re
    w = Path(__file__).resolve().parent.parent / "web"

    tsx = (w / "app/t/[token]/LandingView.tsx").read_text(encoding="utf-8")
    # Klassen des App-Rahmens sind erlaubt — die kommen aus `Rail`/`explorer.css`.
    rahmen = {"app", "body", "main", "seitenmain", "landing"}
    fremd = sorted({k for treffer in re.findall(r'className="([^"{]+)"', tsx)
                    for k in treffer.split()
                    if not k.startswith("lg-") and k not in rahmen})
    assert not fremd, f"ungepraefixte Klassen im Markup: {fremd}"

    css = (w / "app/landing.css").read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)          # Kommentare erwaehnen alte Namen
    sel = sorted({m for m in re.findall(r"\.([a-zA-Z][\w-]*)", css)
                  if not m.startswith("lg-") and m != "landing"})
    assert not sel, f"ungepraefixte Selektoren in landing.css: {sel}"


def test_tageslauf_erntet_vor_dem_abrufen():
    """Gold muss VOR den Unterlagen-Abrufern stehen, und die Abrufer unter einem Budget.

    Am 2026-08-16 riss der Lauf nach 623 min die 8-h-Grenze. 18 von 33 Schritten waren
    erledigt; ausgefallen war ausgerechnet alles, was aus Daten ein Produkt macht:
    Gold-Rebuild, Signale, Frontend-Export, Supabase, Ertragsbericht. 93 % der Laufzeit
    steckten in Beschaffung.

    Gemessen ueber fuenf Laeufe: Beschaffung 1.622 min im schlimmsten Fall und nach oben
    offen, Wertschoepfung 45 min und gedeckelt. Wer das Gedeckelte hinter das Offene
    stellt, verliert im Zweifel immer dasselbe.

    Die Kette Firewall -> Kategorie -> Gold muss dabei GESCHLOSSEN bleiben: die
    Kategorie-Ableitung liest `notice_duplicates` aus der Firewall, der Gold-Lead-Bau
    liest `lead_kategorie.parquet` aus der Kategorie-Ableitung.
    """
    from pathlib import Path
    quelle = (Path(__file__).resolve().parent.parent / "scripts/daily_leads.sh").read_text(encoding="utf-8")

    def pos(nadel: str) -> int:
        i = quelle.find(nadel)
        assert i > 0, f"nicht gefunden: {nadel}"
        return i

    firewall = pos('step "Dubletten-Firewall')
    kategorie = pos('step "Kategorie-Ableitung')
    gold = pos('step "Gold-Rebuild')
    marke_abruf = pos("_ABRUF_PHASE=1")
    erster_abruf = pos('step "NetServer-Unterlagen')
    marke_ernte = pos("_ABRUF_PHASE=0")
    entpacken = pos('step "Unterlagen entpacken')

    assert firewall < kategorie < gold, "Firewall -> Kategorie -> Gold ist die Datenkette"
    assert gold < marke_abruf < erster_abruf, "Gold gehoert VOR die Unterlagen-Abrufer"
    assert erster_abruf < marke_ernte < entpacken, "Auswertung liegt hinter der Abruf-Marke"

    # Der Waechter selbst: Reserve gesetzt und in `mit_grenze` konsultiert.
    assert "ERNTE_RESERVE=${GOVISOR_ERNTE_RESERVE:-5400}" in quelle
    assert 'if [ "${_ABRUF_PHASE:-0}" = "1" ] && ! abruf_erlaubt' in quelle
    # Uebersprungene Abrufe muessen im Abschlussbericht auftauchen, sonst sieht ein
    # gekuerzter Lauf aus wie ein vollstaendiger.
    assert "_ABRUF_UEBERSPRUNGEN" in quelle and "Abrufe uebersprungen (Zeitbudget)" in quelle


def test_dedupe_fenster_vereinigt_statt_zu_ersetzen(tmp_path, monkeypatch):
    """Ein Fensterlauf muss den Bestand ERGAENZEN, sonst ist er Datenverlust.

    Das rollende Fenster sieht nur die letzten 190 Tage. Wuerde `schreibe` die Datei wie
    bisher ueberschreiben, waeren beim ersten Nachtlauf alle Paare aus 2004 bis vorletztes
    Jahr weg — lautlos, weil die Datei ja da ist und plausibel aussieht.

    Geprueft wird beides: dass Altes bleibt UND dass eine neue Zeile mit gleichem
    Schluessel die alte ersetzt (der frische Lauf hat die aktuellere Anreicherung).
    """
    from govisor import dedupe as D
    import pyarrow.parquet as pq

    monkeypatch.setattr(D, "ROOT", tmp_path)

    def zeile(m, d, beleg="alt"):
        return {"master_id": m, "duplicate_id": d, "master_quelle": "ted",
                "duplicate_quelle": "doe", "enthaltung": 0.9, "gleicher_kaeufer": True,
                "beleg": beleg, "tage_abstand": 1, "ergaenzt": None}

    D.schreibe([zeile("alt_1", "alt_2"), zeile("bleibt", "auch")], "XX")
    ziel = D.schreibe([zeile("neu_1", "neu_2"), zeile("alt_1", "alt_2", beleg="frisch")],
                      "XX", vereinigen=True)

    rows = {(z["master_id"], z["duplicate_id"]): z for z in pq.read_table(ziel).to_pylist()}
    assert ("bleibt", "auch") in rows, "historisches Paar wurde weggeworfen"
    assert ("neu_1", "neu_2") in rows, "neues Paar fehlt"
    assert rows[("alt_1", "alt_2")]["beleg"] == "frisch", "neue Zeile muss gewinnen"

    # Ohne `vereinigen` bleibt das alte Verhalten: ersetzen. Der Vollauf braucht das.
    ziel = D.schreibe([zeile("nur", "das")], "XX")
    assert len(pq.read_table(ziel).to_pylist()) == 1


def test_dedupe_fenster_nimmt_saetze_ohne_datum_mit():
    """Saetze ohne Datum paaren mit allem und muessen in JEDEM Fensterlauf dabei sein.

    In DE sind das 16.694 Bekanntmachungen. Faellt die `IS NULL`-Klausel weg, verschwinden
    sie aus dem taeglichen Abgleich und ihre Dubletten werden nie gefunden — ohne dass
    irgendetwas abbricht.
    """
    from pathlib import Path
    quelle = (Path(__file__).resolve().parent.parent / "govisor/dedupe.py").read_text(encoding="utf-8")
    assert "coalesce(n.publication_date, n.submission_deadline) IS NULL" in quelle
    # Der Tageslauf nutzt das Fenster, sonntags aber die volle Historie.
    lauf = (Path(__file__).resolve().parent.parent / "scripts/daily_leads.sh").read_text(encoding="utf-8")
    assert "--fenster-tage 190" in lauf
    assert '[ "$(date +%u)" = "7" ]' in lauf, "Sonntags-Vollauf fehlt"
