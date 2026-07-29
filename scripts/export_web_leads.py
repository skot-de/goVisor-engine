"""Exportiert echte Gold-Leads in die UI-Lead-Form des Web-Explorers (JSON).

Mappt `lead_export` (+ `lead_lot`, `dim_cpv_label`, `dim_cpv`) auf die Objektform,
die die Prototyp-Renderer erwarten. Felder, die es in Gold nicht gibt (Kommentare,
Team-Log, Begriffs-Extraktion, Angebotsaufwand-Details), bleiben leer/na — das
Datenblatt-Prinzip (Übergabenotiz §3) zeigt Fehlendes ehrlich an, statt es zu erfinden.

Schreibt `web/data/leads-<branche>.json` (je Grundraum gekappt) + `web/data/branchen.json`.
Lokal-first: kein Supabase nötig. Später durch eine Live-Query ersetzbar.
"""
import duckdb, json, pathlib
from datetime import date

TODAY = date.today()


def days_until(d):
    """Tage von HEUTE bis zum Datum d (date/Timestamp) — für frische, nicht build-relative
    Fristen. None bei fehlendem/ungültigem Datum (inkl. pandas NaT)."""
    if d is None:
        return None
    try:
        if d != d:
            return None
    except Exception:
        pass
    try:
        dd = d.date() if hasattr(d, "date") else d
        return (dd - TODAY).days
    except Exception:
        return None

CAP = 6000          # Leads je Grundraum (nach Dringlichkeit). Client-seitiges Filtern deckelt
                    # bei ein paar Tausend; der volle Bestand (Bau 48k) braucht die Server-Query.
OUT = pathlib.Path("web/data"); OUT.mkdir(parents=True, exist_ok=True)
con = duckdb.connect()
G = "data/gold/DE"


def _union(table):
    """DE-Gold + jede weitere ``gold/<CC>/<table>.parquet`` (CH, AT, künftige) per union_by_name —
    jede Quelle füllt nur ihre Spalten, fehlende werden NULL (DACH-Mehrquellen ohne Schema-Zwang).
    Unterschieden über die country-Spalte (→ land). DE zuerst (Basis-Schema)."""
    others = sorted(str(p) for p in pathlib.Path("data/gold").glob(f"*/{table}.parquet")
                    if p.parent.name != "DE")
    files = [f"{G}/{table}.parquet"] + others
    lst = ", ".join(f"'{f}'" for f in files)
    return f"read_parquet([{lst}], union_by_name=true)"


E = _union("lead_export")
CL = f"read_parquet('{G}/dim_cpv_label.parquet')"
DC = f"read_parquet('{G}/dim_cpv.parquet')"
LOTS = f"read_parquet('{G}/lead_lot.parquet')"
BS = f"read_parquet('{G}/buyer_stats.parquet')"
ATTR = "read_parquet('data/silver/DE/attributes/*/*.parquet', hive_partitioning=1)"
MO = f"read_parquet('{G}/market_opportunity.parquet')"
CS = f"read_parquet('{G}/contractor_stats.parquet')"
EI = f"read_parquet('{G}/entity_identity.parquet')"
DL = _union("lead_deadline")                        # Angebotsfrist-Herkunft (#16), DE+CH
LG = _union("lead_geo")                              # Koordinate je Lead (echter km-Radius), DE+CH
PLZ = f"read_parquet('{G}/dim_plz.parquet')"        # PLZ→Zentroid für die PLZ-Umkreissuche
# Vorgänger-Link: offene Leads (ohne eigenen Zuschlag) erben Incumbent/Bieterzahl/Kette vom
# jüngsten passenden Vorgänger-Zuschlag. Guard: fehlt die Tabelle, leerer Stub (kein Join-Fehler).
_LP_PATH = f"{G}/lead_predecessor.parquet"
LP = (f"read_parquet('{_LP_PATH}')" if pathlib.Path(_LP_PATH).exists() else
      "(SELECT NULL::VARCHAR lead_id, NULL::VARCHAR incumbent_name, NULL::BIGINT n_bidders, "
      "NULL::VARCHAR competition_level, NULL::BIGINT chain_depth, NULL::BIGINT incumbent_since_year "
      "WHERE false)")
# Dokument-Signale (aus den Vergabeunterlagen extrahiert): überschreiben die dünnen eForms-
# Aufwand-Felder, wo Unterlagen vorliegen. Guard: fehlt die Tabelle, leerer Stub.
_DS_PATH = f"data/docs/{'DE'}/doc_signals.parquet"
DS = (f"read_parquet('{_DS_PATH}')" if pathlib.Path(_DS_PATH).exists() else
      "(SELECT NULL::VARCHAR notice_id, NULL::BOOLEAN guarantee_required, NULL::BIGINT binding_days, "
      "NULL::BIGINT eligibility_count, NULL::VARCHAR certificates, NULL::BOOLEAN variants_allowed "
      "WHERE false)")


def de_date(d):
    """date/Timestamp → 'TT.MM.JJJJ' (oder None). Fängt None, NaN und pandas NaT ab."""
    if d is None:
        return None
    try:
        if d != d:          # NaN und pandas NaT sind ungleich sich selbst
            return None
    except Exception:
        pass
    try:
        return d.strftime("%d.%m.%Y")
    except (AttributeError, ValueError):
        return None

_seg = None
def segments():
    """CPV-Segment-Chancen (market_opportunity) je cpv4 — für den Markt-Tab. §8-konform:
    Nachfrage × Schwäche × Struktur + Top-Dominatoren, KEIN regionaler Makro-Prädiktor."""
    global _seg
    if _seg is None:
        _seg = {}
        for r in con.execute(f"""SELECT cpv4, segment_label, n_awards, erfolglos_pct,
                single_bidder_pct, struktur, top3_share, chronic_needs, opportunity_score,
                top_dominators, window_start, window_end FROM {MO}""").fetchall():
            (cpv4, label, na, erf, sb, struk, t3, chron, score, dom, ws, we) = r
            _seg[cpv4] = {
                "cpv4": cpv4, "label": label, "nAwards": int(na or 0),
                "erfolglos": round(erf) if erf is not None else None,
                "singleBidder": round(sb) if sb is not None else None,
                "struktur": struk, "top3": round((t3 or 0) * 100),
                "chronic": int(chron or 0), "score": int(score) if score is not None else None,
                "zeitraum": f"{ws}–{we}" if ws and we else None,
                "dominatoren": [{"n": d["name"], "wins": int(d["wins"]),
                                 "share": round(d["share"] * 100, 1)} for d in (dom or [])[:5]],
            }
    return _seg


def aufwand_for(ids):
    """Angebotsaufwand aus `attributes`: Bietungsbürgschaft + Bindefrist. Ehrlich sparse —
    nur diese zwei sind verlässlich verknüpfbar (E-Abgabe/Lebenslauf sind im flachen
    Attribut-Baum nicht sauber zuzuordnen). Der Aufwand-BALKEN erscheint erst bei ≥2
    bekannten Feldern (aufwandStufe); einzeln füllen sie die Datenblatt-Zeilen."""
    if not ids:
        return {}
    con.execute("CREATE OR REPLACE TEMP TABLE _ai(id VARCHAR)")
    con.executemany("INSERT INTO _ai VALUES (?)", [(i,) for i in ids])
    rows = con.execute(f"""
        SELECT notice_id,
          max(CASE WHEN path ILIKE '%RequiredFinancialGuarantee.GuaranteeTypeCode'
                    AND path NOT ILIKE '%listName' THEN lower(value) END) AS guar,
          max(CASE WHEN path ILIKE '%TenderValidityPeriod.DurationMeasure'
                    AND path NOT ILIKE '%unitCode' THEN try_cast(value AS INTEGER) END) AS bindnum,
          max(CASE WHEN path ILIKE '%TenderValidityPeriod.DurationMeasure@unitCode'
                    THEN upper(value) END) AS bindunit
        FROM {ATTR}
        WHERE notice_id IN (SELECT id FROM _ai)
          AND (path ILIKE '%RequiredFinancialGuarantee.GuaranteeTypeCode'
               OR path ILIKE '%TenderValidityPeriod.DurationMeasure%')
        GROUP BY 1""").fetchall()
    out = {}
    for nid, guar, bindnum, bindunit in rows:
        a = {}
        if guar is not None:
            a["buergschaft"] = ("nein" if guar in ("false", "none")
                                else "ja · vorläufig" if guar == "provisional" else "ja")
        if bindnum:
            days = bindnum * (30 if bindunit in ("MONTH", "MONTHS") else 1)
            a["bindefrist"] = f"{days} Tage"
        if a:
            out[nid] = a
    return out

BRANCHE_LABEL = {"it": "IT & Software", "bau": "Bau & Infrastruktur",
                 "medizin": "Medizin & Gesundheit", "beratung": "Beratung & Dienstleistung",
                 "sicherheit": "Sicherheit & Verteidigung", "energie": "Energie & Versorgung"}


def conc_band(t):
    return "fragmentiert" if t < 40 else "moderat" if t <= 70 else "oligopol"


def de(n):
    return f"{int(n):,}".replace(",", ".")


_prof_cache = {}


def lot_limits_for(ids):
    """Los-Grenzen aus attributes (eForms LotDistribution): max. Lose je Bieter zum
    Anbieten (BT-1340) und zum Gewinnen (BT-1341). Speist die „Partner nötig?"-Sektion —
    wer höchstens N von M Losen gewinnen darf, braucht für den Gesamtauftrag Partner."""
    if not ids:
        return {}
    con.execute("CREATE OR REPLACE TEMP TABLE _li(id VARCHAR)")
    con.executemany("INSERT INTO _li VALUES (?)", [(i,) for i in ids])
    rows = con.execute(f"""
        SELECT notice_id,
          max(CASE WHEN path ILIKE '%LotDistribution.MaximumLotsSubmittedNumeric'
                    THEN try_cast(value AS INTEGER) END) AS max_bid,
          max(CASE WHEN path ILIKE '%LotDistribution.MaximumLotsAwardedNumeric'
                    THEN try_cast(value AS INTEGER) END) AS max_win
        FROM {ATTR}
        WHERE notice_id IN (SELECT id FROM _li)
          AND path ILIKE '%LotDistribution.MaximumLots%'
        GROUP BY 1""").fetchall()
    return {nid: (mb, mw) for nid, mb, mw in rows}


def incumbent_stats_for(ids):
    """Vergleichs-Zahlen des Amtsinhabers im CPV-Feld des Leads (Direktvergleich, Ticket #3).
    incumbent_group_id (Identität) → Entities → contractor_stats(cpv_class=cpv4), aggregiert:
    Gruppen-Wins summiert, Anteil = Summe der Entity-Anteile (= Gruppe/Klassen-Total), bester Rang."""
    if not ids:
        return {}
    ph = ",".join(f"'{i}'" for i in ids)
    rows = con.execute(f"""
      WITH li AS (
        SELECT lead_id, incumbent_group_id, substr(cpv_code, 1, 4) AS cpv4
        FROM {E} WHERE lead_id IN ({ph}) AND incumbent_group_id IS NOT NULL AND cpv_code IS NOT NULL),
      ge AS (SELECT li.lead_id, li.cpv4, ei.entity_id
             FROM li JOIN {EI} ei ON ei.identity_id = li.incumbent_group_id),
      j AS (SELECT ge.lead_id, cs.total_wins, cs.market_share_by_wins, cs.market_rank, cs.trend_yoy,
                   row_number() OVER (PARTITION BY ge.lead_id ORDER BY cs.total_wins DESC) rn
            FROM ge JOIN {CS} cs ON cs.entity_id = ge.entity_id AND cs.cpv_class = ge.cpv4)
      SELECT lead_id, sum(total_wins) AS wins, sum(market_share_by_wins) AS share,
             min(market_rank) AS rang, max(trend_yoy) FILTER (WHERE rn = 1) AS trend
      FROM j GROUP BY 1""").fetchall()
    out = {}
    for lead_id, wins, share, rang, trend in rows:
        t = None
        if trend is not None:
            t = max(-95, min(300, round(float(trend) * 100)))   # extreme Kleinbasis-Ausreißer kappen
        out[lead_id] = {
            "wins": int(wins or 0),
            "marktanteil": round(float(share) * 100) if share else None,
            "rang": int(rang) if rang is not None else None,
            "trend": t,
        }
    return out


def market_summary(key):
    """Marktblöcke für den Chancen-Tab (Branche-weit, ohne Firmenprofil füllbar, §8):
    aktivste Vergabestellen + einstiegsfreundliche offene Ausschreibungen + Eckzahlen."""
    where = f"""FROM {E} e LEFT JOIN {DC} b ON b.division = substr(e.cpv_code, 1, 2)
                WHERE ({BRANCHE}) = '{key}'"""
    tot, offen, stellen = con.execute(f"""
        SELECT count(*), count(*) FILTER (WHERE phase='open'), count(DISTINCT buyer_name) {where}""").fetchone()
    top = con.execute(f"""
        SELECT buyer_name, count(*) n, count(*) FILTER (WHERE phase='open') offen
        {where} AND buyer_name IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 6""").fetchall()
    ein = con.execute(f"""
        SELECT title, value_eur, cpv_code {where} AND phase='open' AND value_eur IS NOT NULL
        AND value_eur > 0 ORDER BY value_eur ASC LIMIT 5""").fetchall()
    return {
        "vergaben": de(tot), "offen": de(offen), "stellen": de(stellen),
        "regionen": None,  # ohne Firmenprofil kein Regionsbezug
        "topStellen": [{"n": n, "vergaben": v, "offen": o} for n, v, o in top],
        "einstieg": [{"n": (t[:60] + "…") if len(t) > 60 else t, "wert": eur(val), "bieter": None}
                     for t, val, _ in ein],
    }


def buyer_profiles(names):
    """Echte Vergabestellen-Profile aus buyer_stats (+ CPV-Mix aus lead_export als Proxy).
    Fehlende Felder (Median/Volumen/Single-Bidder/Retention) bleiben null → der Renderer
    zeigt sie ehrlich als „zu wenig Daten"."""
    todo = [n for n in names if n and n not in _prof_cache]
    if todo:
        con.execute("CREATE OR REPLACE TEMP TABLE _bn(name VARCHAR)")
        con.executemany("INSERT INTO _bn VALUES (?)", [(n,) for n in todo])
        stats = {r["buyer_name"]: r for r in con.execute(
            f"SELECT * FROM {BS} WHERE buyer_name IN (SELECT name FROM _bn)").df().to_dict("records")}
        mix = {}
        for bn, br, n in con.execute(f"""
                SELECT e.buyer_name, {BRANCHE} AS br, count(*) n
                FROM {E} e LEFT JOIN {DC} b ON b.division = substr(e.cpv_code, 1, 2)
                WHERE e.buyer_name IN (SELECT name FROM _bn) GROUP BY 1, 2""").fetchall():
            mix.setdefault(bn, {})[br] = n
        for n in todo:
            st = stats.get(n)
            if not st:
                _prof_cache[n] = None
                continue
            total = int(st["total_awards"] or 0)
            wy = int(st["window_years"] or 5)
            we = int(st["window_end"] or 2026)
            tw = list(st["top_contractors"]) if st["top_contractors"] is not None else []
            top3 = round(sum(int(w["wins"]) for w in tw[:3]) / total * 100) if total else 0
            dc = int(st["distinct_contractors"] or 0)
            dec = st["avg_decision_days"]
            dec = int(dec) if (dec is not None and dec == dec) else None  # NaN-sicher
            _prof_cache[n] = {
                "name": n, "sparse": total < 20,
                "total": de(total) if total else None, "zeitraum": f"{we-wy+1}–{we}",
                "perYear": str(round(total / wy)) if (wy and total) else None,
                "decision": f"{dec} Tage" if dec is not None else None,
                "median": None, "volume": None, "coverage": None,
                "division": None, "categories": None,
                "winners": de(dc) if dc else None,
                "top3": top3, "concentration": conc_band(top3),
                "topWinners": [{"n": w["name"], "w": de(int(w["wins"])),
                                "pct": round(int(w["wins"]) / total * 100)} for w in tw[:5]] if total else [],
                "winsAvg": str(round(total / dc, 1)).replace(".", ",") if dc else None,
                "single": None, "avgBidders": None, "retention": None, "retentionLevel": None,
                "below": None, "recent": [],
                "_mix": mix.get(n, {}),
            }
    return {n: _prof_cache.get(n) for n in names}


def attach_mix(prof, own_branche):
    """CPV-Mix je Vergabestelle in die Ring-Form bringen; das eigene Feld markieren."""
    p = {k: v for k, v in prof.items() if k != "_mix"}
    counts = prof.get("_mix", {})
    tot = sum(counts.values()) or 1
    items = sorted(counts.items(), key=lambda kv: -kv[1])
    mix, seen = [], set()
    for br, n in items[:4]:
        seen.add(br)
        mix.append({"label": BRANCHE_LABEL.get(br, br), "pct": round(n / tot * 100),
                    "n": str(n), "key": br, "own": br == own_branche})
    if own_branche in counts and own_branche not in seen:
        n = counts[own_branche]
        mix.append({"label": BRANCHE_LABEL.get(own_branche, own_branche),
                    "pct": round(n / tot * 100), "n": str(n), "key": own_branche, "own": True})
    rest = sum(n for br, n in items if br not in {m["key"] for m in mix})
    if rest:
        mix.append({"label": "Sonstige", "pct": round(rest / tot * 100), "n": str(rest), "rest": True})
    p["mix"] = mix
    return p

BRANCHE = """CASE b.branche
  WHEN 'IT' THEN 'it' WHEN 'Elektro' THEN 'it' WHEN 'Messtechnik' THEN 'it'
  WHEN 'Bau' THEN 'bau' WHEN 'Installation' THEN 'bau' WHEN 'Immobilien' THEN 'bau'
    WHEN 'Ingenieur/Architektur' THEN 'bau' WHEN 'Wartung' THEN 'bau'
  WHEN 'Medizin' THEN 'medizin' WHEN 'Gesundheit' THEN 'medizin'
  WHEN 'Sicherheit' THEN 'sicherheit'
  WHEN 'Energie' THEN 'energie' WHEN 'Versorgung' THEN 'energie' WHEN 'Wasser' THEN 'energie'
    WHEN 'Umwelt/Reinigung' THEN 'energie' WHEN 'Chemie' THEN 'energie' WHEN 'Rohstoffe' THEN 'energie'
  ELSE 'beratung' END"""

# Codes → Anzeige-Labels (Vertragsende/Rahmenvertrag/Dienstleistung …) leben jetzt im
# Frontend-Katalog web/lib/labels.js; der Export trägt nur noch die Codes (src/contractKind/
# naturKat). Die *-SRC/LVL-Maps unten sind CODES (echt/schaetz/hoch), auf die das Frontend
# stylt — keine Anzeigetexte, bleiben hier.
SRC = {"expiring": "auslauf", "open": "f02", "planned": "f01"}
NATURKAT = {"services": "dienst", "supplies": "liefer", "works": "bau"}
VAL_SRC = {"actual": "echt", "estimated": "schaetz", "unknown": "unbekannt", None: "unbekannt"}
TIM_SRC = {"actual": "echt", "estimated": "schaetz", "uncertain": "unsicher", "unknown": "unbekannt", None: "unbekannt"}
KONK_SRC = {"actual": "echt", "unknown": "unbekannt", "na": "na", None: "na"}
INC_SRC = {"actual": "echt", "uncertain": "unsicher", None: "echt"}
LVL = {"high": "hoch", "medium": "mittel", "low": "niedrig", "na": "na", None: "na"}
KONK_LVL = {"low": "gering", "medium": "mittel", "high": "hoch", "na": "na", None: "na"}
RAHMEN_OK = {"vgv", "vob", "uvgo", "sektvo"}


def eur(v):
    if v is None:
        return None
    v = float(v)
    if v >= 1_000_000:
        return f"{v/1_000_000:.1f}".replace(".", ",") + " Mio €"
    return f"{int(round(v)):,}".replace(",", ".") + " €"


def lots_for(ids):
    """Lose je Lead (nur echte Titel/Werte) → {lead_id: [ {nr,titel,wert,dauer,region} ]}."""
    if not ids:
        return {}
    con.execute("CREATE OR REPLACE TEMP TABLE _ids(id VARCHAR)")
    con.executemany("INSERT INTO _ids VALUES (?)", [(i,) for i in ids])
    rows = con.execute(f"""
        SELECT lead_id, lot_title, lot_value_eur, duration_months, lot_market_nuts3, lot_cpv_code
        FROM {LOTS} WHERE lead_id IN (SELECT id FROM _ids) AND lot_title IS NOT NULL
        ORDER BY lead_id, lot_id""").fetchall()
    out = {}
    for lid, titel, wert, dur, nuts, cpv in rows:
        lst = out.setdefault(lid, [])
        # cpv/nuts je Los = Relevanzeinheit (#12); Los-Wert bleibt meist offen (Feld ~1 %).
        lst.append({"nr": len(lst) + 1, "titel": titel,
                    "wert": eur(wert) or "Wert offen",
                    "dauer": f"{int(dur)} Monate" if dur else "—",
                    "region": nuts or "", "cpv": cpv or None})
    return out


# CH-Spezifika (Silber-attributes) → l.extras[]: der generische, quellengefüllte „Zusätzliche
# Angaben"-Block (nur belegte Pfade, sprechende Labels + Reihenfolge). Universelle Felder
# (Gewinner/Preis/Bieterzahl/Fristen) gehören NICHT hierher, sondern in ihre Standard-Slots.
CH_ATTR = "data/silver/CH/attributes/*/*.parquet"
EXTRA_LABEL = {  # path → (Label, Sortier-Rang)
    "simap/stateContractArea": ("WTO/GPA-Abkommen", 1),
    "simap/bkp": ("BKP-Bauklasse", 2),
    "simap/cpcCode": ("CPC-Klasse", 3),
    "simap/subContractorAllowed": ("Nachunternehmer zugelassen", 4),
    "simap/remediesNotice": ("Rechtsmittel", 5),
    "simap/publicationTed": ("Auch EU-weit (TED)", 6),
}
_EXTRA_VAL = {"true": "ja", "yes": "ja", "false": "nein", "no": "nein"}


def ch_extras_for(ids):
    """CH-Attributes je Lead → [{label, value}] (nach Rang sortiert). Leer für DE-Leads."""
    if not ids or not pathlib.Path("data/silver/CH").exists():
        return {}
    con.execute("CREATE OR REPLACE TEMP TABLE _eids(id VARCHAR)")
    con.executemany("INSERT INTO _eids VALUES (?)", [(i,) for i in ids])
    rows = con.execute(f"""
        SELECT notice_id, path, value FROM read_parquet('{CH_ATTR}', hive_partitioning=1)
        WHERE notice_id IN (SELECT id FROM _eids)""").fetchall()
    out = {}
    for nid, path, val in rows:
        meta = EXTRA_LABEL.get(path)
        if not meta:
            continue
        raw = str(val).strip()
        if raw.lower() in ("not_specified", "none", ""):
            continue                                  # unbelegt → weglassen, nicht als Roh-Code zeigen
        v = _EXTRA_VAL.get(raw.lower(), raw)
        if len(v) > 160:                              # lange Texte (Rechtsmittel) kappen
            v = v[:160].rstrip() + " …"
        label, rank = meta
        out.setdefault(nid, []).append((rank, {"label": label, "value": v}))
    return {nid: [e for _, e in sorted(items, key=lambda x: x[0])] for nid, items in out.items()}


def export_branche(key):
    rows = con.execute(f"""
        WITH mapped AS (
          SELECT e.*, cl.label AS cpv_label, {BRANCHE} AS ui_branche,
                 dl.deadline_source AS frist_source,
                 lg.lat AS geo_lat, lg.lon AS geo_lon,
                 lp.incumbent_name AS pred_incumbent, lp.n_bidders AS pred_bidders,
                 lp.competition_level AS pred_konk, lp.chain_depth AS pred_chain,
                 lp.incumbent_since_year AS pred_since,
                 ds.guarantee_required AS doc_guarantee, ds.binding_days AS doc_binding,
                 ds.eligibility_count AS doc_eligibility, ds.certificates AS doc_certs,
                 ds.variants_allowed AS doc_variants
          FROM {E} e
          LEFT JOIN {DC} b ON b.division = substr(e.cpv_code, 1, 2)
          LEFT JOIN {CL} cl ON cl.cpv_code = e.cpv_code
          LEFT JOIN {DL} dl ON dl.notice_id = e.lead_id
          LEFT JOIN {LG} lg ON lg.lead_id = e.lead_id
          LEFT JOIN {LP} lp ON lp.lead_id = e.lead_id
          LEFT JOIN {DS} ds ON ds.notice_id = e.lead_id
        )
        , filtered AS (
          SELECT * FROM mapped WHERE ui_branche = '{key}'
            -- Nativ: Auslauf-Radar nur bis 18 Monate Vertragsende (weiter = kein handlungs-
            -- relevanter Lead, nur Ballast). Offene/angekündigte immer; unbekanntes Ende bleibt.
            AND (phase != 'expiring' OR months_to_expiry IS NULL OR months_to_expiry <= 18)
        ), ranked AS (
          SELECT *, row_number() OVER (
            ORDER BY (phase = 'open') DESC,
                     coalesce(days_to_deadline, days_to_expiry, 99999) ASC) AS rn
          FROM filtered
        )
        -- CAP nach Dringlichkeit — aber Nicht-DE-Leads (CH/AT, der DACH-Differenzierer, wenige)
        -- IMMER behalten, sonst verdrängt der große DE-Bestand sie aus dem Umkreis-losen Blick.
        SELECT * EXCLUDE(rn) FROM ranked
        WHERE rn <= {CAP} OR coalesce(country, 'DE') <> 'DE'
        ORDER BY (phase = 'open') DESC,
                 coalesce(days_to_deadline, days_to_expiry, 99999) ASC""").df().to_dict("records")

    lots = lots_for([r["lead_id"] for r in rows])
    leads = []
    for r in rows:
        g = lambda k: (None if (k not in r or r[k] is None or (isinstance(r[k], float) and r[k] != r[k])) else r[k])
        src = SRC.get(g("phase"), "auslauf")
        naturkat = NATURKAT.get(g("contract_nature"))
        rahmen = g("regulatory_regime")
        rahmen = rahmen if rahmen in RAHMEN_OK else None
        # Rahmenvertrag (Zyklus-Doc §7.2): kein bloßes Label, sondern ein Bewertungssignal —
        # der Nennwert unterzeichnet, das reale Abrufvolumen liegt oft um ein Vielfaches höher.
        ist_rahmen = g("contract_kind") == "framework"
        frist_source = g("frist_source")
        frist_date = de_date(g("deadline_date"))
        frist_tage = int(r["days_to_deadline"]) if g("days_to_deadline") is not None else None
        # Bei ECHTER Frist die Tage relativ zu HEUTE aus dem Datum neu rechnen — der gold-
        # gespeicherte days_to_deadline ist build-relativ und veraltet (sonst "-X Tage").
        if frist_source == "echt":
            fresh = days_until(g("deadline_date"))
            if fresh is not None:
                frist_tage = fresh
        # Offene Ausschreibung mit ABGELAUFENER echter Frist = nicht mehr biet-bar → raus aus
        # der Akquise-Liste (Gold behält sie; nur die Frontend-Sicht filtert). Geschätzte
        # Fristen bleiben (Schätzung könnte daneben liegen).
        if src == "f02" and frist_source == "echt" and frist_tage is not None and frist_tage < 0:
            continue
        z = []
        if g("price_weight_pct") is not None:
            z.append({"art": "preis", "label": "Preis", "pct": int(r["price_weight_pct"])})
        if g("quality_weight_pct") is not None:
            z.append({"art": "qualitaet", "label": "Qualität", "pct": int(r["quality_weight_pct"])})
        if g("cost_weight_pct") is not None:
            z.append({"art": "kosten", "label": "Kosten", "pct": int(r["cost_weight_pct"])})

        tage = frist_tage if (src == "f02" and frist_tage is not None) else None
        endTage = int(r["days_to_expiry"]) if g("days_to_expiry") is not None else None
        mte = g("months_to_expiry")
        endet = f"in {int(mte)} Mon." if mte is not None else None

        nb = g("n_bidders")
        # Vorgänger-Fallback: offene Leads (ohne eigenen Zuschlag) erben Incumbent/Bieterzahl/
        # Wettbewerb/Kette vom jüngsten passenden Vorgänger-Zuschlag (build_lead_predecessor).
        use_pred = (not g("incumbent_name")) and bool(g("pred_incumbent"))
        if use_pred and not nb:
            nb = g("pred_bidders")
        konk_wert = f"{int(nb)} Bieter" if nb else "nicht veröffentlicht"
        konk_stufe = KONK_LVL.get(g("competition_level"), "na")
        if konk_stufe == "na":
            konk_stufe = KONK_LVL.get(g("pred_konk"), "na")     # Intensität aus Vorgänger
        wechsel = LVL.get(g("switch_chance"), "na")
        if wechsel == "na":
            wechsel = LVL.get(g("pred_konk"), "na")             # Angreifbarkeit grob aus Vorgänger-Wettbewerb
        pred_chain = g("pred_chain")
        kette = ({"tiefe": int(pred_chain),
                  "seit": str(int(g("pred_since"))) if g("pred_since") else ""}
                 if pred_chain and int(pred_chain) >= 2 else None)
        if use_pred:
            inc_obj = {"name": g("pred_incumbent"),
                       "seit": str(int(g("pred_since"))) if g("pred_since") else "",
                       "src": "uncertain", "hint": "aus dem letzten vergleichbaren Zuschlag desselben Käufers",
                       "groupId": None, "conf": 0.6}
        elif g("incumbent_name"):
            inc_obj = {"name": r["incumbent_name"],
                       "seit": str(int(r["incumbent_since_year"])) if g("incumbent_since_year") else "",
                       "src": INC_SRC.get(g("incumbent_source"), "echt"), "hint": "",
                       "groupId": g("incumbent_group_id"),
                       "conf": float(r["incumbent_confidence"]) if g("incumbent_confidence") is not None else None}
        else:
            inc_obj = None

        leads.append({
            # Sprachneutral: nur Codes (src/contractKind/naturKat/volumen.src). Die deutschen
            # Anzeige-Labels setzt das Frontend über lib/labels.js (applyLabels) — so bleibt
            # die JSON sprachfrei und eine 2. Sprache ist ein Frontend-Katalog, kein Re-Export.
            "id": r["lead_id"], "branche": key, "src": src,
            "titel": g("title") or "(ohne Titel)",
            "buyer": g("buyer_name") or "", "buyerShort": g("buyer_name") or "",
            "beschreibung": g("description") or "",
            "hasDetail": bool(g("has_detailed_description")),
            "cpv": g("cpv_code"), "cpvLabel": g("cpv_label") or g("buyer_activity") or "",
            # Vergabe-Land aus der country-Spalte (DE-Gold hat keine → NULL → Default DE;
            # CH-Gold trägt 'CH'). Speist den DACH-Länderfilter.
            "land": g("country") or "DE",
            "region": g("buyer_region_name") or g("region") or "", "nuts": g("buyer_nuts") or "",
            # Koordinate (Käufersitz) für die echte PLZ-Umkreissuche (Haversine im Frontend);
            # None, wenn kein Geo-Bezug (bundesweite/ortsungebundene Leads) — ehrlich leer.
            "lat": round(float(r["geo_lat"]), 4) if g("geo_lat") is not None else None,
            "lon": round(float(r["geo_lon"]), 4) if g("geo_lon") is not None else None,
            "marktRegion": g("market_nuts3"), "marktRegionOk": bool(g("market_region_known")),
            "is_nationwide": bool(g("is_nationwide")),
            "contractKind": g("contract_kind"),
            "istRahmen": ist_rahmen,
            "naturKat": naturkat or "dienst",
            "rahmen": rahmen,
            "volumen": {"wert": eur(g("value_eur")) or "Wert offen",
                        "src": VAL_SRC.get(g("value_source"), "unbekannt")},
            "timing": {"wert": endet or (f"{tage} Tage" if tage is not None else "offen"),
                       "src": TIM_SRC.get(g("timing_source"), "unbekannt"), "warn": False,
                       "hint": ""},
            "konk": {"wert": konk_wert,
                     "src": KONK_SRC.get(g("competition_source"), "uncertain" if use_pred else "na"),
                     "stufe": konk_stufe,
                     "hint": ("Aus der letzten Zuschlagsbekanntmachung." if g("competition_source") == "actual"
                              else "Aus dem letzten vergleichbaren Zuschlag desselben Käufers." if use_pred else "")},
            "relevanz": "na",  # ohne gepflegtes Profil nicht berechenbar → ehrlich n/a
            "wechsel": wechsel,
            "kette": kette,    # Nachfolge-Kette: {tiefe, seit} — nur wenn ≥2 Verträge belegt
            "neu": bool(g("is_new_tender")) and not use_pred,
            "incumbent": inc_obj,
            "tage": tage, "endTage": endTage, "endet": endet,
            # #16 Angebotsfrist (echte Daten): Datum + Resttage + Herkunft. Uhrzeit/Bieterfragen-
            # Frist sind (noch) nicht in Gold extrahiert → hier ehrlich weggelassen, nicht erfunden.
            "frist": ({"date": frist_date, "tage": frist_tage, "uhrzeit": g("deadline_time"),
                       "src": "echt" if g("frist_source") == "echt" else "schaetz"}
                      if (frist_date or frist_tage is not None) else None),
            # #16-Rest: Bieterfragen-Frist (letzter Tag für Rückfragen). question_deadline ist ein
            # ISO-String „YYYY-MM-DD" (aus SQL substr) → direkt nach TT.MM.JJJJ formatieren.
            "fragefrist": ((lambda q: f"{q[8:10]}.{q[5:7]}.{q[0:4]}")(str(g("question_deadline")))
                           if g("question_deadline") else None),
            "lose": lots.get(r["lead_id"], []), "zuschlag": z,
            # #13 Dokument-Wasserfall: erst der echte Unterlagen-Link (documents_url), sonst nur
            # die Plattform (source_url). `source` hält die zwei sauber auseinander; `access` ist
            # ehrlich 'unknown' — die non-restricted-Markierung ist noch nicht aus dem XML gezogen.
            "unterlagen": ({"url": g("documents_url"), "source": "docs", "access": "unknown"} if g("documents_url")
                           else {"url": g("source_url"), "source": "portal", "access": "unknown"} if g("source_url")
                           else None),
            # #15 Weg A — strukturierte Anforderungen aus eForms. True/False = belegt,
            # None = nicht veröffentlicht (ehrlich weglassen statt „erfüllt" zu behaupten).
            # #15/#18: strukturierte Anforderungen. Dokument-Signale (aus den Vergabeunterlagen)
            # überschreiben die dünnen eForms-Felder, wo Unterlagen vorliegen — sonst eForms.
            "anf": {
                "buergschaft": (bool(g("doc_guarantee")) if g("doc_guarantee") is not None
                                else bool(g("guarantee_required")) if g("guarantee_required") is not None else None),
                "nebenangebote": (bool(g("doc_variants")) if g("doc_variants") is not None
                                  else bool(g("variants_allowed")) if g("variants_allowed") is not None else None),
                "bindefristTage": (int(g("doc_binding")) if g("doc_binding") is not None
                                   else int(r["validity_days"]) if g("validity_days") is not None else None),
                "eignung": (["Nachweis"] * int(g("doc_eligibility")) if g("doc_eligibility")
                            else str(g("selection_types")).split(",") if g("selection_types") else []),
                "zertifikate": (str(g("doc_certs")).split(",") if g("doc_certs") else []),
                "quelle": ("unterlagen" if g("doc_eligibility") or g("doc_guarantee") is not None else "eforms"),
            },
            "status": "ungesichtet", "seen": None, "merk": None,
            "aktualitaet": None, "aufwand": None,
            "comments": [], "log": [], "kw": [], "extrakt": [],
            "hasCmp": bool(g("has_comparables")), "hasContracts": bool(g("has_contract_history")),
        })

    # Echte Vergabestellen-Profile anhängen (Vergabestelle-Tab)
    profs = buyer_profiles(sorted({l["buyer"] for l in leads if l["buyer"]}))
    for l in leads:
        p = profs.get(l["buyer"])
        l["buyerProfile"] = attach_mix(p, l["branche"]) if p else None

    # Angebotsaufwand (Bürgschaft/Bindefrist) aus attributes anhängen
    aufw = aufwand_for([l["id"] for l in leads])
    for l in leads:
        l["aufwand"] = aufw.get(l["id"])  # None → Aufwand-Achse bleibt ehrlich n/a

    # Länderspezifischer „Zusätzliche Angaben"-Block (aktuell CH; generisch, quellengefüllt)
    extras = ch_extras_for([l["id"] for l in leads])
    for l in leads:
        ex = extras.get(l["id"])
        if ex:
            l["extras"] = ex

    # Amtsinhaber-Vergleichszahlen (Direktvergleich) an den incumbent anhängen
    inc = incumbent_stats_for([l["id"] for l in leads if l.get("incumbent")])
    for l in leads:
        if l.get("incumbent") and l["id"] in inc:
            l["incumbent"].update(inc[l["id"]])

    # Los-Grenzen → „Partner nötig?"-Sektion nur, wo man NICHT alle Lose gewinnen darf
    lims = lot_limits_for([l["id"] for l in leads])
    for l in leads:
        lim = lims.get(l["id"])
        nlose = len(l.get("lose") or [])
        if lim and nlose > 1 and lim[1] and lim[1] < nlose:
            l["loseMaxAngebot"] = lim[0] or nlose
            l["loseMaxZuschlag"] = lim[1]
            l["bgForm"] = "gesamtschuldnerisch haftend"  # Standardform; Klausel-Detail folgt später

    # Payload-Split: die zwei schweren Felder (Beschreibung, Vergabestellen-Profil) wandern
    # in eine Detail-Datei und werden erst beim Öffnen eines Leads nachgeladen. So bleibt die
    # Listen-Ladung schlank genug, um viele Tausend Leads client-seitig zu filtern/sortieren.
    seg = segments()
    for l in leads:
        l["marktSegment"] = seg.get((l.get("cpv") or "")[:4])
    detail = {}
    for l in leads:
        # Beschreibung bleibt AM Lead (nicht ausgelagert): sie ist der eigentliche Inhalt und
        # muss durchsuchbar sein (leadText). Nur buyerProfile/marktSegment werden on-demand
        # nachgeladen. Sehr lange Beschreibungen (selten, bis 17k) für die Listen-Payload auf
        # 2.000 Zeichen deckeln — der Volltext liegt ohnehin in den Vergabeunterlagen.
        if l.get("beschreibung") and len(l["beschreibung"]) > 2000:
            l["beschreibung"] = l["beschreibung"][:2000] + " …"
        detail[l["id"]] = {"buyerProfile": l.pop("buyerProfile", None),
                           "marktSegment": l.pop("marktSegment", None)}
    (OUT / f"leads-{key}.json").write_text(json.dumps(leads, ensure_ascii=False))
    (OUT / f"detail-{key}.json").write_text(json.dumps(detail, ensure_ascii=False))
    return len(leads)


counts = con.execute(f"""
    SELECT {BRANCHE} AS k, count(*) n
    FROM {E} e LEFT JOIN {DC} b ON b.division = substr(e.cpv_code, 1, 2)
    WHERE (e.phase != 'expiring' OR e.months_to_expiry IS NULL OR e.months_to_expiry <= 18)
    GROUP BY 1""").fetchall()
counts = {k: n for k, n in counts}

exported = {}
markets = {}
for key in ["it", "bau", "medizin", "beratung", "sicherheit", "energie"]:
    exported[key] = export_branche(key)
    markets[key] = market_summary(key)
    print(f"  {key:11} {exported[key]:>5} / {counts.get(key, 0):>6} exportiert")

(OUT / "markt.json").write_text(json.dumps(markets, ensure_ascii=False))

(OUT / "branchen.json").write_text(json.dumps(counts, ensure_ascii=False))

# PLZ→Koordinate für die echte Umkreissuche: {plz: [lat, lon, ort]}. Aus dim_plz (GeoNames-
# Zentroide), kompakt gerundet. Das Frontend schlägt die getippte PLZ hier nach und filtert
# die Leads per Haversine gegen ihre lat/lon — kein Erste-Ziffer-Bundesland-Hack mehr.
# PLZ→Koordinate country-verschachtelt: {DE:{plz:[lat,lon,ort]}, CH:{…}, AT:{…}}. Nötig, weil
# AT und CH BEIDE 4-stellig sind und kollidieren (1010 = Wien AT / Lausanne CH) — die getippte
# Suche wählt anhand des aktiven Länderfilters. DE (5-stellig) bleibt eindeutig.
plz_rows = con.execute(
    f"SELECT country, plz, lat, lon, ort FROM {PLZ} WHERE lat IS NOT NULL").fetchall()
plz_geo = {}
for cc, p, la, lo, o in plz_rows:
    plz_geo.setdefault(cc, {})[p] = [round(float(la), 4), round(float(lo), 4), o or ""]
(OUT / "plz-geo.json").write_text(json.dumps(plz_geo, ensure_ascii=False, separators=(",", ":")))
print(f"PLZ→Koordinate: {sum(len(v) for v in plz_geo.values())} Einträge "
      f"({', '.join(f'{k}:{len(v)}' for k, v in plz_geo.items())}) → plz-geo.json")

print(f"\nGesamt-Bestand je Grundraum: {counts}")
print(f"Dateien in {OUT}/")
