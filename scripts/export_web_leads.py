"""Exportiert echte Gold-Leads in die UI-Lead-Form des Web-Explorers (JSON).

Mappt `lead_export` (+ `lead_lot`, `dim_cpv_label`, `dim_cpv`) auf die Objektform,
die die Prototyp-Renderer erwarten. Felder, die es in Gold nicht gibt (Kommentare,
Team-Log, Begriffs-Extraktion, Angebotsaufwand-Details), bleiben leer/na — das
Datenblatt-Prinzip (Übergabenotiz §3) zeigt Fehlendes ehrlich an, statt es zu erfinden.

Schreibt `web/data/leads-<branche>.json` (je Grundraum gekappt) + `web/data/branchen.json`.
Lokal-first: kein Supabase nötig. Später durch eine Live-Query ersetzbar.
"""
import json, pathlib, sys
from datetime import date

# Der Runner ruft dieses Skript als `python3 scripts/export_web_leads.py` — dabei liegt die
# Repo-Wurzel NICHT im Suchpfad, nur `scripts/`. Solange die Datei nichts aus `govisor`
# importierte, fiel das nicht auf; seit dem `db`-Import (2026-08-14) bricht sie ohne diese
# Zeile mit `ModuleNotFoundError` ab — und zwar erst im Tageslauf, nicht beim Testen.
# Gleiche Loesung wie in `scripts/export_supabase.py`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from govisor import db as _db  # noqa: E402
from govisor.testvergaben import sql_bedingung as _testvergabe_sql

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

CAP_MONAT = 120     # Auslauf-Leads je Grundraum UND Auslauf-Monat (24 Monate → ~2.900).
# ⚠ CAP gilt seit 2026-08-18 NUR NOCH fuer nicht-offene Phasen, und dort greift ohnehin
# CAP_MONAT. Die Konstante bleibt stehen, weil sie an anderer Stelle gelesen wird — wer sie
# wieder auf offene Ausschreibungen anwendet, schneidet sie erneut bei sechs Tagen Frist ab.
CAP = 2500          # Leads je Grundraum UND Phase (Quote statt gemeinsamer Rangliste).
                    # 3 Phasen × 2.500 ≈ derselbe Umfang wie vorher 6.000 gesamt,
                    # aber jede Phase kommt vor. Client-seitiges Filtern deckelt
                    # bei ein paar Tausend; der volle Bestand (Bau 48k) braucht die Server-Query.
OUT = pathlib.Path("web/data"); OUT.mkdir(parents=True, exist_ok=True)


def _volltext_index() -> set:
    """Welche Leads haben bei UNS den Volltext der Vergabeunterlagen?

    ⚠ **Das ist eine andere Frage als `has_documents`, und die Verwechslung stand im
    Produkt falsch herum.** `has_documents` sagt „die QUELLE bewirbt Unterlagen"; es wird
    fuer die Schweiz aus der simap-Projektbruecke gefuellt und fuer Deutschland von
    niemandem. Gemessen am 2026-08-25 ueber 18.594 Leads mit laufender Frist:

        DE   5.899 Leads haben bei uns den VOLLTEXT — und keiner sagte es dem Nutzer
             (2.573 + 9.614 zeigten „unknown" bzw. gar keinen Unterlagen-Block)
        CH     166 zeigten „offen", obwohl NICHTS abgerufen wurde

    Der Nutzer konnte also nicht erkennen, ob wir die Unterlagen gelesen haben — genau die
    Auskunft, fuer die er das Produkt benutzt. `docs/laender/03-input-dokumente.md` verlangt
    dafuer ausdruecklich ein `gelesen`-Feld.

    Der Index entsteht in `scripts/export_doc_text.py` und laeuft im Tageslauf VOR diesem
    Skript (Zeile 1009 gegen 1094). Fehlt er, wird nichts behauptet: leere Menge.
    """
    p = OUT / "doc-text-index.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        print("  ⚠ doc-text-index.json fehlt — `gelesen` bleibt bei allen Leads False.")
        return set()
    return set(d)


VOLLTEXT = _volltext_index()


def _unterlagen(g, volltext: set) -> dict | None:
    """Der Unterlagen-Block eines Leads. ``None``, wenn es nichts zu sagen gibt.

    Zwei Fragen, die vorher zu einer verschmolzen waren:

    * **`access`** — was die QUELLE anbietet (offen, kostenpflichtig, auf Anfrage,
      unbekannt). Kommt aus `has_documents`/`documents_paid`/`documents_source`.
    * **`gelesen`** — ob WIR den Volltext haben. Das ist die Auskunft, für die der Nutzer
      das Produkt benutzt, und sie fehlte vollständig.

    ⚠ Der Block entsteht auch **ohne Link**, wenn wir den Text haben. Sonst fällt genau
    die Auskunft weg, die zählt: gemessen am 2026-08-25 hatten 5.155 offene deutsche Leads
    Volltext bei uns und **gar keinen** Unterlagen-Block, weil weder `documents_url` noch
    `source_url` gesetzt war.
    """
    gelesen = g("lead_id") in volltext
    wie = g("documents_source") or None
    if g("documents_url"):
        return {"url": g("documents_url"), "source": "docs",
                "access": ("offen" if g("has_documents") and not g("documents_paid")
                           else "kostenpflichtig" if g("documents_paid")
                           else "auf_anfrage" if wie == "on_request"
                           else "unknown"),
                "wie": wie, "gelesen": gelesen}
    if g("source_url"):
        return {"url": g("source_url"), "source": "portal",
                "access": "auf_anfrage" if wie == "on_request" else "unknown",
                "wie": wie, "gelesen": gelesen}
    if gelesen:
        return {"url": None, "source": None, "access": "unknown", "wie": wie,
                "gelesen": True}
    return None
con = _db.connect()
G = "data/gold/DE"


def _union(table, key=None, mit_land=False):
    """DE-Gold + jede weitere ``gold/<CC>/<table>.parquet`` (CH, AT, künftige) per union_by_name —
    jede Quelle füllt nur ihre Spalten, fehlende werden NULL (DACH-Mehrquellen ohne Schema-Zwang).
    Unterschieden über die country-Spalte (→ land). DE zuerst (Basis-Schema).

    Mit ``key`` wird je Schlüssel genau EINE Zeile behalten, DE gewinnt. Grund: gemessen liegen
    drei Leads in AT **und** DE (EU-Einrichtungen mit Sitz in Frankfurt, die beide Länderfilter
    passieren). Ohne Entscheidung vervielfacht der nachgelagerte Join sie, und welche Zeile
    gewinnt, entschied der Zufall — ein Lead trug bei einem Lauf Koordinaten und beim nächsten
    keine. Die drei sind ein eigener Datenbefund; hier wird nur der Export eindeutig gemacht.
    """
    others = sorted(str(p) for p in pathlib.Path("data/gold").glob(f"*/{table}.parquet")
                    if p.parent.name != "DE")
    files = [f"{G}/{table}.parquet"] + others
    lst = ", ".join(f"'{f}'" for f in files)
    roh = f"read_parquet([{lst}], union_by_name=true, filename=true)"
    if mit_land:
        # Fuer Tabellen OHNE `country`-Spalte. `market_opportunity` ist nach `cpv4`
        # verschluesselt, `cpv_adjacency` nach Codepaar — beide sagen nichts darueber,
        # aus welchem Markt die Zahl stammt. Ohne diese Ableitung wuerde ein Verbraucher,
        # der nach dem Fachschluessel greift, still den letzten Treffer bekommen.
        return (f"(SELECT * EXCLUDE(filename), "
                f"regexp_extract(filename, 'gold/([A-Z]{{2}})/', 1) AS land FROM {roh})")
    if not key:
        return roh
    return (f"(SELECT * EXCLUDE(filename) FROM {roh} "
            f"QUALIFY row_number() OVER (PARTITION BY {key} "
            f"ORDER BY (filename LIKE '%/DE/%') DESC, filename) = 1)")


def _silber_union(tabelle: str) -> str:
    """Silber-Tabelle ueber alle Laender, die sie fuehren.

    Getrennt von `_union`: Gold hat EINE Datei je Land, Silber einen Baum aus
    Jahrespartitionen. Laender ohne die Tabelle fallen raus statt durch — ein Glob
    ins Leere ist in DuckDB ein Laufzeitfehler, kein leeres Ergebnis.
    """
    muster = [f"data/silver/{p.parent.name}/{tabelle}/*/*.parquet"
              for p in sorted(pathlib.Path("data/silver").glob(f"*/{tabelle}"))
              if list(p.glob("*/*.parquet"))]
    if not muster:
        return ("(SELECT NULL::VARCHAR AS notice_id, NULL::VARCHAR AS path, "
                "NULL::VARCHAR AS value WHERE false)")
    lst = ", ".join(f"'{m}'" for m in muster)
    return f"read_parquet([{lst}], hive_partitioning=1, union_by_name=true)"


E = _union("lead_export", key="lead_id")

# ── ABGELEITETE BUNDESLÄNDER ─────────────────────────────────────────────────────────────
# `scripts/region_ableiten.py` schliesst die grösste sichtbare Lücke des Bestands: bei den
# OFFENEN Leads fehlte das Bundesland zu 40 % (6.460 von 16.096), weil die unterschwelligen
# Quellen keine NUTS-Kennung liefern. Wer im Explorer nach Bundesland filtert, verlor damit
# vier von zehn aktuellen Ausschreibungen.
#
# Die Ableitung steht in einer EIGENEN Datei, nicht in `lead_export`: sie ist eine Aussage
# über die Daten, keine Quelle. Fehlt die Datei, verhält sich der Export wie vorher.
# ⚠ Ueber ALLE Laender, und der Waechter fragt nach IRGENDEINEM. Bis 2026-08-23 stand hier
# der reine DE-Pfad: `region_ableiten.py` lief nur fuer Deutschland, und selbst nachdem es
# oesterreichische Ableitungen gab, haette der Export sie nicht gelesen. Zwei Schichten
# derselben Annahme, und die zweite haette die Reparatur der ersten lautlos verschluckt.
_FILL_DA = any(pathlib.Path("data/gold").glob("*/lead_region_fill.parquet"))
REGION_FILL = (_union("lead_region_fill", key="lead_id") if _FILL_DA else
               "(SELECT NULL::VARCHAR AS lead_id, NULL::VARCHAR AS buyer_nuts1_abgeleitet, "
               "NULL::VARCHAR AS quelle, NULL::BOOLEAN AS widerspruch, "
               "NULL::VARCHAR AS widerspruch_ort_nuts1 WHERE false)")
CL = f"read_parquet('{G}/dim_cpv_label.parquet')"
DC = f"read_parquet('{G}/dim_cpv.parquet')"
# ⚠ ÜBER ALLE LÄNDER, nicht nur DE. Bis zum 2026-08-22 stand hier `{G}/lead_lot.parquet`
# — also ausschliesslich `data/gold/DE`. Die österreichischen und Schweizer Lose existierten
# längst (AT 10.871 über 6.891 Vergaben, CH 7.660 über 7.346), erreichten das Frontend aber
# nie: „Lose" stand für DE bei 79 %, für AT und CH bei 0 %. Ein `{G}` mitten in einer sonst
# länderübergreifenden Datei ist genau die Sorte Rest, die der EU-weit-Grundsatz meint.
LOTS = _union("lead_lot")
# ⚠ Ueber ALLE Laender: die abgeleitete Region wird hier in Klartext aufgeloest, und die
# oesterreichischen bzw. schweizerischen Namen stehen nur in deren eigenem `dim_nuts`
# (DE 462 Eintraege, AT 48, CH 35 — ohne Ueberschneidung).
DN = _union("dim_nuts")                        # NUTS-Code → Klartextname
# Sprachfassungen je Lead. Ohne sie kann die Oberflaeche keine Dokumentsprache
# anbieten, obwohl die Texte im Silber liegen. Guard: fehlt die Tabelle (Gold aelter
# als der Builder), bleibt es beim einsprachigen Verhalten statt eines Laufzeitfehlers.
_LT = [str(x) for x in pathlib.Path("data/gold").glob("*/lead_text.parquet")]
LT = (f"read_parquet([{', '.join(repr(x) for x in sorted(_LT))}], union_by_name=true)"
      if _LT else None)
# ⚠ Ueber ALLE Laender. Bis 2026-08-23 stand hier der reine DE-Pfad — kein einziger
# oesterreichischer oder schweizerischer Kaeufer bekam ein Profil, und der Renderer zeigte
# stattdessen „zu wenig Daten": eine Aussage ueber die Vergabestelle, wo in Wahrheit nur
# die Datei fehlte. Jetzt AT 4.341 + CH 5.656 Kaeufer zusaetzlich.
#
# Bekannte Grenze, gemessen: der Profil-Nachschlag geht ueber den NAMEN, nicht ueber die
# Kennung. 22 Kaeufernamen kommen in mehr als einem Land vor („Gemeinde Bergheim" gibt es
# in DE und AT, „Stadtbauamt" und „Einkauf" sind ohnehin keine Namen) und treffen 463 von
# 117.241 Leads. Dort gewinnt DE. Das ist der bessere Zustand als vorher — vorher bekamen
# ALLE 27.000 AT/CH-Kaeufer gar nichts — aber es ist keine saubere Aufloesung; die braeuchte
# einen Schluessel aus (Name, Land) durch die ganze Profilkette.
BS = _union("buyer_stats")
# Die letzten Vergaben je Kaeufer. Seit Langem gebaut (38.320 Zeilen), von niemandem
# gelesen — der Vergabestellen-Block zeigte nur Aggregate. „Wer hat dort zuletzt
# was gewonnen" ist die Frage, die ein Bieter wirklich stellt.
BRA = _union("buyer_recent_awards")
# Profil der UNTERSCHWELLIGEN Vergabestellen (DÖE). `buyer_stats` kennt nur, was ueber
# TED lief — gemessen am 2026-08-18 haben 425 Kaeufer mit OFFENEN Ausschreibungen
# deshalb gar kein Profil, obwohl hier eines liegt. Sie sahen „zu wenig Daten".
DBP = f"read_parquet('{G}/doe_buyer_profile.parquet')"
# ⚠ Ueber ALLE Laender. Bis 2026-08-23 stand hier fest `data/silver/DE` — mitten in einem
# Export, der seine Gold-Tabellen laengst per `_union` liest. Folge: der Angebotsaufwand
# (Bietungsbuergschaft, Bindefrist) lag fuer DE bei 30 % und fuer AT und CH bei GENAU 0 %,
# obwohl 272 oesterreichische und 124 schweizerische Attribut-Dateien danebenliegen. Wie
# immer bei dieser Fehlerklasse fiel es nicht auf, weil ein leeres Feld aussieht wie eine
# Quelle, die nichts hergibt.
#
# Kein `_union`, weil das die GOLD-Ebene meint (eine Datei je Land); hier ist es ein
# Silber-Glob ueber Jahrespartitionen.
ATTR = _silber_union("attributes")
# ⚠ Ueber ALLE Laender, und der Schluessel traegt das Land mit. `market_opportunity` ist
# nach `cpv4` verschluesselt, nicht nach Land — ein reines union_by_name wuerde die
# deutschen Marktzahlen still durch die schweizerischen ersetzen, weil im Woerterbuch
# der letzte Treffer gewinnt. Bis 2026-08-23 wurde ausschliesslich DE gelesen: ein
# oesterreichischer Bieter sah im Markt-Tab deutsche Segmentzahlen, ausgegeben als seine.
MO = _union("market_opportunity", mit_land=True)
CS = _union("contractor_stats")
# ⚠ Ebenfalls über alle Länder: AT trägt 70.031 Identitäten, CH 33.443. Nur DE zu lesen
# heisst, dass ein österreichischer Amtsinhaber keinen Namen bekommt — dieselbe Sorte
# DE-Rest wie bei `lead_lot`.
EI = _union("entity_identity")
# HINWEIS-FELDER (s. web/lib/hinweise.ts). Zwei Dinge, die das Frontend braucht und die
# nirgends sonst zusammenkommen:
#
#   PORTALE   auf wie vielen Plattformen dieselbe Vergabe steht. Aus der Dubletten-Firewall,
#             nur die staerkste Belegstufe — schwaechere Stufen sind bei generischen Titeln
#             Rauschen (18.089 `ojs ← text`-Paare in DE sind gleichnamige CPV-Bezeichnungen,
#             keine Dubletten).
#   FRIST_PUB die VEROEFFENTLICHTE Frist aus Silber. Ohne sie kann der Hinweis „Frist
#             verlaengert" nicht sagen, WELCHES Datum vorher galt — und genau das ist bei
#             diesem Hinweis die eigentliche Information, nicht das Label.
# schema_gen → PORTAL. Die Probe zeigte `['eforms','legacy']` als „zwei Portale" — das ist
# aber dasselbe TED-Archiv in zwei Formatgenerationen, kein zweiter Anbieter. Ohne diese
# Abbildung feuerte der Hinweis „Auf mehreren Portalen" bei 81.043 Leads falsch.
_PORTAL_NAME = {
    "eforms": "TED", "legacy": "TED", "ojs": "TED", "text": "TED",
    "doe": "Deutsches Ausschreibungsblatt", "dtvp": "DTVP",
    "netserver": "Landesportal", "simap": "simap.ch", "atverg": "OffeneVergaben.at",
}


def _portal_case(spalte: str) -> str:
    faelle = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in _PORTAL_NAME.items())
    return f"CASE {spalte} {faelle} ELSE {spalte} END"


def _quellen_je_lead() -> str:
    dups = []
    for land in ("DE", "AT", "CH"):
        d = pathlib.Path(f"data/gold/{land}/notice_duplicates.parquet")
        if d.exists():
            dups.append(d.as_posix())
    if not dups:
        return "(SELECT NULL::VARCHAR notice_id, NULL::VARCHAR[] portale WHERE false)"
    return f"""(
      SELECT ziel AS notice_id, list_sort(list_distinct(list(q))) AS portale FROM (
        SELECT master_id AS ziel, {_portal_case('master_quelle')} AS q
          FROM read_parquet({dups!r}) WHERE beleg='kaeufer_und_titel'
        UNION ALL
        SELECT master_id, {_portal_case('duplicate_quelle')}
          FROM read_parquet({dups!r}) WHERE beleg='kaeufer_und_titel')
      GROUP BY ziel HAVING count(DISTINCT q) > 1)"""


def _frist_veroeffentlicht() -> str:
    import glob as _g
    g = []
    for land in ("DE", "AT", "CH"):
        g += _g.glob(f"data/silver/{land}/notices/**/*.parquet", recursive=True)
    if not g:
        return "(SELECT NULL::VARCHAR notice_id, NULL::DATE frist_pub WHERE false)"
    return (f"(SELECT notice_id, CAST(submission_deadline AS DATE) AS frist_pub "
            f"FROM read_parquet({g!r}) WHERE submission_deadline IS NOT NULL)")


PORTALE = _quellen_je_lead()
FRISTPUB = _frist_veroeffentlicht()
DL = _union("lead_deadline", key="notice_id")                        # Angebotsfrist-Herkunft (#16), DE+CH
LG = _union("lead_geo", key="lead_id")                              # Koordinate je Lead (echter km-Radius), DE+CH
PLZ = f"read_parquet('{G}/dim_plz.parquet')"        # PLZ→Zentroid für die PLZ-Umkreissuche
# Vorgänger-Link: offene Leads (ohne eigenen Zuschlag) erben Incumbent/Bieterzahl/Kette vom
# jüngsten passenden Vorgänger-Zuschlag. Guard: fehlt die Tabelle, leerer Stub (kein Join-Fehler).
# Seit 2026-08-23 gibt es die Tabelle auch fuer AT (531) und CH (572) — deshalb ueber
# `_union` und mit `key`, weil der Join gegen `lead_id` genau EINE Zeile erwartet.
# Der Waechter fragt nach IRGENDEINEM Land, nicht nach DE: faellt der deutsche Bau aus,
# waeren sonst auch die vorhandenen AT/CH-Vorgaenger abgeschaltet.
_LP_DA = any(pathlib.Path("data/gold").glob("*/lead_predecessor.parquet"))
LP = (_union("lead_predecessor", key="lead_id") if _LP_DA else
      "(SELECT NULL::VARCHAR lead_id, NULL::VARCHAR incumbent_name, NULL::BIGINT n_bidders, "
      "NULL::VARCHAR competition_level, NULL::BIGINT chain_depth, NULL::BIGINT incumbent_since_year "
      "WHERE false)")
# Abgeleitete Kategorie (Kategorie-Wasserfall, für Quellen ohne CPV). Eigener Join und nicht
# über `lead_export`, weil dessen Vertrag durchgehend ENGLISCH ist — Spalten UND Werte, in
# `tests/test_plumbing.py::_EXPORT_VOCAB` festgenagelt. Die Branchen-Labels sind deutsch
# („Bau", „Umwelt/Reinigung"); sie dort hineinzuschreiben hiesse, den Vertrag für eine
# Bequemlichkeit aufzugeben. `lead_export` trägt deshalb nur die HERKUNFT
# (`category_source`), der Wert kommt von hier.
_KAT_PATH = f"{G}/lead_kategorie.parquet"
KAT = (f"read_parquet('{_KAT_PATH}')" if pathlib.Path(_KAT_PATH).exists() else
       "(SELECT NULL::VARCHAR notice_id, NULL::VARCHAR branche WHERE false)")
# Dokument-Signale (aus den Vergabeunterlagen extrahiert): überschreiben die dünnen eForms-
# Aufwand-Felder, wo Unterlagen vorliegen. Guard: fehlt die Tabelle, leerer Stub.
# ── Welche Laender haben ueberhaupt Vergabeunterlagen? ───────────────────────────────────
# Fuer die Bitte an der Fundstelle (Aktivierung A). Gemessen am 2026-09-01: DE hat Volltext
# fuer 9.788 Vorgaenge, AT und CH fuer **null** — bei zusammen 2.783 offenen Vergaben.
#
# ⚠ ALS MESSUNG, NICHT ALS SATZ. „Aus Oesterreich haben wir keine einzige Unterlage" ist heute
# wahr und ist es an dem Tag nicht mehr, an dem die erste kommt. Ein fester Satz wuerde dann
# luegen, ohne dass es jemand merkt — die Sorte Fehler, die dieses Projekt teuer bezahlt hat.
# Der Export rechnet es jede Nacht neu; steht dort erst eine Unterlage, verschwindet die Bitte.
def _laender_ohne_unterlagen() -> set[str]:
    raus = set()
    for land in ("DE", "AT", "CH"):
        pfad = pathlib.Path(f"data/docs/{land}/doc_text.parquet")
        if not pfad.exists():
            raus.add(land)
            continue
        try:
            n = con.execute(f"select count(distinct notice_id) from read_parquet('{pfad.as_posix()}')").fetchone()[0]
        except Exception:                                          # noqa: BLE001
            n = 0
        if not n:
            raus.add(land)
    return raus


OHNE_UNTERLAGEN = _laender_ohne_unterlagen()

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
        for r in con.execute(f"""SELECT land, cpv4, segment_label, n_awards, erfolglos_pct,
                single_bidder_pct, struktur, top3_share, chronic_needs, opportunity_score,
                top_dominators, window_start, window_end FROM {MO}""").fetchall():
            (land, cpv4, label, na, erf, sb, struk, t3, chron, score, dom, ws, we) = r
            _seg[(land, cpv4)] = {
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

# `ohne` MUSS hier stehen, obwohl es kein Fachgebiet ist. Der Grundraum existiert seit dem
# Wegfall der CPV-Pflicht (Leads, deren QUELLE keinen CPV fuehrt), und `BRANCHE_LABEL.get(br, br)`
# faellt sonst auf den rohen Code zurueck — im Markt-Mix stuende dann „ohne" statt „Ohne
# Kategorie". Das Frontend fuehrt dasselbe Label in `web/lib/explorerCore.js`; die beiden
# muessen zusammenbleiben.
BRANCHE_LABEL = {"it": "IT & Software", "bau": "Bau & Infrastruktur",
                 "medizin": "Medizin & Gesundheit", "beratung": "Beratung & Dienstleistung",
                 "sicherheit": "Sicherheit & Verteidigung", "energie": "Energie & Versorgung",
                 "ohne": "Ohne Kategorie"}


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
                   row_number() OVER (PARTITION BY ge.lead_id ORDER BY cs.total_wins DESC, ge.entity_id) rn
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
    LEFT JOIN {KAT} kat ON kat.notice_id = e.lead_id
                WHERE ({BRANCHE}) = '{key}'"""
    tot, offen, stellen = con.execute(f"""
        SELECT count(*), count(*) FILTER (WHERE phase='open'), count(DISTINCT buyer_name) {where}""").fetchone()
    top = con.execute(f"""
        SELECT buyer_name, count(*) n, count(*) FILTER (WHERE phase='open') offen
        {where} AND buyer_name IS NOT NULL GROUP BY 1 ORDER BY 2 DESC, buyer_name LIMIT 6""").fetchall()
    ein = con.execute(f"""
        SELECT title, value_eur, cpv_code {where} AND phase='open' AND value_eur IS NOT NULL
        AND value_eur > 0 ORDER BY value_eur ASC, title LIMIT 5""").fetchall()
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
        # ⚠ `recent` stand im Export fest auf `[]` — bei ALLEN 4.967 Profilen.
        #
        # Der Renderer hat den Block „Zuletzt vergeben" seit jeher (explorerCore, `d.recent`),
        # und `buyer_recent_awards` liegt seit Langem gebaut daneben (38.320 Zeilen). Nur die
        # Zeile dazwischen fehlte. Nichts war rot: eine leere Liste rendert einen leeren Block,
        # und ein leerer Block sieht aus wie „diese Stelle hat halt nichts vergeben".
        #
        # Neueste zuerst — das ist die Frage, die ein Bieter stellt („wer gewinnt da GERADE?"),
        # nicht „was war mal am groessten".
        letzte = {}
        for bn, lid, tl, wn, val, known, dat in con.execute(f"""
                SELECT buyer_name, lead_id, titel, winner, value_eur, value_known, vergabe_datum
                FROM {BRA} WHERE buyer_name IN (SELECT name FROM _bn)
                QUALIFY row_number() OVER (PARTITION BY buyer_name
                        ORDER BY vergabe_datum DESC NULLS LAST) <= 6""").fetchall():
            letzte.setdefault(bn, []).append({
                "date": dat.strftime("%m/%Y") if dat and hasattr(dat, "strftime") else "",
                "title": tl or "", "winner": wn or "—",
                # Der Renderer prueft auf das Wort „unbekannt", um die Zelle zu graue n —
                # deshalb genau dieses Wort, nicht „k. A." oder ein leerer String.
                "value": eur(val) if (known and val) else "unbekannt",
                "lead": lid,
            })

        # Rueckfallebene fuer Kaeufer ohne TED-Statistik.
        doe = {r[0]: r for r in con.execute(f"""
                SELECT buyer_name, n_tenders, n_awarded, n_cpv_divisions,
                       top_division_label, main_nuts3, last_activity
                FROM {DBP} WHERE buyer_name IN (SELECT name FROM _bn)""").fetchall()}

        mix = {}
        for bn, br, n in con.execute(f"""
                SELECT e.buyer_name, {BRANCHE} AS br, count(*) n
                FROM {E} e LEFT JOIN {DC} b ON b.division = substr(e.cpv_code, 1, 2)
    LEFT JOIN {KAT} kat ON kat.notice_id = e.lead_id
                WHERE e.buyer_name IN (SELECT name FROM _bn) GROUP BY 1, 2""").fetchall():
            mix.setdefault(bn, {})[br] = n
        for n in todo:
            st = stats.get(n)
            if not st:
                # KEIN buyer_stats — aber vielleicht ein DÖE-Profil.
                #
                # Bisher stand hier `None`, und der Renderer zeigte seinen ehrlichen
                # Leerzustand („zu wenig Daten"). Ehrlich war das, vollstaendig nicht:
                # fuer 425 Kaeufer mit offenen Ausschreibungen liegt sehr wohl ein Profil
                # vor, nur eben aus der unterschwelligen Quelle. Das ist keine schlechtere
                # Vergabestelle, sondern eine kleinere — und genau die ist fuer einen
                # Mittelstaendler oft die interessantere.
                #
                # Das Profil bleibt SICHTBAR duenner: nur was DÖE hergibt, keine
                # Retention, kein Single-Bidder-Anteil. `sparse` steht deshalb auf True,
                # und `quelle` sagt dem Renderer und dem Leser, woher es kommt.
                dr = doe.get(n)
                if dr:
                    _, n_t, n_a, n_div, top_lbl, nuts, last = dr
                    _prof_cache[n] = {
                        "name": n, "sparse": True, "quelle": "unterschwellig",
                        "total": de(int(n_a)) if n_a else None,
                        "zeitraum": str(last)[:4] if last else "",
                        "perYear": None, "decision": None, "median": None, "volume": None,
                        "coverage": None, "division": top_lbl, "categories": None,
                        "winners": None, "mix": [], "top3": None,
                        "concentration": "fragmentiert", "topWinners": [], "winsAvg": None,
                        "single": None, "avgBidders": None, "retention": None,
                        "retentionLevel": None, "below": de(int(n_t)) if n_t else None,
                        "recent": letzte.get(n) or [],
                    }
                else:
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
                "below": None, "recent": letzte.get(n) or [],
                "_mix": mix.get(n, {}),
            }
    return {n: _prof_cache.get(n) for n in names}


def attach_mix(prof, own_branche):
    """CPV-Mix je Vergabestelle in die Ring-Form bringen; das eigene Feld markieren."""
    p = {k: v for k, v in prof.items() if k != "_mix"}
    counts = prof.get("_mix", {})
    tot = sum(counts.values()) or 1
    # Zweiter Sortierschlüssel ist Pflicht, nicht Kosmetik: die Liste wird auf vier Einträge
    # gekappt, und bei Gleichstand entschied vorher die zufällige Zeilenreihenfolge der
    # SQL-Abfrage, welche Branche es hineinschafft. Bei Stadt Ahaus liegen drei Branchen mit
    # je 2 % gleichauf — die Vergabestelle zeigte bei jedem Export ein anderes Profil, und im
    # Git-Diff war echte Änderung nicht mehr von Rauschen zu unterscheiden.
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
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

# ⚠ Die NULL-Prüfung steht VOR dem CASE über `b.branche` und ist nicht kosmetisch.
# Seit die CPV-Pflicht aus `build_prospective_leads` raus ist (2026-08-14, sie warf 307
# laufende Ausschreibungen weg), gibt es Leads ganz ohne CPV. Ohne diese Zeile fielen sie
# in das `ELSE 'beratung'` am Fuss des CASE — „Lieferung von 15 Notebooks" und „Milch und
# Molkereiprodukte" stuenden dann unter „Beratung & Dienstleistung". Ein eigener Grundraum
# sagt statt dessen, was der Fall ist: die Vergabe ist da, die Branche kennen wir nicht.
#
# ⚠ ZWEITE HAELFTE, nachgezogen 2026-08-14: „kein CPV" ist seit dem Kategorie-Wasserfall
# NICHT mehr dasselbe wie „Branche unbekannt". `b.branche` traegt jetzt auch die aus dem
# Titel abgeleitete Kategorie (`coalesce(dc.branche, katq.branche, 'Ohne Kategorie')` in
# `build_prospective_leads`), im selben Vokabular wie die CASE-Zweige unten.
#
# Ohne die Ergaenzung stieg der Export beim fehlenden CPV sofort aus und sah die Ableitung
# nie an — gemessen: alle 676 healyhudson-Leads landeten in „ohne", obwohl 674 davon eine
# Kategorie hatten. Der ganze Wasserfall war damit vorne wirkungslos, ohne dass etwas
# abbrach. „Ohne Kategorie" heisst jetzt: weder veroeffentlicht noch ableitbar.
BRANCHE = """CASE WHEN coalesce(b.branche, kat.branche) IS NULL THEN 'ohne'
  ELSE CASE coalesce(b.branche, kat.branche)
  WHEN 'IT' THEN 'it' WHEN 'Elektro' THEN 'it' WHEN 'Messtechnik' THEN 'it'
  WHEN 'Bau' THEN 'bau' WHEN 'Installation' THEN 'bau' WHEN 'Immobilien' THEN 'bau'
    WHEN 'Ingenieur/Architektur' THEN 'bau' WHEN 'Wartung' THEN 'bau'
  WHEN 'Medizin' THEN 'medizin' WHEN 'Gesundheit' THEN 'medizin'
  WHEN 'Sicherheit' THEN 'sicherheit'
  WHEN 'Energie' THEN 'energie' WHEN 'Versorgung' THEN 'energie' WHEN 'Wasser' THEN 'energie'
    WHEN 'Umwelt/Reinigung' THEN 'energie' WHEN 'Chemie' THEN 'energie' WHEN 'Rohstoffe' THEN 'energie'
  ELSE 'beratung' END END"""

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


# ⚠ FRISTEN GETRENNT VON ALLEM ANDEREN.
#
# `web/lib/leadIndex.ts::leadFristen()` braucht die Fristen ALLER Leads und las dafuer alle
# sieben `leads-<branche>.json` nacheinander — gemessen am 2026-08-25: **110 MB** fuer
# 43.735 Leads, von denen es sechs Felder benutzt. Dieselben sechs Felder als eine Datei:
# **7,2 MB**, also 6,5 %. Der Rest sind Beschreibung (22 %), Lose (13 %), Anforderungen
# (11 %) und Unterlagen (7 %) — Dinge, die eine Fristenliste nichts angehen.
#
# Anders als bei den Firmenprofilen hilft hier KEINE Datei je Eintrag: der Verbraucher
# braucht wirklich alle. Was er nicht braucht, sind die Spalten.
FRISTEN: list[dict] = []


def _frist_zeile(l: dict) -> dict:
    # ⚠ `buyer` kam am 2026-09-01 dazu, fuer die beobachtete Vergabestelle (Aktivierung D).
    # Der Posteingang muss wissen, WER ausschreibt, und der einzige andere Weg dorthin waere,
    # die sieben vollen Lead-Dateien zu lesen — 110 MB fuer ein Namensfeld. Genau davon ist
    # diese Datei die Abkehr. Der kurze Name reicht: er steht auch in der Meldung.
    return {"id": l.get("id"), "titel": l.get("titel"), "src": l.get("src"),
            "tage": l.get("tage"), "endTage": l.get("endTage"),
            "endeEcht": (l.get("timing") or {}).get("src") == "echt",
            "buyer": l.get("buyerShort") or l.get("buyer")}


def export_branche(key):
    rows = con.execute(f"""
        WITH mapped AS (
          SELECT e.*, cl.label AS cpv_label, cl.label_en AS cpv_label_en, cl.label_fr AS cpv_label_fr, {BRANCHE} AS ui_branche,
                 dl.deadline_source AS frist_source,
                 dl.deadline_date   AS frist_aktuell,
                 fp.frist_pub       AS frist_veroeffentlicht,
                 pt.portale         AS portale,
                 lg.lat AS geo_lat, lg.lon AS geo_lon,
                 lp.incumbent_name AS pred_incumbent, lp.n_bidders AS pred_bidders,
                 lp.competition_level AS pred_konk, lp.chain_depth AS pred_chain,
                 lp.incumbent_since_year AS pred_since,
                 ds.guarantee_required AS doc_guarantee, ds.binding_days AS doc_binding,
                 ds.eligibility_count AS doc_eligibility, ds.certificates AS doc_certs,
                 ds.variants_allowed AS doc_variants,
                 -- ⚠ VIERTE STELLE MIT DERSELBEN HANDGETIPPTEN LISTE. `doc_signals` traegt
                 -- fuenfzehn Spalten; hier standen fuenf. Die drei unten kippen eine
                 -- Bietentscheidung und muessen deshalb schon in der LISTE liegen, nicht
                 -- erst im Detail: ein Blocker, den man erst nach dem Oeffnen sieht,
                 -- filtert nichts. Welche Signale es gibt, steht in `govisor/kennzahlen.py`.
                 ds.site_visit AS doc_ortstermin,
                 ds.site_visit_mandatory AS doc_ortstermin_pflicht,
                 ds.presentation_required AS doc_praesentation,
                 -- Herkunft mitliefern statt nur den Wert: die Anzeige soll sagen koennen,
                 -- dass ein Bundesland ABGELEITET ist. Ein stillschweigend ergaenzter Wert
                 -- sieht aus wie eine Quelle — und danach wird gefiltert.
                 dn1.name AS region_abgeleitet_name,
                 -- ⚠ `widerspruechlich` steht VOR `amtlich`. Ein Wert, dem der
                 -- Kaeuferort widerspricht, ist nicht belegt — er steht nur da.
                 -- Bis zum 2026-09-01 hiessen 172 Magdeburger Leads unter
                 -- „Nordrhein-Westfalen" `amtlich` (s. scripts/region_ableiten.py).
                 CASE WHEN coalesce(rf.widerspruch, false) THEN 'widerspruechlich'
                      WHEN e.buyer_nuts1 IS NOT NULL AND e.buyer_nuts1 <> '' THEN 'amtlich'
                      WHEN rf.buyer_nuts1_abgeleitet IS NOT NULL THEN 'abgeleitet'
                 END AS region_quelle
          FROM {E} e
          LEFT JOIN {DC} b ON b.division = substr(e.cpv_code, 1, 2)
          LEFT JOIN {KAT} kat ON kat.notice_id = e.lead_id
          LEFT JOIN {CL} cl ON cl.cpv_code = e.cpv_code
          LEFT JOIN {DL} dl ON dl.notice_id = e.lead_id
          LEFT JOIN {PORTALE} pt ON pt.notice_id = e.lead_id
          LEFT JOIN {FRISTPUB} fp ON fp.notice_id = e.lead_id
          LEFT JOIN {LG} lg ON lg.lead_id = e.lead_id
          LEFT JOIN {LP} lp ON lp.lead_id = e.lead_id
          LEFT JOIN {DS} ds ON ds.notice_id = e.lead_id
          -- Abgeleitetes Bundesland (scripts/region_ableiten.py). LEFT JOIN auf eine Datei,
          -- die fehlen DARF: ohne sie verhaelt sich der Export wie vorher.
          LEFT JOIN {REGION_FILL} rf ON rf.lead_id = e.lead_id
          LEFT JOIN {DN} dn1 ON dn1.nuts_code = rf.buyer_nuts1_abgeleitet
        )
        , filtered AS (
          SELECT * FROM mapped WHERE ui_branche = '{key}'
            -- Übungsvorgänge der Portale und Behörden-Selbsttests gehören nicht in die
            -- Lead-Liste: sie sehen aus wie eine echte Ausschreibung, sind aber keine.
            -- Gold MARKIERT sie (Merkmal `testvergabe`), hier fliegen sie raus — das
            -- Frontend ist die Stelle, an der aus „markiert" ein „nicht zeigen" wird.
            -- ⚠ Das Muster ist eng: 203 Titel tragen „test" im Namen (Testautomation,
            -- Wafer Testing), von denen darf keiner mitgehen. S. govisor/testvergaben.py.
            AND NOT {_testvergabe_sql('title')}
            -- Auslauf-Radar bis 24 Monate. Wer eine Nachausschreibung vorbereiten will,
            -- braucht Vorlauf — und der gemessene Versatz (duration_calibration) zeigt, dass
            -- Nachfolger im Median deutlich VOR dem prognostizierten Ende erscheinen.
            AND (phase != 'expiring' OR months_to_expiry IS NULL
                 OR months_to_expiry BETWEEN -1 AND 24)
            -- Untergrenze NEU und nötig: seit die Zeitrechnung auf dem kalibrierten Datum
            -- läuft, rutschen Verträge ins Minus, deren Nachausschreibung erfahrungsgemäß
            -- längst hätte kommen müssen (gemessen 2.620 allein im Bau). Das sind keine
            -- Leads mehr, sondern verpasste Züge. Ein Monat Kulanz bleibt.
        ), ranked AS (
          -- Quote JE PHASE statt einer gemeinsamen Dringlichkeits-Rangliste. Vorher
          -- verdrängten die nächstliegenden Leads alles Ferne: gemessen lagen ALLE
          -- ausgelieferten Auslauf-Leads zwischen 0 und 26 Tagen, obwohl Gold 36.083
          -- mit über 30 Tagen kennt. Der lange Horizont fiel also nicht durch eine
          -- Entscheidung weg, sondern durch den Deckel.
          -- Auslauf zusätzlich JE MONAT quotiert. Ohne das nimmt die Quote wieder nur
          -- die nächstliegenden: mit reiner Phasen-Quote lag das Maximum bei 49 Tagen,
          -- obwohl 24 Monate erlaubt sind. So ist jeder Monat des Horizonts vertreten.
          -- ⚠ PARTITION AUCH NACH LAND. Ohne das belegen AT/CH-Leads Rangplätze in
          -- derselben Quote und schieben deutsche über den Deckel — obwohl sie unten per
          -- `OR country <> 'DE'` ohnehin ungedeckelt durchgehen. Gemessen am 2026-08-13,
          -- als AT/CH von 595/1.591 auf 17.124/8.608 Leads wuchsen: DE-Bau fiel von 5.608
          -- auf 3.837, ohne dass sich am deutschen Bestand irgendetwas geändert hätte.
          -- Der Deckel ist eine Quote FÜR DEUTSCHLAND; andere Länder dürfen sie nicht
          -- aufzehren.
          SELECT *, row_number() OVER (
            PARTITION BY coalesce(country, 'DE'), phase,
              CASE WHEN phase = 'expiring' THEN least(coalesce(months_to_expiry, 0), 24) ELSE 0 END
            ORDER BY coalesce(days_to_deadline, days_to_expiry, 99999) ASC, lead_id) AS rn
          FROM filtered
        )
        -- CAP je Phase — Nicht-DE-Leads (CH/AT, der DACH-Differenzierer, wenige) IMMER
        -- behalten, sonst verdrängt der große DE-Bestand sie aus dem Umkreis-losen Blick.
        -- OFFENE AUSSCHREIBUNGEN SIND UNGEDECKELT.
        --
        -- Sven am 2026-08-18: „ich verstehe nicht, warum wir nicht alle ausschreibungen
        -- anzeigen können?" Gemessen war der Deckel im Bau brutal: von 8.447 offenen kamen
        -- 2.500 durch, und weil nach naechster Frist sortiert wird, endete die Liste bei
        -- einer Frist von SECHS TAGEN. Wer Kapazitaet fuer Oktober plant, sah nichts.
        --
        -- Und sie waren nicht ausgeblendet, sondern WEG: die App liest ausschliesslich
        -- diese Dateien (lib/dataSource.ts → readFile), keine Route greift auf Gold oder
        -- Supabase zu. Kein Filter holt zurueck, was hier fehlt.
        --
        -- Warum es tragbar ist: 27,5 MB roh sind gemessen 3,5 MB ueber die Leitung
        -- (gzip 13 %). Der naheliegende Ausweg „schlanke Liste, Details auf Abruf" half
        -- NICHT — gemessen sind nur 1 % der Felder detail-only, alles andere liest der
        -- Explorer wirklich (Filter, Suche, Empfehlung). Es gibt kein Fett.
        --
        -- Der Auslauf-Radar bleibt monatsquotiert: das sind endende VERTRAEGE, keine
        -- Ausschreibungen, auf die man bieten kann. Ungedeckelt waeren es 64 MB.
        SELECT * EXCLUDE(rn) FROM ranked
        WHERE phase != 'expiring'
              OR rn <= {CAP_MONAT}
              OR coalesce(country, 'DE') <> 'DE'
        ORDER BY (phase = 'open') DESC,
                 coalesce(days_to_deadline, days_to_expiry, 99999) ASC, lead_id""").df().to_dict("records")

    lots = lots_for([r["lead_id"] for r in rows])
    leads = []
    for r in rows:
        g = lambda k: (None if (k not in r or r[k] is None or (isinstance(r[k], float) and r[k] != r[k])) else r[k])
        src = SRC.get(g("phase"), "auslauf")
        # Open House (§130a/§130c SGB V) ist kein Wettbewerb: jederzeit beitretbar, kein
        # Gewinner, keine echte Frist. Ungetrennt standen 1.899 solcher Dauerverfahren als
        # „offene Ausschreibung" in der Akquise — bei Medizin 1.816 von 2.003.
        offenes_haus = g("procedure_kind") == "open_house"
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
        # ⚠ OHNE GEWICHT IST NICHT OHNE KRITERIUM. Bis zum 2026-08-23 stand hier nur, was
        # ein Gewicht trug — und Österreich veröffentlicht die Kriterien zu 54 %, die
        # Gewichte zu 0 %. Also stand dort nichts. Wenn kein Gewicht bekannt ist, tragen
        # wir die genannten Typen ohne Prozentzahl ein; `pct: None` heisst „genannt, aber
        # ohne Gewichtung", nicht „0 %".
        if not z and g("award_types"):
            LAB = {"price": "Preis", "quality": "Qualität", "cost": "Kosten"}
            ART = {"price": "preis", "quality": "qualitaet", "cost": "kosten"}
            for t in str(g("award_types")).split(","):
                if t in LAB:
                    z.append({"art": ART[t], "label": LAB[t], "pct": None})

        tage = frist_tage if (src == "f02" and frist_tage is not None) else None
        endTage = int(r["days_to_expiry"]) if g("days_to_expiry") is not None else None
        mte = g("months_to_expiry")
        # Deutsch vorformuliert waere nicht uebersetzbar (jede Monatszahl ein eigener
        # Schluessel). Die Zahl wandert mit, den Satz baut das Frontend per `tk()`.
        endet = f"in {int(mte)} Mon." if mte is not None else None
        endetMonate = int(mte) if mte is not None else None

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
                       # ⚠ „unsicher", NICHT „uncertain". Die Pipeline spricht Englisch, die
                       # Oberflaeche Deutsch — `INC_SRC` fuenf Zeilen tiefer bildet genau das
                       # ab. Dieser Zweig ging daran vorbei und lieferte den Rohwert aus.
                       # Gemessen am 2026-08-31: 5.683 Leads. Fuer den Nutzer hiess das kein
                       # Herkunftspunkt (die CSS-Regeln greifen nur auf bekannte Werte, der
                       # Punkt blieb durchsichtig) und ein Tooltip mit dem Wort „undefined" —
                       # der Amtsinhaber sah aus wie gemessen, obwohl er aus einem
                       # VERGLEICHBAREN Zuschlag desselben Kaeufers abgeleitet ist.
                       "src": "unsicher", "hint": "aus dem letzten vergleichbaren Zuschlag desselben Käufers",
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
            # ZUSAETZLICHE HINWEISE (`web/lib/hinweise.ts`). Die Komponente war gebaut, im
            # Detail-Panel eingehaengt — und rendete IMMER nichts, weil keines dieser Felder
            # im JSON stand. Die Werte lagen die ganze Zeit in der Abfrage; es fehlte nur
            # diese Zuweisung. Wer ein Signal ergaenzt, ergaenzt HIER eine Zeile — die
            # Komponente muss nie wissen, welche die Pipeline gerade kann.
            #
            # Nur setzen, wo vorhanden: ein fehlendes Feld erzeugt schlicht keinen Hinweis,
            # ein leeres erzeugte einen leeren.
            **({"deadlineSource": g("frist_source")} if g("frist_source") else {}),
            **({"deadlineAktuell": str(g("frist_aktuell"))} if g("frist_aktuell") else {}),
            **({"deadlineVeroeffentlicht": str(g("frist_veroeffentlicht"))}
               if g("frist_veroeffentlicht") else {}),
            # `portale` kommt als Array — `if g("portale")` waere hier kein Wahrheitswert,
            # sondern ein ValueError („truth value of an array is ambiguous").
            **({"portale": [str(x) for x in g("portale")]}
               if g("portale") is not None and len(g("portale")) > 1 else {}),
            # Herkunft der Kategorie. `cpv` = veroeffentlicht (kein Hinweis noetig),
            # `modell` = aus dem Titel abgeleitet — DAS aendert das Vertrauen in den Filter
            # und gehoert deshalb sichtbar gemacht.
            **({"kategorieQuelle": g("category_source")}
               if g("category_source") in ("modell", "zwilling") else {}),
            # Amtsinhaber: die ZYKLEN sind der Massstab, nicht die Jahre (ein einzelner
            # langer Vertrag ist kein „etablierter" Amtsinhaber, s. hinweise.ts).
            **({"amtsinhaberZyklen": int(pred_chain)} if pred_chain else {}),
            **({"amtsinhaberSeitJahre": TODAY.year - int(g("pred_since"))}
               if g("pred_since") and TODAY.year > int(g("pred_since")) else {}),
            "titel": g("title") or "(ohne Titel)",
            "buyer": g("buyer_name") or "", "buyerShort": g("buyer_name") or "",
            "beschreibung": g("description") or "",
            "hasDetail": bool(g("has_detailed_description")),
            "cpv": g("cpv_code"), "cpvLabel": g("cpv_label") or g("buyer_activity") or "",
            # CPV-Bezeichnung amtlich in EN/FR (dieselbe EU-Codeliste, s. build_dim_cpv_label).
            # Nicht ueber den Sprachkatalog: das sind 9.454 Rechtsbegriffe, keine UI-Texte —
            # und die EU liefert sie fertig. Nur setzen, wo vorhanden; sonst bleibt es beim
            # deutschen Label statt einer erfundenen Uebersetzung.
            **({"cpvLabelEn": g("cpv_label_en")} if g("cpv_label_en") else {}),
            **({"cpvLabelFr": g("cpv_label_fr")} if g("cpv_label_fr") else {}),
            # Vergabe-Land aus der country-Spalte (DE-Gold hat keine → NULL → Default DE;
            # CH-Gold trägt 'CH'). Speist den DACH-Länderfilter.
            "land": g("country") or "DE",
            # Aus diesem Land liegt uns NOCH KEINE einzige Vergabeunterlage vor. Steuert die
            # Bitte in der Vergabe-Analyse; siehe `_laender_ohne_unterlagen`.
            "landOhneDocs": (g("country") or "DE") in OHNE_UNTERLAGEN,
              # Abgeleitetes Bundesland nur, wo keines dasteht — und mit Herkunft,
              # damit die Anzeige es kennzeichnen kann (s. `regionQuelle`).
              "region": g("buyer_region_name") or g("region") or g("region_abgeleitet_name") or "",
              # Kein `or "amtlich"`-Notausgang mehr: `region_quelle` deckt jetzt auch
              # den Widerspruchsfall ab, und ein Fallback wuerde ihn wieder zu
              # „belegt" machen — genau der Fehler, der behoben wurde.
              "regionQuelle": g("region_quelle"),
              "nuts": g("buyer_nuts") or "",
            # Koordinate (Käufersitz) für die echte PLZ-Umkreissuche (Haversine im Frontend);
            # None, wenn kein Geo-Bezug (bundesweite/ortsungebundene Leads) — ehrlich leer.
            "lat": round(float(r["geo_lat"]), 4) if g("geo_lat") is not None else None,
            "lon": round(float(r["geo_lon"]), 4) if g("geo_lon") is not None else None,
            "marktRegion": g("market_nuts3"), "marktRegionOk": bool(g("market_region_known")),
            "is_nationwide": bool(g("is_nationwide")),
            "contractKind": g("contract_kind"),
            "istRahmen": ist_rahmen,
            "verfahren": "open_house" if offenes_haus else "wettbewerb",
            "naturKat": naturkat or "dienst",
            "rahmen": rahmen,
            "volumen": {"wert": eur(g("value_eur")) or "Wert offen",
                        "src": VAL_SRC.get(g("value_source"), "unbekannt")},
            "timing": {"wert": endet or (f"{tage} Tage" if tage is not None else "offen"),
                       "src": TIM_SRC.get(g("timing_source"), "unbekannt"), "warn": False,
                       "hint": ""},
            "konk": {"wert": konk_wert,
                     # Dieselbe Falle als Vorgabewert — heute unbenutzt, aber sie waere
                     # beim ersten Treffer genauso still.
                     "src": KONK_SRC.get(g("competition_source"), "unsicher" if use_pred else "na"),
                     "stufe": konk_stufe,
                     "hint": ("Aus der letzten Zuschlagsbekanntmachung." if g("competition_source") == "actual"
                              else "Aus dem letzten vergleichbaren Zuschlag desselben Käufers." if use_pred else "")},
            "relevanz": "na",  # ohne gepflegtes Profil nicht berechenbar → ehrlich n/a
            "wechsel": wechsel,
            "kette": kette,    # Nachfolge-Kette: {tiefe, seit} — nur wenn ≥2 Verträge belegt
            "neu": bool(g("is_new_tender")) and not use_pred,
            "incumbent": inc_obj,
            "tage": tage, "endTage": endTage, "endet": endet, "endetMonate": endetMonate,
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
            # Die Kriterien im Klartext, wie die Vergabestelle sie nennt („Vorstellung",
            # „Termintreue"). Verweise auf die Unterlagen sind in Gold schon aussortiert.
            "zuschlagNamen": (str(g("award_criteria")).split(" · ")
                              if g("award_criteria") else None),
            # #13 Dokument-Wasserfall: erst der echte Unterlagen-Link (documents_url), sonst nur
            # die Plattform (source_url). `source` hält die zwei sauber auseinander; `access` ist
            # ehrlich 'unknown' — die non-restricted-Markierung ist noch nicht aus dem XML gezogen.
            # ⚠ `access` STAND AUF „unknown" — IMMER, bei allen 13.849 Vergaben mit Link.
            # Das Feld existierte, wurde aber nie gefüllt, und der Abrufer konnte deshalb
            # nicht priorisieren: er wusste vorher nie, wo es sich lohnt. Für die Schweiz
            # steht die Antwort seit dem simap-Ingest in Gold — `documents_source` sagt
            # sogar WIE (Plattform, externer Link, auf Anfrage, per Post), und
            # `documents_paid` sagt, ob sie Geld kosten. Gemessen: CH 675 Plattform,
            # 70 externer Link, 67 nur auf Anfrage, 2 postalisch.
            # ⚠ `access` sagt, was die QUELLE anbietet. `gelesen` sagt, ob WIR den Text
            # haben. Zwei verschiedene Fragen, und bis zum 2026-08-25 gab es nur die erste
            # — 5.899 offene deutsche Leads mit Volltext zeigten dem Nutzer „unknown" oder
            # gar nichts. Der Block entsteht deshalb jetzt auch OHNE Link, wenn wir den
            # Text haben: sonst faellt genau die Auskunft weg, die zaehlt.
            "unterlagen": _unterlagen(g, VOLLTEXT),
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
                # ⚠ DREIWERTIG: True / False / None. `None` heisst „das Portal sagt nichts",
                # NICHT „nicht erlaubt". Nur simap veroeffentlicht beides strukturiert
                # (78 % bzw. 55 %); eForms hat dafuer kein bieterseitiges Feld mit Substanz.
                # Die Oberflaeche muss den Unterschied tragen, sonst wird aus einer
                # fehlenden Angabe eine Absage.
                "unterauftrag": (bool(g("subcontracting_allowed"))
                                 if g("subcontracting_allowed") is not None else None),
                "bietergemeinschaft": (bool(g("consortium_allowed"))
                                       if g("consortium_allowed") is not None else None),
                "zertifikate": (str(g("doc_certs")).split(",") if g("doc_certs") else []),
                # ⚠ Ortstermin: DREI Zustaende, und der mittlere ist der wichtige.
                # `None` = die Unterlagen sagen nichts. `True/False` bei `pflicht` gilt nur,
                # wenn ueberhaupt ein Termin erkannt wurde — sonst waere „nicht
                # verpflichtend" eine Aussage ueber einen Termin, den es nicht gibt.
                # Gemessen 2026-09-01: 3.723 Vorgaenge mit Termin, davon 108 verpflichtend.
                "ortstermin": (bool(g("doc_ortstermin")) if g("doc_ortstermin") is not None else None),
                "ortsterminPflicht": (bool(g("doc_ortstermin_pflicht"))
                                      if g("doc_ortstermin") else None),
                "praesentation": (bool(g("doc_praesentation"))
                                  if g("doc_praesentation") is not None else None),
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
            # ⚠ HIER STAND EINE ANNAHME. „gesamtschuldnerisch haftend" wurde jedem Lead
            # mit Los-Grenze angeheftet, ohne einen einzigen Beleg — und die Oberflaeche
            # zeigte daneben „Bietergemeinschaft: zugelassen". Beides war geraten.
            # Jetzt steht die Form nur da, wo das Portal die Bietergemeinschaft wirklich
            # erlaubt (simap, 55 %); sonst bleibt das Feld leer und die Anzeige sagt
            # „keine Angabe" statt einer Zusage.
            if (l.get("anf") or {}).get("bietergemeinschaft"):
                l["bgForm"] = "gesamtschuldnerisch haftend"

    # Payload-Split: die zwei schweren Felder (Beschreibung, Vergabestellen-Profil) wandern
    # in eine Detail-Datei und werden erst beim Öffnen eines Leads nachgeladen. So bleibt die
    # Listen-Ladung schlank genug, um viele Tausend Leads client-seitig zu filtern/sortieren.
    seg = segments()
    for l in leads:
        # Segment des EIGENEN Landes. Kein Rueckfall auf DE: „in Deutschland ist dieses
        # Segment schwach" ist fuer eine Schweizer Vergabe keine Aussage, sondern eine
        # Verwechslung — und sie waere im Markt-Tab nicht als solche zu erkennen.
        l["marktSegment"] = seg.get((l.get("land") or "DE", (l.get("cpv") or "")[:4]))
    # Sprachfassungen nachladen: die Liste bekommt nur die Sprach-CODES (kompakt, fuer
    # einen Umschalter), die Texte selbst wandern ins Detail — sonst blaeht sich die
    # Listen-Payload um ein Vielfaches auf (563 Leads fuehren 24 Sprachen).
    sprachen: dict[str, list[str]] = {}
    fassungen: dict[str, dict] = {}
    if LT and leads:
        ph2 = ",".join("?" for _ in leads)
        for lid, feld, lang, wert in con.execute(f'''
                SELECT lead_id, field, language, value FROM {LT}
                WHERE lead_id IN ({ph2}) AND lot_id IS NULL
                  -- NUR Titel und Beschreibung. `cpv_label` ist die uebersetzte
                  -- CPV-Kategorie, keine Fassung des Dokuments: sie steht in 24 Sprachen
                  -- auch dann da, wenn es nur EINEN Titel gibt. Ungefiltert bekaemen
                  -- gemessen 554 Leads eine Sprachwahl vorgegaukelt — mehr als die 76,
                  -- die wirklich eine haben.
                  AND field IN ('title', 'description')
                ORDER BY lead_id, field, language''',
                [l["id"] for l in leads]).fetchall():
            sprachen.setdefault(lid, [])
            if lang not in sprachen[lid]:
                sprachen[lid].append(lang)
            # Gleiche Deckelung wie bei `beschreibung` unten. Nicht wegen der Payload — die
            # Fassungen liegen ohnehin in der nachgeladenen Detail-Datei —, sondern wegen der
            # Anzeige: der Block nennt eine Wortzahl. Gemessen sind 35 von 442 Fassungen
            # laenger als 2.000 Zeichen; ungedeckelt zeigte dieselbe Ausschreibung auf
            # Deutsch 238 Woerter und auf Franzoesisch 900 — das liest sich wie ein Defekt,
            # nicht wie eine Uebersetzung.
            if feld == "description" and wert and len(wert) > 2000:
                wert = wert[:2000] + " …"
            fassungen.setdefault(lid, {}).setdefault(lang, {})[feld] = wert

    detail = {}
    for l in leads:
        # Beschreibung bleibt AM Lead (nicht ausgelagert): sie ist der eigentliche Inhalt und
        # muss durchsuchbar sein (leadText). Nur buyerProfile/marktSegment werden on-demand
        # nachgeladen. Sehr lange Beschreibungen (selten, bis 17k) für die Listen-Payload auf
        # 2.000 Zeichen deckeln — der Volltext liegt ohnehin in den Vergabeunterlagen.
        if l.get("beschreibung") and len(l["beschreibung"]) > 2000:
            l["beschreibung"] = l["beschreibung"][:2000] + " …"
        # Nur ansagen, wenn es wirklich eine Wahl gibt: eine einzige Fassung ist keine
        # Sprachwahl, sondern nur die Sprache, in der die Vergabe veroeffentlicht wurde.
        sp = sprachen.get(l["id"]) or []
        if len(sp) > 1:
            l["sprachen"] = sp
        detail[l["id"]] = {"buyerProfile": l.pop("buyerProfile", None),
                           "marktSegment": l.pop("marktSegment", None),
                           "sprachfassungen": fassungen.get(l["id"]) if len(sp) > 1 else None}
    (OUT / f"leads-{key}.json").write_text(json.dumps(leads, ensure_ascii=False, sort_keys=True))
    (OUT / f"detail-{key}.json").write_text(json.dumps(detail, ensure_ascii=False, sort_keys=True))
    FRISTEN.extend(_frist_zeile(l) for l in leads)
    return len(leads)


counts = con.execute(f"""
    SELECT {BRANCHE} AS k, count(*) n
    FROM {E} e LEFT JOIN {DC} b ON b.division = substr(e.cpv_code, 1, 2)
    LEFT JOIN {KAT} kat ON kat.notice_id = e.lead_id
    WHERE (e.phase != 'expiring' OR e.months_to_expiry IS NULL OR e.months_to_expiry <= 18)
    GROUP BY 1""").fetchall()
counts = {k: n for k, n in counts}

exported = {}
markets = {}
for key in ["it", "bau", "medizin", "beratung", "sicherheit", "energie", "ohne"]:
    exported[key] = export_branche(key)
    markets[key] = market_summary(key)
    print(f"  {key:11} {exported[key]:>5} / {counts.get(key, 0):>6} exportiert")

(OUT / "leads-fristen.json").write_text(
    json.dumps(FRISTEN, ensure_ascii=False, separators=(",", ":")))
print(f"  {len(FRISTEN):,} Fristen → web/data/leads-fristen.json "
      f"({(OUT / 'leads-fristen.json').stat().st_size / 1048576:.1f} MB "
      f"statt 110 MB ueber sieben Dateien)")

(OUT / "markt.json").write_text(json.dumps(markets, ensure_ascii=False, sort_keys=True))

(OUT / "branchen.json").write_text(json.dumps(counts, ensure_ascii=False, sort_keys=True))

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
(OUT / "plz-geo.json").write_text(json.dumps(plz_geo, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
print(f"PLZ→Koordinate: {sum(len(v) for v in plz_geo.values())} Einträge "
      f"({', '.join(f'{k}:{len(v)}' for k, v in plz_geo.items())}) → plz-geo.json")

print(f"\nGesamt-Bestand je Grundraum: {counts}")
print(f"Dateien in {OUT}/")
