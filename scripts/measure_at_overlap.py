"""AT: Wie stark überschneiden sich TED-AT und OffeneVergaben.at?

**Warum das zählt.** Österreich hat wie die Schweiz zwei Kanäle: TED-AT (EU-Schwelle) und
OffeneVergaben.at (nationale Plattform, auch unterschwellig). Ob die Aufnahme von TED-AT
Markt hinzufügt oder nur Dubletten, entscheidet, ob die österreichische Lead-Liste
belastbar ist. Ergebnis der Messung: **93 % Überschneidung, rund 858 zusätzliche Notices
pro Jahr** — TED-AT ist keine zweite Vollquelle, aber auch nicht redundant.

**Warum kein Schlüssel-Join.** Gemessen: 0 von 236.118 atverg-Notices tragen einen
`ref_publication_number`. Es gibt keine gemeinsame ID, also muss inhaltlich gematcht werden.

**Drei Korrekturen, ohne die die Zahl falsch ist.** Alle drei sind an Stichproben
aufgefallen, nicht am Gefühl — die erste Fassung meldete 30 % Zugewinn statt 7 %:

  1. **Kein Titel-Splitting.** Bei CH ist der TED-Titel eine übersetzte Kette
     „Land – CPV-Label – Originaltitel". Bei AT nicht: nur 6,4 % der Titel enthalten den
     Trenner überhaupt. Österreich ist deutschsprachig, TED zeigt das Original.

  2. **Enthaltung statt symmetrischer Deckung.** ÖBB stellt seinen Titeln eine Vorgangs-ID
     voran („(ProVia-ID 129659) Erstbevorratungspaket DOSTO"), atverg nicht; umgekehrt
     hängt atverg „- Los 2" an. Symmetrische Deckung ließ beides durchfallen. Gemessen wird
     deshalb der Anteil der KLEINEREN Wortmenge, der in der größeren steckt.

  3. **Seed nur über indizierte Wörter.** Der Kandidatenraum wird über das seltenste Wort
     aufgespannt. Genau das war bei ÖBB die ProVia-Nummer — die auf der Gegenseite nie
     vorkommt, also null Kandidaten liefert und den Treffer als „neu" durchgehen ließ.
     Jetzt zählen nur Wörter, die im Index existieren, und drei davon statt einem.

**Warum ±90 Tage.** Nicht geraten, sondern aus der Abstandsverteilung von 8.788 sicheren
Paaren (volle Enthaltung, ≥4 Wörter beidseitig): Median 2 Tage, 82 % binnen einer Woche,
94 % binnen 60, **96 % binnen 90**. Danach flacht die Kurve ab — eine Verdopplung auf 180
Tage bringt noch 1 Punkt, und was dort auftaucht, sind eher gleichnamige Wiederholungs-
vergaben („Kopierpapier 2025") als echter Veröffentlichungsversatz.

**Was TED-AT exklusiv liefert.** Stichprobengeprüft: ÖBB-Sektorenvergaben über die eigene
Plattform, internationale Organisationen mit Wiener Sitz (ICMPD) und einzelne
Medizintechnik-Beschaffungen.

Aufruf:  python scripts/measure_at_overlap.py [--von 2022] [--bis 2025]
"""
from __future__ import annotations

import argparse
import re
import statistics
import sys
import unicodedata
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

N = "read_parquet('data/silver/AT/notices/*/*.parquet', hive_partitioning=1)"
TED_GEN = "('legacy','eforms','text','ojs')"

FENSTER_TAGE = 90        # aus der Abstandsverteilung, s. Docstring
MIN_ENTHALTUNG = 0.8
KURZ = 3                 # bis hierher nur VOLLE Enthaltung — „MRT-System" steckt sonst
                         # in jedem längeren Titel, der beide Wörter zufällig führt.
SEEDS = 3

STOPP = {"los", "lose", "teil", "phase", "etappe", "und", "der", "die", "das", "den", "dem",
         "von", "fur", "mit", "zur", "zum", "auf", "des", "fuer", "bzw", "sowie", "neu",
         "ausschreibung", "vergabe", "beschaffung", "provia"}


def worte(s: str | None) -> frozenset[str]:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return frozenset(w for w in re.findall(r"[a-z0-9]{3,}", s) if w not in STOPP)


def _index(rows):
    inv: dict[str, list[int]] = {}
    mengen = []
    for i, (t, _d) in enumerate(rows):
        w = worte(t)
        mengen.append(w)
        for x in w:
            inv.setdefault(x, []).append(i)
    return inv, mengen


def _kandidaten(tw, inv):
    da = [w for w in tw if w in inv]
    if not da:
        return None
    aus: set[int] = set()
    for w in sorted(da, key=lambda w: len(inv[w]))[:SEEDS]:
        aus.update(inv[w])
    return aus


def _laden(con, jahr):
    ted = con.execute(f"""SELECT title, publication_date FROM {N}
        WHERE schema_gen IN {TED_GEN} AND year(publication_date) = {jahr}
          AND title IS NOT NULL""").fetchall()
    av = con.execute(f"""SELECT title, publication_date FROM {N}
        WHERE schema_gen = 'atverg' AND title IS NOT NULL
          AND publication_date BETWEEN DATE '{jahr-1}-09-01' AND DATE '{jahr+1}-04-30'""").fetchall()
    return ted, av


def lagverteilung(con, jahr: int) -> None:
    """Abstand echter Paare — der Massstab, aus dem das Fenster kommt."""
    ted, av = _laden(con, jahr)
    inv, av_w = _index(av)
    abst = []
    for t, d in ted:
        tw = worte(t)
        if len(tw) < 4 or not d:
            continue
        kand = _kandidaten(tw, inv)
        if not kand:
            continue
        bester = None
        for i in kand:
            if len(av_w[i]) < 4 or len(tw & av_w[i]) / min(len(tw), len(av_w[i])) < 1.0:
                continue
            dd = abs((av[i][1] - d).days)
            bester = dd if bester is None else min(bester, dd)
        if bester is not None:
            abst.append(bester)
    if not abst:
        print("  keine sicheren Paare gefunden")
        return
    print(f"\nAbstandsverteilung sicherer Paare {jahr} (n={len(abst):,}, "
          f"Median {statistics.median(abst):.0f} T):")
    for f in (7, 31, 60, 90, 180, 365):
        n = sum(1 for a in abst if a <= f)
        marke = "  ← gewähltes Fenster" if f == FENSTER_TAGE else ""
        print(f"    ≤ {f:3} T : {100*n/len(abst):5.1f} %{marke}")


def main(von: int, bis: int, lag: bool) -> int:
    con = duckdb.connect()
    print(f"TED-AT gegen OffeneVergaben.at  ·  ±{FENSTER_TAGE} T, "
          f"Enthaltung ≥{MIN_ENTHALTUNG:.0%}\n")
    print(f"  {'Jahr':>6} {'TED-AT':>9} {'Dublette':>10} {'nur TED':>10} {'Anteil neu':>11}")
    ges_t = ges_n = 0
    for jahr in range(von, bis + 1):
        ted, av = _laden(con, jahr)
        if not ted:
            continue
        inv, av_w = _index(av)
        dub = 0
        for t, d in ted:
            tw = worte(t)
            kand = _kandidaten(tw, inv) if d else None
            if not kand:
                continue
            for i in kand:
                m = min(len(tw), len(av_w[i]))
                if not m:
                    continue
                e = len(tw & av_w[i]) / m
                if m <= KURZ and e < 1.0:
                    continue
                if e >= MIN_ENTHALTUNG and av[i][1] and abs((av[i][1] - d).days) <= FENSTER_TAGE:
                    dub += 1
                    break
        neu = len(ted) - dub
        ges_t, ges_n = ges_t + len(ted), ges_n + neu
        print(f"  {jahr:>6} {len(ted):>9,} {dub:>10,} {neu:>10,} {100*neu/len(ted):>10.1f} %")
    if ges_t:
        jahre = bis - von + 1
        print(f"\n  {'Summe':>6} {ges_t:>9,} {ges_t-ges_n:>10,} {ges_n:>10,} "
              f"{100*ges_n/ges_t:>10.1f} %")
        print(f"\n  → TED-AT bringt rund {ges_n//jahre:,} Notices pro Jahr, "
              f"die OffeneVergaben.at nicht hat.")
    if lag:
        lagverteilung(con, bis)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--von", type=int, default=2022)
    ap.add_argument("--bis", type=int, default=2025)
    ap.add_argument("--lag", action="store_true",
                    help="zusätzlich die Abstandsverteilung zeigen (belegt das Fenster)")
    a = ap.parse_args()
    sys.exit(main(a.von, a.bis, a.lag))
