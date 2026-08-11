"""Notices, die nicht ins Länder-Silber gehören, nach ``silver/EU`` verschieben.

**Warum.** Weder die TED-Search-API noch die Monatspakete trennen sauber nach Land:
`buyer-country=DEU` und `buyer-country=AUT` liefern teils dieselbe Bekanntmachung. Gemessen
lagen 121 Notices in DE und AT zugleich, 116 davon gehören zu keinem von beiden — EU-
Einrichtungen (Kommission, EBA, EFSA, ECDC, GÉANT) mit Käufersitz in Belgien, den
Niederlanden, Italien, Luxemburg. `normalize.gehoert_zu_land` verhindert das seit 304deef
für KÜNFTIGE Ingests; dieses Skript räumt den Bestand nach.

**Verschieben, nicht löschen.** Es sind echte Vergaben, die wir haben und sonst nirgends
führen — Belgien und die Niederlande ingesten wir nicht. Sie kommen nach ``silver/EU``,
bleiben also abfragbar, verunreinigen aber keine Länder-Kennzahl mehr. Das ist dieselbe
Linie wie „Kein Datenverlust" an allen anderen Stellen.

**Wie erkannt wird — und warum NICHT über `notices.country`.** Diese Spalte trägt das
Land des INGESTS, nicht das des Käufers (`normalize.rows` schreibt dort sein Argument).
Sie stimmt deshalb immer mit dem Ordner überein und taugt nicht als Prüfstein. Maßgeblich
ist allein die Käuferpartei in `notice_parties`: ihr `country`, ersatzweise ihr `nuts`.
Damit spiegelt die Abfrage die Python-Regel, soweit Silber sie hergibt.

Sicherungen, weil hier Bestandsdateien überschrieben werden:
  · Zeilensumme über Quelle und Ziel muss erhalten bleiben — sonst Abbruch je Tabelle.
  · Geschrieben wird über `.part` + `rename` (atomar).
  · `--dry-run` zeigt die vollständige Bilanz, ohne etwas anzufassen.
  · Idempotent: ein zweiter Lauf findet nichts mehr zu verschieben.

Aufruf:  python scripts/migrate_fremde_notices.py [--laender DE,AT,CH] [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import model  # noqa: E402  (Pfad muss zuerst stehen)

SILBER = ROOT / "data" / "silver"
ZIEL = "EU"
# Nur die TED-Generationen. Die nationalen Connectoren (DÖE, simap, atverg) sind per
# Bauart einländrig — sie hier mitzuprüfen brächte nichts und riskierte Fehlalarme.
TED_GEN = "('legacy','eforms','text','ojs')"


def fremde_ids(con, land: str) -> set[str]:
    """notice_ids im Silber von ``land``, deren Käufer nachweislich woanders sitzt."""
    N = f"read_parquet('{(SILBER/land/'notices').as_posix()}/*/*.parquet', hive_partitioning=1)"
    P = f"read_parquet('{(SILBER/land/'notice_parties').as_posix()}/*/*.parquet', hive_partitioning=1)"
    try:
        rows = con.execute(f"""
            WITH k AS (
                SELECT p.notice_id,
                       list(DISTINCT p.country) FILTER (WHERE p.country IS NOT NULL) AS laender,
                       list(DISTINCT p.nuts)    FILTER (WHERE p.nuts    IS NOT NULL) AS nutse
                FROM {P} p
                JOIN (SELECT notice_id FROM {N} WHERE schema_gen IN {TED_GEN}) n USING(notice_id)
                WHERE lower(p.role) = 'buyer'
                GROUP BY 1)
            SELECT notice_id FROM k
            WHERE CASE
                    -- Käuferland bekannt → es entscheidet.
                    WHEN len(coalesce(laender, [])) > 0 THEN NOT list_contains(laender, '{land}')
                    -- sonst die Sitz-NUTS.
                    WHEN len(coalesce(nutse, [])) > 0
                      THEN NOT list_bool_or(list_transform(nutse, x -> starts_with(x, '{land}')))
                    -- nichts bekannt → behalten, kein stiller Verlust.
                    ELSE FALSE
                  END""").fetchall()
    except duckdb.IOException:
        return set()
    return {r[0] for r in rows}


def ziel_land(con, land: str, ids: set[str], gepflegt: set[str]) -> dict[str, str]:
    """Wohin gehört jede Notice wirklich? notice_id → Zielordner.

    ``EU`` ist der Auffangtopf, NICHT die Standardantwort. Wenn das Käuferland eines der
    von uns gepflegten ist, gehört die Notice dorthin — sonst wandert eine deutsche
    Vergabe, die nur im AT-Silber lag, fälschlich in den EU-Topf statt nach DE. Genau das
    ist beim ersten Lauf zweimal passiert (DB Netz AG 361392_2018 aus dem AT-Silber,
    Republik Österreich 240654_2019 aus dem DE-Silber).
    """
    P = f"read_parquet('{(SILBER/land/'notice_parties').as_posix()}/*/*.parquet', hive_partitioning=1)"
    liste = ",".join(f"'{i}'" for i in sorted(ids))
    rows = con.execute(f"""
        SELECT notice_id, any_value(country) AS l FROM {P}
        WHERE lower(role)='buyer' AND notice_id IN ({liste}) GROUP BY 1""").fetchall()
    echt = {nid: (l or "").upper() for nid, l in rows}
    return {nid: (echt.get(nid) if echt.get(nid) in gepflegt else ZIEL) for nid in ids}


def verschiebe(con, land: str, ids: set[str], dry: bool, ziele: dict[str, str] | None = None
               ) -> tuple[int, int]:
    """Alle Zeilen dieser notice_ids aus ``land`` in ihren Zielordner umhängen."""
    ziele = ziele or {i: ZIEL for i in ids}
    nach = {}
    for i in ids:
        nach.setdefault(ziele[i], set()).add(i)
    bewegt = dateien = 0
    for zielordner, teilmenge in sorted(nach.items()):
      liste = ",".join(f"'{i}'" for i in sorted(teilmenge))
      for tabelle in model.TABLES:
          for quelle in sorted((SILBER / land / tabelle).glob("*/*.parquet")):
              q = quelle.as_posix()
              n_ges = con.execute(f"SELECT count(*) FROM read_parquet('{q}')").fetchone()[0]
              n_weg = con.execute(
                  f"SELECT count(*) FROM read_parquet('{q}') WHERE notice_id IN ({liste})").fetchone()[0]
              if not n_weg:
                  continue
              bewegt += n_weg
              dateien += 1
              if dry:
                  continue

              ziel = SILBER / zielordner / tabelle / quelle.parent.name / quelle.name
              ziel.parent.mkdir(parents=True, exist_ok=True)
              # Ziel kann schon Zeilen aus einem anderen Quellland tragen (dieselbe Notice
              # lag in DE UND AT) — dann wird vereinigt und je notice_id einmal behalten.
              vorhanden = (f"SELECT * FROM read_parquet('{ziel.as_posix()}') "
                           f"UNION ALL BY NAME ") if ziel.exists() else ""
              tmp_z = ziel.with_suffix(".part")
              con.execute(f"""COPY (
                  SELECT * FROM ({vorhanden}
                      SELECT * FROM read_parquet('{q}') WHERE notice_id IN ({liste}))
              ) TO '{tmp_z.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)""")

              tmp_q = quelle.with_suffix(".part")
              con.execute(f"""COPY (
                  SELECT * FROM read_parquet('{q}') WHERE notice_id NOT IN ({liste})
              ) TO '{tmp_q.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)""")

              n_rest = con.execute(f"SELECT count(*) FROM read_parquet('{tmp_q.as_posix()}')").fetchone()[0]
              if n_rest != n_ges - n_weg:
                  tmp_q.unlink(missing_ok=True)
                  tmp_z.unlink(missing_ok=True)
                  raise SystemExit(f"ABBRUCH {quelle}: {n_rest} statt {n_ges - n_weg} Restzeilen")
              tmp_z.replace(ziel)        # erst das Ziel sichern …
              tmp_q.replace(quelle)      # … dann die Quelle kürzen
    return bewegt, dateien


def main(laender: list[str], dry: bool) -> int:
    con = duckdb.connect()
    gesamt_ids = gesamt_zeilen = 0
    for land in laender:
        ids = fremde_ids(con, land)
        if not ids:
            print(f"{land}: nichts zu verschieben.")
            continue
        # Herkunft der Fremdkörper zeigen — die Zahl allein sagt nicht, ob die Regel stimmt.
        P = f"read_parquet('{(SILBER/land/'notice_parties').as_posix()}/*/*.parquet', hive_partitioning=1)"
        liste = ",".join(f"'{i}'" for i in sorted(ids))
        herkunft = con.execute(f"""
            SELECT any_value(country) AS l, count(*) n FROM (
                SELECT notice_id, any_value(country) AS country FROM {P}
                WHERE lower(role)='buyer' AND notice_id IN ({liste}) GROUP BY 1)
            GROUP BY country ORDER BY n DESC LIMIT 8""").fetchall()
        print(f"{land}: {len(ids):,} Notices gehören woanders hin — "
              + ", ".join(f"{l or '?'}:{n}" for l, n in herkunft))
        ziele = ziel_land(con, land, ids, {'DE', 'AT', 'CH'})
        bewegt, dateien = verschiebe(con, land, ids, dry, ziele)
        aufteilung = ", ".join(f"{z}:{len([1 for v in ziele.values() if v == z])}"
                               for z in sorted(set(ziele.values())))
        print(f"   {bewegt:,} Zeilen über {dateien} Dateien → {aufteilung}"
              + (" (dry-run)" if dry else ""))
        gesamt_ids += len(ids)
        gesamt_zeilen += bewegt
    print(f"\nSumme: {gesamt_ids:,} Notices, {gesamt_zeilen:,} Zeilen"
          + (" — dry-run" if dry else f" nach silver/{ZIEL} verschoben"))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--laender", default="DE,AT,CH")
    ap.add_argument("--dry-run", dest="dry", action="store_true")
    a = ap.parse_args()
    sys.exit(main([x.strip() for x in a.laender.split(",") if x.strip()], a.dry))
