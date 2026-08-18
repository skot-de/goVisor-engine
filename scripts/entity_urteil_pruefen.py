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
2. **Gleicher Vorgang, verschiedene Partei — aber nur bei bestimmten Rollen.**

   ⚠️ Die erste Fassung meldete 35 Fälle und lag bei fast allen daneben. Der Blick in die
   Rollen erklärte warum:

   * `review`/`buyer` und `mediation`/`buyer`: dieselbe Behörde ist Auftraggeber UND die
     benannte Nachprüfungs- oder Schlichtungsstelle. Steht so in jeder zweiten
     Bundes-Bekanntmachung (Bundeswehr-Dienstleistungszentrum Kiel, Regierungspräsidium
     Karlsruhe, WWU Münster) und ist der Normalfall.
   * `winner`/`winner`: dieselbe Firma gewinnt mehrere LOSE desselben Verfahrens und steht
     deshalb mehrfach in der Bekanntmachung.

   Ein echter Widerspruch bleibt nur `buyer`/`winner`: wer ausschreibt, gewinnt normalerweise
   nicht selbst. Auch das gibt es (Inhouse-Vergabe an die eigene Tochter), es ist aber selten
   genug, um es anzusehen statt es durchzuwinken.
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
sys.path.insert(0, str(ROOT))
from govisor.adressen import sql_ort  # noqa: E402

# EINE Regel für vertauschte Adressfelder, nicht drei Fassungen in drei Skripten.
# Gefunden beim Prüfen der Zusammenführungen: „Ort=56070, PLZ=Koblenz". Wer das für bare
# Münze nimmt, meldet einen Ortswiderspruch, wo keiner ist.
ORT = sql_ort("p.town", "p.postal_code")
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
               list(DISTINCT lower(regexp_replace({ORT}, '[^A-Za-zÄÖÜäöüß]', '', 'g'))) AS orte
        FROM '{pe}' pe JOIN '{np_}' p
          ON p.notice_id = pe.notice_id AND p.role = pe.role AND p.seq = pe.seq
        WHERE {ORT} IS NOT NULL
          AND regexp_replace({ORT}, '[^A-Za-zÄÖÜäöüß]', '', 'g') <> ''
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
        -- ⚠ DRITTE KORREKTUR DERSELBEN REGEL. Nach PLZ (373 Fehlalarme) und exakter
        -- Stadtgleichheit (270) blieben 97 — und die Impressum-Gegenprobe zeigte, dass auch
        -- davon die meisten TIPPFEHLER der Quelle sind: „lipppstadt", „kalrsruhe",
        -- „erfirt", „garcching", dazu „luxembourg"/„luxemburg" als Sprachvariante. Das
        -- Impressum der jeweiligen Firma nennt die richtige Schreibweise; die Modelle hatten
        -- recht, die Regel hatte unrecht.
        --
        -- Levenshtein <= 2 faengt genau diese Sorte ab. Weiter aufmachen sollte man nicht:
        -- „Neustadt" und „Neustadt an der Weinstrasse" trennt mehr als ein Buchstabendreher,
        -- und das faengt bereits `contains`.
        WHERE NOT EXISTS (
            SELECT 1 FROM unnest(a.orte) AS t(x), unnest(b.orte) AS u(y)
            WHERE x = y OR contains(x, y) OR contains(y, x)
               OR levenshtein(x, y) <= 2)""").fetchone()[0]

    gleicher_vorgang = con.execute(f"""
        SELECT count(DISTINCT (pa.entity_a || '|' || pa.entity_b)) FROM paare pa
        JOIN '{pe}' x ON x.entity_id = pa.entity_a
        JOIN '{pe}' y ON y.entity_id = pa.entity_b
        WHERE x.notice_id = y.notice_id AND (x.role, x.seq) <> (y.role, y.seq)
          -- Nur die Kombination, die wirklich erklaerungsbeduerftig ist (s. oben).
          AND ((x.role = 'buyer' AND y.role = 'winner')
            OR (x.role = 'winner' AND y.role = 'buyer'))""").fetchone()[0]

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
    print(f"    Auftraggeber UND Gewinner im selben Vorgang{gleicher_vorgang:>6,}")
    print(f"    zwei verschiedene Handelsregisternummern  {hr:>6,}")
    print("\n  Ein Urteil ohne Widerspruch ist NICHT bestätigt, nur nicht widerlegt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
