#!/usr/bin/env python3
"""Wächter: eine Warteschlange, in der Arbeit liegt und sich seit Tagen nichts bewegt.

⚠ WARUM ES DIESE SONDE GIBT. Am 2026-10-05 lief der Analyse-Arbeiter seit dem 11. September
ohne Unterbrechung, protokollierte alle 30 Minuten brav seinen Stand — und hatte seit dem
**24. September nichts mehr analysiert**. 3.946 Dokumente lagen unbearbeitet, das OpenRouter-
Guthaben war seit dem 21.09. leer (528 Meldungen „Kein Guthaben" im Protokoll). Elf Tage, und
keine einzige Prüfung schlug an.

Warum es keine der zwölf bestehenden Sonden sah:
  · Der Dienst LÄUFT — in jeder Prozessliste gesund.
  · Die Daten sind VOLLSTÄNDIG — kein Feld NULL, kein Fremdschlüssel gebrochen.
  · Die Frische-Sonde sah `web/data/doc-analysis` altern und sagte „hängt 10,3 Tage zurück" —
    richtig, aber als Dateialter, ohne das WARUM. Niemand las es als „die Analyse steht".
  · Der Arbeiter WEISS es sogar: `data/.llm_stand.json` trägt `halt: "guthaben"` und einen
    Satz im Klartext. **Die Auskunft lag da, es las sie nur niemand.**

DER DETEKTOR. Für jede Warteschlange zwei unabhängige Zahlen, beide aus den DATEN und nicht
aus dem Protokoll (ein Protokolltext ändert sich beim nächsten Umbau, eine Datenspalte nicht):

    wartend        liegt überhaupt Arbeit an?
    letzte Bewegung  wann wurde zuletzt etwas fertig?

Ein Befund ist **nur beides zusammen**. Eine leere Warteschlange, die stillsteht, ist fertig
und kein Problem; eine volle, die sich bewegt, arbeitet sich ab.

⚠ DIE SCHWELLE IST GEMESSEN, NICHT GEFÜHLT. Die Analyse lieferte zwischen dem 2026-08-22 und
dem 2026-09-24 an 23 Tagen Ergebnisse; die Lücken dazwischen waren 1, 2, 3 und 5 Tage, Median
1. Die grösste Lücke im Normalbetrieb war also **5** — die Schwelle liegt darüber und unter
dem Ausfall (11), damit sie weder bei einem ruhigen Wochenende schreit noch den echten Fall
verschläft.

    python3 scripts/pruefe_warteschlangen.py [--offen] [--alle]

Rückgabe 1, wenn eine Warteschlange Arbeit trägt und sich länger als die Schwelle nicht bewegt.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

WURZEL = pathlib.Path(__file__).resolve().parent.parent
DATEN = WURZEL / "data"

# Gemessen am 2026-10-05: grösste Lücke im Normalbetrieb 5 Tage, Ausfall 11.
SCHWELLE_TAGE = 7


def _heute() -> dt.date:
    return dt.date.today()


def _tage_her(wann) -> int | None:
    if wann is None:
        return None
    s = str(wann)[:10]
    try:
        return (_heute() - dt.date.fromisoformat(s)).days
    except ValueError:
        return None


def analyse_schlangen() -> list[dict]:
    """Die Dokumentenanalyse je Land.

    `wartend` kommt aus `.llm_stand.json` — der Arbeiter schreibt dort hinein, was sein
    eigener Lauf übrig gelassen hat. ⚠ Diese Datei zählt über ALLE Länder; sie wird deshalb
    nur der Schlange des Landes zugeordnet, in dem die Analyse tatsächlich läuft (heute DE).
    Eine falsche Zuordnung wäre schlimmer als keine: sie liesse ein Land voll aussehen, das
    gar nichts zu tun hat.
    """
    stand = {}
    p = DATEN / ".llm_stand.json"
    try:
        stand = json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                                # noqa: BLE001
        stand = {}

    import duckdb
    con = duckdb.connect()
    raus = []
    for datei in sorted(DATEN.glob("gold/*/doc_analysis.parquet")):
        land = datei.parent.name
        try:
            neu = con.execute(
                f"SELECT max(stand) FROM read_parquet('{datei.as_posix()}')").fetchone()[0]
        except Exception as e:                                       # noqa: BLE001
            raus.append({"name": f"Analyse {land}", "fehler": f"{type(e).__name__}"})
            continue
        ist_haupt = land == "DE"
        raus.append({
            "name": f"Analyse {land}",
            "wartend": int(stand.get("wartend") or 0) if ist_haupt else None,
            "bewegung": neu,
            "tage": _tage_her(neu),
            "grund": (stand.get("halt_grund") or "").strip() if ist_haupt else "",
            "halt": (stand.get("halt") or "") if ist_haupt else "",
        })
    return raus


def abruf_schlangen() -> list[dict]:
    """Die Dokument-Abrufer je Land und Portal, aus ihren Manifesten.

    ⚠ `wartend` bleibt hier bewusst UNBEKANNT. Wie viele Vergaben ein Abrufer noch vor sich
    hat, sagt der Rückstau — und der filtert bei 3 von 13 Abrufern nachweislich nichts
    (Auto-Memory `govisor-rueckstau-steuerzahl`: simap meldete 1.566, echt waren 3). Eine
    Zahl, der man nicht trauen kann, in einen Riegel zu legen, erzeugt entweder Fehlalarm
    oder falsche Ruhe. Deshalb werden diese Schlangen GEZEIGT, aber nie als Befund gewertet:
    ein Abrufer, der eine Woche nichts holt, kann schlicht nichts zu holen haben.
    """
    import duckdb
    con = duckdb.connect()
    raus = []
    for ordner in sorted((DATEN / "docs").glob("*")):
        if not ordner.is_dir():
            continue
        for m in sorted(ordner.glob("_manifest*.parquet")):
            kurz = m.stem.replace("_manifest", "").lstrip("_") or "gesamt"
            try:
                spalten = [c[0] for c in con.execute(
                    f"describe select * from read_parquet('{m.as_posix()}')").fetchall()]
                if "versucht_am" not in spalten:
                    continue
                n, neu = con.execute(
                    f"SELECT count(*), max(versucht_am) FROM read_parquet('{m.as_posix()}')"
                ).fetchone()
            except Exception:                                        # noqa: BLE001
                continue
            raus.append({"name": f"Abruf {ordner.name}/{kurz}", "wartend": None,
                         "saetze": n, "bewegung": neu, "tage": _tage_her(neu), "grund": ""})
    return raus


def befunde_aus(schlangen: list[dict]) -> list[dict]:
    """Die Entscheidungsregel, getrennt von der Messung — damit sie ohne Datenbestand
    prüfbar ist.

    ⚠ BEIDE HÄLFTEN SIND NÖTIG, und die zweite ist die, die man weglässt:
      · `wartend` falsy  → die Schlange ist leer. Sie steht still, weil sie FERTIG ist.
        Hier zu melden hiesse, jede abgearbeitete Schlange für immer anzuzeigen — und ein
        Wächter, der dauernd grundlos schreit, wird übergangen.
      · `wartend is None` → wir wissen es nicht (Abruf-Schlangen, s. `abruf_schlangen`).
        Nichtwissen ist kein Befund; es als einen zu werten wäre geraten, nicht gemessen.
    """
    return [s for s in schlangen
            if s.get("wartend") and (s.get("tage") or 0) > SCHWELLE_TAGE]


def pruefe() -> tuple[list[dict], list[dict]]:
    """(alle Schlangen, Befunde)."""
    alle = analyse_schlangen() + abruf_schlangen()
    return alle, befunde_aus(alle)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--offen", action="store_true", help="nur die Befunde")
    ap.add_argument("--alle", action="store_true", help="auch die Schlangen ohne Befund")
    a = ap.parse_args(argv)

    if not DATEN.exists():
        print("  ⓘ keine Datenebene — nicht prüfbar, kein Befund.")
        return 0

    alle, befunde = pruefe()
    if not a.offen and a.alle:
        for s in sorted(alle, key=lambda x: -(x.get("tage") or 0)):
            if "fehler" in s:
                print(f"   ⚠ {s['name']:<28} {s['fehler']}")
                continue
            w = s.get("wartend")
            wtxt = f"{w:>6} wartend" if w is not None else "       ?     "
            print(f"   {s['name']:<28} {wtxt} · zuletzt {s['bewegung']} "
                  f"({s['tage']} Tage)")

    if not befunde:
        if not a.offen:
            print(f"  ✓ {len(alle)} Warteschlangen, keine steht mit Arbeit still "
                  f"(Schwelle {SCHWELLE_TAGE} Tage).")
        return 0

    print("\n⚠ Befund: Arbeit liegt an, und es bewegt sich nichts.")
    for s in befunde:
        print(f"   {s['name']}: {s['wartend']} wartend, letzte Bewegung "
              f"{s['bewegung']} — {s['tage']} Tage her (Schwelle {SCHWELLE_TAGE}).")
        # ⚠ Der Grund steht schon in den Daten. Ihn hier NICHT auszugeben hiesse, den Leser
        # dieselbe Suche noch einmal machen zu lassen, die diese Sonde hervorgebracht hat.
        if s.get("grund"):
            print(f"     Der Arbeiter sagt selbst: {s['grund']}")
        elif s.get("halt"):
            print(f"     Haltegrund laut Arbeiter: {s['halt']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
