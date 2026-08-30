"""AT-Unterlagen (vergabeportal.at + wien.gv.at) — Dateilisten, keine Dateien.

Ohne Netz. Die Dateien selbst stehen hinter einem hCaptcha und werden bewusst nicht geholt
(s. `docs/quellen-at-unterschwellig.md`); die LISTE ist offen und beantwortet „gibt es ein
Leistungsverzeichnis".
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
QUELLE = (ROOT / "govisor" / "vergabeportal_at.py").read_text(encoding="utf-8")


def nur_code(quelle: str) -> str:
    """Kommentare und Modul-Docstring weg.

    ⚠ Ohne das verbietet ein Test wie „das Wort CAPTCHA darf nicht vorkommen" genau die
    Stelle, die ERKLÄRT, warum wir es nicht anrühren. Derselbe Fehler ist am 2026-08-30
    schon einmal passiert (`user_profiles` in der Bausteine-Regel).
    """
    zeilen, im_docstring = [], False
    for z in quelle.splitlines():
        s = z.strip()
        if s.startswith('"""') and not im_docstring:
            im_docstring = not s.endswith('"""') or len(s) < 6
            continue
        if im_docstring:
            if s.endswith('"""'):
                im_docstring = False
            continue
        if s.startswith("#"):
            continue
        zeilen.append(z.split("#")[0] if "#" in z else z)
    return "\n".join(zeilen)


CODE = nur_code(QUELLE)


def test_drei_spalten_reichen():
    """⚠ Der Fehler, der 20 von 29 wien.gv.at-Vorgängen kostete.

    Die Schwelle stand auf vier Zellen. Manche Vorgänge führen nur Name/Größe/Erstellt, ohne
    die Spalte „aktualisiert" — die dreispaltige Bauform wurde komplett verworfen, obwohl der
    Reiter „Unterlagen 7" hieß und acht Dateinamen trug. Nachgemessen an allen 20 Fällen:
    20 Listen, 149 Dateinamen statt null.
    """
    assert "zellen.length < 3" in QUELLE
    assert "zellen.length < 4" not in QUELLE


def test_fehlende_spalte_ist_kein_nachtrag():
    """`nachgebessert` vergleicht erstellt/aktualisiert. Ein leerer Wert wäre ein
    Unterschied — und damit ein Nachtrag, den es nie gab."""
    i = QUELLE.index("aktualisiert:")
    zeile = QUELLE[i:QUELLE.index("\n", i)]
    assert "zellen[2]" in zeile, "Rückfall muss der Erstellwert sein, nicht der leere String"


def test_fehlereintrag_traegt_die_url():
    """⚠ 83 Sätze standen als „fehler" ohne Host im Manifest — die Frage „welches Portal
    klemmt?" war aus den eigenen Daten nicht zu beantworten."""
    # Der Manifest-Eintrag, nicht der Rueckgabewert von `hole_liste` — beide tragen
    # denselben Text, und die erste Fundstelle ist die falsche.
    i = CODE.index("_manifest.append")
    while '"status": "fehler"' not in CODE[i:i + 220]:
        i = CODE.index("_manifest.append", i + 1)
    assert '"url": url' in CODE[i:i + 220]


def test_notiz_des_abrufers_wird_nicht_ueberschrieben():
    """Vorher stand bei jedem `leer` stumpf „0 aktiv von 0"; die genauere Auskunft des
    Abrufers ging dabei verloren."""
    assert 'r.get("note") or' in QUELLE


def test_captcha_wird_nicht_angeruehrt():
    """⚠ Grundsatz, kein Detail: ein CAPTCHA ist das deutlichste Signal, das eine Plattform
    senden kann. Die Dateien bleiben ungeholt, die Liste genügt."""
    assert "nur_liste" in CODE
    # Geprüft wird der CODE. Der Modulkopf ERKLÄRT das hCaptcha und die Zustimmungs-Box —
    # ein Test, der die Wörter verbietet, verbietet die Begründung mit.
    for verboten in ("hcaptcha", "h-captcha-response", "2captcha", "anticaptcha",
                     "cbCommitAnonymous"):
        assert verboten.lower() not in CODE.lower(), f"{verboten} hat im Code nichts zu suchen"


def test_nur_die_beiden_bekannten_muster():
    """Die Auswahl bindet an die URL-Form, nicht an Hostnamen — `wien.gv.at` fährt dieselbe
    Software unter `/Vergabeportal/Detail/`."""
    assert "vergabeportal.at/Detail/" in QUELLE
    assert "wien.gv.at/Vergabeportal/Detail/" in QUELLE
