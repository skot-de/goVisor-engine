"""AT: atverg-Notices markieren, die dieselbe Vergabe wie eine TED-AT-Notice sind.

**Warum es diesen Filter braucht, obwohl schon einer da war.** `gold.build_at_gold` schloss
atverg-Notices aus, die als oberschwellig geflaggt sind (`atverg/schwelle='OSB'`), mit der
Begründung, TED und atverg seien danach disjunkt. Das ist gemessen falsch: von 7.870
atverg-Notices, die 2025 nachweislich eine TED-Entsprechung haben, tragen nur 42,8 % das
OSB-Flag. **53,8 % tragen gar keinen Schwellenwert** (81.626 der 236.118 atverg-Notices haben
kein `atverg/schwelle`-Attribut), 3,4 % sind sogar als unterschwellig geflaggt. Damit
überleben **57,2 %** der echten Dubletten den Flag-Filter und landen doppelt in der Liste.

**Wer gewinnt.** Die TED-Zeile — sie trägt die Entscheidungsstruktur: Ø 1,62 Lose gegen 0
bei atverg, längere Beschreibung (235 gegen 181 Zeichen), bessere Fristabdeckung (33,7 %
gegen 20,8 %). Man bietet auf ein Los, nicht auf eine Bekanntmachung.

**Was trotzdem mitgeht: der Wert.** atverg führt bei `estimated_value` 69,8 % gegen 11,0 %
bei TED-AT. Ein reines Verwerfen würde also die bessere Wertabdeckung wegwerfen — und der
Wert trägt das Gebührenband. Deshalb schreibt dieser Filter den atverg-Schätzwert mit in
die Tabelle; `build_at_gold` setzt ihn ein, wo die TED-Zeile keinen hat.

**Wie gematcht wird.** Identisch zu `scripts/measure_at_overlap.py` — die Regeln werden von
dort importiert, damit Messung und Filter nicht auseinanderlaufen können. Kurzfassung:
Wortmengen-Enthaltung ≥80 % gegen die kleinere Menge (fängt ÖBBs „(ProVia-ID …)"-Präfix und
atvergs „- Los 2"-Suffix), kurze Titel nur bei voller Enthaltung, Zeitfenster ±90 Tage aus
der gemessenen Abstandsverteilung (Median 2 Tage, 97,6 % binnen 90).

**Ausfallrichtung.** Ist TED-AT unvollständig, werden zu WENIGE atverg-Notices als Dublette
erkannt — das Ergebnis ist sichtbares Rauschen in der Liste, kein stiller Datenverlust. Der
umgekehrte Fehler wäre schlimmer, deshalb ist das die gewollte Richtung. Ein Frische-Check
warnt trotzdem, statt es zu verschweigen.

Ergebnis: ``data/gold/AT/atverg_dedup.parquet``.
Aufruf:  python scripts/dedupe_at_sources.py [--von 2019] [--bis 2026]
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Die Matching-Regeln kommen aus der Messung — EINE Quelle, sonst driften Zahl und Filter.
_spec = importlib.util.spec_from_file_location("_at_overlap", ROOT / "scripts" / "measure_at_overlap.py")
mo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mo)

OUT = ROOT / "data" / "gold" / "AT" / "atverg_dedup.parquet"
MAX_ALTER_TAGE = 45      # ab hier gilt TED-AT als zu alt für ein verlässliches Urteil


def ted_frische(con) -> tuple[int, dt.date | None]:
    r = con.execute(f"""SELECT max(publication_date) FROM {mo.N}
        WHERE schema_gen IN {mo.TED_GEN}""").fetchone()
    if not r or not r[0]:
        return 10**6, None
    return (dt.date.today() - r[0]).days, r[0]


def main(von: int, bis: int) -> int:
    con = duckdb.connect()
    alter, stand = ted_frische(con)
    if alter > MAX_ALTER_TAGE:
        print(f"⚠ TED-AT ist {alter} Tage alt (Stand {stand}). Der Abgleich läuft trotzdem, "
              f"erkennt aber zu wenige Dubletten — die Liste rauscht, statt Daten zu verlieren.")

    zeilen: list[tuple] = []
    for jahr in range(von, bis + 1):
        ted = con.execute(f"""SELECT notice_id, title, publication_date FROM {mo.N}
            WHERE schema_gen IN {mo.TED_GEN} AND year(publication_date) = {jahr}
              AND title IS NOT NULL""").fetchall()
        if not ted:
            continue
        av = con.execute(f"""SELECT notice_id, title, publication_date, estimated_value, value_currency
            FROM {mo.N} WHERE schema_gen = 'atverg' AND title IS NOT NULL
              AND publication_date BETWEEN DATE '{jahr-1}-09-01' AND DATE '{jahr+1}-04-30'
            """).fetchall()
        inv, av_w = mo._index([(t, d) for _i, t, d, _v, _c in av])

        paare: list[tuple] = []
        for tid, t, d in ted:
            tw = mo.worte(t)
            kand = mo._kandidaten(tw, inv) if d else None
            if not kand:
                continue
            for i in kand:
                m = min(len(tw), len(av_w[i]))
                if not m:
                    continue
                e = len(tw & av_w[i]) / m
                if m <= mo.KURZ and e < 1.0:
                    continue
                if e < mo.MIN_ENTHALTUNG or not av[i][2]:
                    continue
                tage = abs((av[i][2] - d).days)
                if tage > mo.FENSTER_TAGE:
                    continue
                paare.append((e, -tage, tid, i))

        # Gierige 1:1-Zuordnung: sicherster Treffer zuerst, jede Zeile nur einmal vergeben.
        #
        # Beide naiven Varianten sind gemessen falsch. „Je TED-Notice die beste atverg-Zeile"
        # ließ Geschwister stehen: bei „22., Polgarstraße 25" (3 TED-Lose, 2 atverg-Zeilen)
        # wählten alle drei dieselbe, die zweite blieb einen Tag neben ihrem Zwilling in der
        # Liste. „Alle Kandidaten markieren" kippte ins Gegenteil und hätte echte
        # Geschwisterlose gelöscht — „Winterdienst Innsbruck Paket 8" und „Paket 3" sind nach
        # der Tokenisierung identisch, weil einstellige Zahlen herausfallen; die Markierung
        # sprang von 62.506 auf 97.010 atverg-Notices.
        #
        # 1:1 trifft beides: gibt es drei TED-Pakete und drei atverg-Pakete, fliegen alle drei
        # atverg-Zeilen; gibt es nur ein TED-Paket, fliegt genau eine.
        paare.sort(reverse=True)
        ted_vergeben, av_vergeben = set(), set()
        treffer = 0
        for e, negtage, tid, i in paare:
            if tid in ted_vergeben or i in av_vergeben:
                continue
            ted_vergeben.add(tid)
            av_vergeben.add(i)
            zeilen.append((av[i][0], tid, round(e, 3), -negtage, av[i][3], av[i][4], jahr))
            treffer += 1
        print(f"  {jahr}: {len(ted):,} TED-AT → {treffer:,} Dubletten markiert")

    if not zeilen:
        print("Keine Dubletten gefunden — nichts geschrieben.")
        return 1

    # Eine atverg-Notice kann mehrfach getroffen werden (mehrere TED-Lose auf dieselbe
    # Bekanntmachung). Für den Ausschluss zählt die Notice einmal; behalten wird die
    # sicherste Zuordnung.
    OUT.parent.mkdir(parents=True, exist_ok=True)
    con.execute("CREATE TEMP TABLE d(av_id VARCHAR, ted_id VARCHAR, enthaltung DOUBLE, "
                "tage_abstand INTEGER, av_estimated_value DOUBLE, av_currency VARCHAR, jahr INTEGER)")
    con.executemany("INSERT INTO d VALUES (?,?,?,?,?,?,?)", zeilen)
    con.execute(f"""COPY (
        SELECT * FROM (
            SELECT *, row_number() OVER (PARTITION BY av_id
                       ORDER BY enthaltung DESC, tage_abstand ASC) rn FROM d)
        WHERE rn = 1
    ) TO '{OUT.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)""")

    n, mit_wert = con.execute(f"""SELECT count(*), count(av_estimated_value)
        FROM read_parquet('{OUT.as_posix()}')""").fetchone()
    print(f"\n{n:,} atverg-Notices als Dublette markiert "
          f"({mit_wert:,} davon mit Schätzwert, der an TED weitergereicht wird)")
    print(f"→ {OUT}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--von", type=int, default=2019,
                    help="ab diesem Jahr (2019 = ab da liefert atverg nennenswert)")
    ap.add_argument("--bis", type=int, default=dt.date.today().year)
    a = ap.parse_args()
    sys.exit(main(a.von, a.bis))
