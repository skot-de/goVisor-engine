#!/usr/bin/env python3
"""Fehlt uns ein ganzer Monat? — Silber gegen die TED-API, je Land.

**Der Vorfall, der das nötig macht.** Am 2026-09-07 fiel auf, dass Luxemburg für Juli
NULL Bekanntmachungen hatte und für August 16 statt der üblichen ~250. Der Grund war
harmlos und deshalb umso tückischer: die Monatspakete waren beim Onboarding einmal von
Hand geladen worden (Januar bis Juni), danach lief nur noch `fetch_ted_live.py` — und der
wurde für LU erst Ende August dazugeschaltet. Dazwischen lag ein Loch von zwei Monaten.

Gemerkt hat es niemand. Drei unabhängige Wächter liefen jede Nacht und schwiegen:

  · `pruefe_verdrahtung.py`  misst das ALTER von Dateien, nicht ihr Fehlen.
  · `pruefe_sondierung.py`   trennt sondiert von aufgenommen, zählt aber nichts.
  · `govisor verify`         prüft BRONZE — und seit der Umstellung auf den Live-Abruf
                             endet Bronze in JEDEM Land im Juni. Es meldet deshalb für
                             Juli bis heute „FEHLT", auch für Deutschland, wo nichts
                             fehlt. Ein Wächter, der immer schreit, wird abgeschaltet.

Diese Prüfung fragt deshalb das, was zählt: liegt in SILBER ungefähr so viel, wie TED für
diesen Monat kennt?

⚠ **Der laufende Monat wurde übersprungen — und genau dort war ein Loch.** Bis zum
2026-09-11 endete diese Prüfung beim letzten abgeschlossenen Monat, mit der Begründung
„der laufende füllt sich noch". Am 2026-09-09 holte `fetch_ted_live` für Deutschland
**0 von 676** Bekanntmachungen (der Abruf lief in einen Zeitablauf, weil der Rechner mitten
im Lauf schlief), und die Sonde meldete zwei Nächte lang `✓ alle geprueften Monate
vollstaendig` — sie schaute auf August. Deshalb zweite Stufe: der laufende Monat.

⚠ **ABER NUR ALS FENSTERSUMME, NICHT TAGEWEISE.** Die erste Fassung verglich Tag gegen Tag
und lag falsch: unser `publication_date` und die TED-Facette `publication-date` sind
**nicht dasselbe Feld**. Von acht Bekanntmachungen, die TED unter dem 2026-09-11 führt,
liegen alle acht bei uns — zwei unter dem 09.09., sechs unter dem 10.09. Die Sonde meldete
trotzdem „0 von 569". Über genug Tage mittelt sich der Versatz heraus, über einen nicht.
Die Karenz von 4 Tagen ist gemessen, nicht geschätzt (Zahlen in `laufender_monat`).

⚠ **100 % sind nicht zu erwarten, und 90 % sind kein Befund.** Die TED-Facette
`buyer-country` zählt mehr, als uns gehört: EU-Einrichtungen erscheinen unter der Facette
jedes Mitgliedstaats (`normalize.gehoert_zu_land` wirft sie beim Silberbau wieder raus —
für LU im August waren das 6 von 236). Dazu kommen Nachmeldungen. Gemessen am 2026-09-07
liegt der Normalbereich bei **91 bis 103 %**; die Schwelle steht deshalb bei 80 %, nicht
bei 95. Wer sie anhebt, erzeugt einen Wächter, der jede Nacht schreit.

⚠ **Warnung, kein Abbruch** — wie die übrigen Sonden.

Aufruf: python3 scripts/pruefe_abdeckung.py [--monate 6] [--schwelle 0.8]
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
# ⚠ VOR dem `govisor`-Import: der Tageslauf laeuft unter launchd ohne PYTHONPATH.
sys.path.insert(0, str(ROOT))

from govisor.laender import AKTIV                                    # noqa: E402
from govisor.verify import api_count, api_count_zeitraum             # noqa: E402

# TED nutzt Alpha-3, unsere Laender Alpha-2.
ALPHA3 = {"DE": "DEU", "AT": "AUT", "CH": "CHE", "LU": "LUX"}

# ⚠ NUR DIE TED-HERKUNFT VERGLEICHEN. Silber traegt in drei von vier Laendern weitere
# Quellen, die TED gar nicht kennt: DE holt zusaetzlich DTVP, DOeE, NetServer und
# Healy-Hudson, AT die Bulk-Daten von OffeneVergaben.at, CH simap.ch. Gegen die
# Gesamtzahl gemessen meldete diese Pruefung im ersten Anlauf 116 bis 388 % „Abdeckung"
# — und haette eine fehlende TED-Lieferung dort NIE sehen koennen, weil die anderen
# Quellen das Loch zudecken. Genau der Fall, den sie finden soll.
#
# `legacy` und `eforms` sind die beiden TED-Schemageneration; alles andere ist eine
# eigene Quelle mit eigenem Abrufer.
TED_HERKUNFT = ("legacy", "eforms")


def _silber(land: str, jahr: int, monat: int) -> int | None:
    """Wie viele TED-Bekanntmachungen liegen fuer diesen Monat in Silber?"""
    import duckdb
    pfad = ROOT / "data" / "silver" / land / "notices"
    if not pfad.is_dir():
        return None
    anfang = f"{jahr}-{monat:02d}-01"
    ende = f"{jahr + (monat == 12)}-{(monat % 12) + 1:02d}-01"
    herkunft = "','".join(TED_HERKUNFT)
    try:
        return duckdb.connect().execute(
            f"select count(*) from read_parquet('{pfad.as_posix()}/**/*.parquet') "
            f"where publication_date >= '{anfang}' and publication_date < '{ende}' "
            f"and schema_gen in ('{herkunft}')"
        ).fetchone()[0]
    except Exception:                                                # noqa: BLE001
        return None


def _silber_zeitraum(land: str, von: dt.date, bis: dt.date) -> int | None:
    """TED-Bekanntmachungen in Silber zwischen zwei Daten (beide einschliesslich)."""
    import duckdb
    pfad = ROOT / "data" / "silver" / land / "notices"
    if not pfad.is_dir():
        return None
    herkunft = "','".join(TED_HERKUNFT)
    try:
        return duckdb.connect().execute(
            f"select count(*) from read_parquet('{pfad.as_posix()}/**/*.parquet') "
            f"where publication_date >= '{von}' and publication_date <= '{bis}' "
            f"and schema_gen in ('{herkunft}')"
        ).fetchone()[0]
    except Exception:                                                # noqa: BLE001
        return None


def laufender_monat(land: str, cc: str, tage: int, karenz: int,
                    schwelle: float) -> list[str]:
    """Der laufende Monat, tageweise. Gibt die Befunde zurueck (leer = sauber)."""
    heute = dt.date.today()
    bis = heute - dt.timedelta(days=karenz)
    von = max(bis - dt.timedelta(days=tage - 1), dt.date(heute.year, heute.month, 1))
    if von > bis:
        return []                                   # Monatsanfang, noch nichts fertig

    befunde: list[str] = []
    # Erst die Fenstersumme — EIN Abruf, und fuer kleine Laender die einzige belastbare
    # Zahl. Dann die Tage, die gross genug sind, um einzeln beurteilt zu werden.
    ist_ges = _silber_zeitraum(land, von, bis)
    soll_ges = api_count_zeitraum(von, bis, cc)
    if ist_ges is None or not soll_ges:
        print(f"  {land}: {von:%d.%m.}–{bis:%d.%m.} nicht abfragbar")
        return []
    anteil = ist_ges / soll_ges
    zeilen = [f"{von:%d.%m.}–{bis:%d.%m.} {ist_ges:,}/{soll_ges:,} {anteil*100:.0f}%"
              + ("" if anteil >= schwelle else "  ⚠")]
    if anteil < schwelle:
        befunde.append(f"{land} {von:%Y-%m-%d}..{bis:%Y-%m-%d}: {ist_ges:,} von "
                       f"{soll_ges:,} ({anteil*100:.0f} %)")

    # ⚠ HIER STAND EINE TAGESREGEL, UND SIE WAR FALSCH GEBAUT — entfernt am 2026-09-13,
    # zwei Tage nachdem ich sie eingebaut hatte. Sie verglich `publication_date` aus unserem
    # Silber mit der TED-Facette `publication-date`. **Das sind nicht dieselben Felder.**
    #
    # Nachgewiesen Stueck fuer Stueck: von acht Bekanntmachungen, die TED unter dem
    # 2026-09-11 fuehrt, liegen ALLE ACHT bei uns — zwei unter dem 09.09., sechs unter dem
    # 10.09. Es fehlte nichts. Die Sonde meldete trotzdem „DE 2026-09-11: 0 von 569 (0 %)",
    # und am Tag davor „10.09.: 400 von 612 (65 %)". Der Versatz geht in beide Richtungen:
    # am 04.09. haben wir 598 und TED 540, am 08.09. 647 gegen 577.
    #
    # ⚠ Der eine echte Fund (09.09., 0 von 676) war Glueck, nicht Konstruktion: an dem Tag
    # war die Datei wirklich leer, weil der Abruf in einen Zeitablauf lief. Eine Regel, die
    # einmal zufaellig richtig liegt und danach jede Nacht schreit, ist schlechter als keine
    # — sie kostet den Wert aller uebrigen Meldungen mit.
    #
    # Was bleibt, ist die FENSTERSUMME: ueber genug Tage mittelt sich der Versatz heraus.
    # Gemessen am 2026-09-13 ueber alle vier Laender, Fenster ab Monatsanfang:
    #
    #     Karenz 2 Tage:  DE 85 % · AT 86 % · CH  89 % · LU  75 %   ← Versatz zieht runter
    #     Karenz 3 Tage:  DE 94 % · AT 95 % · CH 100 % · LU  85 %
    #     Karenz 4 Tage:  DE 98 % · AT 103 % · CH 100 % · LU 102 %  ← sauber
    #
    # Deshalb Karenz 4 als Vorgabe. Wer sie kleiner stellt, misst den Versatz statt der
    # Abdeckung.
    print(f"  {land}: " + " · ".join(zeilen))
    return befunde


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--monate", type=int, default=6, help="wie weit zurueck (ohne den laufenden)")
    ap.add_argument("--schwelle", type=float, default=0.8,
                    help="ab welchem Anteil es als vollstaendig gilt")
    ap.add_argument("--tage", type=int, default=12,
                    help="wie weit der laufende Monat tageweise geprueft wird")
    ap.add_argument("--karenz", type=int, default=4,
                    help="so viele Tage gelten noch als offen — deckt auch den Versatz "
                         "zwischen unserem publication_date und der TED-Facette (s. Modul)")
    a = ap.parse_args()

    heute = dt.date.today()
    monate = []
    m = dt.date(heute.year, heute.month, 1)
    for _ in range(a.monate):
        m = (m - dt.timedelta(days=1)).replace(day=1)   # jeweils ein Monat zurueck
        monate.append((m.year, m.month))
    monate.reverse()

    print("── Abdeckung: Silber gegen TED ──")
    befunde: list[str] = []
    for land in AKTIV:
        cc = ALPHA3.get(land)
        if not cc:
            print(f"  {land}: kein TED-Laendercode hinterlegt — uebersprungen")
            continue
        zeilen = []
        for jahr, monat in monate:
            ist = _silber(land, jahr, monat)
            soll = api_count(jahr, monat, cc)
            if ist is None or not soll:
                zeilen.append(f"{jahr}-{monat:02d} ?")
                continue
            anteil = ist / soll
            marke = "" if anteil >= a.schwelle else "  ⚠"
            zeilen.append(f"{jahr}-{monat:02d} {ist:>6,}/{soll:<6,} {anteil*100:3.0f}%{marke}")
            if anteil < a.schwelle:
                befunde.append(f"{land} {jahr}-{monat:02d}: {ist:,} von {soll:,} "
                               f"({anteil*100:.0f} %)")
        print(f"  {land}: " + " · ".join(zeilen))
    print()
    print(f"── Laufender Monat, Fenstersumme (Karenz {a.karenz} Tage) ──")
    for land in AKTIV:
        cc = ALPHA3.get(land)
        if cc:
            befunde += laufender_monat(land, cc, a.tage, a.karenz, a.schwelle)
    print()
    if befunde:
        print(f"  ⚠ {len(befunde)} Zeitraum/Zeitraeume unter {a.schwelle*100:.0f} %:")
        for b in befunde:
            print(f"      {b}")
        # ⚠ ZWEI VERSCHIEDENE REPARATUREN, je nachdem WAS fehlt — und sie zu verwechseln
        # kostet Stunden: das Monatspaket fuer einen laufenden Monat gibt es noch gar nicht.
        print("     Abgeschlossener Monat: python3 -m govisor.cli ingest --from YYYY-MM "
              "--to YYYY-MM --country <LAND> --evict && python3 -m govisor.cli silver "
              "--country <LAND>")
        print("     Laufender Monat: python3 scripts/fetch_ted_live.py --country <LAND> "
              "--since YYYY-MM-DD --until YYYY-MM-DD && python3 -m govisor.cli silver "
              "--country <LAND>")
        return 1
    print("  ✓ alle geprueften Monate vollstaendig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
