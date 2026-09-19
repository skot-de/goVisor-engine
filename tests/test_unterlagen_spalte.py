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


def test_drei_label_statt_fuenf_zustaende():
    """⚠ Sven am 2026-09-19, nach mehreren Anlaeufen: „was wäre mit labeln: Ja / Link /
    Nein". Gemessen ueber bau+it+medizin, 28.072 Leads ohne Zuschlaege:

        Ja      4.799   17,1 %   (ausgewertet 2.615 · Volltext 1.623 · Gliederung 561)
        Link   22.923   81,7 %
        Nein      350    1,2 %

    ⚠ „Link" fuellt damit 82 % — mehr als die 75 %, wegen derer die Fassung davor
    gestrichen wurde. Das ist kein Rueckfall, sondern eine andere FRAGE: die alte Spalte
    beantwortete „wie weit sind WIR", die neue „kommst du an die Unterlagen". Fuer die
    zweite ist 82 % die Lage der Welt. Die Abstufung im Stil traegt den Rest: nur „Ja"
    hat Farbe.
    """
    z = _zelle()
    for kl in ("dok-ja", "dok-link2", "dok-nein"):
        assert kl in z, f"das Label {kl!r} gibt es nicht mehr"
    assert z.index("dok-ja") < z.index("dok-link2") < z.index("dok-nein"), (
        "die Reihenfolge stimmt nicht: was wir HABEN schlaegt den blossen Link, und der "
        "schlaegt das Nichts")


def test_keine_zahl_an_ja():
    """⚠ Sven am 2026-09-19: „nein ohne zahl". Ich hatte die Dokumentzahl behalten, weil
    sie verdiente Information ist. Sie ist aber die falsche Information AN DIESER STELLE:
    „Ja 12" laedt zum Vergleichen ein, und auf „12 gegen 3" gibt es keine Antwort — ob
    zwoelf Dateien mehr wert sind als drei, haengt am Inhalt. Im Unterlagen-Tab steht die
    Zahl neben den Dateien und bedeutet etwas; in der Liste war sie nur wieder eine Zahl
    in einer Spalte voller Zahlen, also genau das, wogegen der ganze Umbau lief.

    Dieser Test steht hier, weil die Zahl billig ist: `a.dok` liegt im Lead-Datensatz, und
    beim naechsten Anfassen der Zelle ist sie schnell wieder angehaengt. Zwei Waechter, die
    sie frueher HUETETEN, sind dafuer gewichen — ihre Befunde gelten weiter und sind der
    Grund, warum die Zahl als Anzeige nie gut war:

    · Sie musste gegen die Pruefpunkte verteidigt werden: unter der Ueberschrift
      „Unterlagen" stand zwischenzeitlich die Zahl der Pruefpunkte, was niemand so liest.
    · **14,7 % der Auswertungen tragen `dok = 0`.** Eine 0 dort liest sich als „keine
      Unterlagen", obwohl ausgewertet wurde — sie brauchte also eine Sonderbehandlung,
      damit sie nicht das Gegenteil dessen sagt, was der Fall ist.

    Eine Anzeige, die gegen zwei Missverstaendnisse abgesichert werden muss und am Ende
    nichts Vergleichbares aussagt, ist in einer Liste falsch aufgehoben.
    """
    z = _zelle()
    assert "<i>" not in z, "in der Zelle steht wieder eine Zahl"
    assert "const zahl" not in z, (
        "die Dokumentzahl wird wieder in die Zelle gerechnet — sie gehoert in den "
        "Unterlagen-Tab, nicht in die Liste")


def test_nein_ist_stumm():
    """⚠ Seit jeder Klick in dieser Spalte auf den Unterlagen-Tab fuehrt, waere Nein"
    eine Sackgasse: man landet in einer Ansicht, die sagt, dass es nichts gibt."""
    z = _zelle()
    nein = z[z.index("dok-nein"):]
    assert "data-doklink" not in nein[:200], (
        "Nein ist wieder anklickbar und fuehrt in eine leere Ansicht")
    assert "<span" in z[max(0, z.index("dok-nein") - 40):z.index("dok-nein")], (
        "Nein ist ein Knopf — es tut aber nichts")


def test_alle_zustaende_sind_knoepfe():
    """⚠ HIER STAND DAS GEGENTEIL, und das war ein Fehler von mir.

    Sven sagte „finde die button auch gerade nicht gut", und ich habe daraufhin das
    ELEMENT getauscht statt nur sein Aussehen. Der Einwand galt der gefuellten Flaeche,
    nicht der Funktion. Gemessen ergab das eine Regression: fuenf der sechs anklickbaren
    Zellen einer Zeile sind `<button>` (Stern, Ausblenden, Netz, Unserer, Status), meine
    war die Ausnahme — ohne Tastaturzugang, ohne Fokusring, und bei vier der sechs
    Zustaende ohne Zeiger. Einer trug sogar `cursor: help`: er verspricht einen Hinweis
    und springt stattdessen weg.

    Ein Knopf, der wie Text aussieht, erfuellt beides. Das Aussehen regelt die CSS
    (`td.c-doks button`: keine Flaeche, kein Rahmen, Schriftgrad der Zelle).
    """
    z = _zelle()
    knoepfe = len(re.findall(r"<button[^>]*data-doklink", z))
    assert knoepfe == 2, (
        f"{knoepfe} statt 2 Label sind Knoepfe (Ja und Link; Nein ist stumm). Ein `<span>` ist mit der Tastatur "
        f"nicht erreichbar und traegt keinen Fokusring.")
    assert not re.search(r"<span[^>]*data-doklink", z), (
        "ein Zustand ist wieder ein `<span>` — nicht fokussierbar, nicht per Tastatur "
        "ausloesbar")


def test_kein_hilfe_zeiger_auf_etwas_das_wegspringt():
    """⚠ `cursor: help` verspricht einen Hinweis. Wer darauf klickt, landet in einer
    anderen Ansicht — das ist die Sorte kleiner Luege, die Vertrauen kostet.

    Umgekehrt gilt es genauso: „Nein" springt nirgendwohin und DARF den Hilfe-Zeiger
    tragen, weil sein Titel das einzige ist, was es zu holen gibt.
    """
    css = re.sub(r"/\*[\s\S]*?\*/", "",
                 (WURZEL / "web" / "app" / "explorer.css").read_text(encoding="utf-8"))
    for kl in ("dok-ja", "dok-link2"):
        m = re.search(rf"\.{kl}\b[^{{]*\{{([^}}]*)\}}", css)
        assert m, f".{kl} gibt es nicht mehr"
        assert "cursor:help" not in m.group(1).replace(" ", ""), (
            f".{kl} traegt den Hilfe-Zeiger, obwohl der Klick wegspringt")
    m = re.search(r"td\.c-doks button\b[^{]*\{([^}]*)\}", css)
    assert m, "der Knopf-Zuschnitt der Spalte ist weg"
    assert "cursor:pointer" in m.group(1).replace(" ", ""), (
        "die Label sehen nicht mehr wie etwas Anklickbares aus")
def test_der_klick_oeffnet_den_lead_und_nicht_das_portal():
    """⚠ HIER STAND DAS GEGENTEIL, und die Umkehr ist der Kern.

    Erste Fassung: der Klick oeffnete die Portalseite in einem neuen Tab UND den Lead.
    Die Anforderung war „die seite soll sich in einem neuen tab öffnen, aber govisor
    bleibt das aktive fenster" — und genau das kann eine Seite nicht. Ein Hintergrund-Tab
    entsteht durch Mittel- oder Strg/Cmd-Klick; der einzige Hebel dagegen waere
    `handle.blur()`, und das Handle gibt `window.open` nur OHNE `noopener` zurueck. Dann
    koennte die fremde Seite unser Fenster umleiten.

    Sven hat es umgedreht: der Portal-Link ist ein echtes `<a target="_blank">` im Detail,
    ueber dem Drop-Feld. Klickt der NUTZER ihn, entscheidet er selbst — und ein
    Strg-Klick darauf macht den Hintergrund-Tab, den das Skript nicht erzwingen konnte.
    """
    tab = _ohne_kommentar(TAB.read_text(encoding="utf-8"))
    assert 'closest<HTMLElement>("[data-doklink]")' in tab, "die Tabelle reicht den Klick nicht weiter"
    sh = _ohne_kommentar(SHELL.read_text(encoding="utf-8"))
    i = sh.index("function dokLinkOeffnen")
    rumpf = sh[i:sh.index("\n  }", i)]
    assert "window.open" not in rumpf, (
        "der Klick oeffnet wieder selbst einen Tab. Der Browser fokussiert ihn dann, und "
        "genau das sollte die Umstellung vermeiden.")
    assert "openLead" in rumpf, "der Klick schlaegt den Lead nicht mehr auf"
    # ⚠ DER TAB, NICHT EIN SPRUNGZIEL. Eine erste Fassung scrollte zu `#an-unterlagen` —
    #   das liegt IM Tab `docs`, wird bei aktiver Uebersicht gar nicht gerendert, und der
    #   Sprung lief ins Leere. Er funktionierte nur, wenn der Tab zufaellig offen war.
    assert 'setActiveTab("docs")' in rumpf, (
        "der Klick stellt nicht mehr auf den Unterlagen-Tab")
    assert "setTimeout" in rumpf, (
        "der Tab wird ohne Verzoegerung gesetzt — der Wechsel auf den neuen Lead raeumt "
        "ihn dann wieder weg")


def test_jeder_zustand_der_spalte_springt():
    """Sven: bei jedem klick landet man in den ausschreibungs details unter Unterlagen."
    Vorher trugen nur `Gliederung` und `Link` die Kennung; bei den anderen vier passierte
    dasselbe wie beim Klick auf jede andere Zelle."""
    z = _zelle()
    assert z.count("data-doklink=") == 2, (
        f"{z.count('data-doklink=')} statt 2 Label fuehren in den Unterlagen-Tab: „Ja\" "
        f"und „Link\". „Nein\" ist stumm.")


def test_der_portal_knopf_steht_im_detail_ueber_dem_feld():
    """Ein echtes Anker-Element, damit Strg-Klick funktioniert, und VOR dem Drop-Feld."""
    code = _ohne_kommentar(CORE.read_text(encoding="utf-8"))
    i = code.index("const dropFeld")
    feld = code[i:code.index("\n};", i)]
    assert 'class="va-portal"' in feld and "target=" in feld, (
        "der Portal-Knopf ist kein Anker mehr — dann kann niemand mehr mit Strg-Klick "
        "einen Hintergrund-Tab oeffnen")
    # ⚠ NICHT die Position der KLASSE vergleichen. `class="va-portal"` steht in der
    #   Variablendefinition weiter oben; die Ausgabereihenfolge haengt allein daran, wo
    #   `${knopf}` im Rueckgabewert eingesetzt wird. Ein Rueckbau, der den Knopf ans Ende
    #   schob, lief so gruen durch (gemessen beim Schreiben dieses Tests).
    ruck = feld[feld.index("return `"):]
    assert ruck.index("${knopf}") < ruck.index("va-drop"), (
        "der Knopf wird unter dem Drop-Feld ausgegeben statt darueber")


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


# ── Die Detailseite ueber ihre Zustaende ───────────────────────────────────────────────

def test_auch_im_ausgewerteten_zustand_kann_man_nachreichen():
    """⚠ Gemessen ueber 6.001 Auswertungen haben 1.448 (24,1 %) KEINEN fehlenden Doktyp.
    Der einzige Upload-Knopf steckte in der Gruppe „Offen", die nur entsteht, wenn etwas
    fehlt (`fehlend.length ? … : ''`). Bei einem Viertel der ausgewerteten Vorgaenge
    konnte also niemand eine neuere Fassung schicken, auch wenn er eine hatte."""
    code = _ohne_kommentar(CORE.read_text(encoding="utf-8"))
    i = code.index('<section class="sec va-sec">')
    zweig = code[i:i + 600]
    assert "dropFeld(l)" in zweig, (
        "der ausgewertete Zustand bietet keinen Weg mehr, Unterlagen nachzureichen")
    assert "istOffen" in zweig, (
        "der Nachreich-Block haengt nicht mehr an `istOffen` — bei einer abgelaufenen "
        "Vergabe ist Hochladen sinnlos")


def test_das_drop_feld_ist_formatiert():
    """⚠ DIESE REGELN WAREN ZWEI COMMITS LANG WEG. Beim Ersetzen des Nachbarblocks traf
    `rindex("/* ──", …)` den Kommentarkopf DIESES Blocks; das Drop-Feld rutschte mit
    heraus und rendert seitdem unformatiert. Fallenkatalog F19/F20."""
    css = (WURZEL / "web" / "app" / "explorer.css").read_text(encoding="utf-8")
    for regel in (".va-drop{", ".va-drop.dz-an{", ".va-portal{"):
        assert regel in css, f"die Regel {regel!r} fehlt — das Feld rendert unformatiert"


def test_die_ueberschriften_nennen_den_zustand():
    """Der Tab heisst „Unterlagen"; die Ueberschrift soll sagen, wie weit wir sind, nicht
    wie das Produkt heisst. Vorher stand ueber allen vier leeren Zustaenden
    „Vergabe-Analyse", und die Beischriften mischten Zustand und Herkunft."""
    code = _ohne_kommentar(CORE.read_text(encoding="utf-8"))
    i = code.index('class="sec va-empty"')
    block = code[i:]
    for zustand in ("Liegen uns vor, Auswertung folgt", "Noch nichts aus diesem Land",
                    "Noch nichts", "Nicht abrufbar"):
        assert zustand in block, f"der Zustand {zustand!r} wird nicht mehr benannt"
    assert 'tk("Vergabe-Analyse")}<span class="cov")' not in block
