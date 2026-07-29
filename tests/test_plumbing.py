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
        assert s.connector in sources.CONNECTORS, f"{s.id}: unbekannter Connector {s.connector}"
        assert s.status in sources.STATUSES, f"{s.id}: unbekannter Status {s.status}"
        assert s.tier in ("oberschwellig", "unterschwellig", "beides"), f"{s.id}: Tier {s.tier}"
    summ = sources.summary()
    assert summ["connectors"] == len(sources.CONNECTORS)
    assert summ["quellen_live"] == len(sources.by_status("live"))
    # DACH-Matrix: DE + CH beide Schwellen abgedeckt, AT ist die offene Arbeit
    dach = {(cc, tier): status for cc, tier, _, status in sources.dach_matrix()}
    assert dach[("DE", "oberschwellig")] == "live" and dach[("DE", "unterschwellig")] == "live"
    assert dach[("CH", "oberschwellig")] == "live" and dach[("CH", "unterschwellig")] == "live"
    assert dach[("AT", "unterschwellig")] in ("candidate", "prepared", "live")
    # Die drei Live-Quellen: TED-DE, DÖE-DE, simap-CH
    live_ids = {s.id for s in sources.by_status("live")}
    assert live_ids == {"ted-de", "doe-de", "simap-ch"}
    # AT ist als Brücke vorbereitet (deckt sich mit build_at_gold)
    assert any(s.id == "ted-at" and s.status == "prepared" for s in sources.REGISTRY)


def test_normalize_national_id_leitweg():
    """national_id-Normalisierung: Leitweg-ID (mit/ohne Schema-Präfix) → EIN Schlüssel;
    USt-IdNr normalisiert; Müll (UUID/TED-intern/Kurzzahl/Bindestrich) → None (Name-Fallback)."""
    from govisor.gold import normalize_national_id as N
    # Leitweg-ID: Präfix-Varianten fallen auf denselben Schlüssel
    assert N("0204:991-00199-39") == N("991-00199-39") == "leitweg:991-00199-39"
    assert N("08-A9866-40") == "leitweg:08-A9866-40"
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
