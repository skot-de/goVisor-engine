#!/usr/bin/env python3
"""Standardtext-Anteil je Vorgang → web/data/standardtext.json (Kennzahl 8).

DIE FRAGE. „1.152 Tsd. Zeichen" steht über dem Volltext, und der Leser weiss nicht, ob das
1.152 Tsd. Zeichen Arbeit sind. Wenn drei Viertel davon wortgleich in anderen Vergaben stehen,
ist es das nicht — dann steckt die Arbeit im letzten Viertel.

    Standardtext = ein Absatz ab 120 Zeichen, der WORTGLEICH in mindestens drei Vorgängen steht.

⚠ PRUEFSUMMEN JE DATEI TAUGEN DAFUER NICHT. `document_duplicates` gibt es laengst (4.902
Paare), aber ganze Dateien sind nur in 2,1 % der Faelle identisch: ein geaendertes Datum im
Kopf, und die Pruefsumme ist eine andere. Gemessen wird deshalb je ABSATZ.

⚠ DIE UEBERGABE NENNT MEDIAN 10 %, OBERES VIERTEL 27 % — und sagt selbst, dass das eine
Untergrenze ist. Sie mass in 600 Vorgaengen; je mehr Vorgaenge im Topf sind, desto mehr
Absaetze finden ihre drei Partner. Am vollen Bestand (9.690 Vorgaenge, 1,32 Mio. verschiedene
Absaetze, 4,2 Mrd. Zeichen):

    Median 29 % · oberes Viertel 51 % · p90 74 % · ueber die Haelfte Kopie: 26 %

Das ist rund das Dreifache der Papierwerte. Wer die Zahl gegen das Papier prueft, prueft gegen
eine Stichprobe, nicht gegen einen Fehler.

⚠ VERGLICHEN WIRD JE TEXTMENGE, NICHT JE REGELWERK — und das war nicht die erste Vermutung.
Das Regelwerk trennt sichtbar (UVgO 42 %, VOB 25 %), aber die TEXTMENGE trennt doppelt so
stark, und ihr Muster wiederholt sich INNERHALB jedes Regelwerks:

                   50–200 Tsd.   200–800 Tsd.   ueber 800 Tsd.
    VOB                  41 %           23 %            10 %
    VgV                  37 %           26 %             5 %
    UVgO                 46 %           36 %          zu duenn
    sonst                42 %           25 %            12 %
    ────────────────────────────────────────────────────────
    Spreizung: Textmenge 4,1×  ·  Regelwerk 1,8×

Der Grund ist inhaltlich: grosse Pakete tragen ein eigenes Leistungsverzeichnis und eigene
technische Anlagen, und die stehen nirgends sonst. Wer global vergleicht, nennt jede kleine
Vergabe „viel Kopie" und jede grosse „ungewoehnlich eigen".

⚠ UNTER 50 TSD. ZEICHEN IST DIE ZAHL RAUSCHEN. Dort landen 35 % der Vorgaenge bei genau 0 %
(darueber nur 3 %): zu wenige Absaetze, um ueberhaupt Partner finden zu koennen. Sie bekommen
keinen Wert statt eines schlechten.

⚠ UND SIE HAELT DIE DRIFTPRUEFUNG AUS, weil sie ein VERHAELTNIS ist. Ueber die Lesetiefe:
25 % → 34 % → 32 % → 36 % (1 bis 3 / 4 bis 7 / 8 bis 15 / ab 16 gelesene Dateien), nicht
monoton, Korrelation 0,13. Absolute Zaehlungen aus denselben Dokumenten tun das NICHT (s.
Kennzahl 4: 2 → 7 → 16 Formulare). Die Pruefung laeuft trotzdem bei jedem Lauf mit, statt das
Urteil von heute einzufrieren.

Aufruf: python3 scripts/export_standardtext.py    (rund 90 Sekunden fuer DE)
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
import statistics
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "data" / "standardtext.json"

MIND_ZEICHEN = 120   # kuerzere Absaetze sind Ueberschriften und Tabellenzellen
MIND_VORGAENGE = 3   # „Standard" heisst: nicht nur diese und eine weitere Vergabe
MIND_TEXT = 50_000   # darunter ist der Anteil Rauschen (35 % landen bei 0 %)
MIND_RAHMEN = 100    # weniger tragen keinen Median

# ⚠ Die Vergleichsgruppe ist die TEXTMENGE (s. Kopf): sie trennt 4,1-fach, das Regelwerk nur
# 1,8-fach, und ihr Muster gilt innerhalb jedes Regelwerks.
BAENDER: tuple[tuple[int, int, str], ...] = (
    (50_000, 200_000, "klein"), (200_000, 800_000, "mittel"), (800_000, 10**12, "gross"),
)
BLOCK = 300          # Vorgaenge je Abfrage — 4,2 Mrd. Zeichen passen nicht in einen Rutsch

_ABSATZ = re.compile(r"\n\s*\n|\r\n\s*\r\n")


def _band(zeichen: int) -> str | None:
    """Die Vergleichsgruppe. `None` = zu wenig Text, um ueberhaupt zu messen."""
    for unten, oben, name in BAENDER:
        if unten <= zeichen < oben:
            return name
    return None


def _laender() -> list[str]:
    """Aus dem Bestand, nicht aus einer Liste im Code."""
    docs = ROOT / "data" / "docs"
    return sorted(p.name for p in docs.iterdir()
                  if p.is_dir() and (p / "doc_text.parquet").exists()) if docs.exists() else []


def _anteile(con, T: str) -> dict[str, float]:
    """Ein Durchgang: Absaetze hashen, je Vorgang den Anteil wiederholter Absaetze."""
    ids = [r[0] for r in con.execute(f"select distinct notice_id from {T} where status='ok'").fetchall()]
    vorkommen: collections.Counter = collections.Counter()
    je: dict[str, dict[bytes, int]] = {}
    for i in range(0, len(ids), BLOCK):
        liste = ",".join("'" + str(x).replace("'", "''") + "'" for x in ids[i:i + BLOCK])
        eigen: dict[str, dict[bytes, int]] = collections.defaultdict(dict)
        for nid, txt in con.execute(
                f"select notice_id, text from {T} where status='ok' and notice_id in ({liste})").fetchall():
            for absatz in _ABSATZ.split(txt or ""):
                # ⚠ Leerraum vereinheitlichen. Derselbe Absatz aus PDF und DOCX unterscheidet
                # sich sonst in jedem Zeilenumbruch, und nichts findet je einen Partner.
                absatz = " ".join(absatz.split())
                if len(absatz) < MIND_ZEICHEN:
                    continue
                eigen[nid][hashlib.blake2b(absatz.encode("utf-8"), digest_size=8).digest()] = len(absatz)
        for nid, d in eigen.items():
            je[nid] = d
            # ⚠ Je Vorgang EINMAL zaehlen: ein Absatz, der in fuenf Dateien DESSELBEN Vorgangs
            # steht, ist kein Standardtext, sondern eine Wiederholung im Paket.
            for h in d:
                vorkommen[h] += 1
    raus = {}
    for nid, d in je.items():
        ganz = sum(d.values())
        if ganz:
            raus[str(nid)] = sum(ln for h, ln in d.items() if vorkommen[h] >= MIND_VORGAENGE) / ganz
    return raus


def main() -> int:
    con = duckdb.connect()
    leads: dict[str, int] = {}
    lage: dict[str, dict] = {}
    verworfen: dict[str, str] = {}
    for land in _laender():
        T = f"read_parquet('{(ROOT / 'data' / 'docs' / land / 'doc_text.parquet').as_posix()}')"
        A = ROOT / "data" / "gold" / land / "doc_analysis.parquet"
        anteil = _anteile(con, T)
        if not anteil:
            continue
        umfang = dict(con.execute(
            f"select notice_id, sum(n_chars) from {T} where status='ok' group by 1").fetchall())
        tiefe = dict(con.execute(
            f"select notice_id, n_parsed_files from read_parquet('{A.as_posix()}')").fetchall()) if A.exists() else {}
        gruppen: dict[str, list] = collections.defaultdict(list)
        for nid, v in anteil.items():
            b = _band(int(umfang.get(nid) or 0))
            if b:
                gruppen[b].append((v, tiefe.get(nid) or 0))
                # ⚠ Das Band wird HIER aufgeloest, nicht im Frontend. Der Renderer kennt die
                # Gesamtzeichenzahl nur als `lbChars` — und das ist die AUSGELIEFERTE Laenge,
                # nicht die gemessene. Wer dort neu einordnet, trifft ein anderes Band.
                leads[nid] = {"a": round(100 * v), "band": b}
        for r, werte in gruppen.items():
            if len(werte) < MIND_RAHMEN:
                verworfen[f"{land}:{r}"] = f"nur {len(werte)} Vorgaenge"
                continue
            # ⛔ HIER STAND EINE DRIFTPRUEFUNG. Sie verglich flach gelesene Vorgaenge
            #    (1-7 Dateien) mit tief gelesenen (>=8) und verwarf ein Band, wenn das
            #    VERHAELTNIS der Mediane 1,5 riss. Am 2026-09-18 ausgemessen und gestrichen
            #    (Sven entschied nach der Messung) — `scripts/miss_driftschwelle.py` fuehrt
            #    sie jederzeit wieder vor:
            #
            #      Band       n     flach   tief   Verhaeltnis   Δ Punkte   Zufall p95
            #      klein   5.207    43,9%  52,9%          1,20       +9,0         1,06
            #      mittel  7.171    27,1%  32,6%          1,20       +5,4         1,06
            #      gross   1.664     9,1%  14,7%          1,61       +5,6         1,27
            #
            #    Drei Gruende, jeder fuer sich ausreichend:
            #
            #    1. ALLE DREI Baender driften, alle drei klar ueber dem Zufall (die Spalte
            #       rechts ist die Drift aus 400 ZUFAELLIGEN Teilungen derselben Zahlen).
            #       Die Pruefung traf also nicht ein auffaelliges Band, sondern das mit der
            #       kleinsten Basis.
            #    2. In Prozentpunkten driftet `klein` am STAERKSTEN (+9,0) und blieb stehen;
            #       `gross` driftet am wenigsten (+5,6) und flog. Ein Verhaeltnis ist
            #       skalenabhaengig: bei 9 % bewegt ein Prozentpunkt es um 0,11, bei 44 %
            #       um 0,02.
            #    3. Die Drift ist vermutlich ECHT und erwuenscht: Vorgaenge mit vielen
            #       Dateien tragen mehr Formularwerk, und Formularwerk IST Standardtext.
            #       Dass die Kennzahl mit der Menge der Unterlagen zusammenhaengt, ist der
            #       Grund, warum es die Baender ueberhaupt gibt — ein zweiter Waechter, der
            #       dieselbe Eigenschaft bestraft, nimmt 1.675 gut dokumentierten Vorgaengen
            #       ihre Kennzahl weg.
            #
            # ⚠ `scripts/export_schwellen.py` hat eine EIGENE Driftpruefung mit denselben
            #    Konstantennamen. Sie bleibt: dort sind es Euro-Betraege, die Drift laeuft
            #    nach UNTEN, und gemessen wurde sie nie. Wer diese Begruendung dorthin
            #    uebertraegt, uebertraegt eine Messung, die es fuer jene Zahlen nicht gibt.
            alle = sorted(v for v, _ in werte)
            lage[f"{land}:{r}"] = {"n": len(alle), "median": round(100 * statistics.median(alle)),
                                   "hoch": round(100 * statistics.quantiles(alle, n=4)[2])}
        print(f"  {land}: {len(anteil):,} Vorgaenge gemessen · {len(leads):,} mit genug Text · "
              f"{sum(1 for k in lage if k.startswith(land))} Bänder tragen einen Vergleich")

    for schl, grund in verworfen.items():
        print(f"     verworfen  {schl}: {grund}")
    if not leads:
        print("FEHLT: kein Volltext — erst `doc_text` bauen lassen.")
        return 1
    # Vergleichswerte je Lead aufloesen, damit die Anzeige nur noch formatiert.
    fertig = {}
    # ⚠ DE-FESTER RUECKFALL, und er rettet mehr als er soll. `lage.get("DE:…")` steht
    #    VORNE, nicht als Notnagel: ein luxemburgischer Vorgang wird also gegen DEUTSCHE
    #    Werte verglichen, auch wenn Luxemburg eigene traegt. Heute faellt das nicht auf,
    #    weil nur DE Baender hat (AT und CH haben keinen Volltext, LU ist zu duenn) — der
    #    Tag, an dem es auffaellt, ist der Tag, an dem ein zweites Land genug Unterlagen
    #    hat, und dann sieht niemand, dass die Vergleichszahl aus dem falschen Land kommt.
    #
    #    Reparieren hiesse, das Land im Eintrag mitzufuehren (`leads[nid]` kennt es nicht,
    #    nur die Schleife darueber). Bewusst NICHT hier miterledigt, weil es eine eigene
    #    Entscheidung ist: Standardtext-Anteile sind laenderuebergreifend vermutlich
    #    vergleichbar, und ein duennes Eigenband waere schlechter als ein dickes fremdes.
    #    Gemessen 2026-09-18: 45 LU-Vorgaenge haengen daran.
    for land_nid, eintrag in leads.items():
        g = lage.get(f"DE:{eintrag['band']}") or next(
            (v for k, v in lage.items() if k.endswith(":" + eintrag["band"])), None)
        if g:
            fertig[land_nid] = {"a": eintrag["a"], "median": g["median"], "hoch": g["hoch"]}
    # ⚠ DAS VERWORFENE GEHOERT INS AUSLIEFERGUT, NICHT NUR INS LOG. Am 2026-09-17 fiel
    #   `DE:gross` aus der Driftpruefung (1,53×, tags darauf 1,62×). Folge: 1.329 Vorgaenge —
    #   ausgerechnet die mit den MEISTEN Unterlagen, ueber 800k Zeichen — verloren ihren
    #   Vergleichswert und tragen die Kennzahl seither gar nicht mehr. Sichtbar war das an
    #   genau einer Stelle: einer Zeile im Nachtlauf-Log, die niemand liest.
    #
    #   Der Test darunter wurde rot, meldete aber „die Textmengen-Bänder trennen nicht mehr"
    #   — richtig gemessen, falsch benannt. Die Baender trennen noch (44 % gegen 28 %); was
    #   fehlte, war das dritte. Ein Waechter, der die Wirkung sieht und die Ursache nicht
    #   nennt, kostet jedes Mal dieselbe halbe Stunde.
    ohne = len(leads) - len(fertig)
    # ⚠ ATOMAR SCHREIBEN. `write_text` auf eine Datei, die der laufende Server liest,
    #   liefert dem Leser mit etwas Pech halbes JSON — und `ladeMitGrund` macht daraus eine
    #   503, also eine Stoerungsmeldung fuer einen Vorgang, der voellig in Ordnung ist.
    #   Das Zeitfenster ist klein und der Fehler danach nicht mehr nachstellbar.
    _teil = OUT.with_suffix(".json.part")
    _teil.write_text(json.dumps({"leads": fertig, "baender": lage,
                                 "verworfen": verworfen, "ohne_vergleich": ohne},
                                ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    _teil.replace(OUT)
    print(f"Standardtext → {OUT.name} ({OUT.stat().st_size / 1024:.0f} kB)"
          + (f" · {ohne:,} Vorgaenge ohne Vergleichswert" if ohne else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
