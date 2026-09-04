#!/usr/bin/env python3
"""Aufwand gegen Zeitfenster → web/data/fenster.json (Kennzahl 1 der Übergabe).

⚠ DIE ERSTE DEUTUNG WAR FALSCH, und sie klang besser als sie war. Gemessen über 3.400
Vorgänge liegt der Median bei 34 Tagen, in JEDER Aufwandsklasse (bis 10 Anforderungen 33
Tage, über 100 Anforderungen 35), Korrelation 0,08. Daraus wurde zuerst: „der Markt gibt
dieselbe Zeit, egal wie viel Arbeit drinsteckt."

Sven, beim Lesen: „also zwischen unter 10 Anforderungen und über 100 liegen zwei Tage?!"

Nachgemessen ist die Flachheit **kein Marktverhalten, sondern eine Vorgabe**: 68 % aller
Fenster liegen zwischen 28 und 40 Tagen, die häufigsten Werte sind 30 bis 36. Dort liegen die
gesetzlichen Mindestfristen für offene Verfahren. Die Frist reagiert nicht auf den Aufwand,
weil sie überhaupt nicht auf ihn reagieren soll — sie ist geregelt. Das ist ein anderer Satz
als der erste, und der einzige, den die Daten tragen.

⚠ UND DAS KIPPTE AUCH DEN VERGLEICH. Die kurzen Fenster sind kein aggressiver Auftraggeber,
sondern ein anderes Regelwerk: unter den Vorgängen mit ≤ 28 Tagen sind 21 % UVgO, im Rest nur
4 %. Unterschwellig gelten andere Mindestfristen. Ein globaler Median hätte also jede
UVgO-Vergabe als „knapp" markiert, obwohl sie ihrem eigenen Rahmen entspricht.

    vgv    1.832 Vorgänge   Median 34   Viertel 32–38   p10 30
    vob    1.280            34          31–40           28
    uvgo     183            30          26–37           20
    sonst    105            40          32–52           31

Verglichen wird deshalb JE REGELWERK. Das ist die Bezugsgrössen-Regel in ihrer strengsten
Form: ein Vergleichswert, der zwei Rechtsgrundlagen mischt, ist kein Vergleichswert.

WAS BLEIBT. Die Kennzahl braucht weiterhin BEIDE Seiten — die Bekanntmachung (wann
veröffentlicht, wann Frist) und die Unterlagen (wie viele Anforderungen) — und niemand sonst
hat beide. Die Aussage ist nur enger: nicht „der Markt ist blind für den Aufwand", sondern
„diese Vergabe gibt weniger Zeit als neun von zehn ihres Regelwerks, bei so vielen
Anforderungen".

⚠ DAS VERÖFFENTLICHUNGSDATUM LIEGT NICHT IN GOLD. `lead_export` trägt `deadline_date`, aber
kein `publication_date`; das steht in Silber. Deshalb dieses eigene Skript statt einer Zeile
im grossen Lead-Export.

⚠ FENSTER ZWISCHEN 1 UND 365 TAGEN. Darunter ist es ein Datenfehler (Frist vor
Veröffentlichung), darüber sind es Rahmenvereinbarungen, deren „Frist" kein Zeitfenster für
ein Angebot ist. EIN Vorgang mit Frist 2029 verschöbe den Median um Wochen.

Aufruf: python3 scripts/export_fenster.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
# ⚠ ERST den Projektpfad, DANN `govisor` importieren. Unter launchd gibt es kein
# PYTHONPATH; ein Import davor bricht stumm ab (s. test_skripte_finden_govisor_ohne_pythonpath).
sys.path.insert(0, str(ROOT))
from govisor.laender import AKTIV as _AKTIV  # noqa: E402
sys.path.insert(0, str(ROOT))

OUT = ROOT / "web" / "data" / "fenster.json"
UNTEN, OBEN = 1, 365


def _rahmen(roh: str | None) -> str:
    """Regelwerk in vier Klassen. ⚠ Der Rohwert ist Freitext aus der Bekanntmachung; die
    Klassen sind grob, aber sie trennen die MINDESTFRISTEN, und darum geht es hier."""
    r = (roh or "").lower()
    if "uvgo" in r:
        return "uvgo"
    if "vob" in r:
        return "vob"
    if "vgv" in r:
        return "vgv"
    return "sonst"


def main() -> int:
    con = duckdb.connect()
    raus: dict = {"rahmen": {}, "leads": {}}
    # ⚠ LU seit 2026-09-03. Die Schleife prueft je Land auf die Datei und ueberspringt,
    # was fehlt — ein Land hier zu vergessen wirft also KEINEN Fehler, es zaehlt nur
    # nicht mit. Genau so hat LU 279 Leads lang gefehlt, ohne dass etwas rot wurde.
    # ⚠ Eine Stelle: `govisor/laender.py`. Hier stand eine eigene Liste.
    for land in _AKTIV:
        A = ROOT / "data" / "gold" / land / "doc_analysis.parquet"
        L = ROOT / "data" / "gold" / land / "lead_export.parquet"
        N = ROOT / "data" / "silver" / land / "notices"
        if not (A.exists() and L.exists() and N.exists()):
            continue
        try:
            zeilen = con.execute(f"""
              select a.notice_id,
                     date_diff('day', n.pub, l.deadline_date) AS fenster,
                     l.regulatory_regime
              from read_parquet('{A.as_posix()}') a
              join read_parquet('{L.as_posix()}') l on l.lead_id = a.notice_id
              join (select notice_id, max(publication_date) pub
                    from read_parquet('{(N / "**" / "*.parquet").as_posix()}')
                    group by 1) n on n.notice_id = a.notice_id
              where a.n_checklist > 0 and n.pub is not null and l.deadline_date is not null
                and date_diff('day', n.pub, l.deadline_date) between {UNTEN} and {OBEN}
            """).fetchall()
        except Exception as e:                                     # noqa: BLE001
            print(f"  {land}: {type(e).__name__} — uebersprungen ({str(e)[:70]})")
            continue
        if not zeilen:
            continue
        je_rahmen: dict[str, list[int]] = {}
        for nid, fenster, regime in zeilen:
            r = _rahmen(regime)
            je_rahmen.setdefault(r, []).append(int(fenster))
            raus["leads"][nid] = {"tage": int(fenster), "rahmen": r, "land": land}
        for r, werte in sorted(je_rahmen.items()):
            # ⚠ Unter 30 Vorgaengen kein Vergleichswert. Ein Median aus zwoelf Faellen sieht
            # aus wie einer aus zwoelfhundert und traegt nicht dasselbe.
            if len(werte) < 30:
                print(f"  {land}/{r}: nur {len(werte)} Vorgaenge — kein Vergleichswert")
                continue
            werte.sort()
            bei = lambda p: werte[min(len(werte) - 1, int(len(werte) * p))]   # noqa: E731
            raus["rahmen"][f"{land}:{r}"] = {
                "n": len(werte), "median": bei(0.5),
                "unten": bei(0.25), "oben": bei(0.75), "eng": bei(0.10),
            }
            print(f"  {land}/{r:<5} {len(werte):>5} Vorgaenge · Median {bei(0.5)} · "
                  f"Viertel {bei(0.25)}–{bei(0.75)} · eng ab {bei(0.10)}")

    if not raus["rahmen"]:
        print("FEHLT: keine Datengrundlage — erst `doc_analysis` bauen lassen.")
        return 1
    OUT.write_text(json.dumps(raus, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Zeitfenster: {len(raus['leads']):,} Vorgaenge, {len(raus['rahmen'])} Vergleichsgruppen "
          f"→ {OUT.name} ({OUT.stat().st_size / 1024:.0f} kB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
