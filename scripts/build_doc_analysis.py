#!/usr/bin/env python3
"""Die LLM-Auswertung der Vergabeunterlagen in die Gold-Ebene holen.

WARUM ES DAS GIBT. `analyze_docs.py` schreibt sein Ergebnis nach
`web/data/doc-analysis/<notice>.json` — also in das AUSLIEFERUNGSVERZEICHNIS des Frontends.
Gemessen am 2026-09-01: 7.188 Vorgaenge, 395 MB, **633.078 Einzelaussagen**, entstanden aus
165 Millionen Token. Es ist das einzige Artefakt des Projekts, fuer das echtes Geld geflossen
ist, und das einzige ohne Platz in der Datenhaltung.

Drei Folgen, alle unangenehm:

1. **Nicht abfragbar.** „Welche laufenden Vergaben verlangen ISO 27001?", „Wie oft wiegt der
   Preis ueber 70 %?", „Welche Vergabestelle verlangt immer einen Pflicht-Ortstermin?" —
   keine dieser Fragen liess sich beantworten, ohne 7.188 Dateien zu durchsuchen.
2. **Nicht verbindbar.** Kein Join gegen Leads, Vergabestellen oder die Traeger-Ebene.
3. **Fluechtig.** `web/data` ist eine abgeleitete Auslieferung. Wird sie neu gebaut, waere die
   bezahlte Auswertung weg, und das Nachbauen kostet wieder Geld.

Dieses Skript legt zwei Tabellen an. Danach ist die Auswertung dauerhaft, abfragbar und
verbindbar — und `web/data/doc-analysis/*.json` ist nur noch eine Kopie fuer die Auslieferung.

⚠ RICHTUNG. Heute liest dieses Skript die JSON und schreibt die Tabellen. Richtig waere
umgekehrt: `analyze_docs.py` schreibt die Tabellen, der Web-Export leitet die JSON daraus ab
(so wie `leads-*.json` aus Gold entsteht). Das ist der naechste Schritt; solange die JSON die
Quelle ist, bleibt sie es auch. Der Gewinn hier ist die DAUERHAFTIGKEIT und die Abfragbarkeit,
nicht die Umkehrung.

⚠ ZITATE KOMMEN MIT. Eine Anforderung ohne Beleg ist eine Behauptung. Jede Zeile in
`doc_checklist` traegt `quote`, `source_file`, `source_page` und dazu `marking`
(Zitat/Extrahiert/Abgeleitet) sowie `parser` (leer = LLM, sonst `pdf_fields`/`gaeb`/`xlsx`).
Ohne diese Spalten waere die Tabelle die Haelfte wert — und die Lernschleife unmoeglich, denn
sie lebt davon, Aussagen nach Herkunft und Belegart trennen zu koennen.

Aufruf:  python3 scripts/build_doc_analysis.py [--land DE] [--quelle web/data/doc-analysis]
         [--ziel data/gold]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Kopf-Felder je Vorgang. `doctypes_seen`, `parsed_files` und Co. sind Listen — sie werden
# gezaehlt statt gespeichert; wer die Namen braucht, geht an die Rohdatei. Eine Zahl in der
# Tabelle ist abfragbar, eine Liste in einer Zelle waere es nicht.
def _kopf(notice_id: str, d: dict, stand: str) -> tuple:
    def n(feld):
        v = d.get(feld)
        return len(v) if isinstance(v, (list, dict)) else 0
    return (
        notice_id,
        d.get("ampel"), d.get("ampel_grund"), d.get("zusammenfassung"),
        n("checklist"), n("eignung"), n("zuschlag"), n("fristen"),
        n("ko_kriterien"), n("aufwand"), n("positions"),
        len(d.get("parsed_files") or []), len(d.get("doctypes_seen") or []),
        len(d.get("missing_expected") or []), len(d.get("truncated_doctypes") or []),
        int(d.get("rejected_items") or 0),
        int(d.get("token_cost") or 0),
        d.get("provider"), d.get("model"), stand,
    )


KOPF_SPALTEN = (
    "notice_id VARCHAR, ampel VARCHAR, ampel_grund VARCHAR, zusammenfassung VARCHAR, "
    "n_checklist BIGINT, n_eignung BIGINT, n_zuschlag BIGINT, n_fristen BIGINT, "
    "n_ko_kriterien BIGINT, n_aufwand BIGINT, n_positions BIGINT, "
    "n_parsed_files BIGINT, n_doctypes BIGINT, n_missing_expected BIGINT, "
    "n_truncated BIGINT, rejected_items BIGINT, token_cost BIGINT, "
    "provider VARCHAR, model VARCHAR, stand VARCHAR"
)

CHECK_SPALTEN = (
    "notice_id VARCHAR, nr BIGINT, req_type VARCHAR, theme VARCHAR, label VARCHAR, "
    "value VARCHAR, unit VARCHAR, wert_num DOUBLE, quote VARCHAR, "
    "source_file VARCHAR, source_page VARCHAR, marking VARCHAR, parser VARCHAR"
)


def _zahl(v):
    """`wert_num` kommt mal als Zahl, mal als Text, mal gar nicht. Nie werfen."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
        return f if f == f else None          # NaN faengt sich selbst
    except (TypeError, ValueError):
        return None


def lies(quelle: pathlib.Path) -> tuple[list, list, int]:
    kopf, punkte, kaputt = [], [], 0
    for pfad in sorted(quelle.glob("*.json")):
        try:
            d = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            kaputt += 1
            continue
        if not isinstance(d, dict):
            kaputt += 1
            continue
        notice_id = pfad.stem
        stand = datetime.fromtimestamp(pfad.stat().st_mtime, timezone.utc).date().isoformat()
        kopf.append(_kopf(notice_id, d, stand))
        for i, it in enumerate(d.get("checklist") or [], start=1):
            if not isinstance(it, dict):
                continue
            punkte.append((
                notice_id, i,
                it.get("req_type"), it.get("theme"), it.get("label"),
                None if it.get("value") is None else str(it.get("value")),
                it.get("unit"), _zahl(it.get("wert_num")),
                it.get("quote"), it.get("source_file"),
                None if it.get("source_page") is None else str(it.get("source_page")),
                it.get("marking"), it.get("parser"),
            ))
    return kopf, punkte, kaputt


def schreibe(con, pfad: pathlib.Path, zeilen: list, spalten: str) -> None:
    """Wie `gold._write`: ueber Arrow statt executemany — bei 400.000 Zeilen ist das der
    Unterschied zwischen Sekunden und Minuten."""
    pfad.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"CREATE OR REPLACE TABLE _t ({spalten})")
    if zeilen:
        import pyarrow as pa
        namen = [s.strip().split()[0] for s in spalten.split(",")]
        spaltenweise = list(zip(*zeilen))
        tbl = pa.table({namen[i]: pa.array(spaltenweise[i]) for i in range(len(namen))})
        con.register("_arrow", tbl)
        con.execute("INSERT INTO _t SELECT * FROM _arrow")
        con.unregister("_arrow")
    con.execute(f"COPY (SELECT * FROM _t) TO '{pfad}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.execute("DROP TABLE _t")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--land", default="DE")
    p.add_argument("--quelle", default="web/data/doc-analysis")
    p.add_argument("--ziel", default="data/gold")
    a = p.parse_args()

    quelle = (ROOT / a.quelle) if not pathlib.Path(a.quelle).is_absolute() else pathlib.Path(a.quelle)
    if not quelle.is_dir():
        print(f"  keine Auswertung unter {quelle} — nichts zu tun.")
        return 0

    kopf, punkte, kaputt = lies(quelle)
    if not kopf:
        print(f"  {quelle} ist leer — nichts zu tun.")
        return 0

    import duckdb
    ziel = (ROOT / a.ziel) if not pathlib.Path(a.ziel).is_absolute() else pathlib.Path(a.ziel)
    con = duckdb.connect()
    schreibe(con, ziel / a.land / "doc_analysis.parquet", kopf, KOPF_SPALTEN)
    schreibe(con, ziel / a.land / "doc_checklist.parquet", punkte, CHECK_SPALTEN)
    con.close()

    mit_zitat = sum(1 for z in punkte if z[8])
    print(f"  doc_analysis : {len(kopf):,} Vorgaenge")
    print(f"  doc_checklist: {len(punkte):,} Anforderungen, davon {mit_zitat:,} "
          f"({mit_zitat/max(len(punkte),1)*100:.1f} %) mit Zitat")
    if kaputt:
        print(f"  ⚠ {kaputt} Datei(en) nicht lesbar — uebersprungen, nicht stillschweigend gezaehlt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
