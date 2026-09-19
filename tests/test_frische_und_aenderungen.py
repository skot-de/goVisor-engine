"""Was ist seit deinem letzten Besuch passiert? (`baue_aenderungen.py`, `besuch.ts`, Marke)

⚠ DER ANLASS WAR EINE FRAGE, KEIN FEHLERBERICHT. Sven am 2026-09-19, nachdem der gruene
Teppich aus der Liste geflogen war: „sind die neuen ausschreibungen nun nicht mehr
gehighlighted?" Die ehrliche Antwort war: sie waren es nie. Das Gruen hing an
`status='ungesichtet'`, und der Export schreibt diesen Wert als Konstante in jeden Lead.

Beim Nachsehen kam Schlimmeres heraus. `aktualitaet` — das Feld hinter dem Faehnchen
„geaendert"/„aufgehoben" am Titel — stand in ALLEN 85.168 Leads auf `None`, weil der Export
es als feste Null schrieb. Und eine Ebene tiefer traf `notice_kind='corrigendum'` seit dem
2024-02-05 nichts mehr:

    Jahr   Ausschreibungen   erkannte Berichtigungen
    2023        171.607              14.835
    2024        172.605                 790
    2025        168.884                   0
    2026        132.048                   0

Kein Rueckgang im Markt, sondern ein Formatwechsel: eForms kennt kein eigenes
Berichtigungsformular, eine Berichtigung IST eine neu veroeffentlichte `ContractNotice` mit
einem `<efac:Changes>`-Block. Gemessen ueber 37.398 Meldungen aus 2026-07..09 sind
**13,4 % aller Meldungen Berichtigungen**; daraus wurden 12.557 Ereignisse auf 7.913
Bekanntmachungen, darunter 4.632 Fristaenderungen und 13 Aufhebungen.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SONDE = WURZEL / "web" / "scripts" / "pruefe-frische.mjs"
CORE = WURZEL / "web" / "lib" / "explorerCore.js"
BESUCH = WURZEL / "web" / "lib" / "besuch.ts"
ERZEUGER = WURZEL / "scripts" / "baue_aenderungen.py"
EXPORT = WURZEL / "scripts" / "export_web_leads.py"
SCHEMA = WURZEL / "govisor" / "schema.py"


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


def test_die_marke_haelt_ihre_regeln():
    """Faehrt die ECHTE `frischeMarke` mit allen vier Eingaengen."""
    if not shutil.which("node"):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-400:]
    assert "Eine Marke je Zeile" in r.stdout


def test_die_sonde_sieht_eine_zweite_marke():
    """Gegenprobe mit dem gefaehrlichsten Fall: zwei Auszeichnungen in einer Zeile.

    ⚠ Genau dagegen ist der Entwurf gebaut. „Neu" ist eine Zeitachse, „geaendert" eine
    Ereignisart; wer beides nebeneinander zeigt, zwingt den Leser, sie gegeneinander
    abzuwaegen — und liefert bei 13,6 % frischen Leads wieder einen Teppich.
    """
    if not shutil.which("node"):
        return
    echt = CORE.read_text(encoding="utf-8")
    anker = "  // Kein Ereignis, aber juenger als der letzte Besuch: schlicht neu.\n  if(l.pub"
    assert anker in echt, "die Stelle fuer die Gegenprobe sieht anders aus"
    kaputt = echt.replace(anker, "  // mutiert\n  if(l.pub", 1)
    # aus `return ...` ein Anhaengen machen: dann kaemen beide Marken
    kaputt = kaputt.replace(
        '    return `<span class="akttag akt-${art}" title="${esc(hinweis)}">${wort}</span>`;',
        '    var vorab = `<span class="akttag akt-${art}" title="${esc(hinweis)}">${wort}</span>`;'
        ' if(!(l.pub && seit && l.pub > seit)) return vorab;', 1)
    kaputt = kaputt.replace(
        '    return `<span class="akttag akt-neu"',
        '    return vorab + `<span class="akttag akt-neu"', 1)
    try:
        CORE.write_text(kaputt, encoding="utf-8")
        r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
        assert r.returncode != 0, "die Sonde laesst zwei Marken in einer Zeile durch"
        assert "eine Marke, nicht zwei" in r.stdout
    finally:
        CORE.write_text(echt, encoding="utf-8")


def test_eine_aufhebung_verfaellt_nicht():
    """⚠ Diese Unterscheidung hat die Gegenprobe erzwungen, nicht der Entwurf.

    Die erste Fassung liess JEDES Ereignis vor dem letzten Besuch verfallen — auch die
    Aufhebung. Dann steht „neu" ueber einer Ausschreibung, auf die niemand mehr bieten
    kann. Eine Fristaenderung ist eine Nachricht und irgendwann gelesen; eine Aufhebung ist
    ein Zustand und bleibt.
    """
    kern = _ohne_kommentar(CORE.read_text(encoding="utf-8"))
    m = re.search(r"AKT_BLEIBT = new Set\(\[([^\]]*)\]\)", kern)
    assert m, "die Unterscheidung zwischen Zustand und Nachricht ist weg"
    bleibt = set(re.findall(r"'(\w+)'", m.group(1)))
    assert bleibt == {"aufgehoben", "ausgesetzt"}, (
        f"dauerhaft sind {sorted(bleibt)}. Erwartet aufgehoben und ausgesetzt — beides "
        f"schliesst den Vorgang, alles andere ist eine Nachricht.")
    assert "AKT_BLEIBT.has(a.art)" in kern, "die Ausnahme wird nicht angewendet"


def test_der_besuch_wird_beim_verlassen_gemerkt():
    """⚠ Wer den Stempel beim LADEN setzt, loescht die Antwort auf die Frage, die er gerade
    stellt: alles waere sofort „nicht mehr neu", und zwar dauerhaft und lautlos."""
    code = _ohne_kommentar((WURZEL / "web" / "components" / "explorer" / "ExplorerShell.tsx")
                           .read_text(encoding="utf-8"))
    i = code.index("setStichtag(stichtag())")
    fenster = code[i:i + 420]
    assert "besuchMerken" in fenster, "der Besuch wird nie gemerkt"
    assert "pagehide" in fenster, (
        "der Stempel haengt an keinem Verlassen-Ereignis — dann bleibt er beim ersten "
        "Besuch stehen und jede Zeile ist fuer immer neu")
    vor = code[max(0, i - 300):i]
    assert "besuchMerken()" not in vor, (
        "gemerkt wird VOR dem Lesen des Stichtags — damit ist nie wieder etwas neu")


def test_der_stichtag_kommt_von_aussen():
    """⚠ `explorerCore.js` laeuft in den Sonden unter `node`, wo es kein `localStorage`
    gibt. Ein Zugriff dort wuerde die halbe Pruefkette mit einem ReferenceError stoppen."""
    kern = _ohne_kommentar(CORE.read_text(encoding="utf-8"))
    # ⚠ NUR DIE MARKE, nicht die ganze Datei: explorerCore benutzt `localStorage` an
    # anderen Stellen seit jeher, dort aber in try/catch und nur im Browser-Pfad. Der
    # erste Anlauf dieses Tests verbot es global und schlug an fremdem, gesundem Code an.
    i = kern.index("function frischeMarke")
    marke = kern[i:kern.index("\n}", i)]
    assert "localStorage" not in marke, (
        "die Marke greift auf localStorage zu — unter node ein ReferenceError")
    assert "export function setStichtag" in kern, "der Stichtag laesst sich nicht setzen"


def test_der_export_traegt_ereignis_und_datum():
    """⚠ „Gebaut, nicht verdrahtet" ist die haeufigste Fehlerklasse dieses Projekts — und
    `aktualitaet` war ihr laengster Fall: das Frontend rendert das Faehnchen seit jeher, der
    Export schrieb `None`. Genau deshalb prueft dieser Test die SCHREIBENDE Seite."""
    # ⚠ Kommentare raus. Der Kommentar an der Fundstelle ZITIERT die alte Zeile als
    # Begruendung — ohne Strippen schlaegt der Test an seiner eigenen Erklaerung an (F13).
    code = "\n".join(z.split("#")[0] for z in EXPORT.read_text(encoding="utf-8").splitlines())
    assert '"aktualitaet": None' not in code, (
        "der Export schreibt wieder eine feste Null — das Faehnchen erscheint dann nie")
    assert '"aktualitaet": AENDERUNG.get(' in code, "das Ereignis wird nicht angehaengt"
    assert '"pub": VEROEFFENTLICHT.get(' in code, "das Veroeffentlichungsdatum fehlt"
    for name in ("_aenderungs_index", "_veroeffentlicht_index"):
        assert f"{name}()" in code and f"def {name}" in code, (
            f"{name} ist definiert, wird aber nicht aufgerufen (oder umgekehrt)")


def test_die_erkennung_liegt_im_parser_nicht_im_skript():
    """⚠ Eine zweite Fassung derselben Regel altert unbemerkt. `baue_aenderungen.py` liest
    Roh-XML, der Parser liest dieselben Dateien — beide muessen dieselbe Vorstellung davon
    haben, was eine Berichtigung ist."""
    assert "def eforms_changes(" in SCHEMA.read_text(encoding="utf-8"), (
        "die Erkennung steht nicht mehr im Parser")
    code = ERZEUGER.read_text(encoding="utf-8")
    assert "from govisor.schema import eforms_changes" in code, (
        "der Erzeuger baut die Erkennung selbst nach")
    assert "efac:Changes" not in code.split('"""', 2)[-1], (
        "der Erzeuger sucht selbst im XML statt den Parser zu fragen")


def test_die_ereignisarten_sind_vollstaendig_belegt():
    """⚠ Jede Art in der Zuordnung muss einen gemessenen Code hinter sich haben. Die Liste
    stammt aus 5.028 Berichtigungen (2026-07..09); wer eine Art erfindet, erzeugt eine
    Marke, die nie erscheint, und merkt es nie."""
    code = ERZEUGER.read_text(encoding="utf-8")
    m = re.search(r"_ART = \{([^}]*)\}", code)
    assert m, "_ART gibt es nicht mehr"
    arten = set(re.findall(r':\s*"(\w+)"', m.group(1)))
    assert arten == {"aufgehoben", "ausgesetzt", "geaendert"}, (
        f"Arten aus den Gruenden: {sorted(arten)}. „frist\" darf NICHT dabei sein — sie "
        f"entsteht aus dem VERGLEICH der Fristen, nicht aus einem Grundcode.")
    assert 'art = "frist"' in code, "die Fristaenderung wird nicht mehr erkannt"
    kern = _ohne_kommentar(CORE.read_text(encoding="utf-8"))
    i = kern.index("const AKT_WORT")
    ui = set(re.findall(r"(\w+):'", kern[i:kern.index("}", i)]))
    assert arten <= ui | {"frist"}, f"die Oberflaeche kennt nicht alle Arten: {sorted(arten - ui)}"


def test_besuch_haelt_kaputten_speicher_aus():
    """⚠ Privater Modus, voller Speicher, abgeschaltete Site-Daten: `localStorage` wirft.
    Ein Frischehinweis darf die Liste nicht mitreissen."""
    code = BESUCH.read_text(encoding="utf-8")
    # ⚠ Am Verhaeltnis gemessen, nicht an einer geratenen Zahl: der erste Anlauf verlangte
    # drei `catch` und fand zwei — richtig waren zwei, weil `stichtag()` ueber
    # `letzterBesuch()` geht und dessen Absicherung erbt. Eine feste Zahl im Test haette
    # beim naechsten Zugriff wieder gestimmt und beim uebernaechsten nicht.
    zugriffe = code.count("localStorage.")
    assert zugriffe >= 2, "es gibt keinen Speicherzugriff mehr"
    assert code.count("catch") >= zugriffe, (
        f"{zugriffe} Zugriffe auf localStorage, aber nur {code.count('catch')} Absicherungen")
    assert ".test(d.am)" in code.replace(" ", ""), (
        "der gelesene Wert wird nicht geprueft — ein beschaedigter Eintrag vergleicht sich "
        "dann als Zeichenkette gegen ein Datum")


def test_der_erzeuger_laeuft_vor_dem_export():
    """⚠ REIHENFOLGE IM NACHTLAUF. `export_web_leads.py` LIEST `notice_changes.parquet`.
    Steht der Erzeuger dahinter, traegt die Liste jeden Tag den Stand von gestern — und
    beim allerersten Lauf gar keinen. Derselbe Fehler steckte schon einmal in
    `region_ableiten.py` und fiel nur an nicht passenden Zeilennummern auf.
    """
    sh = (WURZEL / "scripts" / "daily_leads.sh").read_text(encoding="utf-8")
    assert "baue_aenderungen.py" in sh, "der Erzeuger laeuft in keiner Nacht"
    i = sh.index("$PY scripts/baue_aenderungen.py")
    j = sh.index("$PY scripts/export_web_leads.py")
    assert i < j, (
        "der Erzeuger steht HINTER dem Export — die Liste zeigt dann taeglich den Stand "
        "von gestern")


def test_die_laenderluecke_steht_als_luecke_da():
    """⚠ CLAUDE.md: wer ein Feature nur fuer DE baut, hat es angefangen, nicht fertig
    gebaut. `notice_changes` gibt es nur fuer DE, weil die Erkennung an eForms haengt —
    das gehoert in `OFFEN_NUR_DE` (Baustelle), nicht in `BEWUSST_NUR_DE` (Entscheidung).
    """
    code = (WURZEL / "scripts" / "pruefe_verdrahtung.py").read_text(encoding="utf-8")
    i = code.index("OFFEN_NUR_DE: dict[str, str] = {")
    assert "notice_changes" in code[i:code.index("\n}", i)], (
        "die Laenderluecke ist nicht als offen eingetragen")
    j = code.index("BEWUSST_NUR_DE: dict[str, str] = {")
    assert "notice_changes" not in code[j:code.index("\n}", j)], (
        "die Luecke steht als BEWUSSTE Entscheidung da — sie ist aber eine Baustelle")


# ── Geschwister desselben Vergabeverfahrens ─────────────────────────────────────────────
#
# ⚠ Sven am 2026-09-19: „mach die dubletten auch." Gemessen waren 163 Verfahren mit
# mehreren OFFENEN Leads, 377 Zeilen, **214 davon ueberzaehlig**. „Metallbau Aussen/
# Kunststofffenster" stand vier Mal in der Liste, alle vier mit derselben Frist.
#
# ⚠ WARUM DIE BESTEHENDE FIREWALL SIE NICHT FAND. `govisor/dedupe.py` vergleicht Titel und
# Kaeufer und sperrt das Zusammenlegen zweier Saetze DERSELBEN Quelle — zu Recht, denn TED
# fuehrt legitim mehrere Verfahren mit gleichem Titel. Nachgemessen kannte sie das Paar
# 600363_2026 / 606341_2026 nicht: beide standen einzeln als Master gegen
# Landesportal-Dubletten, aber nie gegeneinander.

def test_veraltete_geschwister_fliegen_aus_der_liste():
    """Der Export ueberspringt sie, und die Zahl steht im Lauf."""
    code = EXPORT.read_text(encoding="utf-8")
    assert "if r[\"lead_id\"] in VERALTET:" in code, (
        "veraltete Geschwister werden nicht mehr uebersprungen")
    assert "_uebersprungen += 1" in code and "_uebersprungen}" in code, (
        "der Filter zaehlt nicht oder meldet nicht. Ein stiller Filter nimmt eines Tages "
        "zu viel weg und sagt es niemandem — die Fehlerklasse, an der dieses Projekt "
        "schon mehrfach haengengeblieben ist.")


def test_der_juengste_geschwister_gewinnt():
    """⚠ WEGEN DER FRIST, nicht aus Ordnungsliebe. Gemessen tragen Geschwister
    VERSCHIEDENE Fristen — bei „Rahmenvereinbarung ueber Technologiespezifische …" standen
    2026-09-22 und 2026-10-06 nebeneinander. Wer den aelteren behaelt, zeigt eine Frist,
    die nicht mehr gilt.
    """
    code = EXPORT.read_text(encoding="utf-8")
    i = code.index("def _verfahrens_dubletten")
    block = code[i:code.index("\nGLIEDERUNG", i)]
    sql = " ".join(block.split())
    assert "ORDER BY p.am DESC, p.notice_id DESC" in sql, (
        "die Reihenfolge ist nicht mehr zweistufig. Ohne das Datum gewinnt nicht der "
        "juengste; ohne die Kennung als zweiten Schluessel entscheidet bei gleichem Datum "
        "der Zufall, der Master wechselt zwischen zwei Laeufen und jeder gemerkte Vorgang "
        "wandert mit.")
    assert "WHERE rn = 1" in sql and "g.rn > 1" in sql, (
        "nicht mehr der juengste ist der Master")
    # ⚠ Die Phasenbedingung ist der Rand, an dem die Regel beim ersten Lauf zu weit griff:
    # EIN `open` musste einem `expiring` weichen — eine laufende Ausschreibung einem
    # auslaufenden Vertrag.
    assert "g.phase = m.phase" in sql, (
        "Geschwister verschiedener Phasen werden wieder zusammengelegt")


def test_die_alten_kennungen_bleiben_auffindbar():
    """⚠ DAS IST DER TEIL, DER SCHLIMMER WAERE ALS DIE DUBLETTE. Wer eine Nummer aus einer
    alten Mail sucht und nichts findet, haelt das fuer Datenverlust. Die abgeloesten
    Kennungen wandern deshalb an den ueberlebenden Lead und in `kennungIndex()`.
    """
    assert '"ersetzt": ERSETZT.get(' in EXPORT.read_text(encoding="utf-8"), (
        "die abgeloesten Kennungen wandern nicht mit")
    kern = _ohne_kommentar(CORE.read_text(encoding="utf-8"))
    i = kern.index("function kennungIndex")
    block = kern[i:kern.index("\n}", i)]
    assert "l.ersetzt" in block, (
        "der Kennungsindex kennt die abgeloesten Nummern nicht — aus einer doppelten "
        "Zeile wird dann eine verschwundene")
    assert "replace('_', '-')" in block, (
        "die Bindestrich-Schreibweise der abgeloesten Nummern fehlt")


def test_die_verfahrenskennung_kommt_aus_dem_erzeuger():
    """⚠ Die Zuordnung geht SEPARAT heraus, nicht als Nebenprodukt der Ereignisse: zwei
    Bekanntmachungen desselben Verfahrens sind auch dann Geschwister, wenn keine von beiden
    eine Berichtigung traegt."""
    code = ERZEUGER.read_text(encoding="utf-8")
    assert "notice_procedures.parquet" in code, "die Verfahrenszuordnung wird nicht geschrieben"
    assert "if len(zeilen) > 1" in code, (
        "auch Verfahren mit nur EINER Bekanntmachung landen in der Tabelle — das blaeht "
        "sie ohne Nutzen auf")


def test_die_verfahrenskennung_allein_genuegt_nicht():
    """⛔ DER GEFAEHRLICHSTE BEFUND DIESER ARBEIT, und gefunden hat ihn kein Test, sondern
    das Lesen der Titel am konkreten Beispiel.

    30 von 1.847 Verfahrenskennungen sind SAMMELBECKEN: eine Vergabestelle vergibt
    dieselbe Kennung an alles, was sie ausschreibt. Unter einer davon standen „Metallbau
    Aussen/Kunststofffenster", „Lieferung eines Mobilbaggers", „Firmenfitness" und
    „Gebaeude- und Inhaltsversicherungen" — 18 Meldungen, 18 Titel, EIN Kaeufer.

    Ohne zweiten Beleg haette der Filter 87 voellig verschiedene Ausschreibungen zu einer
    zusammengeworfen und den Rest aus der Liste genommen. Das waere kein aufgeraeumter
    Bestand gewesen, sondern Datenverlust, der aussieht wie Ordnung — und niemand haette
    es gemerkt, weil eine kuerzere Liste nach Erfolg aussieht.

    ⚠ Genau diese Vorsicht hatte `govisor/dedupe.py` immer schon (Sperre gegen das
    Zusammenlegen innerhalb einer Quelle). Sie war richtig, nur zu grob.
    """
    code = EXPORT.read_text(encoding="utf-8")
    i = code.index("def _verfahrens_dubletten")
    sql = " ".join(code[i:code.index("\nGLIEDERUNG", i)].split())
    assert "g.titel = m.titel" in sql, (
        "der Titel muss mitstimmen — sonst legt eine Sammel-Verfahrenskennung voellig "
        "verschiedene Ausschreibungen zusammen")
    assert "g.kaeufer IS NOT DISTINCT FROM m.kaeufer" in sql, (
        "der Kaeufer muss mitstimmen. `IS NOT DISTINCT FROM` und nicht `=`, weil ein "
        "fehlender Kaeufer sonst jeden Vergleich unwahr macht und der Filter still "
        "aufhoert zu wirken.")
