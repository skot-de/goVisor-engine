"""Quelle CH — Vergabeunterlagen von simap.ch, **mit Konto**.

Die Schweiz hängt vollständig an einer Plattform: **alle 889 offenen CH-Leads mit
Unterlagen-Link zeigen auf `simap.ch`**. Ein Connector deckt damit 100 % des Landes ab —
das beste Verhältnis im ganzen Projekt.

**Warum mit Konto.** simap.ch sagt es auf der Vorgangsseite selbst: „Um Unterlagen
herunterzuladen, müssen Sie als Benutzer registriert und eingeloggt sein." Das wurde
2026-08-14 nachgeprüft, nachdem sich an diesem Tag vier vermeintliche Sperren als eigene
Fehldeutung erwiesen hatten — hier ist es eine echte. Das Feld „Bezugsquelle für
Ausschreibungsunterlagen" nennt bei 2 von 6 Vorgängen simap.ch selbst, bei 3 fehlt es, bei
1 steht eine externe Adresse (ebenfalls mit Anmeldung). Kein Umweg.

**Zugangsdaten liegen NICHT im Code und nicht in diesem Repository.**
Sie kommen aus ``.secrets/simap.txt`` — zwei Zeilen, wie bei Supabase::

    govisor@example.ch
    <passwort>

Die Datei ist gitignored und wird von diesem Modul nur gelesen, nie geschrieben und nie
ausgegeben. Fehlt sie, bricht der Lauf mit einer klaren Meldung ab, statt anonym
weiterzulaufen und lauter leere Ergebnisse zu melden.

Die Anmeldung läuft über **Keycloak** (`/auth/realms/simap/protocol/openid-connect/auth`),
Felder ``#username`` / ``#password`` / ``#kc-login``. Einmal je Lauf, danach trägt der
Browser-Kontext die Sitzung.

⚠ **UNGETESTET bis zum ersten angemeldeten Lauf.** Der Weg hinter der Anmeldung — wie die
Dateien konkret ausgeliefert werden, ob einzeln oder als Paket — ist an einem eingeloggten
Vorgang noch nicht gemessen worden. Alles bis zur Anmeldung ist geprüft, alles danach ist
begründete Annahme. Der erste Lauf wird das zeigen; bis dahin darf niemand die Zahlen aus
diesem Modul zitieren.

⚠ **Nutzungsbedingungen.** Ein Konto zu haben und es einen automatischen Abruf benutzen zu
lassen sind zwei verschiedene Dinge. Vor dem ersten regelmässigen Lauf gehören die AGB von
simap.ch gelesen — das ist eine Vertrags-, keine Technikfrage.

Aufruf::

    python3 -m govisor.simap_docs --limit 5 --dry-run    # nur anmelden und die Seite lesen
    python3 -m govisor.simap_docs --limit 20
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZUGANG = ROOT / ".secrets" / "simap.txt"

_LOGIN = "https://www.simap.ch/de/provider/login"
_HOST = "www.simap.ch"

_WARTE_MS = 8000
_TAB_MS = 6000
_HOEFLICH_MS = 2500
_DOWNLOAD_MS = 300000
_MAX_ZIP = 500 * 1024**2
_LAUF_BUDGET_MB = 1500

_ENDUNGEN = ("pdf", "zip", "doc", "docx", "xls", "xlsx", "rtf", "odt", "txt", "dwg", "7z")
_MIT_ENDUNG = re.compile(r"\.(?:" + "|".join(_ENDUNGEN) + r")$", re.IGNORECASE)


def ist_simap(url: str | None) -> bool:
    return bool(url) and f"//{_HOST}/" in url


def zugang() -> tuple[str, str]:
    """`.secrets/simap.txt` → (Benutzer, Passwort).

    Bewusst KEIN anonymer Rueckfallpfad: ohne Konto liefert simap.ch nichts, und ein Lauf,
    der das nicht merkt, meldet 889-mal „keine Dateien" und sieht aus wie ein Portalproblem.
    """
    if not ZUGANG.exists():
        raise SystemExit(
            f"Zugangsdaten fehlen: {ZUGANG}\n"
            "  Zwei Zeilen anlegen — Benutzername, dann Passwort:\n"
            "    printf 'BENUTZER\\nPASSWORT\\n' > .secrets/simap.txt && chmod 600 .secrets/simap.txt\n"
            "  Die Datei ist gitignored und wird nur gelesen.")
    zeilen = [z.strip() for z in ZUGANG.read_text(encoding="utf-8").splitlines() if z.strip()]
    if len(zeilen) < 2:
        raise SystemExit(f"{ZUGANG}: erwartet zwei Zeilen (Benutzer, Passwort).")
    return zeilen[0], zeilen[1]


def anmelden(pg) -> bool:
    """Einmal je Lauf. Gibt True, wenn die Sitzung steht.

    Der Wert des Passworts wird nirgends ausgegeben — auch nicht im Fehlerfall.
    """
    benutzer, passwort = zugang()
    pg.goto(_LOGIN, wait_until="domcontentloaded")
    pg.wait_for_timeout(_WARTE_MS)
    try:
        pg.fill("#username", benutzer)
        pg.fill("#password", passwort)
        pg.click("#kc-login")
    except Exception as e:                               # noqa: BLE001
        print(f"  ⚠ Anmeldeformular nicht bedienbar ({type(e).__name__}) — "
              f"hat simap.ch die Maske geändert?")
        return False
    pg.wait_for_timeout(_WARTE_MS)
    # POSITIVES Merkmal: sind wir vom Keycloak-Pfad weg? Ein fehlgeschlagener Login bleibt
    # dort stehen und zeigt eine Fehlermeldung — ohne diese Pruefung liefe der ganze Lauf
    # anonym weiter und meldete lauter leere Vorgaenge.
    if "/auth/realms/" in pg.url:
        rumpf = pg.evaluate("() => document.body.innerText")[:200].replace("\n", " ")
        print(f"  ⚠ Anmeldung fehlgeschlagen. Seite meldet: {rumpf[:120]}")
        return False
    return True


def hole_vergabe(url: str, pg, ziel: Path, dry_run: bool = False) -> dict:
    """Eine Vergabe → Unterlagen. Setzt eine bestehende Sitzung voraus."""
    r = pg.goto(url, wait_until="domcontentloaded")
    if r is not None and r.status >= 400:
        return {"status": "fehler", "bytes": 0, "n_files": 0, "note": f"http {r.status}"}
    pg.wait_for_timeout(_WARTE_MS)

    # Der Unterlagen-Abschnitt ist ein Menuepunkt, der nicht sichtbar sein muss —
    # deshalb ueber JS klicken statt ueber den sichtbarkeitsgepruften Weg.
    pg.evaluate("""() => [...document.querySelectorAll('button,a')]
        .filter(e => /^Unterlagen$/i.test((e.innerText || '').trim())).forEach(e => e.click())""")
    pg.wait_for_timeout(_TAB_MS)

    rumpf = pg.evaluate("() => document.body.innerText")
    if "registriert und eingeloggt" in rumpf:
        # Die Sitzung greift auf DIESER Seite nicht — das ist etwas anderes als „keine
        # Unterlagen" und muss getrennt sichtbar bleiben.
        return {"status": "nicht_angemeldet", "bytes": 0, "n_files": 0,
                "note": "Seite verlangt weiterhin Anmeldung"}

    eintraege = pg.evaluate(
        """() => [...document.querySelectorAll('a,button')]
             .map(e => ({name: (e.innerText || '').trim(),
                         ref: e.getAttribute('href') || ''}))
             .filter(x => x.name && /\\.[a-z0-9]{2,5}$/i.test(x.name))""")
    if not eintraege:
        if "Unterlagen" not in rumpf:
            return {"status": "fehler", "bytes": 0, "n_files": 0, "note": "kein Unterlagen-Bereich"}
        return {"status": "leer", "bytes": 0, "n_files": 0, "note": "keine Dateien gelistet"}
    if dry_run:
        return {"status": "probe", "bytes": 0, "n_files": len(eintraege),
                "note": ", ".join(e["name"] for e in eintraege[:3])}

    import io
    import zipfile
    puffer = io.BytesIO()
    n = 0
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
        for e in eintraege:
            try:
                with pg.expect_download(timeout=_DOWNLOAD_MS) as dl:
                    pg.click(f"text={e['name']}")
                d = dl.value
                tmp = ziel.parent / f".teil_{n}"
                ziel.parent.mkdir(parents=True, exist_ok=True)
                d.save_as(str(tmp))
                name = d.suggested_filename or e["name"]
                if not _MIT_ENDUNG.search(name):
                    name += ".bin"
                z.writestr(name, tmp.read_bytes())
                tmp.unlink(missing_ok=True)
                n += 1
            except Exception:                            # noqa: BLE001
                continue
    if not n:
        return {"status": "abgewiesen", "bytes": 0, "n_files": 0,
                "note": f"{len(eintraege)} gelistet, keine geladen"}
    blob = puffer.getvalue()
    if len(blob) > _MAX_ZIP:
        return {"status": "zu_gross", "bytes": len(blob), "n_files": n,
                "note": f"{len(blob)/1024**2:.0f} MB"}
    ziel.write_bytes(blob)
    return {"status": "downloaded", "bytes": len(blob), "n_files": n, "note": ""}


def lauf(limit: int | None = None, dry_run: bool = False, country: str = "CH") -> dict:
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    from playwright.sync_api import sync_playwright

    # ZUERST die Zugangsdaten pruefen — vor Browser, vor Abfrage, vor jeder Ausgabe.
    # Sonst startet der Lauf sichtbar, laedt Chromium, fragt 889 Zeilen ab und bricht dann
    # ab: das sieht nach einem Fehler mitten im Betrieb aus statt nach einer fehlenden Datei.
    zugang()

    L = ROOT / "data" / "gold" / country / "lead_export.parquet"
    out_root = ROOT / "data" / "docs" / country
    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT lead_id, documents_url FROM read_parquet('{L.as_posix()}')
        WHERE phase='open' AND documents_url LIKE '%//{_HOST}/%'
          AND deadline_date > current_date
          AND coalesce(procedure_kind, '') <> 'open_house'
        ORDER BY deadline_date ASC""").fetchall()

    offen = [(lid, u, out_root / lid / "Vergabeunterlagen_simap.zip") for lid, u in rows]
    offen = [x for x in offen if not (x[2].exists() and x[2].stat().st_size > 0)]
    if limit:
        offen = offen[:limit]
    print(f"simap.ch: {len(offen)} Vergaben zu holen (von {len(rows)} offenen CH-Leads)")

    saetze, geladen_mb = [], 0.0
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(accept_downloads=True)
        pg = ctx.new_page()
        pg.set_default_timeout(90000)
        if not anmelden(pg):
            b.close()
            return {"versucht": 0, "geladen": 0, "note": "Anmeldung fehlgeschlagen"}
        print("  angemeldet.")
        for i, (lead_id, url, ziel) in enumerate(offen, 1):
            if geladen_mb >= _LAUF_BUDGET_MB:
                print(f"\n  Lauf-Budget erreicht — {len(offen) - i + 1} bleiben für morgen.")
                break
            try:
                r = hole_vergabe(url, pg, ziel, dry_run)
            except Exception as e:                       # noqa: BLE001
                r = {"status": "fehler", "bytes": 0, "n_files": 0, "note": type(e).__name__}
            saetze.append({"lead_id": lead_id, "url": url, **r})
            info = (f"{r['n_files']} Dateien  {r['bytes']/1024**2:.1f} MB"
                    if r["status"] == "downloaded" else f"{r['status']} ({r['note'][:44]})")
            print(f"  [{i}/{len(offen)}] {lead_id[:16]:<16} {info}", flush=True)
            geladen_mb += r["bytes"] / 1e6
            pg.wait_for_timeout(_HOEFLICH_MS)
        ctx.close()
        b.close()

    ok = sum(1 for s in saetze if s["status"] == "downloaded")
    mb = sum(s["bytes"] for s in saetze) / 1e6
    print(f"\nsimap.ch: {len(saetze)} versucht · {ok} geladen · {mb:.1f} MB")
    schlecht: dict[str, int] = {}
    for s in saetze:
        if s["status"] != "downloaded":
            schlecht[s["status"]] = schlecht.get(s["status"], 0) + 1
    if schlecht:
        print("  ⚠ " + ", ".join(f"{k}={v}" for k, v in sorted(schlecht.items())))
    if saetze and not dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist(saetze),
                       out_root / "_manifest_simap.parquet", compression="zstd")
    return {"versucht": len(saetze), "geladen": ok, "mb": round(mb, 1)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true",
                   help="anmelden und die Dateiliste zeigen, nichts herunterladen")
    a = p.parse_args(argv)
    lauf(a.limit, a.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
