"""Feature #24 — Zuschlagsphase: frische Zuschläge als Lead-Phase → web/data/awards-<branche>.json

Ein erteilter Zuschlag macht den Gewinner zum Einkäufer (Nachunternehmer, Fachplanung, Material).
Das Zeitfenster liegt in den Wochen nach dem Zuschlag. goVisor kennt den Auslöser punktgenau:
Gewinner, Volumen, CPV, Datum stehen in TED. KEIN eigener Bereich — eine Phase (src='award')
neben „Ausschreibung offen" und „Vertrag läuft aus", gleiche Liste, andere Handlung: anrufen
statt bieten.

Ehrlichkeits-Leitplanken (Ticket §8):
- „Unteraufträge geregelt" = das Feld liegt in den Unterlagen vor (~1/3 der Verfahren). Fehlt es,
  heißt das **„keine Angabe"**, NIE „keine Unteraufträge".
- Der Passungshinweis ist immer eine **Ableitung** aus der Zuschlagshistorie, kein Bedarf.

Aufruf: python3 scripts/export_web_awards.py
"""
import json
import pathlib

import sys

import duckdb

# ⚠ Projektpfad selbst setzen. Unter launchd gibt es kein PYTHONPATH, und ein Skript, das
# `govisor` importiert, ohne den Pfad zu setzen, bricht dort ab — still, im Tageslauf.
# Genau das hat `test_skripte_finden_govisor_ohne_pythonpath` hier gefangen.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from govisor.testvergaben import sql_bedingung as _testvergabe_sql  # noqa: E402

OUT = pathlib.Path("web/data"); OUT.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(); con.execute("SET threads=4")
G = "data/gold/DE"


def _union(tabelle: str) -> str:
    """Gold-Tabelle ueber ALLE Laender, DE zuerst (Basis-Schema).

    ⚠ Bis 2026-08-23 las dieses Skript nur `data/gold/DE`, und es stand ausserdem in
    KEINEM Lauf. Die Zuschlagsphase im Frontend trug deshalb 379 Leads, alle deutsch —
    die Frage, wer bei einer oesterreichischen oder schweizerischen Stelle zuletzt
    gewonnen hat, blieb ohne Antwort.
    """
    weitere = sorted(str(x) for x in pathlib.Path("data/gold").glob(f"*/{tabelle}.parquet")
                     if x.parent.name != "DE")
    lst = ", ".join(f"'{d}'" for d in [f"{G}/{tabelle}.parquet"] + weitere)
    return f"read_parquet([{lst}], union_by_name=true)"


def _silber_union(tabelle: str) -> str:
    """Silber ueber alle Laender, die die Tabelle fuehren (Glob ins Leere = Laufzeitfehler)."""
    muster = [f"data/silver/{x.parent.name}/{tabelle}/*/*.parquet"
              for x in sorted(pathlib.Path("data/silver").glob(f"*/{tabelle}"))
              if list(x.glob("*/*.parquet"))]
    lst = ", ".join(f"'{m}'" for m in muster)
    return f"read_parquet([{lst}], hive_partitioning=1, union_by_name=true)"


N = _silber_union("notices")
A = _silber_union("attributes")
PE = _union("party_entity")
EI = _union("entity_identity")
EN = _union("entities")
CL = f"read_parquet('{G}/dim_cpv_label.parquet')"   # EU-Vokabular, eine Kopie genuegt
DC = f"read_parquet('{G}/dim_cpv.parquet')"         # dito
LD = _union("lead_duration")

# Standardausschnitt (Ticket §3.3): letzte 30 Tage + ab 500.000 €. Das ist der ehrliche „frische"
# Zuschlag-Stream (unter 500k selten Weitervergabe, nach 30 Tagen ist das Kontakt-Fenster meist zu).
WINDOW_DAYS = 30
VALUE_FLOOR = 500_000
# ⚠ JE BRANCHE **UND LAND**. Bis 2026-08-23 galt der Deckel je Branche allein — das war
# richtig, solange nur Deutschland drin war. Mit AT und CH haetten sich die drei Laender
# denselben Deckel geteilt: ein deutscher Nutzer saehe statt 503 nur noch 196 deutsche
# Zuschlaege, weil oesterreichische und schweizerische ihm die Plaetze wegnehmen. Der
# Deckel soll die Liste kurz halten, nicht Laender gegeneinander ausspielen.
CAP = 120                   # je Branche UND Land

# Branche-Mapping identisch zu export_web_leads.py (dim_cpv.branche → ui_branche)
BRANCHE = """CASE b.branche
  WHEN 'IT' THEN 'it' WHEN 'Elektro' THEN 'it' WHEN 'Messtechnik' THEN 'it'
  WHEN 'Bau' THEN 'bau' WHEN 'Installation' THEN 'bau' WHEN 'Immobilien' THEN 'bau'
    WHEN 'Ingenieur/Architektur' THEN 'bau' WHEN 'Wartung' THEN 'bau'
  WHEN 'Medizin' THEN 'medizin' WHEN 'Gesundheit' THEN 'medizin'
  WHEN 'Sicherheit' THEN 'sicherheit'
  WHEN 'Energie' THEN 'energie' WHEN 'Versorgung' THEN 'energie' WHEN 'Wasser' THEN 'energie'
    WHEN 'Umwelt/Reinigung' THEN 'energie' WHEN 'Chemie' THEN 'energie' WHEN 'Rohstoffe' THEN 'energie'
  ELSE 'beratung' END"""

# ⚠ Regionsnamen aus `dim_nuts` JE LAND statt getippter DE-Liste — dieselbe Falle wie in
# `export_firma_profiles.py`, und beim kritischen Durchgang am 2026-08-23 hier zunaechst
# uebersehen. Gemessen vor der Korrektur: ALLE 306 schweizerischen und 333
# oesterreichischen Zuschlaege zeigten gar keine Region, weil die Liste nur DE-Codes kannte
# UND der Schnitt auf 3 Zeichen die falsche Ebene traf (AT1 = „Ostoesterreich", CH0 = die
# ganze Schweiz). Siehe `docs/laender/07-geo-und-regionen.md`.
def _regionsnamen() -> dict[str, str]:
    aus: dict[str, str] = {}
    for datei in sorted(pathlib.Path("data/gold").glob("*/dim_nuts.parquet")):
        try:
            for code, name in con.execute(
                    f"SELECT nuts_code, name FROM '{datei.as_posix()}'").fetchall():
                if code and name:
                    aus[code] = name
        except Exception:
            continue
    return aus


NUTS1 = _regionsnamen()

# Auf wie vielen Stellen sitzt die Verwaltungseinheit? DE 3, AT 4, CH 5 — muss zu
# `govisor.gold._REGION_STELLEN` passen.
_NUTS_SCHNITT = ("substr(n.performance_nuts, 1, CASE substr(n.performance_nuts, 1, 2) "
                 "WHEN 'AT' THEN 4 WHEN 'CH' THEN 5 ELSE 3 END)")


def eur(v):
    if v is None:
        return None
    v = float(v)
    if v >= 1e9: return f"{v/1e9:.1f}".replace(".", ",") + " Mrd €"
    if v >= 1e6: return f"{v/1e6:.1f}".replace(".", ",") + " Mio €"
    return f"{int(round(v)):,}".replace(",", ".") + " €"


NOW = con.execute(f"SELECT max(award_date) FROM {N} WHERE notice_kind='can' AND award_date <= current_date").fetchone()[0]

# ---- Award-Grundmenge: frische Zuschläge mit Gewinner-Identität, Wert, CPV, Region ----
con.execute(f"""CREATE TEMP TABLE aw AS
  WITH win AS (   -- genau eine Gewinner-Identität je Zuschlag; Konsortien (≥2) markiert
    SELECT p.notice_id, min(ei.identity_id) AS wid, count(DISTINCT ei.identity_id) AS n_win
    FROM {PE} p JOIN {EI} ei ON ei.entity_id = p.entity_id
    WHERE p.role='winner' GROUP BY 1)
  SELECT n.notice_id, n.country, n.title, n.cpv_main, substr(n.cpv_main,1,4) AS cpv4,
         {_NUTS_SCHNITT} AS nuts1,
         n.award_date, coalesce(n.final_value, n.estimated_value) AS wert,
         (n.final_value IS NOT NULL AND n.value_currency='EUR') AS wert_echt,
         date_diff('day', n.award_date, DATE '{NOW}') AS ago,
         nd.contract_end,
         win.wid, win.n_win,
         {BRANCHE} AS ui_branche,
         cl.label AS cpv_label,
         EXISTS(SELECT 1 FROM {A} a WHERE a.notice_id=n.notice_id AND a.path ILIKE '%ubcontract%') AS sub_flag
  FROM {N} n
  JOIN win ON win.notice_id = n.notice_id
  LEFT JOIN {DC} b ON b.division = substr(n.cpv_main,1,2)
  LEFT JOIN {CL} cl ON cl.cpv_code = n.cpv_main
  LEFT JOIN {LD} nd ON nd.notice_id = n.notice_id
  WHERE n.notice_kind='can' AND n.award_date >= (DATE '{NOW}' - INTERVAL {WINDOW_DAYS} DAY)
    -- Übungsvorgänge raus, gleiche Regel wie im Lead-Export (govisor/testvergaben.py).
    -- Ein Zuschlag auf eine Testausschreibung ist genauso wenig ein Zuschlag.
    AND NOT {_testvergabe_sql('n.title')}
    AND n.award_date <= DATE '{NOW}'
    AND coalesce(n.final_value, n.estimated_value) >= {VALUE_FLOOR}
    AND win.wid IS NOT NULL""")

# ---- Gewinner-Statistik je Identität (für Passungshinweis + Gewinner-Karte) ----
con.execute(f"""CREATE TEMP TABLE winners AS
  WITH wl AS (   -- volle Gewinn-Historie der Award-Gewinner
    SELECT DISTINCT ei.identity_id AS wid, p.notice_id,
           substr(n.cpv_main,1,4) AS cpv4,
           {_NUTS_SCHNITT} AS nuts1,
           CASE WHEN n.value_currency='EUR' THEN n.final_value END AS val,
           n.award_date,
           EXISTS(SELECT 1 FROM {A} a WHERE a.notice_id=n.notice_id AND a.path ILIKE '%ubcontract%') AS sub
    FROM {PE} p JOIN {EI} ei ON ei.entity_id=p.entity_id
    JOIN {N} n ON n.notice_id=p.notice_id
    WHERE p.role='winner' AND ei.identity_id IN (SELECT DISTINCT wid FROM aw))
  SELECT wid,
         count(*) AS wins_total,
         count(*) FILTER (WHERE award_date >= (DATE '{NOW}' - INTERVAL 36 MONTH)) AS wins36,
         avg(val) AS avg_val,
         count(*) FILTER (WHERE sub) AS sub_wins
  FROM wl GROUP BY 1""")

# Name je Gewinner + Zuordnungs-Konfidenz
con.execute(f"""CREATE TEMP TABLE wname AS
  SELECT ei.identity_id AS wid,
         arg_max(e.canonical_name, e.confidence) AS name,
         max(CASE WHEN e.method IN ('handelsregister_exakt','ted_nationalid') THEN 1 ELSE 0 END) AS belegt
  FROM {EI} ei JOIN {EN} e ON e.entity_id=ei.entity_id
  WHERE ei.identity_id IN (SELECT DISTINCT wid FROM aw) GROUP BY 1""")

# Top-Leistungsfelder je Gewinner (für die Gewinner-Karte) + Anteil je cpv4 (für overlap)
con.execute(f"""CREATE TEMP TABLE wfields AS
  WITH c AS (
    SELECT ei.identity_id AS wid, substr(n.cpv_main,1,4) AS cpv4, count(*) n
    FROM {PE} p JOIN {EI} ei ON ei.entity_id=p.entity_id JOIN {N} n ON n.notice_id=p.notice_id
    WHERE p.role='winner' AND ei.identity_id IN (SELECT DISTINCT wid FROM aw)
      AND n.cpv_main IS NOT NULL GROUP BY 1,2),
  tot AS (SELECT wid, sum(n) t FROM c GROUP BY 1),
  rk AS (SELECT c.wid, c.cpv4, c.n, c.n::DOUBLE/tot.t AS share,
                row_number() OVER (PARTITION BY c.wid ORDER BY c.n DESC) rn
         FROM c JOIN tot ON tot.wid=c.wid)
  SELECT r.wid,
         list({{'cpv4': r.cpv4, 'label': cl.label, 'share': round(r.share,3)}} ORDER BY r.n DESC) FILTER (WHERE r.rn<=3) AS fields
  FROM rk r LEFT JOIN {CL} cl ON cl.cpv_code = r.cpv4 || '0000'
  GROUP BY 1""")

# Anteil des Gewinners im CPV4 DIESES Zuschlags (steuert overlap)
con.execute(f"""CREATE TEMP TABLE self_share AS
  WITH c AS (
    SELECT ei.identity_id AS wid, substr(n.cpv_main,1,4) AS cpv4, count(*) n
    FROM {PE} p JOIN {EI} ei ON ei.entity_id=p.entity_id JOIN {N} n ON n.notice_id=p.notice_id
    WHERE p.role='winner' AND ei.identity_id IN (SELECT DISTINCT wid FROM aw) GROUP BY 1,2),
  tot AS (SELECT wid, sum(n) t FROM c GROUP BY 1)
  SELECT c.wid, c.cpv4, c.n::DOUBLE/tot.t AS share
  FROM c JOIN tot ON tot.wid=c.wid""")

# Vergabestelle je Zuschlag (Name aus party_entity buyer → entities)
con.execute(f"""CREATE TEMP TABLE abuyer AS
  SELECT a.notice_id, arg_max(e.canonical_name, e.confidence) AS buyer
  FROM aw a JOIN {PE} p ON p.notice_id=a.notice_id AND p.role='buyer'
  JOIN {EN} e ON e.entity_id=p.entity_id GROUP BY 1""")

rows = con.execute(f"""
  SELECT a.*, w.wins_total, w.wins36, w.avg_val, w.sub_wins,
         wn.name AS winner_name, wn.belegt AS winner_belegt,
         wf.fields AS winner_fields, ss.share AS self_share, ab.buyer
  FROM aw a
  LEFT JOIN winners w ON w.wid=a.wid
  LEFT JOIN wname wn ON wn.wid=a.wid
  LEFT JOIN wfields wf ON wf.wid=a.wid
  LEFT JOIN self_share ss ON ss.wid=a.wid AND ss.cpv4=a.cpv4
  LEFT JOIN abuyer ab ON ab.notice_id=a.notice_id
  ORDER BY a.award_date DESC""").df().to_dict("records")


def overlap_of(share):
    """CPV-Überschneidung Gewinner↔Auftrag: wie stark der Gewinner das Auftragsfeld selbst bedient."""
    if share is None:
        return "mittel"
    if share >= 0.5:
        return "hoch"          # spezialisiert → direkter Wettbewerb
    if share >= 0.2:
        return "mittel"
    return "gering"            # gewinnt es, macht es aber selten selbst → vergibt eher weiter


def empfehlung_of(sub_flag, overlap):
    """§3.2: Ansprechen / Prüfen / (kein Eintrag bei hoher Feldüberschneidung)."""
    if overlap == "hoch":
        return ""             # direkter Wettbewerb → keine Empfehlung
    if sub_flag and overlap == "gering":
        return "ansprechen"
    return "pruefen"


def g(r, k):
    v = r.get(k)
    if v is None:
        return None
    if isinstance(v, float) and v != v:
        return None
    return v


by_branche = {}
_je_land: dict[tuple[str, str], int] = {}
for r in rows:
    br = g(r, "ui_branche") or "beratung"
    land = g(r, "country") or "DE"
    if br not in by_branche:
        by_branche[br] = []
    schluessel = (br, land)
    if _je_land.get(schluessel, 0) >= CAP:
        continue
    _je_land[schluessel] = _je_land.get(schluessel, 0) + 1
    share = g(r, "self_share")
    overlap = overlap_of(share)
    sub = bool(g(r, "sub_flag"))
    empf = empfehlung_of(sub, overlap)
    wins_total = int(g(r, "wins_total") or 0)
    sub_wins = int(g(r, "sub_wins") or 0)
    ce = g(r, "contract_end")
    try:
        laufzeit = ce.strftime("%m/%Y") if (ce is not None and hasattr(ce, "strftime")) else None
    except Exception:            # pandas NaT
        laufzeit = None
    wf = r.get("winner_fields")
    wf = [] if wf is None or isinstance(wf, float) else list(wf)   # numpy-Array → Liste
    fields = [dict(f) for f in wf]
    for f in fields:
        f["pct"] = round(float(f.get("share") or 0) * 100)
        f["label"] = f.get("label") or f.get("cpv4")
    by_branche[br].append({
        "id": g(r, "notice_id"), "branche": br, "src": "award",
        "titel": g(r, "title") or "(ohne Titel)",
        "buyer": g(r, "buyer") or "", "buyerShort": g(r, "buyer") or "",
        "cpv": g(r, "cpv_main"), "cpvLabel": g(r, "cpv_label") or "",
        # ⚠ Stand hier bis 2026-08-23 FEST auf "DE" — selbst nachdem die Quellen alle
        # Laender lasen, waere jeder oesterreichische Zuschlag als deutscher ausgegeben
        # worden. Ein hartkodierter Wert ist die leiseste Sorte Fehler: er sieht wie
        # ein Feld aus.
        "land": g(r, "country") or "DE",
        "region": NUTS1.get(g(r, "nuts1"), ""), "nuts": g(r, "nuts1") or "",
        "volumen": {"wert": eur(g(r, "wert")) or "Wert offen",
                    "src": "echt" if g(r, "wert_echt") else "schaetz"},
        # Award-spezifisch
        "award": {
            "date": str(g(r, "award_date")) if g(r, "award_date") else None,
            "ago": int(g(r, "ago")) if g(r, "ago") is not None else None,
            "winner": g(r, "winner_name") or "unbekannt",
            "winnerId": g(r, "wid"),
            "winnerBelegt": bool(g(r, "winner_belegt")),
            "konsortium": int(g(r, "n_win") or 1) >= 2,
            "laufzeit": laufzeit,
            "subcontracting": "geregelt" if sub else "keine_angabe",
            "overlap": overlap,
            "empfehlung": empf,
            "winnerStats": {
                "wins36": int(g(r, "wins36") or 0),
                "avgValue": eur(g(r, "avg_val")),
                "subQuote": f"{sub_wins} von {wins_total}" if wins_total else None,
                "wins_total": wins_total,
            },
            "winnerFields": fields,
        },
    })

total = 0
counts = {}
for br, awards in by_branche.items():
    (OUT / f"awards-{br}.json").write_text(json.dumps(awards, ensure_ascii=False))
    counts[br] = len(awards)
    total += len(awards)

print(f"Stichtag {NOW} · {total} Zuschläge über {len(by_branche)} Branchen → web/data/awards-*.json")
for br in sorted(counts, key=lambda b: -counts[b]):
    print(f"  {br:12s} {counts[br]}")
