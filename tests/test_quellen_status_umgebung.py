"""Der TED-Status wird aus der Datenlage ABGELEITET — und sagt es, wenn er nicht messen kann.

⚠ WARUM DAS EINE EIGENE PRUEFUNG BRAUCHT. `sources._ted_status()` sieht auf der Platte nach,
statt pauschal `candidate` zu setzen — richtig so, denn ein Status, der die Datenlage nicht
kennt, ist eine Vorgabe mit Etikett (Polen stand so monatelang falsch da).

Der Preis davon ist aber, dass die Zahl eine Eigenschaft der MASCHINE wird: derselbe Commit
meldete am 2026-10-05 in einem Baum mit Datenebene **21** live und in einem frischen
Arbeitsbaum ohne `data`-Symlink **18**. Gefunden hat das die Aufräum-Sitzung, weil eine Zahl
auf der Faktenseite nicht stimmen wollte — und sie hätte um ein Haar die 18 dorthin
geschrieben, also den Zustand eines leeren Baums auf eine Seite, die Sprachmodelle wörtlich
übernehmen.

Was diese Prüfung festhält: fehlt die Datenebene GANZ, darf der Status sich nicht wie eine
Messung lesen. Er trägt dann einen Hinweis, der sagt, dass nichts gemessen wurde.
"""
from __future__ import annotations

import importlib.util
import pathlib
import shutil
import sys

import pytest

WURZEL = pathlib.Path(__file__).resolve().parent.parent
QUELLE = WURZEL / "govisor" / "sources.py"


def _ohne_datenebene(tmp_path: pathlib.Path):
    """Laedt `sources.py` aus einem Baum, der KEIN `data` hat."""
    haus = tmp_path / "haus"
    (haus / "govisor").mkdir(parents=True)
    shutil.copy(QUELLE, haus / "govisor" / "sources.py")
    assert not (haus / "data").exists(), "der Scheinbaum soll gerade keine Datenebene haben"
    spec = importlib.util.spec_from_file_location(
        f"sources_ohne_daten_{tmp_path.name}", haus / "govisor" / "sources.py")
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


def test_ohne_datenebene_sagt_der_status_dass_nichts_gemessen_wurde(tmp_path):
    m = _ohne_datenebene(tmp_path)
    status, hinweis = m._ted_status("DE")
    assert status == "candidate", f"ohne Daten darf nichts als angebunden gelten, war {status}"
    assert "NICHT gemessen" in hinweis, (
        "der Status liest sich wie eine Messung, obwohl keine stattfand — genau die "
        f"Fehlerklasse dieses Hauses. Hinweis war: {hinweis!r}")


def test_der_hinweis_landet_auch_in_der_registry(tmp_path):
    """Nicht nur die Funktion, auch das, was ein Leser sieht. Sonst steht die Ehrlichkeit
    im Rueckgabewert und nicht im Produkt."""
    m = _ohne_datenebene(tmp_path)
    ted = [s for s in m.REGISTRY if s.id.startswith("ted-")]
    assert ted, "keine TED-Quellen in der Registry"
    assert any("NICHT gemessen" in s.coverage for s in ted), (
        "der Hinweis kommt in der Registry nicht an")


def test_mit_datenebene_wird_wirklich_gemessen():
    """Die Gegenrichtung — sonst koennte die Funktion immer „nicht gemessen" sagen und
    bestuende beide Pruefungen oben."""
    from govisor import sources
    if not (WURZEL / "data").exists():
        pytest.skip("dieser Baum hat selbst keine Datenebene")
    status, hinweis = sources._ted_status("DE")
    assert "NICHT gemessen" not in hinweis, "mit Datenebene darf der Warnhinweis nicht stehen"
    assert status in ("live", "prepared", "candidate")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
