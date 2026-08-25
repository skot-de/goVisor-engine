"""Quelle DE — Healy-Hudson-Portale: **eine Liste für alle sechzehn Bundesländer**.

Gebaut, weil Sven wissen wollte, ob Bayern und Hamburg als Landesportale angebunden sind.
Die Antwort war größer als die Frage: beide fahren dieselbe Software, und die hat eine
öffentliche, nach Bundesland parametrisierte Bekanntmachungsliste.

**Wie das gefunden wurde.** ``www.evergabe.bayern.de`` und
``fbhh-evergabe.web.hamburg.de`` tragen in unseren Daten denselben URL-Pfad
``/evergabe.bieter/api/supplier/external/deeplink/subproject/<uuid>``. Der Bieterbereich
verlangt beidesmal eine Anmeldung (identischer Login, „Healy Hudson GmbH, Build
4.9.36.294"). Der Deeplink leitet aber auf ein **öffentliches** Dashboard, und die
bayerische Landesseite ``auftraege.bayern.de`` verlinkt „Zu den Ausschreibungen" auf::

    /Dashboards/Dashboard_off?BL=09

``BL`` ist der amtliche Bundesland-Schlüssel. Damit ist die Liste für **jedes** Land
abrufbar, ohne Anmeldung. Gemessen 2026-08-14, offene Vorgänge::

    BY 395 · BW 202 · NRW 151 · NI 147 · SL 119 · HH 67 · HE 49 · BE 49 · RP 35
    SH 19 · BB 15 · MV 14 · SN 14 · TH 12 · ST 10 · HB 2        = 1.300 gesamt

Über die Unterlagen-Links kennen wir davon bisher 508. Die Familie umfasst neben Bayern und
Hamburg auch ``bieterzugang.deutsche-evergabe.de`` (234 Leads),
``bieterportal.noncd.db.de`` (128, Deutsche Bahn), ``bieter.ehealth-evergabe.de`` (23) und
``ausschreibungen.kfw.de`` (4) — **ein Modul statt sechs**. Das ist dieselbe Lehre wie bei
den Unterlagen: die Plattform-Familie ist die Einheit, nicht das Bundesland.

⚠ **Die Liste rotiert.** Ein Abruf liefert ~20–27 Zeilen, unabhängig davon, ob 2 oder 395
Vorgänge gemeldet sind — und bei jedem Abruf eine andere Auswahl. Sechs Abrufe auf Bayern
ergaben kumuliert 91 von 395. Es ist also **keine Seitennavigation**, sondern eine
Zufallsauswahl; ``&page=``, ``&Seite=``, ``&start=`` und drei weitere Varianten wurden
geprüft, alle werden ignoriert (sie liefern zwar andere Zeilen, aber nur weil jede Antwort
neu würfelt). Der CPV-Parameter wird als URL-Argument ebenfalls ignoriert — die Seite
filtert CPV nur über ein POST-Formular.

Konsequenz für die Bauart: **wiederholt abrufen, bis nichts Neues mehr kommt** — und
**melden, wie vollständig der Lauf war**. Kleine Länder sind in einem Abruf komplett
(Bremen: zweimal geholt, beide Male dieselben 4 Zeilen), große brauchen viele Runden. Was
nicht erreicht wurde, steht in der Zusammenfassung; ein Lauf, der 60 % holt und „fertig"
meldet, wäre schlimmer als gar keiner.

**Bronze** (``data/raw_healyhudson/<YYYY-MM>.jsonl``) **und Silber** (seit 2026-08-14,
``--silber``). Ohne den Silber-Schritt sammelte die Quelle wochenlang JSONL, aus dem kein
einziger Lead entstehen konnte — verdrahtet und wirkungslos ist der teuerste Zustand, weil
er von aussen wie „fertig" aussieht.

Was die Quelle NICHT hat: keinen CPV, keinen Wert, keine Beschreibung, keinen Link zum
Vorgang (die Trefferzeilen tragen nachweislich kein ``a[href]``). Was sie als einzige hat:
das **Bundesland**, ausdrücklich, für alle sechzehn. Die unterschwellige Ebene trägt sonst
gar keine Landeszuordnung.

Aufruf::

    python3 -m govisor.healyhudson --laender BY,HH --runden 12
    python3 -m govisor.healyhudson --alle --runden 8
    python3 -m govisor.healyhudson --laender HB --dry-run
    python3 -m govisor.healyhudson --silber          # nur Bronze → Silber, ohne Abruf
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_BASIS = "https://portal.deutsche-evergabe.de/Dashboards/Dashboard_off?BL="

# Amtlicher Bundesland-Schluessel. Genau die Kennung, die `auftraege.bayern.de` selbst
# benutzt — nicht geraten, sondern von der Landesseite abgelesen.
LAENDER = {
    "SH": ("01", "Schleswig-Holstein"),   "HH": ("02", "Hamburg"),
    "NI": ("03", "Niedersachsen"),        "HB": ("04", "Bremen"),
    "NW": ("05", "Nordrhein-Westfalen"),  "HE": ("06", "Hessen"),
    "RP": ("07", "Rheinland-Pfalz"),      "BW": ("08", "Baden-Württemberg"),
    "BY": ("09", "Bayern"),               "SL": ("10", "Saarland"),
    "BE": ("11", "Berlin"),               "BB": ("12", "Brandenburg"),
    "MV": ("13", "Mecklenburg-Vorpommern"), "SN": ("14", "Sachsen"),
    "ST": ("15", "Sachsen-Anhalt"),       "TH": ("16", "Thüringen"),
}

_WARTE_MS = 4500
_HOEFLICH_MS = 1200
_TROCKEN = 4          # so viele Runden ohne Neues gelten als ausgeschoepft
_MAX_RUNDEN = 40      # Notbremse; die Coupon-Collector-Schaetzung fuer BY liegt bei ~95

_ANZAHL = re.compile(r"Anzahl:\s*([\d.]+)")
_DATUM = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")

# Kopfzeile der Trefferliste (abgelesen 2026-08-14):
#   ["", "VORDN.", "TITEL", "VERGABESTELLE", "PUBLIKATION", "FRIST", ""]
# „VORDN." ist NICHT die Vorgangsnummer, sondern die **Verordnung** (VOB/VGV/UVgO/…).
_SPALTE = {"vordn": 1, "titel": 2, "stelle": 3, "pub": 4, "frist": 5}
_MIN_ZELLEN = 6

# Verordnung → das Vokabular, das `gold._lead_context_sql` ohnehin schon liest. Zwei
# Pfade, weil Gold sie unterschiedlich aufloest: Deutschlands eigene Vorschriften stehen
# unter `RegulatoryDomain`, die EU-nahen unter der Legislation-Referenz.
_REGIME_DOMAIN = {"VOB": "de-vob", "UVGO": "de-uvgo"}
_REGIME_LEGIS  = {"VGV": "vgv", "SEKTVO": "sektvo", "KON": "konzvgv", "VSVGV": "vsvgv"}
# `oVO` heisst „ohne Verordnung" und wird BEWUSST nicht abgebildet — es auf ein Regime zu
# zwingen waere geraten. Der Rohwert bleibt trotzdem in `attributes` stehen.

# NUTS-1 je Bundesland. Der eigentliche Gewinn dieser Quelle: sie traegt das Bundesland
# ausdruecklich, waehrend die unterschwellige Ebene sonst gar keine Landeszuordnung hat.
NUTS1 = {
    "BW": "DE1", "BY": "DE2", "BE": "DE3", "BB": "DE4", "HB": "DE5", "HH": "DE6",
    "HE": "DE7", "MV": "DE8", "NI": "DE9", "NW": "DEA", "RP": "DEB", "SL": "DEC",
    "SN": "DED", "ST": "DEE", "SH": "DEF", "TH": "DEG",
}


def schluessel(land: str, teile: list[str]) -> str:
    """Stabile Kennung. Die Liste traegt keine Vorgangs-ID, deshalb ein Hash über Land und
    Zellinhalte — dieselbe Loesung wie bei NetServer, und aus demselben Grund.

    Gehasht werden die ZELLEN, nicht die plattgemachte Zeile: sonst haenge der Schluessel
    an der Leerraum-Normalisierung des Browsers und aendere sich ohne Anlass.
    """
    return hashlib.sha1(("|".join([land] + teile)).encode("utf-8")).hexdigest()[:16]


def zerlege(zellen: list[str], land: str) -> dict | None:
    """Tabellenzellen → Satz. Gibt None, wenn die Zeile nicht wie ein Vorgang aussieht.

    **Warum Zellen und nicht der Zeilentext.** Bis 2026-08-14 las diese Datei
    ``tr.innerText`` und bekam damit Titel, Verfahrensart und Vergabestelle als EINEN
    String — zwischen ihnen steht nur Leerraum, kein Trennzeichen. Der damalige Docstring
    schloss daraus, die Trennung sei „nicht sicher moeglich", und liess das Feld
    ungetrennt stehen. Das war richtig geschlossen, aber aus einer selbstgemachten Lage:
    die Quelle ist eine HTML-**Tabelle** mit sauberen Spalten, und ``innerText`` auf der
    Zeile hat sie plattgemacht. Wer die Zellen einzeln liest, bekommt die Vergabestelle
    geschenkt — und ohne sie gaebe es keinen Kaeufer, also keinen brauchbaren Lead.

    Die Lehre steht hier und nicht im Commit: eine Quelle, die scheinbar zu wenig
    hergibt, ist zuerst ein Verdacht gegen den eigenen Abruf.
    """
    if len(zellen) < _MIN_ZELLEN:
        return None
    hole = lambda k: zellen[_SPALTE[k]].strip()          # noqa: E731
    titel, stelle = hole("titel"), hole("stelle")
    pub, frist = hole("pub"), hole("frist")
    # Beide Datumsspalten muessen wie Daten aussehen — sonst ist es eine Kopf-, Fuss-
    # oder Platzhalterzeile. Die Liste liefert davon reichlich (leere `<tr>`).
    if not titel or not _DATUM.match(pub) or not _DATUM.match(frist):
        return None
    teile = [hole("vordn"), titel, stelle, pub, frist]
    return {
        "quelle": "healyhudson",
        "format": 2,                  # 1 = plattgemachte Zeile (bis 2026-08-14), 2 = Zellen
        "land": land,
        "verordnung": hole("vordn"),
        "titel": titel,
        "vergabestelle": stelle,
        "pub": pub,
        "frist": frist,
        "schluessel": schluessel(land, teile),
        "erfasst_am": dt.date.today().isoformat(),
    }


def hole_land(kuerzel: str, pg, runden: int) -> dict:
    """Ein Bundesland → alle erreichbaren Vorgaenge. Wiederholt, bis nichts Neues kommt."""
    bl, name = LAENDER[kuerzel]
    url = _BASIS + bl
    saetze: dict[str, dict] = {}
    gemeldet = None
    leer = 0
    for runde in range(runden):
        pg.goto(url, wait_until="domcontentloaded")
        pg.wait_for_timeout(_WARTE_MS)
        text = pg.evaluate("() => document.body.innerText")
        if gemeldet is None:
            m = _ANZAHL.search(text)
            gemeldet = int(m.group(1).replace(".", "")) if m else 0
        zeilen = pg.evaluate(
            """() => [...document.querySelectorAll('tr')].slice(1)
                 .map(r => [...r.querySelectorAll('td')]
                             .map(c => c.innerText.replace(/\\s+/g, ' ').trim()))
                 .filter(z => z.length > 1)""")
        neu = 0
        for z in zeilen:
            s = zerlege(z, kuerzel)
            if s and s["schluessel"] not in saetze:
                saetze[s["schluessel"]] = s
                neu += 1
        leer = leer + 1 if neu == 0 else 0
        if leer >= _TROCKEN:
            break
        pg.wait_for_timeout(_HOEFLICH_MS)
    return {"land": kuerzel, "name": name, "gemeldet": gemeldet or 0,
            "geholt": len(saetze), "runden": runde + 1, "saetze": list(saetze.values())}


def lauf(kuerzel: list[str], runden: int, dry_run: bool) -> dict:
    from playwright.sync_api import sync_playwright

    ergebnisse = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context()
        pg = ctx.new_page()
        pg.set_default_timeout(45000)
        for k in kuerzel:
            r = hole_land(k, pg, runden)
            quote = f"{100 * r['geholt'] / r['gemeldet']:.0f}%" if r["gemeldet"] else "—"
            marke = "" if r["geholt"] >= r["gemeldet"] else "  ⚠ unvollständig"
            print(f"  {k}  {r['name']:<24} {r['geholt']:>4} von {r['gemeldet']:>4} "
                  f"({quote:>4}) in {r['runden']} Runden{marke}", flush=True)
            ergebnisse.append(r)
        ctx.close()
        b.close()

    alle = [s for r in ergebnisse for s in r["saetze"]]
    ges_gem = sum(r["gemeldet"] for r in ergebnisse)
    print(f"\nHealy Hudson: {len(alle)} Vorgänge von {ges_gem} gemeldeten "
          f"({100 * len(alle) / ges_gem:.0f} %)" if ges_gem else "\nnichts geholt.")
    # KEIN stilles Abschneiden: was fehlt, wird benannt.
    fehlt = [r for r in ergebnisse if r["geholt"] < r["gemeldet"]]
    if fehlt:
        print("  unvollständig: " + ", ".join(
            f"{r['land']} ({r['gemeldet'] - r['geholt']} offen)" for r in fehlt))
        print("  → mehr Runden helfen; die Liste würfelt je Abruf neu.")

    if dry_run:
        for s in alle[:3]:
            print("   ", json.dumps(s, ensure_ascii=False)[:170])
        return {"geholt": len(alle), "gemeldet": ges_gem}

    out = ROOT / "data" / "raw_healyhudson"
    out.mkdir(parents=True, exist_ok=True)
    ziel = out / f"{dt.date.today():%Y-%m}.jsonl"
    # Anhaengen und beim Lesen deduplizieren — wie die anderen Bronze-Ablagen. Der
    # Schluessel ist stabil, doppelte Zeilen fallen spaeter auf.
    bekannt = set()
    if ziel.exists():
        for line in ziel.open(encoding="utf-8"):
            try:
                bekannt.add(json.loads(line)["schluessel"])
            except Exception:                            # noqa: BLE001
                pass
    frisch = [s for s in alle if s["schluessel"] not in bekannt]
    with ziel.open("a", encoding="utf-8") as fh:
        for s in frisch:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"→ {ziel}  ({len(frisch)} neu, {len(alle) - len(frisch)} bereits bekannt)")
    return {"geholt": len(alle), "neu": len(frisch), "gemeldet": ges_gem}



# --------------------------------------------------------------------------------- Silber

def _datum(d: str):
    """`TT.MM.JJJJ` → date. None statt Ausnahme: eine unlesbare Zelle darf den Lauf nicht
    abbrechen, sie darf nur diesen einen Wert kosten."""
    try:
        return dt.datetime.strptime(d.strip(), "%d.%m.%Y").date()
    except Exception:                                     # noqa: BLE001
        return None


def _regime_zeilen(nid: str, verordnung: str) -> list[dict]:
    """Verordnung → `attributes`-Zeilen im Vokabular, das Gold schon liest.

    Der Rohwert wird IMMER mitgeschrieben, auch wenn er sich nicht abbilden laesst
    (`oVO`). Sonst waere die Zuordnung eine Einbahnstrasse und niemand koennte spaeter
    nachsehen, was die Quelle wirklich gesagt hat.
    """
    v = (verordnung or "").strip()
    zeilen = [{"notice_id": nid, "path": "HealyHudson.Vordn", "value": v}] if v else []
    key = v.upper()
    if key in _REGIME_DOMAIN:
        zeilen.append({"notice_id": nid, "path": "ContractNotice.RegulatoryDomain",
                       "value": _REGIME_DOMAIN[key]})
    elif key in _REGIME_LEGIS:
        zeilen.append({"notice_id": nid,
                       "path": "ContractNotice.TenderingTerms.ProcurementLegislation"
                               "DocumentReference.ID",
                       "value": _REGIME_LEGIS[key]})
    return zeilen


def nach_silber(satz: dict, laender: list[str] | None = None) -> dict[str, list[dict]] | None:
    r"""Ein Bronze-Satz → {tabelle: [zeilen]} im Silber-Schema. None bei Alt-Format.

    **Der Namensraum.** `notice_id` bekommt das Praefix `hh_`. TED-IDs sind `\d+_\d{4}`,
    DÖE nutzt UUIDs und reine Zahlen — ein Hash ohne Praefix koennte mit beiden kollidieren,
    und eine Kollision im Notice-Namensraum ist kein Anzeigefehler, sondern verschmolzene
    Vergaben. Das Praefix macht die Herkunft ausserdem im Rohwert lesbar.

    **Kein CPV.** Die Liste fuehrt keinen. Diese Leads landen deshalb in „Ohne Kategorie" —
    und genau dafuer gibt es seit heute die Kategorie-Wasserfall in `kategorie.py`, die aus
    dem Titel ableitet. Erfundene CPV-Codes waeren die schlechtere Antwort.

    **Mehrere Bundeslaender = bundesweit.** Die Quelle liefert je Land eine eigene Liste,
    bundesweite Vergabestellen (BVVG, Max-Planck, EWN) stehen deshalb in mehreren. Gemessen
    2026-08-14: 101 von 777 Saetzen. Ohne Zusammenfassung waere dieselbe Vergabe bis zu
    viermal ein Lead — und die Dubletten-Firewall faengt es NICHT, weil sie Paare derselben
    Schema-Generation ueberspringt (die Regel, die Geschwister-Lose entschaerft).

    Statt eines neuen Begriffs wird die vorhandene Konvention bedient: `RealizedLocation.
    Address.Region = anyw-cou` ist im Projekt bereits „an keinen Ort gebunden" und speist
    `is_nationwide` — damit greifen Umkreis- und Regionssuche ohne eine Zeile Anpassung.
    `performance_nuts` bleibt dann leer: ein Bundesland zu waehlen waere geraten.
    """
    if satz.get("format") != 2:          # Alt-Format ohne getrennte Spalten
        return None
    nid = f"hh_{satz['schluessel']}"
    pub, frist = _datum(satz.get("pub", "")), _datum(satz.get("frist", ""))
    laender = sorted(set(laender or [satz.get("land") or ""]) - {""})
    nuts = NUTS1.get(laender[0]) if len(laender) == 1 else None
    titel = (satz.get("titel") or "").strip()

    notice = {
        "notice_id": nid,
        "publication_date": pub,
        "country": "DE", "buyer_countries": ["DE"],
        "year": pub.year if pub else None,
        "month": pub.month if pub else None,
        "schema_gen": "healyhudson",
        # ⚠ Leere Listen, nicht NULL — s. `atverg.py`. Ohne sie stehen diese Saetze mit
        # `flags IS NULL` in Silber, und `len(NULL) > 0` schliesst sie lautlos aus jeder
        # Zaehlung aus, statt sie mit null Marken zu zeigen.
        "flags": [], "unknown_country_codes": [],
        "notice_kind": "cn",             # offene Ausschreibung mit Frist, kein Zuschlag
        "language": "de",   # ISO-639-1 klein — `languages.normalize`, nicht "DE"
        "title": titel,
        "submission_deadline": frist,
        # Der eigentliche Gewinn: das Bundesland steht ausdruecklich in der Quelle.
        "performance_nuts": nuts,
        "text_chars": len(titel),
        # KEIN portal_url: die Trefferzeilen tragen nachweislich keinen Link (geprueft
        # 2026-08-14, `a[href]` je Zeile leer). Eine geratene URL waere schlimmer als keine.
    }
    tabellen: dict[str, list[dict]] = {"notices": [notice]}

    stelle = (satz.get("vergabestelle") or "").strip()
    if stelle:
        tabellen["notice_parties"] = [{
            "notice_id": nid, "role": "buyer", "seq": 0,
            "name": stelle, "country": "DE", "nuts": nuts,
        }]
    attr = _regime_zeilen(nid, satz.get("verordnung", ""))
    if len(laender) > 1:
        attr.append({"notice_id": nid,
                     "path": "ContractNotice.ProcurementProject.RealizedLocation"
                             ".Address.Region", "value": "anyw-cou"})
        # Welche Laender es waren, bleibt nachlesbar — sonst waere „bundesweit" eine
        # Behauptung ohne Beleg.
        attr.append({"notice_id": nid, "path": "HealyHudson.Bundeslaender",
                     "value": ",".join(laender)})
    elif laender:
        attr.append({"notice_id": nid, "path": "HealyHudson.Bundesland",
                     "value": laender[0]})
    if attr:
        tabellen["attributes"] = attr
    return tabellen


def build_silber(country: str = "DE") -> dict:
    """Bronze-JSONL → Silber-Parquet (hive: `silver/DE/<tabelle>/year=JJJJ/JJJJ-healyhudson.parquet`).

    Dedup je `notice_id` ueber ALLE Monatsdateien (der spaetere Satz gewinnt) — die Liste
    wuerfelt je Abruf, derselbe Vorgang taucht deshalb ueber Tage wieder auf.

    Schreibt in dieselbe geteilte Ablage wie TED und DÖE. Die Dateinamen tragen
    `-healyhudson`, damit ein erneuter Lauf nur die eigenen Dateien ersetzt und nie fremde.
    """
    from collections import defaultdict

    import pyarrow as pa
    import pyarrow.parquet as pq

    from . import model

    quelle = ROOT / "data" / "raw_healyhudson"
    dateien = sorted(quelle.glob("*.jsonl"))
    if not dateien:
        print("healyhudson Silber: kein Bronze gefunden.")
        return {"notices": 0, "alt_format": 0}

    # Erst nach INHALT gruppieren, dann abbilden. Der Bronze-Schluessel traegt das
    # Bundesland — dieselbe bundesweite Vergabe hat deshalb bis zu sechzehn verschiedene
    # Schluessel. Wer je Schluessel abbildet, baut sie sechzehnmal.
    inhalte: dict[tuple, dict] = {}
    laender_je: dict[tuple, set[str]] = {}
    alt = gelesen = 0
    for f in dateien:
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                satz = json.loads(line)
            except Exception:                             # noqa: BLE001
                continue
            gelesen += 1
            if satz.get("format") != 2:
                alt += 1
                continue
            k = (satz.get("verordnung"), satz.get("titel"), satz.get("vergabestelle"),
                 satz.get("pub"), satz.get("frist"))
            # Der zuerst gesehene Satz gewinnt — nur sein `schluessel` wird zur notice_id.
            # Sortierte Dateiliste + sortierte Laender machen das reproduzierbar.
            inhalte.setdefault(k, satz)
            laender_je.setdefault(k, set()).add(satz.get("land") or "")

    je_id: dict[str, dict[str, list[dict]]] = {}
    mehrfach = 0
    for k, satz in inhalte.items():
        lg = sorted(laender_je[k] - {""})
        if len(lg) > 1:
            mehrfach += 1
        t = nach_silber(satz, lg)
        if t is None:
            continue
        je_id[t["notices"][0]["notice_id"]] = t

    eimer: dict[str, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
    ohne_jahr = 0
    for t in je_id.values():
        jahr = t["notices"][0].get("year")
        if not jahr:
            ohne_jahr += 1
            continue          # ohne Publikationsdatum keine hive-Partition — s. Bericht
        for tabelle, zeilen in t.items():
            eimer[tabelle][jahr].extend(zeilen)

    ziel = ROOT / "data" / "silver" / country
    for tabelle, je_jahr in eimer.items():
        schema = model.TABLES[tabelle]
        for jahr, zeilen in je_jahr.items():
            out = ziel / tabelle / f"year={jahr}" / f"{jahr}-healyhudson.parquet"
            out.parent.mkdir(parents=True, exist_ok=True)
            arrow = pa.Table.from_pylist(zeilen, schema=schema)
            tmp = out.with_suffix(".part")
            pq.write_table(arrow, tmp, compression="zstd")
            tmp.replace(out)

    n = sum(len(v) for v in eimer.get("notices", {}).values())
    print(f"healyhudson Silber: {n} Notices → {len(eimer)} Tabellen "
          f"({gelesen} Bronze-Zeilen gelesen)")
    if mehrfach:
        print(f"  {mehrfach} Vergaben standen in mehreren Bundeslaendern → als bundesweit "
              f"zusammengefasst (sonst waeren sie mehrfach Lead geworden)")
    # Was NICHT durchkam, wird benannt statt verschwiegen.
    if alt:
        print(f"  ⚠ {alt} Zeilen im Alt-Format (ohne getrennte Spalten) uebersprungen — "
              f"sie tragen keine Vergabestelle. Neu holen: --alle")
    if ohne_jahr:
        print(f"  ⚠ {ohne_jahr} ohne lesbares Publikationsdatum uebersprungen.")
    return {"notices": n, "alt_format": alt, "ohne_jahr": ohne_jahr}

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--laender", default="", help="Kürzel, z. B. BY,HH,NW")
    p.add_argument("--alle", action="store_true", help="alle sechzehn")
    p.add_argument("--runden", type=int, default=10,
                   help=f"Abrufe je Land (max {_MAX_RUNDEN}); die Liste würfelt je Abruf")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--silber", action="store_true",
                   help="Bronze → Silber (ohne Abruf, wenn --laender/--alle fehlen)")
    a = p.parse_args(argv)
    if a.silber and not (a.alle or a.laender):
        build_silber()
        return 0
    if a.alle:
        k = list(LAENDER)
    else:
        k = [x.strip().upper() for x in a.laender.split(",") if x.strip()]
    unbekannt = [x for x in k if x not in LAENDER]
    if unbekannt:
        p.error(f"unbekannte Länderkürzel: {unbekannt}. Erlaubt: {', '.join(LAENDER)}")
    if not k:
        p.error("--laender oder --alle angeben")
    lauf(k, min(a.runden, _MAX_RUNDEN), a.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
