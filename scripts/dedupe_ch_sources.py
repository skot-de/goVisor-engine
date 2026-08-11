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

**Wer bei einer Dublette gewinnt: TED — nicht simap.** Das ist die Umkehrung dessen, was
oben nahelag („TED ergänzt simap"), und sie ist gemessen: für 2025–2026 trägt TED-CHE
Ø 1,19 Lose gegen **0** bei simap, längere Beschreibungen (505 gegen 447 Zeichen) und
deutlich mehr echte Fristen (53,2 % gegen 30,5 %). Wert führt keine der beiden (0,2 % / 0 %).
Man bietet auf ein Los, nicht auf eine Bekanntmachung — also bleibt die TED-Zeile stehen und
die simap-Zwillingszeile fällt. simap-Notices **ohne** TED-Partner bleiben davon unberührt;
sie sind der eigentliche Beitrag der nationalen Plattform.

Ergebnis: `data/gold/CH/ted_dedup.parquet` mit je TED-Notice der Entscheidung
(`dublette` / `neu`) und, bei Dublette, der simap-notice_id. `simap.build_ch_gold` schließt
die dort genannten **simap**-IDs aus.

Aufruf:  python scripts/dedupe_ch_sources.py [--von 2026-01] [--bis 2026-08]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import verify  # noqa: E402  (Pfad muss zuerst stehen)

# Exit-Codes, damit der Tageslauf „übersprungen" von „kaputt" unterscheiden kann.
EXIT_OK, EXIT_FEHLER, EXIT_UEBERSPRUNGEN = 0, 1, 2

MIN_VOLLSTAENDIG = 0.90   # Anteil der laut TED-API erwarteten Notices je Monat

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


def backfill_laeuft() -> bool:
    """Läuft gerade ein Historien-Nachlauf? Dann ist jeder Abgleich eine Momentaufnahme."""
    try:
        r = subprocess.run(["pgrep", "-f", "backfill_ted_ch"], capture_output=True, text=True)
        return r.returncode == 0 and bool(r.stdout.strip())
    except OSError:
        return False


def monate(von: str, bis: str) -> list[tuple[int, int]]:
    (vj, vm), (bj, bm) = (int(von[:4]), int(von[5:7])), (int(bis[:4]), int(bis[5:7]))
    heute = date.today()
    aus = []
    j, m = vj, vm
    while (j, m) < (bj, bm):
        # Der laufende Monat ist naturgemäß unvollständig — er darf den Test nicht sperren.
        if (j, m) < (heute.year, heute.month):
            aus.append((j, m))
        j, m = (j + 1, 1) if m == 12 else (j, m + 1)
    return aus


def vollstaendig(von: str, bis: str) -> tuple[bool, str]:
    """Ist die TED-CHE-Seite im Zeitraum vollständig genug für einen Abgleich?

    Ein Abgleich auf halbem Bestand ist schlimmer als keiner: er stuft Notices als „neu"
    ein, die schlicht noch nicht geholt wurden — und wer das Ergebnis benutzt, nimmt
    Dubletten auf. Gemessen wird gegen die TED-API, denselben Maßstab, den auch der
    Backfill und `verify` verwenden.
    """
    con = duckdb.connect()
    luecken = []
    for j, m in monate(von, bis):
        soll = verify.api_count(j, m, country="CHE")
        if soll is None or soll == 0:
            continue                      # API nicht erreichbar → kein Urteil, kein Blocker
        try:
            ist = con.execute(f"""
                SELECT count(*) FROM read_parquet('{SILVER_CH}', hive_partitioning=1)
                WHERE schema_gen <> 'simap'
                  AND publication_date >= DATE '{j:04d}-{m:02d}-01'
                  AND publication_date <  DATE '{j:04d}-{m:02d}-01' + INTERVAL 1 MONTH
            """).fetchone()[0]
        except duckdb.IOException:
            ist = 0
        if ist < soll * MIN_VOLLSTAENDIG:
            luecken.append(f"{j}-{m:02d} ({ist}/{soll})")
        time.sleep(0.2)                   # höflich zur API
    con.close()
    if luecken:
        return False, f"{len(luecken)} unvollständige Monate: " + ", ".join(luecken[:6])
    return True, "vollständig"


def main(von: str, bis: str, ohne_pruefung: bool = False) -> int:
    if not ohne_pruefung:
        if backfill_laeuft():
            print("Backfill läuft gerade — Abgleich übersprungen (wäre eine Momentaufnahme).")
            return EXIT_UEBERSPRUNGEN
        ok, grund = vollstaendig(von, bis)
        if not ok:
            print(f"TED-CHE noch unvollständig — Abgleich übersprungen.\n  {grund}")
            print("  Ein Abgleich auf halbem Bestand meldet Dubletten als 'neu'.")
            return EXIT_UEBERSPRUNGEN

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
        return EXIT_UEBERSPRUNGEN
    if not ted:
        print("Keine TED-CHE-Notices im Zeitraum — nichts abzugleichen.")
        return EXIT_UEBERSPRUNGEN

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

    # Erst ALLE zulässigen Paare sammeln, dann gierig 1:1 zuordnen.
    #
    # Die erste Fassung nahm je TED-Notice die beste simap-Zeile — unabhängig davon, ob eine
    # andere TED-Notice dieselbe Zeile schon beansprucht hatte. Gemessen am Juni-Stand
    # beanspruchten 49 simap-Zeilen mehrere TED-Notices; 92 von 873 Dubletten-Urteilen
    # (10,5 %) hingen daran. Das ist die gefährliche Richtung: eine zu Unrecht als Dublette
    # markierte TED-Notice verschwindet aus der Liste, obwohl sie eine eigene Vergabe ist.
    # Typischer Auslöser sind Geschwisterlose, deren Titel sich nur in einer ein- oder
    # zweistelligen Zahl unterscheiden — die fällt aus der Tokenisierung heraus.
    paare = []
    for idx, (tid, titel, datum, cpv) in enumerate(ted):
        tw = worte(ted_titel(titel))
        if len(tw) < MIN_WOERTER or not datum:
            continue
        # Kandidaten: alles, was mindestens ein Wort teilt — dann echte Deckung prüfen.
        kand: dict[int, int] = {}
        for w in tw:
            for i in inv.get(w, ()):
                kand[i] = kand.get(i, 0) + 1
        for i, gemeinsam in kand.items():
            deckung = gemeinsam / len(tw)
            if deckung < MIN_DECKUNG:
                continue
            sd = simap[i][2]
            if sd and abs((sd - datum).days) <= FENSTER_TAGE:
                paare.append((deckung, -abs((sd - datum).days), idx, i))

    paare.sort(reverse=True)          # sicherster Treffer zuerst
    zuordnung: dict[int, str] = {}
    ted_vergeben, simap_vergeben = set(), set()
    for deckung, _negtage, idx, i in paare:
        if idx in ted_vergeben or i in simap_vergeben:
            continue
        ted_vergeben.add(idx)
        simap_vergeben.add(i)
        zuordnung[idx] = simap[i][0]

    rows = []
    for idx, (tid, titel, datum, cpv) in enumerate(ted):
        passend = zuordnung.get(idx)
        rows.append((tid, passend, "dublette" if passend else "neu",
                     " ".join(sorted(worte(ted_titel(titel))))[:200], datum, cpv))
    treffer = len(zuordnung)

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
    return EXIT_OK


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--von", default="2024-07", help="ab YYYY-MM (Default: simap-Beginn)")
    ap.add_argument("--bis", default="2026-09", help="bis YYYY-MM (exklusiv)")
    ap.add_argument("--ohne-pruefung", dest="ohne_pruefung", action="store_true",
                    help="Vollständigkeitsprüfung überspringen (nur für Tests)")
    a = ap.parse_args()
    sys.exit(main(a.von, a.bis, a.ohne_pruefung))
