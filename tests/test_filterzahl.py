"""Sagt die Oberflaeche, dass NICHTS filtert?

⚠ GEMELDET AM 2026-09-18. Sven sah eine Liste an und fragte „wo sehe ich nun die aktiven
filter?" — ohne gefiltert zu haben. Das Ausbleiben jeder Anzeige war also richtig und
trotzdem keine Auskunft: „kein Filter gesetzt" und „die Anzeige fehlt" sahen gleich aus.

Nachgeprueft war die Mechanik in Ordnung. Die Sonde `pruefe-filtermarken.mjs` faehrt 22
Filterarten durch und jede erzeugt und loest ihre Marke; der Marken-Block liegt in der
Listenansicht direkt ueber der Tabelle. Es fehlte kein Code, es fehlte ein ZUSTAND.

Entschieden: die Zahl am Filter-Knopf steht immer da, auch als Null. Die Marken-Reihe
ueber der Tabelle bleibt bedingt — sie zaehlt nicht, sie listet auf, und eine Reihe, die
in den meisten Faellen „nichts" meldet, ist eine Zeile zu viel. Wir hatten am selben Tag
gerade zwanzig Zeilenrahmen weggeraeumt.
"""
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SHELL = WURZEL / "web" / "components" / "explorer" / "ExplorerShell.tsx"
GLOBALS = WURZEL / "web" / "app" / "globals.css"


def _ohne_kommentar(s: str) -> str:
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


def test_die_zahl_steht_auch_bei_null_da():
    """Der Punkt der Aenderung. Ein `advCount(adv) ? … : null` waere der alte Zustand."""
    code = _ohne_kommentar(SHELL.read_text(encoding="utf-8"))
    i = code.index('className="filt-n"')
    davor = code[max(0, i - 160):i]
    assert "? <span" not in davor and "?<span" not in davor, (
        "die Zahl am Filter-Knopf haengt wieder an einer Bedingung. Dann sieht "
        "kein Filter gesetzt aus wie eine fehlende Anzeige.")
    assert 'data-leer=' in code[i:i + 120], (
        "der Null-Zustand ist nicht mehr gekennzeichnet — dann kann der Stil ihn nicht "
        "von einer aktiven Zahl unterscheiden")


def test_die_null_sieht_nicht_aus_wie_ein_aktiver_filter():
    """⚠ Der eigentliche Fehler waere hier. In derselben gefuellten Pille beantwortet die
    Anzeige die Frage, die sie ausgeloest hat, und zwar falsch."""
    css = re.sub(r"/\*[\s\S]*?\*/", "", GLOBALS.read_text(encoding="utf-8"))
    m = re.search(r"\.filt-n\[data-leer\]\s*\{([^}]*)\}", css)
    assert m, "fuer den Null-Zustand gibt es keine eigene Regel"
    assert "background:none" in m.group(1).replace(" ", ""), (
        "die Null steht in derselben gefuellten Pille wie eine aktive Zahl")


def test_die_markenreihe_bleibt_bedingt():
    """Sie listet auf, statt zu zaehlen. Immer sichtbar waere sie in den meisten Faellen
    eine Zeile, die nichts meldet."""
    code = _ohne_kommentar(SHELL.read_text(encoding="utf-8"))
    i = code.index('className="fmarken"')
    davor = code[max(0, i - 300):i]
    assert "if (!marken.length) return null" in davor, (
        "die Marken-Reihe wird jetzt immer gerendert. Sie soll auflisten, nicht melden, "
        "dass es nichts aufzulisten gibt.")
