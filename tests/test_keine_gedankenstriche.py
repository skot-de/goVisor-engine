"""Oberflaechentexte ohne Gedankenstrich — Svens Vorgabe vom 2026-08-16.

⚠ WARUM ES DIESE DATEI GIBT. Die Regel wurde einmal app-weit durchgesetzt (Commit
`e001ecf`, 300 Texte in 35 Dateien, beide Sprachkataloge) und war am 2026-09-18 wieder
**90-mal** verletzt. Nicht aus Nachlaessigkeit: der Gedankenstrich ist eine
Schreibgewohnheit, und eine Gewohnheit kommt zurueck, wenn nichts sie bemerkt. Eine
Vorgabe ohne Waechter ist eine Bitte, keine Regel.

⚠ WAS BEWUSST STEHEN BLEIBT — ein pauschales Verbot wuerde jedes davon kaputtmachen:

  * **Platzhalter** `"—"` fuer „kein Wert" (112 Stellen). Das ist ein Layout-Zeichen in
    einer Tabellenzelle, kein Text. Durch „bis" oder ein Komma ersetzt, stuende in jeder
    leeren Zelle Unsinn.
  * **Logzeilen** (`console.*`, `[data] …`). Entwicklerausgabe, keine Oberflaeche.
  * **Regexe**, die das Logformat lesen: `/^  ⏱ (.+?) — (\\d+)s$/` in
    `app/api/intern/lauf/route.ts`. Wer hier den Strich ersetzt, bringt dem Laufbericht
    bei, seine eigenen Schrittdauern nicht mehr zu finden — und zwar lautlos.
  * **Kommentare**. 1.307 der 1.534 Striche im Frontend stehen dort. Sie sind Begruendung,
    keine Oberflaeche.
  * Striche **innerhalb von Vergabedaten** („Dresden Hbf – Werdau" ist ein Vertragstitel).

Die drei Ersetzungsregeln stehen in der Auto-Memory `govisor-keine-gedankenstriche`.
"""
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
WEB = WURZEL / "web"
STRICH = re.compile(r"[‒–—―]")
WORT = re.compile(r"[A-Za-zÄÖÜäöüß]")


def _ohne_kommentar(s: str) -> str:
    """`//` und `/* */` raus. Die Laenge bleibt erhalten, damit Zeilennummern stimmen."""
    raus, i, n = [], 0, len(s)
    while i < n:
        if s[i] == "/" and i + 1 < n and s[i + 1] == "/":
            while i < n and s[i] != "\n":
                raus.append(" ")
                i += 1
            continue
        if s[i] == "/" and i + 1 < n and s[i + 1] == "*":
            while i < n and not (s[i] == "*" and i + 1 < n and s[i + 1] == "/"):
                raus.append("\n" if s[i] == "\n" else " ")
                i += 1
            raus.append("  ")
            i += 2
            continue
        raus.append(s[i])
        i += 1
    return "".join(raus)


def _klasse(code: str, i: int) -> str:
    """Wozu gehoert dieser Strich? Nur `text` und `bereich` sind Verstoesse."""
    vor, nach = code[max(0, i - 90):i], code[i + 1:i + 90]
    zeile = code[code.rfind("\n", 0, i) + 1:code.find("\n", i)]
    if re.search(r'["\'`]\s*$', vor) and re.match(r'\s*["\'`]', nach):
        return "platzhalter"
    if "console." in zeile or re.search(r"\[(data|profil|suppliers|fristen|lead-branche)\]", zeile):
        return "log"
    if re.search(r"\.match\(|new RegExp", zeile):
        return "regex"
    if vor.rstrip().endswith(">") and nach.lstrip().startswith("<"):
        return "platzhalter"
    if re.search(r"(\d|\}|\))\s*$", vor) and re.match(r"\s*(\d|\$\{|\w+\()", nach):
        return "bereich"
    if not (WORT.search(vor[-30:]) and WORT.search(nach[:30])):
        return "platzhalter"
    return "text"


def _dateien():
    for p in sorted(WEB.rglob("*")):
        if p.suffix in (".js", ".ts", ".tsx") and "node_modules" not in p.parts \
                and ".next" not in p.parts:
            yield p


def test_kein_gedankenstrich_in_oberflaechentexten():
    """Zwischen zwei Satzteilen gehoert ein Komma oder ein Punkt, kein Strich."""
    funde = []
    for p in _dateien():
        roh = p.read_text(encoding="utf-8", errors="replace")
        if not STRICH.search(roh):
            continue
        code = _ohne_kommentar(roh)
        for m in STRICH.finditer(code):
            if _klasse(code, m.start()) == "text":
                zeile = code[:m.start()].count("\n") + 1
                stelle = code[max(0, m.start() - 44):m.start() + 44].replace("\n", " ")
                funde.append(f"{p.relative_to(WURZEL)}:{zeile}  …{stelle}…")
    assert not funde, (
        f"{len(funde)} Oberflaechentexte tragen einen Gedankenstrich. Regeln: Komma, "
        f"oder Punkt wenn der Nachsatz selbst ein Komma traegt, nie ein Punkt vor "
        f"und/oder/aber/denn/sondern.\n  " + "\n  ".join(funde[:12]))


def test_kein_bis_strich_in_wertebereichen():
    """⚠ Ein Bis-Strich ist kein Gedankenstrich und braucht deshalb eine ANDERE Ersetzung:
    `5–10` wird `5 bis 10`, nicht `5, 10`. Beim Durchgang am 2026-09-18 haben genau diese
    dreizehn Stellen die Regelfunktion in die Irre gefuehrt — „500k–1,3M €" waere als
    Fliesstext zu „500k. 1,3M €" geworden."""
    funde = []
    for p in _dateien():
        roh = p.read_text(encoding="utf-8", errors="replace")
        if not STRICH.search(roh):
            continue
        code = _ohne_kommentar(roh)
        for m in STRICH.finditer(code):
            if _klasse(code, m.start()) == "bereich":
                zeile = code[:m.start()].count("\n") + 1
                stelle = code[max(0, m.start() - 44):m.start() + 44].replace("\n", " ")
                funde.append(f"{p.relative_to(WURZEL)}:{zeile}  …{stelle}…")
    assert not funde, (
        f"{len(funde)} Wertebereiche mit Bis-Strich. Die Ersetzung lautet bis, nicht Komma.\n  "
        + "\n  ".join(funde[:12]))


def test_die_sprachkataloge_tragen_keine_gedankenstriche():
    """Der deutsche Satz IST der Schluessel — ein Strich im Schluessel heisst, dass die
    deutsche Fassung einen traegt oder getragen hat."""
    import json
    for name in ("flat.en.json", "flat.fr.json"):
        d = json.loads((WEB / "lib" / "i18n" / "messages" / name).read_text(encoding="utf-8"))
        quelle = "".join(p.read_text(encoding="utf-8", errors="replace") for p in _dateien())
        # ⚠ NUR LEBENDE Schluessel. Waisen (deutscher Text nicht mehr im Quelltext) sind
        #   ein eigenes Problem — 101 Stueck am 2026-09-18 — und gehoeren nicht in diesen
        #   Test, sonst bewacht er zwei Dinge und niemand weiss, welches gebrochen ist.
        schlimm = [k for k in d if STRICH.search(k) and k in quelle]
        assert not schlimm, (
            f"{name}: {len(schlimm)} lebende Schluessel mit Gedankenstrich.\n  "
            + "\n  ".join(k[:100] for k in schlimm[:8]))
