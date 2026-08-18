#!/usr/bin/env python3
"""Die LLM-Urteile gegen die Daten prüfen — ohne ein weiteres Modell zu fragen.

**Warum diese Prüfung zuerst kommt.** Die Urteile stammen von zwei Anbietern, die im
Nachhinein betrachtet dasselbe Modell fahren (Together und SambaNova liefern beide
Llama-3.3-70B). Zwei Instanzen desselben Modells irren gleich; die gemessenen 88 %
Übereinstimmung sind deshalb schwächer, als sie klingen. Bevor also 4.304 Zusammenführungen
in `gold` wandern, prüfen die Daten selbst, was das Modell behauptet hat.

**Drei Widersprüche, die eine Zusammenführung ausschliessen:**

1. **Getrennte Orte.** Beide Seiten nennen Städte, und keine kommt doppelt vor.

   ⚠️ Die erste Fassung verglich POSTLEITZAHLEN und meldete 373 Widersprüche. Die Stichprobe
   zeigte, dass fast alle davon falsch waren: „Deutsche Post InHaus Service, Bonn 53121"
   gegen „Deutsche Post Inhaus Service, Bonn 53113" ist dieselbe Firma mit zwei Anschriften,
   ebenso LWL Münster 48145/48147 und Rocket Lab Toronto M5V 2M5/M5V 1G1. Grosse
   Organisationen haben mehrere Postleitzahlen, oft eine je Gebäude oder Postfach; das ist
   der Normalfall, nicht der Widerspruch. Verglichen wird deshalb die Stadt.

   Ein Fund nebenbei: in mindestens einem Datensatz stehen Ort und PLZ vertauscht
   („Wasserstrassen- und Schifffahrtsamt, Ort=56070, PLZ=Koblenz"). Rein numerische
   Ortsangaben zählen deshalb nicht als Beleg.
2. **Gleicher Vorgang, verschiedene Partei.** Stehen beide Seiten in derselben Bekanntmachung
   als unterschiedliche Beteiligte, können sie nicht dieselbe Organisation sein — ein
   Auftraggeber schreibt nicht an sich selbst aus, und zwei Bieter sind zwei Bieter.
3. **Widersprüchliche amtliche Kennungen.** Zwei verschiedene Handelsregisternummern sind
   zwei Rechtsträger. (USt-IDs schliessen einander NICHT aus: Organschaften teilen sie sich.)

Die Prüfung ist bewusst konservativ: sie sagt nur, wann eine Zusammenführung **falsch** wäre,
nie, wann sie richtig ist. Ein Urteil ohne Widerspruch ist damit nicht bestätigt, sondern nur
nicht widerlegt.

Aufruf::  scripts/entity_urteil_pruefen.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
G = ROOT / "data/gold/DE"
SILBER = ROOT / "data/silver/DE/notice_parties"


def main() -> int:
    import duckdb
    import pandas as pd

    urteile = pd.read_parquet(G / "entity_merge_urteil.parquet")
    zusammen = urteile[urteile.urteil.isin(["gleich", "alle_gleich"])].copy()
    print(f"  {len(zusammen):,} Urteile würden zusammenführen "
          f"({(urteile.urteil == 'alle_gleich').sum():,} alle_gleich, "
          f"{(urteile.urteil == 'gleich').sum():,} gleich)")

    con = duckdb.connect()
    con.register("u", zusammen[["entity_a", "entity_b", "urteil"]])
    pe = (G / "party_entity.parquet").as_posix()
    np_ = f"{SILBER.as_posix()}/**/*.parquet"
    ent = (G / "entities.parquet").as_posix()

    # Städte je Entität, kleingeschrieben und ohne Zierrat. Rein numerische Werte fliegen
    # raus — dort stand die PLZ im Ortsfeld.
    con.execute(f"""CREATE TEMP TABLE ort AS
        SELECT pe.entity_id,
               list(DISTINCT lower(regexp_replace(p.town, '[^A-Za-zÄÖÜäöüß]', '', 'g'))) AS orte
        FROM '{pe}' pe JOIN '{np_}' p
          ON p.notice_id = pe.notice_id AND p.role = pe.role AND p.seq = pe.seq
        WHERE p.town IS NOT NULL
          AND regexp_replace(p.town, '[^A-Za-zÄÖÜäöüß]', '', 'g') <> ''
        GROUP BY 1""")

    # ⚠ Die B-Seite ist bei `mehrdeutige_id` eine Liste, mit Semikolon verbunden. Ohne das
    # Auftrennen prüfte man gegen eine Zeichenkette, die keine Entität ist — derselbe Fehler,
    # der den ersten Schiedslauf wertlos machte.
    con.execute("""CREATE TEMP TABLE paare AS
        SELECT entity_a, unnest(str_split(entity_b, ';')) AS entity_b, urteil FROM u""")

    getrennte_orte = con.execute("""
        SELECT count(DISTINCT (pa.entity_a || '|' || pa.entity_b)) FROM paare pa
        JOIN ort a ON a.entity_id = pa.entity_a
        JOIN ort b ON b.entity_id = pa.entity_b
        -- ⚠ NICHT auf Gleichheit prüfen, auf ENTHALTENSEIN. Auch die Stadtregel war in der
        -- ersten Fassung zu streng: „müllheim" gegen „müllheimimmarkgräflerland",
        -- „fellbach" gegen „fellbachschmiden", „sanjose" gegen „sanjosecalifornia" — jedes
        -- Mal derselbe Ort in längerer Schreibweise, jedes Mal als Widerspruch gemeldet.
        -- Ein Widerspruch liegt erst vor, wenn KEIN Ortsname der einen Seite in einem der
        -- anderen steckt (und umgekehrt).
        WHERE NOT EXISTS (
            SELECT 1 FROM unnest(a.orte) AS t(x), unnest(b.orte) AS u(y)
            WHERE x = y OR contains(x, y) OR contains(y, x))""").fetchone()[0]

    gleicher_vorgang = con.execute(f"""
        SELECT count(DISTINCT (pa.entity_a || '|' || pa.entity_b)) FROM paare pa
        JOIN '{pe}' x ON x.entity_id = pa.entity_a
        JOIN '{pe}' y ON y.entity_id = pa.entity_b
        WHERE x.notice_id = y.notice_id AND (x.role, x.seq) <> (y.role, y.seq)""").fetchone()[0]

    hr = con.execute(f"""
        SELECT count(DISTINCT (pa.entity_a || '|' || pa.entity_b)) FROM paare pa
        JOIN '{ent}' a ON a.entity_id = pa.entity_a
        JOIN '{ent}' b ON b.entity_id = pa.entity_b
        WHERE a.national_id IS NOT NULL AND b.national_id IS NOT NULL
          AND lower(a.national_id) LIKE '%hr%' AND lower(b.national_id) LIKE '%hr%'
          AND a.national_id <> b.national_id""").fetchone()[0]

    gesamt = con.execute("SELECT count(*) FROM paare").fetchone()[0]
    print(f"\n  Geprüfte Entitäts-Beziehungen: {gesamt:,}")
    print(f"    getrennte Städte (keine gemeinsam)        {getrennte_orte:>6,}")
    print(f"    gleicher Vorgang, verschiedene Partei     {gleicher_vorgang:>6,}")
    print(f"    zwei verschiedene Handelsregisternummern  {hr:>6,}")
    print("\n  Ein Urteil ohne Widerspruch ist NICHT bestätigt, nur nicht widerlegt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
