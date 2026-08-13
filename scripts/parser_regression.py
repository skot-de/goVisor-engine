"""Regressions-Stichprobe für den Dokument-Parser: einfrieren, dann vergleichen.

**Wozu.** Jede neue Regel kann bestehende Ergebnisse verändern — nicht nur ergänzen. Ein
weiter gefasster Ausdruck greift plötzlich an einer Stelle, an der vorher ein anderer griff,
und liefert dort einen anderen Wert. Ohne festgehaltenen Vorher-Stand merkt das niemand: die
Zahlen sehen weiterhin plausibel aus, sie sind nur andere.

Das ist die Bedingung dafür, dass der Kreislauf aus ``parser_gaps.py`` überhaupt tragbar ist.
Lücken finden und Regeln ergänzen darf man nur, wenn man sieht, was die Ergänzung anrichtet.

**Zwei Befehle**

    python3 scripts/parser_regression.py freeze    # aktuellen Stand als Erwartung sichern
    python3 scripts/parser_regression.py check     # aktuellen Stand dagegen prüfen

``check`` unterscheidet drei Fälle und bewertet sie verschieden:

* **neu**      — vorher ``None``, jetzt ein Wert. Das ist der Normalfall beim Ergänzen. Gut.
* **entfallen**— vorher ein Wert, jetzt ``None``. Verdächtig: eine Regel hat aufgehört zu greifen.
* **geändert** — beide Male ein Wert, aber verschieden. **Das ist der gefährliche Fall.**

Exit-Code 1 bei „entfallen" oder „geändert" — damit ein Lauf im Tageslauf oder in CI stolpert,
statt still durchzulaufen. „neu" allein ist nie ein Fehler.

Die Stichprobe liegt als JSON neben den Daten (``data/docs/<C>/parser_baseline.json``) und
enthält NUR die extrahierten Werte, keinen Dokumenttext — sie ist damit klein und
gefahrlos versionierbar.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import docsignals  # noqa: E402

# Nur die Nutzwerte vergleichen. Die Belege (`*_evidence`) sind Fundstellen-Schnipsel: sie
# ändern sich schon, wenn ein Ausdruck ein Zeichen weiter links greift, ohne dass sich am
# Ergebnis etwas ändert. Sie mitzuvergleichen erzeugte Fehlalarm bei jeder Regeländerung.
_IGNORIEREN = ("_evidence",)


def _werte(sig: dict) -> dict:
    return {k: v for k, v in sorted(sig.items())
            if not any(k.endswith(x) for x in _IGNORIEREN) and v not in (None, [], {})}


def _stichprobe(country: str, n: int) -> dict[str, dict]:
    import duckdb

    src = ROOT / "data" / "docs" / country / "doc_text.parquet"
    if not src.exists():
        raise SystemExit(f"kein {src}")
    con = duckdb.connect()
    # Deterministisch: nach notice_id sortiert, nicht zufällig. Ein Zufallssample wäre bei
    # jedem Einfrieren ein anderes und damit als Vergleichsbasis wertlos.
    rows = con.execute(
        f"""SELECT notice_id, string_agg(text, ' ' ORDER BY file) AS full
            FROM read_parquet('{src.as_posix()}') WHERE status='ok'
            GROUP BY notice_id ORDER BY notice_id LIMIT {int(n)}""").fetchall()
    return {nid: _werte(docsignals.extract_signals(t or "")) for nid, t in rows}


def freeze(country: str, n: int) -> int:
    stand = _stichprobe(country, n)
    ziel = ROOT / "data" / "docs" / country / "parser_baseline.json"
    ziel.write_text(json.dumps(stand, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    felder = sum(len(v) for v in stand.values())
    print(f"Eingefroren: {len(stand)} Vorgänge, {felder} Werte → {ziel.relative_to(ROOT)}")
    return 0


def check(country: str, n: int) -> int:
    ziel = ROOT / "data" / "docs" / country / "parser_baseline.json"
    if not ziel.exists():
        print(f"Keine Baseline ({ziel.relative_to(ROOT)}). Erst `freeze` laufen lassen.")
        return 1
    alt = json.loads(ziel.read_text())
    neu = _stichprobe(country, n)

    neu_w, entfallen, geaendert = [], [], []
    for nid in sorted(set(alt) | set(neu)):
        a, b = alt.get(nid, {}), neu.get(nid, {})
        for feld in sorted(set(a) | set(b)):
            va, vb = a.get(feld), b.get(feld)
            if va == vb:
                continue
            if va is None:
                neu_w.append((nid, feld, vb))
            elif vb is None:
                entfallen.append((nid, feld, va))
            else:
                geaendert.append((nid, feld, va, vb))

    print(f"Regressionsprüfung {country} — {len(neu)} Vorgänge\n")
    print(f"  neu:       {len(neu_w):>4}   (vorher nichts, jetzt ein Wert — erwünscht)")
    print(f"  entfallen: {len(entfallen):>4}   (Regel greift nicht mehr)")
    print(f"  geändert:  {len(geaendert):>4}   (anderer Wert als vorher)")
    for nid, feld, va, vb in geaendert[:12]:
        print(f"     ⚠ {nid} · {feld}: {va!r} → {vb!r}")
    for nid, feld, va in entfallen[:8]:
        print(f"     ✖ {nid} · {feld}: {va!r} → nichts")
    if neu_w[:6]:
        print("  Beispiele neu:")
        for nid, feld, vb in neu_w[:6]:
            print(f"     + {nid} · {feld}: {vb!r}")

    if entfallen or geaendert:
        print("\nAbweichung. Wenn sie beabsichtigt ist, `freeze` erneut laufen lassen —"
              " bewusst, nicht beiläufig.")
        return 1
    print("\nKeine Regression.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("befehl", choices=("freeze", "check"))
    ap.add_argument("--country", default="DE")
    ap.add_argument("-n", type=int, default=120, help="Vorgänge in der Stichprobe")
    a = ap.parse_args()
    sys.exit(freeze(a.country, a.n) if a.befehl == "freeze" else check(a.country, a.n))
