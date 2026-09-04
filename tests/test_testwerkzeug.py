"""Prüft das Werkzeug, mit dem geprüft wird.

Ein Test kann nur so viel wert sein wie der Code, den er tatsächlich ausführt. Diese Datei
hält die eine Voraussetzung fest, die genau das sicherstellt.
"""
import importlib.util
import sys


def _laden(pfad, name="_probe"):
    spec = importlib.util.spec_from_file_location(name, pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_eine_aenderung_in_derselben_sekunde_wird_gesehen(tmp_path):
    """Die Gegenprobe darf nicht am Bytecode-Zwischenspeicher vorbeilaufen.

    ⚠ WAS HIER SCHIEFGING. Python vermerkt im `.pyc` die Zeit der Quelldatei in GANZEN
    Sekunden. Eine Änderung, die in derselben Sekunde passiert und die Datei gleich gross
    lässt (`<` zu `>` etwa), ist damit unsichtbar — der nächste Ladevorgang führt den ALTEN
    Code aus. Genau diesen Rhythmus hat jede Gegenprobe hier: Fehler einbauen, testen,
    Fehler entfernen, testen. Am 2026-09-04 hat es zugeschlagen; die Tests blieben nach dem
    Zurückbauen rot, obwohl der Quelltext wieder stimmte.

    `tests/conftest.py` schaltet deshalb das Schreiben von Bytecode ab. Dieser Test ist die
    Gegenprobe dazu: nimmt man die Zeile heraus, wird er rot.
    """
    f = tmp_path / "m.py"
    f.write_text("def wert():\n    return 1\n", encoding="utf-8")
    assert _laden(f).wert() == 1

    # Sofort, ohne zu warten, und mit exakt gleicher Dateigroesse — beides gehoert dazu.
    f.write_text("def wert():\n    return 2\n", encoding="utf-8")
    assert _laden(f).wert() == 2, (
        "Der Ladevorgang hat alten Bytecode ausgefuehrt. Damit prueft JEDE Gegenprobe in "
        "dieser Suite moeglicherweise den falschen Code. Ursache: `sys.dont_write_bytecode` "
        "steht nicht mehr auf True (tests/conftest.py).")


def test_die_voreinstellung_steht():
    """Der Riegel selbst, damit der Grund auffindbar bleibt."""
    assert sys.dont_write_bytecode is True, (
        "tests/conftest.py setzt `sys.dont_write_bytecode` nicht mehr — siehe die "
        "Begruendung dort.")
