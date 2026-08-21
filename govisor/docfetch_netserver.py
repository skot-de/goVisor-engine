"""Quelle DE — Vergabeunterlagen der NetServer-Portale, anonym (§ 41 VgV).

Schliesst die zweitgrösste Dokumentenlücke: **1.055 offene Leads** liegen auf
NetServer-Portalen, deren *Bekanntmachungen* wir längst abholen (`govisor/netserver.py`),
deren *Unterlagen* aber bis 2026-08-14 niemand angefasst hatte. Nach Hosts::

    vergabe.autobahn.de 243 · had.de 197 · vergabe.landbw.de 97 + ausschreibungen 43
    vergabekooperation.berlin 85 · sachsen-vergabe 77 + evergabe.sachsen 71
    vergabe.hessen.de 74 · evergabe-mv 72 + vergabemarktplatz-mv 16
    saarvpsl.vmstart.de 48 · vergabe.bremen.de 20 · vergabe.hamburgwasser.de 12

**Der Weg, Schritt für Schritt reverse-engineert** (2026-08-14, verifiziert an
`vergabe.landbw.de`, Vergabe 26-63148 „Elektro-, Sicherheits- und Informationstechnische
Anlagen"):

1. Die ``documents_url`` zeigt auf ``TenderingProcedureDetails?function=_Details&TenderOID=…``
   — die **Bekanntmachung**. Dort steht ein Link „Unterlagen zur Ansicht herunterladen",
   und der hängt denselben ``TenderOID`` an ``&thContext=publications``.
2. Diese Seite trägt eine Tabelle „Vergabeunterlagen" mit einer Zeile je Version. Die
   Download-Spalte ist im Text LEER — die Schaltfläche ist ein Modal-Auslöser
   ``a.zipFileContents``. Wer nur nach Links mit Dateiendung sucht, findet hier nichts und
   schliesst fälschlich „gegated".
3. Das Modal listet die Unterlagen **gegliedert**: „Dateien für Angebot",
   „Leistungsverzeichnis", „Zusätzliche Informationen". Darin ``Alles auswählen`` und
   ``Auswahl herunterladen`` → ein ZIP.

**Inhaltlich verifiziert**, nicht nur der Download: 12,90 MB, 29 Dateien, darunter
``Leistungsverzeichnis/26-63148.X83`` → ``govisor.docparse.parse_gaeb`` liest **741
Positionen** mit Menge und Einheit („Energie-Schaltgerätekombination DIN EN IEC 61439-2",
1 St). Dazu die VHB-Formblätter 124/211/212/213/214/216/221/222/223/234/235/236/241/244/962.

⚠ **Nur die oberste Zeile nehmen.** Die Tabelle führt alle Versionen; die Seite sagt selbst
„Es gilt immer nur die aktuellste Version der Unterlagen." Gemessen lag Version 2
(11.08.2026) über Version 1 (10.07.2026). Eine ältere Version zu ziehen wäre kein
Teilerfolg, sondern eine falsche Leistungsbeschreibung.

Die Anmeldung auf diesen Seiten gilt **nicht** den Unterlagen: sie ist für Kommunikation,
Bieterfragen und Angebotsabgabe nötig — dieselbe Trennung wie bei cosinex. Der Text sagt es
wörtlich: „Sie haben an dieser Stelle die Möglichkeit, die Unterlagen zur Ansicht
herunterzuladen …" gefolgt von den Vorteilen einer Registrierung *für alles andere*.

Ausgabe wie bei den übrigen Fetchern: ein ZIP je Vergabe unter
``data/docs/<country>/<lead_id>/`` — dort sucht ``docpipe.index``.

Aufruf::

    python3 -m govisor.docfetch_netserver --limit 20
    python3 -m govisor.docfetch_netserver --limit 3 --dry-run
"""
from __future__ import annotations

import argparse
import re
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

# Alle Hosts der Familie. Bewusst eine Liste statt eines `NetServer`-im-Pfad-Tests: der
# Pfad steht zwar in fast allen URLs, aber `had.de` und `vergabe.hessen.de` weichen ab, und
# ein zu weiter Test würde fremde Portale einsammeln.
# ⚠ DIESE LISTE IST DIE AUSNAHME, NICHT DIE REGEL. Erkannt wird zuerst am PFAD
# `/NetServer/` — gemessen 2026-08-14, nachdem Sven nach den zwei fehlenden BW-Portalen
# fragte:
#
#     Hostliste allein      1.055 Leads
#     Pfad /NetServer/      1.524
#     Vereinigung           1.698   ← beides zusammen
#
# Die Liste uebersah 643 Leads auf 26 Hosts: tender24, vmstart, Fraunhofer, Deutsche
# Rentenversicherung, die Staedte Muenchen/Koeln/Duesseldorf/Frankfurt, LVR, LWL, Halle,
# BWB, BWI, UKSH … Der Pfad allein reicht aber auch nicht: 174 Leads liegen auf Hosts, die
# NetServer fahren, ohne den Pfad in der URL zu tragen (evergabe-mv 72, had.de 59,
# ausschreibungen.landbw 43). Deshalb BEIDES.
#
# Dieselbe Lehre wie bei den Unterlagen und bei den Landesportalen, hier zum dritten Mal am
# selben Tag: wer nach HOSTNAMEN sucht statt nach dem Merkmal der Plattform, findet immer
# nur die Portale, die er schon kannte.
#
# ⚠ `had.de` (Hessen) meldete beim ersten Lauf „keine Version gelistet". Dasselbe Portal
# braucht schon bei den Bekanntmachungen einen eigenen Pfad (`netserver.hole_had`) — es ist
# anders geskinnt als die uebrigen. Ob dort wirklich keine Unterlagen liegen oder nur die
# Tabelle anders heisst, ist UNGEPRUEFT. 197 offene Leads haengen daran.
HOSTS = (
    "vergabe.autobahn.de", "www.had.de", "vergabe.hessen.de",
    "vergabe.landbw.de", "ausschreibungen.landbw.de",
    "vergabekooperation.berlin", "saarvpsl.vmstart.de",
    "www.sachsen-vergabe.de", "www.evergabe.sachsen.de",
    "evergabe-mv.de", "www.vergabemarktplatz-mv.de",
    "vergabe.bremen.de", "vergabe.hamburgwasser.de",
)

_WARTE_MS = 6000
_MODAL_MS = 5000
_HOEFLICH_MS = 2000
# 500 MB, nicht 200. Beim ersten Lauf fiel eine Autobahn-Vergabe mit 335 MB durch diese
# Grenze — und eine ganze Vergabeunterlage wegzuwerfen, weil sie gross ist, widerspricht
# dem Grundsatz, dass jede Vergabe zaehlt. Platz ist da (1,6 TB frei bei 89 GB Bestand);
# die Grenze schuetzt nur noch gegen echte Ausreisser.
_MAX_ZIP = 500 * 1024**2
# Diese Pakete sind GROSS. Gemessen an den ersten beiden Vergaben: 64,9 MB (Bremen) und
# 65,5 MB (Autobahn) — Bauvergaben schleppen Plaene mit. Danach liefen vier Abrufe in
# Folge in Timeouts. Ob das Drosselung ist oder schlicht die Leitung, ist nicht
# unterscheidbar; in beiden Faellen ist die Antwort dieselbe: langsamer werden und den
# Lauf deckeln, statt 30 GB am Stueck ziehen zu wollen.
_LAUF_BUDGET_MB = 2000     # danach ist Schluss; der Rest kommt beim naechsten Lauf
_PAUSE_JE_100MB_MS = 8000  # groessenabhaengig nachatmen
_DOWNLOAD_MS = 300000      # 5 min; 65 MB brauchen mehr als die urspruenglichen 3

# DREI Parameternamen fuer DIESELBE Kennung. Gemessen an 1.698 Leads:
#     803  TenderingProcedureDetails?function=_Details&TenderOID=…
#     718  PublicationControllerServlet?function=Detail&TWOID=…
# Verifiziert: der TWOID-Wert funktioniert unveraendert als TenderOID — derselbe Vorgang,
# derselbe Download-Knopf. Wer nur `TenderOID` liest, verliert 42 % der Vorgaenge, und zwar
# lautlos: die URL sieht ja gueltig aus.
_OID = re.compile(r"(?:TenderOID|TWOID|TOID)=([^&#]+)")


# Die Servlet-Namen sind NetServer-eigen und ueberleben auch dann, wenn der Betreiber die
# Anwendung nicht unter `/NetServer/` haengt. Gemessen: `xvergabe.de` fuehrt sieben Vorgaenge
# ueber `PublicationControllerServlet?TWOID=` — reines NetServer, ohne den Pfad. Ein Test
# nur auf Pfad ODER Hostliste haette sie uebersehen, und zwar lautlos.
_SERVLETS = ("PublicationControllerServlet", "TenderingProcedureDetails",
             "PublicationSearchControllerServlet")


def ist_netserver(url: str | None) -> bool:
    """Pfad ODER Servlet-Name ODER Hostliste — alle drei, s. Begruendung an `HOSTS`."""
    if not url:
        return False
    return ("/NetServer/" in url
            or any(sv in url for sv in _SERVLETS)
            or any(f"//{h}/" in url for h in HOSTS))


def unterlagen_url(url: str | None) -> str | None:
    """`documents_url` → Seite mit der Unterlagen-Tabelle.

    Der Umweg über `thContext=publications` ist der Kern: die rohe `documents_url` zeigt auf
    die BEKANNTMACHUNG, und die trägt keine einzige Datei. Genau dort hatte die erste
    Stichprobe „keine Dateien, keine Knöpfe" gemeldet.
    """
    if not ist_netserver(url):
        return None
    m = _OID.search(url)
    if not m:
        return None
    # DAS SERVLET MUSS GETAUSCHT WERDEN, nicht nur der Parameter. Die Roh-URL kommt in zwei
    # Formen; die zweite zeigt auf ein ANDERES Servlet, das `function=_Details` gar nicht
    # kennt:
    #
    #     TenderingProcedureDetails?function=_Details&TenderOID=…
    #     PublicationControllerServlet?function=Detail&TWOID=…
    #
    # Wer nur den Parameter ersetzt und den Pfad stehen laesst, baut
    # `PublicationControllerServlet?function=_Details&TenderOID=…` — und bekommt HTTP 404.
    # Gemessen an drei Vorgaengen (Sachsen, Autobahn), bevor das auffiel. Der
    # Unterlagen-Bereich haengt IMMER an `TenderingProcedureDetails`.
    # Das Servlet wird IMMER auf `TenderingProcedureDetails` gesetzt — egal ob die Anwendung
    # unter `/NetServer/` haengt (die Regel) oder direkt an der Wurzel (xvergabe.de). Zuerst
    # stand hier ein Sonderfall nur fuer `/NetServer/`; xvergabe fiel durch und behielt
    # `PublicationControllerServlet?function=_Details` — dieselbe 404-URL wie beim ersten Mal,
    # nur an einer Stelle, die der Fix nicht erfasst hatte.
    pfad = url.split("?", 1)[0]
    wurzel = pfad.rsplit("/", 1)[0] + "/"
    return (f"{wurzel}TenderingProcedureDetails?function=_Details"
            f"&TenderOID={m.group(1)}&thContext=publications")


def hole_vergabe(seite: str, pg, ziel: Path, dry_run: bool = False) -> dict:
    """Eine Vergabe → Unterlagen-ZIP. Gibt {status, bytes, n_files, note}."""
    r = pg.goto(seite, wait_until="domcontentloaded")
    if r is not None and r.status >= 400:
        return {"status": "fehler", "bytes": 0, "n_files": 0, "note": f"http {r.status}"}
    pg.wait_for_timeout(_WARTE_MS)

    knoepfe = pg.query_selector_all("a.zipFileContents")
    if not knoepfe:
        # POSITIVES Merkmal pruefen, statt aus der Abwesenheit zu schliessen. Traegt die
        # Seite ueberhaupt den Unterlagen-Abschnitt? Wenn ja, hat die Vergabe wirklich
        # keine Dateien; wenn nein, sind wir auf der falschen Seite gelandet.
        rumpf = pg.evaluate("() => document.body.innerText")
        if "Vergabeunterlagen" not in rumpf:
            return {"status": "fehler", "bytes": 0, "n_files": 0,
                    "note": "kein Unterlagen-Abschnitt — falsche Seite?"}
        return {"status": "leer", "bytes": 0, "n_files": 0, "note": "keine Version gelistet"}

    # NUR die oberste Zeile: hoechste Versionsnummer, und die Seite sagt selbst, dass nur
    # die aktuellste gilt.
    knoepfe[0].click()
    pg.wait_for_timeout(_MODAL_MS)
    try:
        pg.click("#detailModal input[value='Alles auswählen']")
        pg.wait_for_timeout(1500)
    except Exception:                                    # noqa: BLE001
        pass                                             # manche Modals haben alles vorgewaehlt
    if dry_run:
        namen = pg.evaluate("""() => [...document.querySelectorAll('#detailModal a')]
            .map(a => (a.innerText || '').trim()).filter(x => /\\.[a-z0-9]{2,5}$/i.test(x))""")
        return {"status": "probe", "bytes": 0, "n_files": len(namen),
                "note": ", ".join(namen[:3])}

    try:
        with pg.expect_download(timeout=_DOWNLOAD_MS) as dl:
            pg.click("#detailModal input[type=submit]")
        d = dl.value
        ziel.parent.mkdir(parents=True, exist_ok=True)
        tmp = ziel.with_suffix(".part")
        d.save_as(str(tmp))
    except Exception as e:                               # noqa: BLE001
        return {"status": "fehler", "bytes": 0, "n_files": 0, "note": type(e).__name__}

    groesse = tmp.stat().st_size
    if groesse > _MAX_ZIP:
        tmp.unlink(missing_ok=True)
        return {"status": "zu_gross", "bytes": groesse, "n_files": 0,
                "note": f"{groesse/1024**2:.0f} MB"}
    import zipfile
    try:
        with zipfile.ZipFile(tmp) as z:
            n = sum(1 for i in z.infolist() if not i.is_dir())
    except zipfile.BadZipFile:
        tmp.unlink(missing_ok=True)
        return {"status": "fehler", "bytes": groesse, "n_files": 0, "note": "defektes ZIP"}
    tmp.replace(ziel)
    return {"status": "downloaded", "bytes": groesse, "n_files": n, "note": ""}


def lauf(limit: int | None = None, dry_run: bool = False, country: str = "DE") -> dict:
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    from playwright.sync_api import sync_playwright

    L = ROOT / "data" / "gold" / country / "lead_export.parquet"
    out_root = ROOT / "data" / "docs" / country
    con = duckdb.connect()
    # Pfad ODER Hostliste — dieselbe Regel wie `ist_netserver`. Stand die Abfrage nur auf
    # der Hostliste, lief der Fetcher ueber 1.055 statt 1.698 Vorgaenge, ohne dass irgendwo
    # eine Zahl fehlte: sie waren schlicht nie in der Auswahl.
    wo = ("documents_url LIKE '%/NetServer/%' OR "
          + " OR ".join(f"documents_url LIKE '%{sv}%'" for sv in _SERVLETS) + " OR "
          + " OR ".join(f"documents_url LIKE '%//{h}/%'" for h in HOSTS))
    rows = con.execute(f"""
        SELECT lead_id, documents_url FROM read_parquet('{L.as_posix()}')
        WHERE phase='open' AND documents_url IS NOT NULL AND ({wo})
          -- Wie in allen Fetchern: Fristtag raus (die Frist traegt eine Uhrzeit),
          -- Open House hat nichts zu bieten.
          AND deadline_date > current_date
          AND coalesce(procedure_kind, '') <> 'open_house'
        ORDER BY deadline_date ASC""").fetchall()

    offen = []
    for lead_id, url in rows:
        seite = unterlagen_url(url)
        if not seite:
            continue
        oid = _OID.search(seite).group(1)[-24:]
        ziel = out_root / lead_id / f"Vergabeunterlagen_ns_{oid}.zip"
        if ziel.exists() and ziel.stat().st_size > 0:
            continue                                     # idempotent
        offen.append((lead_id, seite, ziel))
    # Frueher dauerhaft Gescheitertes ueberspringen — sonst blockiert dieselbe
    # Warteschlangenspitze jeden Lauf. VOR dem Limit, sonst kappt das Limit auf
    # Kandidaten, die gleich wieder aussortiert werden.
    offen, _weg = _queue.filtere(offen, _queue.frueher(out_root, "netserver"))
    if _weg:
        print(_queue.bericht(_weg))
    if limit:
        offen = offen[:limit]
    print(f"NetServer-Unterlagen: {len(offen)} Vergaben zu holen (von {len(rows)} offenen Leads)")

    saetze = []
    geladen_mb = 0.0
    def _sichern():                     # laeuft, wenn die Wache hart abbricht
        if saetze and not dry_run:
            out_root.mkdir(parents=True, exist_ok=True)
            _queue.schreibe(out_root, "netserver", saetze)

    with _queue.Wache("netserver", vorgang_hart_s=0, leerlauf_s=LEERLAUF_S,
                      sichern=_sichern) as wache, sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(accept_downloads=True)
        pg = ctx.new_page()
        pg.set_default_timeout(90000)
        for i, (lead_id, seite, ziel) in enumerate(offen, 1):
            if geladen_mb >= _LAUF_BUDGET_MB:
                print(f"\n  Lauf-Budget von {_LAUF_BUDGET_MB} MB erreicht — "
                      f"{len(offen) - i + 1} Vergaben bleiben für den nächsten Lauf.")
                break
            try:
                with _queue.vorgang_frist(VORGANG_FRIST_S):
                    r = hole_vergabe(seite, pg, ziel, dry_run)
            except _queue.VorgangZuLang:
                r = {"status": "zu_lang", "bytes": 0, "n_files": 0,
                     "note": f"> {VORGANG_FRIST_S}s"}
            except Exception as e:                       # noqa: BLE001
                r = {"status": "fehler", "bytes": 0, "n_files": 0, "note": type(e).__name__}
            host = seite.split("/")[2]
            saetze.append({"lead_id": lead_id, "host": host, "url": seite, **r})
            if r.get("status") == "downloaded":
                wache.erfolg()
            info = (f"{r['n_files']} Dateien  {r['bytes']/1024**2:.1f} MB"
                    if r["status"] == "downloaded" else f"{r['status']} ({r['note']})")
            print(f"  [{i}/{len(offen)}] {host[:24]:<24} {lead_id[:14]:<14} {info}", flush=True)
            mb = r["bytes"] / 1e6
            geladen_mb += mb
            # Nach einem grossen Paket laenger warten als nach einem kleinen.
            pg.wait_for_timeout(_HOEFLICH_MS + int(mb / 100 * _PAUSE_JE_100MB_MS))
        ctx.close()
        b.close()

    ok = sum(1 for s in saetze if s["status"] == "downloaded")
    mb = sum(s["bytes"] for s in saetze) / 1e6
    print(f"\nNetServer-Unterlagen: {len(saetze)} versucht · {ok} geladen · {mb:.1f} MB")
    # KEIN stilles Abschneiden: was scheiterte, wird nach Host aufgeschluesselt — die
    # Portale sind verschieden genug, dass ein Ausfall meist EINEN Host trifft.
    schlecht = {}
    for s in saetze:
        if s["status"] != "downloaded":
            schlecht.setdefault(s["host"], []).append(s["status"])
    for h, st in schlecht.items():
        print(f"  ⚠ {h}: {len(st)}× {', '.join(sorted(set(st)))}")
    if saetze and not dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        _queue.schreibe(out_root, "netserver", saetze)
    return {"versucht": len(saetze), "geladen": ok, "mb": round(mb, 1)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true",
                   help="Modal öffnen und Dateiliste zeigen, nichts herunterladen")
    a = p.parse_args(argv)
    lauf(a.limit, a.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
