#!/usr/bin/env python3
"""Q1b richtig: Inhalts-Ähnlichkeit & Boilerplate-Anteil je Dokumenttyp.

Nicht die ersten Zeichen (= individuelles Deckblatt), sondern der GANZE Text. Zwei Maße je
Dokumenttyp:
  · **Boilerplate-Anteil**: Anteil der 8-Wort-Passagen eines Dokuments, die in ≥30 % der
    Vorgänge desselben Typs vorkommen → „wie viel einer typischen LB wiederholt sich?"
  · **Median Jaccard** (Stichprobe paarweise) → grobe Gesamt-Ähnlichkeit.

Die Doktyp-Klassifikation kommt aus ``govisor.doctypes`` — dieses Skript trug bis
2026-08-21 eine eigene, eingefrorene Kopie der Regeln. Sie kannte weder Oesterreich noch
die VHB-Nummern und zaehlte „Preisermittlung bei Zuschlagskalkulation" als
Zuschlagskriterium. Wer hier wieder Regeln einsetzt, misst an einem anderen Massstab als
der Betrieb.

Liest data/docs/DE/doc_text.parquet (aus `index-docs`). Schreibt data/docs/study/q1b_aehnlichkeit.csv
+ druckt eine Tabelle. Aufruf: python3 scripts/doc_similarity.py
"""
import csv
import glob
import random
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
import sys; sys.path.insert(0, str(ROOT))
from govisor import doctypes  # noqa: E402
SRC = ROOT / "data" / "docs" / "DE" / "doc_text.parquet"
OUTCSV = ROOT / "data" / "docs" / "study" / "q1b_aehnlichkeit.csv"
K = 8            # Shingle-Länge (Wörter)
DF_BOILER = 0.30  # ab welchem Dokument-Frequenz-Anteil eine Passage als Boilerplate gilt
MAXWORDS = 20000  # Deckel je (Vorgang,Typ) — bändigt Riesen-LVs
SAMPLE = 40       # Vorgänge je Typ für die paarweise Jaccard-Messung


def classify(name: str) -> str:
    return doctypes.classify(name)


def shingles(text: str) -> set[int]:
    t = re.sub(r"\d+", " ", text.lower())
    words = re.findall(r"[a-zäöüß]+", t)[:MAXWORDS]
    return {hash(" ".join(words[i:i + K])) for i in range(len(words) - K + 1)}


def main() -> int:
    if not SRC.exists():
        print(f"FEHLT: {SRC} — erst `index-docs` laufen lassen."); return 1
    con = duckdb.connect()
    rows = con.execute(
        f"""SELECT notice_id, file, text FROM read_parquet('{SRC.as_posix()}')
            WHERE status='ok' AND text IS NOT NULL AND length(text) > 200"""
    ).fetchall()

    # Text je (Vorgang, Doctype) zusammenfassen → Shingle-Set
    perdoc: dict[tuple, list[str]] = defaultdict(list)
    for nid, file, text in rows:
        perdoc[(nid, classify(file))].append(text)
    shmap: dict[str, dict[str, set]] = defaultdict(dict)   # doctype → notice → shingles
    for (nid, dt), texts in perdoc.items():
        s = shingles("\n".join(texts))
        if len(s) >= 30:
            shmap[dt][nid] = s

    random.seed(7)
    out = []
    for dt, byn in sorted(shmap.items(), key=lambda kv: -len(kv[1])):
        notices = list(byn)
        n = len(notices)
        if n < 3:
            continue
        # Boilerplate-Anteil: Dokument-Frequenz je Shingle über die Vorgänge dieses Typs
        df = Counter()
        for s in byn.values():
            df.update(s)
        thr = max(2, int(DF_BOILER * n))
        boiler = {sh for sh, c in df.items() if c >= thr}
        shares = []
        for s in byn.values():
            shares.append(len(s & boiler) / len(s))
        med_boiler = round(100 * st.median(shares))
        # Median paarweise Jaccard (Stichprobe)
        samp = notices if n <= SAMPLE else random.sample(notices, SAMPLE)
        pairs = [(i, j) for i in range(len(samp)) for j in range(i + 1, len(samp))]
        random.shuffle(pairs); pairs = pairs[:400]
        js = []
        for i, j in pairs:
            a, b = byn[samp[i]], byn[samp[j]]
            u = len(a | b)
            js.append(len(a & b) / u if u else 0)
        med_j = round(st.median(js), 2) if js else 0
        verdict = ("hohe Boilerplate — Standardformular trägt" if med_boiler >= 55 else
                   "teils geteilt — Segment/Modul-Ebene" if med_boiler >= 25 else
                   "überwiegend individuell")
        out.append([dt, n, med_boiler, med_j, verdict])

    OUTCSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTCSV, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["doctype", "n_vorgaenge", "boilerplate_anteil_%", "median_jaccard", "urteil"]); w.writerows(out)

    print(f"Q1b — Inhalts-Ähnlichkeit je Dokumenttyp (Volltext, {K}-Wort-Shingles)")
    print(f"{'Doctype':22}{'n':>5}{'Boilerpl.%':>12}{'Jaccard':>9}  Urteil")
    for r in out:
        print(f"{r[0]:22}{r[1]:>5}{r[2]:>11}%{r[3]:>9}  {r[4]}")
    print(f"\n→ {OUTCSV.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
