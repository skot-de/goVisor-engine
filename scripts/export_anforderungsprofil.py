#!/usr/bin/env python3
"""Anforderungsprofil je Vorgang → web/data/anforderungsprofil.json (Kennzahl 2).

DIE FRAGE. Verlangt dieser Vorgang mehr als üblich, und worin? Aus `doc_checklist` je Bereich
die Anzahl, dazu die Verteilung über alle ausgewerteten Vorgänge.

    Bereich       Vorgänge   Median   p90
    leistung         7.304       25    39
    formalitaet      7.375       19    38
    vertrag          6.012        6    18
    termin           6.596        4    11
    ausschluss       4.258        5     9
    zuschlag         1.460        3    12
    eignung          3.212        3    10

⚠ „STRENGE" IST FÜR DIE HÄLFTE DER BEREICHE DAS FALSCHE WORT. Die Übergabe nennt die Kennzahl
so; nachgesehen, was wirklich drinsteht:

    eignung      „Technische Mindesteignung", „Mindestanzahl vergleichbarer Referenzen"
                 → eine Hürde. Wer sie nicht nimmt, darf nicht bieten.
    ausschluss   „Ausschluss-/Mindestbedingung" → ebenfalls eine Hürde.
    formalitaet  „Ausfüllbares Formular (61 Felder, 0 Pflicht)" → Aufwand, keine Hürde.
    leistung     „Leistungsumfang / Menge" → Umfang. Eine ausführliche Leistungsbeschreibung
                 ist nicht streng, sie ist ausführlich.

Deshalb trägt jeder Bereich hier seine ART mit, und die Anzeige wählt danach das Wort. Alles
„Strenge" zu nennen wäre eine Behauptung, die die Daten nicht hergeben.

⚠ GEPRÜFT: DIE ZAHL MISST DIE VERGABE, NICHT UNS. Die Sorge war, dass mehr gelesene Dateien
automatisch mehr Anforderungen ergeben — der Fehler, an dem Kennzahl 1 fast gescheitert wäre.
Nachgemessen sind die Mediane über die Datei-Zahl stabil (leistung 25/25/25/26 bei 0–1, 2–3,
4–6, 7+ Dateien; eignung 3/3/3/3), Korrelation 0,196. Die Achse trägt.

Aufruf: python3 scripts/export_anforderungsprofil.py
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "data" / "anforderungsprofil.json"

# Bereich → Art. Steuert das Wort in der Anzeige, nicht die Rechnung.
ART = {
    "eignung": "huerde", "ausschluss": "huerde",
    "formalitaet": "aufwand", "termin": "aufwand",
    "leistung": "umfang", "vertrag": "umfang", "zuschlag": "umfang",
}
MIND_VORGAENGE = 200          # unter dieser Zahl kein Vergleichswert


def main() -> int:
    con = duckdb.connect()
    raus: dict = {"bereiche": {}, "leads": {}}
    # ⚠ LU seit 2026-09-03. Die Schleife prueft je Land auf die Datei und ueberspringt,
    # was fehlt — ein Land hier zu vergessen wirft also KEINEN Fehler, es zaehlt nur
    # nicht mit. Genau so hat LU 279 Leads lang gefehlt, ohne dass etwas rot wurde.
    for land in ("DE", "AT", "CH", "LU"):
        C = ROOT / "data" / "gold" / land / "doc_checklist.parquet"
        if not C.exists():
            continue
        zeilen = con.execute(f"""
          select bereich, notice_id, count(*) k
          from read_parquet('{C.as_posix()}')
          where bereich is not null group by 1, 2
        """).fetchall()
        je_bereich: dict[str, list[int]] = {}
        for bereich, nid, k in zeilen:
            je_bereich.setdefault(bereich, []).append(int(k))
            raus["leads"].setdefault(nid, {})[bereich] = int(k)
        for bereich, werte in sorted(je_bereich.items()):
            if len(werte) < MIND_VORGAENGE:
                print(f"  {land}/{bereich}: nur {len(werte)} Vorgaenge — kein Vergleichswert")
                continue
            werte.sort()
            bei = lambda p: werte[min(len(werte) - 1, int(len(werte) * p))]   # noqa: E731
            raus["bereiche"][f"{land}:{bereich}"] = {
                "n": len(werte), "median": bei(0.5), "hoch": bei(0.90),
                "art": ART.get(bereich, "umfang"),
            }
            print(f"  {land}/{bereich:<12} {len(werte):>5} Vorgaenge · Median {bei(0.5):>3} · "
                  f"oberstes Zehntel ab {bei(0.90):>3} · {ART.get(bereich, 'umfang')}")

    if not raus["bereiche"]:
        print("FEHLT: keine Datengrundlage — erst `doc_checklist` bauen lassen.")
        return 1
    OUT.write_text(json.dumps(raus, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Anforderungsprofil: {len(raus['leads']):,} Vorgaenge, {len(raus['bereiche'])} Bereiche "
          f"→ {OUT.name} ({OUT.stat().st_size / 1024:.0f} kB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
