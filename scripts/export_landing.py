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
    try:
        analysen = json.loads((ROOT / "web/data/doc-analysis.json").read_text(encoding="utf-8"))
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
    }
    ZIEL.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    print(f"  Startseite: {gesamt:,} Vergaben ({offen:,} offen) aus {len(laender)} Ländern "
          f"→ {ZIEL.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
