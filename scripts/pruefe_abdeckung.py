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

⚠ **Der laufende Monat wird übersprungen.** Er füllt sich noch; ein Rückstand dort ist
kein Befund, sondern der Normalzustand.

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
from govisor.verify import api_count                                 # noqa: E402

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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--monate", type=int, default=6, help="wie weit zurueck (ohne den laufenden)")
    ap.add_argument("--schwelle", type=float, default=0.8,
                    help="ab welchem Anteil es als vollstaendig gilt")
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
    if befunde:
        print(f"  ⚠ {len(befunde)} Monat(e) unter {a.schwelle*100:.0f} %:")
        for b in befunde:
            print(f"      {b}")
        print("     Nachladen: python3 -m govisor.cli ingest --from YYYY-MM --to YYYY-MM "
              "--country <LAND> --evict && python3 -m govisor.cli silver --country <LAND>")
        return 1
    print("  ✓ alle geprueften Monate vollstaendig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
