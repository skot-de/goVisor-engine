#!/usr/bin/env python3
"""Sondierung ist kein Onboarding — und das wird hier maschinell festgehalten.

Ein sondiertes Land ist ANGESEHEN, nicht angebunden. Wir wissen, welche Portale es dort
gibt und ob eine Schranke davorsteht. Wir haben keine Zeile seiner Daten.

⚠ WARUM ES DIESE DATEI GIBT. Beim Bau der Vorgangs-Tabellen wurde nebenbei auch fuer PL
und EU geschrieben. Damit galten beide schlagartig als aufgenommene Laender, und die
Paritaetssonde meldete 40 bestehende Tabellen als Luecke. Niemand hatte Polen aufgenommen;
es sah nur so aus. Bei einer EU-weiten Sondierung droht derselbe Fehler dreissigmal.

Ein Etikett allein reicht dafuer nicht — genau ein Etikett war es, das bei Polen versagt
hat. Deshalb pruefen die vier Regeln unten den ZUSTAND AUF DER PLATTE gegen die Registry,
nicht die Absicht.

Aufruf:  python3 scripts/pruefe_sondierung.py          (0 = sauber, 1 = Befunde)
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor import sources                                          # noqa: E402

SONDIERT = "sondiert"
# Diese Verzeichnisse bedeuten „aufgenommen". Taucht ein sondiertes Land darin auf, ist
# entweder der Status falsch oder es wurde geschrieben, wo nicht geschrieben werden darf.
AUFNAHME_PFADE = ("data/gold", "data/silver")
# Das Onboarding-Handbuch. Es beschreibt, WIE ein Land aufgenommen wird — ein sondiertes
# Land hat hier nichts zu suchen, auch nicht als Kapitel „zur Vorbereitung".
HANDBUCH = "docs/laender"
# Wohin die Sondierung stattdessen schreibt.
SONDIERUNG_DATEN = "data/sondierung"
SONDIERUNG_PAPIERE = "docs/sondierung"


def _hat_tabellen(land: str) -> list[str]:
    """Verzeichnisse, in denen dieses Land Tabellen liegen hat."""
    treffer = []
    for rel in AUFNAHME_PFADE:
        d = ROOT / rel / land
        if d.is_dir() and any(d.glob("**/*.parquet")):
            treffer.append(f"{rel}/{land}")
    return treffer


def befunde() -> list[str]:
    """Leere Liste = die Trennung haelt."""
    raus: list[str] = []
    sondierte = {s.country for s in sources.REGISTRY if s.status == SONDIERT}

    # 1 · Ein sondiertes Land darf keine Tabellen haben.
    for land in sorted(sondierte):
        for pfad in _hat_tabellen(land):
            raus.append(
                f"{land} steht auf '{SONDIERT}', hat aber Tabellen in {pfad} — "
                f"entweder ist das Land laengst aufgenommen (dann Status heben) oder es "
                f"wurde geschrieben, wo die Sondierung nicht schreiben darf "
                f"(dann nach {SONDIERUNG_DATEN}/{land} verschieben). Das ist der Polen-Fall.")

    # 2 · Ein sondierter Eintrag hat keinen Konnektor. Ein Befund ist kein Anschluss.
    for s in sources.REGISTRY:
        if s.status == SONDIERT and s.connector:
            raus.append(
                f"{s.id} steht auf '{SONDIERT}', traegt aber den Konnektor "
                f"'{s.connector}' — wer anbindet, hebt den Status. In dieser Reihenfolge.")

    # 3 · Kein sondiertes Land im Onboarding-Handbuch.
    hb = ROOT / HANDBUCH
    if hb.is_dir():
        for datei in sorted(hb.glob("*.md")):
            stamm = datei.stem.lower()
            for land in sorted(sondierte):
                # Laendercode als eigenes Wort im Dateinamen, nicht als Silbe:
                # `12-fallenkatalog` darf nicht wegen „AT" in „katalog" anschlagen.
                if land.lower() in stamm.replace("-", " ").replace("_", " ").split():
                    raus.append(
                        f"{HANDBUCH}/{datei.name} fuehrt das sondierte Land {land} — "
                        f"das Handbuch gehoert den aufgenommenen Laendern. "
                        f"Sondierungen nach {SONDIERUNG_PAPIERE}/.")

    # 5 · `ertrag="ungeprueft"` ist die Kennzeichnung der Sondierung — sie darf nirgends
    #     sonst stehen. Sonst versteckt sich eine angebundene Quelle hinter einem Wort,
    #     das „nie gemessen" bedeutet, und die Ertragstabelle mischt Befund und Vermutung.
    for s in sources.REGISTRY:
        if s.ertrag == "ungeprueft" and s.status != SONDIERT:
            raus.append(
                f"{s.id} traegt ertrag='ungeprueft', steht aber auf '{s.status}' — "
                f"'ungeprueft' gehoert allein der Sondierung.")

    # 4 · Die Umkehrung, und sie ist die wichtigere: ein Land MIT Tabellen darf nicht als
    #     sondiert gefuehrt werden. Regel 1 sieht es aus Sicht der Registry, Regel 4 aus
    #     Sicht der Platte — bei Polen war die Platte schneller als die Registry.
    for rel in AUFNAHME_PFADE:
        d = ROOT / rel
        if not d.is_dir():
            continue
        for land_dir in sorted(x for x in d.iterdir() if x.is_dir()):
            land = land_dir.name
            if land not in sondierte:
                continue
            eintraege = [s.id for s in sources.REGISTRY
                         if s.country == land and s.status != SONDIERT]
            if not eintraege:
                raus.append(
                    f"{rel}/{land} existiert, aber {land} wird ausschliesslich als "
                    f"'{SONDIERT}' gefuehrt — dann ist die Registry hinter der Wirklichkeit "
                    f"her, genau wie bei Polen.")
    return sorted(set(raus))


def main() -> int:
    b = befunde()
    n = sum(1 for s in sources.REGISTRY if s.status == SONDIERT)
    laender = sorted({s.country for s in sources.REGISTRY if s.status == SONDIERT})
    print(f"── Sondierung gegen Aufnahme ── {n} Eintraege, "
          f"{len(laender)} Laender{': ' + ', '.join(laender) if laender else ''}")
    if not b:
        print("  ✓ Trennung haelt")
        return 0
    for z in b:
        print(f"  ⛔ {z}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
