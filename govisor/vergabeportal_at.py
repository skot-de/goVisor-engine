"""Quelle AT — vergabeportal.at + wien.gv.at: **Dateilisten**, nicht Dateien.

Der erste Connector des Projekts für Österreich. 334 offene Leads, das sind **91 % aller
erreichbaren AT-Leads** — denn ``www.wien.gv.at`` fährt dieselbe Software wie
``*.vergabeportal.at``, nur unter eigenem Namen::

    https://wstw.vergabeportal.at/Detail/250054
    https://www.wien.gv.at/Vergabeportal/Detail/250886

Mandanten u. a. gv, wstw, bbg, big, ktn, kwp, schramm-oehler, scwp, steiermark, tirol.

**Warum nur die Liste.** Die Plattform bietet einen anonymen Download ausdrücklich an —
Zustimmungs-Checkbox ``#cbCommitAnonymous``, Hinweis auf die Holschuld, daneben „Login für
Download". Die Dateien bleiben trotzdem gesperrt (``class="link-not-allowed"``,
``data-ng-if="!isValidFile(f)"``). Der Netzwerkverkehr zeigt warum: die Seite lädt
**hCaptcha** (``newassets.hcaptcha.com``, ``POST api.hcaptcha.com/checksiteconfig?…&host=
wstw.vergabeportal.at&sitekey=…``), und im Anonym-Bereich steht ein sichtbares
``div.h-captcha`` samt ``h-captcha-response``-Feld. ``isValidFile`` bleibt falsch, weil das
CAPTCHA ungelöst ist.

**Ein CAPTCHA wird nicht gelöst und nicht umgangen.** Das ist keine technische Einschätzung,
sondern eine Grenze — und zugleich das deutlichste Signal, das ein Betreiber senden kann.
Dieses Modul rührt es nicht an: es klickt weder die Zustimmung noch das Widget, sondern
liest ausschliesslich die Tabelle, die **ohne** CAPTCHA sichtbar ist.

Gemessen 2026-08-14 an sechs Vergaben über vier Mandanten: 0 Dateien freigeschaltet,
6–16 gesperrt je Vorgang — durchgehend, kein Ausreisser.

**Was die Liste hergibt — mehr als bei subreport:**

===================  ==========================================================
``name``             aussagekräftig: ``E_Leistungsverzeichnis.zip``,
                     ``A_Angebotsbestimmungen.zip``, ``B_Vertragsbestimmungen.zip``
``groesse``          „3.7 MB", „530.1 kB"
``erstellt_am``      Datum
``aktualisiert_am``  **Nachtrags-Signal**: weicht es vom Erstelldatum ab, wurde
                     nachgebessert — das haben die deutschen Quellen nicht
``aktiv``            „Inaktiv" kennzeichnet überholte Versionen; nur die aktiven
                     gelten. Ohne dieses Feld würde ein Berichtigungsstand als
                     gleichwertig neben dem gültigen stehen
``hash``             SHA je Datei — erlaubt später, Änderungen zu erkennen, ohne
                     die Datei zu besitzen
===================  ==========================================================

⚠ **Die Zellen einzeln lesen, nicht ``tr.innerText``.** Die Datei-Zelle klebt Name,
„Inaktiv" und „Hash-Wert: …" zusammen; der saubere Name steht in
``span[data-ng-bind="::f.name"]``. Dieselbe Falle wie bei `healyhudson`, wo eine
plattgemachte Zeile die Vergabestelle verschluckte.

Aufruf::

    python3 -m govisor.vergabeportal_at --limit 40
    python3 -m govisor.vergabeportal_at --limit 5 --dry-run
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

from . import docfetch_queue as _queue

ROOT = Path(__file__).resolve().parent.parent

# Beide Formen derselben Software. Der Pfad ist das Merkmal, nicht der Host — die Lehre aus
# drei DE-Quellen an einem Tag.
_DETAIL = re.compile(r"^https?://[^/]+/(?:Vergabeportal/)?Detail/(\d+)", re.IGNORECASE)

_WARTE_MS = 7000
_TAB_MS = 5000
_HOEFLICH_MS = 1800

# Die Datei-Zelle traegt „Hash-Wert: …" und ggf. „Inaktiv" hinter dem Namen.
_HASH = re.compile(r"Hash-Wert:\s*([0-9A-F:]{20,})", re.IGNORECASE)


def ist_vergabeportal(url: str | None) -> bool:
    return bool(url) and bool(_DETAIL.match(url))


def vorgangs_id(url: str | None) -> str | None:
    m = _DETAIL.match(url or "")
    return m.group(1) if m else None


def _liste_von_seite(pg) -> list[dict]:
    """Sichtbare Unterlagen-Tabelle → Saetze. Liest ZELLEN, nicht den Zeilentext."""
    return pg.evaluate(
        """() => [...document.querySelectorAll('tr')].map(tr => {
             const zellen = [...tr.querySelectorAll('td')];
             if (zellen.length < 4) return null;
             const span = zellen[0].querySelector('span[data-ng-bind*="f.name"]');
             if (!span) return null;
             const roh = zellen[0].innerText.replace(/\\s+/g, ' ').trim();
             return {
               name: (span.innerText || '').trim(),
               roh: roh,
               groesse: zellen[1].innerText.trim(),
               erstellt: zellen[2].innerText.trim(),
               aktualisiert: zellen[3].innerText.trim(),
             };
           }).filter(Boolean)""")


def hole_liste(url: str, pg) -> dict:
    """Eine Vergabe → Dateiliste. ⚠ Ruehrt das CAPTCHA nicht an."""
    r = pg.goto(url, wait_until="domcontentloaded")
    if r is not None and r.status >= 400:
        return {"dateien": [], "status": "fehler", "note": f"http {r.status}"}
    pg.wait_for_timeout(_WARTE_MS)

    try:
        pg.click("a:has-text('Unterlagen')", timeout=_TAB_MS)
        pg.wait_for_timeout(_TAB_MS)
    except Exception:                                    # noqa: BLE001
        pass                                             # manche Vorgaenge zeigen den Reiter offen

    roh = _liste_von_seite(pg)
    if not roh:
        # POSITIVES Merkmal: traegt die Seite ueberhaupt den Unterlagen-Bereich? Sonst sind
        # wir woanders gelandet, und das ist etwas anderes als „keine Unterlagen".
        rumpf = pg.evaluate("() => document.body.innerText")
        if "Unterlagen" not in rumpf:
            return {"dateien": [], "status": "fehler", "note": "kein Unterlagen-Bereich"}
        return {"dateien": [], "status": "leer", "note": "keine Dateien gelistet"}

    dateien = []
    for d in roh:
        h = _HASH.search(d["roh"])
        dateien.append({
            "name": d["name"],
            "groesse": d["groesse"],
            "erstellt_am": d["erstellt"],
            "aktualisiert_am": d["aktualisiert"],
            # „Inaktiv" kennzeichnet eine ueberholte Version. Ohne dieses Feld staende ein
            # alter Berichtigungsstand gleichwertig neben dem gueltigen.
            "aktiv": "Inaktiv" not in d["roh"],
            "hash": h.group(1) if h else None,
            # Nachtrag: nachgebessert, nicht nur eingestellt. Diese Unterscheidung haben die
            # deutschen Quellen nicht.
            "nachgebessert": d["erstellt"] != d["aktualisiert"],
        })
    return {"dateien": dateien, "status": "nur_liste", "note": ""}


def lauf(limit: int | None = None, dry_run: bool = False, country: str = "AT",
         alles_neu: bool = False) -> dict:
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    from playwright.sync_api import sync_playwright

    from . import doctypes

    L = ROOT / "data" / "gold" / country / "lead_export.parquet"
    out = ROOT / "data" / "docs" / country / "doc_listing_vergabeportal.parquet"
    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT lead_id, documents_url FROM read_parquet('{L.as_posix()}')
        WHERE phase='open' AND documents_url IS NOT NULL
          AND (documents_url LIKE '%vergabeportal.at/Detail/%'
               OR documents_url LIKE '%wien.gv.at/Vergabeportal/Detail/%')
          AND deadline_date > current_date
          AND coalesce(procedure_kind, '') <> 'open_house'
        ORDER BY deadline_date ASC""").fetchall()

    altbestand: list[dict] = []
    if out.exists() and not alles_neu:
        altbestand = con.execute(
            f"SELECT * FROM '{out.as_posix()}'").arrow().read_all().to_pylist()
        bekannt = {s["lead_id"] for s in altbestand}
        vorher = len(rows)
        rows = [r for r in rows if r[0] not in bekannt]
        if vorher != len(rows):
            print(f"vergabeportal.at: {vorher - len(rows)} bereits erfasst, übersprungen")
    # Zweite Erinnerung, andere Frage. `bekannt` oben ueberspringt, was ERFASST wurde;
    # die Warteschlange ueberspringt, was GESCHEITERT ist. Ohne sie liefen genau die
    # Vorgaenge ewig mit, die unten per `continue` gar keinen Satz hinterlassen.
    _mroot = out.parent
    rows, _weg = _queue.filtere(rows, _queue.frueher(_mroot, "vergabeportal"))
    if _weg:
        print(_queue.bericht(_weg))
    _manifest: list[dict] = []
    if limit:
        rows = rows[:limit]
    print(f"vergabeportal.at: {len(rows)} offene Vergaben zu prüfen")

    saetze: list[dict] = []
    heute = dt.date.today().isoformat()
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context()
        pg = ctx.new_page()
        pg.set_default_timeout(45000)
        for i, (lead_id, url) in enumerate(rows, 1):
            try:
                r = hole_liste(url, pg)
            except Exception as e:                       # noqa: BLE001
                print(f"  [{i}/{len(rows)}] {lead_id}: Fehler ({type(e).__name__})", flush=True)
                _manifest.append({"lead_id": lead_id, "status": "fehler",
                                  "note": f"{type(e).__name__}"})
                continue
            dateien = r["dateien"]
            aktiv = [d for d in dateien if d["aktiv"]]
            typen = [doctypes.classify(d["name"]) for d in aktiv]
            prio = sorted({t for t in typen if doctypes.is_priority(t)},
                          key=doctypes.priority_rank)
            saetze.append({
                "lead_id": lead_id, "url": url, "erfasst_am": heute,
                "n_dateien": len(dateien), "n_aktiv": len(aktiv),
                "n_nachgebessert": sum(1 for d in aktiv if d["nachgebessert"]),
                "dateien": [d["name"] for d in aktiv],
                "doktypen": typen, "prioritaetstypen": prio,
                "detail": json.dumps(dateien, ensure_ascii=False),
                # Ehrlicher Status: die LISTE haben wir, die Dateien nicht — sie stehen
                # hinter einem CAPTCHA, das bewusst nicht angeruehrt wird.
                "status": r["status"],
            })
            # Schlank ins Manifest (Status + Zahl), die Dateiliste bleibt in
            # `doc_listing_vergabeportal.parquet` — eine Datei je Frage.
            _manifest.append({"lead_id": lead_id, "url": url, "status": r["status"],
                              "note": f"{len(aktiv)} aktiv von {len(dateien)}"})
            print(f"  [{i}/{len(rows)}] {lead_id}: {len(aktiv)} aktiv von {len(dateien)}"
                  + (f" · {', '.join(prio)}" if prio else ""), flush=True)
            pg.wait_for_timeout(_HOEFLICH_MS)
        ctx.close()
        b.close()

    mit = sum(1 for s in saetze if s["n_aktiv"])
    lv = sum(1 for s in saetze if "leistungsbeschreibung" in s["prioritaetstypen"])
    eig = sum(1 for s in saetze if "eignung" in s["prioritaetstypen"])
    nach = sum(s["n_nachgebessert"] for s in saetze)
    print(f"\n{len(saetze)} Vergaben · {mit} mit Dateiliste · {lv} mit Leistungsverzeichnis · "
          f"{eig} mit Eignungsunterlage · {nach} nachgebesserte Dateien")
    if dry_run:
        for s in saetze[:2]:
            print("   ", json.dumps({k: v for k, v in s.items() if k != "detail"},
                                    ensure_ascii=False)[:220])
        return {"geprüft": len(saetze), "mit_liste": mit}

    # Das Manifest wird VOR dem frühen Ausstieg unten geschrieben. Ein Lauf, in dem jeder
    # Versuch scheiterte, hat `saetze == []` — und genau seine Fehlschläge sind die, die
    # man beim nächsten Mal überspringen will. Stünde das Schreiben dahinter, wäre der
    # schlechteste Lauf der einzige ohne Gedächtnis.
    if _manifest:
        _mroot.mkdir(parents=True, exist_ok=True)
        _queue.schreibe(_mroot, "vergabeportal", _manifest)

    if not saetze and not altbestand:
        print("nichts zu schreiben.")
        return {"geprüft": 0, "mit_liste": 0}
    out.parent.mkdir(parents=True, exist_ok=True)
    frisch = {s["lead_id"] for s in saetze}
    alle = [s for s in altbestand if s["lead_id"] not in frisch] + saetze
    pq.write_table(pa.Table.from_pylist(alle), out, compression="zstd")
    print(f"→ {out} ({len(alle)} Vergaben gesamt)")
    return {"geprüft": len(saetze), "mit_liste": mit, "gesamt": len(alle)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--alles-neu", action="store_true",
                   help="bekannte Vergaben nicht überspringen (Nachträge einsammeln)")
    a = p.parse_args(argv)
    lauf(a.limit, a.dry_run, alles_neu=a.alles_neu)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
