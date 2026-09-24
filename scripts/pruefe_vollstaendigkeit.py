#!/usr/bin/env python3
"""Traegt JEDER holbare Lead einen Zustand? — die Rechnung vom Lead aus.

**Warum es sie gibt.** Sven am 2026-09-24: „bei jeder neuen ausschreibung wird angeklopft
und nach dem dokument geschaut? wenn ja, dann sollte es auch fuer alle zustaende tags
geben, sonst machts ja kein sinn."

Die Tags gibt es (`docfetch_queue` fuehrt DAUERHAFT, BLOCKIERT, WARTET, KEIN_FEHLSCHLAG),
und `rueckstau.py --lage` uebersetzt sie in Klassen. Beide gehen aber vom ABRUFER aus: sie
zaehlen, was ein Abrufer noch vor sich hat und warum er das Uebrige stehen laesst. Ein Tag
entsteht beim Anklopfen und lebt im Manifest — wer nie angeklopft wurde, steht in keinem
Manifest und hat deshalb keinen Tag. Nicht „unbekannt", sondern gar nicht vorhanden.

Gemessen am 2026-09-24, DE, holbare Leads (Open House abgezogen): von 10.446 trugen 2.339
aus genau diesem Grund keinen Zustand — 22 %, und in keiner Zahl des Hauses sichtbar. Die
groessten Posten waren `www.dtvp.de` (1.455, Anmeldewand), `www.deutsche-evergabe.de` (421)
und `vergabe24` (262 ueber zwei Hosts).

Diese Sonde dreht die Richtung um: sie geht von den LEADS aus und sortiert jeden in genau
eine Klasse. Die Zusage, die sie prueft, ist eine einzige — **die Summe der Klassen ist die
Gesamtzahl der holbaren Leads**. Geht sie nicht auf, faellt etwas stumm heraus, und genau
das ist der Fehler, den sie finden soll.

⚠ **`is_rib` steht NICHT in der Abrufer-Registry** (`rueckstau.abrufer()` kennt dreizehn
Module, `docfetch_rib` ist keins davon — es wird aus `docfetch._waehle_connector` heraus
gerufen und schreibt ins cosinex-Manifest). Wer die Registry fuer vollstaendig haelt,
zaehlt die 652 `meinauftrag.rib.de`-Leads als unabgedeckt. Bei der ersten Messung am
2026-09-24 ist genau das passiert: 4.363 statt 3.711. Die Praedikatliste hier ergaenzt
`rib` deshalb ausdruecklich.

⚠ **OPEN HOUSE GEHOERT NICHT IN DIE GRUNDMENGE.** Dort tritt man einem Rabattvertrag BEI,
statt zu bieten; die Unterlagen liegen systematisch hinter der Teilnahme, und die Abrufer
schliessen sie in ihrer eigenen Auswahl aus (Begruendung und Messung in
`rueckstau.rueckstand`). Zaehlt man sie mit, sieht die Luecke doppelt so gross aus, wie sie
ist: in DE waren es 2.067 Leads, bei cosinex allein 67 % seines scheinbaren Rueckstaus. Bei
der ersten Messung am 2026-09-24 hat das zu einem Fehlbefund gefuehrt („cosinex meldet 0,
obwohl 1.281 warten") — nach Abzug blieb bei cosinex nichts uebrig, die 0 war richtig.

⚠ **DIE SONDE SCHREIT NICHT UEBER DIE BEKANNTE LUECKE.** Ein Waechter, der jede Nacht
dieselbe Zahl meldet, wird abgeschaltet (die Lehre steht in `pruefe_abdeckung.py`). Die
heute bekannten Portale ohne Abrufer stehen deshalb in `curated/portale_ohne_abrufer.csv`
und sind still. Befund ist, was NEU dazukommt — also genau der Fall, der bis zum 2026-09-15
vier Wochen lang unbemerkt blieb, als LU, AT und CH aus der Abruferwahl fielen.

⚠ **AT UND CH RECHNEN MIT, LOESEN ABER KEINEN BEFUND AUS.** Sven am 2026-09-24: „bei AT und
CH brauchen wir keine dokumente anfragen, weil die portale das nicht hergeben." Beide haben
heute keine `doc_text.parquet`, ihre Leads stuenden also vollstaendig in der Luecke und
wuerden jede Nacht schreien. Sie werden trotzdem GEZEIGT, weil eine Zahl, die man nicht
sieht, niemandem auffaellt, wenn sich die Lage aendert (fuer CH ist es eine
Interessensbekundung, keine technische Wand — 1.564 Leads).

Aufruf:  python3 scripts/pruefe_vollstaendigkeit.py [--offen] [--land DE]
Exit 0 = still, 1 = Befund.
"""
from __future__ import annotations

import argparse
import csv
import glob
import importlib
import pathlib
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
# ⚠ VOR dem `govisor`-Import: der Tageslauf laeuft unter launchd ohne PYTHONPATH.
sys.path.insert(0, str(ROOT))

from govisor.laender import AKTIV                                    # noqa: E402

# Laender, in denen wir Unterlagen ueberhaupt holen wollen. Alles andere rechnet mit und
# wird gezeigt, loest aber keinen Befund aus (s. Kopf).
MIT_DOKUMENTEN = ("DE", "LU")

BEKANNTE_LUECKE = ROOT / "curated" / "portale_ohne_abrufer.csv"

# Reihenfolge der Ausgabe. Sie ist der Weg eines Leads, nicht das Alphabet.
ORDNUNG = ["volltext", "geholt", "wartet", "kein_abrufer", "sperre", "dauerhaft"]

ERKLAERUNG = {
    "volltext":     "Text liegt vor                       fertig",
    "geholt":       "geholt, Text noch nicht ausgelesen   kommt von selbst",
    "wartet":       "Abrufer zustaendig, noch nicht dran  Durchsatz",
    "kein_abrufer": "kein Abrufer zustaendig              LUECKE",
    "sperre":       "Sperrfrist laeuft                    kommt von selbst",
    "dauerhaft":    "endgueltig, nichts mehr zu holen     erledigt",
}


def praedikate() -> list[tuple[str, object]]:
    """Kurzname → URL-Pruefer, fuer jeden Abrufer den es gibt.

    ⚠ `rib` wird ergaenzt, weil es kein eigener Abrufer ist (s. Kopf). Ohne diese Zeile
    zaehlen 652 Leads faelschlich als unabgedeckt.
    """
    from govisor.docfetch_rib import is_rib
    from scripts.rueckstau import abrufer

    raus: list[tuple[str, object]] = [("rib", is_rib)]
    for kurz, modul in abrufer().items():
        try:
            m = importlib.import_module(modul)
        except Exception:                                     # noqa: BLE001
            continue
        f = next((getattr(m, n) for n in dir(m)
                  if n.startswith(("ist_", "is_")) and callable(getattr(m, n))), None)
        if f is not None:
            raus.append((kurz, f))
    return raus


def _zustaende(con, land: str) -> dict[str, str]:
    """Kennung → Manifest-Status, ueber ALLE Manifeste des Landes zusammen.

    ⚠ Das Schluesselfeld ist nicht einheitlich: `docfetch` fuehrt `notice_id`, die uebrigen
    `lead_id` (`docfetch_queue.KENNUNG`). Hier wird gelesen, was da ist — eine feste Wahl
    waere bei der Haelfte der Manifeste die falsche.
    """
    raus: dict[str, str] = {}
    for p in sorted(glob.glob(f"{ROOT}/data/docs/{land}/_manifest*.parquet")):
        try:
            spalten = {c[0] for c in con.execute(
                f"describe select * from read_parquet('{p}')").fetchall()}
        except Exception:                                     # noqa: BLE001
            continue
        feld = "notice_id" if "notice_id" in spalten else "lead_id"
        if feld not in spalten or "status" not in spalten:
            continue
        for kenn, status in con.execute(
                f"select {feld}, status from read_parquet('{p}') "
                f"where {feld} is not null").fetchall():
            # Ein Lead kann in zwei Manifesten stehen (ein Portal, zwei Anlaeufe). Der
            # Erfolg gewinnt: er ist die juengere Wahrheit ueber denselben Vorgang.
            if kenn in raus and raus[kenn] in ("downloaded", "exists"):
                continue
            raus[kenn] = status
    return raus


def _klasse(status: str) -> str:
    """Manifest-Status → Klasse dieser Rechnung. Die Wahrheit ueber die Stati steht in
    `docfetch_queue`, nicht hier."""
    from govisor.docfetch_queue import BLOCKIERT, DAUERHAFT, KEIN_FEHLSCHLAG, normalisiere
    st = normalisiere(status)
    if st in KEIN_FEHLSCHLAG:
        return "geholt"
    if st in DAUERHAFT:
        return "dauerhaft"
    if st in BLOCKIERT:
        return "blockiert:" + BLOCKIERT[st]
    return "sperre"


def bekannte_luecke() -> set[str]:
    """Portale, fuer die wir heute bewusst keinen Abrufer haben."""
    if not BEKANNTE_LUECKE.exists():
        return set()
    with BEKANNTE_LUECKE.open(encoding="utf-8") as f:
        return {z["host"].strip() for z in csv.DictReader(f) if z.get("host", "").strip()}


def rechne(land: str) -> tuple[dict[str, int], dict[str, int], int]:
    """(Klasse → Anzahl, Host ohne Abrufer → Anzahl, Grundmenge)."""
    import duckdb

    L = ROOT / "data" / "gold" / land / "lead_export.parquet"
    if not L.exists():
        return {}, {}, 0
    con = duckdb.connect()
    leads = con.execute(f"""
        select lead_id, documents_url from read_parquet('{L.as_posix()}')
        where phase='open' and documents_url is not null
          and deadline_date > current_date
          and coalesce(procedure_kind, '') <> 'open_house'""").fetchall()

    T = ROOT / "data" / "docs" / land / "doc_text.parquet"
    text: set[str] = set()
    if T.exists():
        text = {r[0] for r in con.execute(
            f"select distinct notice_id from read_parquet('{T.as_posix()}')").fetchall()}

    zustand = _zustaende(con, land)
    con.close()

    pruefer = praedikate()
    klassen: dict[str, int] = {}
    ohne: dict[str, int] = {}
    for lead_id, url in leads:
        if lead_id in text:
            k = "volltext"
        elif lead_id in zustand:
            k = _klasse(zustand[lead_id])
        elif any(_trifft(f, url) for _, f in pruefer):
            k = "wartet"
        else:
            k = "kein_abrufer"
            host = _host(url)
            ohne[host] = ohne.get(host, 0) + 1
        klassen[k] = klassen.get(k, 0) + 1
    return klassen, ohne, len(leads)


def _host(url: str) -> str:
    """URL → blanker Rechnername, klein, ohne Port und ohne Query.

    ⚠ NICHT `regexp('https?://([^/]+)')`. Die erste Fassung dieser Sonde hat das getan und
    sich damit selbst unbrauchbar gemacht: eine URL OHNE Pfad haengt ihren Query an den
    Rechnernamen, und `vergabeplattform.charite.de` erschien als **19 verschiedene
    Portale** — je eine pro `?tid=…`. Jede neue Sitzungskennung waere ein „neues Portal"
    und damit jede Nacht ein Befund gewesen. Genau der Waechter, der abgeschaltet wird.
    """
    try:
        return (urllib.parse.urlsplit(url or "").hostname or "?").lower()
    except ValueError:
        return "?"


def _trifft(f, url: str) -> bool:
    """Ein Praedikat, das an einer URL stolpert, ist ein „nein" — kein Absturz der Sonde."""
    try:
        return bool(f(url))
    except Exception:                                         # noqa: BLE001
        return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--land", help="nur dieses Land")
    ap.add_argument("--offen", action="store_true",
                    help="auch die Portale ohne Abrufer einzeln auflisten")
    a = ap.parse_args(argv)

    laender = [a.land] if a.land else list(AKTIV)
    bekannt = bekannte_luecke()
    befunde: list[str] = []

    for land in laender:
        klassen, ohne, grund = rechne(land)
        if not grund:
            continue
        zaehlt = land in MIT_DOKUMENTEN
        print(f"── {land}: {grund:,} holbare Leads"
              f"{'' if zaehlt else '   (rechnet mit, loest keinen Befund aus)'} ──")

        rest = dict(klassen)
        for k in ORDNUNG:
            if k in rest:
                n = rest.pop(k)
                print(f"   {n:>7,}  {ERKLAERUNG.get(k, k)}")
        # Alles, was BLOCKIERT mitbringt, in einem Block darunter — die Klassen kommen aus
        # `docfetch_queue`, nicht aus einer Liste hier, und duerfen deshalb wachsen.
        for k in sorted(rest):
            print(f"   {rest[k]:>7,}  {k}")

        summe = sum(klassen.values())
        if summe != grund:
            befunde.append(f"{land}: Summe der Klassen {summe:,} != {grund:,} holbare Leads "
                           f"— es faellt etwas stumm heraus")
        else:
            print(f"   {'':>7}  ✓ Summe geht auf ({summe:,})")

        neu = {h: n for h, n in ohne.items() if h not in bekannt}
        if a.offen and ohne:
            print("   Portale ohne Abrufer:")
            for h, n in sorted(ohne.items(), key=lambda x: -x[1]):
                print(f"      {'NEU ' if h in neu else '    '}{h:<44}{n:>6,}")
        if neu and zaehlt:
            oben = sorted(neu.items(), key=lambda x: -x[1])[:3]
            befunde.append(
                f"{land}: {len(neu)} Portal(e) ohne Abrufer sind NEU "
                f"({sum(neu.values()):,} Leads): "
                + ", ".join(f"{h} {n:,}" for h, n in oben)
                + (" …" if len(neu) > 3 else ""))
        print()

    if befunde:
        print("⚠ Befund:")
        for b in befunde:
            print(f"   {b}")
        print(f"\n   Bekannte Luecken stehen in {BEKANNTE_LUECKE.relative_to(ROOT)}. "
              f"Ein neues Portal gehoert dort hinein (mit Grund) oder braucht einen Abrufer.")
        return 1
    print("✓ Jeder holbare Lead traegt einen Zustand.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
