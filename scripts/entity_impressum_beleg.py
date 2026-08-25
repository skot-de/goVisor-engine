#!/usr/bin/env python3
"""Strittige Zusammenführungen am Impressum prüfen — Evidenz von aussen.

**Warum überhaupt eine dritte Instanz.** Die Schiedssprüche stammen von zwei Anbietern, die
dasselbe Modell fahren (Together und SambaNova liefern beide Llama-3.3-70B). Zwei Instanzen
eines Modells irren gleich; ihre Übereinstimmung ist deshalb kein starker Beleg. Was fehlt,
ist Evidenz ANDERER ART — nicht ein drittes Sprachmodell, sondern eine Quelle ausserhalb
unserer Daten. Das Impressum einer Firmenwebsite ist so eine Quelle: es nennt den Rechtssitz
verbindlich, und es ist unabhängig davon, was in Vergabebekanntmachungen steht.

**Die Frage, die es beantwortet.** Nach der Datengegenprobe bleiben Fälle vom Typ „gleicher
Name, verschiedene Städte" (97 gemessen am 2026-08-18). Genau dort entscheidet der
Rechtssitz: steht im Impressum EINE der beiden Städte, ist die andere eine Niederlassung
oder eine andere Firma; stehen BEIDE, ist es ein Unternehmen mit zwei Anschriften.

**Was es NICHT kann.** Ein Impressum nennt einen Sitz, nicht alle Standorte. Es kann
„verschieden" stützen und „gleich" plausibler machen, aber nichts davon beweisen. Und es
gibt es nur für Firmen: Vergabestellen haben in `suppliers.json` keine Domain.

Aufruf::  scripts/entity_impressum_beleg.py [--n 40] [--parallel 4]
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor.impressum import pruefe, falte  # noqa: E402

G = ROOT / "data/gold/DE"
SILBER = ROOT / "data/silver/DE/notice_parties"
ZIEL = G / "entity_impressum_beleg.parquet"


def domain_karte() -> dict[str, str]:
    """Normalisierter Firmenname → belegte Domain, aus `web/data/suppliers.json`.

    Die Lieferantendatei führt Domains samt Herkunft und Belegzahl; 16.029 von 30.750
    Einträgen (52 %) haben eine. Verknüpft wird über den gefalteten Namen, weil die
    Kandidatenpaare ohnehin über den Namen gebildet wurden — eine Entitäts-Kennung führen
    die Lieferanten nicht mit.
    """
    karte: dict[str, str] = {}
    datei = ROOT / "web/data/suppliers.json"
    for s in json.loads(datei.read_text(encoding="utf-8")):
        d = s.get("domain")
        if not d:
            continue
        for name in [s.get("name")] + list(s.get("aliases") or []):
            if name:
                karte.setdefault(falte(name), d)
    return karte


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--parallel", type=int, default=4, help="höflich bleiben: fremde Server")
    a = ap.parse_args()

    import duckdb
    import pandas as pd

    urteile = pd.read_parquet(G / "entity_merge_urteil.parquet")
    con = duckdb.connect()
    con.register("u", urteile[urteile.urteil.isin(["gleich", "alle_gleich"])]
                 [["entity_a", "entity_b", "urteil", "name_a"]])
    con.execute("""CREATE TEMP TABLE paare AS
        SELECT entity_a, unnest(str_split(entity_b, ';')) AS entity_b, urteil, name_a FROM u""")
    con.execute(f"""CREATE TEMP TABLE ort AS
        SELECT pe.entity_id,
               list(DISTINCT lower(regexp_replace(p.town, '[^A-Za-zÄÖÜäöüß]', '', 'g'))) AS orte
        FROM '{(G / 'party_entity.parquet').as_posix()}' pe
        JOIN '{SILBER.as_posix()}/**/*.parquet' p
          ON p.notice_id = pe.notice_id AND p.role = pe.role AND p.seq = pe.seq
        WHERE p.town IS NOT NULL AND regexp_replace(p.town, '[^A-Za-zÄÖÜäöüß]', '', 'g') <> ''
        GROUP BY 1""")

    # Genau die Fälle, in denen die Datenprüfung widersprochen hat: keine gemeinsame Stadt.
    strittig = con.execute(f"""
        SELECT pa.name_a, e.canonical_name AS name_b, a.orte AS orte_a, b.orte AS orte_b, pa.urteil
        FROM paare pa
        JOIN ort a ON a.entity_id = pa.entity_a
        JOIN ort b ON b.entity_id = pa.entity_b
        JOIN '{(G / 'entities.parquet').as_posix()}' e ON e.entity_id = pa.entity_b
        WHERE NOT EXISTS (SELECT 1 FROM unnest(a.orte) AS t(x), unnest(b.orte) AS u(y)
                          WHERE x = y OR contains(x, y) OR contains(y, x))
        LIMIT {a.n}""").df()

    karte = domain_karte()
    aufgaben = []
    for _, r in strittig.iterrows():
        d = karte.get(falte(r["name_a"])) or karte.get(falte(r["name_b"]))
        if d:
            aufgaben.append((r["name_a"], r["name_b"], d,
                             list(r["orte_a"])[0], list(r["orte_b"])[0], r["urteil"]))
    print(f"  {len(strittig)} strittige Paare · {len(aufgaben)} mit belegter Domain")
    if not aufgaben:
        return 0

    def belegen(auf):
        name_a, name_b, domain, ort_a, ort_b, urteil = auf
        # Zwei Abrufe je Domain (einer je Stadt). Der Pruefer bringt seine eigenen
        # Hoeflichkeitsgrenzen mit; deshalb hier nur wenige Faeden.
        ba = pruefe(domain, name_a, ort=ort_a)
        bb = pruefe(domain, name_b, ort=ort_b)
        if ba.ort_belegt and bb.ort_belegt:
            beleg = "beide_orte_im_impressum"          # ein Unternehmen, zwei Anschriften
        elif ba.ort_belegt or bb.ort_belegt:
            beleg = "nur_ein_ort_im_impressum"         # der andere ist nicht der Sitz
        else:
            beleg = "kein_ort_im_impressum"            # nichts gewonnen
        return {"name_a": name_a, "name_b": name_b, "domain": domain,
                "ort_a": ort_a, "ort_b": ort_b, "urteil_modell": urteil,
                "impressum_urteil": ba.urteil, "beleg": beleg,
                "register_belegt": bool(ba.register_belegt or bb.register_belegt)}

    ergebnisse = []
    with ThreadPoolExecutor(max_workers=a.parallel) as pool:
        for fut in as_completed([pool.submit(belegen, x) for x in aufgaben]):
            try:
                ergebnisse.append(fut.result())
            except Exception as ex:                                # noqa: BLE001
                print(f"    ✖ {type(ex).__name__}: {str(ex)[:60]}", file=sys.stderr)

    df = pd.DataFrame(ergebnisse)
    df.to_parquet(ZIEL, index=False)
    print(f"\n  {dict(df['beleg'].value_counts())}")
    print(f"  Impressum-Urteil zur Domain: {dict(df['impressum_urteil'].value_counts())}")
    print(f"  → {ZIEL.relative_to(ROOT)}")
    print("  Ein Impressum nennt den SITZ, nicht alle Standorte: es stützt, es beweist nicht.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
