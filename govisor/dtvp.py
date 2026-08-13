"""Quelle DE — DTVP (Deutsches Vergabeportal) Bekanntmachungs-Downloader.

**Warum diese Quelle.** DTVP (Bundesanzeiger Verlag + cosinex) führt ober- UND unterschwellige
Vergaben. Über TED bekommen wir nur die oberschwelligen. Gemessen 2026-08-13 an einer über
05/2024–08/2026 gestreuten Stichprobe von 50 VOB/A-Ausschreibungen: **38 % fehlten in unserem
Bestand** — kommunaler Tiefbau, Schul- und Bädersanierung, Universitätsbau. Hochgerechnet auf
6.769 offene VOB/A-Treffer sind das ~2.600 Vergaben allein in dieser Kategorie.

⚠ Eine *erste*, kleinere Stichprobe (12 Titel, alle vom selben Publikationstag) ergab 0 %
Zugewinn und hätte fast zur Entscheidung „nicht bauen" geführt. Sie war systematisch verzerrt:
ausgerechnet der laufende Tag ist durch den TED-Live-Abruf gut abgedeckt. **Eine Stichprobe aus
einem einzigen Zeitpunkt misst den Zeitpunkt, nicht die Quelle.**

**Warum ein Browser und nicht `requests`.** Gemessen und dreifach belegt: die Trefferliste
entsteht clientseitig. Die Suchparameter stehen als Base64-JSON im **URL-Fragment**, das ein
Server nie zu sehen bekommt; dieselben Parameter als Query-String liefern eine leere Seite
(vier Varianten getestet), ein Formular-POST antwortet mit HTTP 500, und beim Seitenwechsel
wird kein einziger XHR abgesetzt. Deshalb Playwright. Das ist teurer als der RIB-Connector
(`requests` genügte, weil dort ein JS-Literal im HTML stand) — aber es gibt keinen billigeren Weg.

**Der Suchvertrag** (aus der laufenden Anwendung abgelesen)::

    /Center/common/project/search.do?method=showExtendedSearch&fromExternal=true#<base64-json>
    {"contractingRules":["VOB"], "publicationTypes":["Tender"], "pageNumber":"1",
     "cpvCodes":[], "location":{}, "searchText":"",
     "sort":{"order":[{"property":"PROJECT_PUBLICATION_DATE_LNG","direction":"DESC"}]}}

    contractingRules   VOL (= VgV/VOL/A/UVgO) · VOB (= VOB/A) · VSVGV · SEKTVO · OTHER
    publicationTypes   Tender (Ausschreibung) · ExAnte (Vorinfo) · ExPost (Zuschlag)

Sortierung nach Veröffentlichungsdatum absteigend: ein Tageslauf blättert nur so weit, bis er
auf bereits bekannte `pid` trifft (``--stop-nach-bekannten``), statt jedes Mal 339 Seiten.

**Bronze = eine Zeile je Bekanntmachung als JSONL**, ``data/raw_dtvp/DE/YYYY-MM.jsonl``,
dedupliziert über ``pid``. Wie bei TED/DÖE/simap liegt die Verlustfreiheit in Bronze: ein
Parser-Fix kostet einen Re-Run über lokale Dateien, keinen erneuten Abruf.

**Was DTVP NICHT liefert.** Die Trefferzeile trägt Veröffentlichung, Frist, Titel, Verfahrensart
und Vergabestelle — keinen CPV-Code, keine Beschreibung, keinen Wert. Die Detailseite liegt
hinter ``/Center/secured/…`` und ist ungeprüft. Ein DTVP-Lead ist damit ärmer als ein
TED-Lead; das gehört beim Mapping nach Silber ausgewiesen, nicht kaschiert.

Aufruf::

    python3 -m govisor.dtvp --regeln VOB,VOL --typen Tender --max-seiten 20
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BASE = "https://www.dtvp.de/Center/common/project/search.do?method=showExtendedSearch&fromExternal=true"
EINSTIEG = "https://www.dtvp.de/Center/company/announcements/categoryOverview.do?method=showCategoryOverview"

REGELN = ("VOL", "VOB", "VSVGV", "SEKTVO", "OTHER")
TYPEN = ("Tender", "ExAnte", "ExPost")
_PRO_SEITE = 20
_WARTE_MS = 3000          # Rendern abwarten; darunter kamen leere Tabellen
_HOEFLICH_MS = 1200       # Pause zwischen Seiten — fremdes System, kein Grund zu hetzen


def _fragment(regel: str, typ: str, seite: int) -> str:
    par = {
        "cpvCodes": [], "contractingRules": [regel], "publicationTypes": [typ],
        "location": {}, "pageNumber": str(seite), "searchText": "",
        "sort": {"order": [{"property": "PROJECT_PUBLICATION_DATE_LNG", "direction": "DESC"}]},
    }
    return base64.b64encode(json.dumps(par, separators=(",", ":")).encode()).decode()


_ZEILE_JS = """() => [...document.querySelectorAll('tbody tr')].map(tr => {
    const c = [...tr.cells].map(x => x.innerText.replace(/\\s+/g,' ').trim());
    const a = tr.querySelector('a');
    const m = a && (a.getAttribute('href')||'').match(/pid=(\\d+)/);
    return c.length >= 5 ? {pub:c[0], frist:c[1], titel:c[2], typ:c[3], stelle:c[4],
                            pid: m ? m[1] : null} : null;
  }).filter(Boolean)"""


def _datum(s: str):
    try:
        return dt.datetime.strptime(s.strip(), "%d.%m.%Y").date()
    except (ValueError, AttributeError):
        return None


def hole(regeln, typen, max_seiten: int, bekannt: set[str], stop_nach: int):
    """Bekanntmachungen abrufen. Gibt eine Liste von Sätzen zurück (Bronze-Form)."""
    from playwright.sync_api import sync_playwright

    aus: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        seite = browser.new_page()
        seite.set_default_timeout(45000)
        seite.goto(EINSTIEG, wait_until="domcontentloaded")
        for regel in regeln:
            for typ in typen:
                treffer_alt = 0
                for nr in range(1, max_seiten + 1):
                    seite.goto(f"{BASE}#{_fragment(regel, typ, nr)}", wait_until="domcontentloaded")
                    seite.wait_for_timeout(_WARTE_MS)
                    zeilen = seite.evaluate(_ZEILE_JS)
                    if not zeilen:
                        break                       # Ende der Liste
                    neu = [z for z in zeilen if z.get("pid") and z["pid"] not in bekannt]
                    for z in neu:
                        z["regel"], z["ptyp"] = regel, typ
                        aus.append(z)
                    treffer_alt += len(zeilen) - len(neu)
                    print(f"    {regel}/{typ} S.{nr}: {len(zeilen)} Zeilen, {len(neu)} neu",
                          flush=True)
                    # Sortiert nach Datum absteigend: sind genug Bekannte in Folge dabei,
                    # sind wir am Stand des letzten Laufs angekommen.
                    if stop_nach and treffer_alt >= stop_nach:
                        print(f"    {regel}/{typ}: {treffer_alt} bekannte erreicht — Abbruch",
                              flush=True)
                        break
                    seite.wait_for_timeout(_HOEFLICH_MS)
        browser.close()
    return aus


def schreibe_bronze(saetze: list[dict], country: str = "DE") -> dict:
    """Nach Monat gebündelt als JSONL, dedupliziert über pid. Idempotent."""
    root = ROOT / "data" / "raw_dtvp" / country
    root.mkdir(parents=True, exist_ok=True)
    nach_monat: dict[str, list[dict]] = {}
    for s in saetze:
        d = _datum(s.get("pub", ""))
        nach_monat.setdefault(d.strftime("%Y-%m") if d else "unbekannt", []).append(s)
    stat = {}
    for monat, neue in nach_monat.items():
        pfad = root / f"{monat}.jsonl"
        vorhanden: dict[str, dict] = {}
        if pfad.exists():
            for zeile in pfad.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(zeile)
                    vorhanden[r["pid"]] = r
                except (json.JSONDecodeError, KeyError):
                    continue
        vor = len(vorhanden)
        for r in neue:
            vorhanden[r["pid"]] = r
        pfad.write_text("\n".join(json.dumps(r, ensure_ascii=False)
                                  for r in vorhanden.values()) + "\n", encoding="utf-8")
        stat[monat] = (len(vorhanden) - vor, len(vorhanden))
    return stat


def bekannte_pids(country: str = "DE") -> set[str]:
    root = ROOT / "data" / "raw_dtvp" / country
    aus: set[str] = set()
    if not root.exists():
        return aus
    for f in root.glob("*.jsonl"):
        for zeile in f.read_text(encoding="utf-8").splitlines():
            m = re.search(r'"pid":\s*"(\d+)"', zeile)
            if m:
                aus.add(m.group(1))
    return aus


# ── Bronze → Silber ───────────────────────────────────────────────────────────────────────────
#
# **Die CPV-Frage ist die schwierigste an dieser Quelle.** DTVP liefert in der Trefferzeile
# keinen CPV-Code, und `gold.build_prospective_leads` verlangt `cpv_main IS NOT NULL` — ohne
# CPV fiele jeder DTVP-Lead lautlos aus der Lead-Schicht (genau der Mechanismus, an dem in
# Oesterreich 357 offene Verfahren haengen blieben, siehe A6-Guard).
#
# Geraten wird trotzdem nicht. Fuer **VOB/A** ist die Branche keine Vermutung, sondern die
# Definition der Vorschrift: VOB ist die Vergabe- und Vertragsordnung fuer BAULEISTUNGEN.
# Jede VOB/A-Vergabe ist eine Bauleistung, deshalb CPV-Division 45 (Bauarbeiten). Der
# generische Code `45000000-7` traegt genau diese Aussage — Bau, ohne Gewerk-Detail — und
# nicht mehr.
#
# Fuer **VOL/UVgO** (Liefer- und Dienstleistungen) gibt es keine solche Ableitung: das kann
# IT, Beratung, Reinigung oder Medizintechnik sein. Dort bleibt `cpv_main` NULL. Diese Leads
# erscheinen damit NICHT in der Branchen-Liste — richtig so, denn eine erfundene Branche
# waere schlimmer als eine fehlende. Ein spaeterer Titel-Klassifizierer koennte das heben;
# er gehoert dann in die `review`-Queue mit Konfidenz, nicht hierher.
#
# Die Herkunft steht in `attributes` (`dtvp/cpv_hergeleitet`), damit im Produkt nachvollziehbar
# bleibt, dass diese 45er nicht aus der Bekanntmachung stammen, sondern aus dem Regelwerk.
_CPV_AUS_REGELWERK = {"VOB": "45000000-7"}      # VOB/A = Bauleistungen, per Definition
_KIND = {"Tender": "cn", "ExAnte": "pin", "ExPost": "can"}


def nach_silber(country: str = "DE") -> dict:
    """Bronze-JSONL → Silber-Parquet (notices, notice_parties, attributes).

    `notice_id` ist ``dtvp:<pid>`` — der Praefix haelt den Namensraum von TED-IDs getrennt
    (dieselbe Konvention wie bei DOeE, wo reine Zahlen sonst mit TED kollidiert waeren).
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    roh_dir = ROOT / "data" / "raw_dtvp" / country
    if not roh_dir.exists():
        print(f"kein Bronze-Bestand unter {roh_dir}")
        return {}
    saetze: list[dict] = []
    for f in sorted(roh_dir.glob("*.jsonl")):
        for zeile in f.read_text(encoding="utf-8").splitlines():
            try:
                saetze.append(json.loads(zeile))
            except json.JSONDecodeError:
                continue
    if not saetze:
        return {}

    notices, parties, attrs = [], [], []
    for r in saetze:
        nid = f"dtvp:{r['pid']}"
        pub, frist = _datum(r.get("pub", "")), _datum(r.get("frist", ""))
        regel = r.get("regel", "")
        cpv = _CPV_AUS_REGELWERK.get(regel)
        notices.append({
            "notice_id": nid, "publication_number": r["pid"], "oj_ref": None,
            "publication_date": pub, "ted_url": None, "country": country,
            "buyer_countries": [country],
            "year": pub.year if pub else None, "month": pub.month if pub else None,
            "schema_gen": "dtvp", "form_type": r.get("typ"),
            "notice_kind": _KIND.get(r.get("ptyp"), "cn"),
            # KLEINGESCHRIEBEN. `test_sprachcodes_sind_kanonisch` verlangt die
            # kanonische Form; "DE" liess den Guard sofort anschlagen.
            "language": "de",
            "title": r.get("titel"), "description": None, "description_field": None,
            "cpv_main": cpv, "performance_nuts": None,
            "contract_nature": "works" if regel == "VOB" else None,
            "procedure_type": None, "submission_deadline": frist,
            "portal_url": f"https://www.dtvp.de/Center/secured/company/projectForwarding.do?pid={r['pid']}",
            "estimated_value": None, "final_value": None, "value_currency": None,
            "award_date": None, "start_date": None, "end_date": None,
            "lot_count": None, "text_chars": len(r.get("titel") or ""),
            "ref_publication_number": None, "ref_ted_url": None,
            "flags": [], "unknown_country_codes": [],
        })
        if r.get("stelle"):
            parties.append({
                "notice_id": nid, "role": "buyer", "seq": 0, "name": r["stelle"],
                "national_id": None, "town": None, "postal_code": None, "country": country,
                "nuts": None, "email": None, "phone": None, "contact_person": None,
                "url": None, "is_sme": None, "in_consortium": None,
                "year": pub.year if pub else None,
            })
        attrs.append({"notice_id": nid, "path": "dtvp/contractingRule", "value": regel})
        if cpv:
            attrs.append({"notice_id": nid, "path": "dtvp/cpv_hergeleitet",
                          "value": f"aus Regelwerk {regel}"})

    stat = {}
    for name, zeilen in (("notices", notices), ("notice_parties", parties),
                         ("attributes", attrs)):
        nach_jahr: dict[int, list] = {}
        for z in zeilen:
            nach_jahr.setdefault(z.get("year") or 0, []).append(z)
        n = 0
        for jahr, gruppe in nach_jahr.items():
            d = ROOT / "data" / "silver" / country / name / f"year={jahr}"
            d.mkdir(parents=True, exist_ok=True)
            pq.write_table(pa.Table.from_pylist(gruppe), d / f"{jahr}-dtvp.parquet",
                           compression="zstd")
            n += len(gruppe)
        stat[name] = n
    ohne_cpv = sum(1 for x in notices if not x["cpv_main"])
    print(f"DTVP Silber {country}: " + " · ".join(f"{k} {v:,}" for k, v in stat.items()))
    print(f"  cpv_main aus Regelwerk hergeleitet: {len(notices)-ohne_cpv:,} (VOB/A = Bauleistung)")
    print(f"  ohne CPV (VOL/UVgO, bewusst NULL):  {ohne_cpv:,}")
    return stat


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="DTVP-Bekanntmachungen → Bronze")
    ap.add_argument("--regeln", default="VOB,VOL",
                    help=f"Komma-Liste aus {','.join(REGELN)}")
    ap.add_argument("--typen", default="Tender", help=f"Komma-Liste aus {','.join(TYPEN)}")
    ap.add_argument("--max-seiten", type=int, default=20, help="je Regel×Typ")
    ap.add_argument("--stop-nach-bekannten", type=int, default=40,
                    help="Abbruch, wenn so viele bereits bekannte Treffer gesehen wurden (0 = nie)")
    ap.add_argument("--silber", action="store_true", help="nach dem Abruf Bronze→Silber bauen")
    ap.add_argument("--nur-silber", action="store_true", help="nur Bronze→Silber, kein Abruf")
    a = ap.parse_args(argv)
    regeln = [x.strip() for x in a.regeln.split(",") if x.strip() in REGELN]
    typen = [x.strip() for x in a.typen.split(",") if x.strip() in TYPEN]
    if not regeln or not typen:
        print(f"Ungültige Auswahl. Regeln: {REGELN}, Typen: {TYPEN}")
        return 2
    if a.nur_silber:
        nach_silber()
        return 0
    bekannt = bekannte_pids()
    print(f"DTVP-Abruf: Regeln {regeln}, Typen {typen}, max. {a.max_seiten} Seiten je Kombination")
    print(f"  {len(bekannt):,} pid bereits im Bestand")
    saetze = hole(regeln, typen, a.max_seiten, bekannt, a.stop_nach_bekannten)
    if not saetze:
        print("  Keine neuen Bekanntmachungen.")
        return 0
    stat = schreibe_bronze(saetze)
    ges = sum(n for n, _ in stat.values())
    print(f"\n  {ges:,} neue Bekanntmachungen in {len(stat)} Monatsdateien:")
    for monat in sorted(stat)[-6:]:
        neu, total = stat[monat]
        print(f"    {monat}: +{neu:,} (jetzt {total:,})")
    if a.silber:
        print()
        nach_silber()
    return 0


if __name__ == "__main__":
    sys.exit(main())
