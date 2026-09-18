"""Wie viele Rahmen stecken im Ueberblick ineinander?

⚠ GEMELDET AM 2026-09-18. Sven vor dem Bildschirm: „balken mit balken mit balken". Das war
buchstaeblich gemeint und nachgezaehlt richtig:

    Tabelle darueber        Zeilen mit Rand
    └ lb-drei               vier Spalten
      └ je Spalte           Ueberschrift + grosse Zahl + bis zu 5 lb-row
        └ lb-row            1 px Rand, Radius 8, eigener Hintergrund
      └ Was euch bremst     zusaetzlich 3 lb-kachel
        └ lb-kachel         1 px Rand, Radius 7, eigener Hintergrund

Bis zu 20 gerahmte Kaestchen plus 3 gerahmte Kacheln, unter einer Tabelle aus gerahmten
Zeilen. Dreimal dieselbe Behandlung ineinander, und der Rand trug nichts bei.

Entschieden: der Rahmen bleibt dort, wo er etwas BEDEUTET — an den drei Kacheln, die
Handlungsaufforderungen sind. Die zwanzig Zeilen sind eine Aufzaehlung und kommen ohne aus.

⚠ DER TEIL, DER LEICHT VERLORENGEHT. Der Rand war das EINZIGE Signal, dass die Zeilen
anklickbar sind (sie oeffnen den Lead). Ihn ersatzlos zu streichen tauscht Unruhe gegen
eine unsichtbare Funktion. Deshalb pruefen zwei der drei Tests hier nicht das Weglassen,
sondern den Ersatz.
"""
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
CSS = WURZEL / "web" / "app" / "explorer.css"


def _regel(name: str) -> str:
    """Der Rumpf einer CSS-Regel, Kommentare vorher raus (F13: der Kommentar darueber
    nennt genau die Worte, auf die die Pruefung anspringt)."""
    roh = CSS.read_text(encoding="utf-8")
    ohne = re.sub(r"/\*[\s\S]*?\*/", "", roh)
    m = re.search(rf"^{re.escape(name)}\s*\{{([^}}]*)\}}", ohne, re.M)
    assert m, f"CSS-Regel {name} gibt es nicht mehr"
    return m.group(1)


def test_die_zeilen_tragen_keinen_rahmen_mehr():
    rumpf = _regel(".lb-row")
    assert re.search(r"\bborder\s*:\s*0", rumpf), (
        "lb-row hat wieder einen Rahmen. Damit stehen bis zu 20 gerahmte Kaestchen in "
        "vier Spalten unter einer Tabelle aus gerahmten Zeilen.")
    assert "background:none" in rumpf.replace(" ", ""), (
        "lb-row hat wieder einen eigenen Hintergrund und setzt sich damit erneut als "
        "Kasten vom Panel ab.")


def test_die_kacheln_behalten_ihren():
    """Sie sind Handlungsaufforderungen, keine Aufzaehlung. Ohne Rahmen waeren sie von den
    Zeilen darueber nicht mehr zu unterscheiden, und dann war das Aufraeumen umsonst."""
    rumpf = _regel(".lb-kachel")
    assert re.search(r"border\s*:\s*1px solid", rumpf), (
        "auch die Kacheln haben ihren Rahmen verloren. Dann sieht der ganze Ueberblick "
        "gleich aus und die drei Handlungsaufforderungen gehen unter.")


def test_die_zeilen_bleiben_erkennbar_anklickbar():
    """⚠ Der eigentliche Test. Der Rand war das einzige Signal; fehlt der Ersatz, ist die
    Funktion unsichtbar und der Umbau hat mehr gekostet als gebracht."""
    roh = re.sub(r"/\*[\s\S]*?\*/", "", CSS.read_text(encoding="utf-8"))
    assert re.search(r"\.lb-row:hover\s*\{[^}]*background", roh), (
        "beim Ueberfahren passiert nichts mehr")
    assert re.search(r"\.lb-row:hover\s+\.lb-row-t\s*\{[^}]*color", roh), (
        "der Titel wechselt beim Ueberfahren nicht mehr die Farbe. Ohne Rand und ohne "
        "Farbwechsel sieht die Zeile aus wie Text, nicht wie ein Knopf.")
    assert re.search(r"\.lb-row:focus-visible\s*\{[^}]*outline", roh), (
        "ohne Rand ist der Tastatur-Fokus voellig unsichtbar geworden")
