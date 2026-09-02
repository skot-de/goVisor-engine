"""Der Gold-Waechter — und vor allem: laeuft er ueberhaupt jemand?

`verify.gold_integrity` gab es seit dem ersten Gold-Bau und war korrekt. Aufgerufen hat
sie der Tageslauf bis zum 2026-09-02 trotzdem nie: sie hing hinter `cli verify`, das davor
rund 270 Monate gegen die TED-API prueft. Genau die Fehlerklasse „gebaut, aber nicht
verdrahtet" — deshalb prueft die erste Funktion hier die VERDRAHTUNG und nicht die Logik.
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKRIPT = ROOT / "scripts" / "pruefe_gold_integritaet.py"


def _quelle() -> str:
    return SKRIPT.read_text(encoding="utf-8")


def _tageslauf_ohne_kommentare() -> str:
    """⚠ Kommentarzeilen streichen — sonst besteht der Test auch dann noch, wenn der
    Aufruf laengst auskommentiert ist und der Name nur noch in der Begruendung steht.
    Dieselbe Vorsicht wie in `test_verdrahtung.py`."""
    lauf = (ROOT / "scripts" / "daily_leads.sh").read_text(encoding="utf-8")
    return "\n".join(z for z in lauf.splitlines() if not z.lstrip().startswith("#"))


def test_der_waechter_haengt_im_tageslauf():
    """Ohne diese Zeile ist der Waechter genau das, was er beheben soll."""
    assert "scripts/pruefe_gold_integritaet.py" in _tageslauf_ohne_kommentare(), (
        "Der Gold-Waechter steht in keinem Tageslauf — dann prueft er nichts.")


def test_der_waechter_bricht_den_lauf_nicht_ab():
    """Wie die uebrigen Sonden: Befund melden, aber die Nacht nicht abschiessen."""
    lauf = _tageslauf_ohne_kommentare()
    stelle = lauf.index("scripts/pruefe_gold_integritaet.py")
    assert "||" in lauf[stelle:stelle + 300], "Befund darf den Tageslauf nicht abbrechen"


def test_die_laender_stehen_nicht_im_skript():
    """Eine feste Laenderliste haette den Waechter beim vierten Land ausgehebelt.

    goVisor ist EU-weit geplant; ein Waechter, der nur DE/AT/CH kennt, meldet fuer Polen
    stillschweigend „sauber". Die Laender kommen deshalb von der Platte.
    """
    q = _quelle()
    assert not re.search(r'\(\s*"DE"\s*,\s*"AT"\s*,\s*"CH"\s*\)', q), (
        "feste Laenderliste im Gold-Waechter — ein neues Land faellt sonst heraus")
    assert "_laender" in q


def test_der_waechter_fuehrt_keine_eigene_ausnahmeliste():
    """Ausnahmen gehoeren in `verify.gold_integrity`, wo die Messung danebensteht.

    Eine zweite Liste hier waere die handgepflegte Parallelliste, an der schon der
    Altersbericht gescheitert ist: sie hoert irgendwann auf mitzuwachsen.
    """
    q = _quelle()
    assert "AUSNAHMEN" not in q.replace("FK_AUSNAHMEN", ""), (
        "Der Waechter baut eine zweite Ausnahmeliste auf — sie gehoert in verify.py")


@pytest.fixture()
def waechter(tmp_path, monkeypatch):
    import importlib.util
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("pgi_test", SKRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "ROOT", tmp_path)
    return m


def _gold(tmp_path: pathlib.Path, land: str, tabelle: str, spalten: dict[str, list[str]]):
    import pyarrow as pa
    import pyarrow.parquet as pq
    d = tmp_path / "data" / "gold" / land
    d.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table({k: pa.array(v, pa.string()) for k, v in spalten.items()}),
                   d / tabelle)


def _paar_tabelle(tmp_path: pathlib.Path, land: str, master: list[str], dup: list[str]):
    """`notice_duplicates` traegt BEIDE Schluesselspalten — beide werden geprueft."""
    _gold(tmp_path, land, "notice_duplicates.parquet",
          {"master_id": master, "duplicate_id": dup})


def test_waise_wird_gemeldet(waechter, tmp_path):
    """Der Fall vom 2026-09-02: die Firewall zeigt auf eine zurueckgezogene Kennung."""
    _gold(tmp_path, "AT", "quality.parquet", {"notice_id": ["atv-1", "atv-2"]})
    _paar_tabelle(tmp_path, "AT", master=["atv-1", "atv-1"], dup=["atv-2", "atv-9"])

    treffer = waechter.befunde("AT")
    assert treffer, "die Waise atv-9 muss auffallen"
    label, n = treffer[0]
    assert "notice_duplicates" in label and n == 1
    assert waechter.main([]) == 1, "ein Befund muss den Rueckgabewert 1 ergeben"


def test_sauberes_gold_meldet_nichts(waechter, tmp_path):
    _gold(tmp_path, "AT", "quality.parquet", {"notice_id": ["atv-1", "atv-2"]})
    _paar_tabelle(tmp_path, "AT", master=["atv-1"], dup=["atv-2"])
    assert waechter.befunde("AT") == []
    assert waechter.main([]) == 0


def test_neues_land_wird_von_allein_mitgeprueft(waechter, tmp_path):
    """Der eigentliche Zweck von `_laender`: Polen darf niemand eintragen muessen."""
    _gold(tmp_path, "PL", "quality.parquet", {"notice_id": ["pl-1"]})
    _paar_tabelle(tmp_path, "PL", master=["pl-1"], dup=["pl-9"])
    assert "PL" in waechter._laender()
    assert waechter.main([]) == 1
