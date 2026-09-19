#!/usr/bin/env python3
"""Was klicken die Nutzer weg, und warum? (`user_lead_hidden`, Migration 0021)

⚠ WOZU DAS DA IST. Jedes Ausblenden ist ein NEGATIVES BEISPIEL fuer die Passung — die
einzige Sorte Rueckmeldung, die einen Klick kostet statt eines Formulars. Ohne Auswertung
ist sie nur eine Zeile in einer Tabelle; ausgewertet sagt sie, wo der Vorschlag danebenlag.

⚠ VIER FRAGEN, DIE DIESE AUSWERTUNG BEANTWORTEN SOLL — und sie sind nicht gleich viel wert:

  1. **Welcher Grund ueberwiegt?** „falscher Inhalt" heisst, die Branchenzuordnung greift
     daneben; „falsche Region" heisst, der Ortsfilter tut es. Zwei ganz verschiedene
     Baustellen, und nur die Aufteilung sagt, welche.
  2. **Welche CPV-Klassen werden ueberdurchschnittlich weggeklickt?** Das ist der Hebel:
     eine Klasse, die alle wegklicken, gehoert nicht in den Grundraum.
  3. **Welche Kaeufer?** Ein Kaeufer, den jeder wegklickt, ist ein Kandidat fuer eine
     Regel, kein Einzelfall.
  4. **Wie oft wird OHNE Grund weggeklickt?** Die Zahl ist die ehrlichste hier: sie sagt,
     wie belastbar alles andere ist. Liegt sie bei 90 %, sind die uebrigen Prozente
     Rauschen aus einer Handvoll Klicks.

⚠ DIE SCHWELLE IST DER GANZE TRICK. Bei wenigen Nutzern sind das kleine Zahlen; drei
Klicks auf dieselbe CPV-Klasse sind kein Muster, sondern ein Mensch mit einem Nachmittag.
Deshalb wird ALLES mit `n` ausgewiesen und unterhalb von `--mindestens` gar nicht erst
gezeigt. Eine Prozentzahl ohne Nenner ist in diesem Projekt schon zweimal teuer geworden.

Aufruf:  python3 scripts/auswertung_ausgeblendet.py [--mindestens 5] [--json]
Rueckgabe: 0 immer (eine leere Auswertung ist kein Fehler, sondern ein junges Produkt)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from collections import Counter

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

# ⚠ DIESELBE LISTE WIE IN DER OBERFLAECHE (`AUS_GRUENDE` in ExplorerShell.tsx). Ein
# zweiter, abweichender Katalog hier waere die Sorte Bruch, die erst auffaellt, wenn die
# Zahlen nicht mehr aufgehen — `tests/test_ausgeblendet_auswertung.py` haelt beide zusammen.
GRUENDE = ["nicht unser Fach", "zu weit weg", "zu groß", "zu klein"]


def _dsn() -> str | None:
    a, b = WURZEL / ".secrets" / "supabase.txt", WURZEL / ".secrets" / "supabase_db.txt"
    if not (a.exists() and b.exists()):
        return None
    try:
        ref = a.read_text(encoding="utf-8").splitlines()[0].split("//")[1].split(".")[0]
        return (f"postgresql://postgres:{b.read_text(encoding='utf-8').strip()}"
                f"@db.{ref}.supabase.co:5432/postgres")
    except (IndexError, OSError):
        return None


def hole() -> list[dict] | None:
    dsn = _dsn()
    if not dsn:
        return None
    try:
        from govisor.psql import psql_oder_fehler
        r = subprocess.run(
            [psql_oder_fehler(), dsn, "-At", "-F", "\x1f", "-c",
             "select lead_id, coalesce(grund,''), coalesce(titel,''), coalesce(buyer_name,''),"
             " user_id::text, created_at::date from public.user_lead_hidden"],
            capture_output=True, text=True, timeout=90)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    raus = []
    for z in r.stdout.splitlines():
        if not z.strip():
            continue
        t = z.split("\x1f")
        if len(t) >= 6:
            raus.append({"lead_id": t[0], "grund": t[1], "titel": t[2],
                         "buyer": t[3], "user": t[4], "am": t[5]})
    return raus


def _cpv_je_lead(ids: set[str]) -> dict:
    """CPV-Klasse (vierstellig) je ausgeblendetem Lead, aus Gold."""
    if not ids:
        return {}
    try:
        import duckdb
        dateien = sorted(str(p) for p in pathlib.Path("data/gold").glob("*/lead_export*.parquet"))
        if not dateien:
            return {}
        con = duckdb.connect()
        lst = ",".join("'" + i.replace("'", "") + "'" for i in ids)
        return {r[0]: r[1] for r in con.execute(
            f"SELECT lead_id, substr(cpv_main,1,4) FROM read_parquet({dateien!r},"
            f" union_by_name=true) WHERE lead_id IN ({lst}) AND cpv_main IS NOT NULL").fetchall()}
    except Exception:
        return {}


def bericht(zeilen: list[dict], mindestens: int) -> dict:
    n = len(zeilen)
    mit_grund = [z for z in zeilen if z["grund"]]
    cpv = _cpv_je_lead({z["lead_id"] for z in zeilen})
    def top(zaehler: Counter) -> list:
        return [{"wert": k, "n": v} for k, v in zaehler.most_common(10) if v >= mindestens]
    return {
        "ausgeblendet": n,
        "nutzer": len({z["user"] for z in zeilen}),
        "mit_grund": len(mit_grund),
        # ⚠ Die wichtigste Zahl des Berichts: sie sagt, wie belastbar alles darunter ist.
        "grund_quote": round(100 * len(mit_grund) / n, 1) if n else 0.0,
        "gruende": top(Counter(z["grund"] for z in mit_grund)),
        "cpv": top(Counter(cpv[z["lead_id"]] for z in zeilen if z["lead_id"] in cpv)),
        "kaeufer": top(Counter(z["buyer"] for z in zeilen if z["buyer"])),
        "mindestens": mindestens,
        # ⚠ Gruende, die in der Datenbank stehen, aber nicht mehr in der Oberflaeche: ein
        # umbenannter Knopf laesst alte Klicks zu Waisen werden, und ohne diese Zeile
        # verschwinden sie stillschweigend aus jeder Statistik.
        "unbekannte_gruende": sorted({z["grund"] for z in mit_grund} - set(GRUENDE)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mindestens", type=int, default=5,
                    help="unterhalb dieser Zahl wird nichts gezeigt (Vorgabe 5)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    zeilen = hole()
    if zeilen is None:
        print("  (kein Zugang zur Datenbank — keine Auskunft)")
        return 0
    b = bericht(zeilen, a.mindestens)
    if a.json:
        print(json.dumps(b, ensure_ascii=False, indent=2))
        return 0
    if not b["ausgeblendet"]:
        print("  Noch nichts ausgeblendet. Die Tabelle ist seit dem 2026-09-19 scharf.")
        return 0
    print(f"  {b['ausgeblendet']:,} Ausblendungen von {b['nutzer']} Nutzer(n)")
    print(f"  mit Grund: {b['mit_grund']:,} ({b['grund_quote']} %)"
          f"  ← sagt, wie belastbar der Rest ist\n")
    for titel, schluessel in (("Gruende", "gruende"), ("CPV-Klassen", "cpv"), ("Kaeufer", "kaeufer")):
        print(f"  {titel} (ab n={b['mindestens']}):")
        if not b[schluessel]:
            print("    (nichts ueber der Schwelle)")
        for e in b[schluessel]:
            print(f"    {str(e['wert'])[:46]:<48} {e['n']:>5}")
        print()
    if b["unbekannte_gruende"]:
        print(f"  ⚠ Gruende ohne Knopf in der Oberflaeche: {b['unbekannte_gruende']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
