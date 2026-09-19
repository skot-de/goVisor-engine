"""Alle Marken einer Tabellenzeile tragen dieselbe Bauform — GEMESSEN.

⚠ DIESER TEST IST DIE ANTWORT AUF EINEN FEHLSCHLAG DES BESTEHENDEN WAECHTERS. Am
2026-09-19 stand in `explorer.css` korrekt

    .dokpill{font-size:11.5px;font-weight:500; …}

und die Unterlagen-Label standen trotzdem in **13 px** neben lauter 11,5-px-Marken. Eine
Zeile weiter unten stand naemlich

    td.c-doks button{font:inherit; …}

`td.c-doks button` ist spezifischer als `.dokpill`, und das `font`-Kuerzel setzt Groesse,
Gewicht, Familie und Zeilenhoehe auf geerbt. Der Wert war da und galt nicht.

⚠ `test_tabelle_ruhe.py::test_die_unterlagen_label_haben_die_form_der_anderen_spalten` war
dabei GRUEN, zu Recht: es prueft die Deklaration, und die war richtig. Eine Textpruefung
kann Kaskade und Spezifitaet nicht sehen. Gefunden hat es Sven mit blossem Auge, nachdem
die Suite alles in Ordnung gemeldet hatte.

Die Lehre ist nicht „mehr Textpruefungen", sondern: **wo das Ergebnis aus einer Kaskade
entsteht, muss man das Ergebnis messen.** Der alte Test bleibt trotzdem stehen — er sagt,
was GEWOLLT ist, und das liest sich im Fehlerfall schneller als eine Pixelzahl.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SONDE = WURZEL / "scripts" / "pruefe_marken_optik.py"


def _lauf(*args: str):
    return subprocess.run([sys.executable, str(SONDE), *args],
                          capture_output=True, text=True, cwd=WURZEL, timeout=180)


def test_die_marken_sehen_gleich_aus():
    """Ohne Playwright/Chromium gibt die Sonde keine Auskunft — das ist kein Befund."""
    r = _lauf()
    if r.returncode == 2:
        return
    assert r.returncode == 0, r.stdout[-1200:] + r.stderr[-400:]
    assert "eine Bauform" in r.stdout


def test_die_sonde_sieht_eine_abweichung_die_nur_aus_der_kaskade_kommt():
    """Gegenprobe mit GENAU DEM FEHLER, der passiert ist.

    ⚠ Die Mutation setzt keinen falschen Wert — sie setzt an anderer Stelle einen
    RICHTIGEN, der den ersten ueberstimmt. Eine Textpruefung auf `.dokpill` bleibt dabei
    gruen; nur eine Messung sieht es.
    """
    css = WURZEL / "web" / "app" / "explorer.css"
    echt = css.read_text(encoding="utf-8")
    anker = "td.c-doks button{font-family:inherit;cursor:pointer;transition:.12s}"
    assert anker in echt, "die Knopf-Regel der Unterlagen-Spalte sieht anders aus"
    try:
        css.write_text(echt.replace(
            anker, "td.c-doks button{font:inherit;cursor:pointer;transition:.12s}", 1),
            encoding="utf-8")
        r = _lauf()
        if r.returncode == 2:
            return
        assert r.returncode == 1, (
            "die Sonde bleibt gruen, obwohl die Unterlagen-Label wieder groesser sind als "
            "alle anderen")
        assert "Schriftgroessen laufen auseinander" in r.stdout
    finally:
        css.write_text(echt, encoding="utf-8")


def test_die_sonde_sieht_eine_marke_ohne_farbe():
    """Der zweite Teil von Svens Meldung: „die farben kommen nicht rueber"."""
    css = WURZEL / "web" / "app" / "explorer.css"
    echt = css.read_text(encoding="utf-8")
    anker = ".dok-link2{background:var(--surface-3);color:var(--ink-500)}"
    assert anker in echt
    try:
        css.write_text(echt.replace(
            anker, ".dok-link2{background:transparent;color:var(--ink-500)}", 1),
            encoding="utf-8")
        r = _lauf()
        if r.returncode == 2:
            return
        assert r.returncode == 1, "eine Marke ohne Grund faellt der Sonde nicht auf"
        assert "ohne getoenten Grund" in r.stdout
    finally:
        css.write_text(echt, encoding="utf-8")


def test_jede_ausnahme_traegt_eine_begruendung():
    """⚠ Eine Ausnahmeliste ohne Gruende wird zur Muellhalde: jeder neue Befund wandert
    hinein, und nach einem halben Jahr prueft die Sonde nichts mehr. Dieselbe Regel haelt
    `tests/test_verdrahtung.py` fuer die Verdrahtungssonde.
    """
    code = SONDE.read_text(encoding="utf-8")
    i = code.index("OHNE_GRUND_ERLAUBT = {")
    block = code[code.rindex("# ⚠ AUSNAHMEN STEHEN HIER", 0, i):code.index("}", i)]
    namen = [z for z in block.splitlines() if z.strip().startswith('"')]
    assert len(namen) <= 2, (
        f"{len(namen)} Ausnahmen. Ab der dritten ist es keine Ausnahme mehr, sondern die "
        f"Regel — dann gehoert die Regel geaendert, nicht die Liste verlaengert.")
    kommentar = "\n".join(z for z in block.splitlines() if z.strip().startswith("#"))
    assert len(kommentar) > 200, "die Ausnahmen sind nicht begruendet"


def test_die_liste_deckt_alle_marken_spalten_ab():
    """⚠ Die Sonde misst nur, was in `MARKEN` steht — und genau daran ist sie einmal
    gescheitert: `.wettb` fehlte, also meldete sie „eine Bauform", waehrend die Spalte
    Wettbewerb in 9,5 px mit Versalien danebenstand (15 px hoch statt 21). Gefunden hat es
    Sven, nicht die Sonde.

    Dieser Test schliesst die halbe Luecke: das ENTFERNEN einer bekannten Spalte faellt auf.
    Eine NEUE Marken-Spalte muss weiterhin ein Mensch eintragen. Das ist ehrlicher, als so
    zu tun, als liesse sich „ist das eine Marke?" aus dem Quelltext ableiten — in
    `cellHTML` stehen Dutzende `<span class=…>`, und die meisten sind Text, nicht Marke.
    """
    code = SONDE.read_text(encoding="utf-8")
    i = code.index("MARKEN = [")
    block = code[i:code.index("\n]", i)]
    for zelle, was in (("c-src", "Phase"), ("c-natur", "Leistung"), ("c-wf", "Status"),
                       ("c-doks", "Unterlagen"), ("c-empf", "Empfehlung"),
                       ("c-neu", "Wettbewerb")):
        assert f'"{zelle}"' in block, (
            f"die Spalte {was} ({zelle}) wird nicht mehr gemessen — sie kann beliebig "
            f"auseinanderlaufen, ohne dass es auffaellt")
