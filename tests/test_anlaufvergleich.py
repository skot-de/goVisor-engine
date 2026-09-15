"""Zweiter Anlauf gegen ersten (`scripts/build_anlaufvergleich.py`).

Der Erbauer haelt zwei Versprechen, und beide sind leicht zu brechen:
1. Der Status „erfolglos" gehoert dem VORGANG, nicht seiner Ausschreibung.
2. Die Dokumentenspalten stehen im Schema, auch solange sie leer sind — sonst muesste das
   Schema wandern, sobald die Unterlagen da sind, und genau das soll niemand tun muessen.
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
QUELLE = ROOT / "scripts" / "build_anlaufvergleich.py"


def _modul():
    spec = importlib.util.spec_from_file_location("anlaufvergleich", QUELLE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_status_wird_ueber_den_vorgang_verbunden_nicht_ueber_die_ausschreibung():
    """Die Falle, die beim Bauen zugeschlagen hat.

    `verfahren_status='erfolglos'` haengt zu 100 % am Zuschlag (`can`), nie an der
    Ausschreibung (`cn`). Der erste Entwurf verband auf die Leitbekanntmachung und meldete
    daraufhin 0 gescheiterte Anlaeufe bei 101.270 Paaren — kein Fehler, kein leeres Ergebnis,
    nur eine stille Null. Wer den Verbund wieder auf `notice_id` legt, bekommt sie zurueck.
    """
    quelle = QUELLE.read_text(encoding="utf-8")
    assert "stat sa on sa.vorgang_id" in quelle, \
        "Status muss ueber den Vorgang verbunden werden, nicht ueber die Leitbekanntmachung"
    assert "stat sa on sa.notice_id" not in quelle


def test_dokumentenspalten_stehen_im_schema_auch_wenn_sie_leer_sind():
    """Sonst muesste das Schema wandern, sobald die ersten Unterlagenpaare entstehen."""
    duckdb = pytest.importorskip("duckdb")
    if not (ROOT / "data" / "gold" / "DE" / "vorgang_kette.parquet").exists():
        pytest.skip("kein DE-Gold vorhanden")
    m = _modul()
    con = duckdb.connect()
    m.baue(con, "DE")
    spalten = {r[0] for r in con.execute("describe select * from ergebnis").fetchall()}
    for pflicht in ("unterlagen_beide", "vorher_n_anforderungen", "nachher_n_anforderungen",
                    "anf_entfallen", "anf_neu", "vorher_unterlagen", "nachher_unterlagen"):
        assert pflicht in spalten, f"Dokumentenspalte {pflicht} fehlt im Schema"


def test_guete_der_kette_wandert_mit():
    """Ein maschinell entschiedenes Paar darf nicht aussehen wie ein eindeutiges."""
    duckdb = pytest.importorskip("duckdb")
    if not (ROOT / "data" / "gold" / "DE" / "vorgang_kette.parquet").exists():
        pytest.skip("kein DE-Gold vorhanden")
    m = _modul()
    con = duckdb.connect()
    m.baue(con, "DE")
    spalten = {r[0] for r in con.execute("describe select * from ergebnis").fetchall()}
    assert {"konfidenz", "methode"} <= spalten, \
        "ohne Guete darf der Vergleich nicht angezeigt werden (s. Modulkopf)"


def test_baut_alle_aktiven_laender_nicht_nur_de():
    """Die Altlast, die hier schon mehrfach zugeschlagen hat: --land DE als stiller Vorgabewert."""
    baum = ast.parse(QUELLE.read_text(encoding="utf-8"))
    for knoten in ast.walk(baum):
        if (isinstance(knoten, ast.Call) and getattr(knoten.func, "attr", "") == "add_argument"
                and knoten.args and getattr(knoten.args[0], "value", "") == "--land"):
            vorgabe = [k.value.value for k in knoten.keywords if k.arg == "default"]
            assert vorgabe == [None], "--land darf keinen Vorgabewert haben, sonst faellt AT/CH/LU aus"
    assert "from govisor.laender import AKTIV" in QUELLE.read_text(encoding="utf-8")


def test_probe_schreibt_nichts():
    """`--probe` muss rechnen duerfen, waehrend ein anderer Lauf nach data/ schreibt."""
    quelle = QUELLE.read_text(encoding="utf-8")
    baum = ast.parse(quelle)
    fn = next(k for k in ast.walk(baum)
              if isinstance(k, ast.FunctionDef) and k.name == "main")
    schreibt = [k for k in ast.walk(fn)
                if isinstance(k, ast.Call) and getattr(k.func, "id", "") == "schreibe"]
    assert schreibt, "main muss schreibe() kennen"
    # ... aber nur im Nicht-Probe-Zweig
    assert "if a.probe else" in quelle, "schreibe() darf bei --probe nicht aufgerufen werden"
