#!/usr/bin/env python3
"""Stand der laufenden Pruefung: `fenster` gegen die Kontrollgruppe `anfang`.

Kostet nichts — die Zahlen fallen im Normalbetrieb an. Aufruf:
    python3 scripts/lb_auswahl_stand.py

⚠ **Das ist KEIN gepaarter Vergleich.** Jeder Vorgang bekommt genau ein Verfahren (stabil
ueber den Hash seiner Kennung, s. `govisor.lbauswahl.verfahren_fuer`). Zwei Gruppen
verschiedener Vergaben zu vergleichen ist schwaecher als derselbe Vorgang zweimal — dafuer
kostet es keinen zweiten Modellaufruf. Bei kleinen Zahlen sagt das Ergebnis wenig; die
Aussagekraft waechst mit den Wochen.

Der bezahlte Vorversuch (2026-08-22, 47 gepaarte Dreiergruppen) ergab:
    anfang   30,5 Eintraege je Vorgang · 18,0 % Verwerfungsquote
    fenster  33,3 Eintraege je Vorgang · 10,4 % Verwerfungsquote
gepaarte Vorzeichentests aber ohne Signifikanz (p ≈ 0,41 bzw. 1,00).
"""
from __future__ import annotations

import json
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUELLE = ROOT / "web" / "data" / "doc-analysis.json"


def _u(k: int, n: int) -> float:
    """Grobe Signifikanz zweier unabhaengiger Anteile (Normalnaeherung)."""
    return 0.0 if n == 0 else k / n


def main() -> int:
    if not QUELLE.exists():
        print(f"FEHLT: {QUELLE}")
        return 1
    d = json.loads(QUELLE.read_text(encoding="utf-8"))
    gruppen: dict[str, list[dict]] = defaultdict(list)
    for v in d.values():
        if not isinstance(v, dict):
            continue
        art = v.get("lb_auswahl")
        if art in ("anfang", "fenster", "gemischt"):
            gruppen[art].append(v)

    if not gruppen:
        print("Noch keine Vorgänge mit vermerktem Auswahlverfahren.")
        print("Das Feld `lb_auswahl` entsteht erst bei NEUEN Analysen — bestehende")
        print("Ergebnisse tragen es nicht. Die Prüfung beginnt mit dem nächsten Lauf.")
        return 0

    print(f"  {'Verfahren':<10} {'Vorgänge':>9} {'Einträge Ø':>11} {'verworfen Ø':>12} "
          f"{'Verwerfungsquote':>17}")
    stand = {}
    for art in ("anfang", "fenster", "gemischt"):
        g = gruppen.get(art)
        if not g:
            continue
        items = [len(x.get("checklist", [])) for x in g]
        rej = [x.get("rejected_items", 0) or 0 for x in g]
        quote = sum(rej) / max(1, sum(items) + sum(rej))
        stand[art] = (len(g), st.mean(items), st.mean(rej), quote)
        print(f"  {art:<10} {len(g):>9,} {st.mean(items):>11.1f} {st.mean(rej):>12.1f} "
              f"{100*quote:>16.1f} %")

    if "anfang" in stand and "fenster" in stand:
        na, nf = stand["anfang"][0], stand["fenster"][0]
        print()
        if min(na, nf) < 30:
            print(f"  ⚠ Zu wenig Material für eine Aussage (Kontrolle {na}, Behandlung {nf}).")
            print("    Aussagekräftig wird es ab etwa 30 Vorgängen je Gruppe.")
        else:
            d_items = stand["fenster"][1] - stand["anfang"][1]
            d_quote = stand["fenster"][3] - stand["anfang"][3]
            print(f"  fenster gegenüber anfang: {d_items:+.1f} Einträge je Vorgang · "
                  f"Verwerfungsquote {100*d_quote:+.1f} pp")
            print("  ⚠ Gruppenvergleich, nicht gepaart — er trägt weniger als der Vorversuch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
