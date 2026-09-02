"""Standardtext-Anteil (Kennzahl 8) — die Zahl, die sagt, ob 1.152 Tsd. Zeichen Arbeit sind.

Zwei Dinge unterscheiden sie von allem, was in dieser Reihe vorher kam:

  * Sie ist ein VERHÄLTNIS und hält die Driftprüfung deshalb aus (25 % → 34 % → 32 % → 36 %
    über die Lesetiefe), wo absolute Zählungen aus denselben Dokumenten durchfallen
    (Kennzahl 4: 2 → 7 → 16 Formulare).
  * Ihre Vergleichsgruppe ist NICHT das Regelwerk, sondern die Textmenge. Das war nicht die
    erste Vermutung und ist gemessen: 4,1× gegen 1,8×.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SKRIPT = WURZEL / "scripts" / "export_standardtext.py"
QUELLE = SKRIPT.read_text(encoding="utf-8")
CORE = (WURZEL / "web" / "lib" / "explorerCore.js").read_text(encoding="utf-8")
DATEI = WURZEL / "web" / "data" / "standardtext.json"


def _modul():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_st", SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _block(name: str) -> str:
    rest = CORE[CORE.index(f"function {name}("):]
    return rest[:rest.index("\n}")]


def _körper(name: str) -> str:
    """Rumpf ohne Docstring — die Kommentare zitieren absichtlich, was der Code nicht tut."""
    fn = next(n for n in ast.walk(ast.parse(QUELLE))
              if isinstance(n, ast.FunctionDef) and n.name == name)
    rumpf = fn.body[1:] if ast.get_docstring(fn) else fn.body
    return "\n".join(ast.get_source_segment(QUELLE, k) or "" for k in rumpf)


# ── die Definition ──────────────────────────────────────────────────────────────────────

def test_je_absatz_nicht_je_datei():
    """⚠ `document_duplicates` gibt es längst (4.902 Paare) und beantwortet eine andere Frage:
    ganze Dateien sind nur in 2,1 % der Fälle identisch, ein geändertes Datum im Kopf genügt."""
    m = _modul()
    assert m.MIND_ZEICHEN == 120 and m.MIND_VORGAENGE == 3
    k = _körper("_anteile")
    assert "_ABSATZ.split" in k, "es wird nicht in Absätze zerlegt"
    assert "pruefsumme" not in k and "document_duplicates" not in k


def test_leerraum_wird_vereinheitlicht():
    """⚠ Derselbe Absatz aus PDF und DOCX unterscheidet sich in jedem Zeilenumbruch. Ohne
    Normalisierung findet nichts je einen Partner."""
    assert '" ".join(absatz.split())' in QUELLE


def test_je_vorgang_einmal_gezaehlt():
    """⚠ Ein Absatz, der in fünf Dateien DESSELBEN Vorgangs steht, ist kein Standardtext,
    sondern eine Wiederholung im Paket. Gezählt wird über ein Dict je Vorgang."""
    k = _körper("_anteile")
    assert "for h in d:" in k and "vorkommen[h] += 1" in k
    assert "for h, ln in d.items():\n            vorkommen" not in k


# ── die Vergleichsgruppe ────────────────────────────────────────────────────────────────

def test_verglichen_wird_je_textmenge_nicht_je_regelwerk():
    """⚠ DER BEFUND, der die erste Fassung umgeworfen hat. Das Regelwerk trennt sichtbar
    (UVgO 42 %, VOB 25 %, 1,8×), die Textmenge doppelt so stark (41 / 25 / 10 %, 4,1×) — und
    ihr Muster wiederholt sich innerhalb jedes Regelwerks. Grosse Pakete tragen ein eigenes
    Leistungsverzeichnis, und das steht nirgends sonst."""
    m = _modul()
    assert len(m.BAENDER) == 3
    assert [b[2] for b in m.BAENDER] == ["klein", "mittel", "gross"]
    assert not hasattr(m, "_rahmen"), "die Einteilung nach Regelwerk ist noch da"
    assert "regulatory_regime" not in QUELLE


def test_zu_wenig_text_bekommt_keinen_wert():
    """⚠ Unter 50 Tsd. Zeichen landen 35 % der Vorgänge bei genau 0 % (darüber 3 %): zu wenige
    Absätze, um überhaupt Partner finden zu können. Kein Wert ist besser als ein schlechter."""
    m = _modul()
    assert m.MIND_TEXT == 50_000
    assert m._band(10_000) is None
    assert m._band(100_000) == "klein" and m._band(1_000_000) == "gross"


def test_das_band_wird_im_export_aufgeloest():
    """⚠ Der Renderer kennt nur `lbChars`, und das ist die AUSGELIEFERTE Länge, nicht die
    gemessene. Wer dort neu einordnete, träfe ein anderes Band — und der Anteil fällt von 41 %
    auf 10 %, wenn das Paket wächst."""
    b = _block("standardtextAnteil")
    assert "lbChars" not in b and "band" not in b, "das Frontend ordnet selbst ein"
    assert "st.median" in b and "st.hoch" in b


def test_driftpruefung_laeuft_mit():
    """Sie hält sie aus, weil sie ein Verhältnis ist — geprüft wird trotzdem bei jedem Lauf,
    statt das Urteil von heute einzufrieren."""
    k = _körper("main")
    assert "MAX_DRIFT" in k and "n_parsed_files" in k and "verworfen" in k
    m = _modul()
    assert m.MAX_DRIFT <= 1.5


# ── Anzeige ─────────────────────────────────────────────────────────────────────────────

def test_steht_im_volltext_kopf():
    """Dort entscheidet jemand, ob er das liest — und dort steht die Zahl, die sie einordnet."""
    stelle = CORE[CORE.index('<span class="rt-open">'):]
    stelle = stelle[:stelle.index("</summary>")]
    assert "standardtextAnteil(l)" in stelle
    assert "Tsd. Zeichen" in stelle, "die Zahl, auf die sie sich bezieht, fehlt daneben"


def test_kein_warnton():
    """⚠ Ein hoher Anteil ist keine schlechte Nachricht, sondern weniger Arbeit. Farbig ist in
    dieser Ansicht, was Geld oder Ausschluss kostet."""
    css = (WURZEL / "web" / "app" / "explorer.css").read_text(encoding="utf-8")
    block = css[css.index(".rt-std {"):css.index(".rt-std-viel") + 200]
    assert "--flag" not in block and "--warn" not in block


def test_der_titel_nennt_die_definition():
    """„62 % Standardtext" ohne Definition ist eine Behauptung. Der Titel sagt, was gezählt
    wurde und wogegen verglichen wird."""
    b = _block("standardtextAnteil")
    assert "120 Zeichen" in b and "drei Vergaben" in b and "{m}" in b


# ── Ausliefergut ────────────────────────────────────────────────────────────────────────

def test_ausgabe_haelt_die_form():
    if not DATEI.exists():
        return
    d = json.loads(DATEI.read_text(encoding="utf-8"))
    assert set(d) == {"leads", "baender"}
    assert d["leads"] and d["baender"]
    for v in d["leads"].values():
        assert set(v) == {"a", "median", "hoch"}
        assert 0 <= v["a"] <= 100 and v["hoch"] >= v["median"]
    # ⚠ Die Bänder müssen sich unterscheiden, sonst war die Einteilung umsonst.
    med = sorted(g["median"] for g in d["baender"].values())
    assert med[-1] >= 2 * med[0], f"die Textmengen-Bänder trennen nicht mehr: {med}"
