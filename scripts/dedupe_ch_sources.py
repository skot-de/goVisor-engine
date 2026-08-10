"""CH: TED-Notices gegen simap.ch abgleichen — damit der Zugewinn ankommt, nicht die Dublette.

**Warum das nötig ist.** Gemessen am Testmonat Juni 2026: von 1.091 TED-CHE-Notices finden
sich **93,5 %** titelgleich in simap (bei ±1 Monat Fenster; enger gefasst 81,8 %, weiter
gefasst 93,7 % — die Sättigung zeigt, dass ±1 Monat das richtige Fenster ist). TED und simap
melden weitgehend dieselben Schweizer Vergaben; TED ist der WTO-GPA-Kanal, simap die
nationale Plattform.

Ohne Abgleich würde die Aufnahme von TED-CHE die Schweizer Lead-Liste fast verdoppeln, ohne
mehr Markt abzudecken. Mit Abgleich bleibt genau das übrig, was simap nicht hat — nach der
Juni-Messung rund 6 % zusätzliche Notices.

**Warum nicht über die ID.** simap vergibt UUIDs (`18700689-51a5-…`), TED Publikations-
nummern (`370795-2026`). Es gibt keinen gemeinsamen Schlüssel, also muss inhaltlich
gematcht werden.

**Wie gematcht wird.** Der TED-Titel ist eine übersetzte Kette „Land – CPV-Label –
Originaltitel"; nur der letzte Teil ist der echte Titel. Aus ihm wird eine Wortmenge gebildet
(klein, akzentfrei, ohne Füllwörter) und gegen simap gesucht: mindestens 60 % der TED-Wörter
müssen im simap-Titel vorkommen, innerhalb ±60 Tagen.

Beide Werte sind an echten Daten korrigiert, nicht geraten. Ein Zeichen-Präfix schlug fehl,
weil simap Projektnummern voranstellt und TED nicht. Das Datumsfenster von 31 Tagen ließ
12 Paare mit voller Wortdeckung durchrutschen (34–57 Tage auseinander, Median 40).

Ergebnis: `data/gold/CH/ted_dedup.parquet` mit je TED-Notice der Entscheidung
(`dublette` / `neu`) und, bei Dublette, der simap-notice_id. Das Gold für CH kann darauf
filtern, statt blind beide Quellen zu vereinigen.

Aufruf:  python scripts/dedupe_ch_sources.py [--von 2026-01] [--bis 2026-08]
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SILVER_CH = "data/silver/CH/notices/*/*.parquet"
OUT = ROOT / "data" / "gold" / "CH" / "ted_dedup.parquet"

# WORT-Mengen statt Zeichen-Präfix. Der Präfix-Ansatz ist an echten Daten gescheitert:
# er stufte 100 Notices als „neu" ein, von denen die Stichprobe ALLE in simap fand —
# simap stellt Projektnummern voran, TED nicht, und schon ist der Präfix verschoben
# („Louis-Bertrand - M…" gegen „…Louis-Bertrand…"). Wortmengen sind gegen Umstellungen,
# Präfixe und abweichende Interpunktion unempfindlich.
# 60 statt 31 Tage — aus den Daten korrigiert: 12 Notices mit ≥80 % Wortdeckung lagen
# 34–57 Tage auseinander (Median 40) und wären fälschlich als 'neu' durchgerutscht.
# TED meldet den WTO-GPA-Kanal mit spürbarem Versatz zur nationalen Veröffentlichung.
FENSTER_TAGE = 60
MIN_WOERTER = 3          # kürzere Titel tragen keine verlässliche Menge
MIN_DECKUNG = 0.6        # Anteil der TED-Wörter, die im simap-Titel vorkommen müssen

# Füllwörter, die in fast jedem Vergabetitel stehen und nichts unterscheiden.
STOPP = {"los", "lot", "lotto", "teil", "partie", "parte", "phase", "etappe", "und", "et",
         "e", "der", "die", "das", "le", "la", "les", "il", "lo", "di", "de", "du", "des",
         "von", "fur", "pour", "per", "mit", "avec", "con", "bkp", "ccc", "sia", "nr", "no"}


def worte(s: str | None) -> frozenset[str]:
    """Titel → bedeutungstragende Wortmenge (klein, akzentfrei, ohne Füllwörter)."""
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return frozenset(w for w in re.findall(r"[a-z0-9]{3,}", s) if w not in STOPP)


def ted_titel(roh: str | None) -> str:
    """„Schweiz – Lampen – LED-Kit-2026" → „LED-Kit-2026"."""
    if not roh:
        return ""
    return roh.split("–")[-1].strip()


def main(von: str, bis: str) -> int:
    con = duckdb.connect()
    ted_glob = "data/silver/CH/notices/*/*.parquet"   # TED-CHE landet im selben Silber
    try:
        ted = con.execute(f"""
            SELECT notice_id, title, publication_date, cpv_main
            FROM read_parquet('{ted_glob}', hive_partitioning=1)
            WHERE schema_gen IN ('eforms','legacy','text','ojs')
              AND publication_date >= DATE '{von}-01' AND publication_date < DATE '{bis}-01'
        """).fetchall()
    except duckdb.IOException:
        print("Kein CH-Silber vorhanden — erst TED-CHE ingesten.")
        return 0
    if not ted:
        print("Keine TED-CHE-Notices im Zeitraum — nichts abzugleichen.")
        return 0

    simap = con.execute(f"""
        SELECT notice_id, title, publication_date
        FROM read_parquet('{SILVER_CH}', hive_partitioning=1)
        WHERE schema_gen = 'simap'
    """).fetchall()

    # Invertierter Index Wort → simap-Einträge. Ohne ihn wäre der Abgleich ein
    # Kreuzprodukt (1.000 × 31.000); so werden nur Kandidaten mit gemeinsamem Wort geprüft.
    inv: dict[str, list[int]] = {}
    simap_worte: list[frozenset[str]] = []
    for i, (sid, titel, datum) in enumerate(simap):
        ws = worte(titel)
        simap_worte.append(ws)
        for w in ws:
            inv.setdefault(w, []).append(i)

    rows = []
    treffer = 0
    for tid, titel, datum, cpv in ted:
        tw = worte(ted_titel(titel))
        passend = None
        if len(tw) >= MIN_WOERTER and datum:
            # Kandidaten: alles, was mindestens ein Wort teilt — dann echte Deckung prüfen.
            kand: dict[int, int] = {}
            for w in tw:
                for i in inv.get(w, ()):
                    kand[i] = kand.get(i, 0) + 1
            beste = 0.0
            for i, gemeinsam in kand.items():
                deckung = gemeinsam / len(tw)
                if deckung < MIN_DECKUNG or deckung <= beste:
                    continue
                sid, _st, sd = simap[i][0], simap[i][1], simap[i][2]
                if sd and abs((sd - datum).days) <= FENSTER_TAGE:
                    beste, passend = deckung, sid
        if passend:
            treffer += 1
        rows.append((tid, passend, "dublette" if passend else "neu",
                     " ".join(sorted(tw))[:200], datum, cpv))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    con.execute("CREATE TEMP TABLE d(ted_id VARCHAR, simap_id VARCHAR, status VARCHAR, "
                "titel_key VARCHAR, publication_date DATE, cpv_main VARCHAR)")
    con.executemany("INSERT INTO d VALUES (?,?,?,?,?,?)", rows)
    con.execute(f"COPY d TO '{OUT}' (FORMAT PARQUET, COMPRESSION ZSTD)")

    quote = 100.0 * treffer / len(ted)
    print(f"TED-CHE {von}…{bis}: {len(ted):,} Notices")
    print(f"  simap-Bestand:      {len(simap):,}")
    print(f"  als Dublette erkannt: {treffer:,} ({quote:.1f} %)")
    print(f"  neu (nur bei TED):    {len(ted)-treffer:,} ({100-quote:.1f} %)")
    print(f"→ {OUT}")
    return len(ted)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--von", default="2024-07", help="ab YYYY-MM (Default: simap-Beginn)")
    ap.add_argument("--bis", default="2026-09", help="bis YYYY-MM (exklusiv)")
    a = ap.parse_args()
    main(a.von, a.bis)
