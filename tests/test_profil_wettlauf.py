"""Zwei Schreibvorgaenge auf dasselbe Feld, beide ohne `await` — und der falsche gewinnt.

⚠ GEMESSEN AM 2026-09-17, waehrend der Vorbereitung einer Vorfuehrung. Ein frisch
angelegtes Konto trug im `user_profiles.profile`-Blob nur noch die Firmenprofil-Felder
(`stammdaten`, `attributes`, …) — `cpvFields`, `regions` und `branche` waren weg.

Die Folge in der Oberflaeche ist das Gegenteil von harmlos: `brancheFromProfile` findet
nichts, der Explorer faellt auf den Vorgaberaum „it" zurueck, und ein Bau-Profil filtert
die IT-Liste auf **0 von 7.013**. Der Nutzer liest „Keine Leads mit diesen Filtern" —
unmittelbar nach einem Onboarding, das ihm gerade 509 Zuschlaege bestaetigt hat.

Ursache: `uebernimmCheck` und `saveProfile` schreiben BEIDE nach `user_profiles.profile`.
`uebernimmCheck` liest den Blob, aendert die Nachweisfelder und schreibt ihn ZURUECK — also
den Stand vom Lesezeitpunkt. Beide liefen ohne `await`; kam der Check zuletzt an,
ueberschrieb er das gerade gespeicherte Engine-Profil.

⚠ WARUM DAS NIEMAND BEMERKT HAT. Der Fehler braucht BEIDES: einen ausgefuellten
Eignungs-Check und eine erkannte Firma. Wer ohne Check durchs Onboarding geht — und so
entstehen alle vorbereiteten Testkonten — bekommt ein heiles Profil. Der Weg, der bricht,
ist ausgerechnet der vollstaendige.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEITE = ROOT / "web" / "app" / "onboarding" / "page.tsx"


def _ohne_kommentar(s: str) -> str:
    """`//` und `/* */` raus — sonst prueft der Test die Begruendung (F13)."""
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


def test_das_engine_profil_wird_zuerst_und_abgewartet_geschrieben():
    """Reihenfolge UND `await` — eines allein genuegt nicht.

    Ohne `await` ist die Reihenfolge im Quelltext bedeutungslos: beide Versprechen laufen
    gleichzeitig los, und welches zuletzt schreibt, entscheidet das Netz.
    """
    code = _ohne_kommentar(SEITE.read_text(encoding="utf-8"))

    i_save = code.find("saveProfile(profile)")
    i_check = code.find("uebernimmCheck(")
    assert i_save > 0, "saveProfile wird nicht mehr aufgerufen"
    assert i_check > 0, "uebernimmCheck wird nicht mehr aufgerufen"

    assert i_save < i_check, (
        "uebernimmCheck steht VOR saveProfile. Es liest den Blob und schreibt ihn zurueck — "
        "damit ueberschreibt es das Engine-Profil, das danach erst kommt. Der Nutzer landet "
        "mit leerem Profil im Explorer und sieht 0 Treffer.")

    for name, i in (("saveProfile", i_save), ("uebernimmCheck", i_check)):
        davor = code[max(0, i - 12):i]
        assert "await" in davor, (
            f"{name} wird nicht abgewartet. Zwei ungebremste Schreibvorgaenge auf dasselbe "
            f"jsonb-Feld entscheidet das Netz, nicht der Quelltext.")


def test_die_funktion_darf_ueberhaupt_warten():
    """`await` in einer nicht-asynchronen Funktion ist ein Syntaxfehler — und genau der
    faellt beim Umstellen der Reihenfolge leicht hinten runter."""
    code = _ohne_kommentar(SEITE.read_text(encoding="utf-8"))
    m = re.search(r"(async\s+)?function fertigstellen\s*\(", code)
    assert m, "fertigstellen() gibt es nicht mehr"
    assert m.group(1), "fertigstellen() ist nicht async, kann also nicht awaiten"
