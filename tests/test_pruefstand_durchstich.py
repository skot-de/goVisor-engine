"""Durchstich durch den automatischen Modelltest — alles echt ausser dem Modell.

**Warum es diesen Test gibt.** Die Unit-Tests in `test_modellwahl.py` fuettern den
Pruefstand mit Zahlen, die ich mir ausgedacht habe. Genau daran sind am 2026-08-24 zwei
Fehler vorbeigelaufen: unlesbare Antworten kamen oben als „0 Punkte bei 0 Verwerfungen" an
(und haetten gute Modelle dauerhaft aussortiert), und das Kostenbuch buchte leere Antworten
nicht. Beide waren unsichtbar, weil kein Test die Kette **vom Modell bis zum Urteil**
durchlief.

Hier laeuft `scripts/modellpruefung.py:main()` echt: Grundlinie messen, Vorpruefung,
Uebernahme der Vorpruefungswerte in die Hauptpruefung, Urteil, automatische Freigabe per
Unterprozess. Gefaelscht ist einzig `llm.chat` — und zwar so, dass es sich wie ein echtes
Modell verhaelt: es beantwortet den Zusammenfassungs-Aufruf anders als den
Extraktions-Aufruf und bucht seine Kosten ins Kostenbuch, wie `_buchen` es taete.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import kostenbuch, llm, pruefstand as ps  # noqa: E402

SUMMARY = ('{"ampel":"gelb","ampel_grund":"Test","zusammenfassung":"Test",'
           '"aufwand":"mittel"}')
TEXT = "Eignungskriterien. Der Bieter hat drei Referenzen vorzulegen. " * 40


def _items(n: int) -> str:
    """n belegte Eintraege, deren Zitat woertlich im TEXT steht (sonst verwirft §6a.2)."""
    return json.dumps([{"req_type": "referenz_anzahl", "text": f"Referenz {i}",
                        "value_num": 3,
                        "quote": "Der Bieter hat drei Referenzen vorzulegen",
                        "marking": "Zitat"} for i in range(n)], ensure_ascii=False)


def _lade(pfad: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / pfad)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture()
def buehne(tmp_path, monkeypatch):
    """Alles Persistente in tmp_path, Geldwache aus, Modell gefaelscht."""
    monkeypatch.setattr(kostenbuch, "PFAD", tmp_path / "kosten.jsonl")
    monkeypatch.setattr(ps, "WARTESCHLANGE", tmp_path / "pruefstand.json")
    monkeypatch.setattr(ps, "VORPRUEFUNG_N", 2)
    monkeypatch.setattr(ps, "HAUPTPRUEFUNG_N", 4)
    monkeypatch.setattr(ps, "MIN_N", 3)
    monkeypatch.setattr(llm, "_geldwache", lambda: None)
    # Der Unterprozess der Freigabe erbt die Umgebung — er muss in dieselbe Datei schreiben.
    monkeypatch.setenv("GOVISOR_MODELLFREIGABE", str(tmp_path / "freigabe.json"))
    monkeypatch.setenv("GOVISOR_PRUEFSTAND", str(tmp_path / "pruefstand.json"))
    monkeypatch.setenv("GOVISOR_KOSTENBUCH", str(tmp_path / "kosten.jsonl"))
    return tmp_path


def _stelle_modell(monkeypatch, punkte_je_modell: dict, preis_je_modell: dict,
                   protokoll: list):
    """Faelscht `llm.chat` so, dass es sich wie ein Modell verhaelt — inklusive Buchung."""
    import govisor.docextract as dx

    def fake(messages, model=None, **kw):
        txt = " ".join(m.get("content", "") for m in messages)
        grund = kostenbuch.grundmodell(model or "")
        vorgang = getattr(llm._KONTEXT, "vorgang", None)
        zweck = getattr(llm._KONTEXT, "zweck", None)
        protokoll.append((grund, vorgang))
        kostenbuch.notiere(anbieter="openrouter", modell=model or "?", endpunkt="Fake",
                           vorgang=vorgang, zweck=zweck, eingabe_token=1000,
                           ausgabe_token=200,
                           kosten_usd=preis_je_modell.get(grund, 0.01), sekunden=1.0)
        if "ampel" in txt.lower():
            return SUMMARY
        return _items(punkte_je_modell.get(grund, 0))

    monkeypatch.setattr(llm, "chat", fake)
    monkeypatch.setattr(dx, "chat", fake, raising=False)
    return fake


def _fahre(monkeypatch, buehne, kandidat: str, punkte: dict, preise: dict,
           protokoll: list, argv: list | None = None):
    mp = _lade("scripts/modellpruefung.py", "mp")
    ad = _lade("scripts/analyze_docs.py", "ad_test")
    monkeypatch.setattr(mp, "lade_analyse", lambda: ad)
    monkeypatch.setattr(mp, "pruefsatz",
                        lambda stand, n: {f"N{i}": [(f"Eignungskriterien{i}.pdf", TEXT)]
                                          for i in range(n)})
    monkeypatch.setattr(ad, "chat", _stelle_modell(monkeypatch, punkte, preise, protokoll))
    monkeypatch.setattr(sys, "argv",
                        argv or ["modellpruefung.py", "--kandidat", kandidat,
                                 "--budget-usd", "5.0"])
    assert mp.main() == 0
    return mp, json.loads((buehne / "pruefstand.json").read_text(encoding="utf-8"))


AMT = "google/gemini-2.5-flash"


def test_kandidat_besteht_und_wird_automatisch_freigegeben(buehne, monkeypatch):
    """Der ganze Weg: Grundlinie → Vorprüfung → Hauptprüfung → Urteil → Freigabe."""
    prot: list = []
    mp, stand = _fahre(monkeypatch, buehne, "billig/gut",
                       punkte={AMT: 3, "billig/gut": 3},
                       preise={AMT: 0.030, "billig/gut": 0.003},
                       protokoll=prot)

    # 5. Grundlinie wurde gemessen und festgehalten
    assert stand["grundlinie"]["modell"] == AMT
    assert len(stand["grundlinie"]["je_vorgang"]) == 4

    # 9. Urteil: gleichwertig, aber 90 % billiger → bestanden
    k = stand["kandidaten"]["billig/gut"]
    assert k["status"] == "bestanden", k.get("urteil")
    assert "billiger" in k["urteil"]

    # 10. Die automatische Freigabe lief wirklich — als echter Unterprozess
    frei = json.loads((buehne / "freigabe.json").read_text(encoding="utf-8"))
    assert "billig/gut" in frei
    assert "Prüfstand" in frei["billig/gut"]["grund"]

    # Kosten wurden je Vorgang zugeordnet, nicht in einen Topf geworfen
    assert all(v["kosten_usd"] > 0 for v in k["je_vorgang"].values())


def test_vorpruefungswerte_werden_uebernommen_und_nicht_neu_bezahlt(buehne, monkeypatch):
    """⚠ Die Vorprüfung fährt die ERSTEN Vorgänge des Prüfsatzes. Würden sie in der
    Hauptprüfung erneut gemessen, zahlten wir sie doppelt."""
    prot: list = []
    _fahre(monkeypatch, buehne, "billig/gut",
           punkte={AMT: 3, "billig/gut": 3}, preise={AMT: 0.03, "billig/gut": 0.003},
           protokoll=prot)
    # Je Vorgang zwei Aufrufe (Extraktion + Zusammenfassung), jeder Vorgang GENAU einmal.
    je_vorgang: dict = {}
    for modell, vorgang in prot:
        if modell == "billig/gut":
            je_vorgang[vorgang] = je_vorgang.get(vorgang, 0) + 1
    assert set(je_vorgang) == {"N0", "N1", "N2", "N3"}
    assert set(je_vorgang.values()) == {2}, f"kein Vorgang doppelt: {je_vorgang}"


def test_schlechter_kandidat_faellt_in_der_vorpruefung_und_kostet_nicht_die_hauptpruefung(
        buehne, monkeypatch):
    prot: list = []
    _, stand = _fahre(monkeypatch, buehne, "billig/schlecht",
                      punkte={AMT: 8, "billig/schlecht": 1},
                      preise={AMT: 0.03, "billig/schlecht": 0.001}, protokoll=prot)
    k = stand["kandidaten"]["billig/schlecht"]
    assert k["status"] == "durchgefallen" and "Hälfte" in k["urteil"]
    berührt = {v for m, v in prot if m == "billig/schlecht"}
    assert berührt == {"N0", "N1"}, "nur die Vorprüfung, nicht der ganze Satz"
    assert not (buehne / "freigabe.json").exists(), "ein Durchgefallener wird nie freigegeben"


# ── Der Wechsel selbst ───────────────────────────────────────────────────────────────

def test_waehlen_nimmt_das_billigste_freigegebene_und_hinterlegt_es(tmp_path, monkeypatch,
                                                                    capsys):
    """⚠ DER MOMENT DES WECHSELS. Vorher war er nur mit EINEM freigegebenen Modell erprobt —
    da kann nichts schiefgehen, weil es nichts zu wählen gibt.

    Geprüft wird zusätzlich, dass nach dem **Mischpreis** gewählt wird und nicht nach der
    Summe der beiden Preise: unsere Last ist ausgabelastig (gemessen 1,33:1), und ein
    Modell mit billiger Eingabe und teurer Ausgabe wäre sonst zu gut bewertet.
    """
    mw = _lade("scripts/modellwaechter.py", "mw_test")
    monkeypatch.setattr(mw, "WAHL", tmp_path / "wahl.json")
    monkeypatch.setattr(mw, "FREIGABE", tmp_path / "freigabe.json")
    (tmp_path / "freigabe.json").write_text(json.dumps({
        AMT: {"grund": "Titelverteidiger", "seit": "2026-08-18"},
        "billig/gut": {"grund": "Prüfstand", "seit": "2026-08-24"},
        "falle/teure-ausgabe": {"grund": "Prüfstand", "seit": "2026-08-24"},
    }), encoding="utf-8")

    tauglich = {"kontext": 1_000_000, "params": ["structured_outputs"], "auslauf": None}
    monkeypatch.setattr(mw.mk, "hole", lambda *a, **k: [])
    monkeypatch.setattr(mw.mk, "verdichte", lambda roh: {
        AMT: {"name": "A", "ein": 0.30, "aus": 2.50, **tauglich},
        "billig/gut": {"name": "B", "ein": 0.05, "aus": 0.40, **tauglich},
        # Billiger in der EINGABE, teurer in der Ausgabe — die Falle.
        "falle/teure-ausgabe": {"name": "C", "ein": 0.01, "aus": 3.00, **tauglich},
    })
    boeden = {AMT: (0.15, 1.25), "billig/gut": (0.05, 0.40),
              "falle/teure-ausgabe": (0.01, 3.00)}
    monkeypatch.setattr(mw.mk, "bodenpreis", lambda slug, **k: {
        "ein": boeden[slug][0], "aus": boeden[slug][1],
        "endpunkt": "fake", "haeuser": 1, "endpunkte": 1})
    monkeypatch.setattr(kostenbuch, "PFAD", tmp_path / "leer.jsonl")

    assert mw.waehle() == 0
    aus = capsys.readouterr()
    assert aus.out.strip() == "billig/gut", "auf stdout gehört NUR der Modellname"
    assert "Wechsel von" in aus.err

    hinterlegt = json.loads((tmp_path / "wahl.json").read_text(encoding="utf-8"))
    assert hinterlegt["modell"] == "billig/gut"
    assert hinterlegt["stand"], "ohne Datum verfällt die Wahl nie"


def test_waehlen_faellt_auf_den_amtierenden_zurueck_wenn_der_katalog_ausfaellt(
        tmp_path, monkeypatch, capsys):
    """Fail-open: ein Wächter, der den Lauf verhindert, ist teurer als jedes Modell."""
    mw = _lade("scripts/modellwaechter.py", "mw_test2")
    monkeypatch.setattr(mw, "WAHL", tmp_path / "wahl.json")
    monkeypatch.setattr(mw, "FREIGABE", tmp_path / "freigabe.json")
    monkeypatch.setattr(mw.mk, "hole",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("Netz weg")))
    monkeypatch.setattr(kostenbuch, "PFAD", tmp_path / "leer.jsonl")

    assert mw.waehle() == 0
    aus = capsys.readouterr()
    assert aus.out.strip() == mw.AMTIEREND
    assert "nicht erreichbar" in aus.err


def test_waehlen_ueberspringt_ein_freigegebenes_das_nicht_mehr_taugt(tmp_path, monkeypatch,
                                                                     capsys):
    """Ein Modell kann abgekündigt werden oder seinen Kontext verlieren, nachdem wir es
    freigegeben haben. Dann darf es nicht mehr gewählt werden — auch nicht als billigstes."""
    mw = _lade("scripts/modellwaechter.py", "mw_test3")
    monkeypatch.setattr(mw, "WAHL", tmp_path / "wahl.json")
    monkeypatch.setattr(mw, "FREIGABE", tmp_path / "freigabe.json")
    (tmp_path / "freigabe.json").write_text(json.dumps({
        AMT: {"grund": "x", "seit": "1"}, "geschrumpft/x": {"grund": "y", "seit": "2"},
    }), encoding="utf-8")
    monkeypatch.setattr(mw.mk, "hole", lambda *a, **k: [])
    monkeypatch.setattr(mw.mk, "verdichte", lambda roh: {
        AMT: {"name": "A", "ein": 0.30, "aus": 2.50, "kontext": 1_000_000,
              "params": ["structured_outputs"], "auslauf": None},
        "geschrumpft/x": {"name": "S", "ein": 0.001, "aus": 0.001, "kontext": 8192,
                          "params": ["structured_outputs"], "auslauf": None},
    })
    monkeypatch.setattr(mw.mk, "bodenpreis", lambda slug, **k: {
        "ein": 0.15, "aus": 1.25, "endpunkt": "f", "haeuser": 1, "endpunkte": 1})
    monkeypatch.setattr(kostenbuch, "PFAD", tmp_path / "leer.jsonl")

    assert mw.waehle() == 0
    aus = capsys.readouterr()
    assert aus.out.strip() == AMT, "das geschrumpfte Modell darf nicht gewählt werden"
    assert "erfüllt den Bedarf nicht mehr" in aus.err
