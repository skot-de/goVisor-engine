"""Status setzen, ohne den Lead zu oeffnen.

⚠ Sven am 2026-09-19: „ich will den status nicht nur aendern/setzen koennen, wenn ich in
den ausschreibungsdetails bin, sondern schon in der leaduebersicht." Bis dahin hing
`setWf` an `activeId` — also am GEOEFFNETEN Lead.

⚠ DIE NAHELIEGENDE LOESUNG WAERE FALSCH GEWESEN. Vier Zustands-Knoepfe je Zeile sind bei
50 Zeilen 200 zusaetzliche Elemente, und die andere Meldung desselben Tages lautete „es
sind immer noch einfach ganz viele balken". Die Zelle sieht deshalb aus wie vorher; ein
EINZIGES Menue haengt sich beim Klick an sie.
"""
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
CORE = WURZEL / "web" / "lib" / "explorerCore.js"
TABELLE = WURZEL / "web" / "components" / "explorer" / "LeadTable.tsx"
SHELL = WURZEL / "web" / "components" / "explorer" / "ExplorerShell.tsx"


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


def test_die_statuszelle_ist_anklickbar():
    code = _ohne_kommentar(CORE.read_text(encoding="utf-8"))
    i = code.index("case 'wf':")
    zelle = code[i:code.index("</td>", i)]
    assert "data-wf=" in zelle, (
        "die Statusspalte traegt keine Kennung mehr. Dann laesst sich der Status wieder "
        "nur im geoeffneten Lead setzen.")


def test_die_tabelle_reicht_den_klick_weiter():
    code = _ohne_kommentar(TABELLE.read_text(encoding="utf-8"))
    assert 'closest<HTMLElement>("[data-wf]")' in code, "die Delegation fehlt"
    assert "onWf" in code, "der Rueckweg nach oben fehlt"
    i = code.index('closest<HTMLElement>("[data-wf]")')
    j = code.index('closest<HTMLElement>("[data-star]")')
    assert i < j, (
        "die Statuszelle wird nach der Zeilenauswahl geprueft. Dann oeffnet der Klick "
        "den Lead, statt das Menue zu zeigen.")


def test_kein_knopf_je_zustand_und_zeile():
    """⚠ Der eigentliche Punkt. Vier Knoepfe je Zeile waeren bei 50 Zeilen 200 Elemente
    mehr — genau die Unruhe, die am selben Tag gemeldet wurde."""
    code = _ohne_kommentar(CORE.read_text(encoding="utf-8"))
    i = code.index("case 'wf':")
    zelle = code[i:code.index("</td>", i)]
    assert zelle.count("data-wf=") == 1, (
        f"die Statuszelle enthaelt {zelle.count('data-wf=')} Schaltflaechen. Sie soll "
        f"genau eine haben; die Auswahl gehoert ins Menue.")
    assert "Object.entries(WF" not in zelle and "map(" not in zelle, (
        "die Zelle zaehlt die Zustaende auf, statt sie im Menue anzubieten")


def test_menue_setzt_direkt_das_detail_schaltet_um():
    """⚠ Zwei Aufrufer, zwei Bedeutungen. Im Detail nimmt ein Klick auf den AKTIVEN
    Zustand ihn zurueck. Im Menue waehlt man aus; dort waere Umschalten falsch, denn
    Interessant auf einem schon interessanten Lead soll ihn nicht leeren."""
    code = _ohne_kommentar(SHELL.read_text(encoding="utf-8"))
    i = code.index("function setWfFuer")
    menue = code[i:code.index("function setWf(", i)]
    assert "l.userStatus = k;" in menue, (
        "das Listenmenue schaltet um, statt zu setzen. Dann leert ein zweiter Klick auf "
        "denselben Zustand den Lead.")
    j = code.index("function setWf(")
    detail = code[j:j + 400]
    assert "=== k ? null : k" in detail, (
        "das Detail setzt jetzt direkt, statt umzuschalten — dort gibt es keinen eigenen "
        "Punkt zum Zuruecknehmen")
