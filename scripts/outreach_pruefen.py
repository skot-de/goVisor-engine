#!/usr/bin/env python3
"""Landings stapelweise prüfen, bevor sie rausgehen.

**Warum es das gibt.** Sven am 2026-08-17: „ich kann und werde nicht bei jedem kunden dabei
sein und vorher gucken was er sehen würde. wir müssen da ein muster schaffen, das immer
funktioniert."

Der Anlass war ein Fehler, der jede technische Prüfung überstanden hatte. Die Seite empfahl
H. Klostermann (Fernmelde- und Stromleitungen für DB Netz) Ausschreibungen von Schulbau
Hamburg und dem Gebäudemanagement Hannover. Alle Zahlen stimmten, alle Tests waren grün,
die CPV-Klasse passte — nur die Arbeit nicht. Gefunden wurde es, weil jemand die Namen
gelesen hat.

**Was dieses Werkzeug NICHT kann.** Es entscheidet nicht, ob eine Landing gut ist. Es
findet die Landings, bei denen ein Mensch hinsehen sollte, und sortiert sie nach Dringlich-
keit. Der Rest darf ungesehen raus. Das ist der Unterschied zwischen „alle prüfen" und
„nichts prüfen", und nur der ist bei wachsender Zahl haltbar.

**Die Prüfungen sind aus echten Fehlern entstanden**, nicht aus einer Checkliste:

  ohne_passung   Ein Baustein verspricht Passung („wo eure Aufträge herkommen könnten"),
                 wurde aber nur über CPV verengt. Genau der Klostermann-Fall.
  fremde_welt    Die empfohlenen Vergabestellen haben eine andere Tätigkeit als die, für
                 die die Firma bisher gearbeitet hat. Maschinell prüfbar, weil beide
                 Verteilungen in den Daten stehen.
  duenn          Weniger als drei belegte Bausteine. Die Seite trägt dann nicht.
  zerschossen    Fliesstext mit Kleinbuchstabe nach Satzpunkt — der Tausendertrenner hat
                 ein Komma erwischt (passiert am 2026-08-17, s. `zahl()`).
  winzig         Eine Verkaufszahl unter der Fühlbarkeitsschwelle. „6 offene
                 Ausschreibungen" ist ehrlich, aber als Aufmacher zu wenig.

Aufruf::

    scripts/outreach_pruefen.py                    # alle erzeugten Landings
    scripts/outreach_pruefen.py --nur-auffaellige
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

G = str(ROOT / "data/gold/DE")
LANDINGS = ROOT / "web" / "data" / "outreach.json"

# Bausteine, die ausdrücklich PASSUNG versprechen und deshalb eine Tätigkeitsstufe
# brauchen. Ein Baustein, der nur zählt („was gerade offen ist"), braucht sie nicht.
VERSPRECHEN_PASSUNG = {"andere_auftraggeber"}

# Unter dieser Zahl trägt eine Verkaufsaussage nicht mehr. Kein Naturgesetz, sondern eine
# gesetzte Grenze — sie steht hier, damit sie diskutierbar ist und nicht im Code versteckt.
FUEHLBAR_AB = 15

_ABKUERZUNG = re.compile(r"\b(z\. ?B|u\. ?a|ca|bzw|inkl|evtl|ggf|Nr|St|Bd)\.")


def _texte(o, pfad=""):
    if isinstance(o, str):
        yield pfad, o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from _texte(v, f"{pfad}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _texte(v, f"{pfad}[{i}]")


def taetigkeitsprofil(con, identity_id: str) -> dict[str, float]:
    """Anteile der Auftraggeber-Tätigkeiten in der Historie der Firma."""
    rows = con.execute(f"""SELECT buyer_activity, count(*) FROM
      read_parquet('{G}/lead_export.parquet')
      WHERE incumbent_group_id = ? AND buyer_activity IS NOT NULL
      GROUP BY 1""", [identity_id]).fetchall()
    ges = sum(n for _, n in rows)
    return {a: n / ges for a, n in rows} if ges else {}


def pruefe(con, token: str, l: dict) -> list[tuple[str, str]]:
    """Alle Befunde zu EINER Landing. Leere Liste heisst: darf ungesehen raus."""
    befunde: list[tuple[str, str]] = []
    nach_id = {b["id"]: b for b in l.get("bausteine") or []}

    if len(nach_id) < 3:
        befunde.append(("duenn", f"nur {len(nach_id)} belegte Bausteine"))

    for bid in VERSPRECHEN_PASSUNG & set(nach_id):
        b = nach_id[bid]
        stufen = {s.get("art") for s in (nach_id.get("offene_im_feld", {}).get("trichter") or [])}
        if "aktivitaet" not in stufen:
            befunde.append(("ohne_passung",
                            f"`{bid}` verspricht Passung, verengt aber nur über CPV/Region"))

    # Der eigentliche Klostermann-Test, maschinell: gleicht die empfohlene Welt der
    # bisherigen? Verglichen wird die praegende Taetigkeit der Historie gegen die der
    # empfohlenen Vergabestellen.
    profil = taetigkeitsprofil(con, l["id"])
    if profil:
        haupt, anteil = max(profil.items(), key=lambda x: x[1])
        for bid in VERSPRECHEN_PASSUNG & set(nach_id):
            namen = nach_id[bid].get("namen") or []
            if not namen or anteil < 0.6:
                continue
            ph = ",".join("?" * len(namen))
            treffer = con.execute(f"""SELECT
                count(*) FILTER (WHERE buyer_activity = ?) , count(*)
              FROM read_parquet('{G}/lead_export.parquet')
              WHERE buyer_name IN ({ph}) AND buyer_activity IS NOT NULL""",
              [haupt] + namen).fetchone()
            if treffer and treffer[1] and treffer[0] / treffer[1] < 0.5:
                befunde.append(("fremde_welt",
                                f"Firma arbeitet zu {anteil:.0%} für `{haupt}`, die empfohlenen "
                                f"Stellen nur zu {treffer[0]/treffer[1]:.0%}"))

    for pfad, t in _texte(l):
        if re.search(r"[a-zäöüß]\. [a-zäöüß]", t) and not _ABKUERZUNG.search(t):
            befunde.append(("zerschossen", f"{pfad}: {t[:70]}"))
            break

    for b in nach_id.values():
        if b.get("gruppe") != "fuer_euch":
            continue
        # Nur die ERSTE Zahl, und nur wenn sie eine reine Anzahl ist.
        #
        # Der erste Anlauf prüfte jede Zahl jedes Bausteins und meldete „bis zu 4 Jahre
        # sucht dieselbe Stelle schon" als zu klein. Das ist eine Dauer, keine Menge —
        # vier Jahre erfolgloses Suchen sind gerade das starke Signal. Ein Prüfer, der
        # Fehlalarme produziert, wird nach der dritten Meldung ignoriert und ist dann
        # schlechter als keiner.
        erste = next(iter(b.get("zahlen") or []), None)
        if not erste:
            continue
        wert = (erste.get("wert") or "").strip()
        if not re.fullmatch(r"[\d.]+", wert):
            continue                      # „bis zu 4 Jahre", „99 %" → keine Anzahl
        if int(wert.replace(".", "")) < FUEHLBAR_AB:
            befunde.append(("winzig", f"`{b['id']}`: {wert} {erste['label'][:44]}"))
    return befunde


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--nur-auffaellige", action="store_true")
    a = ap.parse_args(argv)

    if not LANDINGS.exists():
        print("keine Landings erzeugt", file=sys.stderr)
        return 1
    alle = json.loads(LANDINGS.read_text(encoding="utf-8"))
    con = duckdb.connect()

    sauber, auffaellig = 0, []
    for token, l in alle.items():
        b = pruefe(con, token, l)
        if b:
            auffaellig.append((token, l, b))
        else:
            sauber += 1

    # Nach Schwere sortieren: was eine Empfehlung falsch macht, zuerst.
    rang = {"fremde_welt": 0, "ohne_passung": 1, "zerschossen": 2, "duenn": 3, "winzig": 4}
    auffaellig.sort(key=lambda x: min(rang.get(k, 9) for k, _ in x[2]))

    print(f"\n  {len(alle)} Landings · {sauber} ohne Befund · {len(auffaellig)} zum Ansehen\n")
    for token, l, befunde in auffaellig:
        print(f"  /t/{token}  {l['name'][:52]}")
        for art, text in befunde:
            print(f"      [{art}] {text[:96]}")
    if not auffaellig:
        print("  ✓ nichts, was ein Mensch ansehen müsste.")
    elif not a.nur_auffaellige:
        print(f"\n  Die übrigen {sauber} dürfen ungesehen raus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
