#!/usr/bin/env python3
"""Aufwand gegen Zeitfenster → web/data/fenster.json (Kennzahl 1 der Übergabe).

DER BEFUND. Zwischen Bekanntmachung und Angebotsfrist liegen im Median **34 Tage**, und zwar
UNABHÄNGIG davon, wie viel Arbeit das Verfahren macht. Gemessen am 2026-09-02 über 3.400
Vorgänge mit ausgewerteten Unterlagen:

    bis 10 Anforderungen   102 Vorgänge   Median 33 Tage
    11 bis 25              246            34
    26 bis 50              847            34
    51 bis 100           1.979            34
    über 100               226            35

Korrelation zwischen Anforderungszahl und Fenster: **0,08**, also keine. Ein Verfahren mit 186
Anforderungen bekommt dieselbe Zeit wie eines mit dreien.

⚠ WARUM DAS EINE KENNZAHL IST UND KEINE ANEKDOTE. Sie braucht BEIDE Seiten: die
Bekanntmachung (wann veröffentlicht, wann Frist) und die Unterlagen (wie viele Anforderungen).
Wer nur eine hat, kann sie nicht rechnen — und niemand sonst hat beide.

⚠ DAS VERÖFFENTLICHUNGSDATUM LIEGT NICHT IN GOLD. `lead_export` trägt `deadline_date`, aber
kein `publication_date`; das steht in Silber. Deshalb dieses eigene Skript statt einer Zeile
im grossen Lead-Export: dort gäbe es den Join nicht ohne Umbau.

⚠ FENSTER ZWISCHEN 1 UND 365 TAGEN. Alles darunter ist ein Datenfehler (Frist vor
Veröffentlichung), alles darüber sind Rahmenvereinbarungen und dynamische Systeme, deren
„Frist" kein Zeitfenster für ein Angebot ist. Ohne diese Grenze verschiebt ein Vorgang mit
Frist 2029 den Median um Wochen.

Aufruf: python3 scripts/export_fenster.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "web" / "data" / "fenster.json"
UNTEN, OBEN = 1, 365


def main() -> int:
    con = duckdb.connect()
    raus: dict = {"laender": {}, "leads": {}}
    for land in ("DE", "AT", "CH"):
        A = ROOT / "data" / "gold" / land / "doc_analysis.parquet"
        L = ROOT / "data" / "gold" / land / "lead_export.parquet"
        N = ROOT / "data" / "silver" / land / "notices"
        if not (A.exists() and L.exists() and N.exists()):
            continue
        try:
            zeilen = con.execute(f"""
              select a.notice_id,
                     date_diff('day', n.pub, l.deadline_date) AS fenster,
                     a.n_checklist
              from read_parquet('{A.as_posix()}') a
              join read_parquet('{L.as_posix()}') l on l.lead_id = a.notice_id
              join (select notice_id, max(publication_date) pub
                    from read_parquet('{(N / "**" / "*.parquet").as_posix()}')
                    group by 1) n on n.notice_id = a.notice_id
              where a.n_checklist > 0 and n.pub is not null and l.deadline_date is not null
                and date_diff('day', n.pub, l.deadline_date) between {UNTEN} and {OBEN}
            """).fetchall()
        except Exception as e:                                     # noqa: BLE001
            print(f"  {land}: {type(e).__name__} — übersprungen ({str(e)[:70]})")
            continue
        if not zeilen:
            continue
        werte = sorted(int(z[1]) for z in zeilen)
        bei = lambda p: werte[min(len(werte) - 1, int(len(werte) * p))]   # noqa: E731
        # ⚠ `eng` ist das ZEHNTE Perzentil, nicht das Viertel. Mit dem Viertel erschien die
        # Zeile bei 51 % aller Vorgaenge (26 % eng, 25 % weit) — bei jedem zweiten, also
        # Tapete. Beim zehnten Perzentil sind es 11 %, und die tragen dann auch etwas:
        # 28 Tage oder weniger fuer eine Anforderungsliste, die im Median 34 bekommt.
        raus["laender"][land] = {
            "n": len(werte), "median": bei(0.5),
            "unten": bei(0.25), "oben": bei(0.75), "eng": bei(0.10),
        }
        for nid, fenster, _ in zeilen:
            raus["leads"][nid] = int(fenster)
        print(f"  {land}: {len(werte):,} Vorgänge · Median {bei(0.5)} Tage "
              f"(Viertel {bei(0.25)} bis {bei(0.75)}, eng ab {bei(0.10)})")

    if not raus["laender"]:
        print("FEHLT: keine Datengrundlage — erst `doc_analysis` bauen lassen.")
        return 1
    OUT.write_text(json.dumps(raus, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Zeitfenster: {len(raus['leads']):,} Vorgänge → {OUT.name} "
          f"({OUT.stat().st_size / 1024:.0f} kB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
