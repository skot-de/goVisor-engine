#!/usr/bin/env python3
"""Aenderungen an den Vergabeunterlagen → web/data/unterlagenstand.json.

DIE FRAGE. Die Vergabestelle stellt eine neue Fassung der Unterlagen ein. Wer auf der alten
kalkuliert hat, rechnet falsch — und erfaehrt es nicht, weil das Portal nur die neueste zeigt.

    Version 3 der Unterlagen. Seit Version 2 geaendert: Leistungsverzeichnis,
    Anlage 201 Eignungskriterien.

⚠ SIE IST NICHT DIE „ANFORDERUNGS-DRIFT" AUS DER UEBERGABE, und der Eintrag dort bleibt offen.
Das Papier meint „dieselbe Stelle, zwei Runden: verschaerft?" — den Vergleich einer Vergabe mit
der VORIGEN VERGABE derselben Stelle. Der ist mit den heutigen Daten nicht rechenbar, und zwar
strukturell:

    contract_succession × doc_checklist  =  0 Paare
    Nachfolger mit Unterlagen: 0 · Vorgaenger mit Unterlagen: 0

Unterlagen gibt es nur waehrend laufender Angebotsfrist; ein Vorgaenger ist per Definition
abgeschlossen. Die beiden Bestaende sind disjunkt und werden es bleiben, solange wir Dokumente
nach dem Zuschlag nicht aufbewahren. Das Papier ahnt es („Historie beginnt mit dem Lauf 02.09.")
und meint damit einen Zeitverlauf UNSERER Laeufe — der faengt heute an und traegt in Wochen.

Was hier gebaut ist, ist die Drift INNERHALB des laufenden Verfahrens. Sie ist frueher da und
naeher an der Entscheidung: eine Aenderung zwei Runden zurueck ist Marktkunde, eine Aenderung
seit gestern kostet Geld.

⚠ DIE VERSION STECKT AUCH IM ZIP-NAMEN, und daran ist die erste Messung gescheitert. Der Pfad
lautet `Z42-2025-0209_Version 1.zip::Anlage 510-...`; wer nur das Verzeichnis `Version 1/`
normalisiert, haelt jede Datei der neuen Fassung fuer neu. Gemessen: „56 neu, 54 weg" in einem
Vorgang, von denen 47 byte-gleich waren. Normalisiert wird deshalb JEDES Vorkommen von
„Version N" im ganzen Pfad.

⚠ UND VERGLICHEN WIRD DER LETZTE SCHRITT, nicht Version 1 gegen die neueste. Wer die Unterlagen
gestern gezogen hat, will wissen, was seitdem passiert ist. Ueber alle Versionen summiert
entstuende eine Liste, in der das Wichtige untergeht (Median 3 Dateien je Schritt, max 37).

Gemessen 2026-09-02: 209 Vorgaenge mit mehreren Fassungen, 93 davon noch offen — und alle 93
haben im letzten Schritt eine Aenderung.

Aufruf: python3 scripts/export_unterlagenstand.py
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "data" / "unterlagenstand.json"

MAX_NENNEN = 5   # mehr Dateinamen liest niemand; die Gesamtzahl steht daneben

# ⚠ JEDES Vorkommen, nicht nur das Verzeichnis: „…_Version 1.zip::…/Version 1/datei.pdf".
VERSION = re.compile(r"[ _]?version[ _]?(\d{1,3})", re.I)


def _version(pfad: str) -> int | None:
    treffer = [int(m.group(1)) for m in VERSION.finditer(pfad)]
    return max(treffer) if treffer else None


def _ohne_version(pfad: str) -> str:
    return VERSION.sub("", pfad).replace("//", "/").strip("/")


def _kurz(pfad: str) -> str:
    """Dateiname ohne Verzeichnis. ⚠ Aus fremden Unterlagen — wer ihn rendert, escaped ihn."""
    return str(pfad or "").replace("\\", "/").split("/")[-1].split("::")[-1].strip()[:70]


def _laender() -> list[str]:
    docs = ROOT / "data" / "docs"
    return sorted(p.name for p in docs.iterdir()
                  if p.is_dir() and (p / "doc_text.parquet").exists()) if docs.exists() else []


def main() -> int:
    con = duckdb.connect()
    raus: dict[str, dict] = {}
    for land in _laender():
        T = (ROOT / "data" / "docs" / land / "doc_text.parquet").as_posix()
        je: dict[str, dict[int, dict[str, bytes]]] = collections.defaultdict(
            lambda: collections.defaultdict(dict))
        for nid, datei, text in con.execute(
                f"select notice_id, file, text from read_parquet('{T}') where status = 'ok'").fetchall():
            pfad = str(datei or "")
            ver = _version(pfad)
            if ver is None:
                continue
            je[str(nid)][ver][_ohne_version(pfad)] = hashlib.blake2b(
                str(text or "").encode("utf-8"), digest_size=8).digest()
        mehrere = 0
        for nid, fassungen in je.items():
            if len(fassungen) < 2:
                continue
            mehrere += 1
            stufen = sorted(fassungen)
            vor, letzt = fassungen[stufen[-2]], fassungen[stufen[-1]]
            # ⚠ „geaendert" ist der gefaehrliche Fall: gleicher Name, anderer Inhalt. Wer die
            # Datei schon hat, sieht keinen Anlass, sie noch einmal zu ziehen.
            geaendert = sorted({_kurz(k) for k in vor if k in letzt and vor[k] != letzt[k]})
            neu = sorted({_kurz(k) for k in letzt if k not in vor})
            weg = len({k for k in vor if k not in letzt})
            if not (geaendert or neu or weg):
                continue
            raus[nid] = {"version": stufen[-1], "vorige": stufen[-2], "nVersionen": len(stufen),
                         "geaendert": geaendert[:MAX_NENNEN], "nGeaendert": len(geaendert),
                         "neu": neu[:MAX_NENNEN], "nNeu": len(neu), "nWeg": weg}
        print(f"  {land}: {mehrere:,} Vorgaenge mit mehreren Fassungen · "
              f"{sum(1 for k in raus):,} mit Aenderung im letzten Schritt")

    if not raus:
        print("FEHLT: keine Fassungsangaben in den Pfaden.")
        return 1
    OUT.write_text(json.dumps(raus, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Unterlagenstand → {OUT.name} ({OUT.stat().st_size / 1024:.0f} kB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
