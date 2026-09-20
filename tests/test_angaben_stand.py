"""„4 von 6 Angaben" — die Zahl im Ueberblick, gerechnet statt gelesen.

⚠ WARUM DIESE ZAHL EINEN EIGENEN WAECHTER HAT. Sie ist die einzige im Ueberblick, die
nicht aus den Leads kommt, sondern aus dem Profil des Nutzers — und sie fordert etwas von
ihm. Eine Zahl, die zu Unrecht eine Luecke behauptet, ist deshalb kein Schoenheitsfehler,
sondern eine falsche Mahnung. Zwei Wege dorthin sind im Code angelegt und sehen beide
harmlos aus:

  * `regions: null` heisst „bundesweit taetig", nicht „nicht ausgefuellt". `buildProfile`
    macht aus einer leeren Eingabe bewusst null. Wer das als Luecke zaehlt, mahnt eine
    Angabe an, die schon gemacht wurde.
  * `zielrichtung` traegt eine Vorgabe und ist damit immer gesetzt. Im Nenner waere sie
    eine geschenkte Angabe.

⚠ Und warum „4 von 6" und nicht „67 %": ein Prozentsatz verspricht, dass 100 erreichbar
ist. Wer keine Buergschaft hat und keine will, kommt nie dorthin und wird dafuer jeden Tag
angetippt. Sven am 2026-09-20 entschieden.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SONDE = WURZEL / "web" / "scripts" / "pruefe-angaben.mjs"
ENGINE = WURZEL / "web" / "lib" / "profileEngine.js"
TSX = WURZEL / "web" / "components" / "explorer" / "DetailPanel.tsx"


def _lauf():
    return subprocess.run(["node", str(SONDE)], capture_output=True, text=True,
                          cwd=WURZEL / "web", timeout=120)


def _mit_mutation(datei: Path, alt: str, neu: str):
    echt = datei.read_text(encoding="utf-8")
    assert echt.count(alt) == 1, f"Anker nicht eindeutig ({echt.count(alt)}x): {alt[:70]}"
    try:
        datei.write_text(echt.replace(alt, neu, 1), encoding="utf-8")
        return _lauf()
    finally:
        datei.write_text(echt, encoding="utf-8")


def test_die_angaben_werden_richtig_gezaehlt():
    r = _lauf()
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-500:]
    assert "Angaben-Zaehlung stimmt" in r.stdout


def test_die_sonde_sieht_wenn_bundesweit_als_luecke_zaehlt():
    """Die falsche Mahnung: wer bundesweit arbeitet, hat die Frage beantwortet."""
    r = _mit_mutation(
        ENGINE,
        "    ['region', !!(p && ((p.regions && p.regions.length) || p.regionTyp === 'bundesweit'))],",
        "    ['region', !!(p && p.regions && p.regions.length)],")
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl bundesweit als Luecke zaehlt"
    assert "bundesweit" in r.stdout


def test_die_sonde_sieht_eine_geschenkte_angabe_im_nenner():
    """`zielrichtung` hat eine Vorgabe — im Nenner waere sie immer schon erfuellt."""
    r = _mit_mutation(
        ENGINE, "    ['aus',    gesetzt(p && p.exclusions)],",
        "    ['aus',    gesetzt(p && p.exclusions)],\n"
        "    ['ziel',   gesetzt(p && p.zielrichtung)],")
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl der Nenner auf 7 steht"
    assert "sechs Angaben im Nenner" in r.stdout


def test_die_sonde_sieht_die_doppelt_gezaehlte_wertspanne():
    r = _mit_mutation(
        ENGINE, "    ['wert',   !!(p && (p.volMin != null || p.volMax != null))],",
        "    ['wert',   !!(p && p.volMin != null)],\n"
        "    ['wert2',  !!(p && p.volMax != null)],")
    assert r.returncode == 1, "die Sonde bleibt gruen, obwohl die Spanne doppelt zaehlt"


def test_die_zahl_steht_als_verhaeltnis_und_nicht_als_prozent():
    """⚠ Textpruefung, und sie weiss das: sie haelt eine ENTSCHEIDUNG fest, keine Mechanik.
    Ein Prozentzeichen im Ueberblick waere das Versprechen, dass 100 erreichbar ist."""
    q = TSX.read_text(encoding="utf-8")
    i = q.index('label={t("Angaben im Profil")}')
    fenster = q[i - 400:i]
    assert '{a} von {b}' in fenster, "die Kachel zeigt die Angaben nicht mehr als Verhaeltnis"
    assert "%" not in fenster, "im Ueberblick steht wieder ein Prozentsatz"
