"""Findet die Firewall Dubletten INNERHALB einer Quelle?

⚠ WARUM DIESE DATEI EXISTIERT. `_paare_finden` uebersprang Paare gleicher Quelle mit der
Begruendung „dieselbe Quelle dedupliziert sich selbst schon". Gemessen am 2026-09-17 ueber
die DE-Ausschreibungen ab 2025 stimmt das nicht:

    identischer Titel + Kaeufer + Stufe, <= 90 Tage   77.341 Paare gleicher Quelle
    davon stehen BEIDE in der ausgelieferten Liste     8.797  ← doppelt sichtbar

eForms und TED veroeffentlichen Korrekturen als eigene Bekanntmachung. Gemeldet als „nun
sehe ich direkt auf der startseite 4mal den gleichen lead".

⚠ DIE SCHWIERIGKEIT IST DIE SERIE. Derselbe Titel beim selben Kaeufer heisst nicht immer
dieselbe Vergabe: „Abschluss nicht-exklusiver Rabattvereinbarungen nach §130a" steht
219-mal bei einer Krankenkasse (Open House je Praeparat), „Erweiterung und Sanierung
Klinikum Altmuehlfranken" 53-mal (je Gewerk). Die zusammenzufassen hiesse, echte Vergaben
zu loeschen.
"""
import importlib
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
dedupe = importlib.import_module("govisor.dedupe")


def _satz(**kw):
    basis = dict(id="x", gen="eforms", titel="t", w=frozenset({"neubau", "rathaus", "elektro"}),
                 z=frozenset(), art="cn", d=None, buyer="stadt musterhausen", bid="",
                 cpv="45310000", wert=None, frist="2026-09-24", nuts=None, beschr=None)
    basis.update(kw)
    return basis


def test_die_vier_belege_muessen_alle_zutreffen():
    """Jede einzelne Bedingung ist notwendig — fehlt eine, ist es keine Wiederholung.

    ⚠ Die Wortmenge muss IDENTISCH sein, Enthaltung genuegt nicht: „… Los VM 004 -
    Abbrucharbeiten" gegen „Erweiterung Stadtbad Plauen" ist ein Los, keine Kopie.
    """
    a = _satz(id="1")
    gruppe = {(a["w"], a["buyer"], a["gen"]): 2}
    assert dedupe._wiederholung(a, _satz(id="2"), gruppe), "der Normalfall wird nicht erkannt"

    faelle = {
        "andere Wortmenge (Enthaltung)": _satz(id="2", w=a["w"] | {"los"}),
        "anderer Kaeufer": _satz(id="2", buyer="stadt woanders"),
        "andere Frist": _satz(id="2", frist="2026-10-01"),
        "andere CPV": _satz(id="2", cpv="45320000"),
        "Frist fehlt": _satz(id="2", frist=None),
        "CPV fehlt": _satz(id="2", cpv=None),
    }
    for name, b in faelle.items():
        g = {(a["w"], a["buyer"], a["gen"]): 2, (b["w"], b["buyer"], b["gen"]): 2}
        assert not dedupe._wiederholung(a, b, g), (
            f"{name!r} wird faelschlich als Wiederholung gewertet")


def test_serien_werden_nicht_zusammengefasst():
    """Der Gruppendeckel ist das, was Wiederholung von Serie trennt.

    Gemessen ueber dieselbe Menge:

        ohne Deckel   20.271 Paare, davon 6.630 aus der 219er-Rabatt-Serie
        Deckel 3       7.679 Paare, davon     3

    ⚠ Ohne ihn wuerde die Regel 219 eigenstaendige Open-House-Vergaben zu einer machen.
    """
    a, b = _satz(id="1"), _satz(id="2")
    schl = (a["w"], a["buyer"], a["gen"])
    assert dedupe._wiederholung(a, b, {schl: dedupe.SERIEN_DECKEL}), "Deckel zu eng"
    assert not dedupe._wiederholung(a, b, {schl: dedupe.SERIEN_DECKEL + 1}), (
        "eine Serie wird als Wiederholung gewertet — der Deckel greift nicht")
    # ⚠ FEHLT DIE GRUPPE GANZ, liefert `get` 0 und die Regel laeuft durch — der Fall
    # sieht aus wie „kleine Gruppe". Das ist hier ungefaehrlich, weil `_paare_finden` die
    # Zaehlung ueber DIESELBE Satzmenge baut, aus der auch die Paare kommen: jeder Satz mit
    # Kaeufer ist darin. Wer die Zaehlung spaeter woanders herholt, muss diesen Satz neu
    # pruefen — sonst waere der Deckel lautlos wirkungslos.
    assert dedupe._wiederholung(a, b, {}), (
        "ohne Gruppenzaehlung faellt die Regel durch — dann ist der Deckel wirkungslos, "
        "und zwar ohne dass irgendetwas bricht")


def test_die_master_wahl_ist_deterministisch():
    """Bei gleicher Quelle sind die Quellen-Raenge gleich — dann entscheidet das Datum.

    ⚠ Vorher nahm der Code einfach `s`, und welcher Satz das ist, haengt an der
    Reihenfolge der Kandidatenmenge. Solange nur Paare VERSCHIEDENER Quellen entstanden,
    fiel das kaum auf; mit Wiederholungen derselben Quelle ist Gleichstand der Normalfall.
    Ein Abgleich, dessen Ergebnis zwischen zwei Laeufen schwankt, laesst sich weder
    pruefen noch reproduzieren — denselben Satz traegt die Seed-Sortierung im selben Modul.
    """
    quelle = (WURZEL / "govisor" / "dedupe.py").read_text(encoding="utf-8")
    i = quelle.index("def _rang(x):")
    zeile = quelle[i:quelle.index("\n", quelle.index("return", i))]
    assert 'x["d"]' in zeile and 'x["id"]' in zeile, (
        "die Master-Wahl faellt wieder auf die Iterationsreihenfolge zurueck")


def test_die_neue_stufe_heisst_eigen():
    """Eigene Belegstufe, damit die Wirkung sichtbar und umkehrbar bleibt.

    `gold.py` nennt die ausschliessenden Stufen einzeln; eine neue Stufe wirkt also erst,
    wenn sie dort ausdruecklich aufgenommen wird.
    """
    quelle = (WURZEL / "govisor" / "dedupe.py").read_text(encoding="utf-8")
    assert '"gleiche_quelle_wiederholt" if gleiche_quelle' in quelle, (
        "Wiederholungen derselben Quelle tragen keine eigene Stufe mehr — ihre Wirkung "
        "waere dann nicht mehr von den quellenuebergreifenden Dubletten zu trennen")
