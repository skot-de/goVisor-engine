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
