#!/usr/bin/env python3
"""Welche Auswertungen wuerde ein Nachlauf ueberhaupt veraendern — und was kostet er?

⚠ WARUM ES DIESE ZAHL BRAUCHT. Nach jeder Aenderung an `govisor/doctypes.py` liegt die
Frage auf dem Tisch: „muessen wir die alten Auswertungen neu rechnen?" Die naheliegende
Antwort ist die Zahl der veralteten Auswertungen — und die ist als Entscheidungsgrundlage
falsch, weil sie eine OBERGRENZE ist. Am 2026-09-21 waren es 3.344 veraltete Auswertungen
(43 bis 71 USD), aber nur 651 davon enthalten ueberhaupt eine Datei, die heute anders
eingeordnet wuerde. Ein Nachlauf der uebrigen 2.693 kostet Geld und aendert nichts.

⚠ `other_documents` IST DAS PROTOKOLL DES ALTEN KLASSIFIKATORS. Deshalb braucht diese
Rechnung keine alte Programmfassung: was dort steht, hat der Klassifikator von damals
aussortiert. Steht ein Name heute in einem AUSWERTUNG-Typ, wuerde ein Nachlauf diese Datei
lesen — genau das ist der Unterschied, den man bezahlt.

⚠ NUR AM NAMEN GERECHNET, also eine UNTERGRENZE. Die Produktion zieht zusaetzlich eine
Inhaltsprobe heran, und die kann nur hinzufuegen (`classify` entscheidet erst am Namen und
faellt nur bei „sonstiges" auf den Inhalt zurueck).

⚠ DIE TRENNUNG NACH `analysiert_am` IST DER EIGENTLICHE BEFUND. Auswertungen OHNE das Feld
stammen aus der Zeit vor den Doktyp-Regeln vom 21./25.08.2026; bei ihnen wirken zwei
Ursachen zusammen. Auswertungen MIT dem Feld koennen nur von einer Regel betroffen sein,
die SEITDEM dazugekommen ist — stehen dort viele, ist die juengste Aenderung der Grund,
nicht die Veralterung.

Aufruf:  python3 scripts/nachlauf_kandidaten.py [--liste <datei>]
"""
from __future__ import annotations

import collections
import json
import pathlib
import statistics as st
import sys

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
from govisor import doctypes  # noqa: E402

ANALYSEN = WURZEL / "web" / "data" / "doc-analysis"
KOSTENBUCH = WURZEL / "data" / "llm_kosten.jsonl"
AUSWERTUNG = set(("fragenantworten",) + tuple(doctypes.PRIORITY))


def kosten_je_vorgang() -> tuple[float, float]:
    """Median und Mittel der echten Analysekosten je Vorgang, aus dem Kostenbuch."""
    if not KOSTENBUCH.exists():
        return 0.0, 0.0
    je: dict[str, float] = collections.defaultdict(float)
    with KOSTENBUCH.open(encoding="utf-8") as f:
        for zeile in f:
            try:
                d = json.loads(zeile)
            except Exception:
                continue
            if d.get("zweck") == "analyse":
                je[d.get("vorgang")] += float(d.get("kosten_usd") or 0)
    werte = sorted(je.values())
    return (st.median(werte), sum(werte) / len(werte)) if werte else (0.0, 0.0)


def main() -> int:
    if not ANALYSEN.is_dir():
        print("  (keine Auswertungen unter web/data/doc-analysis)")
        return 2
    gruppen: dict[str, list[str]] = {"alt": [], "neu": []}
    gesamt = collections.Counter()
    dateien = collections.Counter()
    for f in ANALYSEN.glob("*.json"):
        try:
            a = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        schiene = "neu" if a.get("analysiert_am") else "alt"
        gesamt[schiene] += 1
        n = sum(1 for name in (a.get("other_documents") or [])
                if doctypes.classify(name) in AUSWERTUNG)
        if n:
            gruppen[schiene].append(f.stem)
            dateien[schiene] += n

    med, mit = kosten_je_vorgang()
    print(f"  Auswertungen insgesamt: {sum(gesamt.values()):,}\n")
    for schiene, label in (("alt", "ohne analysiert_am (vor den Regeln vom 21./25.08.)"),
                           ("neu", "mit analysiert_am")):
        n, g = len(gruppen[schiene]), gesamt[schiene]
        print(f"  {label}")
        print(f"    {g:>6,} Auswertungen · davon betroffen {n:,} ({n*100//max(g,1)} %) "
              f"· {dateien[schiene]:,} Dateien")
        if med:
            print(f"    Nachlauf: {med*n:6.2f} $ bis {mit*n:6.2f} $")
    n = len(gruppen["alt"]) + len(gruppen["neu"])
    print(f"\n  zusammen {n:,} Vorgaenge"
          + (f" · {med*n:.2f} $ bis {mit*n:.2f} $" if med else ""))
    print("  ⚠ Untergrenze: nur am Dateinamen gerechnet, die Inhaltsprobe kann nur "
          "hinzufuegen.")

    if "--liste" in sys.argv:
        ziel = pathlib.Path(sys.argv[sys.argv.index("--liste") + 1])
        ziel.write_text("\n".join(gruppen["alt"] + gruppen["neu"]) + "\n", encoding="utf-8")
        print(f"  Kennungen geschrieben: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
