#!/usr/bin/env python3
"""Die gemessenen Zahlen in `docs/weiterentwicklung/sichtbarkeit-in-ki-antworten.md` nachziehen.

    python3 scripts/zahlen_nachziehen.py              # Blöcke neu schreiben
    python3 scripts/zahlen_nachziehen.py --pruefen    # nur melden, ob das Dokument veraltet ist

⚠ WARUM MARKIERTE BLÖCKE UND NICHT DAS GANZE DOKUMENT. `scripts/kpi_katalog.py` schreibt sein
Dokument komplett neu (`write_text`) — das geht dort, weil es nur eine Tabelle ist. Die
Marktanalyse besteht dagegen überwiegend aus Prosa und Strategie. Ein Erzeuger, der sie
überschreibt, löscht die Arbeit; einer, der sie anhängt, erzeugt Dubletten. Ersetzt werden
deshalb NUR die Bereiche zwischen den Markierungen.

⚠ UND WARUM DIE ZAHLEN AN GENAU EINER STELLE STEHEN. Dieselbe Zahl an zwei Orten im Dokument
wäre dieselbe Falle wie zwei Plan-Spalten in der Datenbank: eine wird nachgezogen, die andere
nicht, und niemand merkt welche. Die Prosa verweist deshalb auf den Block statt Ziffern zu
wiederholen; `--pruefen` schlägt an, wenn doch eine veraltete Ziffer daneben steht.

⚠ WAS BEWUSST NICHT ERZEUGT WIRD: die Behauptungen und Preise der Wettbewerber. Die stammen aus
einer Websuche, nicht aus unseren Daten — sie tragen ein Prüfdatum und veralten SICHTBAR. Ein
Mechanismus, der fremde Werbeaussagen nächtlich abgreift, wäre brüchig und würde zudem
Behauptungen wie Messungen aussehen lassen.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
ZIEL = WURZEL / "docs" / "weiterentwicklung" / "sichtbarkeit-in-ki-antworten.md"
LAENDER = ("DE", "AT", "CH", "LU")

# ⚠ Ein Datum vor der Gründung von TED ist keine Messung, sondern ein Parserfehler. Es wird
# als solcher gemeldet statt als frühester Bestand ausgegeben (AT trug am 2026-10-01
# `0001-01-01`). Die Schwelle ist bewusst grob: TED beginnt 1993, unser Bestand 2004.
FRUEHESTES_PLAUSIBEL = dt.date(1993, 1, 1)


def _de(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def messe() -> dict:
    import duckdb
    from govisor.config import Config
    from govisor import sources

    cfg = Config()
    con = duckdb.connect()
    je_land: dict[str, dict] = {}
    for land in LAENDER:
        muster = cfg.silver_table_glob("notices", land)
        if not glob.glob(muster):
            continue
        n, c, von, bis = con.execute(f"""
            SELECT COUNT(DISTINCT notice_id),
                   SUM(CASE WHEN notice_kind='can' THEN 1 ELSE 0 END),
                   MIN(publication_date), MAX(publication_date)
            FROM read_parquet('{muster}')""").fetchone()
        akte = WURZEL / "data" / "gold" / land / "vorgaenge.parquet"
        v = (con.execute(f"SELECT COUNT(*) FROM read_parquet('{akte.as_posix()}')").fetchone()[0]
             if akte.exists() else 0)
        je_land[land] = {"notices": n or 0, "awards": c or 0, "akten": v,
                         "von": von, "bis": bis,
                         "von_kaputt": bool(von) and von < FRUEHESTES_PLAUSIBEL}
    con.close()
    return {
        "je_land": je_land,
        "quellen": len(sources.REGISTRY),
        "stand": dt.date.today().isoformat(),
    }


def block_bestand(m: dict) -> str:
    jl = m["je_land"]
    kopf = "| | " + " | ".join(jl) + " | gesamt |"
    trenn = "|---|" + "".join("---:|" for _ in jl) + "---:|"
    def zeile(name: str, schl: str) -> str:
        werte = [_de(jl[l][schl]) for l in jl]
        return f"| {name} | " + " | ".join(werte) + f" | **{_de(sum(jl[l][schl] for l in jl))}** |"
    def ab() -> str:
        aus = []
        for l in jl:
            d = jl[l]
            aus.append("⚠ Datenfehler" if d["von_kaputt"] else str(d["von"] or "—"))
        return "| Bestand ab | " + " | ".join(aus) + " | |"
    zeilen = [kopf, trenn,
              zeile("Bekanntmachungen", "notices"),
              zeile("Zuschläge", "awards"),
              zeile("Vorgangsakten", "akten"),
              ab()]
    kaputt = [l for l, d in jl.items() if d["von_kaputt"]]
    if kaputt:
        zeilen += ["", f"⚠ {', '.join(kaputt)} trägt als frühestes `publication_date` einen Wert vor "
                      f"1993. Das ist ein Parserfehler, kein Bestand — er ist zu klären, bevor "
                      f"diese Tabelle öffentlich wird."]
    zeilen += ["", f"Quellen-Registry (`govisor/sources.py`): **{_de(m['quellen'])}** Einträge.",
               "", f"*Gemessen am {m['stand']} von `scripts/zahlen_nachziehen.py`. "
                   f"Nicht von Hand ändern — der nächste Lauf überschreibt es.*"]
    return "\n".join(zeilen)


BLOECKE = {"bestand": block_bestand}


def _ersetze(text: str, name: str, inhalt: str) -> str:
    a, e = f"<!-- ZAHLEN:{name} -->", f"<!-- /ZAHLEN:{name} -->"
    if a not in text or e not in text:
        raise SystemExit(f"✖ Markierung {a} … {e} fehlt in {ZIEL.name}. "
                         f"Ohne sie weiss der Erzeuger nicht, was er ersetzen darf.")
    i, j = text.index(a) + len(a), text.index(e)
    if j < i:
        raise SystemExit(f"✖ Markierungen für {name} stehen in falscher Reihenfolge.")
    return text[:i] + "\n" + inhalt + "\n" + text[j:]


def _verwaiste_ziffern(text: str, m: dict) -> list[str]:
    """Steht eine der erzeugten Zahlen NOCH EINMAL ausserhalb ihres Blocks?

    ⚠ Das ist die eigentliche Falle an diesem Mechanismus: der Block wird nachgezogen, eine
    Wiederholung in der Prosa nicht, und das Dokument widerspricht sich selbst.
    """
    a, e = "<!-- ZAHLEN:bestand -->", "<!-- /ZAHLEN:bestand -->"
    ausserhalb = text[:text.index(a)] + text[text.index(e):] if a in text and e in text else text
    ausserhalb = "\n".join(z for z in ausserhalb.splitlines() if not z.lstrip().startswith(">"))
    jl = m["je_land"]
    kandidaten = {_de(sum(jl[l][s] for l in jl)) for s in ("notices", "awards", "akten")}
    kandidaten |= {_de(jl[l][s]) for l in jl for s in ("notices", "awards", "akten")}
    return sorted(z for z in kandidaten if len(z) >= 7 and z in ausserhalb)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pruefen", action="store_true",
                    help="nicht schreiben, nur melden, ob das Dokument veraltet ist")
    a = ap.parse_args()
    if not ZIEL.exists():
        print(f"✖ {ZIEL.relative_to(WURZEL)} fehlt.")
        return 2

    m = messe()
    if not m["je_land"]:
        print("✖ keine Silber-Ebene gefunden — es wird NICHTS geschrieben "
              "(ein leerer Block wäre schlimmer als ein veralteter).")
        return 3

    alt = ZIEL.read_text(encoding="utf-8")
    neu = alt
    for name, bauer in BLOECKE.items():
        neu = _ersetze(neu, name, bauer(m))

    waisen = _verwaiste_ziffern(neu, m)
    if waisen:
        print("⚠ Dieselbe Zahl steht auch ausserhalb des Blocks — sie wird dort NICHT "
              "nachgezogen:\n    " + "\n    ".join(waisen))

    # Beim Vergleich das Messdatum ausklammern: es aendert sich taeglich und sagt nichts
    # darueber, ob die ZAHLEN veraltet sind.
    ohne_datum = lambda t: re.sub(r"\*Gemessen am \d{4}-\d{2}-\d{2}", "*Gemessen am TAG", t)
    veraltet = ohne_datum(alt) != ohne_datum(neu)

    if a.pruefen:
        if veraltet:
            print("✖ Die Zahlen im Dokument stimmen nicht mehr. "
                  "Nachziehen: python3 scripts/zahlen_nachziehen.py")
            return 1
        print(f"  Zahlen aktuell ({len(m['je_land'])} Länder, "
              f"{_de(sum(d['notices'] for d in m['je_land'].values()))} Bekanntmachungen).")
        return 1 if waisen else 0

    if neu == alt:
        print("  unverändert — nichts zu schreiben.")
        return 1 if waisen else 0
    ZIEL.write_text(neu, encoding="utf-8")
    print(f"  ✓ {ZIEL.relative_to(WURZEL)} nachgezogen "
          f"({_de(sum(d['notices'] for d in m['je_land'].values()))} Bekanntmachungen, "
          f"{m['quellen']} Quellen).")
    return 1 if waisen else 0


if __name__ == "__main__":
    sys.exit(main())
