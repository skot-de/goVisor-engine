"""Quelle DE — Vergabeunterlagen der Healy-Hudson-Portale, anonym.

Gegenstück zu ``govisor/healyhudson.py``: das holt die **Bekanntmachungen** aller sechzehn
Bundesländer, das hier die **Unterlagen**. 508 offene Leads über sechs Hosts —
``bieterzugang.deutsche-evergabe.de`` 234 · ``bieterportal.noncd.db.de`` 128 (Deutsche
Bahn) · ``www.evergabe.bayern.de`` 69 · ``fbhh-evergabe.web.hamburg.de`` 50 ·
``bieter.ehealth-evergabe.de`` 23 · ``ausschreibungen.kfw.de`` 4.

**Die Plattform sagt es selbst.** Auf der Vorgangsseite steht wörtlich: „Sie können die
Vergabeunterlagen ohne Anmeldung herunterladen." Daneben ein Knopf „Alle herunterladen"
und die Dateien einzeln benannt (gemessen 2026-08-14 an ``fbhh-evergabe.web.hamburg.de``,
Vergabe DP31-202600034 „KKSys-as-a-Service", Auftraggeber Dataport AöR:
``Vergabeunterlagen.pdf``, ``Checkliste Vergabeunterlagen.docx``, neun Dateien insgesamt).

⚠ **Die Instanzen verhalten sich verschieden — das ist der Fallstrick dieses Moduls.**
Derselbe Deeplink-Pfad führt nicht überall zum selben Ziel:

* Hamburg, Bahn: bleiben auf dem eigenen Host und zeigen die Vorgangsseite mit Dateien.
* Bayern, bieterzugang: leiten auf ``portal.deutsche-evergabe.de/dashboards/dashboard_off/…``
  — ein öffentliches Dashboard, das den Vorgang **listet**, aber keine Dateien trägt.

Wer die eine Instanz prüft und auf die anderen schliesst, liegt in beide Richtungen falsch.
Deshalb prüft dieses Modul je Vorgang auf ein **positives Merkmal** (den Download-Knopf)
und meldet sonst ehrlich ``kein_downloadbereich`` statt ``leer``.

Ausgabe wie bei den übrigen Fetchern: ein ZIP je Vergabe unter
``data/docs/<country>/<lead_id>/`` — dort sucht ``docpipe.index``. Einzeldateien werden
lokal zu einem ZIP gebündelt, damit der nachgelagerte Pfad unverändert bleibt.

Aufruf::

    python3 -m govisor.docfetch_healyhudson --limit 20
    python3 -m govisor.docfetch_healyhudson --limit 3 --dry-run
"""
from __future__ import annotations

import argparse
import io
import re
import tempfile
import zipfile
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

# Der Deeplink-Pfad ist das gemeinsame Merkmal der Familie — verlaesslicher als eine
# Hostliste, weil weitere Instanzen dieselbe Software fahren koennen.
_DEEPLINK = "/api/supplier/external/deeplink/"

_WARTE_MS = 7000
_HOEFLICH_MS = 2000
_MAX_DATEI = 60 * 1024**2
_MAX_VERGABE = 200 * 1024**2

# LAUF-BUDGET IN BYTES. Als EINZIGER Abrufer hatte healyhudson keins — alle anderen
# deckeln bei 1.500 bis 2.000 MB. Genau dieser Abrufer lief am 2026-08-15 719 Minuten.
#
# Warum ein Byte-Deckel und nicht nur ein Stueck-Deckel: `--limit 60` zaehlt Vorgaenge,
# und ein Vorgang ist gemessen alles zwischen 0 und 636 MB (Median 8, 90 % unter 72).
# 60 Stueck sind damit je nach Zusammensetzung 0,6 bis 3,3 GB. Die beobachtete Streuung
# von 55,6 bis 719,1 min ist zum grossen Teil kein Server-Zufall, sondern diese Einheit:
# gezaehlt wurde die falsche Groesse.
_LAUF_BUDGET_MB = 2000
# ECHTE Dokumentendungen, keine generische `\.\w{2,5}$`-Regel. Die faengt naemlich auch
# `kundendienst@deutsche-evergabe.de` — gemessen im ersten Probelauf, wo drei von vier
# Vorgaengen die Kontakt-Mailadresse als „Datei" meldeten.
_ENDUNGEN = ("pdf", "zip", "doc", "docx", "xls", "xlsx", "rtf", "odt", "ods", "txt",
             "dwg", "gaeb", "x81", "x82", "x83", "x84", "x86", "d81", "d83", "p81", "p83",
             "jpg", "png", "csv", "xml", "7z")
_MIT_ENDUNG = re.compile(r"\.(?:" + "|".join(_ENDUNGEN) + r")$", re.IGNORECASE)

# Der Sammelknopf. Die Oberflaeche benutzt Material-Icons, der Text steht daneben.
_FEHLERSCHLUESSEL = re.compile(r"ErrorMessageKey=([A-Za-z0-9._]+)")

_ALLE = ("xpath=//*[self::button or self::a]"
         "[contains(normalize-space(.), 'Alle herunterladen')]")


def ist_healyhudson(url: str | None) -> bool:
    return bool(url) and _DEEPLINK in url


def _dateiliste(pg) -> list[dict]:
    """Sichtbare Vorgangsseite → [{name, ref}] der einzeln benannten Dateien."""
    return pg.evaluate(
        """() => [...document.querySelectorAll('a,button')]
             .map(e => ({name: (e.innerText || '').trim(),
                         ref: e.getAttribute('href') || ''}))
             .filter(x => !/^mailto:/i.test(x.ref) && RE.test(x.name))""".replace(
             "RE", "/\\.(?:" + "|".join(_ENDUNGEN) + ")$/i"))


def hole_vergabe(url: str, pg, tmp: Path, dry_run: bool = False) -> dict:
    """Eine Vergabe → {dateien: [(name, bytes)], status, note}."""
    r = pg.goto(url, wait_until="domcontentloaded")
    if r is not None and r.status >= 400:
        return {"dateien": [], "status": "fehler", "note": f"http {r.status}", "gelistet": 0}
    pg.wait_for_timeout(_WARTE_MS)

    # ⚠ Healy-Hudson beantwortet Fehlgriffe mit einer eigenen Seite, und die traegt den
    # Grund maschinenlesbar in der Adresse (`ErrorMessage.aspx?ErrorMessageKey=…`). Wer nur
    # nach Dateien sucht, sieht dort keine und meldet „keine Dateien auf der Vorgangsseite"
    # — eine Aussage ueber die Vergabe, obwohl die Seite eine ueber die ANFRAGE macht.
    # Gemessen am 2026-08-24 ueber die 14 so gemeldeten Faelle: 3× noch nicht
    # veroeffentlicht, 3× nicht mehr verfuegbar, 7 hatten inzwischen Dateien.
    if "errormessage.aspx" in pg.url.lower():
        m = _FEHLERSCHLUESSEL.search(pg.url)
        schluessel = m.group(1) if m else ""
        if schluessel.startswith("Project.NotBeenPublished"):
            return {"dateien": [], "status": "nicht_veroeffentlicht", "gelistet": 0,
                    "note": "Verfahren noch nicht veröffentlicht"}
        if schluessel.startswith("SubProject.NotAvailable"):
            return {"dateien": [], "status": "weg", "gelistet": 0,
                    "note": "Verfahren nicht mehr verfügbar"}
        return {"dateien": [], "status": "fehler", "gelistet": 0,
                "note": f"Fehlerseite {schluessel or 'ohne Schlüssel'}"}

    rumpf = pg.evaluate("() => document.body.innerText")
    eintraege = _dateiliste(pg)
    knopf = pg.query_selector(_ALLE)

    if not eintraege and knopf is None:
        # POSITIVES Merkmal fehlt. Zwei sehr verschiedene Faelle, und sie duerfen nicht
        # dieselbe Meldung bekommen: das zentrale Dashboard (Bayern-Weg) traegt nie
        # Dateien, eine echte Vorgangsseite ohne Unterlagen schon.
        if "dashboard" in pg.url.lower() or "Anzahl:" in rumpf:
            return {"dateien": [], "status": "kein_downloadbereich", "gelistet": 0,
                    "note": "auf zentrales Dashboard umgeleitet"}
        return {"dateien": [], "status": "leer", "gelistet": 0,
                "note": "keine Dateien auf der Vorgangsseite"}

    if dry_run:
        return {"dateien": [], "status": "probe", "gelistet": len(eintraege),
                "note": ", ".join(e["name"] for e in eintraege[:3])}

    dateien: list[tuple[str, bytes]] = []
    uebersprungen: list[str] = []

    def sichern(d, vorschlag: str) -> None:
        ziel = tmp / f"dl_{len(dateien)}_{len(uebersprungen)}"
        d.save_as(str(ziel))
        g = ziel.stat().st_size
        name = d.suggested_filename or vorschlag or f"datei_{len(dateien)}"
        if g > _MAX_DATEI:
            uebersprungen.append(f"{name} ({g/1024**2:.0f} MB)")
        else:
            if not _MIT_ENDUNG.search(name):
                name += ".bin"
            dateien.append((name, ziel.read_bytes()))
        ziel.unlink(missing_ok=True)

    # Erst der Sammelknopf — ein Abruf statt N, das ist auch fuer das fremde System
    # freundlicher.
    if knopf is not None:
        try:
            with pg.expect_download(timeout=180000) as dl:
                knopf.click()
            sichern(dl.value, "Vergabeunterlagen.zip")
        except Exception as e:                           # noqa: BLE001
            uebersprungen.append(f"Alle herunterladen ({type(e).__name__})")

    # Nur wenn der Sammelweg nichts brachte, einzeln nachfassen.
    if not dateien:
        for e in eintraege:
            if sum(len(b) for _, b in dateien) >= _MAX_VERGABE:
                uebersprungen.append(f"{e['name']} (Vergabe-Budget)")
                continue
            try:
                with pg.expect_download(timeout=120000) as dl:
                    pg.click(f"xpath=//*[normalize-space()='{e['name']}']")
                sichern(dl.value, e["name"])
            except Exception as ex:                      # noqa: BLE001
                uebersprungen.append(f"{e['name']} ({type(ex).__name__})")

    status = "downloaded" if dateien else "abgewiesen"
    return {"dateien": dateien, "status": status, "gelistet": len(eintraege),
            "note": "; ".join(uebersprungen[:3])}


def _schreibe_zip(ziel: Path, dateien: list[tuple[str, bytes]]) -> int:
    """Einzeldateien → ein ZIP. Ist die einzige Datei schon ein ZIP, wird sie durchgereicht."""
    ziel.parent.mkdir(parents=True, exist_ok=True)
    if len(dateien) == 1 and dateien[0][0].lower().endswith(".zip"):
        ziel.write_bytes(dateien[0][1])
        return ziel.stat().st_size
    puffer = io.BytesIO()
    gesehen: dict[str, int] = {}
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name, blob in dateien:
            if name in gesehen:
                gesehen[name] += 1
                stamm, punkt, endung = name.rpartition(".")
                name = f"{stamm}_{gesehen[name]}{punkt}{endung}" if punkt else f"{name}_{gesehen[name]}"
            else:
                gesehen[name] = 0
            z.writestr(name, blob)
    ziel.write_bytes(puffer.getvalue())
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
        WHERE phase='open' AND documents_url LIKE '%{_DEEPLINK}%'
          AND deadline_date > current_date
          AND coalesce(procedure_kind, '') <> 'open_house'
        ORDER BY deadline_date ASC""").fetchall()

    offen = []
    for lead_id, url in rows:
        ziel = out_root / lead_id / "Vergabeunterlagen_hh.zip"
        if ziel.exists() and ziel.stat().st_size > 0:
            continue
        offen.append((lead_id, url, ziel))
    # Frueher dauerhaft Gescheitertes ueberspringen — sonst blockiert dieselbe
    # Warteschlangenspitze jeden Lauf. VOR dem Limit, sonst kappt das Limit auf
    # Kandidaten, die gleich wieder aussortiert werden.
    offen, _weg = _queue.filtere(offen, _queue.frueher(out_root, "healyhudson"))
    if _weg:
        print(_queue.bericht(_weg))
    if limit:
        offen = offen[:limit]
    print(f"Healy-Hudson-Unterlagen: {len(offen)} Vergaben zu holen (von {len(rows)} offenen Leads)")

    saetze = []
    def _sichern():                     # laeuft, wenn die Wache hart abbricht
        if saetze and not dry_run:
            out_root.mkdir(parents=True, exist_ok=True)
            _queue.schreibe(out_root, "healyhudson", saetze)

    with _queue.Wache("healyhudson", vorgang_hart_s=0, leerlauf_s=LEERLAUF_S,
                      sichern=_sichern) as wache, sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(accept_downloads=True)
        pg = ctx.new_page()
        pg.set_default_timeout(90000)
        geladen_mb = 0.0
        for i, (lead_id, url, ziel) in enumerate(offen, 1):
            if geladen_mb >= _LAUF_BUDGET_MB:
                print(f"\n  Lauf-Budget von {_LAUF_BUDGET_MB} MB erreicht — "
                      f"{len(offen) - i + 1} Vergaben bleiben fuer den naechsten Lauf.")
                break
            host = url.split("/")[2]
            try:
                with tempfile.TemporaryDirectory() as td:
                    with _queue.vorgang_frist(VORGANG_FRIST_S):
                        r = hole_vergabe(url, pg, Path(td), dry_run)
                    groesse = (_schreibe_zip(ziel, r["dateien"])
                               if r["dateien"] and not dry_run else 0)
            except _queue.VorgangZuLang:
                r = {"dateien": [], "status": "zu_lang", "gelistet": 0,
                     "note": f"> {VORGANG_FRIST_S}s"}
                groesse = 0
            except Exception as e:                       # noqa: BLE001
                r = {"dateien": [], "status": "fehler", "gelistet": 0, "note": type(e).__name__}
                groesse = 0
            saetze.append({"lead_id": lead_id, "host": host, "url": url,
                           "status": r["status"], "bytes": groesse,
                           "n_files": len(r["dateien"]), "gelistet": r["gelistet"],
                           "note": r["note"]})
            if r.get("status") == "downloaded":
                wache.erfolg()
            geladen_mb += groesse / 1e6
            info = (f"{len(r['dateien'])} Dateien  {groesse/1024**2:.1f} MB"
                    if r["status"] == "downloaded" else f"{r['status']} ({r['note'][:50]})")
            print(f"  [{i}/{len(offen)}] {host[:30]:<30} {lead_id[:14]:<14} {info}", flush=True)
            pg.wait_for_timeout(_HOEFLICH_MS)
        ctx.close()
        b.close()

    ok = sum(1 for s in saetze if s["status"] == "downloaded")
    mb = sum(s["bytes"] for s in saetze) / 1e6
    print(f"\nHealy-Hudson-Unterlagen: {len(saetze)} versucht · {ok} geladen · {mb:.1f} MB")
    # Nach Host aufschluesseln — die Instanzen sind verschieden, ein Ausfall trifft meist
    # genau eine.
    je_host: dict[str, dict[str, int]] = {}
    for s in saetze:
        je_host.setdefault(s["host"], {}).setdefault(s["status"], 0)
        je_host[s["host"]][s["status"]] += 1
    for h, st in sorted(je_host.items()):
        print("  " + h + ": " + ", ".join(f"{k}={v}" for k, v in sorted(st.items())))
    if saetze and not dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        _queue.schreibe(out_root, "healyhudson", saetze)
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
