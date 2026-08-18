#!/usr/bin/env python3
"""Datenqualität messen — jede Nacht dieselben Zahlen, mit Vortageswert.

**Warum es das braucht.** Jede Zahl, mit der wir heute gearbeitet haben — 40 % der offenen
Leads ohne Bundesland, 54 % der Entitäten nur über den Namen aufgelöst, 1.332 Zeilen mit der
PLZ im Ortsfeld — ist von Hand ermittelt worden. Solange das so bleibt, merkt eine
Verschlechterung niemand. Genau daran ist in diesem Projekt schon zweimal etwas monatelang
unbemerkt geblieben: 14 statt 4.499 Volltexte im Frontend, und ein Signal-Export, der nach
dem Index nicht mehr lief.

**Der Verlauf ist der Punkt, nicht der Stand.** Eine Kennzahl ohne Vortageswert sagt nur,
wie es ist; erst der Vergleich sagt, ob jemand etwas kaputt gemacht hat. Deshalb schreibt
der Bericht bei jedem Lauf eine Zeile in `qualitaet_verlauf.jsonl` und liefert im
Ergebnis Stand UND Vortag.

**Was NICHT hineingehört.** Geschäftszahlen. „Wie viele Ausschreibungen haben wir" gehört
ins Produkt, nicht in die Qualitätsmessung. Hier steht nur, was über die VERLÄSSLICHKEIT
der Daten Auskunft gibt — Lücken, Herkünfte, Widersprüche.

Aufruf::  scripts/qualitaet_bericht.py
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
G = ROOT / "data/gold/DE"
SILBER = ROOT / "data/silver/DE/notice_parties"
VERLAUF = G / "qualitaet_verlauf.jsonl"
BERICHT = ROOT / "web/data/qualitaet.json"


def messen() -> dict:
    import duckdb

    con = duckdb.connect()
    le = (G / "lead_export.parquet").as_posix()
    ent = (G / "entities.parquet").as_posix()
    m: dict[str, float] = {}

    # ── Leads: was der Kunde sieht ───────────────────────────────────────────────────────
    # Getrennt nach offen und gesamt, weil sich beides stark unterscheidet: die offenen
    # kommen ueberwiegend aus den unterschwelligen Quellen und sind schlechter befuellt.
    for name, wo in (("gesamt", "TRUE"), ("offen", "phase = 'open'")):
        zeile = con.execute(f"""SELECT count(*),
            count(*) FILTER (WHERE buyer_nuts1 IS NULL OR buyer_nuts1 = ''),
            count(*) FILTER (WHERE NOT market_region_known),
            count(*) FILTER (WHERE value_eur IS NULL),
            count(*) FILTER (WHERE cpv_code IS NULL OR cpv_code = '')
            FROM '{le}' WHERE {wo}""").fetchone()
        n = zeile[0] or 1
        m[f"leads_{name}"] = zeile[0]
        m[f"ohne_bundesland_{name}_pct"] = round(100 * zeile[1] / n, 1)
        m[f"ohne_marktregion_{name}_pct"] = round(100 * zeile[2] / n, 1)
        m[f"ohne_wert_{name}_pct"] = round(100 * zeile[3] / n, 1)
        m[f"ohne_cpv_{name}_pct"] = round(100 * zeile[4] / n, 1)

    # ── Entitäten: wie belegt ist die Auflösung? ─────────────────────────────────────────
    for methode, n in con.execute(
            f"SELECT method, count(*) FROM '{ent}' GROUP BY 1").fetchall():
        m[f"entitaeten_{methode}"] = n
    gesamt = sum(v for k, v in m.items() if k.startswith("entitaeten_")) or 1
    m["entitaeten_nur_name_pct"] = round(100 * m.get("entitaeten_nur_name", 0) / gesamt, 1)

    # ── Adressfelder: Fehler, die sich durch alles durchziehen ───────────────────────────
    # `town` mit einer Zahl darin ist ein vertauschtes Feld; gefunden beim Pruefen der
    # Zusammenfuehrungen („Ort=56070, PLZ=Koblenz").
    np_ = f"{SILBER.as_posix()}/**/*.parquet"
    zeile = con.execute(f"""SELECT count(*),
        count(*) FILTER (WHERE town IS NOT NULL AND regexp_matches(town, '^[0-9 -]+$')),
        count(*) FILTER (WHERE postal_code IS NOT NULL AND NOT regexp_matches(postal_code, '[0-9]')),
        count(*) FILTER (WHERE town IS NULL)
        FROM '{np_}'""").fetchone()
    m["parteien"] = zeile[0]
    m["ort_ist_zahl"] = zeile[1]
    m["plz_ohne_ziffer"] = zeile[2]
    m["ohne_ort_pct"] = round(100 * zeile[3] / (zeile[0] or 1), 1)

    # ── Abgeleitetes: wie viel steht auf zweiter Hand? ───────────────────────────────────
    fill = G / "lead_region_fill.parquet"
    if fill.exists():
        m["bundesland_abgeleitet"] = con.execute(
            f"SELECT count(*) FROM '{fill.as_posix()}'").fetchone()[0]
    karte = G / "entity_merge_map.parquet"
    if karte.exists():
        m["entitaeten_zusammenfuehrbar"] = con.execute(
            f"SELECT count(*) FROM '{karte.as_posix()}'").fetchone()[0]
    return m


def main() -> int:
    jetzt = messen()
    jetzt["stand"] = datetime.now().isoformat(timespec="seconds")

    vorher = None
    if VERLAUF.exists():
        zeilen = [z for z in VERLAUF.read_text(encoding="utf-8").splitlines() if z.strip()]
        if zeilen:
            vorher = json.loads(zeilen[-1])
    with VERLAUF.open("a", encoding="utf-8") as f:
        f.write(json.dumps(jetzt, ensure_ascii=False) + "\n")

    BERICHT.write_text(json.dumps({"jetzt": jetzt, "vorher": vorher}, ensure_ascii=False),
                       encoding="utf-8")

    print("  Datenqualität — Stand und Veränderung zum letzten Lauf\n")
    for schluessel, wert in jetzt.items():
        if schluessel == "stand":
            continue
        alt = (vorher or {}).get(schluessel)
        delta = ""
        if isinstance(wert, (int, float)) and isinstance(alt, (int, float)) and alt != wert:
            zeichen = "+" if wert > alt else ""
            delta = f"   ({zeichen}{round(wert - alt, 1):g})"
        print(f"    {schluessel:<34} {wert:>10,}{delta}")
    print(f"\n  → {BERICHT.relative_to(ROOT)} · Verlauf: {VERLAUF.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
