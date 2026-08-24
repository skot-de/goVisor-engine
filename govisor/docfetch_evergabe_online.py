"""Vergabeunterlagen von **evergabe-online.de** (e-Vergabe des Bundes).

Die groesste einzelne Luecke im deutschen Bestand: **1.034 offene Leads**, bis zuletzt ohne
jeden Zugang. Sie war lange nicht pruefbar, weil die Plattform ueber Tage in Wartung stand.

**Der Download ist frei — die Plattform sagt es selbst.** Auf der Vorgangsseite steht
woertlich „Die Vergabeunterlagen stehen fuer einen uneingeschraenkten und vollstaendigen
direkten Zugang gebuehrenfrei zur Verfuegung", und die Unterlagenseite bietet „Als ZIP-Datei
herunterladen" ohne Anmeldung an. Der Hinweis daneben — freier Download diene „nur einer
ersten Ansicht", fuer die Teilnahme brauche es ein Konto — betrifft das Bieten, nicht das
Lesen. Gemessen an 30 zufaelligen Vorgaengen: **28 mit freiem ZIP**.

**Vorher gepruefte Schnittstellenfrage** (Arbeitsweise: erst fragen, dann abgreifen). Die
Standardpfade (`/v3/api-docs`, `/openapi.json`, `/swagger-ui/…`, `/api/`, `/rest/`) geben
alle 404. Die `robots.txt` verraet aber, dass es Dienste GIBT:

    Disallow: /axis2/services/
    Disallow: /xvergabe/services/
    Disallow: /ws-suche/

`/xvergabe/services/` ist der deutsche **XVergabe**-Standard, also genau eine dokumentierte
Bezugs-Schnittstelle fuer Bietersoftware. ⚠ **Diese Pfade werden hier bewusst NICHT
angesprochen** — der Betreiber hat sie fuer automatische Zugriffe gesperrt, und dieselbe
Zurueckhaltung gilt wie beim CAPTCHA auf vergabeportal.at. Oeffentliche Doku dazu gibt es
nicht (die Info-Seite kennt nur einen Nachrichten-RSS). Der richtige Weg ist die Anfrage ans
Beschaffungsamt; bis dahin der freie, ausdruecklich angebotene Download.

**URL-Formen im Bestand** (1.031 von 1.034 mit echter Kennung, kein nackter Host-Schwanz):

    519  /tenderdocuments.html?id=<N>     direkt die Unterlagenseite
    512  /tenderdetails.html?id=<N>       Vorgangsseite, Knopf fuehrt zur Unterlagenseite
      2  /tenderer/awardingauthorityinfo  ⚠ liegt unter dem robots-Disallow → ausgelassen

Beide Formen tragen dieselbe `id`, deshalb wird schlicht auf `tenderdocuments.html?id=<N>`
normalisiert statt dem Knopf zu folgen — ein Seitenaufruf weniger je Vergabe.

⚠ **Der ZIP-Link laesst sich nicht bauen, nur lesen.** Die Anwendung ist Wicket-basiert und
traegt den Seitenzustand IM Pfad
(`?0--documentsTableContainer-zipDownloadButton&id=…`). Die fuehrende Zahl ist ein
Versionszaehler der Sitzung; eine selbst zusammengesetzte URL laeuft ins Leere. Also: Seite
laden, `href` aus dem gerenderten Knopf lesen, in derselben Sitzung ausloesen.

Aufruf:  python3 -m govisor.docfetch_evergabe_online [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

from . import docfetch_queue as _queue

# ZEITGRENZE JE VORGANG. Playwrights `set_default_timeout` deckelt eine OPERATION; zehn
# Dateien à 33 MB bleiben jede darunter und brauchen zusammen eine halbe Stunde. Genau so
# ist am 2026-08-16 ein Abrufer bei Vorgang 33 von 60 stehengeblieben und hat den ganzen
# Schritt mitgerissen. Diese Grenze wirft EINEN Vorgang weg, nicht den Rest.
# 8 min: der groesste je geholte Vorgang war 636 MB, das Mittel liegt bei 8 MB.
VORGANG_FRIST_S = int(__import__("os").environ.get("GOVISOR_VORGANG_FRIST", "480"))

# Wie lange ein Lauf OHNE ein einziges neues Paket weiterlaufen darf. Der Fall, der am
# 2026-08-21 zwei Abrufer 54 Stunden hat laufen lassen, war nicht ein haengender Vorgang,
# sondern ein Abrufer, der beschaeftigt aussah und nichts mehr lieferte.
LEERLAUF_S = int(__import__("os").environ.get("GOVISOR_LEERLAUF", "3600"))


ROOT = Path(__file__).resolve().parent.parent

_HOST = "www.evergabe-online.de"
_WARTE_MS = 4000            # die Dateitabelle rendert nach
_HOEFLICH_MS = 1500
_DOWNLOAD_MS = 300000       # grosse Bauvergaben brauchen lange
# 500 MB wie bei den uebrigen Abrufern. Die 200-MB-Grenze der ersten Fassung verwarf eine
# 335-MB-Vergabe — „jede Vergabe ist wertvoll" (Sven), also lieber grosszuegig.
_MAX_ZIP = 500 * 1024**2
_LAUF_BUDGET_MB = 2000

_ID = re.compile(r"[?&]id=(\d+)")
_ZIP_TEXT = "Als ZIP-Datei herunterladen"


def ist_evergabe_online(url: str | None) -> bool:
    return bool(url) and f"//{_HOST}/" in url


def unterlagen_url(url: str | None) -> str | None:
    """Beliebige Vorgangs-URL → die Unterlagenseite. None, wenn keine Kennung drinsteht.

    ⚠ `/tenderer/…` wird ausgelassen: die `robots.txt` sperrt diesen Zweig ausdruecklich.
    Betrifft 2 von 1.034 Leads — die Regel ist es trotzdem wert, an einer Stelle zu stehen.
    """
    if not ist_evergabe_online(url) or "/tenderer/" in url:
        return None
    m = _ID.search(url)
    return f"https://{_HOST}/tenderdocuments.html?id={m.group(1)}" if m else None


def detailseite(url: str | None) -> str | None:
    """Unterlagenseite → Vorgangsseite. Dort steht der Grund, hier steht nur das Ergebnis."""
    if not url:
        return None
    return url.replace("tenderdocuments.html", "tenderdetails.html")


# Die Unterlagenseite antwortet auf jeden Fehlgriff mit demselben Satz. Er sagt NICHTS —
# nicht ob der Vorgang weg ist, ob die Frist durch ist oder ob die Unterlagen absichtlich
# zurueckgehalten werden.
_NICHTSSAGEND = "steht aktuell nicht zur Verfügung"

# ⚠ Die Vergabestelle kann Unterlagen bewusst zurueckhalten. Woertlich: „Aus Gruenden der
# Vertraulichkeit sind die Vergabeunterlagen nicht frei zugaenglich … Registrierte Nutzer
# koennen sie im Bereich ‚Meine e-Vergabe‘ anfordern." Das ist kein Fehlschlag und keine
# leere Vergabe, sondern ein Zugang, den wir nicht haben.
_VERTRAULICH = ("Vertraulichkeit", "nicht frei zugänglich")

_FRIST = re.compile(r"Abgabefrist Angebot:\s*\n+\s*(\d{2})\.(\d{2})\.(\d{4})")


def grund_von_detailseite(text: str, heute=None) -> dict:
    """Vorgangsseiten-Text → warum es keine Unterlagen gab.

    ⚠ Gemessen am 2026-08-24 ueber ALLE 23 Faelle, die als „keine Unterlagen" im Manifest
    standen: 17 Vertraulichkeit, 4 Abgabefrist verstrichen, 1 wirklich offen (ein Vorgang
    lag doppelt). Kein einziger davon war eine Vergabe ohne Unterlagen — was der Vermerk
    aber behauptete.
    """
    import datetime as _dt
    if not text or _NICHTSSAGEND in text:
        return {"status": "leer", "note": "auch die Vorgangsseite gibt nichts her"}
    if all(w in text for w in _VERTRAULICH):
        return {"status": "gated", "note": "Vertraulichkeit — nur auf Anforderung"}
    m = _FRIST.search(text)
    if m:
        frist = _dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if frist < (heute or _dt.date.today()):
            return {"status": "abgelaufen", "note": f"Abgabefrist {frist:%d.%m.%Y} verstrichen"}
    return {"status": "leer", "note": "kein Grund auf der Vorgangsseite"}


_KLICK = """u => { const a = document.createElement('a'); a.href = u; a.download = '';
                   document.body.appendChild(a); a.click(); }"""


def hole_vergabe(seite: str, pg, ziel: Path, dry_run: bool = False) -> dict:
    """Eine Vergabe → ZIP nach `ziel`. Gibt {status, bytes, n_files, note}."""
    pg.goto(seite, wait_until="domcontentloaded")
    pg.wait_for_timeout(_WARTE_MS)

    knopf = pg.evaluate(
        """(txt) => { const a = [...document.querySelectorAll('a')]
             .find(e => (e.textContent || '').includes(txt));
             return a ? a.href : null; }""", _ZIP_TEXT)
    # Dateizahl aus der Tabelle — sagt auch dann etwas, wenn der ZIP-Knopf fehlt.
    n_gelistet = pg.evaluate(
        """() => document.querySelectorAll("a[href*='-downloadLink']").length""")

    if not knopf:
        # Unterscheiden, sonst haelt man leere Vergaben fuer gescheiterte Abrufe — genau
        # dieser Fehler ist mir bei evergabe.de vier Mal passiert.
        txt = pg.inner_text("body")
        if re.search(r"nicht mehr verf|abgelaufen|beendet|zurückgezogen|aufgehoben", txt, re.I):
            return {"status": "abgelaufen", "bytes": 0, "n_files": 0, "note": ""}
        if n_gelistet:
            return {"status": "nur_einzeldateien", "bytes": 0, "n_files": n_gelistet,
                    "note": f"{n_gelistet} Dateien gelistet, kein ZIP-Knopf"}
        # ⚠ NICHT „keine Unterlagen" behaupten. Die Unterlagenseite antwortet auf jeden
        # Fehlgriff mit demselben nichtssagenden Satz; der Grund steht eine Seite weiter.
        # Ein Seitenaufruf mehr, und das nur fuer die wenigen Faelle, die hier ankommen.
        d = detailseite(seite)
        try:
            pg.goto(d, wait_until="domcontentloaded")
            pg.wait_for_timeout(_WARTE_MS)
            detail = pg.inner_text("body")
        except Exception as e:                           # noqa: BLE001
            return {"status": "fehler", "bytes": 0, "n_files": 0, "note": type(e).__name__}
        g = grund_von_detailseite(detail)
        return {"status": g["status"], "bytes": 0, "n_files": 0, "note": g["note"]}

    if dry_run:
        return {"status": "probe", "bytes": 0, "n_files": n_gelistet,
                "note": f"{n_gelistet} Dateien, ZIP vorhanden"}

    ziel.parent.mkdir(parents=True, exist_ok=True)
    with pg.expect_download(timeout=_DOWNLOAD_MS) as dl:
        pg.evaluate(_KLICK, knopf)
    pfad = Path(dl.value.path())
    groesse = pfad.stat().st_size
    if groesse > _MAX_ZIP:
        return {"status": "zu_gross", "bytes": groesse, "n_files": n_gelistet,
                "note": f"{groesse/1024**2:.0f} MB"}

    import zipfile
    tmp = ziel.with_suffix(".teil")
    dl.value.save_as(str(tmp))
    try:
        with zipfile.ZipFile(tmp) as z:
            n = len(z.namelist())
    except zipfile.BadZipFile:
        tmp.unlink(missing_ok=True)
        # Kein ZIP heisst meist: statt der Datei kam eine HTML-Fehlerseite. Als „leer" zu
        # buchen waere die teure Luege — dann suchte niemand nach der Ursache.
        return {"status": "kein_zip", "bytes": groesse, "n_files": 0,
                "note": "Antwort war kein ZIP"}
    tmp.replace(ziel)                                    # atomar
    return {"status": "downloaded", "bytes": groesse, "n_files": n, "note": ""}


def lauf(limit: int | None = None, dry_run: bool = False, country: str = "DE") -> dict:
    import duckdb
    from playwright.sync_api import sync_playwright

    L = ROOT / "data" / "gold" / country / "lead_export.parquet"
    out_root = ROOT / "data" / "docs" / country
    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT lead_id, documents_url FROM read_parquet('{L.as_posix()}')
        WHERE phase='open' AND documents_url LIKE '%//{_HOST}/%'
          AND deadline_date > current_date
          AND coalesce(procedure_kind, '') <> 'open_house'
        ORDER BY deadline_date ASC""").fetchall()
    con.close()

    # Mehrere Leads koennen auf dieselbe Vergabe zeigen (Lose). Einmal holen, dann in die
    # uebrigen Lead-Verzeichnisse kopieren — `docpipe` liest je Lead-Verzeichnis.
    offen: list[tuple[str, str, Path]] = []
    geschwister: dict[str, list[Path]] = {}
    gesehen: dict[str, str] = {}
    ohne_kennung = 0
    for lead_id, url in rows:
        seite = unterlagen_url(url)
        if not seite:
            ohne_kennung += 1
            continue
        kennung = _ID.search(seite).group(1)
        ziel = out_root / lead_id / f"Vergabeunterlagen_evgo_{kennung}.zip"
        if ziel.exists() and ziel.stat().st_size > 0:
            gesehen[seite] = lead_id
            continue                                     # idempotent
        if seite in gesehen:
            geschwister.setdefault(seite, []).append(ziel)
            continue
        gesehen[seite] = lead_id
        offen.append((lead_id, seite, ziel))
    # Frueher Gescheitertes ueberspringen. VOR dem Limit, sonst kappt das Limit auf
    # Kandidaten, die gleich wieder aussortiert werden.
    offen, _weg = _queue.filtere(offen, _queue.frueher(out_root, "evergabe_online"))
    if _weg:
        print(_queue.bericht(_weg))
    if limit:
        offen = offen[:limit]
    print(f"evergabe-online.de: {len(offen)} Vergaben zu holen (von {len(rows)} offenen Leads"
          + (f", {ohne_kennung} ohne nutzbare Kennung" if ohne_kennung else "") + ")")

    saetze: list[dict] = []
    geladen_mb = 0.0
    def _sichern():                     # laeuft, wenn die Wache hart abbricht
        if saetze and not dry_run:
            out_root.mkdir(parents=True, exist_ok=True)
            _queue.schreibe(out_root, "evergabe_online", saetze)

    with _queue.Wache("evergabe_online", vorgang_hart_s=0, leerlauf_s=LEERLAUF_S,
                      sichern=_sichern) as wache, sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(accept_downloads=True)
        pg = ctx.new_page()
        pg.set_default_timeout(60000)
        for i, (lead_id, seite, ziel) in enumerate(offen, 1):
            if geladen_mb >= _LAUF_BUDGET_MB:
                print(f"\n  Lauf-Budget erreicht — {len(offen) - i + 1} bleiben für morgen.")
                break
            try:
                with _queue.vorgang_frist(VORGANG_FRIST_S):
                    r = hole_vergabe(seite, pg, ziel, dry_run)
            except _queue.VorgangZuLang:
                r = {"status": "zu_lang", "bytes": 0, "n_files": 0,
                     "note": f"> {VORGANG_FRIST_S}s"}
            except Exception as e:                       # noqa: BLE001
                erste = str(e).strip().splitlines()[0] if str(e).strip() else ""
                r = {"status": "fehler", "bytes": 0, "n_files": 0,
                     "note": f"{type(e).__name__}: {erste}"[:160]}
            saetze.append({"lead_id": lead_id, "url": seite, **r})
            if r.get("status") == "downloaded":
                wache.erfolg()
            geladen_mb += r["bytes"] / 1024**2
            if r["status"] == "downloaded":
                for zwilling in geschwister.get(seite, []):
                    zwilling.parent.mkdir(parents=True, exist_ok=True)
                    zwilling.write_bytes(ziel.read_bytes())
            info = (f"{r['n_files']} Dateien  {r['bytes']/1024**2:.1f} MB"
                    if r["status"] == "downloaded" else f"{r['status']} ({r['note'][:44]})")
            print(f"  [{i}/{len(offen)}] {lead_id[:16]:<16} {info}", flush=True)
            pg.wait_for_timeout(_HOEFLICH_MS)
        ctx.close()
        b.close()

    ok = sum(1 for s in saetze if s["status"] == "downloaded")
    mb = sum(s["bytes"] for s in saetze) / 1e6
    print(f"\nevergabe-online.de: {len(saetze)} versucht · {ok} geladen · {mb:.1f} MB")
    schlecht: dict[str, int] = {}
    for s in saetze:
        if s["status"] != "downloaded":
            schlecht[s["status"]] = schlecht.get(s["status"], 0) + 1
    if schlecht:
        print("  ⚠ " + ", ".join(f"{k}={v}" for k, v in sorted(schlecht.items())))
    if saetze and not dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        _queue.schreibe(out_root, "evergabe_online", saetze)
    return {"versucht": len(saetze), "geladen": ok, "mb": mb}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true",
                   help="Seiten lesen und zeigen, was da wäre — nichts herunterladen, "
                        "nichts nach data/docs schreiben")
    a = p.parse_args(argv)
    lauf(a.limit, a.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
