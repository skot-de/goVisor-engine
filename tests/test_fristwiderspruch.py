"""Widerspruch bei der Angebotsfrist (Kennzahl 9).

Die einzige Kennzahl dieser Reihe, bei der ein Fehlalarm eine Angebotsabgabe kosten kann. Diese
Datei hält deshalb vor allem fest, was NICHT gemeldet wird — und warum jeder dieser Filter aus
einem Beleg stammt und nicht aus einer Schätzung.
"""
from __future__ import annotations

import ast
import datetime as dt
import json
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SKRIPT = WURZEL / "scripts" / "export_fristwiderspruch.py"
QUELLE = SKRIPT.read_text(encoding="utf-8")
CORE = (WURZEL / "web" / "lib" / "explorerCore.js").read_text(encoding="utf-8")
DATEI = WURZEL / "web" / "data" / "fristwiderspruch.json"


def _modul():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_fw", SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _block(name: str) -> str:
    rest = CORE[CORE.index(f"function {name}("):]
    return rest[:rest.index("\n}")]


# ── Filter 1: nur die Angebotsfrist ─────────────────────────────────────────────────────

def test_andere_fristen_fallen_raus():
    """⚠ `req_type='frist'` mischt alles. Von 33.399 Fristzeilen benennen nur 4.586 eindeutig
    die Angebotsfrist; 6.247 sind Binde-, Zuschlags-, Ausführungs- oder Rückfragefristen."""
    m = _modul()
    assert m._ist_angebotsfrist("Ablauf der Angebotsfrist: Datum: 01.09.2026 Uhrzeit: 18:00")
    for raus in ("Bindefrist endet am: 29.10.2026",
                 "Die Ausführungsfrist beginnt am 01.10.2026",
                 "Frist für Rückfragen bis 20.08.2026",
                 "Zuschlagsfrist bis 30.11.2026"):
        assert not m._ist_angebotsfrist(raus), raus
    # ⚠ DIE VIER OBEN PRUEFEN DIE SPERRE GAR NICHT: sie scheitern schon am Angebotsmuster. Die
    # Sperre greift erst, wo BEIDES im Satz steht — und genau das ist der gefaehrliche Fall,
    # weil dort ein Datum steht, das wie eine Angebotsfrist aussieht.
    for beides in ("Ablauf der Angebotsfrist ist die Bindefrist von 30 Tagen zu beachten",
                   "Abgabefrist der Unterlagen richtet sich nach der Ausführungsfrist",
                   "Angebotsabgabe und Zuschlagsfrist: siehe Anlage"):
        assert not m._ist_angebotsfrist(beides), beides


def test_lieferfristen_der_vertragsphase_fallen_raus():
    """„Abgabefrist für sämtliche geforderten Daten und Unterlagen" trifft das Angebotsmuster
    und meint doch eine Lieferung nach Zuschlag."""
    m = _modul()
    assert not m._ist_angebotsfrist(
        "Die Abgabefrist für sämtliche geforderten Daten richtet sich nach der Leistungszeit")


def test_seitenkoepfe_fallen_raus():
    """⚠ „11.07.2026 VERGABEUNTERLAGE · ZUR ANGEBOTSABGABE Seite 26 von 653" nennt das
    Druckdatum. Ohne diesen Filter erschiene es als Frist, 66 Tage daneben."""
    m = _modul()
    assert not m._ist_angebotsfrist(
        "11.07.2026 VERGABEUNTERLAGE · ZUR ANGEBOTSABGABE Seite 26 von 653")


# ── Filter 2: die Bandbreite ────────────────────────────────────────────────────────────

def test_grosse_abweichungen_bleiben_stumm():
    """⚠ DIE WICHTIGSTE GRENZE, und sie stammt aus den Belegen: innerhalb von 30 Tagen lauten
    die Zitate durchweg „Ablauf der Angebotsfrist Datum … Uhrzeit …", darüber stehen
    Lieferfristen, Seitenköpfe und Jahresdreher.

    ⚠ Die ±365-Tage-Fälle sind der Grund, dass die Grenze existiert und nicht grosszügiger ist:
    „Die Angebotsfrist endet am 10.09.2027" KANN ein echter Jahresdreher des Auftraggebers sein.
    Ohne das Dokument zu öffnen lässt sich sein Tippfehler nicht von unserem Lesefehler
    unterscheiden — bei einer Frist ist Schweigen billiger als Raten."""
    m = _modul()
    assert m.MAX_TAGE == 30
    if DATEI.exists():
        d = json.loads(DATEI.read_text(encoding="utf-8"))
        assert all(0 < abs(v["tage"]) <= 30 for v in d.values())


def test_beide_datumsschreibweisen():
    """⚠ `value` kommt als `2026-09-29 11:00` UND als `31.03.2027`."""
    m = _modul()
    assert m._datum("2026-09-29 11:00") == dt.date(2026, 9, 29)
    assert m._datum("31.03.2027") == dt.date(2027, 3, 31)
    assert m._datum(dt.date(2026, 1, 2)) == dt.date(2026, 1, 2)
    assert m._datum("30 Tage") is None and m._datum(None) is None
    assert m._datum("2026-02-30") is None, "ein unmögliches Datum darf keine Frist werden"


def test_der_beleg_muss_das_datum_tragen():
    """⚠ FILTER 4, gefunden beim Blick in die laufende App. Der Kasten zeigte „Ablauf der
    Angebotsfrist Datum Uhrzeit" als Beleg für einen 28-Tage-Widerspruch — ein Formularetikett
    ohne jedes Datum. 93 % der Zitate tragen das Datum ohnehin, 0 % ein ANDERES (das wäre das
    Alarmzeichen), 7 % gar keines. Bei einer Frist soll der Nutzer selbst nachschlagen können."""
    m = _modul()
    tag = dt.date(2026, 9, 1)
    assert m._beleg_traegt("Ablauf der Angebotsfrist: Datum: 01.09.2026 Uhrzeit: 18:00", tag)
    assert m._beleg_traegt("Angebotsfrist 2026-09-01", tag)
    assert not m._beleg_traegt("Ablauf der Angebotsfrist Datum Uhrzeit", tag)
    assert not m._beleg_traegt("Ablauf der Angebotsfrist: 08.09.2026", tag), \
        "ein Zitat mit ANDEREM Datum darf erst recht nicht durchgehen"
    if DATEI.exists():
        d = json.loads(DATEI.read_text(encoding="utf-8"))
        for v in d.values():
            assert m._beleg_traegt(v["beleg"], dt.date.fromisoformat(v["dok"])), v["beleg"]


# ── die Aussage ─────────────────────────────────────────────────────────────────────────

def test_der_ausschnitt_liegt_um_das_datum():
    """⚠ DIE FALLE, die dieses Projekt schon einmal getroffen hat. Der Beleg wird gekürzt, und
    eine Kürzung ab Satzanfang schneidet genau das weg, was den Widerspruch belegt: das Datum
    steht oft erst nach 150 Zeichen. Damals wurde aus „Bindefrist: 30.10.2026" ein
    „Bindefrist: …" — ausgerechnet die Zahl, wegen der man hinschaut."""
    m = _modul()
    tag = dt.date(2026, 10, 14)
    lang = ("Angebote, die nicht fristgerecht eingegangen sind, werden vom Vergabeverfahren "
            "ausgeschlossen, es sei denn, der Bieter hat die Verspätung nicht zu vertreten. "
            "Ablauf der Angebotsfrist: 14.10.2026 08:00 Uhr")
    a = m._ausschnitt(lang, tag)
    assert "14.10.2026" in a, a
    assert len(a) <= m.BELEG_MAX + 8
    assert not a.startswith("… eschlossen"), "der Ausschnitt beginnt mitten im Wort"
    # Kurze Zitate bleiben unangetastet.
    assert m._ausschnitt("Angebotsfrist: 14.10.2026", tag) == "Angebotsfrist: 14.10.2026"


def test_behauptet_nicht_welche_seite_recht_hat():
    """⚠ Die Abweichungen spitzen auf Vielfachen von sieben — die Signatur verlängerter
    Fristen. Mal bleibt das alte Dokument liegen, mal trägt das Dokument die Verlängerung und
    die Bekanntmachung nicht. Der einzige Satz, der immer stimmt, ist der über die frühere
    Angabe."""
    b = _block("fristWiderspruch")
    sätze = re.findall(r'tk\("([^"]+)"', b)
    assert any("frühere Angabe ist die sichere" in s for s in sätze)
    for s in sätze:
        assert not re.search(r"\bfalsch\b|\bfehlerhaft\b|\bstimmt nicht\b", s), f"urteilt: {s!r}"


def test_beide_daten_stehen_da():
    """Ein Widerspruch ohne beide Zahlen ist eine Beunruhigung ohne Handlungsmöglichkeit."""
    b = _block("fristWiderspruch")
    assert "w.dok" in b and "w.bek" in b and "w.tage" in b


def test_der_beleg_steht_dabei():
    """Bei einer Frist muss der Nutzer nachschlagen können, welches Dokument das sagt."""
    b = _block("fristWiderspruch")
    assert "esc(w.beleg)" in b and "esc(w.datei)" in b


def test_traegt_die_warnfarbe_nicht_die_hinweisfarbe():
    """⚠ Die einzige Zeile dieser Reihe in Warnrot. Ein übersehener Fristwiderspruch kostet die
    Abgabe — eine andere Klasse als „Vertragsstrafe höher als üblich"."""
    css = (WURZEL / "web" / "app" / "explorer.css").read_text(encoding="utf-8")
    block = css[css.index(".frist-konflikt {"):css.index(".fk-satz")]
    assert "--risk" in block and "--flag" not in block


def test_steht_bei_der_frist():
    """Im Fristen-Block, nicht in einer eigenen Kachel: dort liest jemand den Termin."""
    stelle = CORE[CORE.index('${tk("Angebotsfrist")}'):]
    stelle = stelle[:stelle.index('${tk("Bindefrist")}')]
    assert "fristWiderspruch(l)" in stelle


# ── Ausliefergut ────────────────────────────────────────────────────────────────────────

def test_ausgabe_haelt_die_form():
    if not DATEI.exists():
        return
    d = json.loads(DATEI.read_text(encoding="utf-8"))
    assert d
    for v in d.values():
        assert set(v) == {"dok", "bek", "tage", "beleg", "datei"}
        dok, bek = dt.date.fromisoformat(v["dok"]), dt.date.fromisoformat(v["bek"])
        assert (dok - bek).days == v["tage"], "die Differenz passt nicht zu den Daten"
        assert v["beleg"], "ein Fristwiderspruch ohne Beleg wäre eine blosse Behauptung"


def test_die_wochenverteilung_haelt():
    """⚠ DER BEFUND, der die Kennzahl entlastet hat. Fünf -1-Tage-Fälle hintereinander sahen
    zuerst nach einem Datumsfehler von uns aus. Die Verteilung spitzt aber auf Vielfachen von
    sieben (verlängerte Fristen), nicht auf ±1 — bei einem Off-by-one wäre es umgekehrt.
    Kippt das, stimmt etwas mit der Datumsbehandlung nicht."""
    if not DATEI.exists():
        return
    d = json.loads(DATEI.read_text(encoding="utf-8"))
    tage = [v["tage"] for v in d.values()]
    wochen = sum(1 for t in tage if t % 7 == 0)
    eins = sum(1 for t in tage if abs(t) == 1)
    assert wochen > len(tage) * 0.3, f"nur {wochen} von {len(tage)} auf Wochenvielfachen"
    assert eins < wochen, f"±1 ({eins}) häufiger als Wochenvielfache ({wochen}) — Datumsfehler?"
