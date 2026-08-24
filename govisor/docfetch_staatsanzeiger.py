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

_HOST = "www.staatsanzeiger-eservices.de"
_ANONYM = "input[type=submit][value='Anonym als Zip']"
# Die Absage des Portals, woertlich. Sie steht auf der Trefferliste selbst.
_ABSAGE = "Vergabeunterlagen stehen nicht zum Download bereit"

_ZIP = re.compile(r"https?://[^\"']*staatsanzeiger-eservices\.eu/[^\"']+\.zip", re.IGNORECASE)

_WARTE_MS = 8000
_NACH_KLICK_MS = 8000
# Der Frameset-Download erscheint waehrend des Seitenaufbaus; gemessen nach ~2 s.
_FRAMESET_MS = 6000
_HOEFLICH_MS = 2500
_MAX_ZIP = 500 * 1024**2
_LAUF_BUDGET_MB = 1500


def ist_staatsanzeiger(url: str | None) -> bool:
    return bool(url) and f"//{_HOST}/" in url


def _als_zip(ziel: Path, name: str, blob: bytes) -> int:
    """Eine Einzeldatei in ein ZIP legen. `docpipe` indiziert ausschliesslich ``*.zip``;
    eine lose PDF neben dem Vorgang wuerde niemand je lesen."""
    import io
    import zipfile

    ziel.parent.mkdir(parents=True, exist_ok=True)
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, blob)
    ziel.write_bytes(puffer.getvalue())
    return ziel.stat().st_size


def hole_vergabe(url: str, pg, ziel: Path, dry_run: bool = False) -> dict:
    """Eine Vergabe → Unterlagen-ZIP. Drei Stufen, s. Modulkopf."""
    # Die zweite URL-Form schiebt ihre Datei als DOWNLOAD waehrend des Seitenaufbaus heraus,
    # ohne dass jemand klickt (s. Frameset-Zweig unten). Der Horcher muss deshalb VOR dem
    # `goto` stehen.
    gefangen: list = []

    # ⚠ KEINE gebundene Methode (`gefangen.append`): Playwright heftet dem Horcher ein
    # eigenes Attribut an, und an einer eingebauten Methode geht das nicht
    # (`AttributeError: … no __dict__`). Eine gewoehnliche Funktion vertraegt es.
    def _sammeln(dl):
        gefangen.append(dl)
    pg.on("download", _sammeln)
    try:
        return _hole(url, pg, ziel, dry_run, gefangen)
    finally:
        try:
            pg.remove_listener("download", _sammeln)
        except Exception:                                     # noqa: BLE001
            pass


def _hole(url: str, pg, ziel: Path, dry_run: bool, gefangen: list) -> dict:
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
            # ⚠ **Der Inhalts-Frame IST erreichbar — aber nur ueber den Browser selbst.**
            # Gemessen am 2026-08-21: `GetFile2?z_param1=…` einzeln angefragt gibt
            # `http 200, content-length: 0` zurueck, AUCH mit den Sitzungs-Cookies des
            # Kontexts. Laedt dagegen der Browser den Frame im Zuge des Seitenaufbaus,
            # kommt `application/pdf` — und Playwright meldet einen Download. Der Server
            # unterscheidet also die Anfrage, nicht die Sitzung. Die alte Notiz
            # („Inhalts-Frame ohne Sitzung leer") war insofern nicht ganz richtig.
            #
            # ⚠ **Was kommt, ist die BEKANNTMACHUNG, nicht die Vergabeunterlagen.**
            # Acht Stichproben: sieben duenne Notice-PDFs (4 davon Ex-ante, die per
            # Definition keine Unterlagen haben), EINE mit 61 KB, in der
            # „Vergabeunterlagen" und „Zuschlagskriterien" ausgeschrieben stehen. Deshalb
            # ein eigener Status statt `downloaded`: die Zahl im Bericht soll nicht
            # behaupten, hier laegen Unterlagen.
            pg.wait_for_timeout(_FRAMESET_MS)
            if dry_run:
                return {"status": "probe", "bytes": 0, "n_files": len(gefangen),
                        "note": "Frameset, Bekanntmachung als Download"}
            if gefangen:
                dl = gefangen[0]
                name = (dl.suggested_filename or "Bekanntmachung").strip() or "Bekanntmachung"
                if "." not in name:
                    name += ".pdf"
                blob = Path(dl.path()).read_bytes()
                if blob:
                    n = _als_zip(ziel, name, blob)
                    return {"status": "nur_bekanntmachung", "bytes": n, "n_files": 1,
                            "note": f"{name} aus dem Frameset ({len(blob):,} B)"}
            return {"status": "frameset", "bytes": 0, "n_files": 0,
                    "note": "Frameset, aber kein Download erschienen"}
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
        # ⚠ Kein ZIP-Link ist noch kein Befund. Das Portal sagt in diesem Fall selbst,
        # woran es liegt — und zwar auf derselben Seite, nur ausserhalb des Bereichs, in
        # dem wir nach Links suchen. Gemessen am 2026-08-24 ueber die 11 so gemeldeten
        # Faelle: 7 lieferten beim zweiten Anlauf einen Link, 4 tragen diese Absage.
        rumpf = pg.evaluate("() => document.body.innerText")
        if _ABSAGE in rumpf:
            return {"status": "nicht_bereitgestellt", "bytes": 0, "n_files": 0,
                    "note": "Portal verweist an die Vergabestelle (INFO 75630)"}
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
    def _sichern():                     # laeuft, wenn die Wache hart abbricht
        if saetze and not dry_run:
            out_root.mkdir(parents=True, exist_ok=True)
            _queue.schreibe(out_root, "staatsanzeiger", saetze)

    with _queue.Wache("staatsanzeiger", vorgang_hart_s=0, leerlauf_s=LEERLAUF_S,
                      sichern=_sichern) as wache, sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(accept_downloads=True)
        pg = ctx.new_page()
        pg.set_default_timeout(60000)
        for i, (lead_id, url, ziel) in enumerate(offen, 1):
            if geladen_mb >= _LAUF_BUDGET_MB:
                print(f"\n  Lauf-Budget von {_LAUF_BUDGET_MB} MB erreicht — "
                      f"{len(offen) - i + 1} bleiben für den nächsten Lauf.")
                break
            try:
                with _queue.vorgang_frist(VORGANG_FRIST_S):
                    r = hole_vergabe(url, pg, ziel, dry_run)
            except _queue.VorgangZuLang:
                r = {"status": "zu_lang", "bytes": 0, "n_files": 0,
                     "note": f"> {VORGANG_FRIST_S}s"}
            except Exception as e:                       # noqa: BLE001
                r = {"status": "fehler", "bytes": 0, "n_files": 0, "note": type(e).__name__}
            saetze.append({"lead_id": lead_id, "url": url, **r})
            if r.get("status") == "downloaded":
                wache.erfolg()
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
