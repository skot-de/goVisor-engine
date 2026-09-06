"""Der Preisdeckel und die Modellwahl — zwei Ausfälle, die wie Erfolg aussahen.

`govisor.kategorie` hat seit seiner Einführung KEINEN einzigen erfolgreichen LLM-Aufruf
gehabt. Das Kostenbuch kennt drei Einträge zum Zweck `kategorie`, alle mit null Token;
der Nachtlauf meldete 44 Fehlschläge je Lauf als Warnung, und 2.065 Ausschreibungen
blieben jede Nacht ohne Kategorie. Zwei unabhängige Ursachen.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
LLM = (WURZEL / "govisor" / "llm.py").read_text(encoding="utf-8")
KAT = (WURZEL / "govisor" / "kategorie.py").read_text(encoding="utf-8")


def _nur_code(quelle: str) -> str:
    """Quelltext ohne Docstrings und Kommentare.

    ⚠ SONST PRUEFT DER TEST DIE WARNUNG STATT DES CODES. Beide Dateien WARNEN ausdruecklich
    vor dem, was hier verboten wird — und zitieren es dabei woertlich („hier stand
    `MODELL = ...`", „NICHT `except Exception`"). Ohne Strippen schlaegt der Test also an
    der Begruendung an, die ihn ueberfluessig machen soll.
    """
    import ast
    import re
    baum = ast.parse(quelle)
    for k in ast.walk(baum):
        if isinstance(k, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                          ast.Module)) and ast.get_docstring(k):
            k.body = k.body[1:]
    return re.sub(r"#[^\n]*", "", ast.unparse(baum))


# ── Ursache 1: der Rückfall kannte nur eine Formulierung ────────────────────────────

def test_deckel_absage_erkennt_beide_formulierungen():
    """⚠ Der Rückfall „einmal ohne Deckel" gab es seit dem 2026-08-24 — er prüfte aber auf
    das Wort `provider` („no allowed providers"). Für einen Deckel, den KEIN Endpunkt
    einhält, antwortet OpenRouter anders: „No endpoints found that satisfy the max price for
    this request" — ohne das Wort. Der Rückfall griff deshalb nie."""
    import sys
    sys.path.insert(0, str(WURZEL))
    from govisor.llm import _deckel_abgelehnt
    assert _deckel_abgelehnt('{"error":{"message":"No allowed providers are available"}}')
    assert _deckel_abgelehnt(
        '{"error":{"message":"No endpoints found that satisfy the max price for this request"}}')
    assert not _deckel_abgelehnt('{"error":{"message":"context length exceeded"}}')
    assert not _deckel_abgelehnt("")


def test_der_rueckfall_haengt_nicht_mehr_an_einem_wort():
    kern = LLM.split("if (400 <= r.status_code < 500")[1][:300]
    assert "_deckel_abgelehnt(r.text)" in kern
    assert '"provider" in r.text.lower()' not in kern


# ── Ursache 2: ein fest verdrahtetes, nicht freigegebenes Modell ────────────────────

def test_kategorie_verdrahtet_kein_modell_mehr():
    """⚠ `MODELL = "google/gemini-2.5-flash-lite"` stand nicht einmal auf der Freigabeliste
    (`data/modellfreigabe.json` kennt zwei Modelle). Der Schritt umging damit Prüfstand,
    Freigabe und die tägliche Wahl des Wächters."""
    code = _nur_code(KAT)
    assert "gemini-2.5-flash-lite" not in code, "das Modell ist wieder verdrahtet"
    assert "llm.gewaehltes_modell()" in code
    freigabe = json.loads((WURZEL / "data" / "modellfreigabe.json").read_text(encoding="utf-8"))
    assert "google/gemini-2.5-flash-lite" not in freigabe


def test_modell_wird_beim_aufruf_erfragt_nicht_beim_import():
    """Beim Import ausgewertet fröre die Wahl auf den Stand ein, den der Prozess beim Start
    vorfand — bei einem Arbeiter, der Stunden läuft, ist das die Entscheidung von gestern."""
    kern = KAT.split("def _modell(")[1].split("\ndef ")[0]
    assert "return llm.gewaehltes_modell()" in kern
    assert "_MODELL =" not in KAT and "MODELL = llm." not in KAT


# ── Die Rangfolge und ihre Verfallszeit ─────────────────────────────────────────────

def test_rangfolge_der_modellwahl(tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(WURZEL))
    from govisor import llm
    monkeypatch.setenv("OR_MODEL_FEST", "zwang/modell")
    assert llm.gewaehltes_modell() == "zwang/modell", "Zwang schlaegt alles"
    monkeypatch.delenv("OR_MODEL_FEST")
    assert llm.gewaehltes_modell() == json.loads(
        (WURZEL / "data" / "modellwahl.json").read_text(encoding="utf-8"))["modell"]


def test_veraltete_wahl_wird_ignoriert(tmp_path, monkeypatch):
    """Eine alte Entscheidung stillschweigend weiterzufahren wäre die schlechtere Sorte
    Automatik — dann gilt wieder die Vorgabe, und der Lauf sagt es."""
    import sys
    sys.path.insert(0, str(WURZEL))
    from govisor import llm
    alt = tmp_path / "data"
    alt.mkdir()
    (alt / "modellwahl.json").write_text(json.dumps(
        {"modell": "uralt/modell", "stand": str(dt.date.today() - dt.timedelta(days=30))}))
    monkeypatch.setattr(llm, "__file__", str(tmp_path / "govisor" / "llm.py"))
    monkeypatch.delenv("OR_MODEL_FEST", raising=False)
    monkeypatch.delenv("OR_MODEL", raising=False)
    assert llm.gewaehltes_modell() != "uralt/modell"


def test_kein_breiter_fang_um_die_modellwahl():
    """⚠ Beim Einbau fehlten `json` und `ROOT` im Modul; ein `except Exception` hat den
    NameError verschluckt und still die Vorgabe geliefert — ein Ausfall, der wie ein
    funktionierender Standard aussieht, also genau die Sorte Fehler, wegen der diese
    Funktion überhaupt entstanden ist."""
    kern = _nur_code(LLM).split("def gewaehltes_modell(")[1].split("\ndef ")[0]
    assert "except Exception" not in kern
    assert "except (OSError, json.JSONDecodeError, KeyError, ValueError)" in kern
