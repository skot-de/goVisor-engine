"""Der Kostenbericht — bis zum 2026-08-25 das einzige Stück des Moduls ohne Tests.

Ausgerechnet das Werkzeug, mit dem geprüft wird, ob das Kostenbuch vollständig ist. Sein
einseitiger Vergleich (nur nach oben) fiel heute nur zufällig auf, als er −25 % mit einem
zufriedenen „stimmt überein" quittierte.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import kostenbuch  # noqa: E402


def _bericht():
    spec = importlib.util.spec_from_file_location("kb_rep", ROOT / "scripts/kostenbericht.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_MARKE = {"gesetzt": "2026-08-24T10:00:00+00:00", "total_usage": 100.0, "buch": 10.0}


def test_luecke_misst_beide_zuwaechse_seit_der_marke():
    kb = _bericht()
    l = kb._luecke(_MARKE, 105.0, 14.0)
    assert l["konto"] == pytest.approx(5.0) and l["buch"] == pytest.approx(4.0)
    assert l["luecke"] == pytest.approx(1.0) and l["anteil"] == pytest.approx(0.20)


def test_buch_ueber_der_abrechnung_ergibt_eine_negative_luecke():
    """⚠ Der Grund für die beidseitige Prüfung: `total_usage` läuft nach.

    Die erste Fassung schaute nur nach oben und quittierte −25 % mit „stimmt überein".
    """
    kb = _bericht()
    l = kb._luecke(_MARKE, 104.0, 15.0)
    assert l["luecke"] < 0 and l["anteil"] < 0


def test_ohne_abrechnung_seit_der_marke_gibt_es_keinen_anteil():
    """Ein Anteil braucht einen Bezug. Ohne Abrechnung gibt es keinen."""
    kb = _bericht()
    assert kb._luecke(_MARKE, 100.0, 10.0)["anteil"] == 0.0
    assert kb._luecke(_MARKE, 100.0, 12.0)["anteil"] == 0.0


def test_zeilen_seit_filtert_nach_zeitpunkt(tmp_path, monkeypatch):
    kb = _bericht()
    buch = tmp_path / "k.jsonl"
    monkeypatch.setattr(kostenbuch, "PFAD", buch)
    for ts in ("2026-08-23T09:00:00+00:00", "2026-08-24T09:00:00+00:00",
               "2026-08-25T09:00:00+00:00"):
        with buch.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": ts, "zweck": "analyse", "kosten_usd": 0.01}) + "\n")
    assert len(list(kb._zeilen(None))) == 3
    assert len(list(kb._zeilen("2026-08-24"))) == 2
    assert len(list(kb._zeilen("2026-08-25"))) == 1


def test_die_auffaelligkeiten_zaehlen_den_zeitraum_nicht_das_ganze_buch(tmp_path,
                                                                        monkeypatch, capsys):
    """⚠ Die erste Fassung zählte lebenslang unter der Überschrift „Abgleich seit …".

    Solange die Marke jung ist, fällt das nicht auf; über Wochen schreibt der Bericht
    damit alte Auffälligkeiten dem laufenden Zeitraum zu.
    """
    kb = _bericht()
    buch = tmp_path / "k.jsonl"
    monkeypatch.setattr(kostenbuch, "PFAD", buch)
    monkeypatch.setattr(kb, "MARKE", tmp_path / "marke.json")
    (tmp_path / "marke.json").write_text(json.dumps(_MARKE), encoding="utf-8")
    monkeypatch.setattr(kb, "_gesamtverbrauch", lambda: 105.0)
    with buch.open("w", encoding="utf-8") as f:
        # zwei ALTE leere Antworten (vor der Marke) und eine neue
        for ts, leer in (("2026-08-23T09:00:00+00:00", True),
                         ("2026-08-23T10:00:00+00:00", True),
                         ("2026-08-25T09:00:00+00:00", True)):
            f.write(json.dumps({"ts": ts, "zweck": "analyse", "kosten_usd": 0.01,
                                "leer": leer}) + "\n")
    kb.abgleich()
    aus = capsys.readouterr().out
    assert "1 leere Antwort(en)" in aus, f"nur die eine seit der Marke: {aus}"
