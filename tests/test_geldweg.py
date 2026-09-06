"""Kein Weg an der Geldwache vorbei.

Die Bremse sitzt in `llm.chat()` — Reserve, Tagesdeckel, Lauf-Limit. Wer selbst gegen
OpenRouter anruft, hat sie nicht, bucht nichts ins Kostenbuch und zahlt Listenpreis statt
Bodenpreis. Eine Bremse, an der ein Weg vorbeiführt, ist keine Bremse.

⚠ GEFUNDEN AM 2026-09-04. `govisor/kategorie.py` hatte einen eigenen `requests.post` gegen
`openrouter.ai/api/v1/chat/completions`, mit eigenem Schlüssel-Leser und eigener
Wiederholschleife. Gemessen im Lauf desselben Tages: 1.179 Titel, 40 Stapel, **jede Nacht**.
Kein grosser Betrag, aber unsichtbar — und die nächtliche Modellmarkt-Rechnung („Mischung
3.0:1, gemessen an 24.455 Buchungen") stand damit auf unvollständigen Zahlen.

⚠ BEWUSST AUSGENOMMEN: `govisor/llm_batch.py`. Der Stapelweg ist asynchron (absenden, 24 h
später abholen); die Kosten stehen erst beim Abholen fest, eine synchrone Vorabbremse passt
dort nicht. Er hängt in keinem Lauf-Skript, sondern nur an `scripts/analyse_batch.py` von
Hand. Das ist eine offene Lücke, aber eine andere — hier benannt, nicht stillschweigend
mitgezählt.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ERLAUBT = {"govisor/llm.py", "govisor/llm_batch.py"}
ENDPUNKT = "chat/completions"


def _code_zeichenketten(quelle: str):
    """Zeichenketten, die der Rechner benutzt — Docstrings und Kommentare NICHT.

    ⚠ Sonst schlägt der Wächter auf seiner eigenen Dokumentation an. Genau das ist beim
    Bauen passiert: der erklärende Kommentar in `kategorie.py` nennt den Endpunkt, und die
    Textsuche meldete die reparierte Datei prompt wieder als Befund.
    """
    baum = ast.parse(quelle)
    docstrings = set()
    for k in ast.walk(baum):
        if isinstance(k, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            erste = k.body[0] if k.body else None
            if (isinstance(erste, ast.Expr) and isinstance(erste.value, ast.Constant)
                    and isinstance(erste.value.value, str)):
                docstrings.add(id(erste.value))
    for k in ast.walk(baum):
        if isinstance(k, ast.Constant) and isinstance(k.value, str) and id(k) not in docstrings:
            yield k.lineno, k.value


def _dateien():
    for ordner in ("govisor", "scripts"):
        for p in sorted((ROOT / ordner).glob("*.py")):
            yield p


def test_niemand_ruft_den_chat_endpunkt_selbst_an():
    """Nur `llm.py` spricht mit dem Chat-Endpunkt."""
    befunde = []
    for p in _dateien():
        rel = p.relative_to(ROOT).as_posix()
        if rel in ERLAUBT:
            continue
        try:
            for zeile, wert in _code_zeichenketten(p.read_text(encoding="utf-8")):
                if ENDPUNKT in wert:
                    befunde.append(f"{rel}:{zeile}")
        except SyntaxError:
            continue
    assert not befunde, (
        "Diese Stellen rufen OpenRouter selbst an, also ohne Geldwache, ohne Kostenbuch und "
        "ohne Bodenpreis:\n  " + "\n  ".join(befunde)
        + "\nStattdessen `govisor.llm.chat(...)` benutzen.")


def test_niemand_liest_den_schluessel_selbst():
    """Wer den Schlüssel selbst liest, kennt nur EINEN — `llm` kann rotieren.

    `kategorie.py` prüfte mit einem eigenen `_key()`, ob überhaupt gearbeitet werden kann.
    Das las nur `.secrets/openrouter.key`, nicht die Mehrfachdatei, und wusste nichts von
    leergelaufenen Schlüsseln: es meldete „kein Schlüssel", während `llm` noch zwei hatte —
    oder umgekehrt.
    """
    befunde = []
    for p in _dateien():
        rel = p.relative_to(ROOT).as_posix()
        if rel in ERLAUBT:
            continue
        try:
            for zeile, wert in _code_zeichenketten(p.read_text(encoding="utf-8")):
                if "openrouter.key" in wert or wert == "OPENROUTER_KEY_FILE":
                    befunde.append(f"{rel}:{zeile}  {wert[:60]!r}")
        except SyntaxError:
            continue
    assert not befunde, (
        "Diese Stellen lesen den OpenRouter-Schluessel selbst:\n  " + "\n  ".join(befunde)
        + "\n`llm.available_keys()` fragt dasselbe und kennt die Mehrfachdatei.")


def test_die_kategorie_ableitung_geht_ueber_die_bremse():
    """Der reparierte Weg, festgehalten."""
    q = (ROOT / "govisor" / "kategorie.py").read_text(encoding="utf-8")
    assert "llm.chat(" in q, "die Kategorie-Ableitung ruft nicht mehr ueber `llm.chat`"
    assert 'kontext(zweck="kategorie")' in q, (
        "ohne Zweck ist die Buchung im Kostenbuch nicht zuordenbar")
    assert "BudgetErschoepft" in q, (
        "ein erschoepftes Budget muss die Schleife abbrechen, nicht vierzigmal scheitern")


# ---- Verhalten, nicht nur Quelltext -------------------------------------------
def _kategorie():
    import importlib
    return importlib.import_module("govisor.kategorie")


KAT = {"45": ("Bau", "bau"), "72": ("IT", "it")}


def test_kategorie_liest_die_antwort_und_prueft_die_kennung(monkeypatch):
    """Der normale Weg — und die Kennungspruefung, die schon einmal 60 Leads gekostet hat."""
    k = _kategorie()
    from govisor import llm

    gesehen = {}

    def falsches_chat(messages, **kw):
        gesehen["modell"] = kw.get("model")
        gesehen["n"] = len(messages)
        # Eine echte, eine erfundene Kennung, eine unbekannte Division.
        return ('{"v":[{"id":"a1","div":"45"},{"id":"gibtsnicht","div":"72"},'
                '{"id":"b2","div":"99"}]}')

    monkeypatch.setattr(llm, "chat", falsches_chat)
    aus = k.frag_modell([("a1", "Dachsanierung"), ("b2", "Serverwartung")], KAT, [])
    assert aus == {"a1": "45"}, aus
    # Bis zum 2026-09-06 stand hier `k.MODELL` — eine fest verdrahtete Konstante, die
    # Pruefstand, Freigabe und Modellwahl umging. Die Zusicherung ist dieselbe geblieben:
    # was `_modell()` liefert, muss bei `llm.chat` ankommen.
    assert gesehen["modell"] == k._modell(), "das Modell wird nicht mehr durchgereicht"
    assert gesehen["n"] == 2, "System- und Nutzernachricht muessen beide ankommen"


def test_kategorie_bricht_beim_budget_ab_statt_vierzigmal_zu_scheitern(monkeypatch):
    """⚠ Die Geldwache ist KLEBRIG: einmal gefallen, wirft jeder weitere Aufruf sofort.

    Vierzig Stapel durchlaufen zu lassen, die alle scheitern, erzeugt vierzig gleiche
    Zeilen und verdeckt den einen Grund. Der erste Wurf muss die Schleife beenden.
    """
    k = _kategorie()
    from govisor import llm

    rufe = {"n": 0}

    def leeres_konto(messages, **kw):
        rufe["n"] += 1
        raise llm.BudgetErschoepft("Reserve unterschritten")

    monkeypatch.setattr(llm, "chat", leeres_konto)
    faelle = [(f"id{i}", f"Titel {i}") for i in range(3 * k.BATCH)]   # drei Stapel
    aus = k.frag_modell(faelle, KAT, [])
    assert aus == {}, "bei erschoepftem Budget darf nichts geraten werden"
    assert rufe["n"] == 1, f"nach dem ersten Wurf muss Schluss sein, waren {rufe['n']}"


def test_ein_kaputter_stapel_beendet_den_lauf_nicht(monkeypatch):
    """„Fehlschlaege sind LEER, nicht geraten" — aber der naechste Stapel kommt dran."""
    k = _kategorie()
    from govisor import llm

    rufe = {"n": 0}

    def mal_so_mal_so(messages, **kw):
        rufe["n"] += 1
        if rufe["n"] == 1:
            raise RuntimeError("Endpunkt haengt")
        return '{"v":[{"id":"id30","div":"72"}]}'

    monkeypatch.setattr(llm, "chat", mal_so_mal_so)
    faelle = [(f"id{i}", f"Titel {i}") for i in range(2 * k.BATCH)]
    aus = k.frag_modell(faelle, KAT, [])
    assert rufe["n"] == 2, "der zweite Stapel muss trotzdem laufen"
    assert aus == {"id30": "72"}, aus


def test_unlesbare_antwort_ist_ein_leerer_stapel(monkeypatch):
    """Kein JSON heisst kein Ergebnis — und kein Absturz."""
    k = _kategorie()
    from govisor import llm
    monkeypatch.setattr(llm, "chat", lambda m, **kw: "Entschuldigung, das kann ich nicht.")
    assert k.frag_modell([("a1", "Dachsanierung")], KAT, []) == {}


def test_kategorie_bricht_ab_wenn_kein_schluessel_mehr_kann(monkeypatch):
    """⚠ Unterschied zum Budget: `AllKeysExhausted` faellt schon bei einem haengenden
    Endpunkt. Das waere ein schlechter Grund, vierzig Stapel abzublasen — endgueltig ist es
    erst, wenn KEIN Schluessel mehr kann. Deshalb fragt die Schleife das echte Signal
    (`llm.available_keys()`) statt die Ausnahme zu deuten.
    """
    k = _kategorie()
    from govisor import llm

    rufe = {"n": 0}

    def immer_kaputt(messages, **kw):
        rufe["n"] += 1
        raise llm.AllKeysExhausted("Alle 1 Keys fehlgeschlagen")

    monkeypatch.setattr(llm, "chat", immer_kaputt)
    faelle = [(f"id{i}", f"Titel {i}") for i in range(3 * k.BATCH)]

    monkeypatch.setattr(llm, "available_keys", lambda: 2)     # noch Vorrat → weitermachen
    k.frag_modell(faelle, KAT, [])
    assert rufe["n"] == 3, f"bei vorhandenem Vorrat muessen alle Stapel laufen, waren {rufe['n']}"

    rufe["n"] = 0
    monkeypatch.setattr(llm, "available_keys", lambda: 0)     # nichts mehr da → abbrechen
    k.frag_modell(faelle, KAT, [])
    assert rufe["n"] == 1, f"ohne Vorrat muss nach dem ersten Wurf Schluss sein, waren {rufe['n']}"
