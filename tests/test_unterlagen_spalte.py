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


def test_die_fuenf_zustaende_sind_unterscheidbar():
    """⚠ Gemessen ueber 17.837 Leads in Bau (ohne Zuschlaege):

        nur der Link, nichts gelesen        13.909   78,0 %
        analysiert, mit Pruefpunkten         2.105   11,8 %
        Text liegt vor, Auswertung offen     1.383    7,8 %
        gar nichts                             345    1,9 %
        analysiert, nichts gefunden             95    0,5 %

    ⚠ ICH HATTE HIER EINEN ZUSTAND ZU WENIG. Auf Svens Frage nach drei Zustaenden
    antwortete ich, „nur Gliederung gelesen" gebe es nicht — gestuetzt allein auf die
    ausgelieferten Lead-Daten. Sein Widerspruch war richtig: „bei einigen portalen lesen
    wir nur die gliederung aus, weil wir die unterlagen nicht automatisiert herunterladen
    dürfen." Der Zustand steht in `doc_listing_*.parquet` (subreport, vergabeportal.at):
    2.670 Vorgaenge mit 53.966 gelisteten Dateien, davon 518 in Bau. Sie sahen aus wie ein
    blosser Link, obwohl wir wissen, WELCHE Unterlagen es gibt.

    ⚠ Die Manifest-Zeilen mit Status `nur_liste` tragen KEINE notice_id (alle 1.606 sind
    NULL) — ueber sie ist der Zustand nicht zuzuordnen. Die Listen selbst haben eine
    lead_id.
    """
    z = _zelle()
    for klasse, was in (("dok dok-", "analysiert mit Pruefpunkten"),
                        ("dok-leer", "analysiert, nichts gefunden"),
                        ("dok-warte", "Text liegt vor, Auswertung offen"),
                        ("dok-liste", "nur die Gliederung gelesen")):
        assert klasse in z, f"der Zustand {was!r} ist nicht mehr unterscheidbar"
    assert z.index("dok-warte") < z.index("dok-liste"), (
        "die Reihenfolge stimmt nicht: vorhandener Volltext schlaegt die Gliederung")
    # ⚠ Wo wir NICHTS haben, bleibt die Zelle leer und stumm. Vorher stand dort „Link"
    #   (75,1 % aller Zellen) bzw. ein Strich — beides die ABWESENHEIT unserer Arbeit, in
    #   derselben Position, in der sonst eine Anzahl steht.
    assert '<td class="c-doks"></td>' in z, (
        "wo wir nichts haben, steht wieder etwas in der Zelle")


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
    assert knoepfe == 4, (
        f"nur {knoepfe} von 4 Zustaenden sind Knoepfe. Ein `<span>` ist mit der Tastatur "
        f"nicht erreichbar und traegt keinen Fokusring.")
    assert not re.search(r"<span[^>]*data-doklink", z), (
        "ein Zustand ist wieder ein `<span>` — nicht fokussierbar, nicht per Tastatur "
        "ausloesbar")


def test_kein_hilfe_zeiger_auf_etwas_das_wegspringt():
    """⚠ `cursor: help` verspricht einen Hinweis. Wer darauf klickt, landet in einer
    anderen Ansicht — das ist die Sorte kleiner Luege, die Vertrauen kostet."""
    css = re.sub(r"/\*[\s\S]*?\*/", "",
                 (WURZEL / "web" / "app" / "explorer.css").read_text(encoding="utf-8"))
    for kl in ("dok-warte", "dok-leer"):
        m = re.search(rf"\.{kl}\b[^{{]*\{{([^}}]*)\}}", css)
        assert m, f".{kl} gibt es nicht mehr"
        assert "cursor:help" not in m.group(1).replace(" ", ""), (
            f".{kl} traegt wieder den Hilfe-Zeiger, obwohl der Klick wegspringt")


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
    """Sven: „bei jedem klick landet man in den ausschreibungs details unter Unterlagen."
    Vorher trugen nur `Gliederung` und `Link` die Kennung; bei den anderen vier passierte
    dasselbe wie beim Klick auf jede andere Zelle."""
    z = _zelle()
    assert z.count("data-doklink=") == 4, (
        f"{z.count('data-doklink=')} statt 4 Zustaende fuehren in den Unterlagen-Tab. "
        f"Seit dem 2026-09-19 sind es vier: die zwei Zustaende ohne eigene Arbeit "
        f"(nur Link, gar nichts) zeigen nichts mehr an und springen auch nicht.")


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
