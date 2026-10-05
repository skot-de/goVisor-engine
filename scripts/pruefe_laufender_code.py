#!/usr/bin/env python3
"""Wächter: läuft nachts der Code, den wir gebaut haben?

⚠ WARUM ES DIESE SONDE GIBT. Am 2026-10-05 standen zwei Prüfungen rot und meldeten, der
KMU-Anteil der Schweiz sei wieder zu einer Konstanten entartet — demselben Defekt, der am
2026-09-01 gefunden und behoben worden war. Er war aber nicht zurückgekehrt. **Er war nie
abgestellt, wo es zählt.**

Der Fix lag auf zwei Zweigen (`claude/distracted-lichterman-183f62`, `pipeline/entity-wachen`).
Der Nachtlauf fährt den **Haupt-Baum**, und der stand auf einem dritten Zweig. Dort gab es das
Wort `a36` nicht ein einziges Mal. Nacht für Nacht schrieb also der alte Code in
`web/data/strategie.json` — und weil `web/data` und `data` in jedem Arbeitsbaum **Symlinks in
den Haupt-Baum** sind, lasen die Prüfungen im Arbeitsbaum genau diese fremde Ausgabe.

Die bittere Pointe: `scripts/pruefe_streuung.py`, die Sonde, die diesen Defekt melden soll,
**gibt es im Nachtlauf-Baum als Datei nicht**. Dort laufen zwölf Sonden, sie ist keine davon.
Der Wächter gegen die stille Kennzahl war selbst still.

DER DETEKTOR. Für jede Datei, die der Nachtlauf AUSFÜHRT, wird verglichen, ob dieser
Arbeitsbaum dieselbe Fassung hat. Kein git, keine Zweige, keine Zusammenführungs-Logik —
nur: ist die Datei, die heute Nacht läuft, dieselbe wie die, gegen die wir hier prüfen?

⚠ **Nicht jeder Unterschied ist ein Befund.** Ein Arbeitsbaum, in dem gerade gebaut wird,
weicht naturgemäss ab; das ist der Zweck eines Arbeitsbaums. Ein Befund ist nur, wo eine
**geteilte Ausgabe** betroffen ist: eine Datei, die der Nachtlauf schreibt und die Prüfungen
hier lesen. Dort — und nur dort — ist die Abweichung eine Lüge über das, was geprüft wird.
Diese Paare stehen unten in `ERZEUGER`, als Code und nicht als Textdatei.

    python3 scripts/pruefe_laufender_code.py [--offen] [--alle]

Rückgabe 1, wenn ein Erzeuger einer geteilten Ausgabe abweicht oder im Nachtlauf-Baum fehlt.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import plistlib
import sys

HIER = pathlib.Path(__file__).resolve().parent.parent

# Geteilte Ausgabe → das Skript, das sie erzeugt.
#
# ⚠ Hier gehört ein Paar hinein, sobald eine Prüfung eine Datei liest, die der Nachtlauf
# schreibt. Das ist die ganze Bedingung — nicht „wichtige Datei", sondern „wird hier geprüft
# und dort erzeugt". Fehlt das Paar, ist der Fehlschlag der Prüfung irreführend: er beschuldigt
# die Kennzahl, obwohl der Erzeuger ein anderer ist.
ERZEUGER = {
    "web/data/strategie.json": "scripts/export_strategie.py",
    "data/reference/waehrungskurse.json": "scripts/fetch_ezb_kurse.py",
}

# Was überhaupt verglichen wird: alles, was der Nachtlauf ausführen kann.
ORDNER = ("scripts", "govisor")
ENDUNGEN = (".py", ".sh")

PLIST = (pathlib.Path.home() / "Library" / "LaunchAgents"
         / "de.skot.govisor.daily.plist")


def nachtlauf_baum() -> tuple[pathlib.Path | None, str]:
    """Der Baum, in dem der Tageslauf wirklich läuft — aus dem launchd-Eintrag.

    ⚠ NICHT geraten. Welcher Baum nachts fährt, ist genau die Frage, um die es hier geht;
    sie aus dem eigenen Pfad abzuleiten hiesse, die Antwort vorauszusetzen. Steht kein
    launchd-Eintrag da, sagt die Sonde das und misst nichts.
    """
    if not PLIST.exists():
        return None, f"kein launchd-Eintrag unter {PLIST}"
    try:
        d = plistlib.loads(PLIST.read_bytes())
    except Exception as e:                                           # noqa: BLE001
        return None, f"{PLIST.name} nicht lesbar: {type(e).__name__}"
    wd = d.get("WorkingDirectory")
    if not wd:
        return None, f"{PLIST.name} nennt kein WorkingDirectory"
    p = pathlib.Path(wd)
    return (p, "") if p.is_dir() else (None, f"WorkingDirectory {wd} gibt es nicht")


def _hash(p: pathlib.Path) -> str | None:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def vergleiche(hier: pathlib.Path, dort: pathlib.Path) -> dict:
    """Alle ausführbaren Dateien beider Bäume gegeneinander."""
    anders, fehlt, gleich = [], [], 0
    for ordner in ORDNER:
        wurzel = hier / ordner
        if not wurzel.is_dir():
            continue
        for p in sorted(wurzel.rglob("*")):
            if p.suffix not in ENDUNGEN or not p.is_file():
                continue
            rel = str(p.relative_to(hier))
            a, b = _hash(p), _hash(dort / rel)
            if b is None:
                fehlt.append(rel)
            elif a != b:
                anders.append(rel)
            else:
                gleich += 1
    return {"anders": anders, "fehlt": fehlt, "gleich": gleich}


def befunde(ergebnis: dict) -> list[dict]:
    """Nur die Erzeuger geteilter Ausgaben sind ein Befund."""
    betroffen = set(ergebnis["anders"]) | set(ergebnis["fehlt"])
    aus = []
    for ausgabe, skript in sorted(ERZEUGER.items()):
        if skript in betroffen:
            aus.append({"ausgabe": ausgabe, "skript": skript,
                        "art": "fehlt" if skript in ergebnis["fehlt"] else "weicht ab"})
    return aus


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--offen", action="store_true", help="nur die Befunde")
    ap.add_argument("--alle", action="store_true",
                    help="auch die Abweichungen, die keine geteilte Ausgabe betreffen")
    a = ap.parse_args(argv)

    dort, grund = nachtlauf_baum()
    if dort is None:
        print(f"  ⓘ {grund} — nicht prüfbar, kein Befund.")
        return 0
    if dort.resolve() == HIER.resolve():
        if not a.offen:
            print("  ✓ Dieser Baum IST der Nachtlauf-Baum — nichts zu vergleichen.")
        return 0

    e = vergleiche(HIER, dort)
    b = befunde(e)

    if not a.offen:
        print(f"── Nachtlauf-Baum: {dort}")
        print(f"── dieser Baum   : {HIER}")
        print(f"   {e['gleich']} Dateien gleich · {len(e['anders'])} abweichend · "
              f"{len(e['fehlt'])} dort nicht vorhanden")
        if a.alle:
            for titel, liste in (("weicht ab", e["anders"]), ("fehlt dort", e["fehlt"])):
                for x in liste:
                    print(f"     {titel:<11} {x}")

    if not b:
        if not a.offen:
            print("  ✓ Kein Erzeuger einer geteilten Ausgabe betroffen.")
        return 0

    print("\n⚠ Befund: der Nachtlauf erzeugt geteilte Dateien mit ANDEREM Code als hier geprüft.")
    for x in b:
        print(f"   {x['ausgabe']}")
        print(f"     erzeugt von {x['skript']} — dort {x['art']}")
    print("\n   Folge: eine Prüfung, die diese Ausgabe liest, misst FREMDEN Code. Schlägt sie"
          "\n   an, ist die Ursache womöglich nicht die Kennzahl, sondern dieser Unterschied."
          "\n   `web/data` und `data` sind in jedem Arbeitsbaum Symlinks in den Haupt-Baum.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
