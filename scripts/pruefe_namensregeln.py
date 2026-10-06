#!/usr/bin/env python3
"""**Hoheitswache** — findet Hoheitsträger, die das Länderprofil noch nicht kennt.

⚠ WARUM ES DIESE SONDE GIBT. Das Muster für generische Hoheitsträger stand bis zum
2026-10-06 als modulfeste DEUTSCHE Regex in `govisor/names.py` und wurde auf ALLE Länder
angewandt. Folge, gemessen: „REPUBLIK ÖSTERREICH vertreten durch die Bundesministerin für
Landesverteidigung" wurde nie aufgelöst — 5.251 österreichische Zeilen unter 724 Namen
landeten als EINE Entität `name:republik oesterreich` (428 Namen in 16 Orten). In Deutschland
richtete der Fehler nichts an; er wartete auf das erste Land mit einem anderen Hoheitsträger.
Dieselbe Form wie Fallenkatalog C16 (ein Jahr unsichtbar, weil LU in keiner Suchmenge stand).

**Die Sonde pflegt keine Liste von Ländern, sie misst die Quelle.** Für jedes Land: welche
Präfixe stehen vor einer Vertretungsklausel, wie viele VERSCHIEDENE Stellen vertreten sie,
und greift `locales.<LAND>.re_sovereign` darauf? Ein Präfix, der viele verschiedene Stellen
vertritt und nicht erkannt wird, ist ein Kandidat — und solange er nicht erkannt ist, tragen
alle diese Stellen EINEN Schlüssel.

⚠ **WORAN SIE SICH NICHT FESTMACHT, UND WARUM.** Der erste Entwurf wurde rot, sobald ein
Präfix viele Stellen vertritt und das Muster ihn nicht kennt. Damit meldete er für DE 24
Befunde, von denen 22 richtig waren — „Stadt Hanau", „Landeshauptstadt Potsdam", „DB Netz
AG", „Klinikum Chemnitz": alles Stellen mit vielen Abteilungen, bei denen der Präfix bleiben
MUSS. Diese Liste ist offen; jede neue Stadt hätte eine Zeile gebraucht, und genau das ist
die alternde Liste, die hier nicht entstehen soll.

Ein messbares Trennmerkmal gibt es nicht. Geprüft und verworfen (2026-10-06): die Hypothese
„ein Hoheitsträger vertritt EIGENSTÄNDIGE Organisationen, eine Stadt ihre Ämter" — gemessen
am Anteil der Vertretenen, die auch allein als Käufer vorkommen, liegen die Hoheitsträger bei
30–41 % (Bundesrepublik 39 %, Freistaat Bayern 36 %, Saarland 30 %) und die Stellen bei
11–78 % (Landeshauptstadt Potsdam 78 %, Landkreis Freising 11 %). Vollständig überlappend.

**Ob ein Präfix eine Gebietskörperschaft ist, ist Fachwissen, keine Eigenschaft der Daten.**
Deshalb: die Gebietskörperschaften eines Landes sind eine GESCHLOSSENE, kleine Menge (ein
Bund, ~16 Länder) und gehören als Regex-Familie ins Länderprofil. Die Stellen sind eine
OFFENE Menge und dürfen nie zu einem Befund führen.

**Rot wird die Sonde deshalb nur in einem Fall**: ein Land, dessen Quelle Vertretungsklauseln
in nennenswertem Umfang zeigt, hat gar KEIN Hoheitsmuster. Das ist genau der AT-Fehler, und
er wiederholt sich beim nächsten Land von selbst. Die Umfangsgrenze ist gemessen, nicht
gesetzt: AT trug vor der Korrektur 25.445 von 409.923 Käufer-Zeilen in dieser Form (6,2 %),
CH 497 von 126.108 (0,4 %), LU 10 von 35.369 (0,03 %) — und für LU ist gemessen KEIN
wiederkehrender Hoheitsträger ableitbar. Die Grenze liegt bei 1 %, zwei Größenordnungen über
LU und eine unter AT.

Alles andere ist **Information**: die unerkannten Präfixe werden aufgelistet, damit man sie
ansehen kann, ohne dass der Nachtlauf davon rot wird.

LESEND. Nimmt keine Tageslauf-Sperre, schreibt nicht nach `data/`.

    python3 scripts/pruefe_namensregeln.py [--land DE] [--alle] [--json]

Rückgabe 1, wenn ein unerkannter Präfix über der Schwelle liegt und nicht entschieden ist.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import kennungen, locales, names      # noqa: E402
from govisor.config import Config                  # noqa: E402

# Derselbe Trenner, den `names.resolve_representation` benutzt — keine zweite Fassung, die
# anders altert. Nur die AGENT-Formen („im Namen und auf Rechnung") bleiben aussen vor: dort
# ist der Präfix per Konstruktion die handelnde Stelle, da gibt es nichts zu entscheiden.
TRENNER = names._VERTRETEN


def _laender(cfg: Config) -> tuple[str, ...]:
    """Von der Platte, nicht aus einer Liste (wie `pruefe_verdrahtung._laender`)."""
    w = cfg.silver_dir
    if not w.exists():
        return ()
    return tuple(sorted(p.name for p in w.iterdir()
                        if p.is_dir() and any((p / "notice_parties").glob("*/*.parquet"))))


# Anteil der Käufer-Zeilen in Vertretungsform, ab dem ein Land ohne Hoheitsmuster ein Befund
# ist. Gemessen (s. Modul-Docstring): AT 6,2 % vor der Korrektur, CH 0,4 %, LU 0,03 %.
UMFANG_GRENZE = 0.01


def pruefe_land(cfg: Config, land: str, alle: bool = False) -> tuple[list[str], dict]:
    import duckdb

    if land in locales.LOCALES:
        locales.use(land)
    loc = locales.active()
    con = duckdb.connect(config={"memory_limit": "4GB", "threads": "3"})
    try:
        rows = con.execute(f"""
            SELECT name, count(*) AS n
            FROM '{cfg.silver_table_glob("notice_parties", land)}'
            WHERE role = 'buyer' AND name IS NOT NULL
            GROUP BY 1
        """).fetchall()
    finally:
        con.close()

    kaeufer_zeilen = sum(n for _, n in rows)
    vertretene: dict[str, set[str]] = defaultdict(set)   # Präfix → verschiedene Vertretene
    zeilen: dict[str, int] = defaultdict(int)
    for nm, n in rows:
        if not TRENNER.search(nm or ""):
            continue
        t = TRENNER.split(nm, maxsplit=1)
        pre = re.sub(r"\s+", " ", t[0]).strip()
        koerper = TRENNER.split(t[1], maxsplit=1)[0] if len(t) > 1 else ""
        koerper = re.sub(r"\s+", " ", koerper).strip().lower()
        if not pre:
            continue
        if koerper:
            vertretene[pre.lower()].add(koerper)
        zeilen[pre.lower()] += n

    if not vertretene:
        print(f"── {land} ── keine Vertretungsklausel in der Quelle — nichts zu prüfen")
        return [], {"land": land, "praefixe": 0}

    verteilung = [len(v) for v in vertretene.values()]
    rohe = kennungen.perzentil(verteilung, kennungen.SCHWELLEN_PERZENTIL)
    grenze = max(rohe, kennungen.MINDEST_SCHWELLE)

    erkannt, offen = [], []
    for pre, koerper in vertretene.items():
        if len(koerper) <= grenze:
            continue
        (erkannt if loc.re_sovereign.match(pre) else offen).append(pre)

    klausel_zeilen = sum(zeilen.values())
    anteil = klausel_zeilen / max(kaeufer_zeilen, 1)
    hat_muster = loc.re_sovereign.pattern != r"(?!x)x"

    print(f"── {land} ──")
    print(f"  {len(vertretene):,} Präfixe vor einer Vertretungsklausel · "
          f"{klausel_zeilen:,} von {kaeufer_zeilen:,} Käufer-Zeilen ({anteil:.2%})")
    print(f"  Schwelle {grenze} verschiedene Vertretene (p{kennungen.SCHWELLEN_PERZENTIL:.0%}"
          f"{', Entartungsschutz griff' if grenze > rohe else ''})")
    print(f"  Hoheitsmuster im Profil: {'ja' if hat_muster else 'NEIN'} · "
          f"davon erkannt {len(erkannt)}"
          + (f" ({', '.join(sorted(erkannt)[:3])} …)" if erkannt else ""))

    # ── Information, kein Befund: die unerkannten Präfixe. Das sind ganz überwiegend Stellen
    # mit vielen Abteilungen, bei denen der Präfix bleiben MUSS (s. Modul-Docstring).
    if offen:
        print(f"  ℹ {len(offen)} Präfix(e) über der Schwelle, die das Muster nicht kennt "
              f"— zur Ansicht, nicht als Mangel:")
        for pre in sorted(offen, key=lambda p: -len(vertretene[p]))[:None if alle else 8]:
            print(f"      {len(vertretene[pre]):>4} Vertretene · {zeilen[pre]:>6,} Zeilen  "
                  f"{pre[:72]}")

    befunde = []
    if not hat_muster and anteil > UMFANG_GRENZE:
        befunde.append(
            f"{land}: {klausel_zeilen:,} Käufer-Zeilen ({anteil:.1%}) stehen in der Form "
            f"[X] vertreten durch [Y], aber locales.{land} hat kein Hoheitsmuster. Alle "
            f"Stellen unter demselben [X] tragen damit einen Schlüssel. Muster als Familie in "
            f"govisor/locales.py eintragen (sovereign=), nach Messung der Präfixe oben.")
    return befunde, {
        "land": land, "praefixe": len(vertretene), "klausel_zeilen": klausel_zeilen,
        "kaeufer_zeilen": kaeufer_zeilen, "anteil": round(anteil, 5),
        "schwelle": grenze, "rohe_schwelle": rohe, "erkannt": len(erkannt),
        "unerkannt": len(offen), "hat_muster": hat_muster,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--land", action="append", help="nur dieses Land (mehrfach möglich)")
    ap.add_argument("--alle", action="store_true", help="alle Befunde, nicht nur die ersten 15")
    ap.add_argument("--json", action="store_true", help="Kennzahlen als JSON")
    a = ap.parse_args()

    cfg = Config()
    laender = tuple(a.land) if a.land else _laender(cfg)
    if not laender:
        print("  ⚠ kein Silber mit notice_parties gefunden — nichts zu prüfen")
        return 0

    befunde, zahlen = [], []
    for land in laender:
        b, z = pruefe_land(cfg, land, a.alle)
        befunde += b
        zahlen.append(z)
        print()
    if a.json:
        print(json.dumps(zahlen, indent=2, ensure_ascii=False))
    if befunde:
        print(f"  ⚠ {len(befunde)} Befund(e):")
        for b in befunde:
            print(f"      {b}")
        print("     Die Gebietskörperschaften eines Landes sind eine geschlossene Menge — "
              "ein Bund, die Länder/Kantone/Regionen. Sie gehören als Regex-Familie ins "
              "Profil, nicht als Einzelfälle.")
        print("     Details je Land: python3 scripts/pruefe_namensregeln.py --land <L> --alle")
        return 1
    print("  ✓ jedes Land mit nennenswerter Vertretungsform hat ein Hoheitsmuster")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
