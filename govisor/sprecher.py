"""Wer spricht: die Vergabestelle oder ein Bieter?

In einem Fragenkatalog stehen zwei Stimmen nebeneinander. Nur eine davon ist verbindlich.
Der Satz „Wir gehen davon aus, dass die Gebuehren uebernommen werden" ist die ANNAHME
EINES BIETERS — als Anforderung der Vergabestelle gebucht ist er schlicht falsch.

Gemessen am 2026-09-01: 4.349 der 396.284 Anforderungen stammen aus Fragenkatalogen
(`analyze_docs.AUSWERTUNG` nimmt sie absichtlich mit auf), 84 davon sind erkennbar
fragehaft formuliert. Heute ist das wenig. Der Anteil waechst aber genau in dem Mass, in
dem wir mehr Fragenkataloge hereinholen — und das ist der Plan.

⚠ **DIESES MODUL LOEST DAS PROBLEM NICHT GANZ, UND DAS IST KEINE NACHLAESSIGKEIT.**
1.574 der 2.065 Fragenkataloge sind TABELLEN: die Kopfzeile lautet
„Nr | Bieterfrage | Antwort | Eingangsdatum", Frage und Antwort stehen in SPALTEN. Die
Textextraktion plaettet die Tabelle zu einer Zeichenkette, und damit verschwindet die
Reihenfolge, aus der sich der Sprecher ableiten liesse. Fuer drei Viertel des Materials
ist eine folgerichtige Zuordnung strukturell unmoeglich — nicht schwierig, unmoeglich.

Deshalb kennt dieses Modul drei Antworten, nicht zwei. `unklar` ist ein ERGEBNIS, keine
Luecke: es sagt „diese Anforderung stammt aus einem Fragenkatalog und wir wissen nicht,
wer sie gesagt hat". Wer sie ohne diesen Vorbehalt anzeigt, verkauft die Vermutung eines
Bieters als Vorgabe der Vergabestelle.

Die vollstaendige Loesung gehoert an die Extraktion: das Modell SIEHT die Tabelle und
kann je Fundstelle sagen, aus welcher Spalte der Satz stammt. Ein zusaetzliches Feld im
Schema, derselbe Aufruf, keine zusaetzlichen Kosten. Das gehoert zu `doc_qa` (Schritt 2,
s. `docs/bieterfragen-datenmodell.md`) — nicht hierher.
"""
import re

# Der Doppelpunkt ist die Marke, nicht das Wort. „Nachfrage bzgl.", „Zukunftfragenstudie"
# und „Bieterfragen Vergabenummer" enthalten alle `frage`, aber keine Frage. Eine erste
# Fassung ohne diese Bedingung ordnete 982 Anforderungen einem Bieter zu, darunter
# Treffer mitten in „ZukunftJugendFRAGENstudie" — dieselbe Teilwort-Falle, die den
# Bibel-Pruefer und die Buergschafts-Messung schon erwischt hat.
FRAGE = re.compile(r'(?:^|[\s„»\-])(?:bieter|nach|rück|rueck)?frage\s*(?:nr\.?\s*)?\d{0,3}\s*[:.]',
                   re.I | re.M)
ANTWORT = re.compile(r'antwort(?:\s*(?:zu|auf)\s*(?:die\s*)?frage\s*\d{0,3})?\s*[:.]', re.I)

# Tabellenkopf: Frage UND Antwort dicht beieinander in EINER Zeile. Dann sind es Spalten,
# und die Reihenfolge im geplaetteten Text bedeutet nichts.
TABELLENKOPF = re.compile(r'^[^\n]{0,80}\bfrage\b[^\n]{0,40}\bantwort\b[^\n]{0,80}$', re.I | re.M)

# ⚠ **DIE ZWEI RICHTUNGEN SIND NICHT GLEICH VERLAESSLICH.** Steht ein `Antwort:` vor dem
# Zitat, spricht die Vergabestelle — das haelt der Stichprobe stand. Der Umkehrschluss
# haelt NICHT: in vielen Katalogen folgt die Antwort direkt auf die Frage, ohne eigene
# Marke:
#     Frage 3: Koennen wir X anbieten?
#     Mehrleistung kann angeboten werden, fuehrt aber nicht zu hoeheren Punkten.
# Eine erste Fassung ordnete solche Saetze dem Bieter zu, weil die letzte Marke davor eine
# Frage war. Nachgesehen: „Beide Positionen sind mit der neuen Version (3) aus dem LV
# gestrichen" — unverkennbar die Vergabestelle, als Bieter gebucht.
#
# Deshalb verlangt `BIETER` ZWEIERLEI: eine Fragemarke davor UND ein Zitat, das selbst wie
# eine Frage oder eine Bieterannahme klingt. Alles andere ist `UNKLAR`. Lieber weniger
# zuordnen als falsch zuordnen — eine falsche Zuschreibung ist genau der Fehler, den
# dieses Modul verhindern soll.
FRAGEHAFT = re.compile(
    r'\?|^\s*(?:ist|sind|kann|k[oö]nnen|wird|werden|wie|was|wo|wann|warum|welche|'
    r'gibt\s+es|d[uü]rfen|muss|m[uü]ssen|besteht|w[aä]re|wir\s+gehen\s+davon\s+aus|'
    r'wir\s+bitten|wir\s+nehmen\s+an|gehen\s+wir|d[uü]rfen\s+wir|k[oö]nnen\s+wir)\b', re.I)

BIETER, VERGABESTELLE, UNKLAR = "bieter", "vergabestelle", "unklar"


def ist_tabelle(roh: str) -> bool:
    """Steht Frage neben Antwort statt darunter? Dann traegt die Reihenfolge nichts."""
    return bool(TABELLENKOPF.search(roh or ""))


def indexkarte(roh: str) -> tuple[str, list[int]]:
    """Normalisierter Text plus Ruecklaufkarte auf die Rohpositionen.

    ⚠ Warum nicht einfach `docextract._normalize`: die Marken muessen im ROHTEXT gesucht
    werden, weil dort noch Wortgrenzen und Doppelpunkte stehen. Das Zitat dagegen muss
    normalisiert gesucht werden, weil PDFs Woerter mit Trennstrichen zerhacken. Beides
    zugleich geht nur mit einer Karte von der einen in die andere Welt.

    ⚠ `len(cf) == 1` filtert Zeichen, die beim Kleinschreiben LAENGER werden (»ß« wird zu
    »ss«). Ohne diese Bedingung verschieben sich alle folgenden Positionen um eins und die
    Karte zeigt auf die falsche Stelle.
    """
    norm: list[str] = []
    idx: list[int] = []
    for k, c in enumerate(roh or ""):
        cf = c.casefold()
        if len(cf) == 1 and (cf.isalnum() or cf in "äöüß"):
            norm.append(cf)
            idx.append(k)
    return "".join(norm), idx


def zuordnen(roh: str, quelle_norm: str, karte: list[int], zitat_norm: str,
             zitat_roh: str = "") -> str:
    """Sprecher des Zitats. `UNKLAR`, wenn die Reihenfolge nichts hergibt."""
    # ⚠ Mindestlaenge wie bei der Zitatpruefung. Ein kurzes Zitat findet sich zufaellig
    # irgendwo, und dann entscheidet die Marke davor ueber eine Zuschreibung, die auf
    # einem Zufallstreffer steht.
    if len(zitat_norm) < 12 or not quelle_norm:
        return UNKLAR
    if ist_tabelle(roh):
        return UNKLAR
    p = quelle_norm.find(zitat_norm)
    if p < 0 or p >= len(karte):
        return UNKLAR
    pos = karte[p]
    letzte_frage = None
    for m in FRAGE.finditer(roh, 0, pos):
        letzte_frage = m
    letzte_antwort = None
    for m in ANTWORT.finditer(roh, 0, pos):
        letzte_antwort = m
    if letzte_frage is None and letzte_antwort is None:
        return UNKLAR
    frage_zuletzt = (letzte_antwort is None
                     or (letzte_frage is not None
                         and letzte_frage.start() > letzte_antwort.start()))
    if not frage_zuletzt:
        return VERGABESTELLE
    # Fragemarke davor — das allein genuegt nicht (s. Kopf). Das Zitat muss selbst
    # fragehaft klingen, sonst ist es vermutlich die unmarkierte Antwort darunter.
    return BIETER if FRAGEHAFT.search(" ".join(str(zitat_roh or "").split())) else UNKLAR
