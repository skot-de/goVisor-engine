#!/usr/bin/env python3
"""Offene Zusammenführungs-Kandidaten von zwei Modellen beurteilen lassen.

**Das Problem.** Die Entitäten-Auflösung entscheidet nach Handregeln: gleiche Handelsregister-
Nummer → dieselbe Firma, gleiche TED-Kennung → dieselbe. Was übrig bleibt, bleibt liegen.
Gemessen am 2026-08-18 über 334.037 Entitäten:

    ted_nationalid          43.850   Konfidenz 1,0
    handelsregister_exakt   55.558             0,9
    nur_name               181.034             0,4   ← nur der Name stimmt überein
    nicht_aufgeloest        53.595             0,0

Dazu 6.971 Paare in `entity_merge_candidates`, die die Regeln ausdrücklich NICHT entschieden
haben: 5.171 mit mehrdeutiger Kennung, 1.800 ohne PLZ-Beleg. „Spenglerei Sharuk GmbH" zweimal,
ohne Ortsangabe — eine Regel kann da nur raten, ein Modell mit Kontext nicht unbedingt.

**Warum zwei Modelle und nicht eines.** Eine falsche Zusammenführung ist teurer als eine
unterlassene: sie verschmilzt zwei Firmen zu einer, und danach stimmen Marktanteile,
Wettbewerbsbilder und Firmenprofile nicht mehr — sichtbar erst, wenn ein Kunde sein eigenes
Profil ansieht. Deshalb entscheidet hier nicht ein Modell, sondern die **Übereinstimmung
zweier unabhängiger** (voreingestellt xAI und Perplexity, s. `govisor/llm.py`). Sind sie
uneins, lautet das Urteil `unsicher` — und es passiert nichts.

**Was das Skript NICHT tut: zusammenführen.** Es schreibt Urteile nach
``data/gold/DE/entity_merge_urteil.parquet``. Ob und wann die in `gold` einfliessen, ist eine
zweite Entscheidung mit eigenem Lauf — „markieren statt löschen", wie überall hier.

Aufruf::

    scripts/entity_adjudicate.py --n 40          # Probe
    scripts/entity_adjudicate.py --alle
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor import llm  # noqa: E402

G = ROOT / "data/gold/DE"
SILBER = ROOT / "data/silver/DE/notice_parties"
ZIEL = G / "entity_merge_urteil.parquet"

def richter_waehlen(anzahl: int = 2) -> list[str]:
    """Die besten ZWEI Anbieter, die gerade auch wirklich liefern.

    ⚠ WARUM NICHT FEST VERDRAHTET. Erst standen hier xAI und Perplexity — die beiden Sieger
    des Modellvergleichs. Eine Stunde später war das xAI-Guthaben aufgebraucht (die
    Dokumentenanalyse hatte es mit 40 Fäden verbrannt) und Perplexity antwortete mit 401.
    Der Lauf lieferte daraufhin 40 von 40 Urteilen „unsicher", bei 100 % Einigkeit der
    Richter — beide sagten nichts, und das sah nach Übereinstimmung aus. Eine feste Liste
    misst irgendwann nicht mehr die Sache, sondern den Kontostand.

    Deshalb: kurz anklopfen, und wer antwortet, richtet. Die Reihenfolge in `llm._anbieter()`
    ist die nach gemessener Qualität sortierte.
    """
    lebt = []
    for a in llm._anbieter():
        if not a["keys"]:
            continue
        try:
            llm.chat([{"role": "user", "content": "ok"}], anbieter=a["name"], max_retries=1, timeout=30)
            lebt.append(a["name"])
        except Exception:                                      # noqa: BLE001
            continue
        if len(lebt) == anzahl:
            break
    return lebt

SYSTEM = (
    "Du ordnest einen Eintrag aus Vergabebekanntmachungen (A, nur ein Name, keine amtliche "
    "Kennung) den Kandidaten mit Kennung (B) zu. Antworte NUR als JSON: "
    '{"urteil":"gleich|alle_gleich|verschieden|unsicher","treffer":"<entity_id oder null>",'
    '"grund":"ein kurzer Satz"}. '
    "Bedeutung der Urteile: "
    "'gleich' = A ist GENAU EINER der Kandidaten, dessen entity_id in 'treffer' steht. "
    "'alle_gleich' = A und ALLE Kandidaten bezeichnen dieselbe Organisation, die mehrfach "
    "mit verschiedenen Kennungen erfasst wurde (gleicher Name, gleicher Ort, keine "
    "widersprechenden Angaben). "
    "'verschieden' = A ist keiner davon. 'unsicher' = die Angaben tragen keine Entscheidung. "
    "Regeln: Gleicher Name allein genügt NICHT, wenn Ort oder Kennung widersprechen. "
    "Verschiedene Orte bei gleichem Namen sprechen für verschieden, ausser der Name nennt eine "
    "überregionale Organisation. Fehlende Angaben sind kein Beleg für Gleichheit. Passen "
    "mehrere Kandidaten gleich gut UND unterscheiden sie sich in Ort oder Rechtsform, ist die "
    "Antwort 'unsicher', nicht 'alle_gleich'. Eine falsche Zusammenführung ist schlimmer als "
    "eine unterlassene."
)

# ── WARUM ES 'alle_gleich' GIBT ──────────────────────────────────────────────────────────
# Der erste Durchgang lieferte 14 von 30 „unsicher", und die Begruendungen sagten fast immer
# dasselbe: „mehrere Kandidaten mit identischem Namen und Ort, beide passen gleich gut."
# Das ist keine Unentschiedenheit, sondern ein Befund — die KANDIDATEN sind untereinander
# dieselbe Organisation, mehrfach erfasst unter verschiedenen Kennungen (Leitweg-ID, USt-ID,
# HRB, je nach Quelle). Die Frage „welcher von beiden" hat dort keine Antwort, weil die
# Voraussetzung falsch ist: es sind nicht zwei.
#
# Sven am 2026-08-18: „bau das urteil 'kandidaten untereinander gleich' ein."
#
# ⚠ Das Urteil ist ausdruecklich enger gefasst als „sieht gleich aus": unterscheiden sich die
# Kandidaten in Ort oder Rechtsform, bleibt es bei 'unsicher'. Sonst verschmilzt es genau die
# Faelle, wegen denen die Handregel ueberhaupt aufgegeben hat.


def _als_text(wert) -> str | None:
    if wert is None:
        return None
    if isinstance(wert, (list, tuple)):
        return ";".join(str(w) for w in wert if w) or None
    return str(wert)


def kontext(con, entity_id: str) -> dict:
    """Was wir über eine Entität wissen: Name, Kennung, Orte, Rollen, Umfang."""
    zeile = con.execute(
        f"SELECT canonical_name, national_id, method FROM '{(G / 'entities.parquet').as_posix()}' "
        "WHERE entity_id = ?", [entity_id]).fetchone()
    orte = con.execute(f"""
        SELECT DISTINCT p.postal_code, p.town, p.role
        FROM '{(G / 'party_entity.parquet').as_posix()}' pe
        JOIN '{(SILBER).as_posix()}/**/*.parquet' p
          ON p.notice_id = pe.notice_id AND p.role = pe.role AND p.seq = pe.seq
        WHERE pe.entity_id = ? LIMIT 6""", [entity_id]).fetchall()
    n = con.execute(f"SELECT count(*) FROM '{(G / 'party_entity.parquet').as_posix()}' "
                    "WHERE entity_id = ?", [entity_id]).fetchone()[0]
    return {"name": zeile[0] if zeile else "?", "kennung": zeile[1] if zeile else None,
            "methode": zeile[2] if zeile else None, "vorgaenge": n,
            "orte": [{"plz": o[0], "ort": o[1], "rolle": o[2]} for o in orte]}


def kontexte(con, roh_id: str) -> list[dict]:
    """Die B-Seite auflösen — sie ist NICHT immer eine einzelne Entität.

    Bei `mehrdeutige_id` verbindet `gold.py` mehrere Entitäts-Kennungen mit Semikolon
    („id:12317;id:HRB9319;id:vat:DE114874293"). Der erste Entwurf schickte diese Zeichenkette
    als Kennung an das Modell; gemessen liessen sich nur 1.793 von 6.971 B-Seiten so auflösen,
    der Rest kam LEER an — und die Modelle antworteten folgerichtig „B enthält weder Name noch
    Ort noch Kennung". 30 von 30 Urteilen lauteten „unsicher", und das sah aus wie Vorsicht.
    War es aber nicht: es war eine falsch gestellte Frage.
    """
    teile = [t for t in (roh_id or "").split(";") if t.strip()]
    aus = [kontext(con, t) for t in teile]
    return [k for k in aus if k["name"] != "?"] or aus[:1]


def urteil_von(anbieter: str, a: dict, b: dict) -> dict:
    """Ein Richter, ein Anbieter. Ohne globale Umschaltung — s. `llm.chat(anbieter=…)`."""
    try:
        roh = llm.chat([{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": json.dumps({"A": a, "B": b}, ensure_ascii=False)}],
                       anbieter=anbieter)
    except Exception as ex:                                    # noqa: BLE001
        return {"urteil": "unsicher", "grund": f"{type(ex).__name__}: {str(ex)[:60]}"}
    roh = re.sub(r"^```json|^```|```$", "", roh.strip(), flags=re.M).strip()
    try:
        d = json.loads(roh)
    except json.JSONDecodeError:
        return {"urteil": "unsicher", "grund": "Antwort war kein JSON"}
    if d.get("urteil") not in ("gleich", "alle_gleich", "verschieden", "unsicher"):
        return {"urteil": "unsicher", "grund": "unbekanntes Urteil"}
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--alle", action="store_true")
    ap.add_argument("--parallel", type=int, default=8)
    a = ap.parse_args()

    import duckdb
    con = duckdb.connect()
    paare = con.execute(
        f"SELECT name_only_entity, candidate_entity, reason "
        f"FROM '{(G / 'entity_merge_candidates.parquet').as_posix()}'"
        + ("" if a.alle else f" USING SAMPLE {a.n} ROWS")).fetchall()
    richter = richter_waehlen()
    if len(richter) < 2:
        print(f"  ✖ Nur {len(richter)} Anbieter mit Guthaben — ein Urteil braucht zwei "
              "unabhängige. Abbruch, damit nicht eine Meinung wie ein Konsens aussieht.",
              file=sys.stderr)
        return 2
    print(f"  {len(paare):,} Kandidatenpaare · Richter: {', '.join(richter)}")

    def beurteile(paar):
        e1, e2, grund = paar
        # Kontext im Arbeitsfaden holen: DuckDB-Verbindungen sind nicht fadensicher.
        c = duckdb.connect()
        a_ctx = kontext(c, e1)
        kandidaten = kontexte(c, e2)
        b_ctx = {"kandidaten": kandidaten}
        c.close()
        urteile = [urteil_von(r, a_ctx, b_ctx) for r in richter]
        einig = len({u["urteil"] for u in urteile}) == 1
        return {"entity_a": e1, "entity_b": e2, "regel_grund": grund,
                "name_a": a_ctx["name"],
                "name_b": " | ".join(k["name"] for k in kandidaten)[:200],
                "kandidaten": len(kandidaten),
                # Eine Spalte, ein Typ. Modelle liefern bei „alle_gleich" gern eine Liste
                # von Kennungen; als Objektspalte scheitert der Parquet-Schreiber („Expected
                # bytes, got a 'list'"). Zusammengefuegt bleibt die Information erhalten.
                "treffer": _als_text(urteile[0].get("treffer")) if einig else None,
                "urteil": urteile[0]["urteil"] if einig else "unsicher",
                "einig": einig,
                "urteil_1": urteile[0]["urteil"], "urteil_2": urteile[1]["urteil"],
                "grund_1": (urteile[0].get("grund") or "")[:200],
                "grund_2": (urteile[1].get("grund") or "")[:200]}

    ergebnisse = []
    with ThreadPoolExecutor(max_workers=a.parallel) as pool:
        for fut in as_completed([pool.submit(beurteile, p) for p in paare]):
            try:
                ergebnisse.append(fut.result())
            except Exception as ex:                            # noqa: BLE001
                print(f"    ✖ {type(ex).__name__}: {ex}", file=sys.stderr)

    import pandas as pd
    df = pd.DataFrame(ergebnisse)
    df.to_parquet(ZIEL, index=False)

    einig = int(df["einig"].sum())
    print(f"\n  Urteile: {dict(df['urteil'].value_counts())}")
    print(f"  Die zwei Richter waren sich in {einig}/{len(df)} Fällen einig "
          f"({einig / max(len(df), 1):.0%}).")
    print(f"  → {ZIEL.relative_to(ROOT)} · ZUSAMMENGEFÜHRT WIRD NICHTS, das ist ein eigener Schritt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
