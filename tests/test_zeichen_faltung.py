"""Kennen die Wortfaltungen die Buchstaben der Laender, fuer die sie laufen?

⚠ ES SIND ZWEI FALTUNGEN, UND SIE SIND NICHT DIESELBE. Bis zum 2026-09-18 stand in
`docs/laender/14-zeichen-und-schrift.md`, der Dublettenwall trage dieselbe Faltung wie die
Regionsableitung. Nachgemessen:

    Ort        dedupe.worte()        region_ableiten._worte()
    Łódź       []                    ['d']
    Kraków     ['kraków']            ['krak', 'w']
    Zürich     ['zürich']            ['zuerich']

Die letzte Zeile ist die wichtigste: die beiden weichen schon IN DACH voneinander ab. Wer
eine repariert, hat die andere nicht mit repariert.

⚠ WARUM DAS EIN BLINDGAENGER IST UND KEIN BRAND. `dedupe._wiederholung()` verlangt
IDENTISCHE Wortmengen. Ein Ort, der bei der Faltung spurlos verschwindet, traegt zur
Unterscheidung nichts bei:

    Przebudowa drogi gminnej w miejscowości Łódź   → ['drogi','gminnej','miejscowo','przebudowa']
    Przebudowa drogi gminnej w miejscowości Łomża  → dieselbe Menge
    _wiederholung() → True

Zwei VERSCHIEDENE Strassenbauvergaben derselben Gemeinde. Eine davon fiele in `gold.py`
aus der ausgelieferten Liste. Solange nur DACH laeuft, passiert nichts; der Tag, an dem es
etwas tut, ist der Tag, an dem jemand ein Land dazunimmt — und dann faellt es niemandem
auf, weil ein fehlender Lead wie ein nicht vorhandener aussieht.

⚠ `MIN_WORTE = 3` ist KEIN Schutz dagegen. Es verwirft Titel mit weniger als drei Woertern;
im Beispiel bleiben vier uebrig. Es faengt den offensichtlichen Fall und gerade nicht den
gefaehrlichen.

Dieser Test ist deshalb an `laender.AKTIV` gebunden: er schweigt, solange nur DACH laeuft,
und wird rot, sobald ein Land dazukommt, dessen Buchstaben keine der beiden Faltungen kennt.
"""
import importlib
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
dedupe = importlib.import_module("govisor.dedupe")
laender = importlib.import_module("govisor.laender")

# Buchstaben, die NFKD nicht zerlegt, je Sprachraum. Die Tabelle stammt aus Kapitel 14.
EIGENE_BUCHSTABEN = {
    "PL": "łŁżŻźŹńŃśŚćĆęĘąĄ",
    "CZ": "ěĚřŘžŽčČšŠůŮťŤďĎňŇ",
    "SK": "ľĽĺĹťŤžŽčČšŠňŇôÔ",
    "HR": "đĐžŽčČćĆšŠ",
    "DK": "øØæÆåÅ",
    "NO": "øØæÆåÅ",
    "SE": "åÅäÄöÖ",
    "IS": "þÞðÐæÆöÖ",
    "TR": "ıİğĞşŞçÇöÖüÜ",
    "HU": "őŐűŰáÁéÉíÍóÓöÖúÚüÜ",
    "RO": "ăĂâÂîÎșȘțȚ",
}
DACH = {"DE", "AT", "CH", "LU"}


def _ueberlebt(zeichen: str) -> bool:
    """Bleibt ein Wort mit diesem Buchstaben als EIN Wort erhalten?

    Gepruefte Form ist ein Kunstwort aus lauter unverfaenglichen Buchstaben plus dem
    fraglichen Zeichen. Zerfaellt es oder verschwindet es, ist der Buchstabe ein Trenner.
    """
    probe = f"mate{zeichen}rial"
    w = dedupe.worte(probe)
    return len(w) == 1 and next(iter(w), "") not in ("mate", "rial")


def test_die_faltung_kennt_die_buchstaben_der_aktiven_laender():
    """⚠ Bindet an `laender.AKTIV`, nicht an eine eigene Liste — sonst altert der Test
    getrennt von dem, was die Pipeline tatsaechlich baut (Kapitel 15)."""
    offen = []
    for land in laender.AKTIV:
        if land in DACH:
            continue
        for z in EIGENE_BUCHSTABEN.get(land, ""):
            if not _ueberlebt(z):
                offen.append(f"{land}: {z!r} zerlegt das Wort in `dedupe.worte()`")
    assert not offen, (
        f"{len(offen)} Buchstaben aktiver Laender wirken in der Wortfaltung als Trenner. "
        f"Damit verschwinden Ortsnamen spurlos aus den Wortmengen, und "
        f"`_wiederholung()` haelt zwei verschiedene Vergaben fuer eine "
        f"(docs/laender/14-zeichen-und-schrift.md).\n  " + "\n  ".join(offen[:10]))


def test_der_befund_von_2026_09_18_ist_reproduzierbar():
    """Der Beleg selbst. Faellt dieser Test, ist die Faltung repariert worden — dann
    gehoert Kapitel 14 nachgezogen, statt den Test zu loeschen."""
    a = dedupe.worte("Przebudowa drogi gminnej w miejscowości Łódź")
    b = dedupe.worte("Przebudowa drogi gminnej w miejscowości Łomża")
    if a != b:
        return                                  # repariert — Kapitel 14 nachziehen
    gruppe = {(a, "gmina x", "eforms"): 2}
    s = dict(id="1", gen="eforms", w=a, buyer="gmina x", cpv="45233000", frist="2026-10-01")
    t = dict(id="2", gen="eforms", w=b, buyer="gmina x", cpv="45233000", frist="2026-10-15")
    assert dedupe._wiederholung(s, t, gruppe), (
        "Zwei verschiedene polnische Vergaben werden nicht mehr als Wiederholung gewertet "
        "— gut, aber dann stimmt die Messung in Kapitel 14 nicht mehr")


def test_das_kapitel_nennt_beide_faltungen():
    """⚠ Hier stand einmal „dieselbe Faltung". Ein Satz, der zwei verschiedene Dinge
    zusammenzieht, ist schlimmer als gar keiner: er beendet die Suche."""
    text = (WURZEL / "docs" / "laender" / "14-zeichen-und-schrift.md").read_text(encoding="utf-8")
    assert "dedupe.worte()" in text and "region_ableiten" in text, (
        "Kapitel 14 nennt nicht mehr beide Faltungen namentlich")
    assert "Dieselbe Faltung trägt auch" not in text, (
        "die widerlegte Behauptung steht wieder da")
