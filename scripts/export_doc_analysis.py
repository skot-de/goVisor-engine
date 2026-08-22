#!/usr/bin/env python3
"""LLM-Vergabe-Analyse je Vorgang → web/data/doc-analysis/<id>.json

**Warum eine Datei je Vorgang.** `doc-analysis.json` war am 2026-08-22 auf **252 MB**
gewachsen (6.262 Auswertungen à rund 690 Zeichen). `/api/lead-detail` lud und parste sie
vollstaendig, um EINE Auswertung herauszugreifen — lokal ein Plattenzugriff, im Betrieb ein
Netzabruf von 252 MB je Instanz und Kaltstart. Dazu hielt die Route sie in einer
Modulvariable OHNE Verfall: eine laufende Instanz haette bis zum naechsten Deployment die
Auswertungen von gestern geliefert.

Denselben Weg ist `doc-text` schon gegangen (294 MB → eine Datei je Vorgang, s.
`scripts/export_doc_text.py`). Dies ist die gleiche Kur fuer die Auswertungen.

⚠ DIE SAMMELDATEI BLEIBT — sie ist der ARBEITSSTAND des Analyse-Arbeiters. `analyze_docs.py`
schreibt sie, `analyse_arbeiter.sh` liest sie, um zu wissen, was noch fehlt. Sie gehoert
damit zum Betrieb, nicht zum Frontend, und wird vom Upload ausgenommen (s.
`upload_web_data.py`): 252 MB jede Nacht hochzuladen, damit sie niemand liest, waere teuer
und sinnlos.

Aufruf: python3 scripts/export_doc_analysis.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SAMMEL = ROOT / "web" / "data" / "doc-analysis.json"
JE_VORGANG = ROOT / "web" / "data" / "doc-analysis"
# Verzeichnis ohne Inhalt: wer ausgewertet ist, mit Ampel. Rund 300 KB statt 252 MB, und es
# beantwortet die Fragen des Lauf-Monitors, ohne die Auswertungen selbst zu laden.
INDEX = ROOT / "web" / "data" / "doc-analysis-index.json"

# Dateinamen kommen aus fremden Kennungen (TED, DTVP, NetServer). Alles ausser dem engen
# Zeichensatz fliegt raus — der Name landet in einem Pfad, und `..` waere ein Weg hinaus.
_SICHER = re.compile(r"[^A-Za-z0-9_-]")


def main() -> int:
    if not SAMMEL.exists():
        print(f"  ✖ {SAMMEL.relative_to(ROOT)} fehlt — analyze_docs.py noch nicht gelaufen?")
        return 1
    daten = json.loads(SAMMEL.read_text(encoding="utf-8"))
    JE_VORGANG.mkdir(parents=True, exist_ok=True)

    vorher = {p.name for p in JE_VORGANG.glob("*.json")}
    geschrieben, uebersprungen = 0, 0
    index = {}
    for kennung, eintrag in daten.items():
        sicher = _SICHER.sub("", str(kennung))
        if not sicher:
            uebersprungen += 1
            continue
        ziel = JE_VORGANG / f"{sicher}.json"
        text = json.dumps(eintrag, ensure_ascii=False)
        # Nur schreiben, was sich geaendert hat: der Arbeiter laeuft staendig, der Export
        # taeglich. Unveraendert neu zu schreiben hiesse, jede Nacht 6.262 Dateien als
        # „geaendert" in den Objektspeicher zu schieben.
        if ziel.exists() and ziel.read_text(encoding="utf-8") == text:
            uebersprungen += 1
        else:
            ziel.write_text(text, encoding="utf-8")
            geschrieben += 1
        vorher.discard(f"{sicher}.json")
        index[sicher] = {"ampel": eintrag.get("ampel") if isinstance(eintrag, dict) else None}

    # Was der Arbeitsstand nicht mehr kennt, gehoert auch nicht mehr ins Frontend.
    for tot in vorher:
        (JE_VORGANG / tot).unlink(missing_ok=True)

    INDEX.write_text(json.dumps(index, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(f"  {len(daten):,} Auswertungen → {geschrieben:,} geschrieben, "
          f"{uebersprungen:,} unveraendert, {len(vorher):,} entfernt")
    print(f"  Index: {INDEX.relative_to(ROOT)} ({INDEX.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
