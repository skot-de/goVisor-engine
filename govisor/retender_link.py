"""Zweitversuch-Kennzeichnung je Lead — „diese Vergabe wurde schon X-mal erfolglos gesucht".

**Warum es das gibt.** `gold.build_retender_signal` findet chronisch erfolglose Bedarfe:
Behörden, die einen Bedarf über mehrere Jahre wiederholt ausgeschrieben haben, ohne dass
ein brauchbares Angebot kam. Das ist das stärkste Einstiegssignal im ganzen Bestand — eine
Vergabestelle, die zum dritten Mal sucht, hat ein Problem und wenig Auswahl.

Nur: das Signal endete bisher **auf CPV-Segment-Ebene**. Man konnte sehen, dass ein
Fachgebiet chronisch klemmt, aber nicht, dass genau DIESE offene Ausschreibung der dritte
Anlauf ist. Genau danach hat Sven am 2026-08-16 gefragt, und die Antwort war: gibt es nicht.

**Wie verknüpft wird — dieselbe Regel wie beim Bauen des Signals.** Ein offener Lead gehört
zu einem chronischen Bedarf, wenn Käufer-Entität und CPV-Klasse übereinstimmen UND die
Titel-Token zu mindestens 55 % überlappen (Jaccard). Die Schwelle ist nicht neu erfunden,
sondern aus `build_retender_signal` übernommen — zwei verschiedene Schwellen für dieselbe
Frage hiessen, dass ein Bedarf beim Bauen zusammengehört und beim Verknüpfen nicht.

**Warum über die Entität und nicht über den Namen.** „Stadt Köln" und „Stadt Köln, Amt für
Gebäudewirtschaft" sind derselbe Käufer und zwei Namen. Das Signal ist über
`entity_id` gebaut; ein Namensvergleich hier würde die Hälfte der Treffer verlieren.
"""
from __future__ import annotations

from pathlib import Path

# Schwelle und Tokenisierung kommen AUS dem Signal-Bauer — nicht nachgebaut, importiert.
from .gold import _succ_tokens

JACCARD_MIN = 0.55


def _paare(con, cfg, gold: Path, country: str) -> tuple[list, list]:
    """(chronische Bedarfe, offene Leads) — beide mit Käufer-Entität und CPV-Klasse."""
    R = (gold / "retender_signal.parquet").as_posix()
    L = (gold / "lead_export.parquet").as_posix()
    # `notice_parties` liegt hive-partitioniert als VERZEICHNIS vor, nicht als eine Datei.
    # Den Pfad selbst zusammenzusetzen ging schief; `silver_table_glob` ist die Stelle,
    # die das im Projekt kennt.
    # Die Zuordnung Beteiligter → ENTITAET steht in Gold, nicht in Silber: `notice_parties`
    # kennt nur Namen, `party_entity` traegt die aufgeloeste `entity_id`. Genau diese Datei
    # benutzt auch `build_retender_signal` — beide Seiten muessen dieselbe Aufloesung sehen.
    PE = (cfg.gold_dir / country / "party_entity.parquet").as_posix()

    bedarfe = con.execute(f"""
        SELECT buyer_entity, cpv_class, need_title, fail_attempts, fail_years,
               first_fail_year, last_fail_year
        FROM read_parquet('{R}')
        WHERE still_open      -- nur Bedarfe, deren letzter Fehlversuch aktuell genug ist
    """).fetchall()

    # Die Käufer-Entität steht nicht im Lead-Export, sondern in den Beteiligten. `arg_min`
    # nimmt den ERSTEN Käufer je Notice — dieselbe Regel wie beim Bauen des Signals, sonst
    # zeigten die beiden Seiten auf verschiedene Entitäten desselben Vorgangs.
    leads = con.execute(f"""
        SELECT l.lead_id, bpe.buyer, substr(l.cpv_code, 1, 4) AS cpv4, l.title
        FROM read_parquet('{L}') l
        JOIN (SELECT notice_id, arg_min(entity_id, seq) buyer
              FROM read_parquet('{PE}') WHERE role='buyer' GROUP BY 1) bpe
          ON bpe.notice_id = l.lead_id
        WHERE l.phase = 'open' AND l.cpv_code IS NOT NULL AND l.title IS NOT NULL
    """).fetchall()
    return bedarfe, leads


def verknuepfe(cfg, country: str = "DE", schreiben: bool = True) -> dict:
    """Chronische Bedarfe → offene Leads. Schreibt ``lead_retender.parquet``.

    Mit ``schreiben=False`` wird nur gemessen — nützlich, solange ein anderer Lauf nach
    `data/` schreibt.
    """
    import duckdb

    gold = cfg.data_dir / "gold" / country
    if not (gold / "retender_signal.parquet").exists():
        print("retender_link: kein retender_signal — erst `gold` laufen lassen.")
        return {}

    con = duckdb.connect()
    con.execute("SET memory_limit='2GB'")
    bedarfe, leads = _paare(con, cfg, gold, country)

    # Nach (Käufer, CPV) gruppieren: nur innerhalb dieser Klammer wird überhaupt verglichen.
    # Ohne sie wären es 3.903 × 90.000 Titelvergleiche statt einiger Tausend.
    nach_schluessel: dict = {}
    for b in bedarfe:
        nach_schluessel.setdefault((b[0], b[1]), []).append((b[2], _succ_tokens(b[2]), b))

    treffer = []
    for lead_id, buyer, cpv4, titel in leads:
        kandidaten = nach_schluessel.get((buyer, cpv4))
        if not kandidaten:
            continue
        tl = _succ_tokens(titel)
        if not tl:
            continue
        bester, bestwert = None, 0.0
        for _, tb, b in kandidaten:
            if not tb:
                continue
            w = len(tl & tb) / len(tl | tb)
            if w > bestwert:
                bester, bestwert = b, w
        if bester and bestwert >= JACCARD_MIN:
            treffer.append({
                "lead_id": lead_id,
                "need_title": bester[2],
                "fail_attempts": int(bester[3]),
                "fail_years": int(bester[4]),
                "first_fail_year": int(bester[5]),
                "last_fail_year": int(bester[6]),
                "aehnlichkeit": round(bestwert, 3),
            })

    ergebnis = {"bedarfe_offen": len(bedarfe), "leads_geprueft": len(leads),
                "verknuepft": len(treffer)}

    if treffer and schreiben:
        import pyarrow as pa
        import pyarrow.parquet as pq
        felder = ["lead_id", "need_title", "fail_attempts", "fail_years",
                  "first_fail_year", "last_fail_year", "aehnlichkeit"]
        pq.write_table(pa.Table.from_pylist([{k: t[k] for k in felder} for t in treffer]),
                       gold / "lead_retender.parquet", compression="zstd")
        ergebnis["geschrieben"] = str(gold / "lead_retender.parquet")

    con.close()
    if treffer:
        v = sorted(treffer, key=lambda t: (-t["fail_years"], -t["fail_attempts"]))[:3]
        for t in v:
            print(f"  {t['fail_years']}× in Folge erfolglos · {t['need_title'][:64]}")
    print(f"retender_link {country}: {len(treffer):,} offene Leads sind ein Zweitversuch "
          f"(von {len(leads):,} offenen, {len(bedarfe):,} chronische Bedarfe)")
    return ergebnis


def main(argv=None) -> int:
    """Aufruf von Hand und aus dem Tageslauf — den es bis zum 2026-08-25 nicht gab.

    ⚠ **Dieses Modul ist NIE GELAUFEN.** Es war vollstaendig gebaut, mit Docstring und
    Begruendung, und wurde von niemandem gerufen: keine CLI, kein Tageslauf, kein Skript.
    `lead_retender.parquet` existierte in KEINEM Land — nicht veraltet, sondern nie
    entstanden. Deshalb konnte auch die Verdrahtungspruefung nichts melden: Sonde 1 misst
    das Alter vorhandener Dateien, und eine Datei, die es nie gab, hat kein Alter.

    Gemessen beim ersten Lauf ueberhaupt (2026-08-25, DE): 2.464 chronische Bedarfe,
    14.470 offene Leads, **11 Verknuepfungen**. Es funktioniert, die Ausbeute ist bei
    JACCARD_MIN = 0.55 aber klein — wer sie heben will, faengt bei der Schwelle an.

    ⚠ **Und es liest immer noch niemand.** Der Erzeuger ist ab heute verdrahtet, der
    Verbraucher fehlt: `lead_retender.parquet` kommt in keiner Frontend-Datei vor. Das ist
    eine Produktentscheidung (`web/`), keine Aufraeumarbeit — sie steht hier als offener
    Punkt, damit sie nicht wieder unsichtbar wird.
    """
    import argparse

    from .config import Config

    ap = argparse.ArgumentParser(description="Zweitversuch-Kennzeichnung je offenem Lead")
    ap.add_argument("--country", default="DE")
    ap.add_argument("--trocken", action="store_true",
                    help="nur messen, nichts schreiben (wenn ein anderer Lauf nach data/ schreibt)")
    a = ap.parse_args(argv)
    verknuepfe(Config(countries=(a.country,)), a.country, schreiben=not a.trocken)
    return 0


if __name__ == "__main__":
    import sys as _sys

    _sys.exit(main())
