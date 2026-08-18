#!/usr/bin/env python3
"""``region_kpi`` → ``web/data/regionen.json`` — die Regionalansicht.

**Warum es das gibt.** `region_kpi.parquet` lag seit dem Ausbau der Destatis-Anreicherung
fertig herum und kam im Frontend nie an: 437 Regionen, Nachfrage × Angebotsseite ×
Vorlaufindikator × Fiskallage, sichtbar nur für den, der DuckDB startet. Sven am
2026-08-18 beim Durchgehen der ungenutzten Tabellen: „verdrahte auch die sachen sauber,
damit wir daraus nutzen ziehen können."

**Was hier NICHT passiert.** Es wird nichts neu gerechnet. Die Kennzahlen entstehen in
`govisor.gold.build_region_kpi`; dieses Skript formt sie nur um: englische Spalten →
Feldnamen der Oberfläche, NUTS-Präfix → Bundesland, plus die Mediane als Vergleichsmass.
Wer eine Kennzahl ändern will, ändert `gold.py`, nicht diese Datei.

**Die Mediane sind der eigentliche Trick.** `docs/kpi-region-und-kontext.md` warnt
ausdrücklich: Frankfurt und Bonn sind Ausreisser, und wer eine Region ohne Vergleichswert
zeigt, produziert Zahlen ohne Bedeutung („418 Baugenehmigungen" — viel? wenig?). Deshalb
liegt zu jeder Kontextgrösse der Median der deutschen Regionen daneben.

**Ausland bleibt drin.** 20 der 437 Regionen liegen ausserhalb Deutschlands (Leistungsort
im Ausland, meist n=1). Nach der EU-weit-Regel in `CLAUDE.md` werden sie nicht
weggeworfen, sondern als eigene Gruppe geführt — mit dem ehrlichen Hinweis, dass der
Destatis-Kontext dort fehlt, weil Destatis nur Deutschland zählt.

Aufruf: python3 scripts/export_regionen.py [--country DE]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# NUTS-1-Präfix → Bundesland. Steht hier und nicht in einer Referenzdatei, weil es sich
# seit 1990 nicht geändert hat und eine Datei mehr Ausfallstelle als Nutzen wäre.
LAENDER = {
    "DE1": "Baden-Württemberg", "DE2": "Bayern", "DE3": "Berlin", "DE4": "Brandenburg",
    "DE5": "Bremen", "DE6": "Hamburg", "DE7": "Hessen", "DE8": "Mecklenburg-Vorpommern",
    "DE9": "Niedersachsen", "DEA": "Nordrhein-Westfalen", "DEB": "Rheinland-Pfalz",
    "DEC": "Saarland", "DED": "Sachsen", "DEE": "Sachsen-Anhalt",
    "DEF": "Schleswig-Holstein", "DEG": "Thüringen",
    # DEZ ist die NUTS-Kennung für „extra-regio" — Vorgänge, die keinem Kreis zuzuordnen
    # sind. Sie als Bundesland zu führen wäre falsch; sie zu verschweigen auch.
    "DEZ": "nicht zuordenbar",
}

# Was in die Datei geht: Parquet-Spalte → Feldname der Oberfläche. Die Auswahl ist bewusst
# kürzer als die Tabelle — `bau_umsatz_eur` etwa ist zu 0 % gedeckt und `volumen_2023_eur`
# steckt bereits in `intensitaet_pct`.
FELDER = [
    ("n_offen", "offen"), ("n_vergeben", "vergeben"), ("n_vergabestellen", "stellen"),
    ("volumen_eur", "volumen"), ("volumen_coverage", "volumenDeckung"),
    ("single_bidder_rate", "singleBieter"), ("genehmigungen_gesamt", "genehmigungen"),
    ("investitionen_eur", "investitionen"), ("investition_je_kopf_eur", "investitionKopf"),
    ("schulden_je_kopf_eur", "schuldenKopf"), ("bevoelkerung", "einwohner"),
    ("baubetriebe", "baubetriebe"), ("bau_beschaeftigte", "bauBeschaeftigte"),
    ("auftraege_je_1000_ew", "je1000"), ("auftraege_je_betrieb", "jeBetrieb"),
    ("intensitaet_pct", "intensitaet"),
]

# Kontextgrössen, für die der Median als Normalfall danebensteht. Nachfragezahlen (offen,
# vergeben) stehen bewusst NICHT drin: bei ihnen ist die Region gross oder klein, nicht
# „über oder unter Normal".
MIT_MEDIAN = ["genehmigungen", "investitionKopf", "schuldenKopf", "je1000", "jeBetrieb",
              "baubetriebe", "singleBieter", "intensitaet"]


def zahl(v):
    """Rundet auf, was die Oberfläche ohnehin gerundet zeigt — und wirft NaN raus.

    NaN überlebt `json.dumps` als `NaN`, was **kein gültiges JSON** ist: `JSON.parse`
    wirft, und die Seite bliebe leer, ohne dass irgendwo etwas rot wäre.
    """
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:                       # NaN
        return None
    return round(f, 2) if abs(f) < 1000 else round(f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="DE")
    a = ap.parse_args()

    import duckdb

    quelle = ROOT / "data/gold" / a.country / "region_kpi.parquet"
    if not quelle.exists():
        print(f"  ✖ {quelle} fehlt — erst `govisor gold` laufen lassen.", file=sys.stderr)
        return 1

    con = duckdb.connect()
    spalten = ", ".join(f'"{p}"' for p, _ in FELDER)
    zeilen = con.execute(
        f"SELECT nuts_code, region_name, {spalten} FROM '{quelle.as_posix()}'"
        " ORDER BY n_offen DESC, n_vergeben DESC"
    ).fetchall()

    regionen = []
    for z in zeilen:
        code, name = z[0], z[1]
        praefix = (code or "")[:3]
        regionen.append({
            "id": code,
            "name": name or code,
            # Ausland: Destatis kennt es nicht, also gibt es dort auch keinen Kontext.
            # Die Gruppe sagt das, statt leere Felder unkommentiert stehen zu lassen.
            "land": LAENDER.get(praefix, "ausserhalb Deutschlands"),
            **{feld: zahl(w) for (_, feld), w in zip(FELDER, z[2:])},
        })

    # ── Brücke, bis `gold` neu gelaufen ist ────────────────────────────────────────────
    # In den vorhandenen Parquets steht bei 86 Regionen eine 0 bei den Baugenehmigungen,
    # wo „unbekannt" gemeint ist (`coalesce(...,0)` — in gold.py inzwischen behoben). Es
    # sind exakt jene ohne Destatis-Zuordnung, erkennbar an der fehlenden Einwohnerzahl:
    # nachgemessen sind beide Mengen identisch, 86 = 86, ohne einen einzigen Abweichler.
    # Eine 0 stehenzulassen hiesse „in diesem Landkreis wurde 2023 kein einziges Gebäude
    # genehmigt" zu behaupten. Nach dem nächsten Gold-Lauf greift diese Zeile ins Leere.
    for r in regionen:
        if r.get("einwohner") is None and r.get("genehmigungen") == 0:
            r["genehmigungen"] = None

    # Median NUR über die deutschen Regionen: ein Median, in den 20 Auslandsregionen ohne
    # Kontextzahlen einfliessen, wäre der Median einer anderen Grundgesamtheit.
    inland = [r for r in regionen if (r["id"] or "").startswith("DE")]
    median = {}
    for feld in MIT_MEDIAN:
        werte = [r[feld] for r in inland if r.get(feld) is not None]
        median[feld] = round(statistics.median(werte), 2) if werte else None

    ziel = ROOT / "web/data/regionen.json"
    ziel.write_text(json.dumps({
        "stand": date.today().isoformat(),
        # Alle Destatis-Grössen sind Stand 2023 (docs/kpi-region-und-kontext.md §9). Die
        # Zahl gehört in die Datei, nicht in den Code der Oberfläche: wenn der Cache auf
        # 2024 wechselt, ändert sich hier eine Zeile und die Anzeige stimmt wieder.
        "kontextJahr": 2023,
        "median": median,
        "regionen": regionen,
    }, ensure_ascii=False, allow_nan=False), encoding="utf-8")

    mit_kontext = sum(1 for r in inland if r.get("genehmigungen") is not None)
    print(f"  ✓ {len(regionen):,} Regionen → {ziel.relative_to(ROOT)} "
          f"({ziel.stat().st_size/1024:.0f} KB)")
    print(f"    davon {len(inland):,} in Deutschland, {mit_kontext:,} mit Destatis-Kontext")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
