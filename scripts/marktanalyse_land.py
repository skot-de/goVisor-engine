#!/usr/bin/env python3
"""Marktanalyse für EIN Land — Volumen, Portale, potenzielle Kunden.

Beantwortet vor dem Markteintritt die drei Fragen, die zählen: **wie viel wird dort
ausgeschrieben, über welche Plattformen läuft es, und wie viele Unternehmen kämen als
zahlende Kunden in Frage.**

Bewusst länderunabhängig gebaut. Der Anlass war Polen, aber ein Skript, das nur PL kann,
wäre nach dem Projektgrundsatz („jede Funktion gilt für ALLE Länder") nicht fertig, sondern
angefangen. Es läuft gegen jedes Land, für das Silber existiert.

**Was es braucht:** Silber (`data/silver/<LAND>/`). Gold ist optional — liegt es vor,
kommt die Kundenzahl auf Konzernebene, sonst über normalisierte Namen mit ausgewiesener
Unschärfe.

**Was es NICHT tut:** Zahlungsbereitschaft schätzen. Es misst Marktgrösse, nicht Umsatz.

Aufruf:
    python3 scripts/marktanalyse_land.py --land PL
    python3 scripts/marktanalyse_land.py --land PL --monate 36
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _hat_silber(land: str) -> bool:
    return (ROOT / "data" / "silver" / land / "notices").exists()


def _n(x) -> str:
    return f"{x:,}".replace(",", ".") if x is not None else "—"


def analyse(con, land: str, monate: int) -> list[str]:
    N = f"read_parquet('{ROOT}/data/silver/{land}/notices/**/*.parquet', hive_partitioning=1)"
    P = f"read_parquet('{ROOT}/data/silver/{land}/notice_parties/**/*.parquet', hive_partitioning=1)"
    fenster = f"coalesce(award_date, publication_date) >= current_date - INTERVAL '{monate} months'"
    z = [f"## {land}", ""]

    # 1) Bestand und Kadenz
    r = con.execute(f"""SELECT count(*), min(publication_date), max(publication_date),
                               count(*) FILTER (WHERE {fenster})
                        FROM {N}""").fetchone()
    z += ["### Bestand", "",
          f"- **{_n(r[0])} Bekanntmachungen** im Silber, {r[1]} bis {r[2]}",
          f"- davon **{_n(r[3])}** in den letzten {monate} Monaten", ""]
    z += ["| Art | Anzahl (Fenster) |", "|---|---:|"]
    for art, n in con.execute(f"""SELECT notice_kind, count(*) FROM {N} WHERE {fenster}
                                  GROUP BY 1 ORDER BY 2 DESC LIMIT 8""").fetchall():
        z.append(f"| {art or '(ohne)'} | {_n(n)} |")
    z += [""]
    z += ["| Jahr | Bekanntmachungen |", "|---|---:|"]
    for j, n in con.execute(f"""SELECT year(publication_date), count(*) FROM {N}
                                WHERE publication_date IS NOT NULL AND {fenster}
                                GROUP BY 1 ORDER BY 1""").fetchall():
        z.append(f"| {j} | {_n(n)} |")
    z += [""]

    # 2) Offene Ausschreibungen — das, was ein Produkt am Tag 1 anzeigen könnte
    r = con.execute(f"""SELECT count(*),
             count(*) FILTER (WHERE portal_url IS NOT NULL AND portal_url <> '')
           FROM {N}
           WHERE notice_kind IN ('cn','pin') AND submission_deadline > current_date""").fetchone()
    z += ["### Offene Ausschreibungen (Frist in der Zukunft)", "",
          f"- **{_n(r[0])}** offen · davon **{_n(r[1])}** mit Portal-Adresse", ""]

    # 3) Portallandschaft — die eigentliche Eintrittsfrage
    z += ["### Portallandschaft", "",
          "Aus `portal_url` der Bekanntmachungen im Fenster. Wo TED keine Adresse führt, "
          "steht `(ohne)` — das ist selbst eine Aussage über die Erreichbarkeit.", "",
          "| Portal (Host) | Bekanntmachungen | Anteil |", "|---|---:|---:|"]
    ges = con.execute(f"SELECT count(*) FROM {N} WHERE {fenster}").fetchone()[0] or 1
    for host, n in con.execute(f"""
            SELECT coalesce(nullif(regexp_extract(portal_url, '://([^/]+)', 1), ''), '(ohne)'),
                   count(*)
            FROM {N} WHERE {fenster} GROUP BY 1 ORDER BY 2 DESC LIMIT 15""").fetchall():
        z.append(f"| `{host}` | {_n(n)} | {100*n/ges:.1f} % |")
    z += [""]

    # 4) Käufer
    r = con.execute(f"""SELECT count(DISTINCT p.name)
           FROM {P} p JOIN {N} n USING(notice_id)
           WHERE p.role='buyer' AND {fenster.replace('award_date','n.award_date').replace('publication_date','n.publication_date')}""").fetchone()
    z += ["### Auftraggeber", "", f"- **{_n(r[0])}** verschiedene Vergabestellen im Fenster",
          "  (über Namen gezählt — ohne Entity-Auflösung ist das eine Obergrenze)", ""]

    # 5) Potenzielle Kunden: Gewinner mit Mindestaktivität
    z += ["### Potenzielle Kunden", ""]
    gold = ROOT / "data" / "gold" / land / "entity_identity.parquet"
    if gold.exists():
        I = f"'{gold}'"
        PE = f"'{ROOT}/data/gold/{land}/party_entity.parquet'"
        E = f"'{ROOT}/data/gold/{land}/entities.parquet'"
        r = con.execute(f"""
          WITH g AS (SELECT DISTINCT pe.notice_id, i.identity_id, e.confidence
                     FROM {PE} pe JOIN {I} i USING(entity_id) JOIN {E} e USING(entity_id)
                     WHERE pe.role='winner')
          SELECT count(DISTINCT identity_id),
                 count(DISTINCT identity_id) FILTER (WHERE confidence >= 0.9)
          FROM g JOIN {N} n USING(notice_id) WHERE n.notice_kind='can' AND {fenster}
        """).fetchone()
        z += [f"- **{_n(r[0])}** Auftragnehmer auf Konzernebene (Entity-Auflösung)",
              f"- davon **{_n(r[1])}** register-/ID-gestützt — die belastbare Grundgesamtheit", ""]
    else:
        r = con.execute(f"""
          SELECT count(DISTINCT lower(trim(p.name)))
          FROM {P} p JOIN {N} n USING(notice_id)
          WHERE p.role='winner' AND n.notice_kind='can' AND {fenster}""").fetchone()
        z += [f"- **{_n(r[0])}** Auftragnehmer über normalisierte Namen",
              "  ⚠ **ohne Gold-Schicht** — keine Entity-Auflösung, keine Konzernebene. Die Zahl",
              "  ist eine **Obergrenze**: Schreibvarianten derselben Firma zählen mehrfach. In DE",
              "  senkte die Auflösung samt Filtern die Zahl um rund zwei Drittel.", ""]

    # 6) Wert und Währung — die Falle, die uns in CH erwischt hat
    r = con.execute(f"""SELECT count(*), count(final_value),
             count(*) FILTER (WHERE upper(coalesce(value_currency,'')) NOT IN ('EUR','')
                                AND final_value IS NOT NULL)
           FROM {N} WHERE notice_kind='can' AND {fenster}""").fetchone()
    z += ["### Auftragswerte", "",
          f"- {_n(r[0])} Zuschläge · **{_n(r[1])} mit Wert** ({100*r[1]/max(r[0],1):.1f} %)",
          f"- davon **{_n(r[2])} in Fremdwährung** — die fielen mit der heutigen Regel aus jeder "
          "Wert-Kennzahl (s. CHF-Lücke)", ""]
    for w, n in con.execute(f"""SELECT coalesce(nullif(value_currency,''),'(leer)'), count(*)
            FROM {N} WHERE notice_kind='can' AND {fenster} AND final_value IS NOT NULL
            GROUP BY 1 ORDER BY 2 DESC LIMIT 4""").fetchall():
        z.append(f"  - {w}: {_n(n)}")
    z += [""]

    # 7) Branchen
    z += ["### Branchen (CPV-Divisionen im Fenster)", "",
          "| Division | Bekanntmachungen |", "|---|---:|"]
    for d, n in con.execute(f"""SELECT substr(cpv_main,1,2), count(*) FROM {N}
            WHERE {fenster} AND cpv_main IS NOT NULL
            GROUP BY 1 ORDER BY 2 DESC LIMIT 10""").fetchall():
        z.append(f"| {d} | {_n(n)} |")
    return z + [""]


def main(argv=None) -> int:
    import duckdb
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--land", required=True)
    ap.add_argument("--monate", type=int, default=36)
    a = ap.parse_args(argv)
    land = a.land.upper()
    if not _hat_silber(land):
        raise SystemExit(f"Kein Silber-Bestand für {land} "
                         f"— erst `python3 -m govisor.cli ingest --country {land} …` "
                         f"und `silver --country {land}`.")
    con = duckdb.connect()
    kopf = [f"# Marktanalyse {land}", "",
            f"**Erzeugt:** {dt.date.today().isoformat()} · `scripts/marktanalyse_land.py` · "
            f"Fenster: letzte {a.monate} Monate", "",
            "Quelle ist der TED-Bestand. **Unterschwellige Vergaben fehlen darin** — in "
            "Deutschland macht der unterschwellige Anteil rund die Hälfte aus. Die Zahlen "
            "hier sind also eine **Untergrenze** des tatsächlichen Marktes.", ""]
    ziel = ROOT / "data" / "analyse" / f"markt_{land.lower()}.md"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text("\n".join(kopf + analyse(con, land, a.monate)), encoding="utf-8")
    con.close()
    print(f"→ {ziel}")
    print(ziel.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
