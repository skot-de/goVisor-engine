#!/usr/bin/env python3
"""Zahlen für die öffentliche Startseite → ``web/data/landing.json``.

**Warum eine eigene Datei und keine Konstanten im Seitencode.** Eine Startseite, die „über
100.000 Vergaben" behauptet, veraltet in dem Moment, in dem jemand sie tippt — und niemand
merkt es, weil eine Zahl im JSX wie eine Tatsache aussieht. Hier kommen die Zahlen aus
demselben Bestand, den die Anwendung ausliefert, und tragen ihren Stand mit.

**Bewusst wenige.** Was hier steht, muss ein Besucher in fünf Sekunden einordnen können:
wie viel, aus welchen Ländern, wie tief ausgewertet. Alles Weitere ist Produkt, nicht
Werbung.

Aufruf::  scripts/export_landing.py
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZIEL = ROOT / "web/data/landing.json"


# ── EIGNUNGS-CHECK ──────────────────────────────────────────────────────────────────
# Sven: „ich will das man da klicken kann oder direkt seine daten eingeben kann um sein
# profil zu checken. nach dem motto ‚jeder kann an ausschreibungen teilnehmen, auch du.
# schau wie nah du dran bist'". Drinnen in der Anwendung gibt es den Abgleich laengst
# (Ticket #27 Eignungsprofil, Ticket #26 Handlungsempfehlung) — er setzt aber ein Konto
# und ein gepflegtes Profil voraus. Draussen fehlte jeder Einstieg.
#
# **Was hier vorberechnet wird und warum nicht im Browser gerechnet wird.** Die Leaddateien
# sind zusammen ueber 40 MB; sie einem Besucher zu schicken, damit er drei Zahlen
# vergleicht, waere absurd. Stattdessen liegt hier ein Wuerfel: je Fachgebiet × Region die
# Zahl der offenen Vorgaenge und ihre Verteilung ueber sechs Groessenstufen, dazu je
# Fachgebiet die tatsaechlich verlangten Schwellen (Haftpflicht, Referenzen, Mindestumsatz)
# als kumulierte Zaehlung entlang derselben Auswahlleiter, die die Oberflaeche anbietet.
# Der Browser addiert nur noch.
#
# **Nur veroeffentlichte Werte.** `volumen.src == 'echt'` ist die einzige zulaessige Quelle
# fuer die Groessenverteilung. Der Bestand traegt auch geschaetzte Werte (Median-Imputation,
# erkennbar daran, dass 369.663 € 335-mal vorkommt) — eine Startseite, die daraus eine
# Spanne bildet, behauptet Messung und zeigt Rechnung.
# Nur die 16 Laender, nichts sonst: der Bestand trug auch zwei Vorgaenge mit region
# „Deutschland", und die stuenden in der Auswahl direkt neben „Deutschland gesamt".
BUNDESLAENDER = frozenset((
    "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen", "Hamburg", "Hessen",
    "Mecklenburg-Vorpommern", "Niedersachsen", "Nordrhein-Westfalen", "Rheinland-Pfalz",
    "Saarland", "Sachsen", "Sachsen-Anhalt", "Schleswig-Holstein", "Thüringen"))
STUFEN = [(0, 25_000), (25_000, 100_000), (100_000, 500_000),
          (500_000, 2_000_000), (2_000_000, 10_000_000), (10_000_000, None)]
# Grenzen, unterhalb derer eine extrahierte Schwelle nicht plausibel ist: „Mindestumsatz 2 €"
# und „Haftpflichtdeckung 0 €" sind Extraktionsfehler, keine Anforderungen.
ANF_LEITER = {
    "haftpflicht": {"typ": "berufshaftpflicht", "min": 10_000, "unten": "keine",
                    "frage": "Wie hoch ist eure Betriebshaftpflicht?",
                    "einheit": "€", "stufen": [250_000, 500_000, 1_000_000, 3_000_000,
                                               5_000_000, 10_000_000]},
    "referenzen": {"typ": "referenz_anzahl", "min": 1, "max": 20, "unten": "keine",
                   "frage": "Wie viele vergleichbare Referenzen könnt ihr vorlegen?",
                   "einheit": "", "stufen": [1, 2, 3, 5, 10]},
    "umsatz": {"typ": "mindestumsatz", "min": 10_000, "unten": "weniger",
               "frage": "Wie hoch ist euer Jahresumsatz?",
               "einheit": "€", "stufen": [100_000, 250_000, 500_000, 1_000_000,
                                          2_500_000, 5_000_000, 10_000_000]},
}


def _wert_eur(roh: object) -> int | None:
    """„1,2 Mio €" → 1_200_000. Gibt None zurück, wenn nichts Zählbares dasteht."""
    import re
    m = re.fullmatch(r"([\d.,]+)\s*(Mio|Mrd|Tsd)?\s*€", str(roh or "").strip())
    if not m:
        return None
    zahl = m.group(1)
    if m.group(2):
        return int(float(zahl.replace(".", "").replace(",", "."))
                   * {"Tsd": 1e3, "Mio": 1e6, "Mrd": 1e9}[m.group(2)])
    try:
        return int(zahl.replace(".", "").replace(",", ""))
    except ValueError:
        return None


def _zahl(roh: object) -> float | None:
    import re
    m = re.search(r"\d+(?:[.,]\d+)?", str(roh or "").replace(".", "").replace(",", "."))
    return float(m.group()) if m else None


def eignungs_check(root, fachliste, analysen: dict) -> dict:
    """Der Würfel für den öffentlichen Eignungs-Check."""
    import json as _json
    from collections import Counter, defaultdict

    fach_von_lead: dict[str, str] = {}
    zellen: dict[str, dict] = {}
    alle_werte: list[int] = []

    for f in fachliste:
        schluessel = f["schluessel"]
        pfad = root / "web/data" / f"leads-{schluessel}.json"
        try:
            leads = _json.loads(pfad.read_text(encoding="utf-8"))
            leads = leads if isinstance(leads, list) else list(leads.values())
        except Exception:                                      # noqa: BLE001
            continue
        # Region: in DE das Bundesland (74 % belegt), in AT/CH nur das Land — dort ist die
        # Regionalzuordnung zu grob, um ein Versprechen darauf zu bauen.
        offen_je_region: dict[str, Counter] = defaultdict(Counter)
        werte_je_region: dict[str, list[int]] = defaultdict(list)
        for l in leads:
            if not (isinstance(l.get("endTage"), int) and l["endTage"] >= 0):
                continue
            fach_von_lead[l.get("id")] = schluessel
            land = l.get("land")
            raeume = ["alle"]
            if land == "DE":
                raeume.append("DE")
                if l.get("region") in BUNDESLAENDER:
                    raeume.append(l["region"])
            elif land in ("AT", "CH"):
                raeume.append(land)
            v = l.get("volumen") or {}
            eur = _wert_eur(v.get("wert")) if v.get("src") == "echt" else None
            if eur is not None:
                alle_werte.append(eur)
            for r in raeume:
                offen_je_region[r]["offen"] += 1
                if eur is not None:
                    werte_je_region[r].append(eur)
        for r, c in offen_je_region.items():
            ws = werte_je_region[r]
            stufen = [sum(1 for w in ws if w >= a and (b is None or w < b)) for a, b in STUFEN]
            zellen[f"{schluessel}|{r}"] = {"offen": c["offen"], "mitWert": len(ws),
                                           "stufen": stufen}

    # ── Was dort verlangt wird ──────────────────────────────────────────────────────
    # Aus den ausgewerteten Unterlagen, je Fachgebiet. Wo eine Anforderung im Fachgebiet
    # seltener als 30-mal belegt ist, traegt sie keine Aussage: dann faellt die Oberflaeche
    # auf den Gesamtbestand zurueck. Lieber eine breitere Grundlage als eine, die nach
    # Praezision aussieht und auf elf Faellen steht.
    roh: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for lid, a in analysen.items():
        fk = fach_von_lead.get(lid)
        for it in (a.get("checklist") or []):
            if not isinstance(it, dict) or not it.get("value"):
                continue
            for name, spec in ANF_LEITER.items():
                if it.get("req_type") != spec["typ"]:
                    continue
                z = _zahl(it["value"])
                if z is None or z < spec["min"] or z > spec.get("max", float("inf")):
                    continue
                roh[name]["alle"].append(z)
                if fk:
                    roh[name][fk].append(z)

    anforderungen: dict[str, dict] = {}
    for name, spec in ANF_LEITER.items():
        je_fach = {}
        for raum, werte in roh[name].items():
            if len(werte) < 30 and raum != "alle":
                continue
            # kumuliert: wie viele der verlangten Schwellen erfüllt jemand mit Stufe i
            je_fach[raum] = {"n": len(werte), "median": sorted(werte)[len(werte) // 2],
                             "kum": [sum(1 for w in werte if w <= s) for s in spec["stufen"]]}
        anforderungen[name] = {"frage": spec["frage"], "einheit": spec["einheit"],
                               "unten": spec["unten"],
                               "stufen": spec["stufen"], "je_fach": je_fach}

    # Reihenfolge der Auswahl: „alle" zuerst, dann Deutschland und seine Laender nach
    # Bestand, dann Oesterreich und die Schweiz. Nur Raeume, in denen ueberhaupt etwas offen
    # ist — eine Auswahl, die auf „0 Vorgaenge" fuehrt, ist ein Fehler, kein Ergebnis.
    summe: dict[str, int] = defaultdict(int)
    for k, z in zellen.items():
        summe[k.split("|", 1)[1]] += z["offen"]
    laender_raeume = [r for r in ("alle", "DE", "AT", "CH") if summe.get(r)]
    bundeslaender = sorted((r for r in summe if r not in ("alle", "DE", "AT", "CH")),
                           key=lambda r: -summe[r])
    regionen = ([{"schluessel": r, "label": {"alle": "überall", "DE": "Deutschland gesamt",
                                             "AT": "Österreich", "CH": "Schweiz"}[r],
                  "offen": summe[r]} for r in laender_raeume]
                + [{"schluessel": r, "label": r, "offen": summe[r]} for r in bundeslaender])

    alle_werte.sort()
    return {
        "regionen": regionen,
        "stufen": [{"von": a, "bis": b} for a, b in STUFEN],
        "zellen": zellen,
        "anforderungen": anforderungen,
        "wert": {"n": len(alle_werte),
                 "min": alle_werte[0] if alle_werte else None,
                 "median": alle_werte[len(alle_werte) // 2] if alle_werte else None,
                 "max": alle_werte[-1] if alle_werte else None,
                 "unter25k": sum(1 for w in alle_werte if w < 25_000)},
    }


def main() -> int:
    import duckdb

    con = duckdb.connect()
    laender: dict[str, dict] = {}
    gesamt = offen = 0
    for land in ("DE", "AT", "CH"):
        p = ROOT / "data/gold" / land / "lead_export.parquet"
        if not p.exists():
            continue
        n, o = con.execute(
            f"SELECT count(*), count(*) FILTER (WHERE phase='open') FROM '{p.as_posix()}'"
        ).fetchone()
        laender[land] = {"gesamt": n, "offen": o}
        gesamt += n
        offen += o

    # ── PLANUNGSHORIZONT ────────────────────────────────────────────────────────────────
    # Die Startseite zeigte zuerst nur den Einzelfall: eine offene Ausschreibung mit ihren
    # Anforderungen. Was fehlte, ist die Zeitachse — und dort steht die staerkste Zahl des
    # Bestands: die auslaufenden Vertraege. Eine laufende Ausschreibung ist fuer die meisten
    # Firmen zu spaet; wer einen Amtsinhaber verdraengen will, faengt ein Jahr vorher an.
    de_le = (ROOT / 'data/gold/DE/lead_export.parquet').as_posix()
    horizont = con.execute(f"""SELECT
        count(*) FILTER (WHERE phase='expiring'),
        count(*) FILTER (WHERE phase='expiring' AND months_to_expiry BETWEEN 0 AND 24)
        FROM '{de_le}'""").fetchone()
    regionen = 0
    rp = ROOT / "data/gold/DE/region_kpi.parquet"
    if rp.exists():
        regionen = con.execute(f"SELECT count(*) FROM '{rp.as_posix()}'").fetchone()[0]

    # Vergabestellen und Fachgebiete nur aus DE: für AT/CH ist die Entitäten-Auflösung
    # schwächer, und eine Zahl, die zwei verschiedene Qualitäten mischt, ist keine Zahl.
    de = (ROOT / "data/gold/DE/lead_export.parquet").as_posix()
    stellen, cpv = con.execute(
        f"SELECT count(DISTINCT buyer_name), count(DISTINCT cpv_code) FROM '{de}'").fetchone()

    # ── FACHGEBIETE ─────────────────────────────────────────────────────────────────────
    # Die Startseite sprach niemanden an: kein einziges Gewerk genannt. Ein Dachdecker
    # entscheidet in drei Sekunden, ob eine Seite ihn meint, und „117.493 Vergaben" sagt
    # ihm nichts. Gezaehlt werden Vorgaenge mit LAUFENDER Frist — nicht der Gesamtbestand,
    # denn was zaehlt, ist was heute offen ist.
    fach = []
    for datei, label in (("bau", "Bau und Handwerk"), ("it", "IT und Digitales"),
                         ("beratung", "Planung und Beratung"), ("energie", "Energie und Umwelt"),
                         ("medizin", "Medizin und Pflege"), ("sicherheit", "Sicherheit")):
        pfad = ROOT / "web/data" / f"leads-{datei}.json"
        try:
            leads = json.loads(pfad.read_text(encoding="utf-8"))
            leads = leads if isinstance(leads, list) else list(leads.values())
            n = sum(1 for l in leads if isinstance(l, dict)
                    and isinstance(l.get("endTage"), int) and l["endTage"] >= 0)
        except Exception:                                      # noqa: BLE001
            n = 0
        if n:
            fach.append({"schluessel": datei, "label": label, "offen": n})
    fach.sort(key=lambda f: -f["offen"])

    def zaehle(name: str) -> int:
        p = ROOT / "web/data" / name
        try:
            return len(json.loads(p.read_text(encoding="utf-8")))
        except Exception:                                      # noqa: BLE001
            return 0

    # ── EIN ECHTES BEISPIEL ──────────────────────────────────────────────────────────────
    # Die Startseite behauptet, dass zu jeder Anforderung das woertliche Zitat danebensteht.
    # Das kann man schreiben — oder zeigen. Gezeigt wird ein ECHTER offener Vorgang mit
    # seinen belegten Anforderungen; ausgesucht nach Kriterien, nicht von Hand, damit er
    # nicht eines Tages abgelaufen auf der Startseite steht.
    #
    # Alles daran ist oeffentlich: Vergabebekanntmachungen und ihre Unterlagen sind es von
    # Natur aus. Trotzdem bewusst nur DREI Anforderungen und gekuerzte Zitate — die Seite
    # soll neugierig machen, nicht die Auswertung ersetzen.
    beispiel = None
    analysen_fuer_check: dict = {}
    try:
        analysen = json.loads((ROOT / "web/data/doc-analysis.json").read_text(encoding="utf-8"))
        analysen_fuer_check = analysen
        offen_map = {r[0]: r[1:] for r in con.execute(
            f"""SELECT lead_id, title, buyer_name, deadline_date, buyer_region_name
                FROM '{de}' WHERE phase='open' AND deadline_date >= current_date
                  AND title IS NOT NULL""").fetchall()}
        beste = None
        for lid, a_ in analysen.items():
            wo = offen_map.get(lid)
            if not wo:
                continue
            treffer = [c for c in (a_.get("checklist") or [])
                       if isinstance(c, dict) and c.get("quote") and c.get("label")]
            typen = {c.get("req_type") for c in treffer}
            # Verschiedene Anforderungsarten sind aussagekraeftiger als viele gleiche:
            # dreimal „Ausschlussgrund" zeigt weniger als Haftpflicht + Umsatz + Referenz.
            if len(typen) >= 3 and (beste is None or len(typen) > beste[0]):
                beste = (len(typen), lid, wo, treffer)
        if beste:
            _, lid, (titel, kaeufer, frist, region), treffer = beste
            gesehen, punkte = set(), []
            for c in treffer:
                if c["req_type"] in gesehen:
                    continue
                gesehen.add(c["req_type"])
                punkte.append({"label": c["label"], "zitat": c["quote"][:150],
                               "datei": (c.get("source_file") or "").split("/")[-1][:60]})
                if len(punkte) == 3:
                    break
            beispiel = {"titel": titel[:90], "kaeufer": kaeufer, "region": region,
                        "frist": str(frist), "punkte": punkte}
    except Exception:                                          # noqa: BLE001
        beispiel = None                                        # ohne Beispiel bleibt die Seite ganz

    daten = {
        "stand": date.today().isoformat(),
        "vergaben": gesamt,
        "offen": offen,
        "laender": laender,
        "vergabestellen_de": stellen,
        "fachgebiete_de": cpv,
        "unterlagen_volltext": zaehle("doc-text-index.json"),
        "unterlagen_analysiert": zaehle("doc-analysis.json"),
        "auslaufend": horizont[0],
        "auslaufend_24m": horizont[1],
        "regionen": regionen,
        "anbieter": zaehle("suppliers.json"),
        "fachgebiete": fach,
        "beispiel": beispiel,
        "check": eignungs_check(ROOT, fach, analysen_fuer_check),
    }
    ZIEL.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    print(f"  Startseite: {gesamt:,} Vergaben ({offen:,} offen) aus {len(laender)} Ländern "
          f"→ {ZIEL.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
