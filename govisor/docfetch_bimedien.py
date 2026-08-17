"""Vergabeunterlagen von **bi-medien.de** (110 offene Leads).

Der sauberste Zugang seit aumass: die Vorgangsseite traegt die Download-Adressen bereits im
Markup, und sie zeigen auf einen eigenen Dienst, der **anonym** ausliefert.

    publictender.bi-medien.de/api/Part/<uuid>       ← die ganze Vergabe als ZIP
    publictender.bi-medien.de/api/Document/<uuid>   ← Einzeldatei

Gemessen 2026-08-15: **2 von 2**, ``application/zip`` 1,4 MB und 38 MB, Einzel-PDFs http 200.
„Login" und „Kostenlos testen" stehen zwar auf der Seite, betreffen aber das Abo-Produkt
(Suche, Benachrichtigungen) — nicht die Unterlagen.

⚠ **Die Links sind da, aber zugeklappt.** Im DOM stehen sie mit ``sichtbar: false`` (Akkordeon
hinter dem Reiter „Unterlagen"), NICHT ``disabled``. Ein Klick auf den Reiter laeuft in einen
30-Sekunden-Timeout; das Auslesen der ``href``-Attribute funktioniert sofort. Wer hier klickt
statt liest, haelt ein offenes Portal fuer gesperrt — genau der Fehler, der mich bei diesem
Portal zuerst zwei Anlaeufe gekostet hat.

**Warum kein Zusammenbauen aus Einzeldateien.** Fehlt der ``Part``-Sammellink, meldet der
Abruf ehrlich ``nur_einzeldateien`` samt Zahl, statt selbst ein ZIP zu schnueren. Beide
gemessenen Vergaben hatten den Sammellink; ein ungetesteter Rueckfallpfad waere hier die
schlechtere Wahl als ein sichtbarer offener Punkt.

Aufruf:  python3 -m govisor.docfetch_bimedien [--limit N] [--dry-run]
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


ROOT = Path(__file__).resolve().parent.parent

_HOST = "bi-medien.de"
_API = "publictender.bi-medien.de/api"
_WARTE_MS = 3500
_HOEFLICH_MS = 1500
_DOWNLOAD_MS = 300000
_MAX_ZIP = 500 * 1024**2
_LAUF_BUDGET_MB = 2000

_ID = re.compile(r"/ausschreibungen/([A-Za-z0-9_-]+)")

_KLICK = """u => { const a = document.createElement('a'); a.href = u; a.download = '';
                   document.body.appendChild(a); a.click(); }"""


def ist_bimedien(url: str | None) -> bool:
    return bool(url) and f"//{_HOST}/" in url


def kennung(url: str | None) -> str | None:
    """`documents_url` → Vorgangs-Kennung aus dem Pfad. None, wenn keine drinsteht."""
    if not ist_bimedien(url):
        return None
    m = _ID.search(url)
    return m.group(1) if m else None


def _links(pg) -> tuple[list[str], list[str]]:
    """(Sammel-Links, Einzeldatei-Links) aus dem DOM — auch die zugeklappten."""
    alle = pg.evaluate(
        """(api) => [...new Set([...document.querySelectorAll('a')]
             .map(e => e.getAttribute('href') || '')
             .filter(h => h.includes(api)))]""", _API)
    return ([u for u in alle if "/api/Part/" in u],
            [u for u in alle if "/api/Document/" in u])


def hole_vergabe(seite: str, pg, ziel: Path, dry_run: bool = False) -> dict:
    """Eine Vergabe → ZIP nach `ziel`."""
    pg.goto(seite, wait_until="domcontentloaded")
    pg.wait_for_timeout(_WARTE_MS)
    sammel, einzeln = _links(pg)

    if not sammel and not einzeln:
        return {"status": "leer", "bytes": 0, "n_files": 0, "note": "keine Unterlagen"}
    if not sammel:
        return {"status": "nur_einzeldateien", "bytes": 0, "n_files": len(einzeln),
                "note": f"{len(einzeln)} Dateien, kein Sammel-Link"}
    if dry_run:
        return {"status": "probe", "bytes": 0, "n_files": len(einzeln),
                "note": f"Sammel-ZIP + {len(einzeln)} Einzeldateien"}

    ziel.parent.mkdir(parents=True, exist_ok=True)
    with pg.expect_download(timeout=_DOWNLOAD_MS) as dl:
        pg.evaluate(_KLICK, sammel[0])
    groesse = Path(dl.value.path()).stat().st_size
    if groesse > _MAX_ZIP:
        return {"status": "zu_gross", "bytes": groesse, "n_files": len(einzeln),
                "note": f"{groesse/1024**2:.0f} MB"}

    import zipfile
    tmp = ziel.with_suffix(".teil")
    dl.value.save_as(str(tmp))
    try:
        with zipfile.ZipFile(tmp) as z:
            n = len(z.namelist())
    except zipfile.BadZipFile:
        tmp.unlink(missing_ok=True)
        return {"status": "kein_zip", "bytes": groesse, "n_files": 0,
                "note": "Antwort war kein ZIP"}
    tmp.replace(ziel)
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

    offen: list[tuple[str, str, Path]] = []
    geschwister: dict[str, list[Path]] = {}
    gesehen: dict[str, str] = {}
    ohne_kennung = 0
    for lead_id, url in rows:
        k = kennung(url)
        if not k:
            ohne_kennung += 1
            continue
        ziel = out_root / lead_id / f"Vergabeunterlagen_bimedien_{k}.zip"
        if ziel.exists() and ziel.stat().st_size > 0:
            gesehen[url] = lead_id
            continue
        if url in gesehen:
            geschwister.setdefault(url, []).append(ziel)
            continue
        gesehen[url] = lead_id
        offen.append((lead_id, url, ziel))
    # Frueher Gescheitertes ueberspringen. VOR dem Limit, sonst kappt das Limit auf
    # Kandidaten, die gleich wieder aussortiert werden.
    offen, _weg = _queue.filtere(offen, _queue.frueher(out_root, "bimedien"))
    if _weg:
        print(_queue.bericht(_weg))
    if limit:
        offen = offen[:limit]
    print(f"bi-medien.de: {len(offen)} Vergaben zu holen (von {len(rows)} offenen Leads"
          + (f", {ohne_kennung} ohne Kennung" if ohne_kennung else "") + ")")

    saetze: list[dict] = []
    geladen_mb = 0.0
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(accept_downloads=True)
        pg = ctx.new_page()
        pg.set_default_timeout(60000)
        for i, (lead_id, url, ziel) in enumerate(offen, 1):
            if geladen_mb >= _LAUF_BUDGET_MB:
                print(f"\n  Lauf-Budget erreicht — {len(offen) - i + 1} bleiben für morgen.")
                break
            try:
                with _queue.vorgang_frist(VORGANG_FRIST_S):
                    r = hole_vergabe(url, pg, ziel, dry_run)
            except _queue.VorgangZuLang:
                r = {"status": "zu_lang", "bytes": 0, "n_files": 0,
                     "note": f"> {VORGANG_FRIST_S}s"}
            except Exception as e:                       # noqa: BLE001
                erste = str(e).strip().splitlines()[0] if str(e).strip() else ""
                r = {"status": "fehler", "bytes": 0, "n_files": 0,
                     "note": f"{type(e).__name__}: {erste}"[:160]}
            saetze.append({"lead_id": lead_id, "url": url, **r})
            geladen_mb += r["bytes"] / 1024**2
            if r["status"] == "downloaded":
                for zwilling in geschwister.get(url, []):
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
    print(f"\nbi-medien.de: {len(saetze)} versucht · {ok} geladen · {mb:.1f} MB")
    schlecht: dict[str, int] = {}
    for s in saetze:
        if s["status"] != "downloaded":
            schlecht[s["status"]] = schlecht.get(s["status"], 0) + 1
    if schlecht:
        print("  ⚠ " + ", ".join(f"{k}={v}" for k, v in sorted(schlecht.items())))
    if saetze and not dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        _queue.schreibe(out_root, "bimedien", saetze)
    return {"versucht": len(saetze), "geladen": ok, "mb": mb}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true",
                   help="Links zählen — nichts herunterladen")
    a = p.parse_args(argv)
    lauf(a.limit, a.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
