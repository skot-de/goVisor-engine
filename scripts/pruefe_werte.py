#!/usr/bin/env python3
"""**Wert-Waechter** — findet Betraege, die keiner lesen kann, und solche, die niemand zahlt.

WARUM ES DIESE DATEI GIBT. Am 2026-09-15 stellte sich heraus, dass **86.177**
Bekanntmachungen ueber vier Laender einen Endwert **ohne Waehrung** trugen — DE 74.051,
AT 8.425, LU 2.227, CH 1.474, ueber den ganzen Zeitraum 2010 bis 2024. Ursache war eine
einzige Zeile im Legacy-Parser: die Waehrung haengt im Vor-2014-Format am ELTERN-Knoten
(`COSTS_RANGE_AND_CURRENCY_WITH_VAT_RATE@CURRENCY`), gesucht wurde sie am Wertknoten.

Dahinter versteckt lag ein zweiter Fehler derselben Zeile: der Textknoten ist formatiert
(`189 945 844,15`), und `_to_amount` wirft das Dezimalkomma weg — rund 57 % der
betroffenen Saetze trugen deshalb das **Hundertfache** ihres Wertes. Ein Schweizer
Tunnellos stand mit 19 Mrd CHF statt 190 Mio da.

⚠ **DER ENTSCHEIDENDE PUNKT: gemeldet wurde beides die ganze Zeit.** Gold setzt seit
Langem das Qualitaetsmerkmal `waehrung_angenommen`, wenn ein Wert ohne Waehrung dasteht.
Das Merkmal beschreibt eine DATENLAGE („die Quelle nennt keine Waehrung") — und wurde zur
Tarnkappe fuer einen PARSER-FEHLER („wir lesen sie nicht"). Niemand sah nach, weil die
Zahl nie jemandem vorgelegt wurde.

Dieser Waechter legt sie vor. Zwei Fragen, beide auf Silber, ohne Netz:

  1. **Wie viele Werte haben keine Waehrung?** Ein einzelner Satz ist eine Datenlage.
     Ein ganzer Jahrgang ist ein Parser-Fehler.
  2. **Wie viele Werte liegen ueber der Plausibilitaetsgrenze?** Die Grenze (1 Mrd) gibt
     es in `gold.build_quality` seit Langem — sie hat die 19 Mrd nie gesehen, weil die
     Waehrungssperre die Saetze eine Stufe frueher verwarf. Ein Sprung hier ist das
     typische Zeichen eines Faktorfehlers.

    python3 scripts/pruefe_werte.py              # alle Laender mit Silber
    python3 scripts/pruefe_werte.py --land CH

Rueckgabewert 1, sobald eine Schwelle reisst. Der Tageslauf wertet ihn als Warnung.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

HIER = pathlib.Path(__file__).resolve().parent
ROOT = HIER.parent
sys.path.insert(0, str(ROOT))

# Ein Wert ohne Waehrung ist als Einzelfall vertretbar — manche Quellen nennen sie
# wirklich nicht. Ab hier ist es keine Datenlage mehr, sondern ein Leser, der nicht liest.
ANTEIL_OHNE_WAEHRUNG = 0.01        # 1 % der Saetze mit Wert
# Die Obergrenze aus `gold.build_quality`. Darueber wird der Wert ohnehin verworfen; die
# Frage ist nicht, ob er zaehlt, sondern warum er da ist.
GRENZE_EUR = 1e9
ANTEIL_UEBER_GRENZE = 0.002        # 0,2 %

# ⚠ EINE QUOTE BRAUCHT EINEN NENNER, DER SIE TRAEGT. Bei 69 bewerteten Bekanntmachungen
# (EU-Bestand, gemessen 2026-09-16) sind acht echte Milliardenrahmen 11,6 % — die Sonde
# meldete Alarm fuer eine Datenlage, die voellig in Ordnung ist. Sieben der acht sind
# dasselbe OCRE-Cloud-Rahmenwerk von GEANT, der achte eine HVDC-Umrichterstation.
# Unterhalb dieses Nenners sagt ein Anteil nichts; dann zaehlt nur die absolute Zahl,
# und die ist hier zu klein fuer eine Aussage.
MINDEST_NENNER = 500


def _laender() -> list[str]:
    """Welche Laender haben Silber? Gemessen, nicht gelistet."""
    silber = ROOT / "data" / "silver"
    if not silber.is_dir():
        return []
    return sorted(p.name for p in silber.iterdir()
                  if p.is_dir() and (p / "notices").is_dir())


def befunde(land: str) -> list[str]:
    """Klartext-Befunde — leer heisst sauber."""
    import duckdb

    from govisor.gold import _wert_in_eur_sql

    muster = (ROOT / "data" / "silver" / land / "notices" / "**" / "*.parquet").as_posix()
    # ⚠ DIE GRENZE GILT DEM EURO-BETRAG, NICHT DEM ROHBETRAG — sonst hat diese Sonde
    # genau die Falle, vor der sie warnt (H9 im Fallenkatalog). Gemessen am 2026-09-16 an
    # Polen: **348** Werte ueber 1 Mrd roh, aber nur **75** ueber 1 Mrd Euro. Eine Milliarde
    # Zloty sind 236 Mio Euro; die Sonde haette Polen fuer seine Waehrung bestraft.
    eur = _wert_in_eur_sql()
    con = duckdb.connect()
    try:
        mit_wert, ohne_waehrung, ueber = con.execute(f"""
            SELECT count(*),
                   count(*) FILTER (WHERE value_currency IS NULL),
                   count(*) FILTER (WHERE ({eur}) > {GRENZE_EUR})
            FROM read_parquet('{muster}') WHERE final_value IS NOT NULL""").fetchone()
    finally:
        con.close()
    if not mit_wert:
        return []

    aus: list[str] = []
    if ohne_waehrung / mit_wert > ANTEIL_OHNE_WAEHRUNG:
        aus.append(
            f"{ohne_waehrung:,} von {mit_wert:,} Werten ohne Waehrung "
            f"({100 * ohne_waehrung / mit_wert:.1f} %) — ein ganzer Jahrgang ohne "
            f"Waehrung ist ein Parser-Fehler, keine Datenlage")
    if mit_wert >= MINDEST_NENNER and ueber / mit_wert > ANTEIL_UEBER_GRENZE:
        aus.append(
            f"{ueber:,} von {mit_wert:,} Werten ueber {GRENZE_EUR:,.0f} EUR "
            f"({100 * ueber / mit_wert:.2f} %) — typisch fuer einen Faktorfehler beim "
            f"Lesen formatierter Betraege")
    return aus


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--land", help="nur dieses Land pruefen")
    a = ap.parse_args(argv)

    laender = [a.land] if a.land else _laender()
    if not laender:
        print("Kein Silber gefunden — nichts zu pruefen.")
        return 0

    # ⚠ DIE LAENDER KOMMEN VON DER PLATTE, damit ein neues nicht stillschweigend
    # uebersprungen wird. Gemeldet wird aber nur, was die Pipeline auch BAUT: unter
    # `data/silver` liegen Altbestaende zurueckgebauter Laender (PL, EU), und ein
    # Waechter, der jede Nacht ueber Daten klagt, die niemand pflegt, erzieht zum
    # Wegsehen. Sie stehen darum unter dem Strich, nicht im Befund.
    from govisor.laender import AKTIV

    schlimm = 0
    ruhend: list[str] = []
    for land in laender:
        zeilen = befunde(land)
        if land not in AKTIV:
            # Immer nennen, nie alarmieren: der Bestand existiert, wird aber nicht
            # gepflegt. Verschwiege ihn die Sonde, waere er beim naechsten Anlauf
            # vergessen; alarmierte sie, erzoege sie zum Wegsehen.
            ruhend.append(f"{land}{' ⚠' if zeilen else ''}")
            continue
        if not zeilen:
            print(f"  {land}: sauber")
            continue
        schlimm += 1
        for z in zeilen:
            print(f"  ⚠ {land}: {z}")
    if ruhend:
        print(f"\n  ruhende Bestaende (liegen auf der Platte, stehen nicht in AKTIV, "
              f"werden nicht gebaut): {' · '.join(ruhend)}")
        print("     ⚠ = traegt Befunde. Kein Alarm — diese Daten pflegt niemand. Wer eines "
              "dieser Laender\n       wiederbelebt, baut Silber zuerst neu "
              "(s. Kapitel 13 der Laender-Bibel).")
    if schlimm:
        print(f"\n⚠ {schlimm} Land/Laender mit Wert-Befunden.")
        return 1
    print("\n✓ Wert-Pruefung sauber")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
