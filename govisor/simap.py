"""Quelle CH — simap.ch Downloader (Bronze).

Offene JSON-REST-API, kein Key/Login (Kontrakt: ``docs/quellen-simap-api.md``). Zwei Endpoints:
Such-Endpoint (Cursor-Paginierung über ``pagination.lastItem``) + Detail je Publikation.

**Bronze = rohes JSON je Monat als JSONL** (``data/raw_simap/<country>/YYYY-MM.jsonl``), eine Zeile
je Publikation ``{"summary": <such-obj>, "detail": <detail-obj|null>}``. Verlustfreiheit liegt wie
bei TED/DÖE in Bronze: ein Parser-Fix (Silber, Schritt 3) kostet einen Re-Run über die lokalen
JSONL, keinen erneuten Download. Monats-Bucket = ``base.publicationDate`` (bzw. ``publicationDate``
aus der Trefferliste).

Idempotent: pro Monat wird mit vorhandenem File gemerged, dedupliziert über ``publicationId``.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

from .config import Config

BASE = "https://www.simap.ch"
SEARCH = BASE + "/rest/publications/v2/project/project-search"
DETAIL = BASE + "/rest/publications/v1/project/{pid}/publication-details/{pubid}"
# Länder-Filter der Suche: false = auch Aufträge mit ausländischem Erfüllungsort (die CH-Stelle
# zählt trotzdem). Sprachen: alle, damit fr/it/de-Titel vollständig kommen.
_SEARCH_Q = {"lang": ["de", "fr", "it", "en"], "orderAddressCountryOnlySwitzerland": "false"}
_UA = "govisor-ingest/1.0 (public procurement research)"
_ctx: ssl.SSLContext | None = None


def _get(url: str) -> dict:
    """GET → JSON. Verifiziert; fällt bei Proxy-Cert (Dev-Maschine) auf unverifiziert zurück.

    Nur öffentliche Lesezugriffe, keine Secrets im Request → unverifizierter Fallback vertretbar.
    """
    global _ctx
    if _ctx is None:
        _ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ctx) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as e:
        # SSL-Verifikation scheitert auf Dev-Maschinen hinter einem Proxy mit eigenem Root-Cert
        # (der Fehler kommt als URLError mit SSLCertVerificationError als reason). Einmalig auf
        # unverifiziert umschalten und erneut versuchen — nur öffentliche Lesezugriffe.
        if not isinstance(getattr(e, "reason", None), ssl.SSLError):
            raise
        _ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=30, context=_ctx) as r:
            return json.loads(r.read().decode("utf-8"))


def _search_url(cursor: str | None) -> str:
    q = dict(_SEARCH_Q)
    if cursor:
        q["lastItem"] = cursor
    return SEARCH + "?" + urllib.parse.urlencode(q, doseq=True)


def _iter_projects(max_pages: int | None, delay: float):
    """Trefferliste seitenweise (neueste zuerst) über den lastItem-Cursor. Yieldet Projekte."""
    cursor: str | None = None
    seen_cursors: set[str] = set()
    pages = 0
    while max_pages is None or pages < max_pages:
        data = _get(_search_url(cursor))
        projects = data.get("projects") or []
        if not projects:
            break
        for p in projects:
            yield p
        pages += 1
        cursor = (data.get("pagination") or {}).get("lastItem")
        if not cursor or cursor in seen_cursors:
            break                       # Ende (kein/looping Cursor)
        seen_cursors.add(cursor)
        if delay:
            time.sleep(delay)


def _month_of(p: dict) -> str:
    d = p.get("publicationDate") or ""
    return d[:7] if len(d) >= 7 else "unknown"


def _raw_dir(cfg: Config, country: str) -> Path:
    return cfg.data_dir / "raw_simap" / country


def _merge_month(path: Path, records: list[dict], force: bool) -> int:
    """JSONL je Monat schreiben, dedupliziert über publicationId (neuer Satz gewinnt).

    ``force`` überschreibt das Monatsfile komplett; sonst wird mit dem Bestand gemerged.
    """
    by_id: dict[str, dict] = {}
    if path.exists() and not force:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                by_id[r["summary"]["publicationId"]] = r
            except Exception:
                continue
    for r in records:
        by_id[r["summary"]["publicationId"]] = r
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in by_id.values():
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return len(by_id)


def download(cfg: Config, country: str = "CH", max_pages: int | None = None,
             delay: float = 0.15, force: bool = False) -> int:
    """simap.ch → Bronze. Gibt die Zahl frisch geholter Publikationen zurück.

    ``max_pages`` begrenzt den Lauf (je Seite 20; None = ganze Historie, neueste zuerst).
    Für jede Publikation wird die Detailseite geholt (schlägt sie fehl, bleibt ``detail=None`` —
    die Trefferliste allein trägt schon Kern-Lead + Geo).
    """
    buckets: dict[str, list[dict]] = defaultdict(list)
    n_detail_ok = n_total = 0
    for p in _iter_projects(max_pages, delay):
        n_total += 1
        detail = None
        try:
            detail = _get(DETAIL.format(pid=p["id"], pubid=p["publicationId"]) + "?lang=de")
            n_detail_ok += 1
        except Exception:
            pass
        buckets[_month_of(p)].append({"summary": p, "detail": detail})
        if delay:
            time.sleep(delay)
    for month, records in buckets.items():
        total = _merge_month(_raw_dir(cfg, country) / f"{month}.jsonl", records, force)
        print(f"  {country} {month}: +{len(records)} → {total} gesamt")
    print(f"simap {country}: {n_total} Publikationen geladen "
          f"({n_detail_ok} mit Detail), {len(buckets)} Monate")
    return n_total


def available_months(cfg: Config, country: str = "CH") -> list[str]:
    d = _raw_dir(cfg, country)
    return sorted(p.stem for p in d.glob("*.jsonl")) if d.exists() else []


# ── Parser: Bronze-JSON → Silber-Zeilen ──────────────────────────────────────────────
# simap ist JSON (kein eForms) → eigener Parser, mappt auf dasselbe Silber-Schema wie TED/DÖE.
# Universelle Felder → Standard-Spalten; CH-Spezifika (BKP/WTO/Rechtsmittel …) → attributes
# (Catch-all, „kein Datenverlust") — daraus speist der Export später l.extras[].

import re as _re

_TAG = _re.compile(r"<[^>]+>")
# simap-Ordnungstyp → unser contract_nature (works/services/supplies)
_NATURE = {"construction": "works", "service": "services", "services": "services",
           "supply": "supplies", "delivery": "supplies", "goods": "supplies"}
# pubType → notice_kind (analog TED: cn=Ausschreibung, can=Zuschlag, pin=Vorinfo)
_KIND = {"tender": "cn", "award": "can", "preInformation": "pin", "revocation": "revocation",
         "competition": "cn"}


def _pick(node) -> str | None:
    """Mehrsprachiges {de,fr,it,en} → ein String (de bevorzugt). Auch schon-String durchlassen."""
    if node is None:
        return None
    if isinstance(node, str):
        return node or None
    if isinstance(node, dict):
        for lang in ("de", "fr", "it", "en"):
            v = node.get(lang)
            if v:
                return v
    return None


# ── KANTONSKUERZEL → NUTS-3 ──────────────────────────────────────────────────────────
# simap liefert als Leistungsort einen `cantonId` („ZH", „VD", „BE"). Bis 2026-08-23 stand
# der roh in `performance_nuts` — und war damit KEIN NUTS. Folgen, gemessen:
#
#   4.850 Zuschlaege trugen ein zweistelliges Kuerzel und fielen aus JEDER Regionsanzeige
#         (Zuschlagsphase 306 von 306 ohne Region, Lieferantenindex 6 Regionen fuer die
#         gesamte Schweiz)
#   19.572 trugen „CH0" — NUTS-1, also die ganze Schweiz, als Region wertlos
#
# ⚠ Und ein Kuerzel ist gefaehrlicher als eine Luecke: „BE" ist in der Schweiz Bern, im
# NUTS-Raum aber BELGIEN. Ein Verbraucher, der auf das Praefix schaut, ordnet den Kanton
# Bern dem falschen Land zu.
#
# Die Zuordnung ist vollstaendig und geprueft: 26 Kantone auf genau die 26 fuenfstelligen
# CH-NUTS aus `dim_nuts`, ohne Rest auf beiden Seiten.
_KANTON_NUTS = {
    "VD": "CH011", "VS": "CH012", "GE": "CH013",
    "BE": "CH021", "FR": "CH022", "SO": "CH023", "NE": "CH024", "JU": "CH025",
    "BS": "CH031", "BL": "CH032", "AG": "CH033",
    "ZH": "CH040",
    "GL": "CH051", "SH": "CH052", "AR": "CH053", "AI": "CH054", "SG": "CH055",
    "GR": "CH056", "TG": "CH057",
    "LU": "CH061", "UR": "CH062", "SZ": "CH063", "OW": "CH064", "NW": "CH065", "ZG": "CH066",
    "TI": "CH070",
}


def _nuts(canton: str | None) -> str | None:
    """Kantonskuerzel → NUTS-3. Unbekanntes bleibt unveraendert, nicht leer.

    Wer hier auf None abbildet, verliert die Angabe still; ein unbekanntes Kuerzel ist
    eine Auskunft ueber die Quelle und gehoert sichtbar zu bleiben.
    """
    if not canton:
        return None
    return _KANTON_NUTS.get(str(canton).strip().upper(), canton)


def _fassungen(node, feld: str, nid: str, entwerten: bool = False) -> list[dict]:
    """ALLE gefuellten Sprachen eines simap-Knotens als `notice_text`-Zeilen.

    `_pick` waehlt genau eine Sprache aus und wirft den Rest weg — richtig fuer die
    eine `title`-Spalte in `notices`, falsch fuer alles andere: 31 % der simap-Saetze
    (10.139 von 32.592, gemessen 2026-08-23) tragen den Titel in mehr als einer
    Amtssprache, meist de+fr. Ohne diese Zeilen bekommt kein Schweizer Lead im
    Frontend eine Sprachwahl, obwohl der franzoesische Text im Bronze liegt — die
    164 mehrsprachigen CH-Leads von heute stammen AUSNAHMSLOS aus TED.

    Nur wirklich gefuellte Sprachen: simap liefert die nicht belegten als `null`
    MIT Schluessel. Wer die Schluessel zaehlt statt die Werte, meldet vier Sprachen
    und liefert eine.
    """
    if not isinstance(node, dict):
        return []
    zeilen = []
    for lang, wert in node.items():
        if not isinstance(wert, str) or not wert.strip():
            continue
        text = _TAG.sub(" ", wert).strip() if entwerten else wert.strip()
        if text:
            # KEIN `year` in der Zeile: `model.TABLES["notice_text"]` fuehrt die Spalte
            # nicht, das Jahr kommt aus der Partition (`year=…/`). Wer sie mitgibt,
            # schreibt gegen ein Schema, das sie nicht kennt.
            zeilen.append({"notice_id": nid, "lot_id": None, "field": feld,
                           "language": lang, "value": text})
    return zeilen


def _text(node) -> str | None:
    """Wie _pick, aber HTML-Tags raus (orderDescription trägt <p>…)."""
    s = _pick(node)
    return _TAG.sub(" ", s).strip() if s else None


def _date(s: str | None):
    """ISO-Datum/-Zeit ('2026-09-04' / '2026-09-04T11:00:00+02:00') → date. None-tolerant."""
    if not s or not isinstance(s, str):
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _addr_party(addr: dict, role: str, seq: int, nid: str) -> dict | None:
    if not isinstance(addr, dict) or not addr:
        return None
    return {
        "notice_id": nid, "role": role, "seq": seq,
        "name": _pick(addr.get("name")), "national_id": addr.get("id"),
        "town": _pick(addr.get("city")), "postal_code": addr.get("postalCode"),
        "country": addr.get("countryId") or "CH", "nuts": addr.get("cantonId"),
        # PII bleibt in Silber (server-seitig); die Frontend-Grenze zieht der Export.
        "email": addr.get("email"), "phone": addr.get("phone"),
        "contact_person": _pick(addr.get("contactPerson")), "url": _pick(addr.get("url")),
    }


def parse_publication(rec: dict) -> dict[str, list[dict]]:
    """Ein Bronze-Satz {summary, detail} → {tabelle: [zeilen]} im Silber-Schema."""
    s = rec.get("summary") or {}
    d = rec.get("detail") or {}
    base = d.get("base") or {}
    proc = d.get("procurement") or {}
    pinfo = d.get("project-info") or {}
    dates = d.get("dates") or {}
    dec = d.get("decision") or {}
    terms = d.get("terms") or {}
    ref = d.get("referencingPub") or {}

    nid = s.get("publicationId") or base.get("id")
    if not nid:
        return {}
    pubdate = _date(base.get("publicationDate") or s.get("publicationDate"))
    pubtype = s.get("pubType") or base.get("type")
    cpv = (proc.get("cpvCode") or {}).get("code") or (base.get("cpvCode") or {}).get("code")
    desc = _text(proc.get("orderDescription"))
    title = _pick(base.get("title")) or _pick(s.get("title"))

    # Gewinner + Preis + Bieterzahl (Award) — strukturiert, kein NER nötig.
    final_value = value_ccy = award_date = None
    vendors = dec.get("vendors") or []
    if vendors:
        price = (vendors[0].get("price") or {})
        final_value = price.get("price")
        value_ccy = (price.get("currency") or "").upper() or None
    award_date = _date(dec.get("awardDecisionDate"))

    out: dict[str, list[dict]] = {}
    out["notices"] = [{
        "notice_id": nid,
        "publication_number": base.get("publicationNumber") or s.get("publicationNumber"),
        "publication_date": pubdate,
        "country": "CH", "buyer_countries": ["CH"],
        "year": pubdate.year if pubdate else None,
        "month": pubdate.month if pubdate else None,
        "schema_gen": "simap",
        "form_type": pubtype, "notice_kind": _KIND.get(pubtype, pubtype),
        "language": base.get("creationLanguage"),
        "title": title, "description": desc,
        "cpv_main": cpv,
        "performance_nuts": _nuts((proc.get("orderAddress") or {}).get("cantonId")
                                  or (s.get("orderAddress") or {}).get("cantonId")),
        "contract_nature": _NATURE.get(proc.get("orderType") or s.get("projectSubType")),
        "procedure_type": proc.get("processType") or s.get("processType"),
        "submission_deadline": _date(dates.get("offerDeadline")),
        "portal_url": f"{BASE}/de/project-detail/{s.get('id') or base.get('projectId')}",
        "final_value": float(final_value) if final_value is not None else None,
        "value_currency": value_ccy,
        "award_date": award_date,
        "lot_count": len(d.get("lots") or []),
        "text_chars": len(desc) if desc else 0,
        "ref_publication_number": ref.get("publicationNumber"),
    }]

    # Käufer (+ Empfänger, falls abweichend) und Gewinner als Parteien.
    parties = []
    b = _addr_party(pinfo.get("procOfficeAddress"), "buyer", 0, nid)
    if b:
        parties.append(b)
    for i, v in enumerate(vendors):
        va = dict(v.get("vendorAddress") or {})
        va.setdefault("name", v.get("vendorName"))
        va["id"] = v.get("vendorId")
        w = _addr_party(va, "winner", i, nid)
        if w:
            w["name"] = v.get("vendorName") or w["name"]
            parties.append(w)
    if parties:
        out["notice_parties"] = parties

    # Award-Kennzahlen (Bieterzahl!).
    if pubtype == "award" or dec:
        out["awards"] = [{
            "notice_id": nid, "lot_id": None,
            "winner_name": vendors[0].get("vendorName") if vendors else None,
            "winner_national_id": vendors[0].get("vendorId") if vendors else None,
            "num_tenders": dec.get("numberOfSubmissions"),
        }]

    # CPV (Haupt + zusätzliche).
    cpvs = []
    if cpv:
        cpvs.append(cpv)
    for c in (proc.get("additionalCpvCodes") or []):
        code = c.get("code") if isinstance(c, dict) else c
        if code:
            cpvs.append(code)
    if cpvs:
        out["notice_cpv"] = [{"notice_id": nid, "cpv_code": c, "is_main": (i == 0)}
                             for i, c in enumerate(dict.fromkeys(cpvs))]

    # SPRACHFASSUNGEN. Nur wenn es WIRKLICH eine Wahl gibt: eine einzige Fassung ist
    # keine Sprachwahl, sondern nur die Sprache der Veroeffentlichung — die steht schon
    # als `title`/`description` in `notices`. Der Export prueft das noch einmal, aber
    # eine Tabelle, die 22.453 einsprachige Saetze mitschleppt, laedt jeden spaeteren
    # Verbraucher zum selben Fehlschluss ein.
    # BEIDE Titelknoten zusammenlegen, nicht den ersten nehmen. `detail.base.title` und
    # `summary.title` tragen dieselbe Vergabe, aber nicht dieselbe Sprachmenge: 3.511
    # Saetze sind NUR in `summary` mehrsprachig, umgekehrt kein einziger. Ein `or`
    # zwischen beiden haette diese 3.511 stillschweigend auf eine Sprache reduziert.
    # Zusammenlegen ist belegt, nicht geraten: wo beide Knoten dieselbe Sprache fuehren,
    # stimmen sie in 39.533 von 39.533 Faellen woertlich ueberein (gemessen 2026-08-23).
    _jahr = pubdate.year if pubdate else None
    # Nur GEFUELLTE Werte zusammenlegen. Ein schlichtes {**a, **b} kippt die Sache um:
    # beide Knoten fuehren die unbelegten Sprachen als `null` MIT Schluessel, also
    # ueberschreibt das `"fr": null` des einen das gefuellte `"fr"` des anderen. Beim
    # ersten Versuch blieb die Ausbeute deshalb exakt gleich — der Merge lief, brachte
    # aber nichts.
    _titel: dict = {}
    for _knoten in (s.get("title"), base.get("title")):
        if isinstance(_knoten, dict):
            _titel.update({k: v for k, v in _knoten.items()
                           if isinstance(v, str) and v.strip()})
    fassungen = (_fassungen(_titel or base.get("title") or s.get("title"), "title", nid)
                 + _fassungen(proc.get("orderDescription"), "description", nid,
                              entwerten=True))
    if len({z["language"] for z in fassungen}) > 1:
        out["notice_text"] = fassungen

    # CH-Spezifika → attributes (Catch-all; speist später l.extras[]).
    attrs = []

    def _attr(path, value):
        if value not in (None, "", [], "no"):
            attrs.append({"notice_id": nid, "path": path, "value": str(value)})

    _attr("simap/stateContractArea", base.get("stateContractArea") or pinfo.get("stateContractArea"))
    _attr("simap/publicationTed", base.get("publicationTed"))
    _attr("simap/consortiumAllowed", terms.get("consortiumAllowed"))
    _attr("simap/subContractorAllowed", terms.get("subContractorAllowed"))
    _attr("simap/remediesNotice", _text(terms.get("remediesNotice") or dec.get("remediesNotice")))
    for bkp in (proc.get("bkpCodes") or []):
        _attr("simap/bkp", f"{bkp.get('code')} {_pick(bkp.get('label')) or ''}".strip())
    _attr("simap/cpcCode", proc.get("cpcCode"))
    _attr("simap/questionDeadline", (dates.get("qnas") or [{}])[0].get("date"))
    _attr("simap/offerValidityDeadline", dates.get("offerValidityDeadlineDate"))

    # ── Vergabeunterlagen: was Bronze schon weiss ────────────────────────────────────────
    # Diese vier Felder liegen seit dem ersten simap-Ingest im Detail-JSON und wurden nie
    # durchgereicht. Gemessen 2026-08-13 ueber 11.460 Publikationen aus sechs Monaten:
    #
    #   documents_source_simap    4.452   Unterlagen liegen BEI simap
    #   documents_source_url        238   externer Link
    #   documents_source_email      225   nur auf Anfrage
    #   documents_source_address      5   postalisch
    #   (ohne Unterlagen)         6.540
    #
    # Damit steht je Schweizer Lead OHNE einen einzigen Netzaufruf fest, ob es Unterlagen
    # gibt, woher sie kommen, ob sie etwas kosten und in welcher Sprache. Das ist die
    # Vorstufe zum Dokument-Connector — und sie widerlegt zugleich die fruehere Einstufung
    # „simap verlangt Registrierung": die kam von der Website, die API sagt etwas anderes.
    #
    # `hasProjectDocuments` wird NUR bei True geschrieben. `_attr` filtert "no", aber ein
    # boolesches False rutscht als Zeichenkette "False" durch — ein Attribut, das „nein"
    # sagt, ist hier keine Aussage, sondern Rauschen in 6.540 Saetzen.
    if pinfo.get("hasProjectDocuments") is True or d.get("hasProjectDocuments") is True:
        _attr("simap/hasProjectDocuments", "yes")
    _attr("simap/documentsSourceType", pinfo.get("documentsSourceType"))
    _attr("simap/documentsWithCosts", pinfo.get("documentsWithCosts"))
    for spr in (pinfo.get("documentsLanguages") or []):
        _attr("simap/documentsLanguage", spr if isinstance(spr, str) else _pick(spr))
    if attrs:
        out["attributes"] = attrs

    return out


def build_silver(cfg: Config, country: str = "CH", force: bool = False) -> int:
    """Bronze-JSONL → Silber-Parquet (hive: silver/<c>/<table>/year=YYYY/YYYY-simap.parquet).

    Dedup je notice_id (letzter Satz gewinnt). Gibt die Notice-Zahl zurück. Gold-Integration
    (CH-Leads im Explorer) = Schritt 4.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    from . import model

    by_id: dict[str, dict[str, list[dict]]] = {}
    for month in available_months(cfg, country):
        path = _raw_dir(cfg, country) / f"{month}.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                tables = parse_publication(json.loads(line))
            except Exception:
                continue
            nid = (tables.get("notices") or [{}])[0].get("notice_id")
            if nid:
                by_id[nid] = tables

    # Zeilen je Tabelle + Jahr sammeln.
    buckets: dict[str, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for tables in by_id.values():
        year = (tables["notices"][0].get("year")) or 0
        for table, rows in tables.items():
            buckets[table][year].extend(rows)

    for table, by_year in buckets.items():
        schema = model.TABLES[table]
        for year, rows in by_year.items():
            out = cfg.silver_dir / country / table / f"year={year}" / f"{year}-simap.parquet"
            out.parent.mkdir(parents=True, exist_ok=True)
            arrow = pa.Table.from_pylist(rows, schema=schema)
            tmp = out.with_suffix(".part")
            pq.write_table(arrow, tmp, compression="zstd")
            tmp.replace(out)
    n = len(by_id)
    print(f"simap {country} Silber: {n} Notices → {len(buckets)} Tabellen")
    return n


def build_ch_gold(cfg: Config, country: str = "CH") -> int:
    """CH-Silber → schlanke ``gold/CH/{lead_export,lead_geo,lead_deadline}.parquet`` für den
    Web-Explorer. **Bewusst KEINE volle DE-Gold-Pipeline** (Entity-Resolution/Markt-KPIs sind
    DE-getunt und für 40 Notices sinnlos) — nur die Felder, die ``export_web_leads.py`` liest.

    Leads = **offene Ausschreibungen** (``notice_kind='cn'``) mit Frist in der Zukunft. Zuschläge
    (``can``) sind keine Leads (tragen aber Gewinner/Preis/Bieterzahl — später als Markt-Kontext
    über ``ref_publication_number`` verknüpfbar). Geo: Käufer-PLZ → ``dim_plz`` (enthält jetzt CH).
    Der Exporter vereint DE+CH per ``union_by_name`` und setzt ``land`` aus der ``country``-Spalte.
    """
    import duckdb

    g = cfg.gold_dir / country
    g.mkdir(parents=True, exist_ok=True)
    N = f"'{cfg.silver_table_glob('notices', country)}'"
    P = f"'{cfg.silver_table_glob('notice_parties', country)}'"
    A = f"'{cfg.silver_table_glob('awards', country)}'"
    DP = f"'{(cfg.gold_dir / 'DE' / 'dim_plz.parquet').as_posix()}'"
    # Quellen-Dedup: TED-CHE und simap melden dieselben Schweizer Vergaben weitgehend doppelt
    # (gemessen 93,5 % Titelgleichheit im Testmonat). Die zentrale Firewall `govisor/dedupe.py` paart sie
    # inhaltlich; hier fällt die simap-Zwillingszeile, nicht die TED-Zeile — TED ist für CH die
    # reichere Quelle (Ø 1,19 Lose gegen 0, Beschreibung 505 gegen 447 Zeichen, echte Frist
    # 53,2 % gegen 30,5 %). simap-Notices ohne TED-Partner stehen nicht in der Tabelle und
    # bleiben deshalb erhalten — sie sind der eigentliche Beitrag der nationalen Plattform.
    #
    # Fehlt die Datei (Abgleich noch nie gelaufen oder wegen unvollständigem TED-Bestand
    # übersprungen), bleibt es beim bisherigen Verhalten: beide Quellen ungefiltert. Das
    # rauscht sichtbar, verliert aber nichts — die richtige Ausfallrichtung.
    _dedup = g / "notice_duplicates.parquet"
    # Wie in `gold.build_at_gold`: die Master-Bedingung gehoert dazu. Ohne sie faellt die
    # simap-Zeile auch dann, wenn ihre TED-Entsprechung nicht mehr lead-faehig ist, und die
    # Vergabe verschwindet ganz. Diese Bruecke ist nicht mehr im Tageslauf, aber ueber die
    # CLI erreichbar — ein erreichbarer Pfad mit der gefaehrlichen Haelfte einer Regel ist
    # schlimmer als gar keiner. Eine Kopie der Bedingung waere genau die Verzweigung, die
    # spaeter nur an einer Stelle nachgezogen wird, deshalb der Helfer aus `gold`.
    from . import gold as _gold
    DEDUP_EXCLUDE = (_gold._redundante_zweitquelle_sql(cfg, country)
                     if _dedup.exists() else "")
    LEAD = ("n.notice_kind='cn' AND n.submission_deadline >= current_date"  # offene Ausschreibungen
            + DEDUP_EXCLUDE)
    con = duckdb.connect()

    # Titel-Token (Wörter ≥5 Zeichen, entstopwortet grob über Länge) für die Vor-Zuschlag-Ähnlichkeit.
    _tok = ("list_filter(string_split(regexp_replace(lower({c}), '[^a-zäöü0-9 ]', ' ', 'g'), ' '),"
            " w -> length(w) >= 5)")
    con.execute(f"""COPY (
      WITH buyer AS (
        SELECT notice_id, any_value(name) buyer_name,
               any_value(regexp_extract(postal_code, '([0-9]{{4}})', 1)) plz,
               any_value(nuts) canton, any_value(town) town
        FROM read_parquet({P}, hive_partitioning=1) WHERE role='buyer' GROUP BY notice_id),
      -- CH-Zuschläge mit Gewinner + Bieterzahl + Käufer + CPV + Titel + Jahr
      awn AS (
        SELECT a.notice_id, bu.buyer_name, an.cpv_main, an.title AS atitle,
               a.winner_name, a.num_tenders, year(an.publication_date) AS ayear
        FROM read_parquet({A}, hive_partitioning=1) a
        JOIN read_parquet({N}, hive_partitioning=1) an ON an.notice_id = a.notice_id
        JOIN buyer bu ON bu.notice_id = a.notice_id
        WHERE an.notice_kind = 'can' AND a.winner_name IS NOT NULL),
      -- Bester Vor-Zuschlag je offener Ausschreibung: gleicher Käufer + volle CPV + Titel-Token-
      -- Überlappung (reduziert Fehl-Zuordnung bei anderem Los/Phase). Jüngster gewinnt.
      matched AS (
        SELECT n.notice_id AS lead_id, awn.winner_name, awn.num_tenders, awn.ayear,
               row_number() OVER (PARTITION BY n.notice_id ORDER BY awn.ayear DESC NULLS LAST) rn
        FROM read_parquet({N}, hive_partitioning=1) n
        JOIN buyer b ON b.notice_id = n.notice_id
        JOIN awn ON awn.buyer_name = b.buyer_name AND awn.cpv_main = n.cpv_main
        WHERE {LEAD}
          AND list_has_any({_tok.format(c='n.title')}, {_tok.format(c='awn.atitle')}))
      SELECT n.notice_id AS lead_id, n.title, n.description,
             length(coalesce(n.description, '')) >= 1000 AS has_detailed_description,
             b.buyer_name, n.performance_nuts AS buyer_nuts, b.town AS buyer_region_name,
             n.cpv_main AS cpv_code, n.contract_nature,
             'open' AS phase,
             (m.winner_name IS NULL) AS is_new_tender,   -- mit Vor-Zuschlag = Folgevergabe, sonst Neu
             n.submission_deadline AS deadline_date,
             date_diff('day', current_date, n.submission_deadline) AS days_to_deadline,
             n.portal_url AS source_url, n.portal_url AS documents_url,
             FALSE AS is_nationwide, 'CH' AS country,
             -- Vor-Zuschlag-Kontext: Amtsinhaber unsicher (evtl. anderes Los), Bieterzahl echt.
             m.winner_name AS incumbent_name,
             m.ayear AS incumbent_since_year,
             CASE WHEN m.winner_name IS NOT NULL THEN 'uncertain' END AS incumbent_source,
             CASE WHEN m.winner_name IS NOT NULL THEN 0.55 END AS incumbent_confidence,
             m.num_tenders AS n_bidders,
             CASE WHEN m.num_tenders IS NOT NULL THEN 'actual' END AS competition_source,
             CASE WHEN m.num_tenders IS NULL THEN NULL
                  WHEN m.num_tenders <= 2 THEN 'low'
                  WHEN m.num_tenders <= 5 THEN 'medium' ELSE 'high' END AS competition_level
      FROM read_parquet({N}, hive_partitioning=1) n
      LEFT JOIN buyer b ON b.notice_id = n.notice_id
      LEFT JOIN matched m ON m.lead_id = n.notice_id AND m.rn = 1
      WHERE {LEAD}
    ) TO '{(g / 'lead_export.parquet').as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)""")

    con.execute(f"""COPY (
      WITH buyer AS (
        SELECT notice_id, any_value(regexp_extract(postal_code, '([0-9]{{4}})', 1)) plz,
               any_value(town) town
        FROM read_parquet({P}, hive_partitioning=1) WHERE role='buyer' GROUP BY notice_id)
      SELECT n.notice_id AS lead_id, dp.lat, dp.lon, b.plz, b.town AS ort,
             CASE WHEN dp.lat IS NOT NULL THEN 'plz' ELSE 'none' END AS geo_source
      FROM read_parquet({N}, hive_partitioning=1) n
      LEFT JOIN buyer b ON b.notice_id = n.notice_id
      LEFT JOIN read_parquet({DP}) dp ON dp.plz = b.plz AND dp.country = 'CH'
      WHERE {LEAD}
    ) TO '{(g / 'lead_geo.parquet').as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)""")

    # CH-Fristen sind ECHT (aus submission_deadline) — eigenes lead_deadline, damit der Exporter
    # sie nicht als „geschätzt" labelt.
    con.execute(f"""COPY (
      SELECT n.notice_id, n.submission_deadline AS deadline_date, 'echt' AS deadline_source
      FROM read_parquet({N}, hive_partitioning=1) n WHERE {LEAD}
    ) TO '{(g / 'lead_deadline.parquet').as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)""")

    n = con.execute(f"SELECT count(*) FROM read_parquet('{(g / 'lead_export.parquet').as_posix()}')").fetchone()[0]
    con.close()
    print(f"simap {country} Gold: {n} offene Ausschreibungen → lead_export/lead_geo/lead_deadline")
    return n


def abgeschlossene_projekte(cfg, country: str = "CH") -> set[str]:
    """simap-Projekte, die nachweislich durch sind — Zuschlag, Abbruch oder Widerruf.

    **Warum es das braucht.** Eine Schweizer Vergabe erscheint bei uns doppelt: als
    TED-CHE-Notice (mit TED-Kennung) und als simap-Notice (mit simap-UUID). Wird sie
    vergeben, veroeffentlicht simap den Zuschlag — aber unter der UUID. Die TED-Zeile bleibt
    `notice_kind='cn'` mit ihrer alten, oft weit in der Zukunft liegenden Frist und gilt
    damit ewig als offene Ausschreibung. Gemessen am 2026-08-15: die Vergabe 505197_2025 war
    seit dem 18.11.2025 vergeben und stand bei uns mit Frist 15.09.2026 als offen.

    **Die Bruecke liegt schon im Bestand** — `portal_url` der simap-Notice traegt dieselbe
    Projekt-ID, die in der `documents_url` der TED-Zeile steckt. Es braucht also keinen
    einzigen Netzaufruf, nur den Abgleich.

    Gegen die oeffentliche Schnittstelle geprueft (`project-header.latestPublication.pubType`,
    928 offene CH-Leads einzeln abgefragt): **3 Treffer, 3 bestaetigt, 0 Fehlalarme unter den
    925 echt offenen.** Der Anteil ist heute klein (0,3 %), aber er waechst mit jedem Monat,
    den der Bestand aelter wird — jede offene Ausschreibung wird irgendwann vergeben.
    """
    import duckdb

    con = duckdb.connect()
    try:
        pids = con.execute(f"""
          SELECT DISTINCT regexp_extract(portal_url, 'project-detail/([0-9a-f-]+)', 1)
          FROM read_parquet('{cfg.silver_table_glob('notices', country)}', hive_partitioning=1)
          WHERE portal_url LIKE '%project-detail/%'
            AND notice_kind IN ('can', 'abandonment', 'revocation')""").fetchall()
    finally:
        con.close()
    return {p[0] for p in pids if p[0]}


def _juengste_dokument_flagge_sql(cfg, country: str) -> str:
    """SQL für: Projekt-ID → hat die JÜNGSTE Publikation Unterlagen?

    ⚠ **Die jüngste, nicht irgendeine.** `hasProjectDocuments` hängt an der einzelnen
    Publikation, nicht am Projekt. Ein Maximum über alle Publikationen eines Projekts liegt
    messbar schlechter: gegen die 928 einzeln abgefragten Wahrheitswerte 33 Fehlalarme
    statt 12 (typischer Fall: die alte Ausschreibung hatte Unterlagen, die aktuelle
    Zuschlagsmeldung hat keine — wir würden „Unterlagen vorhanden" behaupten).
    """
    return f"""
      SELECT pid, hat FROM (
        SELECT regexp_extract(n.portal_url, 'project-detail/([0-9a-f-]+)', 1) AS pid,
               max(CASE WHEN a.path = 'simap/hasProjectDocuments' THEN 1 ELSE 0 END) = 1 AS hat,
               row_number() OVER (
                 PARTITION BY regexp_extract(n.portal_url, 'project-detail/([0-9a-f-]+)', 1)
                 ORDER BY n.publication_date DESC NULLS LAST,
                          n.publication_number DESC) AS rn
        FROM read_parquet('{cfg.silver_table_glob('notices', country)}', hive_partitioning=1) n
        LEFT JOIN read_parquet('{cfg.silver_table_glob('attributes', country)}',
                               hive_partitioning=1) a ON a.notice_id = n.notice_id
        WHERE n.portal_url LIKE '%project-detail/%'
        GROUP BY 1, n.notice_id, n.publication_date, n.publication_number)
      WHERE rn = 1"""


def ergaenze_dokument_flagge(cfg, country: str = "CH") -> int:
    """`has_documents` auf den TED-CHE-Leads aus der simap-Zeile desselben Projekts füllen.

    **Das Problem.** Das Feld wird aus dem Attribut `simap/hasProjectDocuments` gebaut, und
    das trägt nur die simap-Zeile. Unsere Schweizer Leads stammen aber überwiegend aus
    TED-CHE — sie haben das Attribut nie gesehen und standen deshalb ausnahmslos auf `false`.
    Gemessen an 928 offenen CH-Leads: **765 davon falsch**, die Flagge war für CH wertlos.

    **Die Brücke ist dieselbe wie bei `entferne_abgeschlossene`** — Projekt-ID aus dem
    `context` der `documents_url` gegen Projekt-ID im `portal_url` der simap-Zeile. Kein
    Netzaufruf.

    **Gemessene Güte** (gegen 928 einzeln abgefragte `project-header.hasProjectDocuments`):
    848 richtig (91,4 %), 22 falsch (2,4 %, davon 12 zu optimistisch), 58 unbekannt (6,3 %,
    kein simap-Geschwister im Bestand). Die 58 bleiben wie bisher auf `false` — das Feld ist
    boolesch, und „lieber nichts versprechen" ist die richtige Ausfallrichtung.

    ⚠ Die Flagge sagt nur, dass es Unterlagen GIBT. Holen kann sie in CH niemand ohne
    Firmenregistrierung und Interessensbekundung (s. `simap_docs.interesse_bekunden`).
    """
    import duckdb

    from .simap_docs import projekt_id

    pfad = (cfg.gold_dir / country / "lead_export.parquet")
    if not pfad.exists():
        return 0

    con = duckdb.connect()
    try:
        con.create_function("_simap_pid", lambda u: projekt_id(u) or "",
                            ["VARCHAR"], "VARCHAR")
        con.execute("CREATE TEMP TABLE flagge AS "
                    + _juengste_dokument_flagge_sql(cfg, country))
        # coalesce um die Brücke: fehlt das Geschwister, bleibt der alte Wert stehen.
        NEU = ("coalesce(f.hat, l.has_documents)")
        geaendert = con.execute(f"""
          SELECT count(*) FROM read_parquet('{pfad.as_posix()}') l
          LEFT JOIN flagge f ON f.pid = _simap_pid(l.documents_url)
          WHERE {NEU} IS DISTINCT FROM l.has_documents""").fetchone()[0]
        if geaendert:
            tmp = pfad.with_suffix(".neu.parquet")
            con.execute(f"""COPY (
              SELECT l.* REPLACE ({NEU} AS has_documents)
              FROM read_parquet('{pfad.as_posix()}') l
              LEFT JOIN flagge f ON f.pid = _simap_pid(l.documents_url)
            ) TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)""")
            tmp.replace(pfad)
    finally:
        con.close()
    print(f"simap {country}: has_documents auf {geaendert} Leads aus der Projekt-Brücke gefüllt")
    return geaendert


def entferne_abgeschlossene(cfg, country: str = "CH") -> int:
    """Vergebene/abgebrochene Vorgaenge aus `lead_export` nehmen. Gibt die Zahl zurueck.

    **Entfernen statt markieren, ausnahmsweise.** Der Projektgrundsatz lautet sonst „Fehler
    markieren statt wegwerfen" — hier ist aber nichts fehlerhaft und nichts geht verloren:
    die Notice bleibt vollstaendig im Silber, die Zeile bleibt in `leads.parquet`, und ueber
    den Zuschlag taucht der Vorgang spaeter im Auslauf-Radar wieder auf. Es faellt allein die
    Zusage weg, das Frontend duerfe sie als *offene Gelegenheit* anbieten. Eine vergebene
    Ausschreibung als offen anzuzeigen waere die teurere Unehrlichkeit.

    ⚠ FK-Richtung beachtet: `verify` prueft `lead_export.lead_id → leads.lead_id`.
    `lead_export` ist das Kind, Zeilen dort zu entfernen erzeugt keine Waisen. Andersherum
    waere es ein Fehler.
    """
    import duckdb

    from .simap_docs import projekt_id

    pfad = (cfg.gold_dir / country / "lead_export.parquet")
    if not pfad.exists():
        return 0
    erledigt = abgeschlossene_projekte(cfg, country)
    if not erledigt:
        return 0

    # NULL-frei halten: DuckDB bricht eine UDF ab, die NULL zurueckgibt („null_handling was
    # set to DEFAULT"), und NULL ist ausserdem genau der Wert, der die Filterlogik unten
    # kippt. Ein leerer String kann nie in `erledigt` stehen — er ist der sichere Nicht-Treffer.
    def _pid(url):
        return projekt_id(url) or ""

    con = duckdb.connect()
    try:
        con.create_function("_simap_pid", _pid, ["VARCHAR"], "VARCHAR")
        con.execute("CREATE TEMP TABLE erledigt(pid VARCHAR)")
        con.executemany("INSERT INTO erledigt VALUES (?)", [(p,) for p in erledigt])
        # ⚠ `coalesce(..., FALSE)` ist hier NICHT Kosmetik. `_simap_pid` gibt bei jeder
        # Nicht-simap-URL NULL zurueck, `NULL IN (…)` ist NULL, und `NOT (TRUE AND NULL)`
        # ist NULL — also nicht wahr, also faellt die Zeile aus dem `WHERE` der Gegenprobe.
        # Ohne das Coalesce loeschte dieser Schritt beim ersten Lauf **859 statt 3** Zeilen:
        # jeden offenen Lead ohne simap-Link. Die Zaehlabfrage merkte davon nichts, weil sie
        # die Bedingung positiv formuliert und NULL dort einfach nicht zaehlt — Zaehlung und
        # Loeschung waren nicht dieselbe Aussage. Genau deshalb prueft der Test unten die
        # UEBERLEBENDEN, nicht die Zahl der Entfernten.
        TRIFFT = ("phase = 'open' AND coalesce(_simap_pid(documents_url) "
                  "IN (SELECT pid FROM erledigt), FALSE)")
        weg = con.execute(f"""
          SELECT count(*) FROM read_parquet('{pfad.as_posix()}') WHERE {TRIFFT}
        """).fetchone()[0]
        if weg:
            tmp = pfad.with_suffix(".neu.parquet")
            con.execute(f"""COPY (
              SELECT * FROM read_parquet('{pfad.as_posix()}') WHERE NOT ({TRIFFT})
            ) TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)""")
            tmp.replace(pfad)                       # atomar, kein halb geschriebener Stand
    finally:
        con.close()
    print(f"simap {country}: {weg} vergebene/abgebrochene Vorgänge aus lead_export entfernt")
    return weg
