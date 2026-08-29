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


def _stand_modul():
    """`scripts/dokumente_stand.py` laden — es ist ein Skript, kein Paket."""
    import importlib.util
    from pathlib import Path

    wurzel = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("ds", wurzel / "scripts" / "dokumente_stand.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_hochrechnung_nimmt_den_bezahlten_preis_je_vorgang(tmp_path, monkeypatch):
    """Der Dokumenten-Stand rechnet hoch, was ein Nachholen kosten würde — und nach dieser
    Zahl entscheidet jemand, ob er Guthaben auflädt.

    Bis zum 2026-08-29 rechnete sie mit einem festen Listenpreis (0,30 $ je Mio
    Eingabe-Token) und liess die Ausgabe-Token ausdrücklich weg, während daneben das
    Kostenbuch mit dem abgerechneten Betrag lag. Gemessen über 16.140 echte Aufrufe:
    tatsächlich 0,64 $ je Mio Eingabe plus 56,7 Mio Ausgabe-Token. Die Hochrechnung lag um
    **Faktor 3,6** zu niedrig — 11 $ statt 40 $. Wer ihr glaubt, lädt ein Viertel des
    Nötigen auf und wundert sich, warum der Lauf steht.

    ⚠ Gerechnet wird je VORGANG, nicht je Aufruf. Eine Vergabe kostet mehrere Aufrufe,
    einen je Dokumentgattung. Wer je Aufruf hochrechnet, liegt um diesen Faktor daneben —
    deshalb prüft der Test genau das.
    """
    import json

    from govisor import kostenbuch

    buch = tmp_path / "llm_kosten.jsonl"
    zeilen = [
        # zwei Vorgaenge, sechs Aufrufe, zusammen 1,20 $ → 0,60 $ je Vorgang
        *[{"ts": "2026-08-27T10:00:00+00:00", "zweck": "analyse", "vorgang": "A",
           "kosten_usd": 0.10} for _ in range(3)],
        *[{"ts": "2026-08-27T10:01:00+00:00", "zweck": "analyse", "vorgang": "B",
           "kosten_usd": 0.30} for _ in range(3)],
        # fremder Zweck und Nullbetrag duerfen den Schnitt nicht verschieben
        {"ts": "2026-08-27T10:02:00+00:00", "zweck": "nachfolge", "vorgang": "C",
         "kosten_usd": 99.0},
        {"ts": "2026-08-27T10:03:00+00:00", "zweck": "analyse", "vorgang": "D",
         "kosten_usd": 0.0},
    ]
    buch.write_text("\n".join(json.dumps(z) for z in zeilen) + "\n", encoding="utf-8")
    monkeypatch.setattr(kostenbuch, "PFAD", buch)

    preis, herkunft = _stand_modul()._preis_je_vorgang()
    assert preis == pytest.approx(0.60), \
        f"je Aufruf statt je Vorgang gerechnet (waere 0,20 $) — bekommen: {preis}"
    assert "bezahlt" in herkunft and "2 Vorgaengen" in herkunft, \
        "die Ausgabe sagt nicht mehr, dass die Zahl gemessen und nicht geschaetzt ist"


def test_ohne_kostenbuch_wird_ehrlich_geschaetzt(tmp_path, monkeypatch):
    """Kein Buch heisst „ich weiss es nicht" — nicht „es war umsonst".

    Der Aufrufer faellt dann auf den sichtbaren Listenpreis zurueck. Wichtig ist nur, dass
    er das SAGT: eine geschaetzte Zahl, die aussieht wie eine gemessene, ist schlimmer als
    gar keine.
    """
    from govisor import kostenbuch

    monkeypatch.setattr(kostenbuch, "PFAD", tmp_path / "gibt-es-nicht.jsonl")
    preis, herkunft = _stand_modul()._preis_je_vorgang()
    assert preis is None and herkunft == ""

    quelle = (ROOT / "scripts" / "dokumente_stand.py").read_text(encoding="utf-8")
    assert "geschaetzt" in quelle, "der Rueckfall kennzeichnet sich nicht mehr als Schaetzung"
