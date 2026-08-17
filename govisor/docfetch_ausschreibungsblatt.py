"""Vergabeunterlagen vom **Deutschen Ausschreibungsblatt** (172 offene Leads).

**Der erste Eindruck war falsch — und zwar auf inzwischen vertraute Weise.** Die Seite wirbt
gross mit „Ausschreibung freischalten … Jetzt den passenden Tarif auswählen", und ich habe das
fuer eine Bezahlschranke vor den Unterlagen gehalten. Sie gilt der **Recherche** (vollstaendige
Bekanntmachung, KI-Chat, Filter, Suchprofile). Messbar: der Tarif-Knopf ist im DOM
`sichtbar: false`, der Knopf „Vergabeunterlagen" ist sichtbar. Dieselbe Fehldeutung wie bei
blb.nrw („Bestaetigung der Teilnahme" = E-Mail-Benachrichtigung) und evergabe-online („nur eine
erste Ansicht" = betrifft das Bieten). Wer hier nach Woertern statt nach Verhalten urteilt,
schreibt ein offenes Portal ab.

Gemessen 2026-08-15: **3 von 3** Vergaben anonym geladen, 7 / 25 / 34 MB.

**Der Weg ist dreistufig und sitzungsgebunden:**

1. Vorgangsseite ``/VN/<Kennung>`` laden
2. sichtbarer Link ``/lookup/documents/initiateDownload/<id>`` — leitet auf die Auswahlseite
   ``/ausschreibung/vu-als-zip-oder-bc`` weiter („ZIP oder BieterCockpit")
3. ``/lookup/download/getZip`` — ⚠ **ohne Kennung im Pfad**. Der Endpunkt weiss aus der
   Sitzung, welche Vergabe gemeint ist. Deshalb bekommt jede Vergabe einen **frischen
   Browser-Kontext**; sonst liefert Schritt 3 die Unterlagen der zuletzt angestossenen.

⚠ **Nicht klicken, sondern Adressen aufloesen.** Ein Consent-Banner (``div#cmpwrapper``) faengt
Klicks ab — ``ElementHandle.click`` laeuft in einen Timeout, waehrend die Seite voellig in
Ordnung ist. Die Weiterleitung wird deshalb per ``fetch(…, {redirect:'follow'}).url``
aufgeloest und direkt angesteuert. Das umgeht keine Zustimmung: gelesen wird ohnehin nur,
und der ZIP-Download ist der ausdruecklich angebotene anonyme Weg.

Aufruf:  python3 -m govisor.docfetch_ausschreibungsblatt [--limit N] [--dry-run]
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

_HOST = "www.deutsches-ausschreibungsblatt.de"
_ZIP_PFAD = "/lookup/download/getZip"
_WARTE_MS = 3500
_HOEFLICH_MS = 2000
_DOWNLOAD_MS = 300000
_MAX_ZIP = 500 * 1024**2
_LAUF_BUDGET_MB = 2000

_VN = re.compile(r"/VN/([A-Za-z0-9_.-]+)")

_KLICK = """u => { const a = document.createElement('a'); a.href = u; a.download = '';
                   document.body.appendChild(a); a.click(); }"""


def ist_ausschreibungsblatt(url: str | None) -> bool:
    return bool(url) and f"//{_HOST}/" in url


def kennung(url: str | None) -> str | None:
    """`documents_url` → Vergabenummer aus dem `/VN/`-Pfad. None, wenn keine drinsteht."""
    if not ist_ausschreibungsblatt(url):
        return None
    m = _VN.search(url)
    return m.group(1) if m else None


def hole_vergabe(seite: str, pg, ziel: Path, dry_run: bool = False) -> dict:
    """Eine Vergabe → ZIP nach `ziel`. Erwartet einen FRISCHEN Kontext (s. Modul-Docstring)."""
    pg.goto(seite, wait_until="domcontentloaded")
    pg.wait_for_timeout(_WARTE_MS)

    start = pg.evaluate(
        """() => { const a = [...document.querySelectorAll('a')]
             .find(e => /initiateDownload/.test(e.getAttribute('href') || ''));
             return a ? a.href : null; }""")
    if not start:
        # Kein Link heisst hier wirklich „keine Unterlagen veroeffentlicht" — der Knopf haengt
        # nicht an der Anmeldung, sonst waere er bei den gemessenen Faellen auch verschwunden.
        return {"status": "leer", "bytes": 0, "n_files": 0, "note": "kein Unterlagen-Link"}

    # Weiterleitung aufloesen statt klicken (Consent-Banner faengt Klicks ab).
    auswahl = pg.evaluate(
        """async (u) => { const r = await fetch(u, {redirect: 'follow'}); return r.url; }""",
        start)
    pg.goto(auswahl, wait_until="domcontentloaded")
    pg.wait_for_timeout(_WARTE_MS)

    hat_zip = pg.evaluate(
        """(p) => [...document.querySelectorAll('a')]
             .some(e => (e.getAttribute('href') || '').includes(p))""", _ZIP_PFAD)
    if not hat_zip:
        # Die Auswahlseite ohne ZIP-Option heisst: nur BieterCockpit, also Anmeldung.
        return {"status": "nur_cockpit", "bytes": 0, "n_files": 0,
                "note": "Auswahlseite ohne ZIP-Option"}
    if dry_run:
        return {"status": "probe", "bytes": 0, "n_files": 0, "note": "ZIP-Option vorhanden"}

    ziel.parent.mkdir(parents=True, exist_ok=True)
    with pg.expect_download(timeout=_DOWNLOAD_MS) as dl:
        pg.evaluate(_KLICK, f"https://{_HOST}{_ZIP_PFAD}")
    groesse = Path(dl.value.path()).stat().st_size
    if groesse > _MAX_ZIP:
        return {"status": "zu_gross", "bytes": groesse, "n_files": 0,
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
        vn = kennung(url)
        if not vn:
            ohne_kennung += 1
            continue
        ziel = out_root / lead_id / f"Vergabeunterlagen_dab_{vn}.zip"
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
    offen, _weg = _queue.filtere(offen, _queue.frueher(out_root, "ausschreibungsblatt"))
    if _weg:
        print(_queue.bericht(_weg))
    if limit:
        offen = offen[:limit]
    print(f"Ausschreibungsblatt: {len(offen)} Vergaben zu holen (von {len(rows)} offenen Leads"
          + (f", {ohne_kennung} ohne Kennung" if ohne_kennung else "") + ")")

    saetze: list[dict] = []
    geladen_mb = 0.0
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        for i, (lead_id, url, ziel) in enumerate(offen, 1):
            if geladen_mb >= _LAUF_BUDGET_MB:
                print(f"\n  Lauf-Budget erreicht — {len(offen) - i + 1} bleiben für morgen.")
                break
            # Frischer Kontext je Vergabe: getZip kennt keine Kennung, nur die Sitzung.
            ctx = b.new_context(accept_downloads=True)
            pg = ctx.new_page()
            pg.set_default_timeout(60000)
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
            finally:
                ctx.close()
            saetze.append({"lead_id": lead_id, "url": url, **r})
            geladen_mb += r["bytes"] / 1024**2
            if r["status"] == "downloaded":
                for zwilling in geschwister.get(url, []):
                    zwilling.parent.mkdir(parents=True, exist_ok=True)
                    zwilling.write_bytes(ziel.read_bytes())
            info = (f"{r['n_files']} Dateien  {r['bytes']/1024**2:.1f} MB"
                    if r["status"] == "downloaded" else f"{r['status']} ({r['note'][:44]})")
            print(f"  [{i}/{len(offen)}] {lead_id[:16]:<16} {info}", flush=True)
        b.close()

    ok = sum(1 for s in saetze if s["status"] == "downloaded")
    mb = sum(s["bytes"] for s in saetze) / 1e6
    print(f"\nAusschreibungsblatt: {len(saetze)} versucht · {ok} geladen · {mb:.1f} MB")
    schlecht: dict[str, int] = {}
    for s in saetze:
        if s["status"] != "downloaded":
            schlecht[s["status"]] = schlecht.get(s["status"], 0) + 1
    if schlecht:
        print("  ⚠ " + ", ".join(f"{k}={v}" for k, v in sorted(schlecht.items())))
    if saetze and not dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        _queue.schreibe(out_root, "ausschreibungsblatt", saetze)
    return {"versucht": len(saetze), "geladen": ok, "mb": mb}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true",
                   help="prüfen, ob die ZIP-Option da wäre — nichts herunterladen")
    a = p.parse_args(argv)
    lauf(a.limit, a.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
