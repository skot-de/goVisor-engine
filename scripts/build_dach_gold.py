"""Volle Gold-Pipeline für AT und CH — dieselbe wie DE, in der richtigen Reihenfolge.

**Warum es dieses Skript gibt.** AT und CH liefen bis 2026-08-13 über eine Schmalspur-Brücke
(``gold.build_at_gold`` / ``simap.build_ch_gold``), die laut eigenem Docstring „bewusst KEINE
volle DE-Gold-Pipeline" baut. Ergebnis: **der Auslauf-Radar existierte für beide Länder gar
nicht** — in Deutschland macht er 86 % aller Leads aus. Gemessen lagen 227.117 österreichische
und 51.262 Schweizer Zuschläge im Silber, davon 62.118 bzw. 6.564 mit Vertragsende; Österreichs
Abdeckung (27,4 %) ist damit besser als die deutsche (14,9 %). Genutzt wurden sie zu 0 %.

**Die Überraschung war, dass fast nichts fehlte.** Von 20 Schritten liefen 18 ohne eine Zeile
Änderung — die Bauer sind längst länder-parametrisiert. Es fehlte allein die Reihenfolge. Sie
steht deshalb hier, an einer Stelle, statt in einem Kommentar.

Ergebnis des ersten Laufs: **AT 595 → 17.124 Leads, CH 1.591 → 8.608.**

**Reihenfolge ist Pflicht, nicht Geschmack.** Jeder Schritt liest, was der vorige schreibt;
die Fehlermeldung bei falscher Reihenfolge ist ein nichtssagendes „No files found that match
the pattern". Wer hier etwas einfügt, prüft die Abhängigkeit, statt es ans Ende zu hängen.

**Was NICHT läuft und warum:** ``build_hr_index`` nimmt kein ``country`` — es ist das deutsche
Handelsregister. Österreich hat das Firmenbuch, die Schweiz das Handelsregister der Kantone;
beides ist nicht angebunden. Die Entity-Auflösung für AT/CH steht damit auf Namen allein, ihre
Konfidenz ist entsprechend niedriger als in DE. Offener Punkt, kein stiller Mangel.

Aufruf:  python3 scripts/build_dach_gold.py [--laender AT,CH] [--as-of YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor.config import Config  # noqa: E402
from govisor import gold  # noqa: E402

# Reihenfolge = Abhängigkeitsgraph. Der Kommentar hinter jedem Schritt nennt, wofür sein
# Ergebnis gebraucht wird — damit man beim Umsortieren sieht, was man zerreißt.
KETTE: list[tuple[str, str]] = [
    ("build_entities",             "Entitäten + party_entity — Basis für alles Käufer-/Gewinner-bezogene"),
    ("build_entity_groups",        "leere Tabelle, wenn keine kuratierte CSV — Nachfolger brauchen die DATEI"),
    ("build_dim_cpv",              "CPV-Divisionen"),
    ("build_dim_deflator",         "Realwert-Faktor (AT/CH: DE-Näherung, in cpi_source gekennzeichnet)"),
    ("build_dim_plz",              "PLZ→Koordinate aus GeoNames"),
    ("build_dim_nuts",             "Regionen-Katalog"),
    ("build_quality",              "Qualitäts-Flags"),
    ("build_procedures",           "Verfahrens-Klammer"),
    ("build_contract_chains",      "Ketten (Alt-Modell, von displaceability gebraucht)"),
    ("build_contract_successions", "Nachfolge-Kanten (PLURAL-Datei!) für displaceability"),
    ("build_content_successions",  "inhaltsbasierte Nachfolgen (Singular-Datei) für succession_kpis"),
    ("build_award_tender_link",    "Zuschlag ↔ Ausschreibung"),
    ("build_succession_kpis",      "succession_events → incumbent_tenure"),
    ("build_incumbent_tenure",     "seit wann Incumbent — für lead_detail"),
    ("build_entity_identity",      "Gruppen-Identität"),
    ("build_duration_calibration", "CPV-Median-Laufzeiten"),
    ("build_lead_duration",        "Vertragsende je Lead — das Herz des Auslauf-Radars"),
    ("build_leads",                "die Auslauf-Leads selbst"),
    ("build_prospective_leads",    "offene Ausschreibungen dazu (f01/f02)"),
    ("build_displaceability",      "Verdrängbarkeit → displ_band in lead_export"),
    ("build_lead_deadline",        "Angebotsfrist"),
    ("build_value_band_effektiv",  "Gebühren-Band"),
    ("build_lead_geo",             "Koordinate je Lead (braucht dim_plz)"),
    ("build_lead_cpv",             "Mehr-CPV je Lead"),
    ("build_lead_detail",          "UI-View je Lead"),
    ("build_lead_export",          "was das Frontend liest — MUSS zuletzt"),
]


def lauf(land: str, as_of: str | None) -> tuple[int, int]:
    cfg = Config(countries=(land,), data_dir="data")
    ok = fehler = 0
    print(f"\n── {land} " + "─" * 56)
    for name, wofuer in KETTE:
        fn = getattr(gold, name, None)
        if fn is None:
            print(f"  · {name:<27} gibt es nicht — übersprungen")
            continue
        t0 = time.time()
        try:
            # Nur die Lead-Bauer kennen einen Stichtag; die übrigen lehnen ihn ab.
            if name in ("build_leads", "build_prospective_leads") and as_of:
                erg = fn(cfg, country=land, reference_date=as_of)
            else:
                erg = fn(cfg, country=land)
            ok += 1
            print(f"  ✓ {name:<27} {str(erg)[:34]:<34} {time.time()-t0:5.1f}s  · {wofuer}",
                  flush=True)
        except Exception as e:
            fehler += 1
            # NICHT abbrechen: ein später Schritt kann scheitern, ohne die früheren zu
            # entwerten. Aber laut, mit dem Grund — ein stiller Fehlschlag hier hiesse,
            # das Land steht morgen wieder auf dem alten Stand und niemand weiss warum.
            print(f"  ✖ {name:<27} {type(e).__name__}: {str(e)[:70]}", flush=True)
    return ok, fehler


def main(laender: list[str], as_of: str | None) -> int:
    gesamt_fehler = 0
    for land in laender:
        if not (ROOT / "data" / "silver" / land).exists():
            print(f"── {land}: kein Silber-Bestand — übersprungen")
            continue
        ok, fehler = lauf(land, as_of)
        gesamt_fehler += fehler
        print(f"   {land}: {ok} Schritte ok, {fehler} fehlgeschlagen")
    # Exit 1 nur bei Fehlern — der Tageslauf behandelt das als nicht-fatal, damit ein
    # AT/CH-Problem den deutschen Kern nicht mit herunterreisst.
    return 1 if gesamt_fehler else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--laender", default="AT,CH")
    ap.add_argument("--as-of", default=dt.date.today().isoformat())
    a = ap.parse_args()
    sys.exit(main([x.strip() for x in a.laender.split(",") if x.strip()], a.as_of))
