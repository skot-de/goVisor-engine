"""Quelle DE — NetServer (Administration Intelligence) Bekanntmachungs-Downloader.

**Warum diese Quelle.** Fünf Bundesländer fahren dieselbe Software: Bremen,
Mecklenburg-Vorpommern, Sachsen, Baden-Württemberg (LandBW) und Hessen (HAD). Sie führen
ober- UND unterschwellige Vergaben; über TED kommen nur die oberschwelligen, über DÖE nur
ein Teil. Gemessen 2026-08-14 an je 25 Vorgängen der öffentlichen Trefferliste:

    Sachsen   23 von 25 fehlten im Bestand (92 %)      6 unterschwellig
    LandBW    14 von 25 (56 %)                        15 unterschwellig (60 %)
    MV         7 von 25 (28 %)                        23 unterschwellig (92 %)
    Bremen     6 von 25 (24 %)                        18 unterschwellig (72 %)

**Die entscheidende Unterscheidung: Liste öffentlich, Detail nicht.** Die Trefferliste
liefert Titel, Verfahrensart, Rechtsrahmen und Abgabefrist ohne jede Anmeldung. Der Klick
auf einen Vorgang führt dagegen auf ``LoginControllerServlet?function=LoginForm`` — in der
Bremer Liste ist das der einzige vorhandene Klick-Handler, Datei-Links gibt es null.

Daraus folgt der Zuschnitt dieses Moduls: **es holt Bekanntmachungen, keine Unterlagen.**
Ein früherer Anlauf im Projekt hat aus der Zugänglichkeit einer Schicht auf eine andere
geschlossen und lag falsch (s. `scripts/probe_portals.py`); hier steht die Grenze deshalb
im Modulkopf und nicht in einer Fussnote. Wer später Unterlagen will, braucht eine
Registrierung — das ist eine Vertrags-, keine Technikfrage.

**Kein Browser nötig.** Anders als bei DTVP ist die Trefferliste serverseitig gerendert;
``curl``/``requests`` genügt. Playwright wäre hier reine Kosten.

⚠ **Die Instanzen sind unterschiedlich geskinnt.** Bremen liefert fünf schlichte ``<td>``
(Datum · Titel · Verfahrensart · Rechtsrahmen · Frist), Sachsen eine Definitionsliste mit
Titel, Beschreibung, Auftraggeber und Fundstelle. Der Parser ist deshalb **feldsuchend statt
spaltenzählend**: er liest alle Zellen einer Zeile und ordnet sie über Muster zu. Ein
spaltenbasierter Parser hätte an der zweiten Instanz gebrochen.

⚠ **Es gibt keine portalseitige Vorgangs-ID.** Weder Bremen noch Sachsen tragen in der
Trefferzeile einen Link mit Kennung — nur Sortier- und Blätter-Links. Der Schlüssel wird
deshalb aus dem Inhalt gebildet (`sha1` über Portal + Veröffentlichung + Titel). Folge, die
man kennen muss: **korrigiert eine Vergabestelle den Titel, entsteht ein zweiter Satz.**
Die Dubletten-Firewall fängt das ab, aber es ist eine echte Grenze und kein Detail. Wo eine
Vergabenummer im Titel steht (`(V0471/2026)`, `(7A032308)`), wird sie zusätzlich als
Attribut mitgeführt — sie ist der stabilere Schlüssel, wenn er denn da ist.

Aufruf::

    python3 -m govisor.netserver --portale hb,sn,mv,bw --kategorien tender
    python3 -m govisor.netserver --silber
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36")

# Kürzel → (Land, Basis-URL). Bewusst eine Tabelle: eine weitere NetServer-Instanz ist
# eine Zeile, kein Codepfad. Hessen/HAD ist eingetragen, aber der Suchendpunkt antwortet
# unter dem üblichen Servlet-Namen mit 404 — deshalb `None` und ein offener Punkt.
PORTALE: dict[str, tuple[str, str | None]] = {
    "hb": ("Bremen", "https://vergabe.bremen.de/NetServer/"),
    "sn": ("Sachsen", "https://www.sachsen-vergabe.de/NetServer/"),
    "mv": ("Mecklenburg-Vorpommern", "https://vergabe.mv-regierung.de/NetServer/"),
    "bw": ("Baden-Württemberg", "https://vergabe.landbw.de/NetServer/"),
    "he": ("Hessen (HAD)", None),          # Suchendpunkt offen, s. Modulkopf
}

# NetServer-Kategorien → unser `notice_kind`.
KATEGORIEN = {
    "tender": ("InvitationToTender", "cn"),
    "vorinfo": ("PriorInformation", "pin"),
    "zuschlag": ("ContractAward", "can"),
}

_SERVLET = "PublicationSearchControllerServlet?function=SearchPublications"
_HOEFLICH_S = 2.0          # Pause zwischen Abrufen — fremdes System

_RECHTSRAHMEN = re.compile(r'\b(VOB|UVgO|VgV|VOL(?:/VgV)?|SektVO|KonzVgV|VSVgV)\b', re.I)
_VERFAHRENSART = re.compile(
    r'(Offenes Verfahren|Nicht ?offenes Verfahren|Beschränkte Ausschreibung|'
    r'Öffentliche Ausschreibung|Freihändige Vergabe|Verhandlungsverfahren[^,;]{0,40}|'
    r'Verhandlungsvergabe|Teilnahmewettbewerb)', re.I)
_DATUM = re.compile(r'\b(\d{2}\.\d{2}\.\d{4})\b')
_FRIST = re.compile(r'\b(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})')
# Reiner Datums-/Zeitstempel — nie ein Titel (s. Verdopplungs-Falle in `zeilen_lesen`).
_NUR_DATUM = re.compile(r'\s*\d{2}\.\d{2}\.\d{4}(?:\s+\d{2}:\d{2})?\s*')
_VERGABENR = re.compile(r'\(([A-Za-z0-9][A-Za-z0-9._/\-]{4,30})\)\s*$')
# Verfahren, die per Vorschrift unterschwellig sind bzw. es typischerweise anzeigen.
_UNTERSCHWELLIG = re.compile(r'UVgO|Freihändige|Beschränkte Ausschreibung|Verhandlungsvergabe', re.I)


def _txt(x: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()


def _datum(s: str | None):
    try:
        return dt.datetime.strptime((s or "").strip(), "%d.%m.%Y").date()
    except (ValueError, AttributeError):
        return None


def _frist(s: str | None):
    m = _FRIST.search(s or "")
    if not m:
        return None
    try:
        return dt.datetime.strptime(f"{m.group(1)} {m.group(2)}", "%d.%m.%Y %H:%M")
    except ValueError:
        return None


def hol(url: str, timeout: int = 40) -> str:
    """Über ``curl``, NICHT ``urllib``.

    In dieser Umgebung scheitert `urllib` an einem TLS-Proxy und meldet für **jedes** Portal
    denselben Fehler. Genau daraus wurde im Projekt schon einmal ein Portalbefund abgeleitet
    („14 von 14 Plattformen …"), der keiner war. curl kommt durch.
    """
    r = subprocess.run(["curl", "-sL", "--max-time", str(timeout), "-A", UA, url],
                       capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"curl exit {r.returncode} für {url}")
    return r.stdout.decode("utf-8", "replace")


def _spalten(seite: str) -> dict[str, int]:
    """Kopfzeile → {Spaltenname: Index}, sofern die Instanz eine führt.

    Nötig, weil die Vergabestelle je Skin anders auftaucht: MV und Baden-Württemberg
    führen eine **Spalte „Vergabestelle"**, Sachsen ein Feld „Auftraggeber:" in einer
    Definitionsliste, Bremen gar nichts. Ein rein musterbasierter Parser fand deshalb nur
    Sachsen und liess 68 Auftraggeber liegen — die dann am `JOIN buyer` des Lead-Baus
    lautlos ausgefallen wären.
    """
    kopf = re.search(r"<tr[^>]*>((?:(?!</tr>).)*?<th.*?)</tr>", seite, re.S | re.I)
    if not kopf:
        return {}
    namen = [_txt(t) for t in re.findall(r"<th[^>]*>(.*?)</th>", kopf.group(1), re.S | re.I)]
    return {n.lower(): i for i, n in enumerate(namen) if n}


def zeilen_lesen(seite: str) -> list[dict]:
    """Trefferzeilen feldsuchend auslesen — unabhängig von Spaltenzahl und Skin.

    Gibt je Zeile die erkannten Felder zurück. Nicht erkannte Felder bleiben leer; sie
    werden NICHT geraten. Eine Zeile ohne Titel gilt nicht als Vorgang.
    """
    aus: list[dict] = []
    spalten = _spalten(seite)
    # Spaltenindex der Vergabestelle, wo die Instanz eine Kopfzeile führt.
    i_stelle = next((i for n, i in spalten.items()
                     if "vergabestelle" in n or "auftraggeber" in n), None)
    for roh in re.findall(r"<tr[^>]*>(.*?)</tr>", seite, re.S | re.I):
        if "<td" not in roh.lower():
            continue
        zellen = [_txt(z) for z in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", roh, re.S | re.I)]
        zellen = [z for z in zellen if z]
        if not zellen:
            continue
        ganz = " · ".join(zellen)
        # Titel = längste Zelle, die nicht nur Datum/Verfahrensart ist. Bei Sachsen steht
        # der Titel im <strong>, deshalb der Vorzug für dessen Inhalt, wenn vorhanden.
        stark = [_txt(m) for m in re.findall(r"<strong[^>]*>(.*?)</strong>", roh, re.S | re.I)]
        stark = [s for s in stark if len(s) > 12]
        kandidaten = stark or [z for z in zellen if len(z) > 12 and not _DATUM.fullmatch(z)]
        if not kandidaten:
            continue
        titel = max(kandidaten, key=len)
        # Ein Datum/Zeitstempel ist kein Titel. Die Tabellen rendern jeden Vorgang ZWEIMAL —
        # einmal vollständig, einmal als reine Fristzeile („11.09.2026 10:00"). Die
        # Längenschwelle allein liess den Zeitstempel als Titel durch und verdoppelte damit
        # den Bestand: Bremen meldete 82 statt 41 Vorgänge.
        if (_VERFAHRENSART.fullmatch(titel) or len(titel) < 12
                or _NUR_DATUM.fullmatch(titel)):
            continue

        # Vergabestelle auf drei Wegen, in dieser Reihenfolge:
        #   1. Spalte laut Kopfzeile (MV, Baden-Württemberg)
        #   2. Feld „Auftraggeber:" in der Definitionsliste (Sachsen)
        #   3. gar nicht (Bremen führt sie nicht) — dann NULL, nicht geraten
        auftraggeber = None
        if i_stelle is not None and i_stelle < len(zellen):
            kand = zellen[i_stelle]
            # Nicht die Titelzelle und kein Datum/Verfahrensart erwischen.
            if (kand and kand != titel and not _NUR_DATUM.fullmatch(kand)
                    and not _VERFAHRENSART.fullmatch(kand) and len(kand) > 2):
                auftraggeber = kand
        if not auftraggeber:
            m_ag = re.search(r"Auftraggeber:?\s*(?:</dt>\s*<dd[^>]*>)?\s*([^<·]{3,80})", roh, re.I)
            auftraggeber = _txt(m_ag.group(1)) if m_ag else None

        daten = _DATUM.findall(ganz)
        frist = _frist(ganz)
        # Veröffentlichung = das früheste Datum, das NICHT die Frist ist.
        #
        # KEIN Rückfall auf „irgendein Datum": Sachsen führt in der Trefferliste gar kein
        # Veröffentlichungsdatum, nur die Abgabefrist. Ein Rückfall setzte dann die Frist
        # als Veröffentlichung — gemessen an allen 202 Zeilen, und das verschöbe Jahr/Monat
        # der Notice und damit den Marktpuls. Lieber NULL als ein falsches Datum.
        pub = None
        for d in daten:
            k = _datum(d)
            if k and (not frist or k != frist.date()):
                pub = k if pub is None or k < pub else pub

        m_rr = _RECHTSRAHMEN.search(ganz)
        m_va = _VERFAHRENSART.search(ganz)
        m_nr = _VERGABENR.search(titel)
        # Eine echte Trefferzeile trägt mindestens EIN hartes Vergabemerkmal. Ohne diese
        # Hürde zählen verschachtelte Layout-Tabellen als Vorgänge mit: bei Sachsen ergaben
        # sich so 202 „Zeilen", von denen nur 50 einen Rechtsrahmen hatten.
        if not (frist or m_rr):
            continue
        aus.append({
            "titel": titel,
            "auftraggeber": auftraggeber,
            "pub": pub.isoformat() if pub else None,
            "frist": frist.isoformat() if frist else None,
            "rechtsrahmen": m_rr.group(1).upper() if m_rr else None,
            "verfahrensart": m_va.group(1) if m_va else None,
            "vergabenummer": m_nr.group(1) if m_nr else None,
            "unterschwellig": bool(_UNTERSCHWELLIG.search(ganz)),
        })
    return aus


def schluessel(portal: str, satz: dict) -> str:
    """Inhaltsschlüssel — es gibt keine portalseitige ID (s. Modulkopf).

    Bewusst über Portal + Veröffentlichung + Titel und NICHT über die Frist: eine
    Fristverlängerung ist derselbe Vorgang und darf keinen zweiten Satz erzeugen.
    """
    roh = f"{portal}|{satz.get('pub') or ''}|{(satz.get('titel') or '').lower()}"
    return hashlib.sha1(roh.encode("utf-8")).hexdigest()[:16]


def hole(portale: list[str], kategorien: list[str], bekannt: set[str]) -> list[dict]:
    saetze: list[dict] = []
    for kuerzel in portale:
        land, basis = PORTALE.get(kuerzel, (kuerzel, None))
        if not basis:
            print(f"  {kuerzel}: kein Suchendpunkt hinterlegt — übersprungen", flush=True)
            continue
        for kat in kategorien:
            cat, _kind = KATEGORIEN[kat]
            url = f"{basis}{_SERVLET}&Gesetzesgrundlage=All&Category={cat}"
            try:
                seite = hol(url)
            except Exception as e:                       # noqa: BLE001
                print(f"  {kuerzel}/{kat}: nicht erreichbar ({type(e).__name__})", flush=True)
                continue
            zeilen = zeilen_lesen(seite)
            neu = 0
            heute = dt.date.today().isoformat()
            for z in zeilen:
                z["portal"], z["land"], z["kategorie"] = kuerzel, land, kat
                # Wann WIR die Zeile gesehen haben. Nötig, weil Sachsen in der Trefferliste
                # gar kein Veröffentlichungsdatum führt (gemessen: 0 von 50). Das ist eine
                # Tatsache über uns, kein erfundenes Quellendatum — und es hält die Sätze
                # aus der `year=0`-Partition, ohne ein Datum zu behaupten.
                z["erfasst_am"] = heute
                z["key"] = schluessel(kuerzel, z)
                if z["key"] in bekannt:
                    continue
                bekannt.add(z["key"])
                saetze.append(z)
                neu += 1
            unter = sum(1 for z in zeilen if z["unterschwellig"])
            print(f"  {kuerzel}/{kat}: {len(zeilen)} Zeilen, {neu} neu, "
                  f"{unter} unterschwellig", flush=True)
            time.sleep(_HOEFLICH_S)
    return saetze


def schreibe_bronze(saetze: list[dict], country: str = "DE") -> dict:
    """Nach Monat gebündelt als JSONL, dedupliziert über `key`. Idempotent.

    Verlustfreiheit liegt wie bei TED/DÖE/simap/DTVP in Bronze: ein Parser-Fix kostet einen
    Re-Run über lokale Dateien, keinen erneuten Abruf beim Portal.
    """
    root = ROOT / "data" / "raw_netserver" / country
    root.mkdir(parents=True, exist_ok=True)
    nach_monat: dict[str, list[dict]] = {}
    for s in saetze:
        # Ohne Veröffentlichungsdatum nach Erfassungsmonat ablegen — die Datei bleibt so
        # auffindbar und der Re-Run idempotent.
        monat = (s.get("pub") or s.get("erfasst_am") or "")[:7] or "unbekannt"
        nach_monat.setdefault(monat, []).append(s)
    stat: dict[str, tuple[int, int]] = {}
    for monat, neue in nach_monat.items():
        pfad = root / f"{monat}.jsonl"
        vorhanden: dict[str, dict] = {}
        if pfad.exists():
            for zeile in pfad.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(zeile)
                    vorhanden[r["key"]] = r
                except (json.JSONDecodeError, KeyError):
                    continue
        vor = len(vorhanden)
        for r in neue:
            vorhanden[r["key"]] = r
        pfad.write_text("\n".join(json.dumps(r, ensure_ascii=False)
                                  for r in vorhanden.values()) + "\n", encoding="utf-8")
        stat[monat] = (len(vorhanden) - vor, len(vorhanden))
    return stat


def bekannte_keys(country: str = "DE") -> set[str]:
    root = ROOT / "data" / "raw_netserver" / country
    aus: set[str] = set()
    if not root.exists():
        return aus
    for f in root.glob("*.jsonl"):
        for zeile in f.read_text(encoding="utf-8").splitlines():
            m = re.search(r'"key":\s*"([0-9a-f]+)"', zeile)
            if m:
                aus.add(m.group(1))
    return aus


# ── Bronze → Silber ───────────────────────────────────────────────────────────────────────
#
# Dieselbe CPV-Frage wie bei DTVP, dieselbe Antwort: **VOB/A ist per Definition die Vergabe-
# und Vertragsordnung für BAULEISTUNGEN**, also CPV-Division 45 — das ist keine Vermutung,
# sondern der Geltungsbereich der Vorschrift. Für VOL/UVgO/VgV gibt es keine solche
# Ableitung (kann IT, Reinigung, Beratung, Medizintechnik sein), dort bleibt `cpv_main`
# NULL. Eine erfundene Branche wäre schlimmer als eine fehlende.
_CPV_AUS_REGELWERK = {"VOB": "45000000-7"}
_NATUR = {"VOB": "works"}


def nach_silber(country: str = "DE") -> dict:
    """Bronze-JSONL → Silber-Parquet (notices, notice_parties, attributes).

    `notice_id` ist ``ns:<portal>:<key>`` — der Präfix hält den Namensraum von TED-IDs
    getrennt (dieselbe Konvention wie DÖE und DTVP).
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    roh_dir = ROOT / "data" / "raw_netserver" / country
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
        nid = f"ns:{r['portal']}:{r['key']}"
        pub = dt.date.fromisoformat(r["pub"]) if r.get("pub") else None
        # `publication_date` bleibt NULL, wenn die Quelle keins führt — kein erfundenes
        # Datum. Für year/month tritt ersatzweise das Erfassungsdatum ein: sonst landen
        # alle sächsischen Sätze in `year=0` und fallen aus jeder Zeitreihe. Die Herkunft
        # steht als Attribut daneben, damit die gröbere Angabe sichtbar bleibt.
        platz = pub or (dt.date.fromisoformat(r["erfasst_am"]) if r.get("erfasst_am") else None)
        frist = dt.datetime.fromisoformat(r["frist"]) if r.get("frist") else None
        rr = (r.get("rechtsrahmen") or "").upper()
        # „VOL/VGV" trägt beide; für die CPV-Ableitung zählt nur reines VOB.
        cpv = _CPV_AUS_REGELWERK.get(rr)
        _, kind = KATEGORIEN.get(r.get("kategorie", "tender"), ("", "cn"))
        notices.append({
            "notice_id": nid, "publication_number": r["key"], "oj_ref": None,
            "publication_date": pub, "ted_url": None, "country": country,
            "buyer_countries": [country],
            "year": platz.year if platz else None, "month": platz.month if platz else None,
            "schema_gen": "netserver", "form_type": r.get("verfahrensart"),
            "notice_kind": kind,
            "language": "de",                       # kleingeschrieben — Guard-Konvention
            "title": r.get("titel"), "description": None, "description_field": None,
            "cpv_main": cpv, "performance_nuts": None,
            "contract_nature": _NATUR.get(rr),
            "procedure_type": r.get("verfahrensart"),
            "submission_deadline": frist,
            "portal_url": PORTALE.get(r["portal"], ("", None))[1],
            "estimated_value": None, "final_value": None, "value_currency": None,
            "award_date": None, "start_date": None, "end_date": None,
            "lot_count": None, "text_chars": len(r.get("titel") or ""),
            "ref_publication_number": None, "ref_ted_url": None,
            "flags": [], "unknown_country_codes": [],
        })
        if r.get("auftraggeber"):
            parties.append({
                "notice_id": nid, "role": "buyer", "seq": 0, "name": r["auftraggeber"],
                "national_id": None, "town": None, "postal_code": None, "country": country,
                "nuts": None, "email": None, "phone": None, "contact_person": None,
                "url": None, "is_sme": None, "in_consortium": None,
                "year": platz.year if platz else None,
            })
        attrs.append({"notice_id": nid, "path": "netserver/portal", "value": r["portal"]})
        if r.get("erfasst_am"):
            attrs.append({"notice_id": nid, "path": "netserver/erfasst_am",
                          "value": r["erfasst_am"]})
        if not pub:
            attrs.append({"notice_id": nid, "path": "netserver/zeitpunkt_aus_erfassung",
                          "value": "Quelle führt kein Veröffentlichungsdatum"})
        attrs.append({"notice_id": nid, "path": "netserver/land", "value": r.get("land")})
        if rr:
            attrs.append({"notice_id": nid, "path": "netserver/rechtsrahmen", "value": rr})
        if r.get("vergabenummer"):
            # Der stabilere Schlüssel, wo er existiert — für spätere Dubletten-Prüfung.
            attrs.append({"notice_id": nid, "path": "netserver/vergabenummer",
                          "value": r["vergabenummer"]})
        if r.get("unterschwellig"):
            attrs.append({"notice_id": nid, "path": "netserver/unterschwellig", "value": "ja"})
        if cpv:
            attrs.append({"notice_id": nid, "path": "netserver/cpv_hergeleitet",
                          "value": f"aus Regelwerk {rr}"})

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
            pq.write_table(pa.Table.from_pylist(gruppe), d / f"{jahr}-netserver.parquet",
                           compression="zstd")
            n += len(gruppe)
        stat[name] = n
    ohne_cpv = sum(1 for x in notices if not x["cpv_main"])
    unter = sum(1 for r in saetze if r.get("unterschwellig"))
    print(f"NetServer Silber {country}: " + " · ".join(f"{k} {v:,}" for k, v in stat.items()))
    print(f"  cpv_main aus Regelwerk hergeleitet: {len(notices)-ohne_cpv:,} (VOB/A = Bauleistung)")
    print(f"  ohne CPV (VOL/UVgO/VgV, bewusst NULL): {ohne_cpv:,}")
    print(f"  als unterschwellig erkannt:          {unter:,}")
    return stat


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--portale", default="hb,sn,mv,bw",
                   help="Kürzel, Komma-getrennt: " + ", ".join(PORTALE))
    p.add_argument("--kategorien", default="tender",
                   help="tender (Ausschreibung) · vorinfo · zuschlag")
    p.add_argument("--silber", action="store_true", help="nur Bronze → Silber, kein Abruf")
    p.add_argument("--dry-run", action="store_true", help="abrufen, nichts schreiben")
    a = p.parse_args(argv)

    if a.silber:
        nach_silber()
        return 0

    portale = [x.strip() for x in a.portale.split(",") if x.strip()]
    kats = [x.strip() for x in a.kategorien.split(",") if x.strip()]
    unbekannt = [k for k in kats if k not in KATEGORIEN]
    if unbekannt:
        print(f"unbekannte Kategorie: {unbekannt} — erlaubt: {list(KATEGORIEN)}", file=sys.stderr)
        return 2

    bekannt = set() if a.dry_run else bekannte_keys()
    print(f"NetServer-Abruf: {len(portale)} Portale, {len(bekannt):,} Vorgänge bereits bekannt")
    saetze = hole(portale, kats, bekannt)
    print(f"\n{len(saetze):,} neue Bekanntmachungen")
    if a.dry_run:
        for s in saetze[:5]:
            print("  ", json.dumps(s, ensure_ascii=False)[:150])
        return 0
    for monat, (neu, gesamt) in sorted(schreibe_bronze(saetze).items()):
        print(f"  {monat}: +{neu} → {gesamt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
