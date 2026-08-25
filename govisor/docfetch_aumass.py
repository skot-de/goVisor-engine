"""Quelle DE — Vergabeunterlagen von aumass, anonym.

Der sauberste Zugang, der an diesem Tag gefunden wurde: die Plattform stellt einen Link
bereit, der wörtlich **„Ohne Registrierung herunterladen."** heisst und auf einen
parametrisierten Endpunkt zeigt::

    /Document/GetDocument?doctype=allfiles&aumassid=<AV-Nummer>

Kein Modal, keine Weiche, keine Sitzungslogik — die AV-Nummer steht in der
``documents_url``. 288 offene Leads.

**Inhaltlich verifiziert** (2026-08-14, AV281953-EU, Landratsamt Landshut, Fassadenarbeiten):
24,00 MB, 8 Einträge, gegliedert in ``Nachträge/``, ``Automatisierte Nachträge/`` und
``Sonstige Vergabeunterlagen/``. Die Gliederung ist inhaltlich wertvoll — eine
``FristAenderung_…pdf`` unter „Automatisierte Nachträge" ist ein Terminsignal, kein
Beiwerk. Verschachtelte ZIPs sind kein Problem, ``docpipe.iter_docs`` steigt ein.

**URL-Formen** (alle im Bestand gemessen, 288 Leads)::

    /Veroeffentlichung/av281953-eu     klein geschrieben, Suffix -eu
    /Veroeffentlichung/AV281953-A      gross, Suffix -A
    /Veroeffentlichung/AV28195318-A    laengere Nummer

Der Endpunkt erwartet die Nummer in GROSSBUCHSTABEN — die URL trägt sie mal so, mal so.
Wer sie durchreicht wie vorgefunden, bekommt bei rund einem Drittel der Vorgänge nichts,
ohne dass eine Fehlermeldung darauf hinweist.

Ausgabe wie bei den übrigen Fetchern: ein ZIP je Vergabe unter
``data/docs/<country>/<lead_id>/``.

Aufruf::

    python3 -m govisor.docfetch_aumass --limit 20
    python3 -m govisor.docfetch_aumass --limit 3 --dry-run
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

_HOST = "plattform.aumass.de"
_ID = re.compile(r"/Veroeffentlichung/([A-Za-z0-9\-]+)", re.IGNORECASE)
_ENDPUNKT = ("https://" + _HOST +
             "/Document/GetDocument?doctype=allfiles&aumassid={}")

_WARTE_MS = 5000
_HOEFLICH_MS = 2500
_DOWNLOAD_MS = 300000
_MAX_ZIP = 500 * 1024**2
_LAUF_BUDGET_MB = 2000

# Ein synthetischer Anker in der Seite, damit der Download durch CHROMES Netzwerk-Stack
# laeuft. Dieselbe Loesung wie bei evergabe.de, und aus demselben Grund: ein eigener
# HTTP-Client hat einen anderen TLS-Fingerprint als die geladene Seite.
_KLICK = """u => { const a = document.createElement('a'); a.href = u; a.download = '';
                   document.body.appendChild(a); a.click(); a.remove(); }"""


def ist_aumass(url: str | None) -> bool:
    return bool(url) and f"//{_HOST}/" in url


def aumass_id(url: str | None) -> str | None:
    """`documents_url` → AV-Nummer in GROSSBUCHSTABEN, oder None.

    Die Grossschreibung ist kein Schoenheitsfehler: der Endpunkt liefert sonst nichts, und
    zwar ohne Fehlermeldung. Gemessen tragen 72 von 288 Leads die Nummer klein.
    """
    if not ist_aumass(url):
        return None
    m = _ID.search(url)
    return m.group(1).upper() if m else None


def hole_vergabe(url: str, pg, ziel: Path, dry_run: bool = False) -> dict:
    """Eine Vergabe → Unterlagen-ZIP."""
    nummer = aumass_id(url)
    if not nummer:
        return {"status": "fehler", "bytes": 0, "n_files": 0, "note": "keine AV-Nummer"}

    r = pg.goto(url, wait_until="domcontentloaded")
    if r is not None and r.status >= 400:
        return {"status": "fehler", "bytes": 0, "n_files": 0, "note": f"http {r.status}"}
    pg.wait_for_timeout(_WARTE_MS)

    # POSITIVES Merkmal: traegt die Seite den Abschnitt „Vergabeunterlagen"? Ohne diese
    # Pruefung sieht eine Vergabe ohne Unterlagen genauso aus wie eine falsch geladene Seite.
    rumpf = pg.evaluate("() => document.body.innerText")
    if "Vergabeunterlagen" not in rumpf:
        # NICHT als Fehler melden, wenn die Bekanntmachungsart gar keine Unterlagen kennt.
        # Gemessen an AV281974-A: eine „EX ANTE BEKANNTMACHUNG" — die kuendigt eine geplante
        # Direktvergabe an, es gibt nichts zu bieten und entsprechend nichts herunterzuladen.
        # Das als `fehler` zu fuehren wuerde eine korrekte Seite wie einen Ausfall aussehen
        # lassen und jeden Lauf mit falschen Warnungen belasten.
        oben = rumpf.upper()
        # Nach Fristende ersetzt aumass die ganze Seite durch EINEN Satz: „DIE ANGEBOTSFRIST
        # FUER DIE AUSSCHREIBUNG … IST ABGELAUFEN." Kein Unterlagen-Abschnitt, keine
        # Bekanntmachungsart — also fiel der Vorgang durch beide Pruefungen und landete als
        # `fehler`, obwohl nichts fehlgeschlagen war. 6 der 7 so gemeldeten Faelle waren das
        # (gemessen 2026-08-24); der siebte hatte inzwischen wieder Unterlagen.
        if "ANGEBOTSFRIST" in oben and "ABGELAUFEN" in oben:
            return {"status": "abgelaufen", "bytes": 0, "n_files": 0,
                    "note": "Angebotsfrist abgelaufen"}

        art = "unbekannt"
        for kennung in ("EX ANTE BEKANNTMACHUNG", "VORINFORMATION", "ZUSCHLAG",
                        "AUFHEBUNG", "BEKANNTMACHUNG VERGEBENER"):
            if kennung in oben:
                art = kennung.title()
                break
        if art != "unbekannt":
            return {"status": "ohne_unterlagen", "bytes": 0, "n_files": 0, "note": art}
        return {"status": "fehler", "bytes": 0, "n_files": 0,
                "note": "kein Unterlagen-Abschnitt"}
    if dry_run:
        return {"status": "probe", "bytes": 0, "n_files": 0, "note": nummer}

    try:
        with pg.expect_download(timeout=_DOWNLOAD_MS) as dl:
            pg.evaluate(_KLICK, _ENDPUNKT.format(nummer))
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
        # Kein ZIP heisst hier meist: der Endpunkt hat eine HTML-Seite geliefert, weil die
        # Nummer nicht passte. Als Fehler melden, nicht als leere Vergabe.
        tmp.unlink(missing_ok=True)
        return {"status": "fehler", "bytes": groesse, "n_files": 0, "note": "kein ZIP"}
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

    # Geschwister: 288 Leads zeigen auf nur 269 verschiedene Vergaben. Dieselbe Vergabe
    # zweimal zu ziehen ist bei 24–188 MB je Paket nicht nur Verschwendung, sondern
    # unnoetige Last auf einem fremden System.
    offen, geschwister, gesehen = [], {}, {}
    for lead_id, url in rows:
        nummer = aumass_id(url)
        if not nummer:
            continue
        ziel = out_root / lead_id / f"Vergabeunterlagen_aumass_{nummer}.zip"
        if ziel.exists() and ziel.stat().st_size > 0:
            gesehen[nummer] = lead_id
            continue
        if nummer in gesehen:
            geschwister.setdefault(nummer, []).append(ziel)
            continue
        gesehen[nummer] = lead_id
        offen.append((lead_id, url, ziel))
    # Frueher dauerhaft Gescheitertes ueberspringen — sonst blockiert dieselbe
    # Warteschlangenspitze jeden Lauf. VOR dem Limit, sonst kappt das Limit auf
    # Kandidaten, die gleich wieder aussortiert werden.
    offen, _weg = _queue.filtere(offen, _queue.frueher(out_root, "aumass"))
    if _weg:
        print(_queue.bericht(_weg))
    if limit:
        offen = offen[:limit]
    print(f"aumass-Unterlagen: {len(offen)} Vergaben zu holen (von {len(rows)} offenen Leads)")

    saetze, geladen_mb = [], 0.0
    def _sichern():                     # laeuft, wenn die Wache hart abbricht
        if saetze and not dry_run:
            out_root.mkdir(parents=True, exist_ok=True)
            _queue.schreibe(out_root, "aumass", saetze)

    with _queue.Wache("aumass", vorgang_hart_s=0, leerlauf_s=LEERLAUF_S,
                      sichern=_sichern) as wache, sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(accept_downloads=True)
        pg = ctx.new_page()
        pg.set_default_timeout(90000)
        for i, (lead_id, url, ziel) in enumerate(offen, 1):
            if geladen_mb >= _LAUF_BUDGET_MB:
                print(f"\n  Lauf-Budget von {_LAUF_BUDGET_MB} MB erreicht — "
                      f"{len(offen) - i + 1} Vergaben bleiben für den nächsten Lauf.")
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

    kopiert = 0
    for nummer, ziele in geschwister.items():
        quelle = out_root / gesehen[nummer] / f"Vergabeunterlagen_aumass_{nummer}.zip"
        if not quelle.exists():
            continue
        for z in ziele:
            if z.exists():
                continue
            z.parent.mkdir(parents=True, exist_ok=True)
            z.write_bytes(quelle.read_bytes())
            kopiert += 1
    if kopiert:
        print(f"  {kopiert} Kopien für Leads auf derselben Vergabe (kein zweiter Abruf)")

    ok = sum(1 for s in saetze if s["status"] == "downloaded")
    mb = sum(s["bytes"] for s in saetze) / 1e6
    print(f"\naumass-Unterlagen: {len(saetze)} versucht · {ok} geladen · {mb:.1f} MB")
    schlecht: dict[str, int] = {}
    for s in saetze:
        if s["status"] != "downloaded":
            schlecht[s["status"]] = schlecht.get(s["status"], 0) + 1
    if schlecht:
        print("  ⚠ " + ", ".join(f"{k}={v}" for k, v in sorted(schlecht.items())))
    if saetze and not dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        _queue.schreibe(out_root, "aumass", saetze)
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
