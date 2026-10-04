"""Antwortvorschlaege aus der Bausteinbibliothek.

⚠ **Diese Suite muss die Belegpruefung ANSCHLAGEN sehen, nicht nur ihre Existenz pruefen.** Ein
Waechter, der nie ausgeloest wurde, ist kein Nachweis — dieser Fehler ist im Projekt schon
mehrfach vorgekommen (s. Auto-Memory `waechter-messen-prosa-statt-code`). Deshalb enthaelt sie je
einen Fall mit erfundenem und mit verwechseltem Zitat und erwartet dort ausdruecklich `unbelegt`.
"""
import json

import pytest

from govisor import antwortvorschlag as av

BAUSTEINE = [
    {"id": "b1", "theme": "zertifikate_qm",
     "content": "Unser Qualitaetsmanagement ist nach ISO 9001 zertifiziert, geprueft im Jahr 2026."},
    {"id": "b2", "theme": "referenzen",
     "content": "Wir haben drei vergleichbare Projekte fuer kommunale Netzbetreiber umgesetzt, "
                "jeweils mit mehr als 400 angebundenen Lieferanten."},
]


# ── Fragen aus dem Bogen ─────────────────────────────────────────────────────────────────────

def test_erkennt_aufforderung_und_echte_frage():
    bogen = ("1. Bitte beschreiben Sie Ihr Qualitaetsmanagementsystem.\n"
             "2.3 Welche Referenzen koennen Sie vorweisen?\n")
    fragen = av.fragen_aus_text(bogen)
    assert len(fragen) == 2
    assert fragen[0]["nr"] == "1"
    assert fragen[0]["frage"].startswith("Bitte beschreiben")


def test_gepunktete_nummer_ohne_punkt_wird_abgetrennt():
    """Regression: `2.3 Welche …` liess die Nummer im Fragetext stehen."""
    fragen = av.fragen_aus_text("2.3 Welche Referenzen koennen Sie vorweisen?\n")
    assert fragen[0]["nr"] == "2.3"
    assert fragen[0]["frage"] == "Welche Referenzen koennen Sie vorweisen?"


def test_blanke_zahl_ohne_satzzeichen_ist_keine_nummer():
    """`3 Monate Frist …` darf nicht als Frage 3 gelesen werden."""
    fragen = av.fragen_aus_text("3 Monate Frist, bitte beschreiben Sie den Ablauf.\n")
    assert fragen and fragen[0]["nr"] is None
    assert fragen[0]["frage"].startswith("3 Monate")


def test_ignoriert_spaltenkoepfe_und_absaetze():
    text = ("Nr.\nFrage\n"
            "Dies ist ein Absatz ohne Aufforderung und ohne Fragezeichen.\n")
    assert av.fragen_aus_text(text) == []


# ── Zuordnung ────────────────────────────────────────────────────────────────────────────────

def test_komposita_finden_ihren_baustein():
    """Selbstprobe fuer `_deckung`: ohne Komposita-Toleranz findet diese Frage nichts.

    `Qualitaetsmanagementsystem` in der Frage, `Qualitaetsmanagement` im Baustein.
    """
    frage = av.fragen_aus_text("1. Bitte beschreiben Sie Ihr Qualitaetsmanagementsystem.\n")[0]
    kand = av.kandidaten(frage, BAUSTEINE)
    assert kand, "Komposita-Toleranz greift nicht"
    assert kand[0]["id"] == "b1"


def test_ohne_passung_keine_kandidaten():
    frage = {"frage": "Wie hoch ist der Wasserstand der Elbe bei Torgau?", "thema": "sonstiges"}
    assert av.kandidaten(frage, BAUSTEINE) == []


# ── Belegpruefung: muss anschlagen ───────────────────────────────────────────────────────────

def _chat(antwort: str, belege: list[dict]):
    return lambda messages: json.dumps({"antwort": antwort, "belege": belege})


def test_kein_baustein_fragt_kein_modell():
    """Ohne Kandidaten darf kein Modell gefragt werden — das kostet sonst Geld fuer nichts."""
    def platzt(messages):
        raise AssertionError("Modell wurde trotz fehlender Bausteine gefragt")

    frage = {"frage": "Wie hoch ist der Wasserstand der Elbe bei Torgau?", "thema": "sonstiges"}
    v = av.vorschlag(frage, BAUSTEINE, chat_fn=platzt)
    assert v["status"] == "kein_baustein"
    assert v["antwort"] == ""


def test_erfundenes_zitat_wird_abgewiesen():
    frage = av.fragen_aus_text("1. Bitte beschreiben Sie Ihr Qualitaetsmanagementsystem.\n")[0]
    v = av.vorschlag(frage, BAUSTEINE, chat_fn=_chat(
        "Wir sind nach ISO 27001 zertifiziert.",
        [{"baustein": "b1", "zitat": "nach ISO 27001 zertifiziert"}]))
    assert v["status"] == "unbelegt"
    assert any("nirgends" in m for m in v["maengel"]), v["maengel"]


def test_zitat_aus_falschem_baustein_wird_benannt():
    """Verwechselt statt erfunden: das Zitat existiert, steht aber im anderen Baustein.

    Geprueft wird direkt an `pruefe_belege`, weil beide Bausteine dafuer Kandidaten sein muessen.
    Ueber `vorschlag` laesst sich der Fall nicht stellen: zu einer QM-Frage ist der
    Referenz-Baustein gar nicht Kandidat, und dann ist „steht nirgends" die richtige Auskunft.
    """
    ok, maengel = av.pruefe_belege(
        "Wir haben drei vergleichbare Projekte umgesetzt.",
        [{"baustein": "b1", "zitat": "drei vergleichbare Projekte"}],
        BAUSTEINE)
    assert not ok
    assert any("b2" in m for m in maengel), maengel


def test_erfundenes_zitat_auch_bei_allen_bausteinen_abgewiesen():
    """Gegenprobe zum Fall darueber: dasselbe Verfahren, aber das Zitat gibt es nirgends."""
    ok, maengel = av.pruefe_belege(
        "Wir sind nach ISO 27001 zertifiziert.",
        [{"baustein": "b1", "zitat": "nach ISO 27001 zertifiziert"}],
        BAUSTEINE)
    assert not ok
    assert any("nirgends" in m for m in maengel), maengel


def test_entwurf_ohne_beleg_ist_unbelegt():
    frage = av.fragen_aus_text("1. Bitte beschreiben Sie Ihr Qualitaetsmanagementsystem.\n")[0]
    v = av.vorschlag(frage, BAUSTEINE, chat_fn=_chat("Wir machen das sehr gut.", []))
    assert v["status"] == "unbelegt"


def test_kaputtes_json_ist_unbelegt_nicht_fertig():
    frage = av.fragen_aus_text("1. Bitte beschreiben Sie Ihr Qualitaetsmanagementsystem.\n")[0]
    v = av.vorschlag(frage, BAUSTEINE, chat_fn=lambda m: "Entschuldigung, kein JSON")
    assert v["status"] == "unbelegt"


def test_guter_fall_ist_fertig():
    frage = av.fragen_aus_text("1. Bitte beschreiben Sie Ihr Qualitaetsmanagementsystem.\n")[0]
    v = av.vorschlag(frage, BAUSTEINE, chat_fn=_chat(
        "Unser Qualitaetsmanagement ist nach ISO 9001 zertifiziert.",
        [{"baustein": "b1", "zitat": "nach ISO 9001 zertifiziert"}]))
    assert v["status"] == "fertig", v["maengel"]
    assert v["belege"][0]["baustein"] == "b1"


# ── Zaehlung ─────────────────────────────────────────────────────────────────────────────────

def test_zaehlung_zaehlt_nur_fertig():
    """Ein `unbelegt` darf nicht als halber Erfolg verbucht werden."""
    fragen = av.fragen_aus_text(
        "1. Bitte beschreiben Sie Ihr Qualitaetsmanagementsystem.\n"
        "2. Welche Referenzen koennen Sie vorweisen?\n")
    assert len(fragen) == 2
    ruf = {"n": 0}

    def wechselnd(messages):
        ruf["n"] += 1
        if ruf["n"] == 1:
            return json.dumps({"antwort": "Nach ISO 9001 zertifiziert.",
                               "belege": [{"baustein": "b1", "zitat": "nach ISO 9001 zertifiziert"}]})
        return json.dumps({"antwort": "Wir haben viele Referenzen.",
                           "belege": [{"baustein": "b2", "zitat": "sehr viele Referenzen"}]})

    erg = av.vorschlaege(fragen, BAUSTEINE, chat_fn=wechselnd)
    assert erg["zaehlung"]["fertig"] == 1
    assert erg["zaehlung"]["unbelegt"] == 1
    assert erg["fertig"] == 1, "die angezeigte Zahl darf nur fertige Vorschlaege zaehlen"


# ── Die Modellwahl faellt einmal je Auftrag ──────────────────────────────────────────────────

def _llm_attrappe(monkeypatch, antwort: str, belege: list[dict]):
    """Haengt sich in `govisor.llm` und zaehlt, wie oft die Modellwahl faellt."""
    import contextlib

    from govisor import llm

    zaehler = {"wahl": 0, "chat": 0}

    def gewaehlt(*a, **k):
        zaehler["wahl"] += 1
        return "attrappe/modell"

    def chat(messages, model=None, **k):
        zaehler["chat"] += 1
        return json.dumps({"antwort": antwort, "belege": belege})

    monkeypatch.setattr(llm, "gewaehltes_modell", gewaehlt)
    monkeypatch.setattr(llm, "mit_boden", lambda m: m)
    monkeypatch.setattr(llm, "chat", chat)
    monkeypatch.setattr(llm, "kontext", lambda **k: contextlib.nullcontext())
    return zaehler


def test_modellwahl_faellt_einmal_je_auftrag(monkeypatch):
    """⚠ Vorher einmal JE FRAGE. `gewaehltes_modell` liest `data/modellwahl.json` von der
    externen Platte, auf der gleichzeitig die Dokument-Arbeiter schreiben — bei zwoelf Fragen
    zwoelf Lesezugriffe unter Last. Der Arbeiter sah dadurch aus, als stuende er still.
    """
    zaehler = _llm_attrappe(monkeypatch, "Nach ISO 9001 zertifiziert.",
                            [{"baustein": "b1", "zitat": "nach ISO 9001 zertifiziert"}])
    fragen = av.fragen_aus_text(
        "1. Bitte beschreiben Sie Ihr Qualitaetsmanagementsystem.\n"
        "2. Welche Nachweise zum Qualitaetsmanagement koennen Sie vorlegen?\n")
    assert len(fragen) == 2
    av.vorschlaege(fragen, BAUSTEINE)
    assert zaehler["chat"] == 2, "beide Fragen sollen gefragt werden"
    assert zaehler["wahl"] == 1, f"Modellwahl fiel {zaehler['wahl']}-mal statt einmal"


def test_ohne_kandidaten_faellt_gar_keine_modellwahl(monkeypatch):
    """Die Zusicherung aus `_spaet`: ohne passenden Baustein wird die Platte nicht angefasst."""
    zaehler = _llm_attrappe(monkeypatch, "egal", [])
    fragen = [{"frage": "Wie hoch ist der Wasserstand der Elbe bei Torgau?", "thema": "sonstiges"},
              {"frage": "Welche Farbe hat das Dach des Rathauses in Torgau?", "thema": "sonstiges"}]
    erg = av.vorschlaege(fragen, BAUSTEINE)
    assert erg["zaehlung"]["kein_baustein"] == 2
    assert zaehler["wahl"] == 0, "ohne Kandidaten darf die Modellwahl nicht fallen"
    assert zaehler["chat"] == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
