#!/usr/bin/env python3
"""**Gold-Waechter** — jeder Fremdschluessel in Gold muss auflösen, in JEDEM Land.

`verify.gold_integrity` gibt es seit dem ersten Gold-Bau, und es ist die Pruefung, die
Waisen findet, bevor sie stumm Leads verschlucken. Sie hing bis zum 2026-09-02 aber an
`python -m govisor.cli verify` — und dieser Befehl prueft VOR der Integritaet jeden Monat
seit 2004 gegen die TED-Search-API. Das ist ein Netzlauf ueber rund 270 Monate; niemand
ruft ihn taeglich auf, und der Tageslauf tat es nie.

Damit war die Lage genau die, vor der `docs/laender/12-fallenkatalog.md` warnt: eine
gebaute, korrekte, unaufgerufene Pruefung. Gefunden wurde das am 2026-09-02 an 28 Waisen
in `notice_duplicates` (AT) — sie standen mindestens seit dem Vortag da, und ohne eine
Nachfrage von Hand haette sie niemand gesehen.

**Warum das ein eigenes Skript ist und kein Flag an `cli verify`.** Die Integritaet
braucht kein Netz, keine Bronze-Archive und keine Monatsschleife: gemessen 2026-09-02
kostet sie ueber DE+AT+CH zusammen **1,3 Sekunden** (DE 0,9 · AT 0,2 · CH 0,1). Alles,
was sie teuer machte, war das Beiwerk drumherum.

**Die Laender kommen von der Platte, nicht aus einer Liste** (`pruefe_verdrahtung._laender`,
dieselbe Quelle wie die Verdrahtungssonden). Wer Polen auf Gold hebt, muss hier nichts
eintragen — sonst waere der Waechter die naechste Liste, die aufhoert zu wachsen.

**Ausnahmen stehen bewusst NICHT hier**, sondern in `verify.gold_integrity` selbst
(`FK_AUSNAHMEN`, `nur_de`, `gruppen_checks`) — mit Messung daneben und von
`tests/test_plumbing.py` gehalten. Eine zweite Ausnahmeliste an dieser Stelle waere genau
die handgepflegte Parallelliste, an der schon der Altersbericht gescheitert ist.

    python3 scripts/pruefe_gold_integritaet.py            # alle Laender mit Gold-Ebene
    python3 scripts/pruefe_gold_integritaet.py --land AT

Rueckgabewert 1, sobald irgendein Fremdschluessel ins Leere zeigt.
"""

from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys

# ZWEI Wurzeln, bewusst getrennt. `HIER` ist, wo der Code liegt — das steht fest.
# `ROOT` ist, wo die DATEN liegen, und nur das darf ein Aufrufer verbiegen (die Tests tun
# es). Beides in einer Variablen zu fuehren sieht richtig aus, solange beides dasselbe
# Verzeichnis ist, und faellt in dem Moment um, in dem es das nicht mehr ist.
HIER = pathlib.Path(__file__).resolve().parent
ROOT = HIER.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(ROOT))


def _laender() -> list[str]:
    """Welche Laender haben eine Gold-Ebene? Gemessen, nicht gelistet.

    Bewusst aus `pruefe_verdrahtung` geliehen statt nachgebaut: zwei Funktionen, die
    dieselbe Frage beantworten, driften auseinander, sobald eine von beiden gepflegt wird.
    """
    spec = importlib.util.spec_from_file_location(
        "pv_gold", HIER / "pruefe_verdrahtung.py")
    pv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pv)
    gold = ROOT / "data" / "gold"
    return list(pv._laender(gold)) if gold.is_dir() else []


def befunde(land: str) -> list[tuple[str, int]]:
    """(Beschreibung, Waisenzahl) je Verstoss — leer heisst sauber."""
    from govisor.config import Config
    from govisor.verify import gold_integrity
    return gold_integrity(Config(data_dir=ROOT / "data"), land)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--land", help="nur dieses Land pruefen (Default: alle mit Gold-Ebene)")
    a = ap.parse_args(argv)

    laender = [a.land] if a.land else _laender()
    if not laender:
        print("Keine Gold-Ebene gefunden — nichts zu pruefen.")
        return 0

    gesamt = 0
    for land in laender:
        treffer = befunde(land)
        if not treffer:
            print(f"  ✓ {land}: alle Fremdschluessel loesen auf")
            continue
        for label, n in treffer:
            print(f"  ✗ {land}: {label} — {n:,} Waisen")
        gesamt += sum(n for _, n in treffer)

    if gesamt:
        print(f"\n⛔ {gesamt:,} Waisen in Gold. Eine Waise verschwindet nicht, sie wird "
              f"still\n   weggejoint — der Lead fehlt, ohne dass etwas scheitert.\n"
              f"   Naechster Schritt: die genannte Kind-Tabelle neu bauen und nachsehen, ob "
              f"ihre\n   Eltern-Tabelle seither ERSETZT wurde (haeufigste Ursache) oder ob "
              f"eine Quelle\n   Kennungen zurueckgezogen hat (s. docs/laender/"
              f"04-dublettenwall.md).")
        return 1
    print("\n✓ Gold-Integritaet: jeder Fremdschluessel loest auf.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
