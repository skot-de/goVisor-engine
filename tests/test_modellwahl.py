"""Modellkatalog, Prüfstand und die Wahl — die Kette vom Marktblick bis zum Wechsel.

Der teuerste Fehler hier wäre ein stiller Wechsel auf ein schlechteres Modell. Die Tests
prüfen deshalb vor allem die **Riegel**: dass ein schlampiges Modell fällt, obwohl es
billig ist; dass ein durchgefallenes nicht jede Nacht erneut Geld kostet; und dass die
Messschleife bei leerem Topf aufhört, ohne das Gemessene zu verlieren.
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import kostenbuch, modellkatalog as mk, pruefstand as ps  # noqa: E402


# ── Katalog ──────────────────────────────────────────────────────────────────────────

def test_verdichte_rechnet_auf_millionen_um():
    roh = [{"id": "a/b", "name": "A B", "context_length": 262144,
            "pricing": {"prompt": "0.0000003", "completion": "0.0000025"},
            "supported_parameters": ["structured_outputs", "tools"]}]
    st = mk.verdichte(roh)
    assert st["a/b"]["ein"] == pytest.approx(0.30)
    assert st["a/b"]["aus"] == pytest.approx(2.50)


def test_verdichte_uebersteht_muell():
    st = mk.verdichte([{"id": "a/b", "pricing": {"prompt": None, "completion": "x"}},
                       {"kein_id": 1}])
    assert st["a/b"]["ein"] == 0.0 and len(st) == 1


@pytest.mark.parametrize("kontext, params, erwartet", [
    (1_000_000, ["structured_outputs"], True),
    (200_000, ["structured_outputs"], True),
    (199_999, ["structured_outputs"], False),          # Kontext reicht nicht
    (1_000_000, ["tools"], False),                     # keine strukturierte Ausgabe
])
def test_taugt_prueft_kontext_und_schema(kontext, params, erwartet):
    assert mk.taugt({"kontext": kontext, "params": params}) is erwartet


def _m(ein=1.0, aus=2.0, kontext=1_000_000, params=("structured_outputs",), **rest):
    return {"name": "M", "ein": ein, "aus": aus, "kontext": kontext,
            "params": list(params), "auslauf": None, **rest}


def test_erster_lauf_meldet_nichts():
    assert mk.vergleiche(None, {"a/b": _m()}) == []


def test_vergleich_findet_neu_weg_und_preise():
    alt = {"bleibt": _m(ein=1.0), "faellt_weg": _m(), "teurer": _m(ein=1.0)}
    neu = {"bleibt": _m(ein=0.5), "teurer": _m(ein=2.0), "ganz_neu": _m()}
    arten = {(b["art"], b["modell"]) for b in mk.vergleiche(alt, neu)}
    assert ("preis_runter", "bleibt") in arten
    assert ("preis_rauf", "teurer") in arten
    assert ("weg", "faellt_weg") in arten
    assert ("neu", "ganz_neu") in arten


def test_kleine_preisaenderung_ist_kein_befund_ausser_bei_beobachteten():
    alt, neu = {"x/y": _m(ein=1.00)}, {"x/y": _m(ein=1.05)}       # +5 %
    assert mk.vergleiche(alt, neu, schwelle=0.20) == []
    b = mk.vergleiche(alt, neu, schwelle=0.20, beobachtet={"x/y"})
    assert b and b[0]["art"] == "preis_rauf", "unser eigenes Modell: jede Änderung zählt"


def test_untaugliche_modelle_erzeugen_keinen_laerm():
    """⚠ Der Katalog verliert ständig Randmodelle. Jedes zu melden heißt, dass niemand
    mehr hinsieht."""
    alt = {"klein": _m(kontext=1000)}
    assert mk.vergleiche(alt, {}) == []
    assert mk.vergleiche(alt, {}, beobachtet={"klein"})[0]["art"] == "weg"


def test_abkuendigung_wird_gemeldet():
    b = mk.vergleiche({"x/y": _m()}, {"x/y": _m(auslauf="2026-12-31")})
    assert b[0]["art"] == "auslauf" and b[0]["auslauf"] == "2026-12-31"


def test_guenstiger_als_verlangt_BEIDE_preise_unter_der_latte():
    stand = {"beides": _m(ein=0.1, aus=1.0), "nur_eingabe": _m(ein=0.1, aus=9.0),
             "untauglich": _m(ein=0.01, aus=0.01, kontext=1000)}
    treffer = [m for m, _ in mk.guenstiger_als(stand, 0.15, 1.25)]
    assert treffer == ["beides"]


# ── Das Urteil ───────────────────────────────────────────────────────────────────────

def _reihe(punkte, verworfen, preis, n=12, sek=5.0):
    return {f"N{i}": {"punkte": punkte, "verworfen": verworfen,
                      "kosten_usd": preis, "sekunden": sek} for i in range(n)}


AMT = _reihe(50, 6, 0.030)


def test_schlampig_faellt_durch_auch_wenn_spottbillig():
    """Der Verwerfungsriegel steht VOR allem. Ein Modell, das flüssig behauptet und selten
    belegt, sieht in jeder Punktzahl gut aus und ist trotzdem unbrauchbar."""
    u = ps.entscheide(_reihe(50, 20, 0.001), AMT)
    assert u["status"] == "durchgefallen" and not u["wechseln"]
    assert "behauptet mehr" in u["grund"]


def test_besser_gewinnt_auch_wenn_teurer():
    """Sven: Qualität steht oben, danach kommt direkt der Preis."""
    u = ps.entscheide(_reihe(62, 6, 0.240), AMT)
    assert u["status"] == "bestanden" and u["wechseln"]
    assert "Qualität geht vor" in u["grund"]


def test_gleichwertig_und_deutlich_billiger_gewinnt():
    u = ps.entscheide(_reihe(50, 6, 0.006), AMT)
    assert u["wechseln"] and "billiger" in u["grund"]


def test_gleichwertig_aber_kaum_billiger_wechselt_nicht():
    u = ps.entscheide(_reihe(50, 6, 0.0285), AMT)        # 5 %
    assert u["status"] == "gleichwertig" and not u["wechseln"]


def test_signifikant_schlechter_faellt_durch():
    assert ps.entscheide(_reihe(38, 5, 0.004), AMT)["status"] == "durchgefallen"


def test_zu_wenig_vorgaenge_ergibt_kein_urteil():
    u = ps.entscheide(_reihe(80, 1, 0.001, n=4), _reihe(50, 6, 0.030, n=4))
    assert u["status"] == "neu" and not u["wechseln"]
    assert "gepaarte Vorgänge" in u["grund"]


def test_geschwindigkeit_wird_gemessen_aber_entscheidet_nicht():
    langsam = ps.entscheide(_reihe(50, 6, 0.006, sek=60.0), AMT)
    assert langsam["wechseln"], "dreimal langsamer, trotzdem bestanden"
    assert langsam["sek_kandidat"] == 60.0 and langsam["sek_amtierend"] == 5.0


def test_vorpruefung_sortiert_nur_nieten_aus():
    ok, _ = ps.vorpruefung_bestanden(_reihe(45, 7, 0.02, n=3), _reihe(50, 6, 0.03, n=3))
    assert ok, "leicht schwächer darf weiter — bei drei Vorgängen entscheidet man nichts Feines"
    schlecht, warum = ps.vorpruefung_bestanden(_reihe(10, 6, 0.02, n=3), _reihe(50, 6, 0.03, n=3))
    assert not schlecht and "Hälfte" in warum
    leer, warum2 = ps.vorpruefung_bestanden({"N0": {"fehler": "Timeout"}}, _reihe(50, 6, 0.03, n=3))
    assert not leer and "keine auswertbaren" in warum2


# ── Warteschlange ────────────────────────────────────────────────────────────────────

def test_durchgefallene_kosten_nicht_jede_nacht_erneut():
    stand = {"kandidaten": {}, "grundlinie": {}}
    assert ps.einreihen(stand, "x/y", preis=0.05, grund="neu")
    stand["kandidaten"]["x/y"]["status"] = "durchgefallen"
    assert not ps.einreihen(stand, "x/y", preis=0.05, grund="nochmal")
    # ... erst ein materieller Preisrutsch macht ihn wieder interessant
    assert ps.einreihen(stand, "x/y", preis=0.02, grund="Preis fiel")
    assert stand["kandidaten"]["x/y"]["status"] == "neu"


def test_bestandene_kommen_nicht_zurueck_in_die_schlange():
    stand = {"kandidaten": {"x/y": {"status": "bestanden", "preis": 0.05}}, "grundlinie": {}}
    assert not ps.einreihen(stand, "x/y", preis=0.01, grund="noch billiger")


def test_naechste_nimmt_die_billigsten_und_deckelt():
    stand = {"kandidaten": {
        "teuer": {"status": "neu", "preis": 0.9},
        "billig": {"status": "neu", "preis": 0.1},
        "mittel": {"status": "vorpruefung_bestanden", "preis": 0.5},
        "fertig": {"status": "bestanden", "preis": 0.01}}, "grundlinie": {}}
    assert ps.naechste(stand, 2) == ["billig", "mittel"]


def test_grundlinie_veraltet():
    heute = date.today()
    frisch = {"grundlinie": {"stand": heute.isoformat(), "je_vorgang": {"N": {}}}}
    alt = {"grundlinie": {"stand": (heute - timedelta(days=99)).isoformat(),
                          "je_vorgang": {"N": {}}}}
    assert ps.grundlinie_frisch(frisch)
    assert not ps.grundlinie_frisch(alt)
    assert not ps.grundlinie_frisch({"grundlinie": {}})


# ── Der Messkern ─────────────────────────────────────────────────────────────────────

class _Nichts:
    """Kontextverwalter, der nichts tut — fuer `kontext` und `frist` in den Attrappen."""

    def __init__(self, *a, **kw):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeLLM:
    BudgetErschoepft = type("BudgetErschoepft", (RuntimeError,), {})

    @staticmethod
    def mit_boden(m):
        return m + ":floor"

    kontext = _Nichts
    frist = _Nichts


class _FakeAnalyse:
    MODEL = "urspruenglich"

    def __init__(self, punkte=7, wirft=None):
        self.punkte, self.wirft, self.gesehen = punkte, wirft, []

    def structured_for_notice(self, nid):
        return {}

    def analyze_notice(self, rows, structured=None, notice_id=None):
        self.gesehen.append(notice_id)
        if self.wirft:
            raise self.wirft
        return {"checklist": [{"marking": "Zitat"} for _ in range(self.punkte)],
                "rejected_items": 1}


def test_messkern_misst_sichert_und_stellt_das_modell_zurueck(tmp_path, monkeypatch):
    monkeypatch.setattr(kostenbuch, "PFAD", tmp_path / "k.jsonl")
    ad = _FakeAnalyse()
    gesichert = []
    erg, grund = ps.messe_reihe(
        analyse=ad, llm=_FakeLLM, kostenbuch=kostenbuch, modell="a/b",
        vorgaenge={"N1": [], "N2": []}, zweck="test",
        nach_vorgang=lambda e: gesichert.append(len(e)))
    assert grund is None and len(erg) == 2 and erg["N1"]["punkte"] == 7
    assert gesichert == [1, 2], "nach JEDEM Vorgang gesichert, nicht erst am Ende"
    assert ad.MODEL == "urspruenglich", "das Modell muss zurückgestellt werden"


def test_messkern_ueberspringt_schon_gemessene():
    ad = _FakeAnalyse()
    erg, _ = ps.messe_reihe(analyse=ad, llm=_FakeLLM, kostenbuch=kostenbuch, modell="a/b",
                            vorgaenge={"N1": [], "N2": []}, zweck="test",
                            vorhanden={"N1": {"punkte": 99, "kosten_usd": 0}})
    assert ad.gesehen == ["N2"] and erg["N1"]["punkte"] == 99


def test_messkern_haelt_bei_leerem_topf_an_ohne_gemessenes_zu_verlieren(tmp_path, monkeypatch):
    monkeypatch.setattr(kostenbuch, "PFAD", tmp_path / "k.jsonl")
    erg, grund = ps.messe_reihe(
        analyse=_FakeAnalyse(), llm=_FakeLLM, kostenbuch=kostenbuch, modell="a/b",
        vorgaenge={"N1": [], "N2": []}, zweck="test", budget=0.0,
        vorhanden={"N0": {"punkte": 5, "kosten_usd": 0.0}})
    assert grund and "Testbudget" in grund
    assert erg == {"N0": {"punkte": 5, "kosten_usd": 0.0}}


def test_messkern_haelt_bei_der_geldwache_an():
    _, grund = ps.messe_reihe(
        analyse=_FakeAnalyse(wirft=_FakeLLM.BudgetErschoepft("Reserve")),
        llm=_FakeLLM, kostenbuch=kostenbuch, modell="a/b",
        vorgaenge={"N1": []}, zweck="test")
    assert grund and "Geldwache" in grund


def test_messkern_ueberlebt_einen_kaputten_vorgang():
    erg, grund = ps.messe_reihe(
        analyse=_FakeAnalyse(wirft=ValueError("kaputt")), llm=_FakeLLM,
        kostenbuch=kostenbuch, modell="a/b", vorgaenge={"N1": [], "N2": []}, zweck="test")
    assert grund is None and erg["N1"]["fehler"] == "ValueError"
    assert "kaputt" in erg["N1"]["grund"], "der Grund gehört mit ins Protokoll"
    assert ps.kennzahlen(erg)["n"] == 0, "Fehler zählen nicht als Messwert"


def test_kosten_seit_ignoriert_fremden_zweck(tmp_path, monkeypatch):
    monkeypatch.setattr(kostenbuch, "PFAD", tmp_path / "k.jsonl")
    marke = ps._buchstand(kostenbuch)
    kostenbuch.notiere(anbieter="or", modell="a/b:floor", vorgang="N1", zweck="test",
                       kosten_usd=0.01)
    kostenbuch.notiere(anbieter="or", modell="a/b:floor", vorgang="N1", zweck="analyse",
                       kosten_usd=5.00)
    summe, _ = ps._kosten_seit(kostenbuch, marke, "N1", "a/b:floor", "test")
    assert summe == pytest.approx(0.01)


# ── Formatriegel: das Modell kann gut sein und trotzdem unlesbar antworten ───────────

def _reihe_fmt(punkte, verworfen, preis, aufrufe=6, fehler=0, n=12):
    return {f"N{i}": {"punkte": punkte, "verworfen": verworfen, "kosten_usd": preis,
                      "sekunden": 5.0, "llm_aufrufe": aufrufe, "formatfehler": fehler}
            for i in range(n)}


AMT_FMT = _reihe_fmt(50, 6, 0.030)


def test_unlesbare_antworten_sind_KEIN_qualitaetsurteil():
    """⚠ Die schlimmste Verwechslung dieses Moduls, wenn sie fehlte.

    `docextract.extract` gibt bei unparsbarer Antwort stillschweigend
    `{"items": [], "parse_error": True}` zurück. Von oben sieht das aus wie
    „0 Punkte bei 0 verworfenen Aussagen" — also nach perfekter Genauigkeit ohne Ertrag.
    Ohne den Formatriegel fiele ein Modell, das unsere Aufgabe beherrscht und nur sein
    JSON in Prosa wickelt, über Regel 2 durch und würde NIE WIEDER geprüft.
    """
    murks = _reihe_fmt(0, 0, 0.002, aufrufe=6, fehler=6)
    u = ps.entscheide(murks, AMT_FMT)
    assert u["status"] == "formatproblem", "nicht 'durchgefallen' — das wäre ein Urteil"
    assert not u["wechseln"] and "nicht lesbar" in u["grund"]
    assert "response_format" in u["grund"], "die Abhilfe gehört in den Befund"


def test_vereinzelte_formatfehler_bleiben_ein_qualitaetsurteil():
    """Unter der Toleranz fängt die eingebaute Wiederholung in docextract es ab."""
    u = ps.entscheide(_reihe_fmt(50, 6, 0.006, aufrufe=20, fehler=1), AMT_FMT)   # 5 %
    assert u["status"] == "bestanden" and u["wechseln"]


def test_formatproblem_faellt_schon_in_der_vorpruefung_auf():
    ok, warum = ps.vorpruefung_bestanden(
        _reihe_fmt(0, 0, 0.002, aufrufe=6, fehler=6, n=3), _reihe_fmt(50, 6, 0.03, n=3))
    assert not ok and "Formatproblem" in warum


def test_formatproblem_wird_nicht_jede_nacht_wiederholt():
    """Es würde identisch scheitern und dabei Geld kosten. Wiedervorlage ist Handarbeit."""
    stand = {"kandidaten": {"x/y": {"status": "formatproblem", "preis": 0.01}},
             "grundlinie": {}}
    assert not ps.einreihen(stand, "x/y", preis=0.01, grund="nochmal")
    assert ps.naechste(stand, 5) == []


def test_formatquote_ohne_aufrufe_ist_null_und_wirft_nicht():
    assert ps.kennzahlen(_reihe_fmt(5, 1, 0.01, aufrufe=0))["formatquote"] == 0.0
    assert ps.kennzahlen({"N0": {"fehler": "Timeout"}}) == {"n": 0}


# ── Zeitgrenze: langsam ist nicht dasselbe wie schlecht ──────────────────────────────

def test_zeitgrenze_bricht_ab_ohne_ein_qualitaetsurteil_zu_faellen(monkeypatch):
    """⚠ Gemessen am 2026-08-24: `nex-agi/nex-n2-mini` brauchte 760 s für EINEN Aufruf
    (Amtierender: 2,6 s im Median) und erzeugte dabei 65.536 Ausgabe-Token — die
    Obergrenze des Endpunkts. Es hörte schlicht nicht auf zu schreiben.

    Der `timeout` in `requests` hilft dagegen nicht: er misst die Pause zwischen Bytes,
    nicht die Gesamtdauer. Der Aufruf lief mit `timeout=120` durch.
    """
    import time as _t

    class Langsam:
        MODEL = "x"

        def structured_for_notice(self, nid):
            return {}

        def analyze_notice(self, rows, structured=None, notice_id=None):
            _t.sleep(0.01)
            return {"checklist": [], "rejected_items": 0}

    class FakeLLM:
        BudgetErschoepft = type("B", (RuntimeError,), {})
        mit_boden = staticmethod(lambda m: m)
        kontext = _Nichts
        frist = _Nichts

    # ⚠ Nicht 0 setzen: eine Grenze von 0 gilt als „keine Grenze" (`if grenze and …`).
    monkeypatch.setattr(ps, "ZEIT_MINDEST", 0.001)
    monkeypatch.setattr(ps, "ZEIT_FAKTOR", 0.001)    # jede echte Dauer reisst die Grenze
    erg, grund = ps.messe_reihe(
        analyse=Langsam(), llm=FakeLLM, kostenbuch=kostenbuch, modell="lahm/x",
        vorgaenge={"N1": [], "N2": []}, zweck="test",
        vergleich={"N1": {"sekunden": 1.0}, "N2": {"sekunden": 1.0}})
    assert grund and grund.startswith("zu langsam")
    assert "Kein Qualitätsurteil" in grund
    assert set(erg) == {"N1"}, "nach dem ersten Verstoss wird abgebrochen"
    assert "sekunden" in erg["N1"], "der Messwert bleibt erhalten"


def test_ohne_vergleichsmass_gibt_es_keine_zeitgrenze():
    """Die Grundlinie ist der Maßstab. Fehlt sie, wird nicht geraten."""
    assert ps.zeitgrenze(None, "N1") is None
    assert ps.zeitgrenze({"N1": {}}, "N1") is None
    assert ps.zeitgrenze({"N1": {"sekunden": 100.0}}, "N1") == max(ps.ZEIT_MINDEST, 400.0)


def test_zu_langsam_kommt_nicht_von_selbst_zurueck_in_die_schlange():
    stand = {"kandidaten": {"lahm/x": {"status": "zu_langsam", "preis": 0.01}},
             "grundlinie": {}}
    assert not ps.einreihen(stand, "lahm/x", preis=0.01, grund="nochmal")
    assert ps.naechste(stand, 5) == []


def test_fristabbrueche_ergeben_kein_qualitaetsurteil():
    """⚠ Der reale Fall vom 2026-08-24, und der Grund für den Fristriegel.

    Bei `nex-agi/nex-n2-mini` rissen zwei von drei Vorgängen die Zeitfrist; der dritte
    ergab null Punkte — dort hatte aber auch der Amtierende null. Es lag also **kein
    einziger** verwertbarer Vergleich vor, und das Urteil lautete trotzdem
    „durchgefallen: findet nur 0,0 statt 25,0 Punkte". Ein Qualitätsurteil über Antworten,
    die nie angekommen sind.
    """
    amt = {f"N{i}": {"punkte": 25, "verworfen": 3, "kosten_usd": 0.03, "sekunden": 5.0}
           for i in range(3)}
    kand = {"N0": {"fehler": "AllKeysExhausted", "grund": "Frist von 240 s überschritten"},
            "N1": {"punkte": 0, "verworfen": 0, "kosten_usd": 0.0005, "sekunden": 19.9},
            "N2": {"fehler": "AllKeysExhausted", "grund": "Frist von 240 s überschritten"}}
    ok, warum = ps.vorpruefung_bestanden(kand, amt)
    assert not ok and "Zeitfrist" in warum and "kein Qualitätsurteil" in warum

    voll = dict(kand)
    voll.update({f"N{i}": {"fehler": "AllKeysExhausted",
                           "grund": "Frist von 240 s überschritten"} for i in range(3, 12)})
    amt_voll = {f"N{i}": {"punkte": 25, "verworfen": 3, "kosten_usd": 0.03, "sekunden": 5.0}
                for i in range(12)}
    u = ps.entscheide(voll, amt_voll)
    assert u["status"] == "zu_langsam" and not u["wechseln"]
    assert "kamen nie an" in u["grund"]


def test_ein_einzelner_fristfall_kippt_das_urteil_nicht():
    """Unter der Hälfte bleibt es ein Qualitätsurteil — sonst rettet ein Ausreißer jedes
    schlechte Modell vor dem Durchfallen."""
    amt = {f"N{i}": {"punkte": 25, "verworfen": 3, "kosten_usd": 0.03, "sekunden": 5.0}
           for i in range(12)}
    kand = {f"N{i}": {"punkte": 2, "verworfen": 1, "kosten_usd": 0.001, "sekunden": 4.0}
            for i in range(12)}
    kand["N0"] = {"fehler": "AllKeysExhausted", "grund": "Frist von 240 s überschritten"}
    u = ps.entscheide(kand, amt)
    assert u["status"] == "durchgefallen", u["grund"]


def test_fristquote_zaehlt_nur_echte_fristfaelle():
    assert ps.fristquote({}) == (0.0, 0, 0)
    gemischt = {"a": {"fehler": "X", "grund": "HTTP 500"},
                "b": {"fehler": "Y", "grund": "Frist von 240 s überschritten"},
                "c": {"punkte": 5}}
    assert ps.fristquote(gemischt) == (1 / 3, 1, 3)
