"""Quelle DE — cosinex-Vergabemarktplätze (VMP) der Länder, Bekanntmachungs-Downloader.

**Warum diese Quelle.** Drei deutsche Landesportale fahren dieselbe cosinex-Software wie
DTVP und waren bisher ungeprüft: **Nordrhein-Westfalen** (evergabe.nrw.de),
**Rheinland-Pfalz** (vergabe.rlp.de) und **Brandenburg** (vergabemarktplatz.brandenburg.de).
Sie führen ober- UND unterschwellige Vergaben; über TED kommen nur die oberschwelligen,
über DÖE nur ein Teil.

**Der Fund, der dieses Modul rechtfertigt: es gibt einen server-gerenderten Weg.** Bei DTVP
wurde gemessen und dreifach belegt, dass die Trefferliste clientseitig entsteht — deshalb
Playwright (`govisor/dtvp.py`, Modulkopf). Das gilt für die **Suchmaske**. Der
**Auftragsgegenstand-Überblick** derselben Software ist dagegen reines Server-HTML::

    /company/announcements/categoryOverview.do?method=showCategoryOverview
        → 45 CPV-Divisionen, jede mit Anzahl (kostenlose Mengenmessung, ein Abruf)
    /company/announcements/categoryOverview.do?method=showTable&cpvCode=45000000-7
        → Trefferliste dieser Division; der Filter bleibt in der SESSION stehen
    …&method=showTable&fromSearch=1&tableSortPROJECT_RESULT=2
       &tableSortAttributePROJECT_RESULT=publicationDate
        → absteigend nach Veröffentlichung (``2`` = absteigend, ``1`` = aufsteigend; gemessen)
    …&method=showTable&fromSearch=1&selectedTablePagePROJECT_RESULT=N
        → blättern, 20 je Seite (eine Seitengrösse liess sich nicht setzen, gemessen)

`requests` mit Session-Cookie genügt also; Playwright wäre hier reine Kosten. Die Lehre aus
`scripts/probe_portals.py` in einer Zeile: **von der Zugänglichkeit EINER Schicht darf man
nicht auf eine andere schliessen — in beide Richtungen nicht.**

**Was die Trefferzeile trägt** (mehr als DTVP und NetServer):

======================  =====================================================
Veröffentlichung        Datum **und Uhrzeit** (im ``abbr title``)
Angebots-/Teilnahmefrist Datum **und Uhrzeit**; ``nv`` = keine
Kurzbezeichnung         Titel
Vergabeordnung          VOB/A · VOL/A · VgV · UVgO · SektVO · VSVgV · KonzVgV
Typ                     Ausschreibung · Beabsichtigte Ausschreibung ·
                        Vergebener Auftrag · TNW (Teilnahmewettbewerb)
Vergabestelle           Klartext, bei allen drei Portalen gefüllt
CPV-Division            aus dem Pfad des Überblicks — **echte Portalangabe**
pid                     stabile Vorgangs-ID des Portals
======================  =====================================================

**Die CPV-Frage ist hier anders gelöst als bei DTVP/NetServer — und das ist der Kern des
Mehrwerts.** Dort musste `cpv_main` für VOB/A aus dem Regelwerk *hergeleitet* werden
(VOB = Bauleistung = 45), und VOL/UVgO blieb NULL — womit diese Leads aus
`gold.build_prospective_leads` (verlangt `cpv_main IS NOT NULL`) lautlos herausfielen. Hier
liefert das Portal die Division selbst, für **jede** Vergabeordnung. Der Preis: es ist die
Division (`45000000-7`), nicht das Gewerk (`45261210-9`). Das steht als
``cosinex/cpv_ebene = division`` in `attributes`, damit niemand die grobe Angabe für eine
feine hält. Feiner ginge über einen zweiten Drilldown (`cpvCode=45100000-8` …) — das
vervielfacht die Abrufe und ist bewusst ein offener Punkt, kein stiller Verzicht.

⚠ **Eine Bekanntmachung kann unter mehreren Divisionen stehen.** Der Abruf sammelt deshalb
ALLE Divisionen je `pid` (`cpv_divs`); die erste wird `cpv_main`, die übrigen landen als
``cosinex/cpv_division`` in `attributes` — kein Datenverlust, aber auch keine erfundene
Hauptkategorie.

⚠ **robots.txt ist nicht überall gleich.** Gemessen 2026-08-14:

    evergabe.nrw.de              keine robots.txt (HTTP 404)      → offen
    vergabe.rlp.de               keine robots.txt (301 auf App)   → offen
    vergabemarktplatz.brandenb.  ``User-agent: * / Disallow: /``  → GESPERRT

Brandenburg steht deshalb in `PORTALE` mit ``robots="disallow"`` und wird **standardmässig
übersprungen**. Das ist keine technische Grenze — der Abruf funktioniert — sondern eine
Entscheidung, die einem Menschen gehört: ``--ignoriere-robots`` schaltet ihn frei. Markieren
statt stillschweigend tun, und markieren statt stillschweigend lassen.
(Zum Vergleich: die vier bereits angeschlossenen NetServer-Portale und dtvp.de führen
keine sperrende robots.txt; Hessen ``vergabe.hessen.de`` dagegen verbietet ausdrücklich
``/NetServer/PublicationSearchControllerServlet?`` — deshalb ist Hessen hier NICHT drin.)

**Bronze = eine Zeile je Bekanntmachung als JSONL**, ``data/raw_cosinex/DE/YYYY-MM.jsonl``,
dedupliziert über ``<portal>:<pid>``. Wie bei TED/DÖE/simap/DTVP/NetServer liegt die
Verlustfreiheit in Bronze: ein Parser-Fix kostet einen Re-Run über lokale Dateien, keinen
erneuten Abruf. Anders als bei NetServer ist das hier auch wirksam, weil Bronze die
**Rohzellen** mitführt (`zellen`), nicht nur das Geparste.

**Kein quellen-eigenes Dedup.** Der Dublettencheck ist zentral gelöst
(`govisor/dedupe.py`, quellenübergreifend) — das war ausdrücklich die Lehre aus DTVP.

Aufruf::

    python3 -m govisor.cosinex --portale nw,rp --ab-jahr 2023 --silber
    python3 -m govisor.cosinex --portale bb --ignoriere-robots
    python3 -m govisor.cosinex --nur-silber
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36 "
      "goVisor-Marktanalyse (sven.kotzur@gmail.com)")

# Kürzel → (Land, Basis-URL, robots-Befund). Eine weitere cosinex-Instanz ist eine ZEILE,
# kein Codepfad — dieselbe Konvention wie `netserver.PORTALE`.
#
# dtvp.de läuft auf derselben Software (Basis `/Center` statt `/VMPCenter`) und wäre hier
# eine Zeile mehr. Es steht BEWUSST nicht drin: `govisor/dtvp.py` ist eine laufende Quelle
# mit eigenem Bronze-Bestand und eigenem Namensraum (`dtvp:<pid>`). Beide gleichzeitig
# würde denselben Vorgang doppelt nach Silber schreiben. Eine Ablösung von dtvp.py durch
# diesen Weg (server-gerendert statt Playwright, und MIT CPV) ist ein eigenes Ticket.
PORTALE: dict[str, tuple[str, str, str]] = {
    "nw": ("Nordrhein-Westfalen", "https://www.evergabe.nrw.de/VMPCenter", "offen"),
    "rp": ("Rheinland-Pfalz", "https://www.vergabe.rlp.de/VMPCenter", "offen"),
    "bb": ("Brandenburg", "https://vergabemarktplatz.brandenburg.de/VMPCenter", "disallow"),
}

_EP = "/company/announcements/categoryOverview.do"
_UEBERBLICK = f"{_EP}?method=showCategoryOverview"
_DIVISION = f"{_EP}?method=showTable&cpvCode=%s"
_SORT_NEU = (f"{_EP}?method=showTable&fromSearch=1&tableSortPROJECT_RESULT=2"
             f"&tableSortAttributePROJECT_RESULT=publicationDate")
_SEITE = f"{_EP}?method=showTable&fromSearch=1&selectedTablePagePROJECT_RESULT=%d"

_HOEFLICH_S = 1.2          # Pause zwischen Abrufen — fremdes System, kein Grund zu hetzen
_TIMEOUT = 45

# Typ-Spalte → unser `notice_kind`. TNW (Teilnahmewettbewerb) ist die erste Stufe eines
# zweistufigen Verfahrens und damit eine Ausschreibung, kein eigener Typ.
_KIND = {
    "Ausschreibung": "cn",
    "TNW": "cn",
    "Teilnahmewettbewerb": "cn",
    "Beabsichtigte Ausschreibung": "pin",
    "Vergebener Auftrag": "can",
}
# Vergabeordnungen, die per Vorschrift unterschwellig sind bzw. es typischerweise anzeigen.
_UNTERSCHWELLIG = re.compile(r"UVgO|VOL/A(?!/)|VOB/A(?!.*EU)", re.I)
# VOB/A ist per Definition die Vergabe- und Vertragsordnung für BAULEISTUNGEN. Anders als
# bei DTVP/NetServer brauchen wir das NICHT für `cpv_main` (das Portal liefert die
# Division) — nur für `contract_nature`.
_NATUR = {"VOB/A": "works"}

_ZELLE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
_ZEILE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_PID = re.compile(r"projectForwarding\.do\?pid=(\d+)")
_ABBR = re.compile(r"<abbr[^>]*title=['\"]([^'\"]+)['\"]", re.I)
_SEITEN = re.compile(r"Seite:\s*(\d+)\s*von\s*(\d+)")
_CPV = re.compile(r"cpvCode=(\d{8}-\d)")
_ZEITSTEMPEL = re.compile(r"(\d{2}\.\d{2}\.\d{4})(?:\s*um\s*(\d{2}:\d{2}))?")


def _txt(x: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()


def _stempel(zelle_html: str) -> str | None:
    """Datum **mit Uhrzeit** aus der Zelle — ISO, oder None.

    Die Zelle trägt den vollen Zeitpunkt im ``abbr title`` (``25.08.2026 um 10:00 Uhr``)
    und nur das Datum im sichtbaren Text. Ohne das ``abbr`` verlöre die Angebotsfrist ihre
    Uhrzeit — bei einer Frist ist das der Unterschied zwischen „heute noch" und „vorbei".
    """
    m = _ABBR.search(zelle_html)
    quelle = m.group(1) if m else _txt(zelle_html)
    t = _ZEITSTEMPEL.search(quelle)
    if not t:
        return None
    try:
        d = dt.datetime.strptime(t.group(1), "%d.%m.%Y")
    except ValueError:
        return None
    if t.group(2):
        h, mi = t.group(2).split(":")
        d = d.replace(hour=int(h), minute=int(mi))
        return d.isoformat()
    return d.date().isoformat()


def zeilen_lesen(seite: str) -> list[dict]:
    """Trefferzeilen einer ``showTable``-Seite auslesen.

    Der Parser ist **spaltenpositions-basiert** und darf das sein: anders als bei NetServer
    (fünf unterschiedlich geskinnte Instanzen) rendert cosinex bei allen drei Portalen
    dieselbe Tabelle aus derselben Software — an NRW, RLP und Brandenburg gemessen. Er
    hängt sich trotzdem nicht an eine feste Spaltenzahl: eine Zeile ohne ``pid`` oder ohne
    Titel gilt nicht als Vorgang.
    """
    aus: list[dict] = []
    for roh in _ZEILE.findall(seite):
        m = _PID.search(roh)
        if not m:
            continue
        zellen = _ZELLE.findall(roh)
        if len(zellen) < 5:
            continue
        titel = _txt(zellen[2])
        if not titel:
            continue
        # Vergabeordnung und Typ stehen in EINER Zelle, getrennt durch <br>:
        #   `VSVgV<br /><abbr title="Teilnahmewettbewerb">TNW</abbr>`
        # Zusammengelesen ergäbe das „VSVgVTNW" — genau die Art stiller Feldvermengung,
        # die später niemand mehr auseinandersortiert.
        teile = [_txt(x) for x in re.split(r"<br\s*/?>", zellen[3], flags=re.I)]
        teile = [x for x in teile if x]
        aus.append({
            "pid": m.group(1),
            "pub": _stempel(zellen[0]),
            "frist": _stempel(zellen[1]),
            "titel": titel,
            "vo": teile[0] if teile else None,
            "typ": teile[1] if len(teile) > 1 else None,
            "stelle": _txt(zellen[4]) or None,
            # Rohzellen mitführen: DAS macht den Bronze-Re-Run wirksam. Bei NetServer
            # speichert Bronze nur das Geparste, weshalb dort ein Parser-Fix einen
            # erneuten ABRUF verlangt (`--neu-einlesen`). Hier nicht.
            "zellen": [_txt(z) for z in zellen[:5]],
        })
    return aus


def divisionen(sess, basis: str) -> list[tuple[str, str, int]]:
    """CPV-Divisionen des Überblicks → [(cpv, Label, Anzahl)]. EIN Abruf, volle Mengenlage."""
    r = sess.get(basis + _UEBERBLICK, timeout=_TIMEOUT)
    r.raise_for_status()
    aus = []
    for roh in _ZEILE.findall(r.text):
        m = _CPV.search(roh)
        z = [_txt(c) for c in _ZELLE.findall(roh)]
        if m and len(z) >= 2 and z[-1].replace(".", "").isdigit():
            aus.append((m.group(1), z[0], int(z[-1].replace(".", ""))))
    return aus


def seitenzahl(seite: str) -> int:
    m = _SEITEN.search(_txt(seite))
    return int(m.group(2)) if m else 1


def hole(portale: list[str], ab_jahr: int, bekannt: set[str], stop_nach: int,
         ignoriere_robots: bool = False, max_seiten: int = 500) -> list[dict]:
    """Bekanntmachungen abrufen. Gibt Bronze-Sätze zurück (eine Zeile je Portal+pid).

    Je Division wird absteigend nach Veröffentlichung geblättert. Zwei Abbruchgründe:
    ``ab_jahr`` (eine ganze Seite älter als das Fenster) und ``stop_nach`` (so viele
    bereits bekannte Vorgänge gesehen — der Tageslauf-Fall).
    """
    import requests

    sess = requests.Session()
    sess.headers.update({"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9"})
    # Ein Satz je (portal,pid); mehrere Divisionen desselben Vorgangs werden GESAMMELT,
    # nicht überschrieben — eine Bekanntmachung kann unter mehreren CPV stehen.
    gesammelt: dict[str, dict] = {}
    for kuerzel in portale:
        land, basis, robots = PORTALE.get(kuerzel, (kuerzel, "", "offen"))
        if not basis:
            print(f"  {kuerzel}: unbekanntes Portal — übersprungen", flush=True)
            continue
        if robots == "disallow" and not ignoriere_robots:
            print(f"  {kuerzel} ({land}): robots.txt sperrt den ganzen Host — übersprungen. "
                  f"Bewusst freischalten mit --ignoriere-robots.", flush=True)
            continue
        sess.cookies.clear()          # Divisionsfilter lebt in der Session
        try:
            divs = divisionen(sess, basis)
        except Exception as e:                                   # noqa: BLE001
            print(f"  {kuerzel}: Überblick nicht erreichbar ({type(e).__name__})", flush=True)
            continue
        print(f"  {kuerzel} ({land}): {len(divs)} Divisionen, "
              f"{sum(d[2] for d in divs):,} Bekanntmachungen im Portal", flush=True)
        for cpv, label, anzahl in divs:
            neu = alt = 0
            try:
                sess.get(basis + (_DIVISION % cpv), timeout=_TIMEOUT)
                time.sleep(_HOEFLICH_S)
                r = sess.get(basis + _SORT_NEU, timeout=_TIMEOUT)
            except Exception as e:                               # noqa: BLE001
                print(f"    {cpv}: Abruf fehlgeschlagen ({type(e).__name__})", flush=True)
                continue
            seiten = min(seitenzahl(r.text), max_seiten)
            for nr in range(1, seiten + 1):
                if nr > 1:
                    time.sleep(_HOEFLICH_S)
                    try:
                        r = sess.get(basis + (_SEITE % nr), timeout=_TIMEOUT)
                    except Exception as e:                       # noqa: BLE001
                        print(f"    {cpv} S.{nr}: {type(e).__name__}", flush=True)
                        break
                zs = zeilen_lesen(r.text)
                if not zs:
                    break
                zu_alt = 0
                for z in zs:
                    jahr = int(z["pub"][:4]) if z["pub"] else None
                    if jahr and jahr < ab_jahr:
                        zu_alt += 1
                        continue
                    schl = f"{kuerzel}:{z['pid']}"
                    if schl in gesammelt:
                        gesammelt[schl]["cpv_divs"].append(cpv)
                        continue
                    if schl in bekannt:
                        alt += 1
                        continue
                    z.update(portal=kuerzel, land=land, key=schl, cpv_divs=[cpv],
                             cpv_label=label,
                             erfasst_am=dt.date.today().isoformat())
                    gesammelt[schl] = z
                    neu += 1
                if zu_alt >= len(zs):        # ganze Seite älter als das Fenster
                    break
                if stop_nach and alt >= stop_nach:
                    break
            print(f"    {cpv} {label[:34]:<34} {anzahl:>5} im Portal → {neu:>4} neu, "
                  f"{alt:>4} bekannt", flush=True)
            time.sleep(_HOEFLICH_S)
    for s in gesammelt.values():
        s["cpv_divs"] = sorted(dict.fromkeys(s["cpv_divs"]))
    return list(gesammelt.values())


def schreibe_bronze(saetze: list[dict], country: str = "DE") -> dict:
    """Nach Monat gebündelt als JSONL, dedupliziert über `key`. Idempotent."""
    root = ROOT / "data" / "raw_cosinex" / country
    root.mkdir(parents=True, exist_ok=True)
    nach_monat: dict[str, list[dict]] = {}
    for s in saetze:
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
    root = ROOT / "data" / "raw_cosinex" / country
    aus: set[str] = set()
    if not root.exists():
        return aus
    for f in root.glob("*.jsonl"):
        for zeile in f.read_text(encoding="utf-8").splitlines():
            m = re.search(r'"key":\s*"([^"]+)"', zeile)
            if m:
                aus.add(m.group(1))
    return aus


# ── Bronze → Silber ───────────────────────────────────────────────────────────────────────
def _iso(s: str | None):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        return None


def nach_silber(country: str = "DE") -> dict:
    """Bronze-JSONL → Silber-Parquet (notices, notice_parties, attributes).

    `notice_id` ist ``cx:<portal>:<pid>`` — der Präfix hält den Namensraum von TED-IDs
    getrennt (dieselbe Konvention wie DÖE `doe:`, DTVP `dtvp:` und NetServer `ns:`).
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    roh_dir = ROOT / "data" / "raw_cosinex" / country
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
        nid = f"cx:{r['portal']}:{r['pid']}"
        pub_dt = _iso(r.get("pub"))
        pub = pub_dt.date() if pub_dt else None
        frist = _iso(r.get("frist"))
        # `publication_date` bleibt NULL, wenn die Quelle keins führt — kein erfundenes
        # Datum. Für year/month tritt ersatzweise das Erfassungsdatum ein, sonst landen
        # die Sätze in `year=0` und fallen aus jeder Zeitreihe (Lehre aus NetServer/Sachsen).
        platz = pub or (_iso(r.get("erfasst_am")) or dt.datetime.min).date()
        platz = platz if pub or r.get("erfasst_am") else None
        vo = (r.get("vo") or "").strip()
        divs = r.get("cpv_divs") or []
        _, basis, _ = PORTALE.get(r["portal"], ("", "", ""))
        notices.append({
            "notice_id": nid, "publication_number": r["pid"], "oj_ref": None,
            "publication_date": pub, "ted_url": None, "country": country,
            "buyer_countries": [country],
            "year": platz.year if platz else None,
            "month": platz.month if platz else None,
            "schema_gen": "cosinex", "form_type": r.get("typ"),
            "notice_kind": _KIND.get((r.get("typ") or "").strip(), "cn"),
            "language": "de",                     # kleingeschrieben — Guard-Konvention
            "title": r.get("titel"), "description": None, "description_field": None,
            # ECHTE Portalangabe, keine Herleitung aus dem Regelwerk (s. Modulkopf).
            "cpv_main": divs[0] if divs else None,
            "performance_nuts": None,
            "contract_nature": _NATUR.get(vo),
            "procedure_type": r.get("typ"),
            "submission_deadline": frist,
            "portal_url": (f"{basis}/public/company/projectForwarding.do?pid={r['pid']}"
                           if basis else None),
            "estimated_value": None, "final_value": None, "value_currency": None,
            "award_date": None, "start_date": None, "end_date": None,
            "lot_count": None, "text_chars": len(r.get("titel") or ""),
            "ref_publication_number": None, "ref_ted_url": None,
            "flags": [], "unknown_country_codes": [],
        })
        # Vergabestelle: alle drei Portale führen sie. Fehlt sie doch, wird sie NICHT
        # erfunden — aber es braucht eine Partei, sonst fällt der Vorgang am `JOIN buyer`
        # von `gold.build_prospective_leads` lautlos aus der Lead-Schicht (die Falle, die
        # bei Bremen alle 41 Ausschreibungen gekostet hätte).
        stelle = (r.get("stelle") or "").strip()
        if not stelle:
            stelle = f"Vergabestelle nicht ausgewiesen ({r.get('land') or r['portal']})"
            attrs.append({"notice_id": nid, "path": "cosinex/stelle_unbekannt",
                          "value": "Portal führte die Vergabestelle in der Trefferzeile nicht"})
        parties.append({
            "notice_id": nid, "role": "buyer", "seq": 0, "name": stelle,
            "national_id": None, "town": None, "postal_code": None, "country": country,
            "nuts": None, "email": None, "phone": None, "contact_person": None,
            "url": None, "is_sme": None, "in_consortium": None,
            "year": platz.year if platz else None,
        })
        attrs.append({"notice_id": nid, "path": "cosinex/portal", "value": r["portal"]})
        attrs.append({"notice_id": nid, "path": "cosinex/land", "value": r.get("land")})
        if vo:
            attrs.append({"notice_id": nid, "path": "cosinex/vergabeordnung", "value": vo})
        for d in divs:
            attrs.append({"notice_id": nid, "path": "cosinex/cpv_division", "value": d})
        if divs:
            # Die Grobheit ausdrücklich benennen — sonst hält sie später jemand für ein Gewerk.
            attrs.append({"notice_id": nid, "path": "cosinex/cpv_ebene", "value": "division"})
        if not pub and r.get("erfasst_am"):
            attrs.append({"notice_id": nid, "path": "cosinex/zeitpunkt_aus_erfassung",
                          "value": "Quelle führte kein Veröffentlichungsdatum"})
        if vo and _UNTERSCHWELLIG.search(vo):
            attrs.append({"notice_id": nid, "path": "cosinex/unterschwellig_moeglich",
                          "value": vo})

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
            pq.write_table(pa.Table.from_pylist(gruppe), d / f"{jahr}-cosinex.parquet",
                           compression="zstd")
            n += len(gruppe)
        stat[name] = n
    mit_cpv = sum(1 for x in notices if x["cpv_main"])
    print(f"cosinex Silber {country}: " + " · ".join(f"{k} {v:,}" for k, v in stat.items()))
    print(f"  cpv_main aus der Portalangabe: {mit_cpv:,} von {len(notices):,} "
          f"({100*mit_cpv/max(len(notices),1):.1f} %, Ebene Division)")
    return stat


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="cosinex-VMP-Bekanntmachungen → Bronze/Silber")
    p.add_argument("--portale", default="nw,rp",
                   help="Kürzel, Komma-getrennt: " + ", ".join(PORTALE))
    p.add_argument("--ab-jahr", type=int, default=dt.date.today().year - 2,
                   help="ältere Veröffentlichungen nicht holen")
    p.add_argument("--stop-nach-bekannten", type=int, default=40,
                   help="Abbruch je Division, wenn so viele bekannte Vorgänge gesehen "
                        "wurden (0 = nie) — der Tageslauf-Fall")
    p.add_argument("--max-seiten", type=int, default=500, help="je Division")
    p.add_argument("--ignoriere-robots", action="store_true",
                   help="auch Portale holen, deren robots.txt den Host sperrt "
                        "(derzeit: Brandenburg) — bewusste Entscheidung, kein Standard")
    p.add_argument("--silber", action="store_true",
                   help="nach dem Abruf auch Bronze → Silber schreiben")
    p.add_argument("--nur-silber", action="store_true", help="kein Abruf, nur Bronze → Silber")
    p.add_argument("--dry-run", action="store_true", help="abrufen, nichts schreiben")
    a = p.parse_args(argv)

    if a.nur_silber:
        nach_silber()
        return 0

    portale = [x.strip() for x in a.portale.split(",") if x.strip()]
    unbekannt = [x for x in portale if x not in PORTALE]
    if unbekannt:
        print(f"unbekanntes Portal: {unbekannt} — erlaubt: {list(PORTALE)}", file=sys.stderr)
        return 2

    bekannt = set() if a.dry_run else bekannte_keys()
    print(f"cosinex-Abruf: {len(portale)} Portale, ab {a.ab_jahr}, "
          f"{len(bekannt):,} Vorgänge bereits bekannt")
    saetze = hole(portale, a.ab_jahr, bekannt, a.stop_nach_bekannten,
                  a.ignoriere_robots, a.max_seiten)
    print(f"\n{len(saetze):,} neue Bekanntmachungen")
    if a.dry_run:
        for s in saetze[:5]:
            print("  ", json.dumps(s, ensure_ascii=False)[:180])
        return 0
    if saetze:
        for monat, (neu, gesamt) in sorted(schreibe_bronze(saetze).items()):
            print(f"  {monat}: +{neu} → {gesamt}")
    if a.silber:
        print()
        nach_silber()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
