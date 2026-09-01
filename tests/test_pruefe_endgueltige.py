"""Sonde 5 — die Wache gegen die Fehlerklasse, die neunmal zugeschlagen hat.

⚠ Der Sinn dieser Datei ist NICHT, dass die Sonde durchläuft. Eine Sonde, die nie anschlägt,
sieht genauso aus wie eine funktionierende — und genau daran sind die neun Vermerke so lange
vorbeigekommen. Geprüft wird deshalb vor allem, dass sie ein gefallenes Urteil ERKENNT.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("pe", WURZEL / "scripts" / "pruefe_endgueltige.py")
pe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pe)


class _Ergebnis:
    def __init__(self, status): self.status = status


def _mit_abrufer(monkeypatch, muster):
    """⚠ Die Folge EINMAL anlegen, nicht je Aufruf. `_waehle_connector` wird pro Satz
    gerufen; ein Iterator im Lambda begänne jedes Mal von vorn und liesse alle 18 Sätze
    zurückkehren — der Test wäre grün gewesen, ohne etwas zu prüfen."""
    from govisor import docfetch
    folge = iter(muster)
    abrufer = lambda *a, **k: _Ergebnis(next(folge))
    monkeypatch.setattr(docfetch, "_waehle_connector", lambda url: abrufer)


def test_gefallenes_urteil_schlaegt_an(monkeypatch):
    """Der rib-Fall: 13 von 18 kamen zurück. Das MUSS auffallen."""
    _mit_abrufer(monkeypatch, ["downloaded"] * 13 + ["abgelaufen"] * 5)
    paare = [(f"n{i}", f"https://x/{i}") for i in range(18)]
    n, zurueck = pe.pruefe(paare, 18)
    assert n == 18 and zurueck == 13
    assert zurueck / n >= pe.SCHWELLE and zurueck >= pe.MIN_TREFFER


def test_haltendes_urteil_bleibt_still(monkeypatch):
    """Der `weg`-Fall: 32 von 33 sind echt 404. Kein Fehlalarm."""
    _mit_abrufer(monkeypatch, ["downloaded"] + ["weg"] * 32)
    paare = [(f"n{i}", f"https://x/{i}") for i in range(33)]
    n, zurueck = pe.pruefe(paare, 33)
    assert not (zurueck / n >= pe.SCHWELLE and zurueck >= pe.MIN_TREFFER)


def test_einzelner_treffer_ist_kein_urteil(monkeypatch):
    """⚠ Aus n=1 wird hier nichts abgeleitet — ein Portal darf einen Vorgang
    wiederveröffentlichen, ohne dass eine ganze Klasse als falsch gilt. Bei einer kleinen
    Gruppe reisst ein einzelner Treffer die Quote sonst über die Schwelle."""
    _mit_abrufer(monkeypatch, ["downloaded"] * 2 + ["weg"] * 3)
    n, zurueck = pe.pruefe([(f"n{i}", f"https://x/{i}") for i in range(5)], 5)
    assert zurueck / n >= pe.SCHWELLE, "40 % — die Quote allein würde anschlagen"
    assert zurueck < pe.MIN_TREFFER, "MIN_TREFFER fängt es ab"


def test_absturz_zaehlt_nicht_als_rueckkehr(monkeypatch):
    """Ein kaputter Abrufer darf nicht als „geht wieder" durchgehen."""
    def kracht(*a, **k): raise RuntimeError("Netz")
    from govisor import docfetch
    monkeypatch.setattr(docfetch, "_waehle_connector", lambda url: kracht)
    n, zurueck = pe.pruefe([("n1", "https://x/1"), ("n2", "https://x/2")], 2)
    assert (n, zurueck) == (2, 0)


def test_erfolg_ist_kein_urteil():
    """`exists`/`downloaded` sind der Erfolgsfall, nicht ein Vermerk über den Vorgang —
    sie dürfen nie in der Prüfliste landen."""
    assert pe.ERFOLG == {"exists", "downloaded"}


def test_sonde_schreibt_nicht():
    """⚠ Sie läuft neben einem aktiven Abrufer. Kein Schreibweg nach data/ im Quelltext."""
    code = (WURZEL / "scripts" / "pruefe_endgueltige.py").read_text(encoding="utf-8")
    ohne_kommentar = "\n".join(z for z in code.splitlines() if not z.lstrip().startswith("#"))
    for verbot in ("write_table", "to_parquet", ".write_bytes", "shutil.move", "replace("):
        assert verbot not in ohne_kommentar, f"{verbot} schreibt"
    assert "TemporaryDirectory" in ohne_kommentar
