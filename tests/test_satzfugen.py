"""Ein Satz, der um eine Fettung herum gebaut ist, behaelt seine Leerzeichen.

⚠ GEMELDET AM 2026-09-20. Sven mit einem Bildschirmfoto der Unterlagen-Seite: „super viele
tippfehler". Es waren keine Tippfehler, sondern eine Fehlerklasse. Im Quelltext stand

    ${tk("… machen wir in Sekunden eine")}<b>${tk("Ampel-Einschätzung")}</b>${tk(", eine abhakbare")}…

und im Browser las man „in Sekunden eineAmpel-Einschätzung, eine abhakbareBieter-Checkliste
(K.o.-Kriterien …) undfüllen Firmenangaben vor". Gefunden wurden 21 solcher Fugen in
`explorerCore.js`, quer durch Strategie, Markt und Unterlagen — sichtbar auf jeder Seite,
die jemand aufmacht, und trotzdem keinem Waechter aufgefallen.

⚠ DIE URSACHE IST DIE UEBERSETZUNG, nicht die Nachlaessigkeit. Ein Satz wird an der
Fettung in `tk()`-Stuecke zerschnitten; ein abschliessendes Leerzeichen im Schluessel sieht
aus wie ein Versehen und faellt beim naechsten Anfassen weg. Deshalb steht das Leerzeichen
jetzt im Bauteil, nicht im Schluessel: `${tk("…eine")} <b>` statt `${tk("…eine ")}<b>`.

⚠ WAS DIESER TEST NICHT LEISTET. Er prueft die Fuge, nicht die Wortstellung. Einen Satz an
einer Fettung zu zerschneiden bleibt fuer Uebersetzungen heikel: im Franzoesischen kann die
Reihenfolge eine andere sein, und die Stuecke stehen fest. Das ist bekannt und
beabsichtigt in Kauf genommen, nicht uebersehen.
"""
from __future__ import annotations

import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"

# Auszeichnungen, die MITTEN im Satz stehen koennen.
TAGS = "b|strong|em|i|a"
# ⚠ Diese Zeichen haengen am Wort davor: vor „," oder „)" gehoert KEIN Leerzeichen. Der
# erste Anlauf setzte eines und machte aus „Ampel-Einschätzung, eine" ein
# „Ampel-Einschätzung , eine" — eine Korrektur, die einen neuen Fehler baut.
ANHAENGEND = ",.;:!?)"

# ⚠ EIN ZEICHEN IST KEIN WORT. `<i aria-hidden="true">›</i>` ist ein Pfeil, keine
# Fortsetzung des Satzes; den Abstand macht dort `gap` im Stylesheet, und ein Leerzeichen
# im Markup waere ein zweiter, ungewollter. Der Waechter hat genau das am 2026-09-21
# gemeldet — richtig erkannt, falsch bewertet. Dekoration ist ausgenommen, Text nicht.
VOR = re.compile(rf'(?:tk|t)\("[^"]*[^ "]"\)\}}<(?:{TAGS})(?![^>]*aria-hidden)[ >]')
NACH = re.compile(rf'</(?:{TAGS})>\$\{{(?:tk|t)\("[^ "{re.escape(ANHAENGEND)}]')


def _dateien():
    for p in [WEB / "lib" / "explorerCore.js", *WEB.glob("components/**/*.tsx")]:
        if "node_modules" not in str(p):
            yield p, p.read_text(encoding="utf-8")


def _fugen(s: str) -> list[str]:
    return [m.group(0) for m in VOR.finditer(s)] + [m.group(0) for m in NACH.finditer(s)]


def test_kein_satz_klebt_an_einer_fettung():
    befunde = []
    for p, s in _dateien():
        for f in _fugen(s):
            befunde.append(f"{p.name}: {f}")
    assert not befunde, ("Saetze ohne Leerzeichen an der Fettung:\n  "
                         + "\n  ".join(befunde[:15]))


def test_der_waechter_sieht_genau_den_gemeldeten_fall():
    """Gegenprobe mit dem Original-Wortlaut vom 2026-09-20."""
    kaputt = 'x${tk("machen wir in Sekunden eine")}<b>${tk("Ampel-Einschätzung")}</b>x'
    assert _fugen(kaputt), "der Waechter sieht die gemeldete Stelle nicht"


def test_der_waechter_sieht_auch_die_fuge_HINTER_der_fettung():
    kaputt = 'x</b>${tk("Diese Ausschreibung ist offen.")}x'
    assert _fugen(kaputt), "der Waechter sieht nur die Fuge davor"


def test_der_waechter_meckert_nicht_ueber_ein_anhaengendes_satzzeichen():
    """⚠ Sonst erzwingt er den Fehler, den ich beim Reparieren selbst gebaut habe."""
    richtig = 'x</b>${tk(", eine abhakbare")}x'
    assert not _fugen(richtig), "vor einem Komma wird faelschlich ein Leerzeichen verlangt"
    assert not _fugen('x</b>${tk(") und weitere")}x'), (
        "vor einer SCHLIESSENDEN Klammer wird faelschlich ein Leerzeichen verlangt")
    # ⚠ Die OEFFNENDE Klammer ist der Gegenfall und muss gemeldet werden: „Bieter-Checkliste
    # (K.o.-Kriterien" braucht das Leerzeichen. Genau hier lag einer der 21 Fehler.
    assert _fugen('x</b>${tk("(K.o.-Kriterien) und")}x'), (
        "vor einer oeffnenden Klammer fehlt die Meldung")


def test_der_waechter_meckert_nicht_ueber_ein_vorhandenes_leerzeichen():
    assert not _fugen('x${tk("eine")} <b>${tk("Ampel")}</b> ${tk("und mehr")}x')


def test_der_waechter_haelt_ein_dekoratives_zeichen_nicht_fuer_einen_satz():
    """⚠ Gegenprobe zur Ausnahme: ein `aria-hidden`-Pfeil direkt hinter einem Text ist in
    Ordnung, ein echtes Wort ohne Leerzeichen nicht."""
    assert not _fugen('x${tk("Wie wir das absichern")}<i aria-hidden="true">\u203a</i>x')
    assert _fugen('x${tk("Wie wir das absichern")}<i>und weiter</i>x'), (
        "ein sichtbares Wort ohne Leerzeichen wird nicht mehr gemeldet")
