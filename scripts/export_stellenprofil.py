#!/usr/bin/env python3
"""Fingerabdruck der Vergabestelle → web/data/stellenprofil.json (Kennzahl 3).

DIE FRAGE. Was verlangt DIESE Stelle fast immer, das andere selten verlangen? Wer das vor dem
Öffnen der Unterlagen weiss, legt die Nachweise bereit, statt sie nachzureichen.

    Landeshauptstadt München      Mindestumsatz          11 von 11   marktweit 10 %
    DB InfraGO, Fahrweg           technische Eignung     17 von 18   marktweit 17 %
    Berliner Wasserbetriebe       Berufshaftpflicht      13 von 14   marktweit 12 %
    BAPersBw, Team Beschaffung    Zuschlagskriterien     12 von 12   marktweit 18 %

⚠ NUR SELTENE ARTEN TRAGEN EINEN FINGERABDRUCK. `einzureichendes_dokument` steht in 92 % aller
Vorgänge, `leistung_menge` in 88 %, `frist` in 83 % — dass eine Stelle sie immer verlangt, ist
keine Eigenschaft der Stelle, sondern des Verfahrens. Gewertet werden deshalb nur die sieben
Arten unter 25 % Marktanteil, und die sind zugleich die einzigen, die etwas kosten:

    eignung_personal 21 % · zuschlagskriterium 18 % · eignung_technisch 17 % ·
    zertifikat 14 % · berufshaftpflicht 12 % · mindestumsatz 10 % · referenz_mindestwert 6 %

⚠ MINDESTENS FÜNF VERFAHREN. Bei dreien ist „3 von 3" rechnerisch auffällig und trotzdem
dünn; die Übergabe nimmt drei, das ergäbe 143 Fingerabdrücke statt 54. Ein Muster, das aus
drei Fällen stammt, sieht genauso aus wie eines aus achtzehn — und dieselbe Verwechslung hat
in diesem Projekt schon mehrfach Geld und Vertrauen gekostet.

⚠ DER SCHLÜSSEL IST DER KÄUFERNAME, nicht eine Entitäts-Kennung. `lead_export` trägt keine;
ein Join gegen Gold gibt es im Frontend nicht. Folge: zwei Schreibweisen derselben Stelle
zählen getrennt, und der Fingerabdruck ist dann schwächer, nie falsch.

Aufruf: python3 scripts/export_stellenprofil.py
"""
from __future__ import annotations

import sys
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
# ⚠ ERST den Projektpfad, DANN `govisor` importieren. Unter launchd gibt es kein
# PYTHONPATH; ein Import davor bricht stumm ab (s. test_skripte_finden_govisor_ohne_pythonpath).
sys.path.insert(0, str(ROOT))
from govisor.laender import AKTIV as _AKTIV  # noqa: E402
OUT = ROOT / "web" / "data" / "stellenprofil.json"

MIND_VERFAHREN = 5           # weniger ist kein Muster, nur ein Zufall mit drei Belegen
ANTEIL = 0.8                 # „fast immer"
MARKT_MAX = 0.25             # darüber ist es Verfahrensroutine, keine Eigenschaft der Stelle
MIND_MARKT = 100             # Arten, die es kaum gibt, tragen keinen Vergleich

LABEL = {
    "eignung_personal": "Personelle Eignung", "zuschlagskriterium": "Zuschlagskriterien",
    "eignung_technisch": "Technische Eignung", "zertifikat": "Zertifikate",
    "berufshaftpflicht": "Berufshaftpflicht", "mindestumsatz": "Mindestumsatz",
    "referenz_mindestwert": "Referenz-Mindestwert",
}


def main() -> int:
    con = duckdb.connect()
    raus: dict = {"markt": {}, "stellen": {}}
    # ⚠ LU seit 2026-09-03. Die Schleife prueft je Land auf die Datei und ueberspringt,
    # was fehlt — ein Land hier zu vergessen wirft also KEINEN Fehler, es zaehlt nur
    # nicht mit. Genau so hat LU 279 Leads lang gefehlt, ohne dass etwas rot wurde.
    # ⚠ Eine Stelle: `govisor/laender.py`. Hier stand eine eigene Liste.
    for land in _AKTIV:
        C = ROOT / "data" / "gold" / land / "doc_checklist.parquet"
        L = ROOT / "data" / "gold" / land / "lead_export.parquet"
        if not (C.exists() and L.exists()):
            continue
        ges = con.execute(f"select count(distinct notice_id) from read_parquet('{C.as_posix()}')").fetchone()[0]
        if not ges:
            continue
        arten = [t for t, v in con.execute(f"""
            select req_type, count(distinct notice_id) v
            from read_parquet('{C.as_posix()}') where req_type is not null group by 1
            having v >= {MIND_MARKT} and v < {ges} * {MARKT_MAX}""").fetchall()]
        if not arten:
            print(f"  {land}: keine hinreichend seltene Anforderungsart")
            continue
        liste = ",".join(f"'{a}'" for a in arten)
        for t, v in con.execute(f"""select req_type, count(distinct notice_id)
            from read_parquet('{C.as_posix()}') where req_type in ({liste}) group by 1""").fetchall():
            raus["markt"][f"{land}:{t}"] = round(100 * v / ges)
        for name, typ, k, n in con.execute(f"""
          with v as (select distinct c.notice_id, l.buyer_name
                     from read_parquet('{C.as_posix()}') c
                     join read_parquet('{L.as_posix()}') l on l.lead_id = c.notice_id
                     where l.buyer_name is not null),
               hat as (select distinct notice_id, req_type
                       from read_parquet('{C.as_posix()}') where req_type in ({liste})),
               je as (select v.buyer_name, h.req_type, count(distinct v.notice_id) k
                      from v join hat h on h.notice_id = v.notice_id group by 1, 2),
               ges as (select buyer_name, count(*) n from v group by 1 having n >= {MIND_VERFAHREN})
          select je.buyer_name, je.req_type, je.k, ges.n
          from je join ges using (buyer_name) where je.k >= ges.n * {ANTEIL}
          order by ges.n desc""").fetchall():
            schluessel = f"{land}:{str(name).strip().lower()[:120]}"
            raus["stellen"].setdefault(schluessel, []).append(
                {"typ": typ, "label": LABEL.get(typ, typ), "k": k, "n": n,
                 "markt": raus["markt"].get(f"{land}:{typ}", 0)})
        print(f"  {land}: {len(arten)} Arten · "
              f"{sum(len(v) for k, v in raus['stellen'].items() if k.startswith(land)):,} Fingerabdruecke "
              f"bei {len([k for k in raus['stellen'] if k.startswith(land)]):,} Stellen")

    if not raus["stellen"]:
        print("FEHLT: keine Datengrundlage — erst `doc_checklist` bauen lassen.")
        return 1
    OUT.write_text(json.dumps(raus, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Stellenprofil → {OUT.name} ({OUT.stat().st_size / 1024:.0f} kB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
