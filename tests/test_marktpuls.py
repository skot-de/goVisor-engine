"""Marktpuls — Regressions-Guards für die Regeln, die man am Bildschirm nicht sieht.

Bewusst OHNE Voll-Lauf: `scripts/build_marktpuls.py` scannt den ganzen Bestand (~40 s).
Geprüft wird deshalb die reine Logik plus der Vertrag der erzeugten Datei, wenn sie da ist.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _modul():
    spec = importlib.util.spec_from_file_location(
        "build_marktpuls", ROOT / "scripts" / "build_marktpuls.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


M = _modul()


def _monate(pcts):
    return [{"m": i + 1, "avg": 100.0, "pct": p} for i, p in enumerate(pcts)]


def test_befund_benennt_nur_echte_ausreisser():
    """Der Ein-Satz-Befund darf keinen Effekt erfinden (Briefing §3.2/§7).

    Unter der Schwelle ist die ehrliche Aussage „gleichmässiger als vermutet" — nicht
    „der stärkste Monat ist X". Genau hier würde eine Marketing-Formulierung entstehen,
    die die Daten nicht hergeben.
    """
    flach = M.befund(_monate([5, -4, 3, 0, 2, -1, 6, -6, 1, 0, -2, 3]))
    assert flach["typ"] == "flach"
    assert flach["monat"] == 7 and flach["monat_tief"] == 8

    spitze = M.befund(_monate([5, -4, 3, 0, 2, -1, 40, -6, 1, 0, -2, 3]))
    assert spitze["typ"] == "spitze" and spitze["monat"] == 7

    tief = M.befund(_monate([5, -4, 3, 0, 2, -1, 6, -30, 1, 0, -2, 3]))
    assert tief["typ"] == "tief" and tief["monat"] == 8

    assert M.befund([])["typ"] == "keine_daten"


def test_quellenfamilien_decken_alle_schema_generationen():
    """Ein neuer Connector bringt eine neue `schema_gen`. Fehlt sie in `QUELLE`, fällt sie
    auf 'sonstige' und würde als eigene Quelle behandelt — ein stiller Fehler, der erst als
    Sprung in der Kurve auffällt. Die Liste muss zu `govisor/schema.py` passen."""
    erwartet = {"legacy", "eforms", "text", "ojs", "doe", "simap", "atverg"}
    assert erwartet <= set(M.QUELLE), f"nicht abgebildet: {erwartet - set(M.QUELLE)}"
    assert set(M.QUELLE.values()) == {"ted", "doe", "simap", "atverg"}


def test_in_list_verdoppelt_hochkommata():
    assert M._in_list("x", []) == "FALSE"
    assert M._in_list("x", ["a'b"]) == "x IN ('a''b')"


def test_branchen_decken_das_ui_vokabular():
    """Dieselben sechs Grundräume wie die Lead-Liste (Briefing §9-4) — sonst zeigt der
    Marktpuls andere Zahlen als die Liste, auf die er verweist."""
    assert set(M.BRANCHEN) == {"bau", "it", "beratung", "medizin", "sicherheit", "energie"}
    for b in M.BRANCHEN:
        assert f"'{b}'" in M.BRANCHE_SQL


@pytest.mark.skipif(not (ROOT / "web" / "data" / "marktpuls.json").exists(),
                    reason="marktpuls.json noch nicht gebaut")
def test_erzeugte_datei_haelt_den_vertrag():
    p = ROOT / "web" / "data" / "marktpuls.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    assert p.stat().st_size < 50 * 1024, "Briefing §5: JSON unter 50 KB"
    for feld in ("schema", "erzeugt", "stand", "laender", "fenster", "coverage", "saison", "lage"):
        assert feld in d, feld
    assert d["fenster"]["jahre"] == M.FENSTER_JAHRE
    assert d["gesamt_key"] in d["coverage"] and d["gesamt_key"] in d["lage"]["je_land"]
    # Jede Land×Branche-Kombination muss existieren — die Anzeige greift blind darauf zu.
    for land in [d["gesamt_key"], *d["laender"]]:
        for br in ["alle", *d["branchen"]]:
            block = d["saison"].get(f"{land}|{br}")
            assert block is not None, f"{land}|{br} fehlt"
            assert len(block["monate"]) == 12
            assert block["genug"] == (block["verfahren_gesamt"] >= d["min_faelle"])
    # Herkunfts-Kennzeichnung darf nie verschwinden (Projekt-Konvention).
    for land, lg in d["lage"]["je_land"].items():
        assert lg["frist_basis"] == "echt", land
        assert "frist_abdeckung" in lg, land
