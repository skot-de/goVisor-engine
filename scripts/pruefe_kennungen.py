#!/usr/bin/env python3
"""**Kennungswache** — findet NEUE Platzhalter in ``national_id``, statt eine Liste zu pflegen.

⚠ WARUM ES DIESE SONDE GIBT. Am 2026-10-06 trug die Entität ``id:keineAngabe`` im deutschen
Gold 2.198 verschiedene Käufernamen in 1.128 Orten — Universitätsklinikum Aachen, Deutscher
Bundestag, Bremer Bäder, Handelskammer Hamburg, alle als EIN Auftraggeber. Die Regel dagegen
steht in ``govisor/kennungen.py`` und verwirft, was eindeutig ist.

**Diese Sonde pflegt keine Liste — Listen altern.** Gemessen tragen ``'8477'`` und
``'00002636'`` dieselbe Form wie echte Registernummern, NUTS-Codes (``DE212``, ``DEA2D``) und
eForms-interne Organisations-Referenzen (``ORG-0001``) stehen ebenfalls im Feld. Morgen
erfindet ein Portal den nächsten Platzhalter. Deshalb prüft die Sonde die **Eigenschaft**:
von wie vielen verschiedenen Namen wird eine Kennung geteilt, und gibt es einen Beleg dafür,
dass es dieselbe Stelle ist?

**SIE PRÜFT AUCH IHRE EIGENE BEGRÜNDUNG.** ``kennungen.BELEG_MINDEST`` steht auf 30 %, weil
die gemessene Beleg-Verteilung zweigipfelig ist und 30 % UNTERHALB ihres Tals liegen. Eine
Schwelle, deren Begründung man nicht nachrechnen kann, veraltet still (s. Auto-Memory
`schwelle-aus-der-quelle-ableiten`). Sonde 2 rechnet das Tal aus den aktuellen Daten zurück
und meldet, wenn es auf die Schwelle zuwandert.

**Drei Befunde, drei verschiedene Ursachen:**

1. **Neuer grosser Verdacht** — eine Kennung über der Streuungsgrenze, die einen Beleg hat
   (also nicht automatisch fällt), die niemand entschieden hat, und die genug Zeilen trägt,
   um zu wirken. Die Melde-Grenze dafür wird aus der Zeilen-Verteilung des Verdachtsbandes
   abgeleitet, nicht getippt — sonst wäre sie die nächste alternde Zahl.
2. **Begründung weggewandert** — das Tal der Beleg-Verteilung liegt nicht mehr über
   ``BELEG_MINDEST``. Dann trennt die Schwelle nicht mehr, was sie trennen sollte.
3. **Totes Handurteil** — eine Zeile in ``curated/<L>_kennung_entscheidung.csv``, zu der es
   in den Daten keine Kennung mehr gibt. Genau die Alterung, die diese Sonde vermeiden soll,
   nur in der Entscheidungsdatei.

LESEND. Nimmt keine Tageslauf-Sperre, schreibt nicht nach ``data/``.

    python3 scripts/pruefe_kennungen.py [--land DE] [--alle] [--json]

Rückgabe 1 bei einem der drei Befunde, 0 sonst.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import kennungen                      # noqa: E402
from govisor.config import Config                  # noqa: E402
from govisor.gold import normalize_national_id     # noqa: E402

# ⚠ Perzentil, nicht Konstante. Welche Verdachtsfälle gemeldet werden, hängt davon ab, wie
# gross die Fälle in DIESER Quelle sind: in DE trägt das Verdachtsband Kennungen mit bis zu
# 5.500 Zeilen, in CH mit bis zu 740. Eine getippte Zeilenzahl würde in einem Land alles und
# im anderen nichts melden. Gemeldet wird das obere Zehntel des Bandes.
MELDE_PERZENTIL = 0.90


def _laender(cfg: Config) -> tuple[str, ...]:
    """Welche Länder haben ein Silber mit Parteien? Von der Platte, nicht aus einer Liste —
    dieselbe Haltung wie `pruefe_verdrahtung._laender`. Wer ein Land aufnimmt, muss hier
    nichts eintragen, sonst wäre die Sonde die nächste Liste, die aufhört zu wachsen."""
    wurzel = cfg.silver_dir
    if not wurzel.exists():
        return ()
    return tuple(sorted(
        p.name for p in wurzel.iterdir()
        if p.is_dir() and any((p / "notice_parties").glob("*/*.parquet"))))


def _entscheidungspfade(cfg: Config, land: str) -> list[pathlib.Path]:
    # Repo zuerst (versioniert, trägt die Handarbeit), externe Platte als Rückfall —
    # dieselbe Reihenfolge, die `kennungen.entscheidungen_lesen` dokumentiert.
    return [ROOT / "curated" / f"{land}_kennung_entscheidung.csv",
            cfg.data_dir / "curated" / f"{land}_kennung_entscheidung.csv"]


def messe(cfg: Config, land: str):
    """Streuung für ein Land — über DIESELBE Funktion, die der Gold-Bau anwendet.

    Keine zweite Implementierung: eine Sonde, die anders rechnet als der Bau, meldet
    irgendwann einen Unterschied, der nur ihr eigener ist.
    """
    import duckdb

    con = duckdb.connect(config={"memory_limit": "4GB", "threads": "3"})
    try:
        paare = con.execute(f"""
            SELECT national_id, name, count(*) AS n
            FROM '{cfg.silver_table_glob("notice_parties", land)}'
            WHERE name IS NOT NULL AND national_id IS NOT NULL AND trim(national_id) <> ''
            GROUP BY 1, 2
        """).fetchall()
    finally:
        con.close()
    return kennungen.streuung(paare, schluessel=normalize_national_id)


def _hat_gold(cfg: Config, land: str) -> bool:
    """Trägt das Land eine Gold-Ebene — wirkt die Kennung also im Produkt?

    ⚠ EINE ANGEFANGENE BAUSTELLE IST KEIN AUFGENOMMENES LAND (dieselbe Lehre wie
    `pruefe_verdrahtung._laender`). PL und EU haben Silber, aber bewusst kein Gold; ihre
    Kennungen gemessen zu MELDEN, färbt den Nachtlauf rot für etwas, das heute nichts
    bewirkt. Gemessen und ausgegeben werden sie trotzdem — wer PL auf Gold hebt, hat die
    Zahlen dann schon, und muss hier nichts eintragen.
    """
    g = cfg.gold_dir / land
    return g.is_dir() and any(g.glob("*.parquet"))


def pruefe_land(cfg: Config, land: str, zeige_alle: bool = False) -> tuple[list[str], dict]:
    streu = messe(cfg, land)
    urteile = kennungen.entscheidungen_lesen(_entscheidungspfade(cfg, land),
                                             schluessel=normalize_national_id)
    befunde: list[str] = []

    verdacht = [b for b in streu.befunde if b.urteil == "verdacht"]
    offen = [b for b in verdacht if b.kennung not in urteile]
    grenze = kennungen.perzentil([b.zeilen for b in verdacht], MELDE_PERZENTIL) if verdacht else 0
    gross = [b for b in offen if b.zeilen >= grenze and grenze > 0]

    print(f"── {land} ──")
    print(f"  Schwelle {streu.schwelle} Namen (p{streu.perzentil:.0%} der Quelle"
          f"{', Entartungsschutz griff' if streu.schwelle_gegriffen else ''}), "
          f"{streu.kennungen:,} Kennungen, {streu.zeilen:,} Partei-Zeilen")
    print(f"  verworfen {len(streu.platzhalter):>4} Kennungen / "
          f"{streu.zeilen_von('platzhalter'):>8,} Zeilen  (Beleg < {streu.beleg_mindest:.0%}, "
          f"fallen auf die Namens-Auflösung zurück, kein Verlust)")
    print(f"  tragen    {len(streu.traegt):>4} Kennungen / {streu.zeilen_von('traegt'):>8,} Zeilen"
          f"  (Beleg >= {streu.beleg_sicher:.0%}, echte Dach-Kennungen)")
    print(f"  Verdacht  {len(verdacht):>4} Kennungen / {streu.zeilen_von('verdacht'):>8,} Zeilen"
          f"  — davon {len(offen)} nicht entschieden, Melde-Grenze {grenze:,} Zeilen")

    # ── 1. Neuer grosser Verdacht ────────────────────────────────────────────────────────
    for b in sorted(gross, key=lambda b: -b.zeilen)[:20 if not zeige_alle else len(gross)]:
        # Schlüssel UND Rohwert nennen: der Schlüssel ist, was in die CSV gehört, der
        # Rohwert ist, was man im Portal wiedererkennt. Nur den Rohwert zu drucken kostete
        # beim ersten Lauf sechs Handurteile, die nichts trafen.
        wie = f"{b.kennung}" + (f" (roh {b.roh!r})" if b.roh.strip() != b.kennung else "")
        befunde.append(f"{land}: Kennung {wie} teilt {b.namen} Namen über "
                       f"{b.zeilen:,} Zeilen (Beleg {b.beleg:.0%} über {b.token!r}) "
                       f"— nicht entschieden")
    if gross:
        print(f"  ⚠ {len(gross)} unentschiedene Kennung(en) ab {grenze:,} Zeilen")

    # ── 2. Begründung weggewandert ───────────────────────────────────────────────────────
    tal = kennungen.senke(streu)
    if tal < 0:
        print(f"  Senke der Beleg-Verteilung: zu wenige Befunde ({len(streu.befunde)}) "
              f"für eine Aussage — Schwelle nicht gegenprüfbar")
    else:
        print(f"  Senke der Beleg-Verteilung bei {tal:.0%} — muss ZWISCHEN "
              f"{streu.beleg_mindest:.0%} und {streu.beleg_sicher:.0%} liegen")
        if not (streu.beleg_mindest < tal < streu.beleg_sicher):
            befunde.append(
                f"{land}: Senke der Beleg-Verteilung bei {tal:.0%} liegt nicht mehr zwischen "
                f"BELEG_MINDEST ({streu.beleg_mindest:.0%}) und BELEG_SICHER "
                f"({streu.beleg_sicher:.0%}) — die Grenzen fassen das Tal nicht mehr ein, "
                f"ihre Begründung ist weggefallen, s. govisor/kennungen.py")

    # ── 3. Totes Handurteil ──────────────────────────────────────────────────────────────
    # ⚠ `urteile` trägt jede Zeile unter Rohwert UND Schlüssel. Tot ist eine Entscheidung
    # erst, wenn KEINE ihrer Formen in den Daten vorkommt — sonst meldet die Sonde jede
    # Rohform als Leiche, obwohl sie über den Schlüssel greift.
    gesehen = {b.kennung for b in streu.befunde}
    tot = sorted(k for k in urteile
                 if k not in gesehen and (normalize_national_id(k) or k) not in gesehen)
    if tot:
        print(f"  ⚠ {len(tot)} Handurteil(e) ohne Gegenstück in den Daten")
        for k in tot[:10]:
            befunde.append(f"{land}: Handurteil zu {k!r} ({urteile[k]}) trifft keine Kennung "
                           f"mehr — Zeile aus {land}_kennung_entscheidung.csv entfernen")

    gold = _hat_gold(cfg, land)
    if befunde and not gold:
        print(f"  ℹ {len(befunde)} Zeile(n) nur zur Kenntnis — {land} hat keine Gold-Ebene, "
              f"die Kennung wirkt im Produkt noch nicht")
        for b in befunde:
            print(f"      {b}")
        befunde = []

    return befunde, {
        "land": land, "gold": gold,
        "schwelle": streu.schwelle, "rohe_schwelle": streu.rohe_schwelle,
        "schwelle_gegriffen": streu.schwelle_gegriffen,
        "kennungen": streu.kennungen, "zeilen": streu.zeilen,
        "platzhalter": len(streu.platzhalter),
        "platzhalter_zeilen": streu.zeilen_von("platzhalter"),
        "verdacht": len(verdacht), "verdacht_zeilen": streu.zeilen_von("verdacht"),
        "verdacht_offen": len(offen), "melde_grenze": grenze, "gemeldet": len(gross),
        "senke": tal, "beleg_mindest": streu.beleg_mindest, "tote_urteile": len(tot),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--land", action="append", help="nur dieses Land (mehrfach möglich)")
    ap.add_argument("--alle", action="store_true", help="alle Befunde, nicht nur die ersten 20")
    ap.add_argument("--json", action="store_true", help="Kennzahlen als JSON")
    a = ap.parse_args()

    cfg = Config()
    laender = tuple(a.land) if a.land else _laender(cfg)
    if not laender:
        print("  ⚠ kein Silber mit notice_parties gefunden — nichts zu prüfen")
        return 0

    befunde: list[str] = []
    zahlen = []
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
        print("     Entscheiden: curated/<LAND>_kennung_entscheidung.csv "
              "(kennung,urteil,grund) mit urteil=platzhalter|traegt|offen")
        print("     Hintergrund und Schwellen: govisor/kennungen.py")
        return 1
    print("  ✓ keine unentschiedene Kennung über der Melde-Grenze, "
          "Schwellen-Begründung trägt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
