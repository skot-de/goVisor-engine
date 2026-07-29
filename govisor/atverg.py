"""Quelle AT unterschwellig — OffeneVergaben.at (data.gv.at / BVergG2018).

Vierte technische Basis (`offeneverg-csv`). Schließt die letzte echte DACH-Lücke: **Österreich
unterschwellig** (>50k €, BVergG2018-Pflicht-Open-Data). Kontrakt: `docs/quellen-at-unterschwellig.md`.

**Bronze = der tägliche CSV-Bulk als ZIP** (`data/raw_atverg/AT/YYYY-MM-DD.zip`). Die Downloads-
Seite generiert die ZIP-URL pro Aufruf frisch mit Zeitstempel+Hash (`/tmp/kerndaten_dailydump_
<ts>_<hash>.zip`) — der Downloader parst sie darum aus dem HTML. Die ZIP enthält **eine** CSV
(`kerndaten_csv_dump_*.csv`, ~130 MB, 236k Records), UTF-8, komma-getrennt, RFC4180-Quotes mit
eingebetteten Zeilenumbrüchen (→ nicht zeilenweise splitten, DuckDB liest sie korrekt).

**Feld-Mapping gemessen** (2026-07-28, 236.118 Records) gegen die echten Spalten, nicht geraten:

* ``art`` = Kerndaten-Kategorie → **notice_kind**: ``KD_x_1_*`` (Bekanntmachung) = ``cn``,
  ``KD_x_2_*`` (vergebener Auftrag) = ``can``.
* ``auftragsart`` → **contract_nature** (Bau/Dienstleistung/Liefer + Konzessionen).
* ``cpv`` = ``"72000000 IT-Dienste…"`` (Code **und** Label) → 8-stelligen Code extrahieren.
* Datumsfelder im Format ``DD.MM.YYYY`` (``try_strptime``). ``wert`` = EUR-Zahl.
* ``"oberschwellenbereich / unterschwellenbereich"`` = OSB/USB → **wichtig**: OSB (~82k) überlappt
  TED-AT; der genuine Neuwert ist USB (~72k). In ``attributes`` als ``atverg/schwelle`` abgelegt,
  damit Gold gegen die TED-AT-Überschneidung filtern/deduplizieren kann.

Füllgrade: titel/auftraggeber/beschreibung 100 %, cpv 99,9 %, ``auftraggeber stammzahl`` 97,6 %
(National-ID → Entity-Resolution), wert 65,4 %, nuts_code nur 33 % (grob, oft nur „AT" → schwache
Geo-Auflösung, ehrlich flaggen), Frist 24 % (weil überwiegend Zuschläge).

**Gold:** ``build_at_gold`` liest bereits alle ``silver/AT``-Notices — nach dem Ingest fließen die
atverg-``cn``-Leads automatisch mit ein (kein eigener Gold-Builder nötig). Einzige Anpassung dort,
wenn scharf geschaltet: OSB-Records ausschließen/deduplizieren (TED-Overlap). Bis dahin ist dies
der **Connector** (Bronze+Silber); der Voll-Ingest wartet wie AT-TED auf den externen Speicher.
"""
from __future__ import annotations

import re
import ssl
import urllib.error
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

from .config import Config

_PAGE = "https://offenevergaben.at/downloads/kerndaten_dump_daily?format=csv"
_ZIP_RE = re.compile(r"https://offenevergaben\.at/tmp/kerndaten_dailydump_\d+_[a-z0-9]+\.zip")
_UA = "goVisor/0.1 (data engine; +https://offenevergaben.at)"
_ctx: ssl.SSLContext | None = None


def _get(url: str) -> bytes:
    """GET mit SSL-Verify, bei SSLError einmalig auf unverified zurückfallen (wie simap._get)."""
    global _ctx
    if _ctx is None:
        _ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=120, context=_ctx) as r:
            return r.read()
    except urllib.error.URLError as e:
        if not isinstance(getattr(e, "reason", None), ssl.SSLError):
            raise
        _ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=120, context=_ctx) as r:
            return r.read()


def _raw_dir(cfg: Config, country: str) -> Path:
    return cfg.data_dir / "raw_atverg" / country


def download(cfg: Config, country: str = "AT", stamp: str | None = None) -> Path:
    """Bronze: tägliche ZIP holen (ZIP-URL aus der Downloads-HTML parsen) → raw_atverg/AT/<stamp>.zip.

    ``stamp`` überschreibt den Datei-Stempel (Default: heute), damit der Lauf reproduzierbar bleibt.
    Gibt den Bronze-Pfad zurück.
    """
    html = _get(_PAGE).decode("utf-8", "replace")
    m = _ZIP_RE.search(html)
    if not m:
        raise RuntimeError("ZIP-Link nicht in der OffeneVergaben-Downloads-Seite gefunden "
                           "(HTML-Struktur geändert? _ZIP_RE prüfen)")
    zip_url = m.group(0)
    blob = _get(zip_url)
    out_dir = _raw_dir(cfg, country)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{stamp or date.today().isoformat()}.zip"
    tmp = out.with_suffix(".part")
    tmp.write_bytes(blob)
    tmp.replace(out)
    print(f"atverg {country} Bronze: {len(blob)/1e6:.1f} MB → {out.name} (Quelle {zip_url.split('/')[-1]})")
    return out


def _latest_zip(cfg: Config, country: str) -> Path | None:
    zips = sorted(_raw_dir(cfg, country).glob("*.zip"))
    return zips[-1] if zips else None


# auftragsart → contract_nature (gemessenes Vokabular)
_NATURE = {
    "Bauauftrag": "works", "Baukonzession": "works",
    "Dienstleistungsauftrag": "services", "Dienstleistungskonzession": "services",
    "Lieferauftrag": "supplies", "Lieferkonzession": "supplies",
}

# Silber-Notices-Spalten in Modell-Reihenfolge → SQL-Ausdruck. Nicht belegte Felder = typisiertes NULL.
# (Kommentierte Herkunft je Feld; Datumsformat DD.MM.YYYY.)
_D = "try_strptime({c}, '%d.%m.%Y')::DATE"


def build_silver(cfg: Config, country: str = "AT", force: bool = False) -> int:
    """Bronze-ZIP → Silber-Parquet (hive: silver/AT/<table>/year=YYYY/YYYY-atverg.parquet).

    Verlustfrei (kein Filtern nach Relevanz — OSB bleibt drin, geflaggt via attributes). Gibt die
    Notice-Zahl zurück. Nutzt DuckDB fürs robuste CSV-Parsen + pyarrow fürs schema-treue Schreiben.
    """
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq

    from . import model

    zp = _latest_zip(cfg, country)
    if not zp:
        print("atverg: keine Bronze-ZIP — erst `ingest-atverg` (download) laufen lassen.")
        return 0

    con = duckdb.connect()
    # CSV aus der ZIP nach DuckDB: über ein temporär entpacktes File (DuckDB liest nicht in-zip).
    with zipfile.ZipFile(zp) as z:
        member = next(n for n in z.namelist() if n.endswith(".csv"))
        tmp_csv = cfg.data_dir / "raw_atverg" / country / "_extract.csv"
        with z.open(member) as src, open(tmp_csv, "wb") as dst:
            dst.write(src.read())

    R = (f"read_csv('{tmp_csv.as_posix()}', header=true, all_varchar=true, "
         f"sample_size=-1, strict_mode=false, ignore_errors=true)")

    # Publikationsdatum-Waterfall (kein sauberes Pub-Datum in den Kerndaten): erste Verfügbarkeit →
    # aktualisiert → Frist → Vertragsabschluss. Steuert year/month-Partition.
    pub = (f"coalesce({_D.format(c='\"tag erstmalige verfügbarkeit\"')}, "
           f"{_D.format(c='aktualisiert')}, {_D.format(c='\"schlusstermin für den eingang\"')}, "
           f"{_D.format(c='\"tag vertragsabschluss\"')})")
    kind = ("CASE WHEN art LIKE 'KD_%_1_%' THEN 'cn' WHEN art LIKE 'KD_%_2_%' THEN 'can' END")
    nat = ("CASE auftragsart " + " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in _NATURE.items()) + " END")

    con.execute(f"CREATE TEMP VIEW src AS SELECT *, {pub} AS _pub, {kind} AS _kind FROM {R}")

    # --- notices ---
    notices_sql = f"""
      SELECT 'atv-' || id AS "notice_id", CAST(NULL AS VARCHAR) AS "publication_number",
             CAST(NULL AS VARCHAR) AS "oj_ref", _pub AS "publication_date", CAST(NULL AS VARCHAR) AS "ted_url",
             'AT' AS "country", ['AT'] AS "buyer_countries",
             CAST(extract(year FROM _pub) AS BIGINT) AS "year", CAST(extract(month FROM _pub) AS BIGINT) AS "month",
             'atverg' AS "schema_gen", art AS "form_type", _kind AS "notice_kind", 'de' AS "language",
             titel AS "title", beschreibung AS "description", 'kerndaten' AS "description_field",
             regexp_extract(cpv, '([0-9]{{8}})', 1) AS "cpv_main", nuts_code AS "performance_nuts",
             {nat} AS "contract_nature", verfahrensart AS "procedure_type",
             {_D.format(c='"schlusstermin für den eingang"')} AS "submission_deadline",
             'https://offenevergaben.at/auftrag/' || id AS "portal_url",
             TRY_CAST(wert AS DOUBLE) AS "estimated_value", CAST(NULL AS DOUBLE) AS "final_value",
             'EUR' AS "value_currency", {_D.format(c='"tag vertragsabschluss"')} AS "award_date",
             {_D.format(c='"geplanter ausführungsbeginn"')} AS "start_date",
             {_D.format(c='"endzeitpunkt / erfüllungszeitpunkt"')} AS "end_date",
             CAST(NULL AS BIGINT) AS "lot_count", CAST(length(coalesce(beschreibung,'')) AS BIGINT) AS "text_chars",
             CAST(NULL AS VARCHAR) AS "ref_publication_number", CAST(NULL AS VARCHAR) AS "ref_ted_url",
             CAST(NULL AS VARCHAR[]) AS "flags", CAST(NULL AS VARCHAR[]) AS "unknown_country_codes"
      FROM src WHERE id IS NOT NULL
    """

    # --- notice_parties: Auftraggeber (+ Lieferant als winner bei Zuschlägen) ---
    parties_sql = f"""
      SELECT 'atv-' || id AS "notice_id", 'buyer' AS "role", 0 AS "seq", auftraggeber AS "name",
             "auftraggeber stammzahl" AS "national_id", CAST(NULL AS VARCHAR) AS "town",
             CAST(NULL AS VARCHAR) AS "postal_code", 'AT' AS "country", nuts_code AS "nuts",
             CAST(NULL AS VARCHAR) AS "email", CAST(NULL AS VARCHAR) AS "phone", CAST(NULL AS VARCHAR) AS "contact_person",
             CAST(NULL AS VARCHAR) AS "url", CAST(NULL AS BOOLEAN) AS "is_sme", CAST(NULL AS BOOLEAN) AS "in_consortium"
      FROM src WHERE id IS NOT NULL AND auftraggeber IS NOT NULL
      UNION ALL
      SELECT 'atv-' || id, 'winner', 0, lieferant, "lieferant stammzahl", NULL, NULL, 'AT', nuts_code,
             NULL, NULL, NULL, NULL, NULL, NULL
      FROM src WHERE id IS NOT NULL AND lieferant IS NOT NULL
    """

    # --- notice_cpv (Haupt-CPV; "cpv zusätzlich" ist frei-getrennt → Haupt genügt für den Scaffold) ---
    cpv_sql = f"""
      SELECT 'atv-' || id notice_id, regexp_extract(cpv, '([0-9]{{8}})', 1) cpv_code, true is_main
      FROM src WHERE id IS NOT NULL AND regexp_extract(cpv, '([0-9]{{8}})', 1) <> ''
    """

    # --- awards (Bieterzahl!) ---
    awards_sql = f"""
      SELECT 'atv-' || id notice_id, CAST(NULL AS VARCHAR) lot_id, lieferant winner_name,
             "lieferant stammzahl" winner_national_id,
             TRY_CAST("anzahl eingegangener angebote" AS BIGINT) num_tenders,
             TRY_CAST("anzahl eingegangener angebote (kmu)" AS BIGINT) num_tenders_sme,
             CAST(NULL AS BIGINT) num_tenders_other_eu, CAST(NULL AS BIGINT) num_tenders_non_eu,
             CAST(NULL AS BIGINT) num_tenders_electronic
      FROM src WHERE id IS NOT NULL AND _kind = 'can'
    """

    # --- attributes: Schwelle (OSB/USB) fürs spätere Overlap-Handling + Verfahrensart-Rohwert ---
    attrs_sql = f"""
      SELECT 'atv-' || id AS "notice_id", 'atverg/schwelle' AS "path",
             "oberschwellenbereich / unterschwellenbereich" AS "value"
      FROM src WHERE id IS NOT NULL AND "oberschwellenbereich / unterschwellenbereich" IS NOT NULL
    """

    tables = {"notices": notices_sql, "notice_parties": parties_sql,
              "notice_cpv": cpv_sql, "awards": awards_sql, "attributes": attrs_sql}
    n_notices = 0
    for table, sql in tables.items():
        arrow = con.execute(sql).fetch_arrow_table()
        # Auf das Modell-Schema casten, damit die Ausgabe byte-kompatibel mit TED/simap-Silber ist.
        if table in model.TABLES:
            arrow = arrow.cast(model.TABLES[table])
        if table == "notices":
            n_notices = arrow.num_rows
        # Nach Jahr partitionieren (year=0 für Datum-lose Records — verlustfrei, kein Drop).
        _write_partitioned(cfg, country, table, arrow, pq, pa)
    tmp_csv.unlink(missing_ok=True)
    print(f"atverg {country} Silber: {n_notices} Notices → {len(tables)} Tabellen")
    return n_notices


def _write_partitioned(cfg, country, table, arrow, pq, pa):
    """Arrow-Tabelle nach year (falls Spalte vorhanden) in silver/AT/<table>/year=YYYY/YYYY-atverg.parquet
    schreiben; sonst als year=0 (Kind-Tabellen ohne Jahr erben es über den notice_id-Join)."""
    import pyarrow.compute as pc
    has_year = "year" in arrow.schema.names
    if has_year:
        years = pc.unique(pc.fill_null(arrow.column("year"), 0)).to_pylist()
    else:
        years = [0]
    for y in years:
        if has_year:
            mask = pc.equal(pc.fill_null(arrow.column("year"), 0), y)
            part = arrow.filter(mask)
        else:
            part = arrow
        out = cfg.silver_dir / country / table / f"year={int(y)}" / f"{int(y)}-atverg.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".part")
        pq.write_table(part, tmp, compression="zstd")
        tmp.replace(out)
