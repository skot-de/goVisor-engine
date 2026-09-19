"""Welche Spalten stehen beim ersten Blick da, und wonach ist sortiert?

⚠ Sven am 2026-09-19: „brauchen wir relevanz, chance und aufwand überhaupt unter den
standard spalten?" Die Nachfrage davor war schaerfer: „was ist dann der unterschied
zwischen empfehlung und relevanz?"

Nachgemessen ist die Antwort unangenehm: `recommendation.js` kodiert die Relevanz als
Zahl (`E2 = relBand === "hoch" ? 75 : "mittel" ? 55 : "niedrig" ? 30`) und benutzt sie als
HAUPTSIGNAL der Empfehlungskaskade. Mit den Schwellen `E2_hoch = 70` und `E2_mittel = 45`
ergibt das eine Eins-zu-eins-Abbildung:

    hoch    → 75 → „Hohe Passung"
    mittel  → 55 → „Passung mittel"
    niedrig → 30 → „Geringe Passung"

Von 14 Verzweigungen beider Kaskaden sagen 7 nur die Relevanz. Die uebrigen sieben leben
von vier Signalen: E8 (eigener auslaufender Vertrag), E5 (Frist kuerzer als der Median),
E3 (Amtsinhaber angreifbar), E10 (Unterlagen fehlen). Die Empfehlung ist also die Relevanz
PLUS vier Umstaende — sie enthaelt die Relevanz vollstaendig, umgekehrt gilt das nicht.

Deshalb bleibt die Empfehlung vorbelegt und die Relevanz nicht. Chance und Aufwand gehen
aus demselben Grund raus: sie beantworten Fragen, die man NACH der Vorauswahl stellt.
"""
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
CORE = WURZEL / "web" / "lib" / "explorerCore.js"
SHELL = WURZEL / "web" / "components" / "explorer" / "ExplorerShell.tsx"


def _spalten():
    s = CORE.read_text(encoding="utf-8")
    i = s.index("const COLS = [")
    b = s[i:s.index("\n];", i)]
    return {k: o == "true" for k, _l, o in
            re.findall(r"\{key:'([^']+)',\s*label:'([^']*)',\s*on:(true|false)", b)}


def test_relevanz_chance_aufwand_sind_nicht_vorbelegt():
    sp = _spalten()
    an = [k for k in ("relevanz", "wechsel", "aufwand") if sp.get(k)]
    assert not an, (
        f"{an} stehen wieder in der Vorbelegung. Die Relevanz sagt dasselbe wie die "
        f"Empfehlung (E2 ist die Relevanz, umkodiert), Chance und Aufwand beantworten "
        f"Fragen, die man erst nach der Vorauswahl stellt.")


def test_die_empfehlung_bleibt_vorbelegt():
    """Sie enthaelt die Relevanz und sagt in den interessanten Faellen mehr. Ohne sie
    faellt die Vorauswahl ganz weg."""
    assert _spalten().get("empf"), "die Empfehlungsspalte ist aus der Vorbelegung genommen"


def test_die_drei_bleiben_zuwaehlbar():
    """⚠ Abwaehlen heisst nicht loeschen. Wer sie braucht, schaltet sie in der
    Spaltenauswahl zu; verschwunden waeren sie ein Verlust ohne Gegenwert."""
    sp = _spalten()
    for k in ("relevanz", "wechsel", "aufwand"):
        assert k in sp, f"die Spalte {k!r} gibt es nicht mehr"


def test_die_empfehlung_sortiert_feiner_als_ihre_stufen():
    """⚠ `rank` kennt eine Handvoll Stufen. Ohne Nachsortierung stuenden die Leads
    innerhalb von „Hohe Passung" in zufaelliger Reihenfolge — und die Relevanzspalte, die
    das vorher aufloeste, ist nicht mehr vorbelegt."""
    s = CORE.read_text(encoding="utf-8")
    i = s.index("case 'empf': return")
    zeile = s[i:s.index(";", i)]
    assert "passung" in zeile, (
        "die Empfehlungsspalte sortiert nur noch nach der groben Stufe")


def test_die_vorgabe_sortiert_nach_frist():
    """Sven: „standardsortierung auf die frist. kürzeste oben". `sortDir: 1` ist
    aufsteigend, und `case 'frist'` liefert die verbleibenden Tage."""
    s = SHELL.read_text(encoding="utf-8")
    ohne = re.sub(r"/\*[\s\S]*?\*/", "", s)
    ohne = re.sub(r"//.*", "", ohne)
    m = re.search(r'setSortKey\("(\w+)"\);\s*setSortDir\((-?\d)\);', ohne)
    assert m, "die automatische Sortierung gibt es nicht mehr"
    assert m.group(1) == "frist", (
        f"die Vorgabe sortiert nach {m.group(1)!r} statt nach der Frist")
    assert m.group(2) == "1", "die Frist wird absteigend sortiert, also laengste oben"
