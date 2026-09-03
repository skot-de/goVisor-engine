#!/usr/bin/env python3
"""Strukturierte Anforderungs-Signale aus den Vergabeunterlagen → web/data/doc-signals.json.

Quelle: data/docs/<country>/doc_signals.parquet (aus `signals-docs`), je notice_id ein Satz.

⚠ WELCHE FELDER MITGEHEN, STEHT NICHT HIER, sondern in `govisor/kennzahlen.py`
(`DOC_SIGNALE`). Bis zum 2026-09-01 zählte dieses Skript seine Spalten selbst auf, und genau
dort gingen sechs Signale verloren: erkannt wurden fünfzehn, geschrieben sieben. Betroffen
waren `binding_until` (5.747 Sätze), `penalty_pct` (4.066), `site_visit` (3.723),
`site_visit_mandatory` (3.723), `presentation_required` (3.576) und `skonto_pct` (393) —
gebaut, gemessen, gespeichert und nie gezeigt. Wer ein Signal ergänzt, trägt es dort ein;
`tests/test_kennzahlen.py` meldet jede Parquet-Spalte, die im Verzeichnis fehlt.

Ausgabe pro notice_id ein kompaktes Objekt für die Detail-Anzeige (Anforderungs-Check aus den
Unterlagen). Leichter Pfad analog doc-text.json — die /api/lead-detail hängt es je Lead an,
kein Voll-Reexport nötig.

Aufruf: python3 scripts/export_doc_signals.py
"""
import json
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from govisor import kennzahlen  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# ⚠ ALLE LAENDER — gleiche Begruendung wie in export_doc_text.py: die Ausgabe ist nach
# `notice_id` verschluesselt, TED-Nummern sind eindeutig, und ein Laenderparameter waere nur
# eine weitere Stelle, an der jemand ein Land vergessen kann.
def _quellen() -> list[Path]:
    return sorted((ROOT / "data" / "docs").glob("*/doc_signals.parquet"))


def _qlist() -> str:
    q = _quellen()
    return "[" + ", ".join(f"'{x.as_posix()}'" for x in q) + "]" if q else "['']"


OUT = ROOT / "web" / "data" / "doc-signals.json"


def main() -> int:
    if not _quellen():
        print(f"FEHLT: kein doc_signals.parquet unter {ROOT / 'data' / 'docs'} "
              f"— erst `signals-docs` laufen lassen.")
        return 1
    con = duckdb.connect()
    # ⚠ KEINE HANDGETIPPTE SPALTENLISTE MEHR. Genau hier gingen am 2026-09-01 sechs Felder
    # verloren: `docsignals` erkannte fünfzehn Signale, das Parquet trug fünfzehn, und dieses
    # SELECT nannte sieben. Der API-Typ und der Renderer erbten die Lücke, weil sie dieselbe
    # Liste ein zweites und drittes Mal führten. Die Spalten kommen jetzt aus
    # `govisor.kennzahlen`, und ein Wächter prüft, dass das Parquet keine Spalte trägt, die
    # dort fehlt — ein neues Signal fällt damit auf, statt lautlos liegenzubleiben.
    felder = kennzahlen.DOC_SIGNALE
    spalten = ", ".join(kennzahlen.spalten(felder))
    rows = con.execute(
        f"SELECT notice_id, {spalten} FROM read_parquet({_qlist()})"
    ).fetchall()

    out = {}
    for zeile in rows:
        nid, werte = zeile[0], zeile[1:]
        obj = {}
        for k, v in zip(felder, werte):
            if k.spalte == "award_weights":
                # Als JSON gespeichert, damit die Gewichtung ihre Kriteriennamen behält.
                try:
                    v = json.loads(v) if v else None
                except (json.JSONDecodeError, TypeError):
                    v = None
            elif k.spalte == "certificates":
                v = [c.strip() for c in v.split(",")] if v else []
            obj[k.schluessel] = v
        # Nur Vorgänge mit mindestens EINEM belegten Signal aufnehmen.
        if any(v not in (None, [], {}, False) for v in obj.values()):
            out[nid] = obj

    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    belegt = {k.schluessel: sum(1 for v in out.values() if v.get(k.schluessel) not in (None, [], {}, False))
              for k in felder}
    print(f"Doc-Signale: {len(out)} Vorgänge → {OUT.name}")
    print("  Belegung:", ", ".join(f"{k}={n}" for k, n in belegt.items() if n))
    leer = [k for k, n in belegt.items() if not n]
    if leer:
        # Ein Signal ohne einen einzigen Beleg ist entweder neu oder kaputt. Beides gehört
        # gesagt, sonst sucht später jemand im Frontend nach einem Feld, das nie ankam.
        print("  ⚠ ohne Beleg:", ", ".join(leer))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
