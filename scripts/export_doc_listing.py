#!/usr/bin/env python3
"""Dateilisten der Portale → web/data/doc-listing/<lead_id>.json

**Warum.** Zwei Abrufer holen, was die Portale ohne Anmeldung hergeben: nicht die Dateien,
sondern die **Liste der Dateinamen**. `govisor/subreport.py` (DE) und
`govisor/vergabeportal_at.py` (AT) schreiben sie samt erkanntem Dokumenttyp nach
`data/docs/<land>/doc_listing_*.parquet` — und dort lag sie bis zum 2026-08-22, ohne dass
irgendjemand sie las. Kein Pipeline-Schritt, kein Export, kein Frontend.

Gemessen an diesem Tag:

    DE  1.205 Vergaben · 28.871 Dateinamen · eignung 795, leistungsbeschreibung 787,
                                             vertrag 762, aufforderung 693
    AT    325 Vergaben ·  3.912 Dateinamen

    944 davon sind HEUTE offen und haben KEINEN Volltext (810 DE, 134 AT).
    Abdeckung mit Substanz: 26 % → 31 %. Für AT sind es die ersten Dokumentsignale ueberhaupt.

⚠ DIE LISTE ERSETZT DIE UNTERLAGEN NICHT und darf nicht so tun. Sie beantwortet zwei Fragen,
die sonst offen bleiben: gibt es ein Leistungsverzeichnis, und welche Nachweise werden
verlangt. Jede Anzeige muss den Unterschied zwischen „gelesen" und „nur gelistet" tragen —
deshalb steht `quelle` und `gelesen: false` in jeder Datei.

Aufruf: python3 scripts/export_doc_listing.py
"""
import json
import re
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ZIEL = ROOT / "web" / "data" / "doc-listing"
INDEX = ROOT / "web" / "data" / "doc-listing-index.json"

# Land → (Parquet, sprechender Quellenname fuer die Anzeige)
QUELLEN = {
    "DE": ("doc_listing_subreport.parquet", "subreport ELViS"),
    "AT": ("doc_listing_vergabeportal.parquet", "vergabeportal.at"),
}

_SICHER = re.compile(r"[^A-Za-z0-9_-]")


def main() -> int:
    con = duckdb.connect()
    ZIEL.mkdir(parents=True, exist_ok=True)
    vorher = {p.name for p in ZIEL.glob("*.json")}
    index, geschrieben, gleich = {}, 0, 0

    for land, (datei, quelle) in QUELLEN.items():
        p = ROOT / "data" / "docs" / land / datei
        if not p.exists():
            print(f"  {land}: {datei} fehlt — übersprungen")
            continue
        zeilen = con.execute(f"""
            SELECT lead_id, url, erfasst_am, n_dateien, dateien, doktypen, prioritaetstypen
            FROM read_parquet('{p.as_posix()}')
            WHERE n_dateien > 0""").fetchall()
        for lid, url, am, n, dateien, doktypen, prio in zeilen:
            sicher = _SICHER.sub("", str(lid))
            if not sicher:
                continue
            # Namen und Typen kommen als parallele Listen. Nicht blind zippen: laufen sie
            # auseinander, bekaeme eine Datei den Typ ihrer Nachbarin — und die Anzeige
            # behauptete etwas Falsches ueber ein Dokument, das wir nie gesehen haben.
            paare = list(zip(dateien or [], doktypen or []))
            if len(dateien or []) != len(doktypen or []):
                paare = [(d, None) for d in (dateien or [])]
            satz = {
                "quelle": quelle,
                "url": url,
                "erfasstAm": str(am) if am else None,
                "gelesen": False,        # ⚠ nur gelistet, keine Datei eingesehen
                "n": int(n or 0),
                "dateien": [{"name": d, "typ": t} for d, t in paare],
                "schwerpunkte": sorted(prio or []),
            }
            text = json.dumps(satz, ensure_ascii=False)
            ziel = ZIEL / f"{sicher}.json"
            if ziel.exists() and ziel.read_text(encoding="utf-8") == text:
                gleich += 1
            else:
                ziel.write_text(text, encoding="utf-8")
                geschrieben += 1
            vorher.discard(f"{sicher}.json")
            index[sicher] = {"n": satz["n"], "quelle": quelle,
                             "schwerpunkte": satz["schwerpunkte"]}

    for tot in vorher:
        (ZIEL / tot).unlink(missing_ok=True)

    INDEX.write_text(json.dumps(index, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(f"  {len(index):,} Dateilisten → {geschrieben:,} geschrieben, {gleich:,} unveraendert, "
          f"{len(vorher):,} entfernt")
    print(f"  Index: {INDEX.relative_to(ROOT)} ({INDEX.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
