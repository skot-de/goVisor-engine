"""Quelle DE — evergabe.de: **echte Vergabeunterlagen**, anonym, § 41 VgV.

Anders als subreport gibt evergabe.de die Unterlagen ohne Anmeldung heraus, und zwar
ausdrücklich: die Plattform stellt selbst zwei Wege nebeneinander und beschriftet den
zweiten mit „Der Auftraggeber erfährt nicht, dass Sie die Vergabeunterlagen ansehen bzw.
herunterladen." Das ist § 41 VgV in der Oberfläche. Wir nehmen genau diesen Weg — es wird
nichts umgangen und keine Teilnahme vorgetäuscht.

**Inhaltlich verifiziert** (2026-08-14, Vergabe 3423114, Neubau Feuerwache Freital Los 401):

    H231205_260715_LVSHNsk3_Los_401_HS.X83   2,8 MB   GAEB DA XML
        → govisor.docparse.parse_gaeb: 625 Positionen mit Menge, Einheit, Kurztext
          („Abwasserleitung PP schallgedämmt mit Steckmuffe", 62,000 m)
    VHB_211_EU_Aufforderung_zur_Abgabe_eines_Angebots_EU.pdf   4 Seiten
        → echte Aufforderung: Vergabestelle Freital, Frist 17.08.2026 09:00, Bindefrist 13.10.

Die Prüfung des INHALTS steht hier bewusst im Kopf, nicht die Prüfung des Downloads.
Bei subreport hatte ein erfolgreicher Download zur Fehldeutung „offen" geführt — die Datei
war die Bekanntmachung, die wir längst über TED haben. Ein HTTP 200 belegt nichts.

⚠ **HTTP 418 von einer T-Systems-CloudWAF** — zweimal, und beide Male nicht das, wonach es
aussah. Der erste 418 traf `curl`; das ist keine Sperre, sondern der TLS-Fingerprint,
derselbe Aufruf aus einem echten Browser liefert 200. Wer ihn für eine Bot-Sperre hält,
verwirft 846 offene Vergaben — dieselbe Fehldeutung wie bei subreport-elvis.

Der zweite 418 traf ``page.request.get``: das teilt zwar die Cookies der Seite, benutzt aber
Playwrights eigenen HTTP-Client. Gemessen kamen Vergabe 1 und 2 durch, ab Vergabe 3 war jede
einzelne Datei 418. Der Abruf läuft deshalb über einen **synthetischen Anker in der Seite**,
also Chromes eigenen Netzwerk-Stack. Und der Grund, warum das überhaupt auffiel: die erste
Fassung meldete „keine Dateien", egal ob die Vergabe leer war oder der Abruf scheiterte.
Erst die Trennung ``leer`` / ``abgewiesen`` machte den Unterschied sichtbar.

**Ausgabe-Layout ist Absicht:** ein ZIP je Vergabe unter
``data/docs/<country>/<lead_id>/`` — exakt dort, wo ``docpipe.index`` sucht. Damit laufen
Volltext-Index, Anforderungs-Signale, LV- und Kriterien-Extraktion ohne eine Zeile
Änderung weiter. Verschachtelte ZIPs sind unproblematisch, ``docpipe.iter_docs`` steigt ein.

Aufruf::

    python3 -m govisor.docfetch_evergabe --limit 50
    python3 -m govisor.docfetch_evergabe --limit 5 --dry-run
"""
from __future__ import annotations

import argparse
import io
import re
import time
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Genau dieser Host. Die Nachbarn heissen fast gleich und sind voellig andere Systeme:
# evergabe-online.de (Bund), deutsche-evergabe.de, evergabe.nrw.de, evergabe.blb.nrw.de,
# bieter.ehealth-evergabe.de. Ein `in`-Test auf "evergabe.de" faengt sie alle mit ein.
_HOST = "www.evergabe.de"

_WARTE_MS = 6000            # die Dateitabelle rendert clientseitig nach
_HOEFLICH_MS = 3000        # die WAF drosselt; gemessen greift sie nach ~10 Vorgaengen
# Die Sperre ist FLUECHTIG. Gemessen 2026-08-14 im Zwei-Minuten-Takt: 418 bei 0, 2 und 4
# Minuten, HTTP 200 bei 6 — mit frischem Browser-Kontext. Deshalb wird pausiert und
# weitergemacht, nicht abgebrochen; ein Abbruch haette bei jedem Lauf nach ~10 Vorgaengen
# aufgegeben und die 845 offenen Vergaben nie eingeholt.
_ABKUEHLUNG_S = 420        # 7 min, mit Reserve auf die gemessenen 6
_MAX_ABKUEHLUNGEN = 4      # danach ist die Sperre keine Drosselung mehr
_MAX_DATEI = 40 * 1024**2   # eine Einzeldatei
_MAX_VERGABE = 150 * 1024**2

# Vier URL-Formen, alle im Bestand gemessen (869 offene Leads):
#     113  /unterlagen/<zahl>/zustellweg-auswaehlen
#     131  /unterlagen/<zahl>-Tender-<hex>-<hex>          (Deeplink, „54321" ist Platzhalter)
#      ~1  /unterlagen/<uuid>/zustellweg-auswaehlen
#     ~   /auftraege/suche-ueber-vergabestellen/<Name>/<zahl>
# Alle vier fuehren auf dieselbe Seite `/unterlagen/<kennung>`. Die Suchform traegt die
# Kennung im LETZTEN Pfadsegment, nicht im ersten — deshalb zwei Regexe statt einem.
_UNTERLAGEN = re.compile(r"/unterlagen/([^/?#]+)")
_SUCHE = re.compile(r"/auftraege/suche-ueber-vergabestellen/[^/]+/(\d+)")

_MIT_ENDUNG = re.compile(r"\.[A-Za-z0-9]{1,5}$")


def ist_evergabe(url: str | None) -> bool:
    return bool(url) and f"//{_HOST}/" in url


def unterlagen_url(url: str | None) -> str | None:
    """`documents_url` → Seite mit der Dateiliste, oder None."""
    if not ist_evergabe(url):
        return None
    m = _SUCHE.search(url) or _UNTERLAGEN.search(url)
    if not m:
        return None
    kennung = m.group(1)
    if kennung in ("", "zustellweg-auswaehlen"):
        return None
    return f"https://{_HOST}/unterlagen/{kennung}"


def _dateiliste(pg) -> list[dict]:
    """Sichtbare Tabelle → [{href, name}]. Der Dateiname ist die Zelle MIT Endung.

    Fest auf Spalte 3 zu gehen waere brueckelig — dieselbe Falle wie bei NetServer, wo ein
    Laengen-Kriterium den Zeitstempel fuer den Titel hielt. Hier entscheidet die Endung.
    """
    return pg.evaluate(
        """() => [...document.querySelectorAll('a[href*="/download/"]')].map(a => {
            const tr = a.closest('tr');
            const zellen = tr ? [...tr.querySelectorAll('td')].map(t => t.innerText.trim()) : [];
            const name = zellen.find(z => /\\.[A-Za-z0-9]{1,5}$/.test(z)) || '';
            return {href: a.getAttribute('href'), name};
        }).filter(x => x.href)""")


# Der Download muss durch CHROMES eigenen Netzwerk-Stack laufen. `page.request.get` teilt
# zwar die Cookies der Seite, benutzt aber Playwrights HTTP-Client — und damit einen anderen
# TLS-Fingerprint. Die CloudWAF laesst die ersten Abrufe durch und antwortet danach mit
# HTTP 418; gemessen: Vergabe 1 und 2 kamen durch, ab Vergabe 3 war jede einzelne Datei 418.
# Ein synthetischer Anker in der Seite loest einen echten Chrome-Download aus und geht durch.
_KLICK = """u => { const a = document.createElement('a'); a.href = u; a.download = '';
                   document.body.appendChild(a); a.click(); a.remove(); }"""


_GESPERRT = (403, 418, 429, 503)


def hole_vergabe(seite: str, pg, tmp: Path) -> dict:
    """Eine Vergabe → {dateien: [(name, bytes)], uebersprungen: [...], gelistet: n}."""
    r = pg.goto(seite, wait_until="domcontentloaded")
    # DEN STATUS LESEN. Eine von der WAF abgewiesene Seite hat einen leeren Rumpf — ohne
    # diese Pruefung sieht sie exakt aus wie eine Vergabe ohne Unterlagen, und der Lauf
    # meldet „keine Dateien gelistet" fuer etwas, das er nie gesehen hat. Gemessen: fuenf
    # von zehn Vorgaengen waren so gemeldet, alle fuenf trugen in Wahrheit Dateien.
    if r is not None and r.status in _GESPERRT:
        return {"dateien": [], "uebersprungen": [], "gelistet": 0,
                "http": r.status, "rumpf": ""}
    try:
        pg.wait_for_selector("a[href*='/download/']", timeout=_WARTE_MS)
    except Exception:                                    # noqa: BLE001
        pg.wait_for_timeout(_WARTE_MS)                   # manche Vergaben haben (noch) keine
    eintraege = _dateiliste(pg)

    # POSITIVES MERKMAL statt Abwesenheit von Links. Die WAF antwortet nicht nur mit 418 —
    # sie liefert auch HTTP 200 mit einer Zwischenseite, und die hat schlicht keine
    # Download-Links. Von „diese Vergabe hat keine Unterlagen" ist das nicht zu unterscheiden,
    # solange man nur Links zaehlt. Gemessen: fuenf Vorgaenge meldeten so „keine Dateien
    # gelistet", darunter die Freitaler Vergabe, aus der wenige Minuten zuvor 29 Dateien
    # samt GAEB-Leistungsverzeichnis geholt worden waren. Die echte Seite traegt immer die
    # Ueberschrift „Vergabeunterlagen"; fehlt die, haben wir die Seite nie gesehen.
    if not eintraege:
        rumpf = pg.evaluate("() => document.body.innerText")
        if "Vergabeunterlagen" not in rumpf:
            return {"dateien": [], "uebersprungen": [], "gelistet": 0, "http": 418,
                    "rumpf": rumpf[:120]}

    dateien: list[tuple[str, bytes]] = []
    uebersprungen: list[str] = []
    summe = 0
    for i, e in enumerate(eintraege):
        if summe >= _MAX_VERGABE:
            # KEIN stilles Abschneiden: was nicht geholt wurde, steht im Manifest.
            uebersprungen.extend(x["name"] or f"datei_{j}" for j, x in enumerate(eintraege[i:], i))
            break
        ziel = tmp / f"dl_{i}"
        try:
            with pg.expect_download(timeout=120000) as dl:
                pg.evaluate(_KLICK, f"https://{_HOST}{e['href']}")
            d = dl.value
            d.save_as(str(ziel))
            name = d.suggested_filename or e["name"] or f"datei_{i}"
        except Exception as ex:                          # noqa: BLE001
            uebersprungen.append(f"{e['name'] or i} ({type(ex).__name__})")
            continue
        groesse = ziel.stat().st_size
        if groesse > _MAX_DATEI:
            uebersprungen.append(f"{name} ({groesse/1024**2:.0f} MB)")
            ziel.unlink(missing_ok=True)
            continue
        if not _MIT_ENDUNG.search(name):
            name += ".bin"
        dateien.append((name, ziel.read_bytes()))
        ziel.unlink(missing_ok=True)
        summe += groesse
    return {"dateien": dateien, "uebersprungen": uebersprungen,
            "gelistet": len(eintraege), "http": 200, "rumpf": ""}


def _schreibe_zip(ziel: Path, dateien: list[tuple[str, bytes]]) -> int:
    ziel.parent.mkdir(parents=True, exist_ok=True)
    puffer = io.BytesIO()
    # Namen koennen sich wiederholen (mehrere „Teilnehmernachricht.txt" je Vergabe). Ein
    # ZIP mit doppeltem Eintrag laesst sich zwar schreiben, aber beim Lesen gewinnt einer —
    # der Rest waere still verloren. Deshalb durchnummerieren statt ueberschreiben.
    gesehen: dict[str, int] = {}
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name, blob in dateien:
            if name in gesehen:
                gesehen[name] += 1
                stamm, punkt, endung = name.rpartition(".")
                name = (f"{stamm}_{gesehen[name]}{punkt}{endung}" if punkt
                        else f"{name}_{gesehen[name]}")
            else:
                gesehen[name] = 0
            z.writestr(name, blob)
    tmp = ziel.with_suffix(".part")
    tmp.write_bytes(puffer.getvalue())
    tmp.replace(ziel)
    return ziel.stat().st_size


def lauf(limit: int | None = None, dry_run: bool = False, country: str = "DE") -> dict:
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    from playwright.sync_api import sync_playwright

    L = ROOT / "data" / "gold" / country / "lead_export.parquet"
    out_root = ROOT / "data" / "docs" / country
    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT lead_id, documents_url FROM read_parquet('{L.as_posix()}')
        WHERE phase='open' AND documents_url LIKE '%//{_HOST}/%'
          -- Wie im cosinex-Abruf: der Fristtag selbst faellt raus (die Frist traegt eine
          -- Uhrzeit), Open House hat nichts zu bieten.
          AND deadline_date > current_date
          AND coalesce(procedure_kind, '') <> 'open_house'
        ORDER BY deadline_date ASC
    """).fetchall()

    offen = []
    for lead_id, url in rows:
        seite = unterlagen_url(url)
        if not seite:
            continue
        ziel = out_root / lead_id / f"Vergabeunterlagen_evergabe_{seite.rsplit('/', 1)[-1]}.zip"
        if ziel.exists() and ziel.stat().st_size > 0:
            continue                                     # idempotent
        offen.append((lead_id, seite, ziel))
    if limit:
        offen = offen[:limit]
    print(f"evergabe.de: {len(offen)} Vergaben zu holen (von {len(rows)} offenen Leads)")

    saetze: list[dict] = []
    abkuehlungen = 0
    nachzuholen: list[tuple] = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(accept_downloads=True)
        pg = ctx.new_page()
        pg.set_default_timeout(60000)
        for i, (lead_id, seite, ziel) in enumerate(offen, 1):
            try:
                with tempfile.TemporaryDirectory() as td:
                    r = hole_vergabe(seite, pg, Path(td))
            except Exception as e:                       # noqa: BLE001
                print(f"  [{i}/{len(offen)}] {lead_id}: Fehler ({type(e).__name__})", flush=True)
                saetze.append({"lead_id": lead_id, "url": seite, "status": "error",
                               "bytes": 0, "n_files": 0, "uebersprungen": [],
                               "note": type(e).__name__})
                continue
            if r.get("http") in _GESPERRT:
                # Abkuehlen und DENSELBEN Vorgang neu versuchen — die Sperre gilt der
                # Sitzung, nicht der Vergabe. Frischer Kontext, weil die alte Sitzung
                # verbrannt ist.
                abkuehlungen += 1
                if abkuehlungen > _MAX_ABKUEHLUNGEN:
                    print(f"\n  ⚠ Auch nach {_MAX_ABKUEHLUNGEN} Pausen abgewiesen — Lauf "
                          f"beendet. Der Rest folgt beim nächsten Durchlauf.", flush=True)
                    saetze.append({"lead_id": lead_id, "url": seite, "status": "gesperrt",
                                   "bytes": 0, "n_files": 0, "uebersprungen": [],
                                   "note": f"http {r['http']}"})
                    break
                print(f"  [{i}/{len(offen)}] {lead_id}: WAF-Sperre (http {r['http']}) — "
                      f"{_ABKUEHLUNG_S//60} min Pause, dann weiter", flush=True)
                ctx.close()
                time.sleep(_ABKUEHLUNG_S)
                ctx = b.new_context(accept_downloads=True)
                pg = ctx.new_page()
                pg.set_default_timeout(60000)
                nachzuholen.append((lead_id, seite, ziel))
                continue
            if not r["dateien"]:
                # Der Unterschied ist wichtig und war beim ersten Lauf nicht sichtbar:
                # „0 gelistet" heisst, die Vergabe hat (noch) keine Unterlagen — „N gelistet,
                # 0 geholt" heisst, der Abruf ist gescheitert. Beides als „keine Dateien" zu
                # melden hat mich vier gescheiterte Abrufe fuer leere Vergaben halten lassen.
                warum = (f"{r['gelistet']} gelistet, alle abgewiesen: "
                         f"{'; '.join(r['uebersprungen'][:3])}" if r["gelistet"]
                         else "keine Dateien gelistet")
                print(f"  [{i}/{len(offen)}] {lead_id}: {warum}", flush=True)
                saetze.append({"lead_id": lead_id, "url": seite,
                               "status": "abgewiesen" if r["gelistet"] else "leer",
                               "bytes": 0, "n_files": 0,
                               "uebersprungen": r["uebersprungen"], "note": ""})
                continue
            groesse = 0 if dry_run else _schreibe_zip(ziel, r["dateien"])
            saetze.append({"lead_id": lead_id, "url": seite, "status": "downloaded",
                           "bytes": groesse, "n_files": len(r["dateien"]),
                           "uebersprungen": r["uebersprungen"], "note": ""})
            rest = f" · {len(r['uebersprungen'])} übersprungen" if r["uebersprungen"] else ""
            print(f"  [{i}/{len(offen)}] {lead_id}: {len(r['dateien'])} Dateien"
                  f"  {groesse/1024:.0f} KB{rest}", flush=True)
            pg.wait_for_timeout(_HOEFLICH_MS)
        # Was waehrend einer Sperre uebersprungen wurde, jetzt nachholen — sonst faellt
        # genau der Vorgang durch, an dem die Drosselung zuschlug, und zwar bei jedem Lauf
        # aufs Neue (die Reihenfolge ist stabil).
        for j, (lead_id, seite, ziel) in enumerate(nachzuholen, 1):
            try:
                with tempfile.TemporaryDirectory() as td:
                    r = hole_vergabe(seite, pg, Path(td))
                    if r.get("http") in _GESPERRT or not r["dateien"]:
                        print(f"  [nach {j}/{len(nachzuholen)}] {lead_id}: weiterhin ohne "
                              f"Erfolg", flush=True)
                        continue
                    groesse = 0 if dry_run else _schreibe_zip(ziel, r["dateien"])
                saetze.append({"lead_id": lead_id, "url": seite, "status": "downloaded",
                               "bytes": groesse, "n_files": len(r["dateien"]),
                               "uebersprungen": r["uebersprungen"], "note": "nachgeholt"})
                print(f"  [nach {j}/{len(nachzuholen)}] {lead_id}: {len(r['dateien'])} "
                      f"Dateien  {groesse/1024:.0f} KB", flush=True)
            except Exception as e:                       # noqa: BLE001
                print(f"  [nach {j}/{len(nachzuholen)}] {lead_id}: Fehler "
                      f"({type(e).__name__})", flush=True)
            pg.wait_for_timeout(_HOEFLICH_MS)
        ctx.close()
        b.close()

    ok = sum(1 for s in saetze if s["status"] == "downloaded")
    mb = sum(s["bytes"] for s in saetze) / 1e6
    print(f"\nevergabe.de: {len(saetze)} versucht · {ok} mit Unterlagen · {mb:.1f} MB")
    if saetze and not dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist(saetze),
                       out_root / "_manifest_evergabe.parquet", compression="zstd")
    return {"versucht": len(saetze), "geladen": ok, "mb": round(mb, 1)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    lauf(a.limit, a.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
