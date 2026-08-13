"""Leistungsumfang + Entscheidungskriterien → ``web/data/doc-struktur.json``.

Bisher lagen ``doc_positions.parquet`` (Leistungsverzeichnisse aus GAEB + Preisblättern)
und ``doc_criteria.parquet`` (UfAB-Kriterienmatrizen) nur als Parquet herum: extrahiert,
aber im Produkt unsichtbar. Dieses Skript reicht sie an die Detailansicht durch — analog
``export_doc_signals.py``, leichter Pfad, kein Voll-Reexport.

**Warum nicht alles.** Ein Bau-LV hat bis zu mehrere tausend Positionen; die vollständig
in eine JSON zu schreiben, die das Frontend bei jedem Lead-Detail lädt, wäre teuer und
für die Entscheidung „biete ich mit?" nutzlos. Deshalb je Vorgang:

* **vollständig** die Mengen-Summen je Einheit (m², Stück, Std …) — das ist die Antwort
  auf „wie viel wovon", und sie ist über ALLE Positionen gerechnet, nicht über den Auszug;
* **ein Auszug** der ersten ``_TOP`` Positionen in **Dokumentreihenfolge**. Bewusst keine
  eigene Rangfolge: „die größten Positionen" wäre bei gemischten Einheiten (150 m² vs.
  3 Stück) eine Scheinordnung. Die LV-Reihenfolge ist die Ordnung, die der Auftraggeber
  selbst gewählt hat. Der Auszug ist im UI als solcher gekennzeichnet.

Bei den Kriterien wird nicht gekürzt (6.832 Zeilen über wenige Vorgänge), aber ``A`` und
``B`` getrennt geführt: ``A = Ausschlusskriterium`` ist die K.o.-Liste und beantwortet die
erste Frage jedes Bieters, ``B = Bewertungskriterium`` die zweite.

**Der Download.** Zusätzlich zur Anzeige schreibt das Skript je Vorgang eine CSV nach
``web/data/lv/`` bzw. ``web/data/kriterien/`` — die VOLLSTÄNDIGE Tabelle, nicht den Auszug.
Das ist unser eigenes Arbeitsergebnis: die Portale liefern eine GAEB-Datei oder ein
Excel-Formular, das man erst aufbereiten muss. Fremde Original-Unterlagen geben wir
bewusst nicht weiter (sie ändern sich während der Frist — eine veraltete Kopie, auf der
jemand kalkuliert, ist ein Haftungsfall); der Portal-Link steht daneben.

CSV-Konvention: **Semikolon** als Trenner, **Dezimalkomma**, UTF-8 **mit BOM**. Ohne diese
drei zerlegt Excel in deutscher Ländereinstellung die Datei in eine einzige Spalte bzw.
liest „1,5" als Text — die Datei wäre formal korrekt und praktisch unbrauchbar.

Aufruf: python3 scripts/export_doc_struktur.py [--country DE]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "data" / "doc-struktur.json"
CSV_LV = ROOT / "web" / "data" / "lv"
CSV_KRIT = ROOT / "web" / "data" / "kriterien"

_TOP = 30          # Positionen je Vorgang im Auszug
_MAX_KRIT = 120    # Kriterien je Vorgang — deckt jede real gesehene Matrix ab


def _schreibe_csv(ziel: Path, kopf: list[str], zeilen: list[tuple]) -> None:
    """Eine Excel-taugliche CSV: Semikolon, Dezimalkomma, BOM."""
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    w.writerow(kopf)
    for z in zeilen:
        w.writerow(["" if v is None
                    else str(v).replace(".", ",") if isinstance(v, float)
                    else v for v in z])
    ziel.write_text("﻿" + puffer.getvalue(), encoding="utf-8")


def main(country: str) -> int:
    import duckdb

    root = ROOT / "data" / "docs" / country
    pos_p, krit_p = root / "doc_positions.parquet", root / "doc_criteria.parquet"
    if not pos_p.exists() and not krit_p.exists():
        print(f"weder doc_positions noch doc_criteria in {root} — erst extract_* laufen lassen.")
        return 1
    con = duckdb.connect()
    aus: dict[str, dict] = {}

    if pos_p.exists():
        # Kopfzahlen je Vorgang: über ALLE Positionen, nicht über den Auszug.
        # Nur die Mengen je Einheit; Positionszahl und Herkunft kommen aus der nächsten
        # Abfrage. (Sie standen hier einmal mit drin und wurden dort ohnehin überschrieben.)
        for nid, einheiten in con.execute(f"""
            SELECT notice_id,
                   to_json(map_from_entries(list(struct_pack(k := einheit, v := s))))
            FROM (
              -- NICHT nach `quelle` gruppieren: seit der Flat-Leser dazukam, liefert derselbe
              -- Vorgang dieselbe Einheit unter „gaeb" UND „gaeb-flat" — als Map-Schlüssel
              -- kollidiert das ("Map keys must be unique"). Die Menge je Einheit ist ohnehin
              -- eine Summe über den ganzen Vorgang, nicht je Parser.
              SELECT notice_id, einheit, round(sum(menge), 1) AS s
              FROM read_parquet('{pos_p.as_posix()}')
              WHERE einheit IS NOT NULL AND menge IS NOT NULL
              GROUP BY 1, 2
            ) GROUP BY 1""").fetchall():
            aus.setdefault(nid, {})["mengen"] = json.loads(einheiten)
        for nid, n, quellen in con.execute(f"""
            SELECT notice_id, count(*), string_agg(DISTINCT quelle, ',')
            FROM read_parquet('{pos_p.as_posix()}') GROUP BY 1""").fetchall():
            d = aus.setdefault(nid, {})
            d["nPositionen"] = n
            d["quelle"] = quellen

        for nid, js in con.execute(f"""
            SELECT notice_id, to_json(list(struct_pack(
                     rno := rno, menge := menge, einheit := einheit, text := text)))
            FROM (SELECT *, row_number() OVER (PARTITION BY notice_id) AS i
                  FROM read_parquet('{pos_p.as_posix()}')
                  WHERE text IS NOT NULL AND length(text) >= 8)
            WHERE i <= {_TOP} GROUP BY 1""").fetchall():
            aus.setdefault(nid, {})["positionen"] = json.loads(js)

    if krit_p.exists():
        for nid, js in con.execute(f"""
            SELECT notice_id, to_json(list(struct_pack(
                     code := code, art := art, text := text, kg := kg,
                     gewichtung := gewichtung, prozent := prozent)))
            FROM (SELECT *, row_number() OVER (PARTITION BY notice_id) AS i
                  FROM read_parquet('{krit_p.as_posix()}'))
            WHERE i <= {_MAX_KRIT} GROUP BY 1""").fetchall():
            k = json.loads(js)
            aus.setdefault(nid, {})["kriterien"] = {
                "ausschluss": [x for x in k if x["art"] == "ausschluss"],
                "bewertung": [x for x in k if x["art"] == "bewertung"],
            }

    # ── CSV je Vorgang: die VOLLSTÄNDIGE Tabelle, nicht der Auszug oben. ──────────────
    # Die Dateinamen sind reine notice_ids; die Route validiert sie zusätzlich gegen
    # Pfad-Traversal, bevor sie ausliefert (der Dateiname kommt dort aus dem Query-String).
    n_csv = 0
    if pos_p.exists():
        CSV_LV.mkdir(parents=True, exist_ok=True)
        for f in CSV_LV.glob("*.csv"):
            f.unlink()                      # alter Stand darf nicht als aktueller durchgehen
        for nid, js in con.execute(f"""
            SELECT notice_id, to_json(list(struct_pack(
                     rno := rno, text := text, menge := menge,
                     einheit := einheit, quelle := quelle, datei := datei)))
            FROM read_parquet('{pos_p.as_posix()}') GROUP BY 1""").fetchall():
            zeilen = [(p["rno"], p["text"], p["menge"], p["einheit"], p["quelle"], p["datei"])
                      for p in json.loads(js)]
            _schreibe_csv(CSV_LV / f"{nid}.csv",
                          ["Pos.", "Leistung", "Menge", "Einheit", "Quelle", "Datei"], zeilen)
            n_csv += 1
    if krit_p.exists():
        CSV_KRIT.mkdir(parents=True, exist_ok=True)
        for f in CSV_KRIT.glob("*.csv"):
            f.unlink()
        for nid, js in con.execute(f"""
            SELECT notice_id, to_json(list(struct_pack(
                     code := code, art := art, text := text, khg := khg, kg := kg,
                     gewichtung := gewichtung, gew_gruppe := gew_gruppe,
                     gew_hauptgruppe := gew_hauptgruppe, prozent := prozent)))
            FROM read_parquet('{krit_p.as_posix()}') GROUP BY 1""").fetchall():
            zeilen = [(k["code"],
                       "Ausschluss" if k["art"] == "ausschluss" else "Bewertung",
                       k["text"], k["khg"], k["kg"], k["gewichtung"],
                       k["gew_gruppe"], k["gew_hauptgruppe"], k["prozent"])
                      for k in json.loads(js)]
            _schreibe_csv(CSV_KRIT / f"{nid}.csv",
                          ["Code", "Art", "Kriterium", "Hauptgruppe", "Gruppe",
                           "Gewichtung", "Gewicht Gruppe", "Gewicht Hauptgruppe", "Prozent"],
                          zeilen)

    OUT.write_text(json.dumps(aus, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    mit_pos = sum(1 for v in aus.values() if v.get("nPositionen"))
    mit_krit = sum(1 for v in aus.values() if v.get("kriterien"))
    kb = OUT.stat().st_size / 1024
    print(f"Doc-Struktur: {len(aus)} Vorgänge → {OUT.name} ({kb:,.0f} KB)")
    print(f"  {mit_pos} mit Leistungsverzeichnis, {mit_krit} mit Kriterienmatrix")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="DE")
    sys.exit(main(ap.parse_args().country))
