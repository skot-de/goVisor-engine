#!/usr/bin/env python3
"""**NUTS-Waechter** — findet eine Regionskennung, die in Wahrheit ein Vorgabewert ist.

Der Anlass, gemessen am 2026-09-01. Die DÖE-Quelle kannte ueber ihren gesamten Bestand
**genau einen** NUTS-Wert: `DEA22` (Bonn). Er stand auf 33.966 Kaeuferzeilen in 393
verschiedenen Orten, und kein einziger DÖE-Kaeufer trug je einen eigenen. Der Grund war
ein Parser-Griff in den falschen Teilbaum: der Kaeufer hat im eForms-XML kein NUTS-Feld,
der eSender (Beschaffungsamt des BMI, Bonn) schon — und `_iter_named` stieg in dessen
Block ab. Im Frontend standen so 172 Leads aus Magdeburg unter „Nordrhein-Westfalen",
mit `regionQuelle='amtlich'`, weil ja ein Wert dastand.

**Warum das ohne Waechter nicht auffaellt.** Nichts scheitert. Ein Kaeufer ohne eigene
NUTS sieht nach dem Fehlgriff aus wie einer MIT — nur mit der Anschrift des Absenders.
Kein Test wird rot, keine Zahl sieht falsch aus, die Abdeckung STEIGT sogar.

**Woran man es erkennt — und woran NICHT.** Der naheliegende Verdacht ist „eine NUTS mit
auffaellig vielen verschiedenen Orten". Nachgemessen taugt er nicht: `DEA22` spannte
92 Orte, der ehrliche Hoechstwert im Bestand liegt bei 110 (`DED42` Erzgebirgskreis, lauter
Kleinstaedte). Eine Zaehl-Schranke haette genau diesen Fehler durchgelassen.

Was trennt, sind ZWEI Bedingungen zusammen — beide gemessen, keine geraten:

    1. Die MEHRHEIT der Zeilen sitzt in einem Ort, der nachweislich zu einer anderen
       Region gehoert  (`fremd_quote >= 0.50`)
    2. Diese fremde Masse verteilt sich auf MINDESTENS VIER verschiedene Regionen,
       jede mit >= 2 % der Zeilen  (`fremde_regionen >= 4`)

Bedingung 2 ist die eigentliche Unterschrift eines Vorgabewerts. Eine echte NUTS-3 liegt
in genau einem Bundesland; ihre Orte loesen nach genau diesem auf. Was dagegen fremd
aussieht, sind ueberwiegend Namensdoppelungen — „Halle" gibt es in Sachsen-Anhalt UND in
Westfalen, „Weilheim", „Dillingen" und „Heidenheim" je zweimal. Solche Faelle erzeugen
EINE fremde Region, nie vier. Gemessen am 2026-09-01 ueber DE/AT/CH: `DEA22` kam auf
sechs, der hoechste ehrliche Wert im ganzen Bestand auf zwei.

Geprueft wird SILBER, nicht Gold: dort schreibt der Parser hin, und dort faellt es auf,
bevor es sich ueber Entities, Leads und Frontend verteilt.

⚠ Der Waechter laeuft ueber ALLE Laender mit Silber-Bestand, nicht nur DE. Der Fehler ist
keine deutsche Eigenheit — jede Plattform mit eSender-Block kann ihn haben.

    python3 scripts/pruefe_nuts_vorgabe.py              # alle Laender
    python3 scripts/pruefe_nuts_vorgabe.py --land DE
    python3 scripts/pruefe_nuts_vorgabe.py --alle       # auch die unauffaelligen Werte

Rueckgabewert 1, sobald ein UNERKLAERTER Vorgabewert auftaucht. Bekannte, bewusst
hingenommene Faelle stehen in `AUSNAHMEN` — als Code mit Begruendung, nicht als Textdatei.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

# ── SCHRANKEN (gemessen 2026-09-01, s. Kopf) ─────────────────────────────────────────
# Unter MIN_ZEILEN aufloesbaren Zeilen ist die Quote Zufall; 200 traf im Bestand jede
# NUTS, die ueberhaupt Gewicht hat (DE 414, AT 22, CH 16 Kennungen).
MIN_ZEILEN = 200
# Mehrheit im fremden Land. DEA22 lag bei 0,92; der hoechste ehrliche Wert mit
# Masse-Verteilung bei 0,44 (DE11C Heidenheim, eine reine Namensdoppelung).
MIN_FREMD_QUOTE = 0.50
# Die entscheidende Bedingung. Ehrlicher Hoechstwert im Bestand: 2. DEA22: 6.
MIN_FREMDE_REGIONEN = 4
# Eine fremde Region zaehlt nur, wenn sie Masse traegt — sonst waere jede einzelne
# Namensdoppelung eine eigene „Region".
MIN_REGIONSANTEIL = 0.02

# „Bundesland" sitzt je Land auf einer anderen NUTS-Stelle — dieselbe Tabelle wie in
# `scripts/region_ableiten.py` und `govisor/gold._REGION_STELLEN`.
REGION_STELLEN = {"DE": 3, "AT": 4, "CH": 5}

# ── AUSNAHMEN ────────────────────────────────────────────────────────────────────────
# Jede Zeile braucht einen Grund. Eine Ausnahme ohne Grund ist keine Ausnahme, sondern
# ein Fehler mit Persilschein. `tests/test_nuts_vorgabe.py` haelt die Liste ehrlich:
# eine Ausnahme fuer etwas, das gar nicht mehr anschlaegt, laesst die Suite rot werden.
AUSNAHMEN: dict[tuple[str, str], str] = {}


def _laender() -> list[str]:
    silber = ROOT / "data" / "silver"
    if not silber.exists():
        return []
    return sorted(p.name for p in silber.iterdir()
                  if p.is_dir() and (p / "notice_parties").exists()
                  and p.name in REGION_STELLEN)


def befunde(land: str) -> list[dict]:
    """Je NUTS-Kennung des Landes: sieht sie aus wie ein Vorgabewert?

    Gibt ALLE geprueften Kennungen zurueck (mit `verdaechtig`-Marke), damit man auch
    sehen kann, wie nah etwas an der Schranke liegt — eine Schranke, deren Umgebung
    man nicht kennt, ist geraten.
    """
    import duckdb

    import region_ableiten as ra

    stellen = REGION_STELLEN[land]
    orte = ra.ortsverzeichnis(land)
    if not orte:
        return []
    glob = f"data/silver/{land}/notice_parties/*/*.parquet"
    if not list((ROOT / f"data/silver/{land}/notice_parties").glob("*/*.parquet")):
        return []
    con = duckdb.connect()
    zeilen = con.execute(f"""
        SELECT nuts, town, count(*) AS n
        FROM read_parquet('{(ROOT / glob).as_posix()}', union_by_name=true)
        WHERE role='buyer' AND nuts IS NOT NULL AND nuts <> ''
          AND town IS NOT NULL AND town <> '' AND length(nuts) >= {stellen}
        GROUP BY 1, 2""").fetchall()
    con.close()

    # Ort -> Region, nur wo der Ortsname EINDEUTIG ist (das leistet `ortsverzeichnis`).
    aufgeloest = []
    for nuts, town, n in zeilen:
        reg_ort = orte.get(" ".join(ra._worte(town)))
        if reg_ort is not None:           # sonst nicht pruefbar — nicht „falsch"
            aufgeloest.append((nuts, town, reg_ort, n))
    return bewerte(land, aufgeloest, stellen)


def bewerte(land: str, aufgeloest: list[tuple[str, str, str, int]],
            stellen: int) -> list[dict]:
    """Die eigentliche Regel, getrennt vom Datenzugriff — damit sie pruefbar ist.

    `aufgeloest` sind Tupel (NUTS am Kaeufer, Ortsname, Region DES ORTES, Zeilenzahl).
    Eine Schranke, die nur im Zusammenspiel mit dem echten Bestand laeuft, kann man
    nicht gegen einen erfundenen Fall halten — und genau das braucht man, um sie
    spaeter nicht versehentlich zu „viele Orte" zu vereinfachen.
    """
    je_nuts: dict[str, dict] = {}
    for nuts, town, reg_ort, n in aufgeloest:
        e = je_nuts.setdefault(nuts, {"zeilen": 0, "fremd": 0, "je_region": {}, "orte": set()})
        e["zeilen"] += n
        e["orte"].add(town)
        if reg_ort != nuts[:stellen]:
            e["fremd"] += n
            e["je_region"][reg_ort] = e["je_region"].get(reg_ort, 0) + n

    aus = []
    for nuts, e in je_nuts.items():
        if e["zeilen"] < MIN_ZEILEN:
            continue
        quote = e["fremd"] / e["zeilen"]
        regionen = sorted((r for r, m in e["je_region"].items()
                           if m / e["zeilen"] >= MIN_REGIONSANTEIL),
                          key=lambda r: -e["je_region"][r])
        aus.append({
            "land": land, "nuts": nuts, "zeilen": e["zeilen"], "orte": len(e["orte"]),
            "fremd_quote": quote, "fremde_regionen": regionen,
            "verdaechtig": quote >= MIN_FREMD_QUOTE and len(regionen) >= MIN_FREMDE_REGIONEN,
        })
    return sorted(aus, key=lambda b: (-len(b["fremde_regionen"]), -b["fremd_quote"]))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--land", help="nur dieses Land pruefen")
    p.add_argument("--alle", action="store_true",
                   help="auch die unauffaelligen Kennungen zeigen (Umgebung der Schranke)")
    a = p.parse_args(argv)

    laender = [a.land] if a.land else _laender()
    if not laender:
        print("Kein Silber-Bestand gefunden — nichts zu pruefen.")
        return 0

    offen = 0
    for land in laender:
        alle = befunde(land)
        if not alle:
            print(f"\n── {land} ── kein Ortsverzeichnis oder kein Bestand, uebersprungen")
            continue
        treffer = [b for b in alle if b["verdaechtig"]]
        print(f"\n── {land} ── {len(alle)} Kennungen mit >= {MIN_ZEILEN} pruefbaren "
              f"Kaeuferzeilen")
        for b in treffer:
            grund = AUSNAHMEN.get((land, b["nuts"]))
            marke = "erklaert" if grund else "⛔ VORGABEWERT"
            print(f"  {marke}  {b['nuts']}  {b['zeilen']} Zeilen in {b['orte']} Orten · "
                  f"{b['fremd_quote']:.0%} davon in fremder Region · "
                  f"verteilt auf {len(b['fremde_regionen'])}: "
                  f"{', '.join(b['fremde_regionen'])}")
            if grund:
                print(f"           Grund: {grund}")
            else:
                offen += 1
        if not treffer:
            spitze = alle[0] if alle else None
            if spitze:
                print(f"  ✓ kein Vorgabewert. Naechster an der Schranke: {spitze['nuts']} "
                      f"({spitze['fremd_quote']:.0%} fremd, "
                      f"{len(spitze['fremde_regionen'])} Regionen; Schranke: "
                      f"{MIN_FREMD_QUOTE:.0%} / {MIN_FREMDE_REGIONEN})")
        if a.alle:
            for b in alle[:15]:
                print(f"     {b['nuts']:6s} {b['zeilen']:7d} Zeilen  {b['orte']:4d} Orte  "
                      f"fremd {b['fremd_quote']:6.1%}  Regionen {len(b['fremde_regionen'])}")

    if offen:
        print(f"\n⛔ {offen} unerklaerte Regionskennung(en) verhalten sich wie ein "
              f"Vorgabewert.\n   Naechster Schritt: im Bronze-XML nachsehen, WOHER der "
              f"Wert kommt — traegt ihn\n   der Kaeufer selbst, oder steht er in einem "
              f"fremden Parteiblock (eSender,\n   veroeffentlichende Stelle)? "
              f"S. govisor/schema._iter_named_ausserhalb.")
        return 1
    print("\n✓ Keine Regionskennung verhaelt sich wie ein Vorgabewert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
