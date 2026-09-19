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
CSS = WURZEL / "web" / "app" / "explorer.css"


def _ohne_kommentar_css(s: str) -> str:
    """⚠ Sonst prueft der Test die eigene Begruendung (F13)."""
    return re.sub(r"/\*[\s\S]*?\*/", "", s)


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


def test_der_leere_status_ist_ein_wort_und_sieht_anklickbar_aus():
    """⚠ Sven am 2026-09-19: „dann brauchen wir was anderes fuer '-', ein neutralen
    status, damit man weiss das man darauf klicken kann".

    Der Strich sah aus wie eine leere Zelle. Dass darunter ein Knopf sitzt, der das
    Status-Menue oeffnet, war nur am Zeiger zu erraten — und der zeigt sich erst, wenn man
    schon dort ist.

    ⚠ WARUM NICHT „NEU", wie zuerst vorgeschlagen. Zwei Gruende, beide hart:

    1. `Neu` steht in derselben Zeile bereits in der Spalte „Wettbewerb" und heisst dort
       Neuvergabe ohne Amtsinhaber (Gegenstueck: `Folge`). Ein Wort, eine Zeile, zwei
       Bedeutungen.
    2. Es waere falsch, sobald man den Lead einmal geoeffnet hat. Der leere Status heisst
       „noch nicht eingeordnet", nicht „neu" — ein Vorgang, den man gestern gelesen und
       nicht eingeordnet hat, stuende weiter als „Neu" da.
    """
    kern = _ohne_kommentar(CORE.read_text(encoding="utf-8"))
    i = kern.index("case 'wf':")
    z = kern[i:i + 420]
    assert "—" not in z and "&mdash;" not in z, "der leere Status ist wieder ein Strich"
    assert 'tk("Setzen")' in z, "der leere Status traegt kein uebersetztes Wort"
    assert '"wf wf-none"' in z, (
        "die leere Marke hat nicht die Kapselform der gesetzten Status — dann sieht sie "
        "nicht aus wie ein Feld, das man fuellen kann")
    # Die Kollision, an der „Neu" gescheitert ist: sie muss sichtbar bleiben.
    j = kern.index("case 'neu':")
    assert 'tk("Neu")' in kern[j:j + 400], (
        "die Spalte Wettbewerb sagt nicht mehr Neu — dann faellt der Grund weg, warum "
        "der leere Status nicht so heissen darf, und jemand wird es wieder vorschlagen")

    css = _ohne_kommentar_css(CSS.read_text(encoding="utf-8"))
    m = re.search(r"\.wf-none\{([^}]*)\}", css)
    assert m, ".wf-none gibt es nicht mehr"
    assert "dashed" in m.group(1), (
        "die leere Marke ist nicht mehr gestrichelt — gefuellt sieht sie aus wie ein "
        "gesetzter Status")


def test_kein_gruener_teppich_ueber_der_ganzen_liste():
    """⚠ Sven am 2026-09-19, als Teil des Vorschlags: das gruene Highlight soll weg.

    Beim Nachmessen war es kein Highlight. `tr[data-unread]` hing an
    `status === "ungesichtet"`, und `export_web_leads.py` schreibt diesen Wert als
    KONSTANTE in jeden Lead:

        leads-bau.json         17.837 x ungesichtet, 0 x anders
        leads-it.json           6.915 x ungesichtet, 0 x anders
        … alle acht Branchendateien: 42.584 von 42.584

    Beim Laden war also jede Zeile gruen hinterlegt, mit gruenem Balken links und
    fetterem Titel. Weiss wurde eine Zeile nur durch einen Klick in DERSELBEN Sitzung;
    gespeichert wird die Sichtung nirgends (`l.status = "gesichtet"` aendert das Objekt im
    Speicher, sonst nichts), nach dem Neuladen war wieder alles gruen.

    ⚠ Die Spur bleibt, nur mit umgekehrter Tinte: `tr.gesichtet` blasst die BESUCHTEN
    Zeilen ab. Beim Laden ist nichts markiert, und die Markierung waechst mit der Arbeit.
    Diese Regel stand vorher schon da — sie ging unter dem Teppich unter.
    """
    css = _ohne_kommentar_css(CSS.read_text(encoding="utf-8"))
    assert "tr[data-unread]" not in css, (
        "der Teppich ist zurueck. Er liegt auf 100 % der Zeilen, weil der Export "
        "\"ungesichtet\" als Konstante schreibt — er sagt nichts.")
    assert "tr.gesichtet .ttitel" in css, (
        "die Gegenrichtung fehlt: ohne sie sieht man nicht mehr, wo man schon war")
    tsx = (WURZEL / "web" / "components" / "explorer" / "LeadTable.tsx").read_text(encoding="utf-8")
    assert "data-unread" not in tsx, "die Zeile traegt wieder einen Haken, den kein CSS liest"
    assert tsx.count('"gesichtet"') >= 2, (
        "die gruppierte UND die flache Liste brauchen die Klasse — sonst hat eine von "
        "beiden keine Spur")
