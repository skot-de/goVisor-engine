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

Aufruf: python3 scripts/export_doc_struktur.py [--country DE]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "data" / "doc-struktur.json"

_TOP = 30          # Positionen je Vorgang im Auszug
_MAX_KRIT = 120    # Kriterien je Vorgang — deckt jede real gesehene Matrix ab


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
        for nid, n, quellen, einheiten in con.execute(f"""
            SELECT notice_id, count(*),
                   string_agg(DISTINCT quelle, ','),
                   to_json(map_from_entries(list(struct_pack(k := einheit, v := s))))
            FROM (
              SELECT notice_id, quelle, einheit, round(sum(menge), 1) AS s
              FROM read_parquet('{pos_p.as_posix()}')
              WHERE einheit IS NOT NULL AND menge IS NOT NULL
              GROUP BY 1, 2, 3
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
