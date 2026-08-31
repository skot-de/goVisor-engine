"""Dokument-Fetcher für cosinex/DTVP-Portale — login-frei, §41 VgV.

Holt die **Vergabeunterlagen** (das ZIP mit Leistungsbeschreibung, Vertragsbedingungen,
Formblättern …) von cosinex-Vergabemarktplatz-Portalen, **ohne Registrierung/Login**. cosinex
betreibt ~32 % der DE-Dokument-Links (dtvp.de + viele Landes-/Kommunalportale unter
``/Satellite/`` bzw. ``/VMPSatellite/``) — ein Fetcher deckt sie alle ab.

**Reverse-engineert + validiert** (2026-07-29) an echten offenen Ausschreibungen:

* Die ``documents_url`` (``…/Satellite/notice/<CX>/documents``) ist eine Landingpage; der Aufruf
  setzt per 302 ein **Session-Cookie** und landet auf ``…/public/company/project/<CX>/de/overview``.
* Die Seite zeigt zwar „Um Zugriff auf dieses Modul zu erhalten müssen Sie am Verfahren teilnehmen"
  — das gilt aber nur für **Kommunikation/Angebotsabgabe**. Die Unterlagen selbst hängen an einem
  **öffentlichen Archiv-Endpoint**, der mit dem Session-Cookie **anonym** ein echtes ZIP liefert:

      <host>/<base>/public/company/project/<CX>/de/documents/archive/Vergabeunterlagen_<CX>.zip

  (``<base>`` = ``Satellite`` oder ``VMPSatellite``, je Portal.) Verifiziert: HTTP 200,
  ``application/zip``, mehrere PDFs (Leistungsbeschreibung etc.).

**Höflich by design:** nur URLs, die wir ohnehin haben (kein Crawlen); Rate-Limit zwischen
Requests; idempotent (bereits geladene Vorgänge werden übersprungen); gegatete/leere Vorgänge
werden geflaggt, nicht als Fehler behandelt. CAPTCHA/Anti-Bot → sauberer Abbruch für den Vorgang
(fällt dann in den „du lieferst"-Pfad).

Speicher-Layout: ``<data>/docs/<country>/<notice_id>/Vergabeunterlagen_<CX>.zip`` + ein Manifest
``<data>/docs/<country>/_manifest.parquet`` (notice_id, cx, portal, status, bytes, n_files, ts).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import requests

from .config import Config

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120 Safari/537.36")
# cosinex-URL: Host + Base (Satellite|VMPSatellite) + CX-Projekt-ID aus notice/<CX> oder project/<CX>.
# ⚠ Der BASISPFAD ist NICHT immer „Satellite". cosinex-Instanzen benennen ihn frei:
# `evergabe.blb.nrw.de` fuehrt ihn als `/Vergabe/`. Bis zum 22.08. stand hier eine Aufzaehlung
# (`Satellite|MPSatellite|VMPSatellite`), und 128 offene Vergaben des Landesbetriebs NRW
# galten deshalb als „Portal ohne Abrufer" — obwohl derselbe ZIP-Weg dort einwandfrei
# liefert (gemessen: `application/zip`, 21 MB und 5 MB).
#
# Die Genauigkeit haengt jetzt an der KENNUNG, nicht am Pfadnamen: cosinex-Projekt-IDs
# beginnen mit `CX`. Gegen den offenen Bestand geprueft — +128 erfasst, 0 verloren, und
# kein fremder Host faellt versehentlich hinein.
# Wie lange ein Lauf OHNE ein einziges neues Ergebnis weiterlaufen darf. Der Fall, der am
# 2026-08-21 zwei Abrufer 54 Stunden hat laufen lassen, war nicht ein haengender Vorgang,
# sondern ein Abrufer, der beschaeftigt aussah und nichts mehr lieferte.
LEERLAUF_S = int(__import__("os").environ.get("GOVISOR_LEERLAUF", "3600"))

_COSINEX_RE = re.compile(
    r"^(?P<origin>https?://[^/]+)/(?P<base>[A-Za-z0-9_-]{2,20})/"
    r"(?:public/company/project|notice)/(?P<cx>CX[A-Z0-9]{6,})", re.I)


def is_cosinex(url: str) -> bool:
    return bool(url and _COSINEX_RE.match(url))


_TEILNAHME = re.compile(r"am Vergabeverfahren teilnehmen|Teilnahmeantrag|Interesse bekunden",
                        re.I)


def _sichtbarer_text(html: str | None) -> str:
    """Nur was ein Mensch sieht. ⚠ Skript und Stil MUESSEN raus.

    Eine erste Fassung dieser Pruefung suchte im Roh-HTML nach „anmelden" und fand es in
    jeder Seite — teils in CSS-Regeln, teils im Kopfmenue, das auf jeder cosinex-Seite
    einen Login-Link traegt. Dieselbe Falle wie die had.de-Brotkrume: ein Merkmal, das
    ueberall steht, belegt nichts.
    """
    if not html:
        return ""
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@dataclass
class FetchResult:
    notice_id: str
    cx: str | None
    portal: str | None
    status: str          # downloaded | exists | gated | weg | kein_zip | empty | error
    bytes: int
    n_files: int
    path: str | None
    note: str = ""


def _zip_url(origin: str, base: str, cx: str) -> str:
    return (f"{origin}/{base}/public/company/project/{cx}/de/documents/"
            f"archive/Vergabeunterlagen_{cx}.zip")


def ziel(documents_url: str, notice_id: str, out_root: Path) -> Path | None:
    """Wohin das ZIP dieses Vorgangs gehoert. ``None``, wenn die URL keine cosinex-URL ist.

    Herausgezogen aus `fetch_one`, damit die Auswahl VOR dem Limit wissen kann, was schon
    da ist — ohne dafuer den Abruf anzustossen (s. `fetch_batch`).
    """
    m = _COSINEX_RE.match(documents_url or "")
    if not m:
        return None
    return out_root / notice_id / f"Vergabeunterlagen_{m.group('cx')}.zip"


def fetch_one(documents_url: str, notice_id: str, out_root: Path,
              session: requests.Session | None = None, timeout: int = 60) -> FetchResult:
    """Ein cosinex-Vorgang → Vergabeunterlagen-ZIP auf die Platte. Idempotent."""
    import zipfile

    m = _COSINEX_RE.match(documents_url or "")
    if not m:
        return FetchResult(notice_id, None, None, "error", 0, 0, None, "keine cosinex-URL")
    origin, base, cx = m.group("origin"), m.group("base"), m.group("cx")
    portal = origin.split("//", 1)[-1]
    dest_dir = out_root / notice_id
    dest = dest_dir / f"Vergabeunterlagen_{cx}.zip"
    if dest.exists() and dest.stat().st_size > 0:
        return FetchResult(notice_id, cx, portal, "exists", dest.stat().st_size, 0, str(dest))

    s = session or requests.Session()
    s.headers.update({"User-Agent": _UA, "Accept-Language": "de-DE,de;q=0.9"})
    try:
        # 1) Session-Cookie setzen (Landingpage besuchen).
        s.get(f"{origin}/{base}/notice/{cx}/documents", timeout=timeout, allow_redirects=True)
        # 2) Archiv-ZIP anonym ziehen.
        r = s.get(_zip_url(origin, base, cx), timeout=timeout, allow_redirects=True)
    except requests.RequestException as e:
        return FetchResult(notice_id, cx, portal, "error", 0, 0, None, f"{type(e).__name__}: {e}"[:150])

    ctype = r.headers.get("content-type", "").lower()
    if r.status_code != 200 or "zip" not in ctype:
        # ⚠ KEIN ZIP HEISST NICHT „gegated". Hier stand bis zum 2026-08-31 pauschal `gated`,
        # und der Kommentar daneben nannte die Zweideutigkeit sogar beim Namen
        # („oder nicht (mehr) verfügbar") — entschieden wurde trotzdem zugunsten der
        # blockierenden Deutung. Gemessen an 45 so abgelegten Vorgaengen:
        #
        #     82 %  404 — der Vorgang ist WEG (www.dtvp.de: 26 von 26)
        #     18 %  „Um Zugriff auf dieses Modul zu erhalten muessen Sie am
        #           Vergabeverfahren teilnehmen." — die einzige echte Schranke
        #
        # Der Unterschied ist nicht kosmetisch: `gated` wartet auf ein Konto (BLOCKIERT),
        # `weg` ist endgueltig. Vier von fuenf Vorgaengen standen damit in der
        # Reichweiten-Arbeitsliste und warteten auf einen Zugang, der ihnen nichts nuetzt.
        sicht = _sichtbarer_text(r.text)
        note = f"http {r.status_code}, {ctype[:30]}"
        if r.status_code == 404 or "(404)" in sicht:
            return FetchResult(notice_id, cx, portal, "weg", 0, 0, None,
                               "Vorgang nicht mehr auf dem Portal (404)")
        if _TEILNAHME.search(sicht):
            return FetchResult(notice_id, cx, portal, "gated", 0, 0, None,
                               "Teilnahme am Verfahren nötig")
        # Weder das eine noch das andere: ehrlich offen lassen, statt zu raten.
        return FetchResult(notice_id, cx, portal, "kein_zip", 0, 0, None, note)
    if not r.content or len(r.content) < 64:
        return FetchResult(notice_id, cx, portal, "empty", len(r.content or b""), 0, None)

    dest_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(r.content)
    # Integrität + Dateizahl prüfen.
    try:
        with zipfile.ZipFile(tmp) as z:
            n_files = sum(1 for i in z.infolist() if not i.is_dir())
    except zipfile.BadZipFile:
        tmp.unlink(missing_ok=True)
        return FetchResult(notice_id, cx, portal, "error", len(r.content), 0, None, "defektes ZIP")
    tmp.replace(dest)
    return FetchResult(notice_id, cx, portal, "downloaded", dest.stat().st_size, n_files, str(dest))


def _waehle_connector(url: str):
    """URL → zustaendiger Connector. Neue Plattform = eine Zeile hier plus ein Modul.

    Bewusst eine Weiche statt einer Kette von `if` im Schleifenrumpf: der naechste
    Connector (subreport, staatsanzeiger …) soll `fetch_batch` nicht anfassen muessen.
    """
    from . import docfetch_rib
    if docfetch_rib.is_rib(url):
        return docfetch_rib.fetch_one
    return fetch_one


# Modulname → Zielpfad-Funktion. Zwei Connectoren, zwei Namensschemata; die Zuordnung
# steht hier, damit `fetch_batch` sie nicht raten muss.
_ZIELE = {
    __name__: lambda u, n, r: ziel(u, n, r),
    __name__.rsplit(".", 1)[0] + ".docfetch_rib":
        lambda u, n, r: __import__(__name__.rsplit(".", 1)[0] + ".docfetch_rib",
                                   fromlist=["ziel"]).ziel(u, n, r),
}


def fetch_batch(cfg: Config, country: str = "DE", limit: int | None = None,
                delay: float = 1.5) -> dict:
    """Alle offenen Leads mit cosinex-``documents_url`` → Unterlagen ziehen (höflich, idempotent).

    Liest ``gold/<country>/lead_export.parquet``, filtert auf cosinex-Vorgänge, lädt je Vorgang das
    ZIP mit ``delay`` s Pause. Schreibt Manifest. Gibt eine Status-Zusammenfassung zurück.
    """
    import duckdb

    G = cfg.gold_dir / country
    out_root = cfg.data_dir / "docs" / country
    out_root.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    rows = con.execute(
        f"""SELECT lead_id, documents_url FROM read_parquet('{(G / 'lead_export.parquet').as_posix()}')
            WHERE phase='open' AND documents_url IS NOT NULL
              -- Zwei Connectoren: cosinex (Satellite-Pfad) und RIB/meinauftrag.
              -- Die Zuordnung je Zeile macht `_waehle_connector` unten — hier nur
              -- vorfiltern, damit nicht 7.000 ungedeckte Vorgaenge durchlaufen.
              -- Basispfad frei, Kennung streng (s. `_COSINEX_RE`): `/Vergabe/notice/CX…`
              -- beim Landesbetrieb NRW gehoert genauso dazu wie `/Satellite/notice/CX…`.
              AND (regexp_matches(documents_url, '/[A-Za-z0-9_-]{2,20}/(public/company/project|notice)/CX[A-Z0-9]{6,}')
                   OR documents_url LIKE '%meinauftrag.rib.de%')
              -- Nur LAUFENDE Verfahren. Die Unterlagen haengen nur waehrend der Angebots-
              -- frist am Portal; danach liefert der Endpoint die Landingpage (Status
              -- `gated`) und der Versuch ist verschenkt.
              --
              -- STRIKT GROESSER: der Fristtag selbst faellt raus. Eine Frist traegt eine
              -- UHRZEIT (`deadline_time`, gemessen typisch 08:00/10:00/12:00) — laeuft der
              -- Fetch nachmittags, ist die Vergabe seit Stunden zu und cosinex hat die
              -- Unterlagen abgehaengt. Gemessen 2026-08-14 an DTVP, je 10 Vorgaenge:
              --
              --     Frist heute      70 % erreichbar
              --     +1 bis  2 Tage  100 %
              --     +3 bis  7 Tage  100 %
              --     +8 bis 30 Tage   90 %
              --
              -- Die Klippe ist also genau EIN Tag breit. Ein grosszuegigerer Vorlauf (die
              -- erste Idee waren 14 Tage) haette 90 % erreichbarer Vorgaenge mit
              -- weggeworfen — die Messung hat den Eingriff kleiner gemacht, nicht groesser.
              -- Und ein Lead, der heute um 10:00 schliesst, ist als Lead ohnehin keiner.
              AND deadline_date > current_date
              -- OPEN HOUSE gar nicht erst versuchen. Dort tritt man einem Rabattvertrag
              -- BEI, statt zu bieten; die Unterlagen liegen systematisch hinter der
              -- Teilnahme („Um Zugriff auf dieses Modul zu erhalten muessen Sie am
              -- Vergabeverfahren teilnehmen"). Gemessen an `vergabe.tk.de`: 197 von 202
              -- Versuchen `gated`, alle acht Stichproben Open-House-Rabattvertraege der
              -- Techniker Krankenkasse mit Fristen bis 2028. Das ist kein Portal-Problem
              -- und keine schliessbare Luecke, sondern die Bauart des Verfahrens —
              -- `gold` fuehrt sie deshalb schon als eigene Klasse.
              AND coalesce(procedure_kind, '') <> 'open_house'
            -- AUFSTEIGEND: naechste Frist zuerst. Vorher stand hier DESC — damit landeten
            -- Fristen in 2029/2030 ganz oben (Rahmenvertraege und Fehlschaetzungen, deren
            -- Ausschreibung laengst zu ist). Gemessen: von den ersten zwoelf Versuchen
            -- gingen sechs an Vergaben aus 2025, Ausbeute null. Aufsteigend trifft man die
            -- Verfahren, die sicher noch offen sind — und zugleich die dringendsten Leads.
            ORDER BY deadline_date ASC""").fetchall()
    # Frueher Gescheitertes ueberspringen. VOR dem Limit, sonst kappt das Limit auf
    # Kandidaten, die gleich wieder aussortiert werden.
    #
    # Der Hebel steckt hier in `gated`: 389 Leads hinter Teilnahmeantrag/Login, gemessen
    # 2026-08-15. Sie wurden bis dahin bei JEDEM Lauf erneut angefragt — das Manifest
    # notierte sie sauber, nur las es niemand.
    from . import docfetch_queue as _queue
    rows, _weg = _queue.filtere(rows, _queue.frueher(out_root, "cosinex", id_feld="notice_id"))
    if _weg:
        print(_queue.bericht(_weg))

    # ⚠ WAS SCHON AUF DER PLATTE LIEGT, EBENFALLS VOR DEM LIMIT AUSSORTIEREN.
    #
    # Der Fehlschlag-Filter darueber tut das seit dem 15.08. fuer frueher Gescheitertes —
    # fuer bereits GEHOLTE Vergaben fehlte dasselbe. `fetch_one` erkennt sie zwar (Status
    # `exists`) und kostet dabei kein Netz, aber sie verbrauchen das Limit. Zusammen mit
    # `ORDER BY deadline_date ASC` traf das immer dieselben: die naechsten Fristen stehen
    # vorn und sind laengst geholt.
    #
    # Gemessen am 2026-08-21: von 2.918 Kandidaten lagen **1.930 schon da**, und der
    # Median der fehlenden stand auf Position 1.842. Mit `--limit 40` waren 8 von 40
    # Versuchen wirklich neu (20 %), mit 150 waren es 35. Die hinteren Zweidrittel des
    # Rueckstaus wurden nie erreicht — nicht weil das Portal sperrt, sondern weil die
    # Liste vorher endete.
    schon = 0
    frisch = []
    for lead_id, url in rows:
        modul = _waehle_connector(url).__module__
        finder = _ZIELE.get(modul)
        z = finder(url, lead_id, out_root) if finder else None
        if z is not None and z.exists() and z.stat().st_size > 0:
            schon += 1
            continue
        frisch.append((lead_id, url))
    if schon:
        print(f"  {schon:,} Vorgänge liegen schon auf der Platte — vor dem Limit aussortiert.")
    rows = frisch

    if limit:
        rows = rows[:limit]

    # ⚠ Auch hier eine Wache, obwohl `requests` je Aufruf ein `timeout` hat: die Grenze
    # schuetzt den EINZELNEN Aufruf, nicht den Lauf. Ein Abrufer, der eine Stunde lang
    # brav in Zeitgrenzen laeuft und dabei nichts holt, ist derselbe Verlust wie einer,
    # der haengt — nur unauffaelliger.
    def _sichern():
        if results:
            _queue.schreibe(out_root, "cosinex", [asdict(r) for r in results],
                            id_feld="notice_id")

    wache = _queue.Wache("cosinex", vorgang_hart_s=0, leerlauf_s=LEERLAUF_S, sichern=_sichern)
    wache.__enter__()
    s = requests.Session()
    results: list[FetchResult] = []
    counts: dict[str, int] = {}
    for i, (lead_id, url) in enumerate(rows, 1):
        res = _waehle_connector(url)(url, lead_id, out_root, session=s)
        results.append(res)
        if res.status == "downloaded":
            wache.erfolg()
        counts[res.status] = counts.get(res.status, 0) + 1
        if res.status in ("downloaded", "exists"):
            tag = f"{res.n_files} Dateien" if res.status == "downloaded" else "vorhanden"
            print(f"  [{i}/{len(rows)}] {res.status:10} {lead_id}  {res.bytes/1024:.0f} KB  {tag}", flush=True)
        else:
            print(f"  [{i}/{len(rows)}] {res.status:10} {lead_id}  ({res.note})", flush=True)
        if res.status == "downloaded" and delay:
            time.sleep(delay)   # nur nach echtem Download drosseln

    if results:
        # Fortschreiben statt ueberschreiben: das alte `write_table` warf mit jedem Lauf
        # die gesamte Vorgeschichte weg — und damit die Grundlage jeder Sperrentscheidung.
        _queue.schreibe(out_root, "cosinex", [asdict(r) for r in results],
                        id_feld="notice_id")
    total_mb = sum(r.bytes for r in results if r.status == "downloaded") / 1e6
    print(f"\nUnterlagen-Fetch {country}: {len(rows)} Vorgänge | " +
          " | ".join(f"{k}={v}" for k, v in sorted(counts.items())) +
          f" | {total_mb:.1f} MB neu")
    return {"total": len(rows), "counts": counts, "mb": round(total_mb, 1)}
