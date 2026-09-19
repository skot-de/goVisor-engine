"""Wie viele kleine Rechtecke stehen in einer Tabellenzeile?

⚠ Sven am 2026-09-19, zum zweiten Mal an diesem Thema: „es sind immer noch einfach ganz
viele balken". Nachgezaehlt war das woertlich richtig:

    3 Baender à 3 Segmente (Relevanz, Chance, Aufwand)   9
    Passungsachse                                        5
    ──────────────────────────────────────────────────────
    je Zeile                                            14
    bei 50 sichtbaren Zeilen                        ca. 700

Die Baender trugen ihr Label (`hoch`/`mittel`/`niedrig`) die ganze Zeit mit, es war in der
Tabelle nur per CSS ausgeblendet. Wort statt Segmente kostet nichts an Information — im
Gegenteil: „mittel" ist in einer 104 px breiten Zelle ablesbar, drei Balkenstriche sind es
nicht. Im DETAIL bleiben die Segmente, dort steht ein Band allein.

⚠ Das Label geht seitdem durch `tk()`. Ausgeblendet fiel nicht auf, dass `bandMeter` den
rohen deutschen Wert schreibt; sichtbar gemacht haette „hoch" bei jedem EN- und FR-Nutzer
dagestanden.
"""
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
CSS = WURZEL / "web" / "app" / "explorer.css"
CORE = WURZEL / "web" / "lib" / "explorerCore.js"
REC = WURZEL / "web" / "lib" / "recommendation.js"


def _ohne_kommentar(s: str) -> str:
    """`//` und `/* */` raus — sonst prueft der Test seine eigene Begruendung (F13)."""
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


def _ohne_kommentar_css(s: str) -> str:
    return re.sub(r"/\*[\s\S]*?\*/", "", s)


def test_die_tabelle_zeigt_das_wort_statt_der_segmente():
    css = _ohne_kommentar_css(CSS.read_text(encoding="utf-8"))
    assert re.search(r"td\.c-band \.band \.segs\s*\{[^}]*display:\s*none", css), (
        "die Segmentbalken sind in der Tabelle wieder sichtbar. Das sind neun kleine "
        "Rechtecke je Zeile, bei 50 Zeilen 450.")
    assert not re.search(r"td\.c-band \.band \.lbl\s*\{[^}]*display:\s*none", css), (
        "das Wort ist wieder ausgeblendet. Dann steht in der Zelle gar nichts mehr.")


def test_das_band_label_ist_uebersetzt():
    """⚠ Solange es ausgeblendet war, fiel der rohe deutsche Wert nicht auf."""
    code = CORE.read_text(encoding="utf-8")
    i = code.index("const bandMeter")
    rumpf = code[i:code.index("\n};", i)]
    assert 'class="lbl">${tk(level)}' in rumpf, (
        "das Band-Label geht nicht mehr durch tk(). Sichtbar in der Tabelle steht dann "
        "bei EN- und FR-Nutzern ein deutsches Wort.")


def test_im_detail_bleiben_die_segmente():
    """Dort steht ein Band allein und traegt Bedeutung; die Aufraeumung galt der Tabelle."""
    css = _ohne_kommentar_css(CSS.read_text(encoding="utf-8"))
    assert re.search(r"\.score \.band \.segs i\s*\{", css), (
        "die Segmentdarstellung im Detail ist mit weggeraeumt worden")


def test_kein_grund_wiederholt_seine_ueberschrift():
    """⚠ Die Empfehlungszelle rendert Label UND Grund untereinander. Sind beide gleich,
    steht dasselbe zweimal da — gemeldet am 2026-09-19 als „hohe passung zweimal
    untereinander". Der Grund soll etwas hinzufuegen."""
    quelle = REC.read_text(encoding="utf-8")
    doppelt = []
    for m in re.finditer(r'label:\s*"([^"]+)",\s*cls:\s*"[^"]*",\s*gruende:\s*\[([^\]]*)\]', quelle):
        gruende = re.findall(r'"([^"]*)"', m.group(2))
        if gruende and gruende[0].strip().lower() == m.group(1).strip().lower():
            doppelt.append(m.group(1))
    assert not doppelt, (
        f"{len(doppelt)} Empfehlungen nennen als Grund ihre eigene Ueberschrift: "
        f"{doppelt}. In der Zelle steht das zweimal untereinander.")


def test_die_marken_tragen_keinen_bedeutungslosen_punkt():
    """⚠ Sven am 2026-09-19: „warum haben phase und leistung in ihren label diesen punkt?"

    Weil ihn niemand je gerechtfertigt hat. Nachgemessen war seine Farbe die Textfarbe,
    eine Spur dunkler, bei `src-award` sogar identisch:

        src-auslauf  Text #33507D  Punkt #3A6099
        src-f01      Text #835616  Punkt #A2691E
        src-award    Text #2B5F86  Punkt #2B5F86
        nat-dienst   Text #365574  Punkt #3A5A75

    Die Kapsel sagt die Kategorie ueber den getoenten Grund, das Wort sagt sie im Klartext,
    und der Punkt sagte sie ein drittes Mal in derselben Farbe. 14 Punkte auf 50 Zeilen,
    fuer nichts.

    ⚠ DER EIGENTLICHE SCHADEN liegt woanders. `.val::before` ist derselbe 6-px-Punkt und
    BEDEUTET etwas: er erscheint nur bei geschaetzten und unsicheren Werten und fehlt bei
    belegten (`[data-src="echt"]::before{display:none}`). Solange zwei Spalten denselben
    Punkt als Zierrat tragen, lernt das Auge, dass ein Punkt in dieser Tabelle nichts
    heisst — und uebersieht den einen, der sagt „diese Zahl ist geraten".

    Deshalb prueft dieser Test beide Richtungen: kein Punkt an den Marken, und der Punkt
    am Beleg ist noch da.
    """
    css = _ohne_kommentar_css(CSS.read_text(encoding="utf-8"))
    for kl in ("srcpill", "nat"):
        assert f".{kl}::before" not in css, (
            f".{kl} traegt wieder einen Punkt. Er wiederholt in der Textfarbe, was Grund "
            f"und Wort schon sagen, und entwertet den Punkt am Beleg-Strich.")
    assert ".val::before" in css, (
        "der Beleg-Punkt ist weg. Er ist der einzige in der Tabelle, der etwas sagt: "
        "geschaetzt oder unsicher statt belegt.")
    assert '.val[data-src="echt"]::before{display:none}' in css, (
        "der Beleg-Punkt steht jetzt auch an belegten Werten — damit sagt er nichts mehr.")


def test_die_unterlagen_label_haben_die_form_der_anderen_spalten():
    """⚠ Sven am 2026-09-19: „mach daraus so label, wie in jeder anderen spalte auch."

    Phase, Leistung und Unterlagen benennen dasselbe Ding: einen Zustand, in einem Wort.
    Drei verschiedene Bauformen dafuer lesen sich als drei verschiedene Arten von Sache.
    """
    css = _ohne_kommentar_css(CSS.read_text(encoding="utf-8"))
    m = re.search(r"\.dokpill\{([^}]*)\}", css)
    assert m, ".dokpill gibt es nicht — die Unterlagen-Label haben keine gemeinsame Form"
    marke = m.group(1).replace(" ", "").replace("\n", "")
    for eigenschaft in ("border-radius:100px", "padding:3px9px", "font-size:11.5px"):
        assert eigenschaft in marke, (
            f".dokpill weicht in {eigenschaft!r} von .srcpill und .nat ab")
    kern = _ohne_kommentar_css(CORE.read_text(encoding="utf-8"))
    i = kern.index("case 'doks': {")
    z = kern[i:kern.index("case '", i + 20)]
    assert z.count("dokpill") == 3, (
        f"{z.count('dokpill')} statt 3 Label tragen die gemeinsame Marke")


def test_eine_zu_knappe_frist_ist_rot_und_sonst_nichts():
    """⚠ Sven am 2026-09-19: „das 'frist zu knapp' label solltest du vll rot machen."

    Der Unterschied zu „Geringe Passung" ist nicht der Grad, sondern die ART. Eine schwache
    Passung ist ein URTEIL, ueber das man anderer Meinung sein kann; eine zu kurze Frist ist
    eine TATSACHE, die den Vorgang schliesst. Beide trugen `gedaempft`, und gedaempft liest
    sich als „lohnt sich eher nicht" statt „geht nicht mehr".

    ⚠ Rot vertraegt nur Seltenheit. Gemessen ueber bau+it+medizin+beratung (36.943 offene
    Leads) mit breitem Profil: **5,4 %** — etwa jede achtzehnte Zeile. Deshalb prueft dieser
    Test auch die Gegenrichtung: genau EIN Label ist rot. Wandern weitere hinein, wird die
    Farbe zur Tapete und sagt nichts mehr.
    """
    quelle = (WURZEL / "web" / "lib" / "recommendation.js").read_text(encoding="utf-8")
    rot = re.findall(r'label: "([^"]+)", cls: "rot"', quelle)
    assert rot == ["Frist zu knapp"], (
        f"rot tragen: {rot}. Erwartet genau „Frist zu knapp\" — eine Alarmfarbe auf "
        f"mehreren Labeln ist keine Alarmfarbe mehr.")

    kern = _ohne_kommentar(CORE.read_text(encoding="utf-8"))
    m = re.search(r"REC_CLS = \{([^}]*)\}", kern)
    assert m and "rot:'stop'" in m.group(1).replace(" ", ""), (
        "die Klasse `rot` hat keine Entsprechung — das Label bekaeme `rec-undefined`")

    css = _ohne_kommentar_css(CSS.read_text(encoding="utf-8"))
    for regel in (".c-empf .empf.rec-stop", ".rec-verdict.rec-stop"):
        assert regel in css, f"{regel} fehlt — Liste und Detail muessen beide rot sein"
    assert "--risk" in css[css.index(".c-empf .empf.rec-stop"):][:160], (
        "das Rot ist kein Token, sondern ein eigener Wert")


def test_die_klassenzuordnung_steht_nur_einmal():
    """⚠ Sie stand ZWEIMAL: als `REC_CLS` fuer die Liste und noch einmal als lokales `CLS`
    im Detail-Verdikt. Beim Nachtragen von `rot` waere die zweite Fassung stehengeblieben,
    `CLS['rot']` haette `undefined` ergeben — ein Verdikt ohne jede Farbe im Detail,
    waehrend die Liste rot leuchtet. Die Sorte Fehler, die niemand meldet, weil die eine
    Ansicht ja stimmt.
    """
    kern = _ohne_kommentar(CORE.read_text(encoding="utf-8"))
    # ⚠ Am Wort `gedaempft` erkannt, nicht an `gruen`: `AMP` (die Ampel der
    # Dokumentauswertung) benutzt ebenfalls gruen/rot, meint aber etwas anderes und ist
    # zu Recht eine eigene Tabelle. Der erste Anlauf dieses Tests hat sie mitgezaehlt.
    eigene = re.findall(r"(?:const|let)\s+\w+\s*=\s*\{[^}]*gedaempft\s*:", kern)
    assert len(eigene) == 1, (
        f"{len(eigene)} Zuordnungen von Kaskaden-Klasse auf CSS-Klasse. Es darf nur eine "
        f"geben, sonst altert eine davon unbemerkt.")
