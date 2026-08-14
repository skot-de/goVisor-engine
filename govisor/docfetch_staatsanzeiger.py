"""Quelle DE — Vergabeunterlagen des Staatsanzeiger-eServices, anonym.

211 offene Leads. Die Plattform bietet den anonymen Weg ausdrücklich an — sie fragt auf
einer eigenen Seite „Wie wollen Sie die Vergabeunterlagen herunterladen?" und stellt
**„Anonym als Zip"** neben „Als Kunde im Profil".

**Der Weg ist DREISTUFIG**, und das ist der Grund, warum er beim ersten Anlauf verworfen
wurde::

    1. documents_url            /aJs/EFormsBekVuUrl?z_param=<n>   (Weiche)
    2. input[value='Anonym als Zip']  →  /aJs/DownlAsAnonym       (Trefferliste)
    3. dort <a href="https://www.staatsanzeiger-eservices.eu/L_<id>_NC-1_TVZ-<n>.zip">

Schritt 2 sieht aus wie ein Download-Knopf, ist aber eine Navigation: `expect_download`
läuft in einen Timeout, obwohl alles funktioniert. Genau daran scheiterte der erste
Versuch — und weil der Knopf ausserdem beim zweiten Seitenaufruf nicht im DOM stand
(ein zu enger XPath auf Blattknoten, kein Rendering-Problem), stand danach die Fehldiagnose
„die Seite rendert inkonsistent". Beides war falsch. ⚠ Der Knopf ist schlicht ein
``input[type=submit][value='Anonym als Zip']``.

Der ZIP liegt auf einem ANDEREN Host: ``…-eservices.eu`` statt ``.de``.

**Inhaltlich verifiziert** (2026-08-14, z_param=326772, Stadt Aschaffenburg,
Hilfeleistungslöschgruppenfahrzeug): 2,37 MB, 29 PDF, alle sauber extrahierbar —
``L 1240 Eigenerklärung zur Eignung``, ``L 211 EU Aufforderung zur Abgabe eines
Angebots``, ``L 212 EU Bewerbungsbedingungen``, ``Erklärung Bezug Russland``.

⚠ **Die Dateinamen tragen hier KEINE Information** — sie heissen ``3925835.pdf``,
``3925836.pdf`` … Damit läuft `doctypes.classify()` ins Leere (29 von 29 „sonstiges"),
anders als bei subreport, wo der Name 90 % trägt. Der Dokumenttyp steht stattdessen in der
ERSTEN ZEILE des Textes (`L 211 EU (VgV - Aufforderung zur Abgabe eines Angebots EU)`).
Wer hier nach Dateinamen typisiert, bekommt ein leeres Ergebnis und haelt es fuer eine
schlechte Quelle. Die Auswertung muss über den Inhalt laufen — was `signals-docs` ohnehin
tut.

Ausgabe wie bei den übrigen Fetchern: ein ZIP je Vergabe unter
``data/docs/<country>/<lead_id>/``.

Aufruf::

    python3 -m govisor.docfetch_staatsanzeiger --limit 20
    python3 -m govisor.docfetch_staatsanzeiger --limit 3 --dry-run
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from . import docfetch_queue as _queue

ROOT = Path(__file__).resolve().parent.parent

_HOST = "www.staatsanzeiger-eservices.de"
_ANONYM = "input[type=submit][value='Anonym als Zip']"
_ZIP = re.compile(r"https?://[^\"']*staatsanzeiger-eservices\.eu/[^\"']+\.zip", re.IGNORECASE)

_WARTE_MS = 8000
_NACH_KLICK_MS = 8000
_HOEFLICH_MS = 2500
_MAX_ZIP = 500 * 1024**2
_LAUF_BUDGET_MB = 1500


def ist_staatsanzeiger(url: str | None) -> bool:
    return bool(url) and f"//{_HOST}/" in url


def hole_vergabe(url: str, pg, ziel: Path, dry_run: bool = False) -> dict:
    """Eine Vergabe → Unterlagen-ZIP. Drei Stufen, s. Modulkopf."""
    r = pg.goto(url, wait_until="domcontentloaded")
    if r is not None and r.status >= 400:
        return {"status": "fehler", "bytes": 0, "n_files": 0, "note": f"http {r.status}"}
    pg.wait_for_timeout(_WARTE_MS)

    knopf = pg.query_selector(_ANONYM)
    if knopf is None:
        # ZWEITE URL-FORM: `besuJs/BekLanding4Bund?z_param=…` (56 der 211 Leads, alle aus
        # DÖE) liefert ein FRAMESET nach XHTML-1.0-DTD. `document.body.innerText` ist dort
        # naturgemaess leer — ein Frameset hat keinen Rumpf. Der Inhalts-Frame zeigt auf
        # `besuJs/GetFile2?z_param1=…`, und der gibt einzeln aufgerufen 0 Byte zurueck
        # (Sitzungsbindung). Gemessen, nicht vermutet.
        #
        # Das ist KEIN Fehler des Abrufs, sondern eine andere Oberflaeche — es als `fehler`
        # zu fuehren wuerde jeden Lauf mit 56 falschen Warnungen belasten, bis niemand mehr
        # hinsieht.
        if len(pg.frames) > 1:
            return {"status": "frameset", "bytes": 0, "n_files": 0,
                    "note": "BekLanding4Bund-Frameset, Inhalts-Frame ohne Sitzung leer"}
        # POSITIVES Merkmal fehlt. Traegt die Seite ueberhaupt die Weiche? Wenn nicht, sind
        # wir woanders gelandet — das ist etwas anderes als „keine Unterlagen".
        rumpf = pg.evaluate("() => document.body.innerText")
        if "Vergabeunterlagen" not in rumpf:
            return {"status": "fehler", "bytes": 0, "n_files": 0, "note": "keine Weiche"}
        return {"status": "ohne_anonym", "bytes": 0, "n_files": 0,
                "note": "Weiche ohne anonymen Weg"}

    # ⚠ KEIN `expect_download` hier. Der Knopf NAVIGIERT (auf /aJs/DownlAsAnonym); ein
    # Download-Warten laeuft in den Timeout, obwohl alles korrekt funktioniert.
    knopf.click()
    pg.wait_for_timeout(_NACH_KLICK_MS)

    treffer = _ZIP.search(pg.evaluate("() => document.documentElement.outerHTML"))
    if not treffer:
        return {"status": "leer", "bytes": 0, "n_files": 0,
                "note": "kein ZIP-Link auf der Trefferliste"}
    zip_url = treffer.group(0)
    if dry_run:
        return {"status": "probe", "bytes": 0, "n_files": 0, "note": zip_url[-42:]}

    # Der ZIP liegt auf `…-eservices.eu` und laesst sich direkt ziehen — kein Cookie, keine
    # Sitzung. Trotzdem ueber die Seite, damit derselbe Stack und dieselbe Herkunft gilt.
    try:
        antwort = pg.request.get(zip_url, timeout=180000)
        blob = antwort.body() if antwort.status == 200 else b""
    except Exception as e:                               # noqa: BLE001
        return {"status": "fehler", "bytes": 0, "n_files": 0, "note": type(e).__name__}
    if not blob:
        return {"status": "fehler", "bytes": 0, "n_files": 0, "note": "leere Antwort"}
    if len(blob) > _MAX_ZIP:
        return {"status": "zu_gross", "bytes": len(blob), "n_files": 0,
                "note": f"{len(blob)/1024**2:.0f} MB"}

    import io
    import zipfile
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            n = sum(1 for i in z.infolist() if not i.is_dir())
    except zipfile.BadZipFile:
        return {"status": "fehler", "bytes": len(blob), "n_files": 0, "note": "kein ZIP"}
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(blob)
    return {"status": "downloaded", "bytes": len(blob), "n_files": n, "note": ""}


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
          AND deadline_date > current_date
          AND coalesce(procedure_kind, '') <> 'open_house'
        ORDER BY deadline_date ASC""").fetchall()

    offen = [(lid, u, out_root / lid / "Vergabeunterlagen_stanz.zip") for lid, u in rows]
    offen = [x for x in offen if not (x[2].exists() and x[2].stat().st_size > 0)]
    # Frueher dauerhaft Gescheitertes ueberspringen — sonst blockiert dieselbe
    # Warteschlangenspitze jeden Lauf. VOR dem Limit, sonst kappt das Limit auf
    # Kandidaten, die gleich wieder aussortiert werden.
    offen, _weg = _queue.filtere(offen, _queue.frueher(out_root, "staatsanzeiger"))
    if _weg:
        print(_queue.bericht(_weg))
    if limit:
        offen = offen[:limit]
    print(f"Staatsanzeiger-Unterlagen: {len(offen)} Vergaben zu holen "
          f"(von {len(rows)} offenen Leads)")

    saetze, geladen_mb = [], 0.0
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context()
        pg = ctx.new_page()
        pg.set_default_timeout(60000)
        for i, (lead_id, url, ziel) in enumerate(offen, 1):
            if geladen_mb >= _LAUF_BUDGET_MB:
                print(f"\n  Lauf-Budget von {_LAUF_BUDGET_MB} MB erreicht — "
                      f"{len(offen) - i + 1} bleiben für den nächsten Lauf.")
                break
            try:
                r = hole_vergabe(url, pg, ziel, dry_run)
            except Exception as e:                       # noqa: BLE001
                r = {"status": "fehler", "bytes": 0, "n_files": 0, "note": type(e).__name__}
            saetze.append({"lead_id": lead_id, "url": url, **r})
            info = (f"{r['n_files']} Dateien  {r['bytes']/1024**2:.1f} MB"
                    if r["status"] == "downloaded" else f"{r['status']} ({r['note']})")
            print(f"  [{i}/{len(offen)}] {lead_id[:14]:<14} {info}", flush=True)
            geladen_mb += r["bytes"] / 1e6
            pg.wait_for_timeout(_HOEFLICH_MS)
        ctx.close()
        b.close()

    ok = sum(1 for s in saetze if s["status"] == "downloaded")
    mb = sum(s["bytes"] for s in saetze) / 1e6
    print(f"\nStaatsanzeiger: {len(saetze)} versucht · {ok} geladen · {mb:.1f} MB")
    schlecht: dict[str, int] = {}
    for s in saetze:
        if s["status"] != "downloaded":
            schlecht[s["status"]] = schlecht.get(s["status"], 0) + 1
    if schlecht:
        print("  ⚠ " + ", ".join(f"{k}={v}" for k, v in sorted(schlecht.items())))
    if saetze and not dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        _queue.schreibe(out_root, "staatsanzeiger", saetze)
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
