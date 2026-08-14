"""Quelle DE — Healy-Hudson-Portale: **eine Liste für alle sechzehn Bundesländer**.

Gebaut, weil Sven wissen wollte, ob Bayern und Hamburg als Landesportale angebunden sind.
Die Antwort war größer als die Frage: beide fahren dieselbe Software, und die hat eine
öffentliche, nach Bundesland parametrisierte Bekanntmachungsliste.

**Wie das gefunden wurde.** ``www.evergabe.bayern.de`` und
``fbhh-evergabe.web.hamburg.de`` tragen in unseren Daten denselben URL-Pfad
``/evergabe.bieter/api/supplier/external/deeplink/subproject/<uuid>``. Der Bieterbereich
verlangt beidesmal eine Anmeldung (identischer Login, „Healy Hudson GmbH, Build
4.9.36.294"). Der Deeplink leitet aber auf ein **öffentliches** Dashboard, und die
bayerische Landesseite ``auftraege.bayern.de`` verlinkt „Zu den Ausschreibungen" auf::

    /Dashboards/Dashboard_off?BL=09

``BL`` ist der amtliche Bundesland-Schlüssel. Damit ist die Liste für **jedes** Land
abrufbar, ohne Anmeldung. Gemessen 2026-08-14, offene Vorgänge::

    BY 395 · BW 202 · NRW 151 · NI 147 · SL 119 · HH 67 · HE 49 · BE 49 · RP 35
    SH 19 · BB 15 · MV 14 · SN 14 · TH 12 · ST 10 · HB 2        = 1.300 gesamt

Über die Unterlagen-Links kennen wir davon bisher 508. Die Familie umfasst neben Bayern und
Hamburg auch ``bieterzugang.deutsche-evergabe.de`` (234 Leads),
``bieterportal.noncd.db.de`` (128, Deutsche Bahn), ``bieter.ehealth-evergabe.de`` (23) und
``ausschreibungen.kfw.de`` (4) — **ein Modul statt sechs**. Das ist dieselbe Lehre wie bei
den Unterlagen: die Plattform-Familie ist die Einheit, nicht das Bundesland.

⚠ **Die Liste rotiert.** Ein Abruf liefert ~20–27 Zeilen, unabhängig davon, ob 2 oder 395
Vorgänge gemeldet sind — und bei jedem Abruf eine andere Auswahl. Sechs Abrufe auf Bayern
ergaben kumuliert 91 von 395. Es ist also **keine Seitennavigation**, sondern eine
Zufallsauswahl; ``&page=``, ``&Seite=``, ``&start=`` und drei weitere Varianten wurden
geprüft, alle werden ignoriert (sie liefern zwar andere Zeilen, aber nur weil jede Antwort
neu würfelt). Der CPV-Parameter wird als URL-Argument ebenfalls ignoriert — die Seite
filtert CPV nur über ein POST-Formular.

Konsequenz für die Bauart: **wiederholt abrufen, bis nichts Neues mehr kommt** — und
**melden, wie vollständig der Lauf war**. Kleine Länder sind in einem Abruf komplett
(Bremen: zweimal geholt, beide Male dieselben 4 Zeilen), große brauchen viele Runden. Was
nicht erreicht wurde, steht in der Zusammenfassung; ein Lauf, der 60 % holt und „fertig"
meldet, wäre schlimmer als gar keiner.

**Schreibt nur Bronze** (``data/raw_healyhudson/<YYYY-MM>.jsonl``). Der Silber-Schritt
fasst ``data/silver/DE/notices`` an — eine geteilte Ablage, an der gerade eine zweite
Sitzung arbeitet. Er kommt bewusst später, s. ``--silber`` unten (noch nicht implementiert).

Aufruf::

    python3 -m govisor.healyhudson --laender BY,HH --runden 12
    python3 -m govisor.healyhudson --alle --runden 8
    python3 -m govisor.healyhudson --laender HB --dry-run
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_BASIS = "https://portal.deutsche-evergabe.de/Dashboards/Dashboard_off?BL="

# Amtlicher Bundesland-Schluessel. Genau die Kennung, die `auftraege.bayern.de` selbst
# benutzt — nicht geraten, sondern von der Landesseite abgelesen.
LAENDER = {
    "SH": ("01", "Schleswig-Holstein"),   "HH": ("02", "Hamburg"),
    "NI": ("03", "Niedersachsen"),        "HB": ("04", "Bremen"),
    "NW": ("05", "Nordrhein-Westfalen"),  "HE": ("06", "Hessen"),
    "RP": ("07", "Rheinland-Pfalz"),      "BW": ("08", "Baden-Württemberg"),
    "BY": ("09", "Bayern"),               "SL": ("10", "Saarland"),
    "BE": ("11", "Berlin"),               "BB": ("12", "Brandenburg"),
    "MV": ("13", "Mecklenburg-Vorpommern"), "SN": ("14", "Sachsen"),
    "ST": ("15", "Sachsen-Anhalt"),       "TH": ("16", "Thüringen"),
}

_WARTE_MS = 4500
_HOEFLICH_MS = 1200
_TROCKEN = 4          # so viele Runden ohne Neues gelten als ausgeschoepft
_MAX_RUNDEN = 40      # Notbremse; die Coupon-Collector-Schaetzung fuer BY liegt bei ~95

_ANZAHL = re.compile(r"Anzahl:\s*([\d.]+)")
# Eine Trefferzeile beginnt mit der Vergabeart und endet auf zwei Datumsangaben.
_ZEILE = re.compile(
    r"^(?P<art>[A-Za-zÄÖÜäöü/]{2,8})\s+(?P<rest>.+?)\s+"
    r"(?P<pub>\d{2}\.\d{2}\.\d{4})\s+(?P<frist>\d{2}\.\d{2}\.\d{4})$")


def schluessel(land: str, zeile: str) -> str:
    """Stabile Kennung. Die Liste traegt keine Vorgangs-ID im Text, deshalb ein Hash über
    Land und Zeileninhalt — dieselbe Loesung wie bei NetServer, und aus demselben Grund."""
    return hashlib.sha1(f"{land}|{zeile}".encode("utf-8")).hexdigest()[:16]


def zerlege(zeile: str, land: str) -> dict | None:
    """Textzeile → Satz. Gibt None, wenn die Zeile nicht wie ein Vorgang aussieht.

    Die Trennung Titel/Verfahrensart/Vergabestelle ist aus der Zeile allein NICHT sicher
    moeglich — zwischen ihnen steht nur Leerraum, kein Trennzeichen. Deshalb bleibt `rest`
    ungetrennt im Satz stehen und wird NICHT geraten. Ein falsch aufgeteilter Titel waere
    schlimmer als ein ungeteilter: die Dubletten-Firewall vergleicht Titel.
    """
    m = _ZEILE.match(zeile.strip())
    if not m:
        return None
    return {
        "quelle": "healyhudson",
        "land": land,
        "vergabeart": m.group("art"),
        "beschreibung": m.group("rest").strip(),   # Titel + Verfahrensart + Vergabestelle
        "pub": m.group("pub"),
        "frist": m.group("frist"),
        "schluessel": schluessel(land, zeile.strip()),
        "erfasst_am": dt.date.today().isoformat(),
    }


def hole_land(kuerzel: str, pg, runden: int) -> dict:
    """Ein Bundesland → alle erreichbaren Vorgaenge. Wiederholt, bis nichts Neues kommt."""
    bl, name = LAENDER[kuerzel]
    url = _BASIS + bl
    saetze: dict[str, dict] = {}
    gemeldet = None
    leer = 0
    for runde in range(runden):
        pg.goto(url, wait_until="domcontentloaded")
        pg.wait_for_timeout(_WARTE_MS)
        text = pg.evaluate("() => document.body.innerText")
        if gemeldet is None:
            m = _ANZAHL.search(text)
            gemeldet = int(m.group(1).replace(".", "")) if m else 0
        zeilen = pg.evaluate(
            """() => [...document.querySelectorAll('tr')].slice(1)
                 .map(r => r.innerText.replace(/\\s+/g, ' ').trim())
                 .filter(x => x.length > 20)""")
        neu = 0
        for z in zeilen:
            s = zerlege(z, kuerzel)
            if s and s["schluessel"] not in saetze:
                saetze[s["schluessel"]] = s
                neu += 1
        leer = leer + 1 if neu == 0 else 0
        if leer >= _TROCKEN:
            break
        pg.wait_for_timeout(_HOEFLICH_MS)
    return {"land": kuerzel, "name": name, "gemeldet": gemeldet or 0,
            "geholt": len(saetze), "runden": runde + 1, "saetze": list(saetze.values())}


def lauf(kuerzel: list[str], runden: int, dry_run: bool) -> dict:
    from playwright.sync_api import sync_playwright

    ergebnisse = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context()
        pg = ctx.new_page()
        pg.set_default_timeout(45000)
        for k in kuerzel:
            r = hole_land(k, pg, runden)
            quote = f"{100 * r['geholt'] / r['gemeldet']:.0f}%" if r["gemeldet"] else "—"
            marke = "" if r["geholt"] >= r["gemeldet"] else "  ⚠ unvollständig"
            print(f"  {k}  {r['name']:<24} {r['geholt']:>4} von {r['gemeldet']:>4} "
                  f"({quote:>4}) in {r['runden']} Runden{marke}", flush=True)
            ergebnisse.append(r)
        ctx.close()
        b.close()

    alle = [s for r in ergebnisse for s in r["saetze"]]
    ges_gem = sum(r["gemeldet"] for r in ergebnisse)
    print(f"\nHealy Hudson: {len(alle)} Vorgänge von {ges_gem} gemeldeten "
          f"({100 * len(alle) / ges_gem:.0f} %)" if ges_gem else "\nnichts geholt.")
    # KEIN stilles Abschneiden: was fehlt, wird benannt.
    fehlt = [r for r in ergebnisse if r["geholt"] < r["gemeldet"]]
    if fehlt:
        print("  unvollständig: " + ", ".join(
            f"{r['land']} ({r['gemeldet'] - r['geholt']} offen)" for r in fehlt))
        print("  → mehr Runden helfen; die Liste würfelt je Abruf neu.")

    if dry_run:
        for s in alle[:3]:
            print("   ", json.dumps(s, ensure_ascii=False)[:170])
        return {"geholt": len(alle), "gemeldet": ges_gem}

    out = ROOT / "data" / "raw_healyhudson"
    out.mkdir(parents=True, exist_ok=True)
    ziel = out / f"{dt.date.today():%Y-%m}.jsonl"
    # Anhaengen und beim Lesen deduplizieren — wie die anderen Bronze-Ablagen. Der
    # Schluessel ist stabil, doppelte Zeilen fallen spaeter auf.
    bekannt = set()
    if ziel.exists():
        for line in ziel.open(encoding="utf-8"):
            try:
                bekannt.add(json.loads(line)["schluessel"])
            except Exception:                            # noqa: BLE001
                pass
    frisch = [s for s in alle if s["schluessel"] not in bekannt]
    with ziel.open("a", encoding="utf-8") as fh:
        for s in frisch:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"→ {ziel}  ({len(frisch)} neu, {len(alle) - len(frisch)} bereits bekannt)")
    return {"geholt": len(alle), "neu": len(frisch), "gemeldet": ges_gem}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--laender", default="", help="Kürzel, z. B. BY,HH,NW")
    p.add_argument("--alle", action="store_true", help="alle sechzehn")
    p.add_argument("--runden", type=int, default=10,
                   help=f"Abrufe je Land (max {_MAX_RUNDEN}); die Liste würfelt je Abruf")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    if a.alle:
        k = list(LAENDER)
    else:
        k = [x.strip().upper() for x in a.laender.split(",") if x.strip()]
    unbekannt = [x for x in k if x not in LAENDER]
    if unbekannt:
        p.error(f"unbekannte Länderkürzel: {unbekannt}. Erlaubt: {', '.join(LAENDER)}")
    if not k:
        p.error("--laender oder --alle angeben")
    lauf(k, min(a.runden, _MAX_RUNDEN), a.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
