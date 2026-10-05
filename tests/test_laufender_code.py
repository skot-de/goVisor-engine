"""Die Sonde „läuft nachts unser Code?" — an gebauten Fällen, nicht an der Tageslage.

⚠ WARUM DAS EIN EIGENER TEST IST. Die Sonde gegen stille Kennzahlen (`pruefe_streuung.py`)
wurde am 2026-09-01 gebaut und hat bis zum 2026-10-05 **nie in Produktion gelaufen** — sie
existierte im Nachtlauf-Baum als Datei nicht. Eine Prüfung, die nur die heutige Lage misst,
hätte das nie gezeigt: sie wäre im Arbeitsbaum grün gewesen, wo die Sonde ja da ist.

Deshalb hier zwei gebaute Fälle, beide Richtungen: der Detektor muss den Unterschied FINDEN,
und er muss bei Gleichheit SCHWEIGEN. Ohne die zweite Hälfte wäre eine Sonde, die immer
anschlägt, von einer richtigen nicht zu unterscheiden.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pruefe_laufender_code as plc      # noqa: E402


def _baum(wurzel: pathlib.Path, dateien: dict[str, str]) -> pathlib.Path:
    for rel, inhalt in dateien.items():
        p = wurzel / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(inhalt, encoding="utf-8")
    return wurzel


GLEICH = {"scripts/export_strategie.py": "print('a')\n",
          "scripts/fetch_ezb_kurse.py": "print('b')\n",
          "govisor/gold.py": "print('c')\n"}


def test_gleiche_baeume_melden_nichts(tmp_path):
    a = _baum(tmp_path / "a", GLEICH)
    b = _baum(tmp_path / "b", GLEICH)
    e = plc.vergleiche(a, b)
    assert e["gleich"] == 3 and not e["anders"] and not e["fehlt"]
    assert plc.befunde(e) == []


def test_abweichender_erzeuger_ist_ein_befund(tmp_path):
    """Der Fall vom 2026-10-05: der Nachtlauf-Baum hat eine ALTE Fassung des Erzeugers."""
    a = _baum(tmp_path / "a", GLEICH)
    b = _baum(tmp_path / "b", GLEICH | {"scripts/export_strategie.py": "print('ALT')\n"})
    b_ = plc.befunde(plc.vergleiche(a, b))
    assert [x["ausgabe"] for x in b_] == ["web/data/strategie.json"]
    assert b_[0]["art"] == "weicht ab"


def test_fehlender_erzeuger_ist_ein_befund(tmp_path):
    """Der haertere Fall: das Skript gibt es im Nachtlauf-Baum gar nicht — so lag
    `pruefe_streuung.py` fuenf Wochen lang."""
    a = _baum(tmp_path / "a", GLEICH)
    b = _baum(tmp_path / "b", {k: v for k, v in GLEICH.items()
                               if k != "scripts/fetch_ezb_kurse.py"})
    b_ = plc.befunde(plc.vergleiche(a, b))
    assert [x["ausgabe"] for x in b_] == ["data/reference/waehrungskurse.json"]
    assert b_[0]["art"] == "fehlt"


def test_abweichung_ohne_geteilte_ausgabe_ist_KEIN_befund(tmp_path):
    """⚠ Die Gegenrichtung, und sie ist die wichtigere. Ein Arbeitsbaum weicht
    naturgemaess ab — das ist sein Zweck. Waere jede Abweichung ein Befund, waere die
    Sonde dauerrot und damit wertlos. Ein Befund ist nur, wo eine geteilte Ausgabe
    betroffen ist."""
    a = _baum(tmp_path / "a", GLEICH)
    b = _baum(tmp_path / "b", GLEICH | {"govisor/gold.py": "print('anders')\n"})
    e = plc.vergleiche(a, b)
    assert e["anders"] == ["govisor/gold.py"]
    assert plc.befunde(e) == [], "eine Abweichung ohne geteilte Ausgabe darf nicht melden"


def test_jeder_erzeuger_existiert_wirklich():
    """Ein Eintrag in `ERZEUGER`, der auf ein geloeschtes Skript zeigt, prueft nichts mehr
    und sieht trotzdem nach Deckung aus — dieselbe Krankheit wie bei den Ausnahme-Listen
    der uebrigen Sonden."""
    for ausgabe, skript in plc.ERZEUGER.items():
        assert (ROOT / skript).exists(), f"{ausgabe}: Erzeuger {skript} gibt es nicht"


def test_der_nachtlauf_baum_wird_nicht_geraten():
    """⚠ Welcher Baum nachts faehrt, ist genau die Frage — sie aus dem eigenen Pfad
    abzuleiten hiesse, die Antwort vorauszusetzen. Ohne launchd-Eintrag misst die Sonde
    nichts und sagt das, statt still etwas anderes zu vergleichen."""
    echt = plc.PLIST
    try:
        plc.PLIST = pathlib.Path("/gibt/es/nicht.plist")
        baum, grund = plc.nachtlauf_baum()
        assert baum is None and "kein launchd-Eintrag" in grund
    finally:
        plc.PLIST = echt


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
