#!/usr/bin/env python3
"""**Verdrahtungspruefung** — findet Bausteine, die es gibt, die aber niemand aufruft.

Der Anlass ist eine Fehlerklasse, die uns wiederholt erwischt hat und die von KEINEM
Unit-Test erfasst wird, weil jedes Stueck fuer sich korrekt ist:

    build_lead_text     im DACH-Gold nie aufgerufen — Datei stand 12 Tage still
    build_lead_lot      dasselbe, 10 Tage
    dedupe/locales      `country` wurde durchgereicht, aber nie aktiviert
    simap `_pick`       Sprachfassungen lagen vor und wurden verworfen
    build_at_gold       Fix landete in einem abgeloesten Modul

Alle 608 Tests waren jedes Mal gruen. Ein Unit-Test prueft, ob ein Baustein das
Richtige tut — nicht, ob ihn jemand benutzt. Genau diese Luecke schliessen die
Sonden hier.

    Sonde 1 (Frische)     Welche Gold-Datei ist gegenueber dem Landeslauf zurueck?
                          Wer nicht mitgebaut wird, faellt zurueck — messbar, ohne
                          dass man wissen muss, WARUM.
    Sonde 2 (Paritaet)    Welche Tabelle gibt es nur in DE? Jede ist entweder eine
                          bewusste Luecke oder ein Verdrahtungsfehler. Das ist der
                          EU-weit-Grundsatz, zum ersten Mal pruefbar statt vereinbart.

AUSNAHMEN sind hier Code, nicht Textdatei, und `tests/test_verdrahtung.py` haelt sie
ehrlich: jede Ausnahme braucht eine Begruendung, und eine Ausnahme, die nicht mehr
zutrifft, laesst die Suite rot werden. Sonst waechst so eine Liste stillschweigend,
bis sie alles enthaelt — dieselbe Krankheit in neuer Form.

    python3 scripts/pruefe_verdrahtung.py            # beide Sonden
    python3 scripts/pruefe_verdrahtung.py --sonde frische
    python3 scripts/pruefe_verdrahtung.py --offen    # auch die bekannten Luecken zeigen

Rueckgabewert 1, sobald etwas UNERKLAERTES auftaucht. Bekannte Luecken (`OFFEN`)
zaehlen nicht als Fehlschlag, werden aber gezaehlt — sie sind eine Arbeitsliste,
kein Friedhof.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
GOLD = ROOT / "data" / "gold"

# ── Sonde 1: Frische ────────────────────────────────────────────────────────
# SCHWELLE, gemessen statt geraten (2026-08-23 an 142 Gold-Dateien): 134 lagen
# innerhalb von 2 Tagen zum jeweils neuesten Stand des Landes, danach klaffte eine
# Luecke bis 4,5 Tage. Der taegliche Lauf braucht mehrere Stunden ueber drei Laender,
# 2 Tage sind also grosszuegig und trennen trotzdem sauber.
SCHWELLE_TAGE = 2.0

# Wer NICHT taeglich gebaut wird. Jede Zeile braucht einen Grund, sonst ist es keine
# Ausnahme, sondern ein vergessener Schritt mit Persilschein.
AUSNAHMEN_FRISCHE: dict[str, str] = {
    "succession_llm_edges":
        "LLM-Adjudikation, kostet Geld — laeuft von Hand ueber scripts/succession_llm.py",
    "entity_merge_map":
        "Entity-Zusammenfuehrung, laeuft nach Pruefung von Hand (scripts/entity_merge_anwenden.py)",
    "entity_merge_urteil":
        "Urteilsstand der Entity-Zusammenfuehrung, gehoert zu entity_merge_map",
    "entity_impressum_beleg":
        "Impressum-Abgleich, eigener Lauf mit Netzzugriff — nicht im Nachtlauf",
    "lead_export.vor-vollpipeline":
        "Sicherungskopie vom Umstieg auf die Vollpipeline (13.08.), bewusst eingefroren",
}

# Dateien, die NIEMAND mehr baut und niemand mehr liest. Am 2026-08-23 waren das
# `ted_dedup` und `atverg_dedup` — die erzeugenden Skripte (`dedupe_at_sources.py`,
# `dedupe_ch_sources.py`) sind seit dem 13.08. geloescht, `govisor/dedupe.py` hat sie
# abgeloest. Beide liegen jetzt in `data/archiv_geloescht_20260823/`, deshalb ist die
# Liste leer. Sie bleibt stehen, weil der naechste Fund dieselbe Form haben wird.
#
# ACHTUNG, gefundene Falle: eine Suche nach dem Dateinamen im Quelltext meldet solche
# Leichen faelschlich als „wird noch verwendet" — der einzige Treffer war ein KOMMENTAR
# in build_marktpuls.py, der erklaert, dass sie abgeloest SIND. Wer Prosa mitzaehlt,
# haelt Leichen fuer lebendig.
LEICHEN: dict[str, str] = {}

# ── Sonde 2: Laenderparitaet ────────────────────────────────────────────────
LAENDER = ("DE", "AT", "CH")

# BEWUSST: gibt es zu Recht nur in DE. Der Grund muss die QUELLE nennen, nicht den
# Aufwand — „lohnt sich nicht" ist keine Begruendung, sondern eine Vertagung.
BEWUSST_NUR_DE: dict[str, str] = {
    "doe_buyer_profile": "DOeE ist eine rein deutsche Unterschwellenquelle",
    "doe_demand": "DOeE ist eine rein deutsche Unterschwellenquelle",
    "buyer_profile": "wird vom DOeE-Builder miterzeugt, haengt an derselben Quelle",
    "entity_impressum_beleg": "deutsche Impressumspflicht (§5 DDG) — kein AT/CH-Gegenstueck",
    "entity_merge_map": "Entity-Aufloesung ist auf das deutsche Handelsregister getunt",
    "entity_merge_urteil": "gehoert zu entity_merge_map",
    "succession_llm_edges": "LLM-Lauf auf dem DE-Bestand, bewusst nicht auf AT/CH ausgeweitet",
    "lead_kategorie": "Kategorie-Wasserfall liest DE-Dubletten und DE-Vokabular",
    "bronze_inventory": "Inventar der DE-Bronze-Pakete (TED-Vollabzug)",
    "document_duplicates": "Dokument-Dublettenwall; AT/CH haben 0 % Dokumentabdeckung",
    "lead_region_fill": "Bundesland-Auffuellung, deutsche NUTS-Systematik",
}

# OFFEN: bekannte Luecke — eine Tabelle, die es nur in DE gibt, obwohl sie es nicht
# muesste. Sie steht hier statt in BEWUSST_NUR_DE, damit sie sichtbar bleibt; wer eine
# davon verdrahtet, streicht die Zeile, und `test_kein_offen_eintrag_ist_laengst_erledigt`
# verlangt das auch.
#
# Am 2026-08-23 standen hier 16 Eintraege. Alle sind erledigt: die Builder waren durchweg
# country-faehig und wurden im DACH-Lauf nur nicht aufgerufen. Verdrahtet, gemessen:
#     lead_criteria    AT 22.471 / CH 13.656      value_anchor  AT 228.920 / CH 51.919
#     lead_party       AT 38.681 / CH 16.462      buyer_stats   AT  4.341 / CH  5.656
#     lead_requirement AT  2.748 / CH    595      market_opp.   AT    317 / CH    125
# Die Liste ist leer und bleibt stehen, weil der naechste Fund dieselbe Form haben wird.
OFFEN_NUR_DE: dict[str, str] = {}


def _dateien(wurzel: pathlib.Path) -> dict[str, list[pathlib.Path]]:
    """Gold-Parquets je Land. Leere Laender fallen raus, nicht durch."""
    aus: dict[str, list[pathlib.Path]] = {}
    if not wurzel.is_dir():
        return aus
    for d in sorted(p for p in wurzel.iterdir() if p.is_dir()):
        fs = list(d.glob("*.parquet"))
        if fs:
            aus[d.name] = fs
    return aus


def sonde_frische(zeige_offen: bool = False,
                  wurzel: pathlib.Path = GOLD) -> list[str]:
    """Welche Gold-Datei haengt gegenueber dem Lauf ihres Landes zurueck?

    Bezug ist die NEUESTE Datei DESSELBEN Landes, nicht die Uhr: der Lauf kann
    ausfallen, ohne dass gleich alles Alarm schlaegt. Damit ein komplett stehen
    `wurzel` ist ausschliesslich fuer den Test da: eine Sonde, die man nur gegen die
    echte Datenlage laufen lassen kann, kann man nicht beweisen — und eine unbewiesene
    Pruefung ist genau das Problem, das sie loesen soll.

    Bezug ist die NEUESTE Datei DESSELBEN Landes, nicht die Uhr: der Lauf kann
    ausfallen, ohne dass gleich alles Alarm schlaegt. Damit ein komplett stehen
    gebliebenes Land trotzdem auffaellt, wird zusaetzlich Land gegen Land geprueft —
    sonst wandert der Bezugspunkt lautlos mit.
    """
    dateien = _dateien(wurzel)
    if not dateien:
        print("  keine Gold-Ebene gefunden — Sonde uebersprungen")
        return []

    neuestes = {land: max(f.stat().st_mtime for f in fs) for land, fs in dateien.items()}
    global_neu = max(neuestes.values())
    fehler: list[str] = []

    # (a) Ganzes Land zurueck?
    for land, t in sorted(neuestes.items()):
        rueck = (global_neu - t) / 86400
        if rueck > SCHWELLE_TAGE:
            fehler.append(f"Land {land} baut seit {rueck:.1f} Tagen nichts mehr "
                          f"(neueste Datei {dt.datetime.fromtimestamp(t):%d.%m. %H:%M})")

    # (b) Einzelne Datei zurueck?
    offen = 0
    for land, fs in sorted(dateien.items()):
        for f in sorted(fs):
            rueck = (neuestes[land] - f.stat().st_mtime) / 86400
            if rueck <= SCHWELLE_TAGE:
                continue
            if f.stem in LEICHEN:
                offen += 1
                if zeige_offen:
                    print(f"    LEICHE  {land}/{f.stem}: {LEICHEN[f.stem]}")
                continue
            if f.stem in AUSNAHMEN_FRISCHE:
                continue
            fehler.append(f"{land}/{f.name} haengt {rueck:.1f} Tage zurueck — "
                          f"wird der Schritt im Lauf des Landes ueberhaupt aufgerufen?")
    if offen and not zeige_offen:
        print(f"    ({offen} Leichen — mit --offen anzeigen)")
    return fehler


def sonde_paritaet(zeige_offen: bool = False,
                   wurzel: pathlib.Path = GOLD) -> list[str]:
    """Welche Gold-Tabelle gibt es nur in DE?

    Jede ist entweder eine bewusste Luecke (dann steht sie in BEWUSST_NUR_DE mit
    Quellen-Begruendung) oder eine bekannte Baustelle (OFFEN_NUR_DE) — oder ein
    Fehler, den niemand bemerkt hat. Nur der dritte Fall laesst die Sonde fallen.
    """
    da: dict[str, set[str]] = collections.defaultdict(set)
    for p in wurzel.glob("*/*.parquet"):
        da[p.stem].add(p.parent.name)
    if not da:
        print("  keine Gold-Ebene gefunden — Sonde uebersprungen")
        return []

    fehler: list[str] = []
    offen: list[str] = []
    for tabelle, laender in sorted(da.items()):
        fehlend = [l for l in LAENDER if l not in laender]
        if not fehlend or "DE" not in laender:
            continue          # in allen Laendern da, oder gar nicht in DE (kein Paritaets-Fall)
        if tabelle in BEWUSST_NUR_DE or tabelle in AUSNAHMEN_FRISCHE or tabelle in LEICHEN:
            continue
        if tabelle in OFFEN_NUR_DE:
            offen.append(f"    OFFEN   {tabelle} fehlt in {','.join(fehlend)}: "
                         f"{OFFEN_NUR_DE[tabelle]}")
            continue
        fehler.append(f"{tabelle} gibt es nur in DE (fehlt in {','.join(fehlend)}) und "
                      f"steht in keiner Liste — bewusste Luecke oder Verdrahtungsfehler?")
    if offen:
        if zeige_offen:
            print("\n".join(offen))
        else:
            print(f"    ({len(offen)} bekannte Luecken — mit --offen anzeigen)")
    return fehler


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sonde", choices=("frische", "paritaet", "alle"), default="alle")
    ap.add_argument("--offen", action="store_true",
                    help="bekannte Luecken und Leichen mit auflisten")
    a = ap.parse_args()

    alles: list[str] = []
    if a.sonde in ("frische", "alle"):
        print("── Sonde 1: Frische (wer wird nicht mitgebaut?) ──")
        f = sonde_frische(a.offen)
        alles += f
        print(f"    {len(f)} unerklaerte Rueckstaende")
    if a.sonde in ("paritaet", "alle"):
        print("── Sonde 2: Laenderparitaet (was gibt es nur in DE?) ──")
        f = sonde_paritaet(a.offen)
        alles += f
        print(f"    {len(f)} unerklaerte Alleingaenge")

    if alles:
        print("\n⚠ Verdrahtungspruefung: " + str(len(alles)) + " Befund(e)")
        for z in alles:
            print(f"  · {z}")
        return 1
    print("\n✓ Verdrahtungspruefung sauber")
    return 0


if __name__ == "__main__":
    sys.exit(main())
