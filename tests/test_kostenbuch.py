"""Kostenbuch und Anbieterboden — dass mitgeschrieben wird, und dass es nichts kaputtmacht.

Die teuerste Sorte Fehler in diesem Bereich ist nicht die falsche Zahl, sondern die
**fehlende**: eine Buchhaltung, die still nichts tut, sieht genauso aus wie eine, die nichts
zu tun hat. Die Tests hier pruefen deshalb beides — dass die Zeile entsteht, und dass ein
Scheitern beim Schreiben den bezahlten Aufruf nicht mitreisst.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import kostenbuch  # noqa: E402


# ── Modellname und Weg ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("roh, modell, weg", [
    ("google/gemini-2.5-flash:floor", "google/gemini-2.5-flash", "floor"),
    ("google/gemini-2.5-flash:nitro", "google/gemini-2.5-flash", "nitro"),
    ("google/gemini-2.5-flash", "google/gemini-2.5-flash", ""),
    # `:free` ist ein ANDERES Angebot, keine Route — es darf nicht wegfallen.
    ("x/y:free", "x/y:free", ""),
    ("", "", ""),
    (None, "", ""),
])
def test_grundmodell_trennt_nur_routen(roh, modell, weg):
    assert kostenbuch.grundmodell(roh) == modell
    assert kostenbuch.weg(roh) == weg


# ── Schreiben ────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def buch(tmp_path, monkeypatch):
    monkeypatch.setattr(kostenbuch, "PFAD", tmp_path / "k.jsonl")
    monkeypatch.setattr(kostenbuch, "_GEMECKERT", False)
    return kostenbuch.PFAD


def test_notiert_und_trennt_weg_vom_modell(buch):
    kostenbuch.notiere(anbieter="openrouter", modell="google/gemini-2.5-flash:floor",
                       endpunkt="Google AI Studio", zweck="analyse", vorgang="N1",
                       eingabe_token=1200, ausgabe_token=300, kosten_usd=0.0031,
                       upstream_usd=0.0029, sekunden=4.2)
    z = json.loads(buch.read_text(encoding="utf-8").strip())
    assert z["modell"] == "google/gemini-2.5-flash" and z["weg"] == "floor"
    assert z["endpunkt"] == "Google AI Studio" and z["zweck"] == "analyse"
    assert z["kosten_usd"] == 0.0031 and z["sekunden"] == 4.2


def test_muell_wird_zu_none_statt_zur_ausnahme(buch):
    """⚠ Der Grund fuer `_zahl`: die Umwandlung lag erst ausserhalb des Schutzes."""
    kostenbuch.notiere(anbieter="or", modell="m", kosten_usd="kaputt",
                       eingabe_token=None, ausgabe_token=object(), sekunden="x")
    z = json.loads(buch.read_text(encoding="utf-8").strip())
    assert z["kosten_usd"] is None and z["eingabe_token"] == 0 and z["sekunden"] is None
    # Ein Zahlenwert als Zeichenkette ist kein Muell, sondern gueltig.
    kostenbuch.notiere(anbieter="or", modell="m", kosten_usd="0.0031")
    assert json.loads(buch.read_text(encoding="utf-8").splitlines()[1])["kosten_usd"] == 0.0031


def test_unschreibbares_buch_meckert_einmal_und_wirft_nie(tmp_path, monkeypatch, capsys):
    """Die Lehre aus dem Tagesbuch: ein `except: pass` machte den Tagesdeckel wirkungslos."""
    monkeypatch.setattr(kostenbuch, "PFAD", tmp_path / "gibt" / "es" / "nicht" / "k.jsonl")
    monkeypatch.setattr(kostenbuch, "_GEMECKERT", False)
    monkeypatch.setattr(kostenbuch.Path, "mkdir",
                        lambda *a, **k: (_ for _ in ()).throw(PermissionError("nein")))
    for _ in range(3):
        kostenbuch.notiere(anbieter="or", modell="m", kosten_usd=0.01)   # wirft nicht
    assert capsys.readouterr().err.count("Kostenbuch nicht schreibbar") == 1


def test_zusammenfassung_rechnet_je_weg(buch):
    for weg, kosten in (("floor", 0.0015), ("floor", 0.0015), ("", 0.0030)):
        kostenbuch.notiere(anbieter="or", modell="m" + (":" + weg if weg else ""),
                           endpunkt="E", eingabe_token=1_000_000, kosten_usd=kosten)
    z = kostenbuch.zusammenfassung(("modell", "weg"))
    assert z[("m", "floor")]["n"] == 2
    assert round(z[("m", "floor")]["kosten_usd"], 6) == 0.003
    assert round(z[("m", "floor")]["usd_je_mio_token"], 6) == 0.0015
    assert round(z[("m", "")]["usd_je_mio_token"], 6) == 0.003


def test_kaputte_zeile_sprengt_das_lesen_nicht(buch):
    kostenbuch.notiere(anbieter="or", modell="m", kosten_usd=0.01)
    with buch.open("a", encoding="utf-8") as f:
        f.write('{"abgeschnitten": ')          # Abbruch mitten im Schreiben
    assert len(list(kostenbuch.lies())) == 1


# ── Anbieterboden in llm.py ──────────────────────────────────────────────────────────

def test_boden_steht_im_modellnamen_nicht_im_provider_block(monkeypatch):
    """⚠ `sort:"price"` allein reicht nicht — nur `:floor` schaltet Flex frei."""
    monkeypatch.delenv("OR_MODEL", raising=False)
    monkeypatch.delenv("OR_MAX_PREIS", raising=False)
    from govisor import llm
    importlib.reload(llm)
    assert llm.DEFAULT_MODEL.endswith(":floor")
    assert llm._or_extra() == {}, "ohne gesetzte Grenzen kein provider-Block"


def test_preisdeckel_und_datenschutz_nur_wenn_gesetzt(monkeypatch):
    monkeypatch.setenv("OR_MAX_PREIS", "0.30/2.50")
    monkeypatch.setenv("OR_DATENSCHUTZ", "deny")
    from govisor import llm
    importlib.reload(llm)
    assert llm._or_extra() == {"provider": {"max_price": {"prompt": 0.30, "completion": 2.50},
                                            "data_collection": "deny"}}
    monkeypatch.setenv("OR_MAX_PREIS", "quatsch")
    importlib.reload(llm)
    assert "max_price" not in llm._or_extra().get("provider", {})
    monkeypatch.delenv("OR_MAX_PREIS"); monkeypatch.delenv("OR_DATENSCHUTZ")
    importlib.reload(llm)


def test_chat_bucht_und_haelt_das_modell_ohne_endung_fest(tmp_path, monkeypatch):
    from govisor import llm
    importlib.reload(llm)
    monkeypatch.setattr(kostenbuch, "PFAD", tmp_path / "k.jsonl")
    monkeypatch.setattr(llm, "_geldwache", lambda: None)
    monkeypatch.setattr(llm, "_anbieter", lambda: [
        {"name": "openrouter", "url": "http://x", "keys": ["k"],
         "model": "google/gemini-2.5-flash:floor", "extra": {}}])

    gesehen = {}

    class Antwort:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"provider": "Google AI Studio",
                    "choices": [{"message": {"content": "hallo"}}],
                    "usage": {"prompt_tokens": 1200, "completion_tokens": 300,
                              "cost": 0.00042,
                              "cost_details": {"upstream_inference_cost": 0.00040},
                              "prompt_tokens_details": {"cached_tokens": 100}}}

    def fake_post(url, headers=None, json=None, timeout=None):
        gesehen.update(json)
        return Antwort()

    monkeypatch.setattr(llm.requests, "post", fake_post)

    with llm.kontext(zweck="versuch", vorgang="N42"):
        assert llm.chat([{"role": "user", "content": "hi"}]) == "hallo"

    assert gesehen["model"] == "google/gemini-2.5-flash:floor", "der Boden muss rausgehen"
    # ... aber NICHT in der Historie landen, sonst zerfaellt sie in zwei Modelle:
    assert llm.letzter_anbieter() == ("openrouter", "google/gemini-2.5-flash")
    assert llm.letzter_verbrauch()["endpunkt"] == "Google AI Studio"

    z = json.loads((tmp_path / "k.jsonl").read_text(encoding="utf-8").strip())
    assert (z["modell"], z["weg"]) == ("google/gemini-2.5-flash", "floor")
    assert z["endpunkt"] == "Google AI Studio" and z["kosten_usd"] == 0.00042
    assert z["upstream_usd"] == 0.0004 and z["cache_token"] == 100
    assert (z["zweck"], z["vorgang"]) == ("versuch", "N42")
    assert z["sekunden"] is not None


def test_kontext_legt_den_vorherigen_stand_zurueck():
    from govisor import llm
    with llm.kontext(zweck="aussen", vorgang="A"):
        with llm.kontext(zweck="innen"):
            assert llm._KONTEXT.zweck == "innen"
            assert llm._KONTEXT.vorgang == "A", "innen erbt, was es nicht selbst setzt"
        assert llm._KONTEXT.zweck == "aussen", "aussen darf seinen Zweck nicht verlieren"


# ── Gepaarter Modellvergleich (scripts/llm_bench.py) ─────────────────────────────────

def _bench():
    spec = importlib.util.spec_from_file_location("bench", ROOT / "scripts/llm_bench.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize("g, v, erwartet", [
    (0, 0, 1.0),        # nichts gemessen
    (8, 0, 0.0078),     # 2 · C(8,0) / 2^8
    (6, 2, 0.2891),     # sieht deutlich aus, ist es nicht
    (10, 1, 0.0117),
    (3, 1, 0.625),      # vier Vorgaenge beweisen nichts
])
def test_vorzeichentest(g, v, erwartet):
    assert round(_bench().vorzeichentest(g, v), 4) == erwartet
    assert _bench().vorzeichentest(g, v) == _bench().vorzeichentest(v, g), "symmetrisch"


def test_kosten_seit_zaehlt_nur_den_eigenen_lauf(tmp_path, monkeypatch):
    """⚠ Der Analyse-Arbeiter schreibt PARALLEL ins selbe Buch — fremde Zeilen dürfen
    dem Vergleich nicht zugerechnet werden, und alte Zeilen davor auch nicht."""
    from govisor import pruefstand as b
    buch = tmp_path / "k.jsonl"
    monkeypatch.setattr(kostenbuch, "PFAD", buch)

    kostenbuch.notiere(anbieter="or", modell="m:floor", vorgang="N1", zweck="bench",
                       kosten_usd=9.99)                       # VOR der Marke → zaehlt nicht
    marke = b._buchstand(kostenbuch)
    kostenbuch.notiere(anbieter="or", modell="m:floor", vorgang="N1", zweck="bench",
                       kosten_usd=0.010)
    kostenbuch.notiere(anbieter="or", modell="m:floor", vorgang="N1", zweck="bench",
                       kosten_usd=0.005)
    kostenbuch.notiere(anbieter="or", modell="m:floor", vorgang="N1", zweck="analyse",
                       kosten_usd=7.00)                       # fremder Zweck
    kostenbuch.notiere(anbieter="or", modell="m:floor", vorgang="N2", zweck="bench",
                       kosten_usd=7.00)                       # anderer Vorgang
    kostenbuch.notiere(anbieter="or", modell="andres", vorgang="N1", zweck="bench",
                       kosten_usd=7.00)                       # anderes Modell
    kostenbuch.notiere(anbieter="or", modell="m:floor", vorgang="N1", zweck="bench",
                       kosten_usd=None)                       # Preis fehlt → gezaehlt

    summe, fehlt = b._kosten_seit(kostenbuch, marke, "N1", "m:floor", "bench")
    assert round(summe, 6) == 0.015 and fehlt == 1


def test_zwischenstand_haelt_und_wird_atomar_ersetzt(tmp_path, monkeypatch):
    b = _bench()
    monkeypatch.setattr(b, "STAND", tmp_path / "mv.json")
    b.sichere({"vorgaenge": ["N1"], "ergebnis": {"m": {"N1": {"punkte": 3}}}})
    assert b.lade_stand()["ergebnis"]["m"]["N1"]["punkte"] == 3
    assert not (tmp_path / "mv.json.teil").exists(), "Teildatei muss verschwinden"


def test_kaputter_zwischenstand_beginnt_neu_statt_zu_sterben(tmp_path, monkeypatch, capsys):
    b = _bench()
    monkeypatch.setattr(b, "STAND", tmp_path / "mv.json")
    (tmp_path / "mv.json").write_text("{kaputt", encoding="utf-8")
    assert b.lade_stand() == {"vorgaenge": [], "ergebnis": {}}
    assert "unlesbar" in capsys.readouterr().err


def test_bericht_paart_nur_gemeinsame_vorgaenge(capsys):
    """Ein Vorgang, den nur EIN Modell geschafft hat, darf den Vergleich nicht verzerren."""
    b = _bench()
    erg = {
        b.AMTIEREND: {f"N{i}": {"punkte": 10, "verworfen": 1, "kosten_usd": 0.01,
                                "sekunden": 5.0} for i in range(6)},
        "kandidat/x": {f"N{i}": {"punkte": 20, "verworfen": 1, "kosten_usd": 0.02,
                                 "sekunden": 5.0} for i in range(5)},
    }
    erg["kandidat/x"]["N5"] = {"fehler": "TimeoutError"}      # ohne Punkte → raus
    b.bericht({"vorgaenge": [], "ergebnis": erg})
    aus = capsys.readouterr().out
    assert "5:0 von 5" in aus, "nur die fünf gemeinsamen Vorgänge zählen"
    assert "p=0.062" in aus, "fünf Siege reichen nicht für 5 % — ehrlich bleiben"


def test_bericht_zeigt_usd_je_punkt(capsys):
    b = _bench()
    b.bericht({"vorgaenge": [], "ergebnis": {b.AMTIEREND: {
        "N1": {"punkte": 50, "verworfen": 0, "kosten_usd": 0.05, "sekunden": 5.0}}}})
    assert "0.00100" in capsys.readouterr().out       # 0,05 $ / 50 Punkte


def test_leere_antwort_wird_gebucht_denn_sie_kostet_geld(tmp_path, monkeypatch):
    """⚠ Ein 200 ohne verwertbaren Inhalt wird von OpenRouter trotzdem abgerechnet.

    Die erste Fassung buchte hier nicht und ging zum nächsten Key weiter. Ergebnis: das
    Buch meldete weniger, als das Konto verlor — und eine Lücke im Buch sieht aus wie
    Sparsamkeit.
    """
    from govisor import llm
    importlib.reload(llm)
    monkeypatch.setattr(kostenbuch, "PFAD", tmp_path / "k.jsonl")
    monkeypatch.setattr(llm, "_geldwache", lambda: None)
    monkeypatch.setattr(llm, "_anbieter", lambda: [
        {"name": "openrouter", "url": "http://x", "keys": ["k1"], "model": "a/b", "extra": {}}])

    class Leer:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"provider": "Google AI Studio",
                    "choices": [{"message": {"content": "   "}}],
                    "usage": {"prompt_tokens": 900, "completion_tokens": 0, "cost": 0.00013}}

    monkeypatch.setattr(llm.requests, "post",
                        lambda *a, **k: Leer())
    with pytest.raises(llm.LLMFehler if hasattr(llm, "LLMFehler") else RuntimeError):
        llm.chat([{"role": "user", "content": "hi"}])

    zeilen = [json.loads(z) for z in
              (tmp_path / "k.jsonl").read_text(encoding="utf-8").splitlines()]
    assert zeilen, "die leere Antwort muss im Buch stehen"
    assert zeilen[0]["leer"] is True
    assert zeilen[0]["kosten_usd"] == 0.00013


@pytest.mark.parametrize("roh, erwartet", [
    ("google/gemini-2.5-flash", "google/gemini-2.5-flash:floor"),
    ("upstage/solar-pro4", "upstage/solar-pro4:floor"),
    # ⚠ Bereits eine Variante — es darf keine zweite drangehaengt werden.
    ("openai/gpt-5-nano:batch", "openai/gpt-5-nano:batch"),
    ("x/y:nitro", "x/y:nitro"),
    ("x/y:floor", "x/y:floor"),
])
def test_mit_boden_haengt_keine_zweite_variante_an(roh, erwartet, monkeypatch):
    from govisor import llm
    monkeypatch.setattr(llm, "OR_BODEN", "an")
    assert llm.mit_boden(roh) == erwartet
