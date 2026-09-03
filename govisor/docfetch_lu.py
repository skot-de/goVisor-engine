"""Vergabeunterlagen aus **Luxemburg** (`pmp.b2g.etat.lu`, Portail des marchés publics).

⚠ **DIESER ABRUFER IST ANDERS GEBAUT ALS DIE ZWÖLF DEUTSCHEN — aus zwei gemessenen Gründen.**

**1. Luxemburg vergisst.** Nach Fristende sind die Unterlagen weg. Gemessen am 2026-09-03:
30 Vergaben aus TED-Paketen der letzten drei Monate meldeten alle
*„Aucune pièce n'a été jointe"*, während drei **laufende** Vergaben „Dossier de soumission"
mit 4,41 / 1,41 / 26,15 MB trugen. Luxemburg ist damit nach Deutschland das zweite Land
ohne Archiv (`docs/sondierung/haltbarkeit.md` §14) — was hier nicht geholt wird, ist
**dauerhaft** verloren.

**2. Darum kommt die Warteschlange NICHT aus Gold.** Alle anderen Abrufer lesen
`data/gold/<land>/lead_export.parquet`. Für LU gibt es die Datei nicht (das Land ist
sondiert, nicht angebunden) — und selbst wenn: die TED-**Monatspakete** liegen bis zu vier
Wochen zurück, und eine luxemburgische Frist ist oft kürzer. Wer aus dem Monatspaket
arbeitet, holt systematisch das, was schon weg ist.

Diese Fassung fragt deshalb die **TED-Suchschnittstelle** direkt:

    POST api.ted.europa.eu/v3/notices/search
         (buyer-country=LUX) AND (publication-date>=…)
         fields: document-url-lot, deadline-receipt-tender-date-lot, …

⚠ **Sortiert nach FRIST, aufsteigend.** Bei einer verderblichen Quelle ist die nächste Frist
der nächste Verlust. Alle anderen Abrufer dürfen nach Ausbeute sortieren; dieser nicht.

## Der Abrufweg: zwei Formularschritte, ohne Personendaten

    1  /index.php?page=Entreprise.EntrepriseDemandeTelechargementDce&id=<n>&orgAcronyme=t5y
       Auswahl „choixAnonyme" — der Betreiber bietet sie selbst an, gestützt auf
       Artikel 64 des Gesetzes vom 17.06.2016 (kostenlos, frei, vollständig, unmittelbar).
    2  derselbe Aufruf, Rückruf „completeDownload"  → application/zip

Belegt am 2026-09-03: **4.626.716 Bytes, 6 Dokumente**, ohne dass ein Feld ausgefüllt wurde.
⚠ Der Zustand (`PRADO_PAGESTATE`) ist ~11.800 Zeichen gross und muss zwischen den beiden
Schritten mitwandern — deshalb Playwright und nicht `curl`.

## ⚠ KEINE Grössenschwelle als Vorgabe

Gemessen an zehn laufenden Vergaben: Median 6,94 MB, Mittel 90,79 MB, grösste **614 MB**.
Eine 50-MB-Schwelle würde 7,2 statt 143 GB im Jahr bedeuten — **aber in Luxemburg heisst
„übersprungen" nicht „später", sondern „nie"**, und die grossen Pakete sind die
Bauvorhaben mit Planunterlagen. Wer eine Schwelle setzt, entscheidet sich dauerhaft gegen
den wertvollsten Teil. `GOVISOR_LU_MAX_MB` gibt es, steht aber auf 0 = aus.

Aufruf:  python3 -m govisor.docfetch_lu [--limit N] [--tage 45] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import zipfile
from datetime import date, timedelta
from pathlib import Path

from . import docfetch_queue as _queue
from .schema import normalize_notice_id

ROOT = Path(__file__).resolve().parent.parent

_HOST = "pmp.b2g.etat.lu"
_UA = "goVisor/1.0 (+https://govisor.eu) Unterlagen-Abruf"
_TED = "https://api.ted.europa.eu/v3/notices/search"

_WARTE_MS = 2500
_HOEFLICH_MS = 2000
_DOWNLOAD_MS = 600_000          # 614-MB-Pakete sind gemessen; 10 min sind knapp genug
VORGANG_FRIST_S = int(os.environ.get("GOVISOR_VORGANG_FRIST", "900"))
LEERLAUF_S = int(os.environ.get("GOVISOR_LEERLAUF", "3600"))
# 0 = keine Schwelle. Siehe Modulkopf: eine Schwelle ist hier ein dauerhafter Verzicht.
MAX_MB = float(os.environ.get("GOVISOR_LU_MAX_MB", "0"))
LAUF_BUDGET_MB = float(os.environ.get("GOVISOR_LU_BUDGET_MB", "8000"))

_ID = re.compile(r"/entreprise/consultation/(\d+)")
# Die Bausteine des Formulars. ⚠ Namen mit '$', Kennungen mit '_' — PRADO schreibt beides.
_RADIO_ANONYM = "#ctl0_CONTENU_PAGE_EntrepriseFormulaireDemande_choixAnonyme"
_ABSENDEN = "#ctl0_CONTENU_PAGE_validateButton"
_KOMPLETT = "#ctl0_CONTENU_PAGE_EntrepriseDownloadDce_completeDownload"


def ist_lu(url: str | None) -> bool:
    return bool(url) and _HOST in url


def kennung(url: str | None) -> str | None:
    """`documents_url` → Vorgangsnummer. None, wenn keine drinsteht."""
    if not ist_lu(url):
        return None
    m = _ID.search(url)
    return m.group(1) if m else None


def _ted_lu(tage: int) -> list[tuple[str, str, str]]:
    """(Vergabenummer, Frist, Konsultations-URL) aus der TED-Suche, Frist aufsteigend.

    ⚠ Nur Vergaben mit Frist IN DER ZUKUNFT — bei allen anderen sind die Unterlagen
    bereits entfernt, und ein Abruf wäre eine garantiert leere Anfrage an das Portal.
    """
    seit = (date.today() - timedelta(days=tage)).strftime("%Y%m%d")
    rumpf = json.dumps({
        "query": f"(buyer-country=LUX) AND (publication-date>={seit})",
        "limit": 250, "page": 1,
        "fields": ["publication-number", "document-url-lot",
                   "deadline-receipt-tender-date-lot"],
    })
    r = subprocess.run(["curl", "-s", "-m", "90", "-A", _UA, "-X", "POST",
                        "-H", "Content-Type: application/json",
                        "-H", "Accept: application/json", "-d", rumpf, _TED],
                       capture_output=True, timeout=120)
    try:
        d = json.loads(r.stdout)
    except Exception:                                                  # noqa: BLE001
        print("  ⚠ TED-Suche nicht erreichbar — kein Zulauf, kein Abruf.")
        return []
    if "message" in d:
        print(f"  ⚠ TED-Suche: {d['message'][:120]}")
        return []
    heute = date.today().isoformat()
    aus: list[tuple[str, str, str]] = []
    for n in d.get("notices") or []:
        urls = n.get("document-url-lot") or []
        fristen = n.get("deadline-receipt-tender-date-lot") or []
        if not urls:
            continue
        frist = min((f[:10] for f in fristen), default="")
        if not frist or frist <= heute:
            continue                     # abgelaufen → Unterlagen sind weg
        for u in urls:
            if ist_lu(u):
                aus.append((str(n.get("publication-number") or ""), frist, u))
                break
    aus.sort(key=lambda t: t[1])          # ⚠ naechste Frist zuerst
    return aus


def _dossier_mb(pg) -> float | None:
    """Grösse laut Vergabeseite („Dossier de soumission - 26,15 Mo"). None = keine Anlage."""
    t = pg.inner_text("body")
    if "Aucune pi" in t:
        return None
    m = re.search(r"Dossier de soumission\s*-\s*([\d.,]+)\s*(Mo|Ko|Go)", t)
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    return v if m.group(2) == "Mo" else (v / 1024 if m.group(2) == "Ko" else v * 1024)


def hole_vergabe(cid: str, pg, ziel: Path, dry_run: bool = False) -> dict:
    """Eine luxemburgische Vergabe → ZIP nach `ziel`."""
    basis = f"https://{_HOST}/entreprise/consultation/{cid}?orgAcronyme=t5y"
    pg.goto(basis, wait_until="domcontentloaded")
    pg.wait_for_timeout(_WARTE_MS)
    mb = _dossier_mb(pg)
    if mb is None:
        # ⚠ „leer" fuer alles ist kein Status (Bibel 03: „Ein Status ist eine Behauptung —
        # und bisher hielt keine einzige stand"). Die Warteschlange enthaelt NUR Vergaben
        # mit Frist in der Zukunft; „Aucune piece jointe" kann hier also nicht „Frist
        # vorbei" heissen. Zwei unterscheidbare Faelle bleiben, und sie werden benannt:
        offen_bis = pg.inner_text("body")
        if "Consultation" in offen_bis and "cl" in offen_bis and "tur" in offen_bis:
            return {"status": "geschlossen", "bytes": 0, "n_files": 0,
                    "note": "Portal fuehrt die Vergabe als geschlossen, TED-Frist noch offen"}
        return {"status": "noch_ohne_anlage", "bytes": 0, "n_files": 0,
                "note": "Frist laeuft, aber kein Dossier eingestellt — erneut versuchen"}
    if MAX_MB and mb > MAX_MB:
        return {"status": "zu_gross", "bytes": 0, "n_files": 0,
                "note": f"{mb:.1f} MB > {MAX_MB:.0f} MB — ⚠ in LU dauerhaft verloren"}
    if dry_run:
        return {"status": "probe", "bytes": 0, "n_files": 0, "note": f"{mb:.2f} MB angekuendigt"}

    pg.goto(f"https://{_HOST}/index.php?page=Entreprise."
            f"EntrepriseDemandeTelechargementDce&id={cid}&orgAcronyme=t5y",
            wait_until="domcontentloaded")
    pg.wait_for_timeout(_WARTE_MS)
    if not pg.locator(_RADIO_ANONYM).count():
        return {"status": "kein_formular", "bytes": 0, "n_files": 0,
                "note": "choixAnonyme nicht auf der Seite"}
    # ⚠ Die Rueckfrage („Bent u zeker…"-Aequivalent) bestaetigt der Betreiber selbst als
    # Hinweis, nicht als Zustimmung: sie sagt nur, dass man ohne Angabe nicht ueber
    # Aenderungen benachrichtigt wird. Kein Einverstaendnis, keine Personendaten.
    pg.on("dialog", lambda d: d.accept())
    pg.check(_RADIO_ANONYM)
    pg.click(_ABSENDEN)
    pg.wait_for_timeout(_WARTE_MS)

    if not pg.locator(_KOMPLETT).count():
        return {"status": "kein_download", "bytes": 0, "n_files": 0,
                "note": "completeDownload fehlt nach dem Absenden"}
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with pg.expect_download(timeout=_DOWNLOAD_MS) as dl:
        pg.click(_KOMPLETT)
    groesse = Path(dl.value.path()).stat().st_size
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
    return {"status": "downloaded", "bytes": groesse, "n_files": n,
            "note": f"angekuendigt {mb:.1f} MB"}


def lauf(limit: int | None = None, dry_run: bool = False, tage: int = 45) -> dict:
    from playwright.sync_api import sync_playwright

    out_root = ROOT / "data" / "docs" / "LU"
    kandidaten = _ted_lu(tage)
    if not kandidaten:
        print("Luxemburg: kein Zulauf.")
        return {"versucht": 0, "geladen": 0, "mb": 0.0}

    offen: list[tuple[str, str, Path]] = []
    for nummer, frist, url in kandidaten:
        cid = kennung(url)
        if not cid:
            continue
        # ⚠ KANONISCHE FORM, NICHT DIE TED-SCHREIBWEISE. Die API liefert „533534-2026"
        # mit Bindestrich; Silber und Gold fuehren „533534_2026". Die erste Fassung dieses
        # Abrufers legte die Ordner mit Bindestrich an — genau die Drift, die am 2026-07-29
        # eine Migration ueber 217,7 Mio. Kennungen gekostet hat (CLAUDE.md). Ohne diese
        # Zeile verbindet sich der Vorgang spaeter mit NICHTS, und zwar lautlos.
        lead_id = normalize_notice_id(nummer) if nummer else cid
        ziel = out_root / lead_id / f"Vergabeunterlagen_lu_{cid}.zip"
        if ziel.exists() and ziel.stat().st_size > 0:
            continue
        offen.append((lead_id, cid, ziel))
    # Frueher Gescheitertes ueberspringen — VOR dem Limit.
    dreier = [(l, c, z) for l, c, z in offen]
    dreier, weg = _queue.filtere(dreier, _queue.frueher(out_root, "lu"))
    if weg:
        print(_queue.bericht(weg))
    if limit:
        dreier = dreier[:limit]
    print(f"Luxemburg: {len(dreier)} Vergaben zu holen "
          f"(von {len(kandidaten)} mit laufender Frist), Frist aufsteigend")

    saetze: list[dict] = []
    geladen_mb = 0.0

    def _sichern():
        if saetze and not dry_run:
            out_root.mkdir(parents=True, exist_ok=True)
            _queue.schreibe(out_root, "lu", saetze)

    with _queue.Wache("lu", vorgang_hart_s=0, leerlauf_s=LEERLAUF_S,
                      sichern=_sichern) as wache, sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(accept_downloads=True, user_agent=_UA)
        pg = ctx.new_page()
        pg.set_default_timeout(60000)
        for i, (lead_id, cid, ziel) in enumerate(dreier, 1):
            if geladen_mb >= LAUF_BUDGET_MB:
                print(f"\n  Lauf-Budget erreicht — {len(dreier) - i + 1} bleiben. "
                      "⚠ In LU heisst das: sie sind morgen vielleicht weg.")
                break
            try:
                with _queue.vorgang_frist(VORGANG_FRIST_S):
                    r = hole_vergabe(cid, pg, ziel, dry_run)
            except _queue.VorgangZuLang:
                r = {"status": "zu_lang", "bytes": 0, "n_files": 0,
                     "note": f"> {VORGANG_FRIST_S}s"}
            except Exception as e:                                     # noqa: BLE001
                erste = str(e).strip().splitlines()[0] if str(e).strip() else ""
                r = {"status": "fehler", "bytes": 0, "n_files": 0,
                     "note": f"{type(e).__name__}: {erste}"[:160]}
            saetze.append({"lead_id": lead_id, "url":
                           f"https://{_HOST}/entreprise/consultation/{cid}?orgAcronyme=t5y", **r})
            if r.get("status") == "downloaded":
                wache.erfolg()
            geladen_mb += r["bytes"] / 1024**2
            info = (f"{r['n_files']} Dateien  {r['bytes']/1024**2:.1f} MB"
                    if r["status"] == "downloaded" else f"{r['status']} ({r['note'][:44]})")
            print(f"  [{i}/{len(dreier)}] {lead_id[:16]:<16} {info}", flush=True)
            pg.wait_for_timeout(_HOEFLICH_MS)
        ctx.close()
        b.close()

    ok = sum(1 for s in saetze if s["status"] == "downloaded")
    mb = sum(s["bytes"] for s in saetze) / 1e6
    print(f"\nLuxemburg: {len(saetze)} versucht · {ok} geladen · {mb:.1f} MB")
    schlecht: dict[str, int] = {}
    for s in saetze:
        if s["status"] != "downloaded":
            schlecht[s["status"]] = schlecht.get(s["status"], 0) + 1
    if schlecht:
        print("  ⚠ " + ", ".join(f"{k}={v}" for k, v in sorted(schlecht.items())))
    if saetze and not dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        _queue.schreibe(out_root, "lu", saetze)
    return {"versucht": len(saetze), "geladen": ok, "mb": mb}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--tage", type=int, default=45,
                   help="wie weit die TED-Suche zurueckschaut (Vorgabe 45)")
    p.add_argument("--dry-run", action="store_true",
                   help="Groessen zaehlen — nichts herunterladen")
    a = p.parse_args(argv)
    lauf(a.limit, a.dry_run, a.tage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
