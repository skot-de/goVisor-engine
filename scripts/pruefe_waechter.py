#!/usr/bin/env python3
"""Welcher Waechter haengt an einem Kommentar statt am Code?

    python3 scripts/pruefe_waechter.py [--alle]

WOZU. Viele Tests hier pruefen Quelltext als Text: `assert "requireCronSecret" in quelle`.
Das ist eine legitime und im Haus uebliche Bauform — nur trifft sie auch **Prosa**. Steht
das gesuchte Wort in einem Kommentar, prueft der Waechter die Begruendung statt das
Verhalten, und niemand merkt es: er ist ja gruen.

WIE. Nicht durch Lesen des Testquelltexts (die Pfade stehen als Ausdruecke da), sondern
durch Zuhoeren: `Path.read_text` gibt waehrend des Laufs eine `str`-Unterklasse zurueck, die
ihren Pfad kennt und jedes `in` mitschreibt. Danach wird jedes getroffene Wort gegen die
ENTKOMMENTIERTE Fassung derselben Datei gehalten. Was dort fehlt, stand nur in Prosa.

WARUM DAS (NOCH) NICHT IM NACHTLAUF HAENGT — und warum das eine Entscheidung ist, kein
Versehen. Der erste Lauf am 2026-09-07 meldete 17 Treffer bei **einem** echten Fehler; der
Rest sind absichtliche Begruendungswaechter („`RUHEND` muss im Kopf stehen", „die gemessene
Gegenzahl gehoert in die Begruendung"). Mit der Liste `ERKLAERT` unten sind es 0 offene, das
Mass waere also scharf genug. Zwei Gruende sprechen trotzdem dagegen:

  · Es braucht einen VOLLEN Suite-Lauf (~90 s), weil es nur beim Ausfuehren zuhoeren kann.
  · Der Anlass ist selten. Blind wird ein Waechter durch eine UMBENENNUNG — und die gibt es
    nicht taeglich. Ein Wachposten, der 364 Tage im Jahr nichts findet, wird ueberlesen.

Damit es nicht dieselbe Leiche wird, gegen die es antritt, haelt `tests/test_verdrahtung.py::
test_die_erklaerten_waechter_gibt_es_noch` die Liste ehrlich (jeder Eintrag muss auf eine
Datei zeigen, die es gibt, und auf ein Wort, das dort steht), und `scripts/pruefe_bibel.py`
fuehrt ihre Laenge als pruefbare Aussage.

WANN MAN ES ALSO LAEUFT. Nach jeder **Umbenennung**. Das ist der Anlass, aus dem der eine
echte Treffer entstand: `loadDataFile` wurde am 2026-09-04 zu `ladeMitGrund`; der Name blieb
in `leadIndex.ts` nur noch in der Erklaerung stehen, warum die Datei NICHT von der Platte
liest. Ein Waechter, der ihn suchte, traf ab da ausschliesslich diesen Kommentar — haette
jemand den Index auf `readdir` umgebaut, waere er gruen geblieben. Dieselbe Umbenennung hatte
zwei Tage vorher schon Sonde 5 der Verdrahtungspruefung blind gemacht.

Und der zweite Anlass: bevor man einer bestehenden Wache traut, die man nicht selbst
geschrieben hat.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

# ── Bekannte, ABSICHTLICHE Begruendungswaechter ───────────────────────────────
# Diese Tests wollen ausdruecklich, dass eine Erklaerung dasteht — „eine Luecke, die niemand
# mehr sieht, wird zur Eigenschaft". Sie stehen hier als Code und nicht in einer Textdatei,
# damit ein geloeschter Eintrag auffaellt. Schluessel: (Datei-Ende, gesuchtes Wort).
ERKLAERT: dict[tuple[str, str], str] = {
    ("govisor/docsafety.py", "RUHEND"): "der Ruhezustand muss benannt sein (§12.2)",
    ("scripts/process_upload.py", "docsafety"): "die Schreibstelle nennt die fehlende Sperre",
    ("govisor/kennzahlen.py", "NEGATIVBEFUND"): "widerlegte Hypothese bleibt dokumentiert",
    ("govisor/docfetch_netserver.py", "aktuellste Version"): "Begruendung der Auswahlregel",
    ("govisor/docfetch_staatsanzeiger.py", "KEIN `expect_download`"): "Begruendung des Verzichts",
    ("govisor/docfetch_queue.py", "nur die Bekanntmachung"): "Begruendung der Abgrenzung",
    ("scripts/build_vorgaenge.py", "position` IST EIN ZEITRANG"): "Warnung vor Fehldeutung",
    ("scripts/export_stellenprofil.py", "schwächer, nie falsch"): "Begruendung des Rueckfalls",
    ("scripts/export_anforderungsprofil.py", "Korrelation 0,196"): "gemessene Zahl mit Datum",
    ("scripts/export_anforderungsprofil.py", "stabil"): "gemessene Aussage",
    ("scripts/pruefe_nuts_vorgabe.py", "110"): "die gemessene Gegenzahl",
    ("scripts/export_vorgaenge.py", "156.000"): "die Baugrenze als Zahl",
    ("scripts/export_vorgaenge.py", "0,6 %"): "gemessener Anteil",
    ("scripts/export_vorgaenge.py", "August 2026"): "Datum der Messung",
    ("web/lib/vorgangsakte.ts", "156.000"): "die Baugrenze als Zahl",
    # ⚠ Kein Befund, sondern eine Grenze des Werkzeugs: der Entkommentierer ersetzt
    # Escape-Folgen in Strings durch Leerzeichen, also verschwindet `\\x` aus `"\\x"`.
    ("web/app/api/blocks/route.ts", "\\\\x"): "Werkzeuggrenze: Escape in einem String",
}

LAUSCHER = '''
import json, os, sys
from pathlib import Path
sys.dont_write_bytecode = True
PROTOKOLL = []
_ORIG = Path.read_text
class Quelltext(str):
    __slots__ = ("pfad",)
    def __contains__(self, teil):
        treffer = str.__contains__(self, teil)
        if isinstance(teil, str):
            PROTOKOLL.append([self.pfad, teil, treffer])
        return treffer
def _read_text(self, *a, **kw):
    s = Quelltext(_ORIG(self, *a, **kw)); s.pfad = str(self); return s
Path.read_text = _read_text
def pytest_sessionfinish(session, exitstatus):
    Path(os.environ["LAUSCHER_ZIEL"]).write_text(json.dumps(PROTOKOLL), encoding="utf-8")
'''


def js_ohne_kommentar(s: str) -> str:
    """`//`- und `/* */`-Kommentare raus, Strings bleiben stehen."""
    raus, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c in "\"'`":
            q = c
            raus.append(c)
            i += 1
            while i < n:
                if s[i] == "\\":
                    raus.append("  ")
                    i += 2
                    continue
                raus.append(s[i])
                if s[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            while i < n and s[i] != "\n":
                raus.append(" ")
                i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "*":
            while i < n and not (s[i] == "*" and i + 1 < n and s[i + 1] == "/"):
                raus.append("\n" if s[i] == "\n" else " ")
                i += 1
            raus.append("  ")
            i += 2
            continue
        raus.append(c)
        i += 1
    return "".join(raus)


def py_ohne_kommentar(s: str) -> str:
    """`#`-Kommentare und Docstrings raus."""
    import io
    import tokenize
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(s).readline))
    except Exception:
        return s
    aus = [list(z) for z in s.splitlines(keepends=True)]
    vorher = None
    for t in toks:
        loeschen = t.type == tokenize.COMMENT
        if t.type == tokenize.STRING and (vorher is None or vorher.type in (
                tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL)):
            loeschen = True
        if loeschen:
            (r0, c0), (r1, c1) = t.start, t.end
            for r in range(r0 - 1, r1):
                a = c0 if r == r0 - 1 else 0
                b = c1 if r == r1 - 1 else len(aus[r])
                for k in range(a, min(b, len(aus[r]))):
                    if aus[r][k] != "\n":
                        aus[r][k] = " "
        if t.type not in (tokenize.NL, tokenize.COMMENT):
            vorher = t
    return "".join("".join(z) for z in aus)


def ohne_kommentar(pfad: str, s: str) -> str:
    if pfad.endswith((".js", ".mjs", ".ts", ".tsx", ".jsx", ".css")):
        return js_ohne_kommentar(s)
    if pfad.endswith(".py"):
        return py_ohne_kommentar(s)
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--alle", action="store_true", help="auch die erklaerten Faelle zeigen")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        plugin = pathlib.Path(tmp) / "lauscher.py"
        plugin.write_text(LAUSCHER, encoding="utf-8")
        ziel = pathlib.Path(tmp) / "protokoll.json"
        umwelt = {**os.environ, "LAUSCHER_ZIEL": str(ziel),
                  "PYTHONPATH": f"{tmp}:{os.environ.get('PYTHONPATH', '')}"}
        lauf = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-q", "-p", "lauscher"],
            cwd=ROOT, env=umwelt, capture_output=True, text=True)
        if not ziel.exists():
            print("Der Testlauf hat nichts protokolliert:")
            print(lauf.stdout[-2000:] or lauf.stderr[-2000:])
            return 2
        daten = json.loads(ziel.read_text(encoding="utf-8"))

    speicher: dict[str, str | None] = {}
    befunde, erklaert = [], []
    for pfad, wort, treffer in daten:
        if not treffer:
            continue
        p = pathlib.Path(pfad)
        # ⚠ NUR DER EIGENE QUELLTEXT. Tests legen Beispieldateien in pytest-Tempordnern an
        # und schreiben dieselbe Datei mehrfach neu; wer sie NACH dem Lauf liest, sieht den
        # letzten Stand und meldet jeden frueheren Treffer als „nur Prosa". Das waren neun
        # von neun Erstbefunden — ein Messfehler, kein Fund.
        if not p.exists() or not p.is_relative_to(ROOT):
            continue
        if pfad not in speicher:
            try:
                speicher[pfad] = ohne_kommentar(pfad, p.read_text(encoding="utf-8"))
            except Exception:
                speicher[pfad] = None
        code = speicher[pfad]
        if code is None or wort in code:
            continue
        kurz = pfad.split("C09_govisor/")[-1]
        grund = next((g for (d, w), g in ERKLAERT.items() if kurz.endswith(d) and w == wort), None)
        eintrag = (kurz, wort, grund)
        (erklaert if grund else befunde).append(eintrag)

    gesehen, offen = set(), []
    for e in befunde:
        if e[:2] in gesehen:
            continue
        gesehen.add(e[:2])
        offen.append(e)

    if args.alle:
        gezeigt = set()
        for kurz, wort, grund in erklaert:
            if (kurz, wort) in gezeigt:
                continue
            gezeigt.add((kurz, wort))
            print(f"  (erklaert) {kurz}: {wort!r} — {grund}")

    for kurz, wort, _ in offen:
        print(f"  ⚠ {kurz}: {wort!r} steht dort NUR in einem Kommentar")
        print("      Der Waechter, der es sucht, prueft die Begruendung, nicht das Verhalten.")

    zahl_erklaert = len({(k, w) for k, w, _ in erklaert})
    wort = "Waechter haengt" if len(offen) == 1 else "Waechter haengen"
    print(f"\n{len(offen)} {wort} an Prosa"
          + (f" · {zahl_erklaert} erklaert" if erklaert else ""))
    return 1 if offen else 0


if __name__ == "__main__":
    raise SystemExit(main())
