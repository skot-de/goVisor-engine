"""Wegklicken mit optionalem Grund, und was man daraus lesen kann.

⚠ Sven am 2026-09-19: „wo kann ich leicht leads löschen … so ein x mit einer kurzen
abfrage nach dem grund wäre cool, aber vll auch nervig."

Den Knopf gab es seit Wochen, und Sven hat ihn nicht gefunden. Drei Gruende, alle behoben:
`opacity:0` bis zum Ueberfahren, ein durchgestrichenes Auge (heisst „nicht anzeigen", nicht
„passt nicht") und die Nachbarschaft zum Stern.

⚠ SEIN ZWEIFEL WAR BERECHTIGT, und die Antwort stand schon im Code. Migration 0021:
„Der Wert des Knopfes ist, dass er einen Klick kostet; wer eine Pflichtbegruendung
davorsetzt, bekommt keine Daten." Deshalb kommt der Grund NACH dem Ausblenden, als Angebot
in einer Leiste, die nach zwoelf Sekunden verschwindet.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SKRIPT = WURZEL / "scripts" / "auswertung_ausgeblendet.py"
SHELL = WURZEL / "web" / "components" / "explorer" / "ExplorerShell.tsx"
CORE = WURZEL / "web" / "lib" / "explorerCore.js"
CSS = WURZEL / "web" / "app" / "explorer.css"


def _modul():
    spec = importlib.util.spec_from_file_location("aus", SKRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules["aus"] = m
    spec.loader.exec_module(m)
    return m


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


def test_der_knopf_ist_ein_kreuz_und_sichtbar():
    """⚠ Drei Gruende, warum ihn niemand fand — alle drei werden hier festgehalten."""
    kern = _ohne_kommentar(CORE.read_text(encoding="utf-8"))
    assert "AUGE_AUS" not in kern, "das Auge ist zurueck — es heisst „nicht anzeigen\", nicht „passt nicht\""
    assert "const KREUZ" in kern and "data-hide" in kern, "der Knopf ist weg"
    css = re.sub(r"/\*[\s\S]*?\*/", "", CSS.read_text(encoding="utf-8"))
    m = re.search(r"\.lt-hide\{([^}]*)\}", css)
    assert m, ".lt-hide gibt es nicht mehr"
    regel = m.group(1).replace(" ", "").replace("\n", "")
    assert "opacity:0;" not in regel and "opacity:0}" not in regel, (
        "der Knopf ist wieder unsichtbar bis zum Ueberfahren — dann findet ihn niemand, "
        "und genau das ist passiert")


def test_der_grund_kommt_nach_dem_klick():
    """⚠ Die Reihenfolge IST die Entscheidung. Eine Pflichtabfrage davor kostet den Klick
    seinen Wert; danach ist sie ein Angebot."""
    code = _ohne_kommentar(SHELL.read_text(encoding="utf-8"))
    i = code.index("function toggleAusblenden")
    block = code[i:i + 1600]
    assert "syncAusgeblendet(" in block, "das Ausblenden schreibt nicht mehr"
    assert "grund" not in block.split("syncAusgeblendet(")[1][:200], (
        "beim Ausblenden wird schon ein Grund verlangt — der Klick kostet dann mehr als "
        "einen Klick")
    assert "function ausGrund" in code, "es gibt keinen Weg, den Grund nachzureichen"
    j = code.index("function ausGrund")
    assert "grund," in code[j:j + 700], "ausGrund reicht den Grund nicht durch"


def test_die_frage_ersetzt_die_zeile():
    """⚠ Sven am 2026-09-19: „klicke ich den 5 lead in der liste an bzw auf das X, dann
    soll anstelle der lead informationen die abfrage eingeblendet werden."

    Mein erster Entwurf hatte eine Leiste ueber der Liste, mit dem Argument, eine Zeile
    lasse die Liste springen. Das Argument gilt fuer einen ZUSAETZLICHEN Platzhalter, nicht
    fuers Ersetzen — die Zeilenzahl bleibt gleich. Und es uebersah den wichtigeren Punkt:
    nach dem fuenften weggeklickten Treffer sucht niemand mehr am oberen Rand nach der
    Frage.
    """
    tab = (WURZEL / "web" / "components" / "explorer" / "LeadTable.tsx").read_text(encoding="utf-8")
    assert "function FrageZeile" in tab, "die Frage steht nicht in der Tabelle"
    # ⚠ OHNE TITEL in der Zeile. Er stand an der Stelle, an der man ihn gerade gelesen und
    # verworfen hat, und drueckte die Knoepfe bei schmalen Fenstern aus der Zeile. Welcher
    # Vorgang gemeint ist, sagt die POSITION. (Gespeichert wird er weiterhin — dort ist er
    # noetig, weil abgelaufene Vorgaenge aus dem Export fallen.)
    i0 = tab.index("function FrageZeile")
    block0 = tab[i0:tab.index("export function LeadTable", i0)]
    assert 'className="af-t"' not in block0, (
        "der Titel steht wieder in der Frage-Zeile")
    # ⚠ Im Block der FrageZeile, nicht irgendwo in der Datei: `colSpan={colspan}` steht
    # auch an der Leer-Zeile („Hier ist gerade nichts"). Der erste Anlauf dieses Tests
    # suchte in der ganzen Datei und blieb gruen, als ich es der Frage weggenommen hatte.
    # ⚠ Bis zur naechsten Funktion schneiden, nicht bis zur naechsten `}`-Zeile: die
    # Typ-Annotation der Props endet selbst mit `}`, und der zweite Anlauf dieses Tests
    # schnitt genau dort ab und pruefte nur noch die Signatur.
    i = tab.index("function FrageZeile")
    block = tab[i:tab.index("export function LeadTable", i)]
    assert "colSpan={colspan}" in block, (
        "die Frage sitzt in einzelnen Zellen — dann muss sie in ein Spaltenraster passen, "
        "das sie nicht meint, und sieht bei jeder Spaltenauswahl anders aus")
    # ⚠ BEIDE Render-Stellen: die Liste hat eine gruppierte und eine flache Fassung, und
    # bis 2026-09-19 ist schon einmal eine davon vergessen worden (data-unread).
    assert tab.count("<FrageZeile") == 2, (
        f"{tab.count('<FrageZeile')} von 2 Render-Stellen zeigen die Frage. Die Liste hat "
        f"eine gruppierte und eine flache Fassung.")
    shell = _ohne_kommentar(SHELL.read_text(encoding="utf-8"))
    assert "fragen.has(String(l.id))" in shell, (
        "der befragte Vorgang wird sofort herausgefiltert — dann steht die Frage an einer "
        "Stelle, an der es keine Zeile mehr gibt, und man sieht gar nichts")
    assert "ausleiste" not in (WURZEL / "web" / "app" / "explorer.css").read_text(encoding="utf-8"), (
        "die alte Leiste ueber der Liste ist noch da — zwei Wege fuer dieselbe Frage")


def test_die_frage_bleibt_bis_jemand_klickt():
    """⚠ Sven am 2026-09-19: „der eintrag soll stehen bleiben bis er was geklickt hat."

    Meine erste Fassung raeumte die Frage nach zwoelf Sekunden weg, begruendet damit, eine
    stehende Frage sei ein Dialog mit Extraschritten. Das stimmt fuer eine Frage, die den
    Weg versperrt — diese steht an der Stelle einer Zeile, die ohnehin verschwinden sollte,
    und versperrt nichts.

    Die haessliche Folge des Zeitgebers: wer beim Lesen unterbrochen wird, findet nach dem
    Blick aus dem Fenster eine Liste vor, in der etwas fehlt, ohne je gefragt worden zu
    sein. Die Frage ist die einzige Stelle, an der die Ausblendung noch sichtbar ist.

    ⚠ Sie geht trotzdem nicht ewig: wer den naechsten Vorgang ausblendet, schiebt die Frage
    dorthin, und der erste verschwindet still. Das ist die EINZIGE Stelle, an der sie von
    allein geht, und sie ist eine Entscheidung des Nutzers.
    """
    code = _ohne_kommentar(SHELL.read_text(encoding="utf-8"))
    assert "setTimeout" not in " ".join(
        code.split("function toggleAusblenden")[1][:4000].split())[:900], (
        "die Frage raeumt sich wieder nach einer Frist weg — dann fehlt in der Liste "
        "etwas, wonach niemand gefragt wurde")
    assert "ausLeisteTimer" not in code, "der Zeitgeber ist noch da"
    # ⚠ Leerraum einziehen, BEVOR gefenstert wird: `_ohne_kommentar` ersetzt Kommentare
    # durch Leerzeichen, und ein Block mit zwanzig Kommentarzeilen ist dann tausend
    # Zeichen lang, ohne eine einzige Anweisung zu enthalten. Der erste Anlauf dieses
    # Tests hat genau darin nichts gefunden und den Code fuer kaputt erklaert.
    i2 = code.index("function toggleAusblenden")
    block = " ".join(code[i2:i2 + 4000].split())[:900]
    assert "if (jetztAus) n.set(id," in block, "beim Ausblenden wird keine Frage gestellt"
    assert "else n.delete(id)" in block, (
        "beim WIEDEREINBLENDEN bleibt die Frage stehen")


def test_oberflaeche_und_auswertung_kennen_dieselben_gruende():
    """⚠ Zwei Kataloge derselben Sache altern auseinander, und der Bruch faellt erst auf,
    wenn die Zahlen nicht mehr aufgehen: ein umbenannter Knopf macht alle alten Klicks zu
    Waisen, die aus jeder Statistik verschwinden."""
    ui = re.search(r"AUS_GRUENDE = \[([^\]]*)\]", SHELL.read_text(encoding="utf-8"))
    assert ui, "AUS_GRUENDE gibt es nicht mehr"
    ui_liste = re.findall(r'"([^"]+)"', ui.group(1))
    assert ui_liste == _modul().GRUENDE, (
        f"Oberflaeche {ui_liste} gegen Auswertung {_modul().GRUENDE}")
    # ⚠ SECHS seit dem 2026-09-20 (Svens Vorgabe). Die Grenze ist nicht Geschmack, sondern
    # Platz: die Leiste steht an der Stelle einer Tabellenzeile und darf nicht umbrechen.
    # Gemessen brauchen die sechs 951 px; unterhalb dieser Breite scrollt die Tabelle
    # ohnehin waagerecht. Ein siebter Knopf muss erst wieder gemessen werden.
    assert len(ui_liste) == 6, (
        f"{len(ui_liste)} Gruende statt 6. Jeder weitere kostet Platz in einer Leiste, die "
        f"in EINE Zeile passen muss — nachmessen, nicht schaetzen.")
    assert not any("sonst" in g.lower() for g in ui_liste), (
        "„Sonstiges\" traegt keine Information und zieht erfahrungsgemaess die Haelfte "
        "aller Klicks auf sich")


def test_der_bericht_rechnet():
    """Faehrt `bericht()` mit Kunstdaten — ohne Datenbank, aber mit echter Logik."""
    m = _modul()
    zeilen = ([{"lead_id": f"a{i}", "grund": "falscher Inhalt", "titel": "x",
                "buyer": "Stadt Ulm", "user": "u1", "am": "2026-09-19"} for i in range(6)]
              + [{"lead_id": f"b{i}", "grund": "", "titel": "y",
                  "buyer": "Kreis Lippe", "user": "u2", "am": "2026-09-19"} for i in range(4)])
    b = m.bericht(zeilen, mindestens=5)
    assert b["ausgeblendet"] == 10 and b["nutzer"] == 2
    assert b["mit_grund"] == 6 and b["grund_quote"] == 60.0
    assert b["gruende"] == [{"wert": "falscher Inhalt", "n": 6}]
    # ⚠ Die Schwelle muss BEIDE Richtungen koennen: „Kreis Lippe" hat 4 und faellt raus.
    assert [e["wert"] for e in b["kaeufer"]] == ["Stadt Ulm"], (
        "die Schwelle greift nicht — drei Klicks auf denselben Kaeufer sind kein Muster, "
        "sondern ein Mensch mit einem Nachmittag")


def test_ein_grund_ohne_knopf_faellt_auf():
    """⚠ Wer einen Knopf umbenennt, macht alle alten Klicks zu Waisen. Ohne diese Meldung
    verschwinden sie stillschweigend aus jeder Statistik."""
    m = _modul()
    b = m.bericht([{"lead_id": "a", "grund": "aus Versehen", "titel": "", "buyer": "",
                    "user": "u", "am": "2026-09-19"}], mindestens=1)
    assert b["unbekannte_gruende"] == ["aus Versehen"]


def test_leere_auswertung_ist_kein_fehler():
    """⚠ Ein junges Produkt hat keine Daten, und ein Bericht, der darueber rot wird, wird
    abgeschaltet statt gelesen."""
    m = _modul()
    b = m.bericht([], mindestens=5)
    assert b["ausgeblendet"] == 0 and b["grund_quote"] == 0.0
    assert b["gruende"] == [] and b["unbekannte_gruende"] == []


def test_das_kreuz_hat_eine_groesse():
    """⚠ GEMESSEN, NICHT VERMUTET — und nur deshalb gefunden. Im ersten gerenderten Bild
    war der Knopf 4 x 18 px gross, also praktisch unsichtbar, obwohl das SVG `width="14"`
    traegt.

    Ursache: `globals.css` setzt `img,svg{display:block;max-width:100%}`. In einem Knopf
    ohne eigene Breite sind 100 % von nichts gleich nichts, und das Attribut zaehlt dann
    nicht mehr. Der Stern daneben hat genau deshalb seit jeher `.tstar svg{width:14px}` —
    beim Kreuz fehlte sie.

    ⚠ Die Falle gilt fuer JEDES neue Icon in einem Knopf dieser Oberflaeche. Sie faellt in
    keinem Test auf, der Quelltext liest, und in keiner Typpruefung; man sieht sie nur im
    Bild.
    """
    css = re.sub(r"/\*[\s\S]*?\*/", "", CSS.read_text(encoding="utf-8"))
    m = re.search(r"\.lt-hide svg\{([^}]*)\}", css)
    assert m, (
        ".lt-hide svg hat keine Groessenregel — das Kreuz ist dann 0 px breit, weil "
        "globals.css `img,svg{max-width:100%}` setzt")
    assert "width:" in m.group(1) and "height:" in m.group(1), (
        "Breite oder Hoehe fehlt")
    # ⚠ Die Zelle muss beide Symbole tragen: 14 + 6 + 14 passen nicht in 30 px.
    z = re.search(r"td\.c-star\{([^}]*)\}", css)
    assert z, "td.c-star gibt es nicht mehr"
    breite = re.search(r"width:(\d+)px", z.group(1))
    assert breite and int(breite.group(1)) >= 44, (
        f"die Sternspalte ist {breite.group(1) if breite else '?'} px breit — Stern und "
        f"Kreuz brauchen zusammen mindestens 44")


def test_die_auswertung_laeuft_jede_nacht():
    """⚠ Ein Bericht, den man erst einschaltet, wenn man ihn braucht, existiert an dem Tag
    noch nicht. `gold_integrity` hing monatelang an einem Netzlauf, den niemand startete —
    aufgefallen ist es an 28 Waisen, die AT einen Tag lang trug."""
    sh = (WURZEL / "scripts" / "daily_leads.sh").read_text(encoding="utf-8")
    assert "auswertung_ausgeblendet.py" in sh, "die Auswertung laeuft in keiner Nacht"
    i = sh.index("$PY scripts/auswertung_ausgeblendet.py")
    assert "--mindestens" in sh[i:i + 120], (
        "ohne Schwelle meldet der Bericht Einzelklicks als Muster")


def test_die_frage_zeile_ist_so_hoch_wie_die_anderen():
    """⚠ GEMESSEN: ohne `min-height` war die Frage-Zeile 40 px hoch neben 47 px hohen
    Nachbarn — die Liste ruckte beim Klicken um sieben Pixel, und beim Verschwinden noch
    einmal. Genau das, was dieser Entwurf vermeiden sollte, und mein eigener Kommentar
    behauptete bereits, es sei geloest.

    `min-height` und nicht festes Polster: eine laengere Gruenden-Liste darf die Zeile
    wachsen lassen, statt abgeschnitten zu werden.
    """
    css = re.sub(r"/\*[\s\S]*?\*/", "", CSS.read_text(encoding="utf-8"))
    m = re.search(r"\.ausfrage\{([^}]*)\}", css)
    assert m, ".ausfrage gibt es nicht mehr"
    regel = m.group(1).replace(" ", "").replace("\n", "")
    h = re.search(r"min-height:(\d+)px", regel)
    assert h and int(h.group(1)) >= 44, (
        f"min-height fehlt oder ist zu klein ({h.group(1) if h else 'keine'}) — die Liste "
        f"ruckt dann beim Klicken")
    assert "box-sizing:border-box" in regel, (
        "ohne border-box addiert sich das Polster auf die Mindesthoehe und die Zeile wird "
        "zu hoch statt gleich hoch")


def test_das_ausblenden_rechnet_die_liste_nicht_neu():
    """⛔ Sven am 2026-09-20: „die ladezeit bis die reaktion nach dem klick auf x ist
    vieeel zu lang."

    Ursache war `bump()` in `toggleAusblenden`. Es erhoeht `tick`, und an `tick` haengen
    vier Berechnungen. Die teuerste ist `facetZahlen`: sie fuehrt JE FACETTE UND JE WERT
    einen vollen `postFilter` aus — gemessen **40 Durchlaeufe ueber 17.753 Leads** im
    Grundraum bau, und `postFilter` tut je Lead mehr als ein trivialer Durchlauf.

    ⚠ MESSEN STATT VERMUTEN HAT HIER ZWEIMAL GESPART. Die naheliegenden Verdaechtigen
    waren schnell: die Filterkette braucht 2 bis 6 ms, der Zeilenaufbau 1 bis 3 ms. Wer
    dort optimiert haette, haette Stunden verloren und nichts gefunden.

    Gebraucht wird `bump()` an dieser Stelle nicht: `setAusgeblendet` und `setFragtNach`
    sind State und zeichnen die Liste ohnehin neu, `rows` haengt bereits an
    `ausgeblendet`, und die Facettenzahlen zaehlen ABSICHTLICH ohne Ausblendungen.
    """
    code = _ohne_kommentar(SHELL.read_text(encoding="utf-8"))
    i = code.index("function toggleAusblenden")
    block = " ".join(code[i:i + 4000].split())[:900]
    assert "bump()" not in block, (
        "bump() ist zurueck in toggleAusblenden — ein Klick auf das Kreuz rechnet dann "
        "wieder die Facettenzahlen neu, also 40 volle Durchlaeufe ueber den Grundraum")
    # ⚠ Gegenprobe zur Gegenprobe: `rows` MUSS an `ausgeblendet` haengen, sonst verschwindet
    # die Zeile ohne bump() gar nicht mehr.
    m = re.search(r"\}, \[aktiveBranche, sortKey, sortDir, tokens, filters, tick[^\]]*\]", code)
    assert m and "ausgeblendet" in m.group(0), (
        "rows haengt nicht mehr an `ausgeblendet` — ohne bump() bliebe die ausgeblendete "
        "Zeile dann einfach stehen")


def test_kein_label_braucht_kontextwissen():
    """⚠ Sven am 2026-09-20: „geh davon aus das die nutzer dumm sind. die label müssen
    kurz und einleuchtend sein." Anlass war „nicht unser Fach" — „Fach" heisst im
    Deutschen zuerst Schulfach, dann Schrankfach, und erst im Handwerk das Gewerk.

    Dieser Test haelt die drei Woerter fest, die im PRODUKT besetzt oder zu grob sind und
    deshalb nie wieder auftauchen duerfen — jedes davon war beim Formulieren der naechste
    naheliegende Kandidat:

    · `Fach`     mehrdeutig (Schulfach), der urspruengliche Befund
    · `bieten`   im Vergabekontext besetzt: 53-mal „Bieter" im Quelltext. „Bieten wir
                 nicht an" liest sich als „wir geben kein Angebot ab" — eine
                 Terminentscheidung statt einer Leistungsfrage.
    · `Branche`  im Produkt der GRUNDRAUM (Bau, IT, Medizin). Wer im Bau-Raum eine
                 Dachdecker-Ausschreibung wegklickt, meint das Gewerk, nicht die Branche —
                 eine daraus abgeleitete Regel blendete den halben Bestand aus.
    """
    ui = re.search(r"AUS_GRUENDE = \[([^\]]*)\]", SHELL.read_text(encoding="utf-8"))
    assert ui, "AUS_GRUENDE gibt es nicht mehr"
    labels = re.findall(r'"([^"]+)"', ui.group(1))
    for wort in ("Fach", "bieten", "Bieten", "Branche"):
        treffer = [g for g in labels if wort in g]
        assert not treffer, (
            f"{treffer} benutzt {wort!r} — im Produkt besetzt oder mehrdeutig, "
            f"Begruendung im Kopf dieses Tests")
    for g in labels:
        # ⚠ 21 statt 17 Zeichen seit „Fehlerhafte Zuordnung". Die Schwelle ist gemessen,
        # nicht gesetzt: mit dieser Laenge brauchen die sechs Knoepfe 951 px, und darunter
        # scrollt die Tabelle ohnehin. Wer sie hochsetzt, misst vorher nach.
        assert len(g) <= 21, f"{g!r} ist {len(g)} Zeichen lang; in der Zeile ist kein Platz"
        assert g[0].isupper(), f"{g!r} faengt klein an, die sechs stehen nebeneinander"
        # ⚠ Nach einem „zu" folgt im Deutschen ein Adjektiv, und das schreibt man klein.
        # Svens Vorlage hatte „Zu Umfangreich" und „Zu Kurzfristig" — die einzige Aenderung
        # an seinen Worten, und eine, die man in einem Knopf sofort sieht.
        if g.startswith("Zu "):
            assert g.split()[1][0].islower(), (
                f"{g!r}: nach „Zu\" folgt ein Adjektiv, das klein geschrieben wird")


def test_jeder_weggeklickte_vorgang_behaelt_seine_frage():
    """⛔ Sven am 2026-09-20: „wenn ich ein lead weggeklickt habe und der gelbe balken
    kommt, kann ich weitere leads einfachso wegklicken ohne das der gelbe balken kommt."

    Die Zustandslogik war richtig — nachgestellt wanderte die Frage sauber zum neuen
    Vorgang. Der Fehler lag eine Ebene hoeher: es gab nur EINE. Der zweite Klick erbte den
    Balken, und der erste Vorgang verschwand still, ohne dass jemand geantwortet hatte.

    ⚠ Das stand zwei Tage vorher schon als Kommentar im Code („der erste verschwindet
    still") — ich hatte es fuer einen Nebeneffekt gehalten statt fuer einen Widerspruch zu
    Svens Ansage, die Zeile solle stehen bleiben, bis geklickt wird. Ein Satz, der ein
    Problem richtig beschreibt und es „bewusst so" nennt, ist keine Begruendung.
    """
    shell = _ohne_kommentar(SHELL.read_text(encoding="utf-8"))
    assert "useState<Map<string, string>>" in shell, (
        "es gibt wieder nur EINE offene Frage — der zweite Klick erbt sie dann, und der "
        "erste Vorgang verschwindet ohne Antwort")
    assert "fragtNach" not in shell, "Rest der Einzelfrage-Fassung"

    tab = (WURZEL / "web" / "components" / "explorer" / "LeadTable.tsx").read_text(encoding="utf-8")
    assert tab.count("fragen?.has(String(l.id))") == 2, (
        "nicht beide Render-Stellen (gruppiert und flach) kennen mehrere Fragen")

    # ⚠ Die Kennung MUSS an `onAusGrund` mit: mit zehn offenen Balken waere „der zuletzt
    # ausgeblendete" die Sorte Fehler, die den falschen Vorgang begruendet und nie auffaellt.
    assert "onAusGrund?: (id: string, grund: string) => void;" in tab, (
        "der Grund wird ohne Kennung gemeldet — bei mehreren offenen Fragen landet er am "
        "falschen Vorgang")
    assert "function ausGrund(id: string, grund: string)" in shell, (
        "ausGrund nimmt die Kennung nicht entgegen")
