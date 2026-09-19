"""Zeigt die Spalte „Unterlagen", was sie verspricht?

⚠ GEMELDET AM 2026-09-19: „zudem ist die aktuelle angabe bei Unterlagen in akquise nicht
richtig." Nachgemessen war die ZAHL richtig gerechnet — der Index stimmt exakt mit dem
Auswertungsspeicher ueberein (0 Abweichungen ueber 3.001 Vorgaenge). Falsch war die
Ueberschrift: die Spalte heisst „Unterlagen" und zeigte die PRUEFPUNKTE.

Jetzt steht dort die Zahl der gelesenen Dokumente. Die Pruefpunkt-Dichte bleibt im Titel —
sie ist weiterhin das unterscheidende Mass (0 bis 186 bei Median 57, waehrend 88,5 % der
Ampeln gelb sind), aber sie ist eine Erklaerung und keine Behauptung mehr.

⚠ `dok === 0` bei 14,7 % der Auswertungen. Eine „0" dort hiesse „keine Unterlagen", obwohl
ausgewertet wurde — deshalb ein Wort statt einer Null.

⚠ Und: nicht ausgewertet ist nicht dasselbe wie nichts da. Wo Unterlagen beim Portal
liegen, steht jetzt ein Link; er oeffnet sie in einem neuen Tab UND schlaegt den Lead bei
`an-unterlagen` auf, wo der Upload-Knopf steht.
"""
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
CORE = WURZEL / "web" / "lib" / "explorerCore.js"
TAB = WURZEL / "web" / "components" / "explorer" / "LeadTable.tsx"
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


def _zelle() -> str:
    code = _ohne_kommentar(CORE.read_text(encoding="utf-8"))
    i = code.index("case 'doks': {")
    return code[i:code.index("case 'empf': {", i)]


def test_die_spalte_zeigt_dokumente_nicht_pruefpunkte():
    z = _zelle()
    m = re.search(r"const zahl = ([^;]+);", z)
    assert m, "die angezeigte Zahl wird nicht mehr benannt"
    assert "a.dok" in m.group(1), (
        "unter der Ueberschrift Unterlagen steht wieder etwas anderes als die Zahl der "
        "Dokumente")
    assert "a.pruef" not in m.group(1), "die Pruefpunkte sind wieder die Hauptzahl"


def test_null_dokumente_zeigen_ein_wort_keine_null():
    """⚠ 14,7 % der Auswertungen tragen `dok = 0`. Eine 0 dort liest sich als
    „keine Unterlagen" — obwohl ausgewertet wurde."""
    z = _zelle()
    assert re.search(r"a\.dok \? String\(a\.dok\) : tk\(", z), (
        "bei 0 Dokumenten steht wieder eine Null statt eines Wortes")


def test_vorhandene_unterlagen_bekommen_einen_link():
    z = _zelle()
    assert "data-doklink=" in z, (
        "wo Unterlagen beim Portal liegen, aber nicht ausgewertet sind, steht wieder nur "
        "ein Strich")
    i, j = z.index("data-doklink="), z.index("dok-na")
    assert i < j, "der Link steht hinter dem Strich-Zweig und wird nie erreicht"


def test_der_klick_oeffnet_beides():
    """Fremden Tab UND das Detail. ⚠ Das Fenster ZUERST: `window.open` gilt nur im
    direkten Klick als gewollt; steht ein Zustandswechsel davor, blockt der Browser es
    als Pop-up."""
    tab = _ohne_kommentar(TAB.read_text(encoding="utf-8"))
    assert 'closest<HTMLElement>("[data-doklink]")' in tab, "die Tabelle reicht den Klick nicht weiter"
    sh = _ohne_kommentar(SHELL.read_text(encoding="utf-8"))
    i = sh.index("function dokLinkOeffnen")
    rumpf = sh[i:sh.index("\n  }", i)]
    assert "window.open" in rumpf and "openLead" in rumpf, "der Klick tut nicht beides"
    assert rumpf.index("window.open") < rumpf.index("openLead"), (
        "der Lead wird vor dem Fenster geoeffnet — der Browser wertet window.open dann "
        "als Pop-up und blockt es")
    assert "an-unterlagen" in rumpf, "es wird nicht zum Unterlagen-Abschnitt gesprungen"


def test_der_abschnitt_ist_anspringbar():
    """Ohne `id` laeuft der Sprung ins Leere, und der Nutzer landet oben im Detail."""
    code = CORE.read_text(encoding="utf-8")
    assert 'id="an-unterlagen"' in code, (
        "der Aufforderungs-Abschnitt traegt keine Kennung mehr")


# ── Das Drop-Feld ──────────────────────────────────────────────────────────────────────

def test_es_gibt_ein_drop_feld_und_einen_knopf():
    """⚠ BEIDES, nicht nur die Flaeche. Ein reines Drop-Feld ist mit der Tastatur nicht
    bedienbar und auf dem Telefon gar nicht — dort gibt es nichts zu ziehen. Die Flaeche
    ist der Weg fuer die Maus, der Knopf fuer alle anderen."""
    code = _ohne_kommentar(CORE.read_text(encoding="utf-8"))
    i = code.index("const dropFeld")
    feld = code[i:code.index("`;", i)]
    assert "data-dropzone=" in feld, "die Flaeche nimmt keine Dateien mehr entgegen"
    assert "data-uploaddocs=" in feld, (
        "der Dateiwaehler ist aus dem Drop-Feld verschwunden. Ohne ihn ist der Upload "
        "mit Tastatur und auf dem Telefon unerreichbar.")


def test_das_ziehen_wird_abgefangen():
    """⚠ Ohne `preventDefault` beim Ueberziehen ist die Flaeche kein gueltiges Ziel: der
    Browser oeffnet die fallengelassene Datei in einem neuen Tab, und der Nutzer verliert
    seine Sicht. Das ist der haeufigste Fehler an Drop-Feldern."""
    dp = _ohne_kommentar((WURZEL / "web" / "components" / "explorer" / "DetailPanel.tsx")
                         .read_text(encoding="utf-8"))
    # ⚠ MIT `={`, sonst trifft der Anker die PROP `onDropDocs` in der Signatur statt den
    #   Handler (F19: der Anker ist nicht eindeutig). Beim Schreiben dieses Tests passiert.
    for ereignis in ("onDragOver={", "onDrop={"):
        i = dp.index(ereignis)
        assert "preventDefault" in dp[i:i + 400], f"{ereignis} verhindert die Vorgabe nicht"


def test_es_gibt_nur_einen_upload_weg():
    """⚠ Der Ablauf nach dem Upload ist nicht trivial: Antwort in den Lead mischen,
    Kaeufer-Rueckfrage bei `leadMismatch`, Hinweis bei `lbAnalyseWartet`. Zwei Kopien
    davon waeren zwei Stellen, an denen dieser Hinweis kuenftig fehlt."""
    sh = _ohne_kommentar(SHELL.read_text(encoding="utf-8"))
    assert sh.count("async function dateiHochladen") == 1, "die Upload-Funktion gibt es nicht mehr"
    assert sh.count("/api/lead-docs?id=") == 1, (
        "es gibt wieder mehr als einen Weg, eine Datei hochzuladen")
