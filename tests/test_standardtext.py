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


def test_kein_band_faellt_mehr_an_der_drift():
    """⚠ HIER STAND DAS GEGENTEIL: „Driftpruefung laeuft mit". Am 2026-09-18 ausgemessen
    und gestrichen.

    Die Pruefung verglich flach gelesene Vorgaenge (1-7 Dateien) mit tief gelesenen (>=8)
    und verwarf ein Band, wenn das VERHAELTNIS der Mediane 1,5 riss. Gemessen, mit 400
    zufaelligen Teilungen derselben Zahlen als Massstab:

        Band       n     flach   tief   Verhaeltnis   Δ Punkte   Zufall p95
        klein   5.207    43,9%  52,9%          1,20       +9,0         1,06
        mittel  7.171    27,1%  32,6%          1,20       +5,4         1,06
        gross   1.664     9,1%  14,7%          1,61       +5,6         1,27

    Alle drei Baender driften und alle drei liegen klar ueber dem Zufall. In
    Prozentpunkten driftet `klein` am staerksten (+9,0) und blieb stehen, `gross` am
    wenigsten (+5,6) und flog — ein Verhaeltnis misst hier die Basisgroesse, nicht die
    Drift. Folge des Ausschlusses waren 1.675 Vorgaenge ohne Vergleichswert, ausgerechnet
    die am besten dokumentierten.

    Dieser Test faengt das Wiedereinbauen. Wer die Pruefung zurueckholen will, misst sie
    vorher neu (`scripts/miss_driftschwelle.py`) — dann faellt dieser Test, und das ist
    die Gelegenheit, die Begruendung mitzuliefern.
    """
    m = _modul()
    assert not hasattr(m, "MAX_DRIFT"), (
        "MAX_DRIFT ist zurueck. Die Schwelle war gemessen ungeeignet: sie warf das Band "
        "raus, das am wenigsten driftet")
    if not DATEI.exists():
        return
    d = json.loads(DATEI.read_text(encoding="utf-8"))
    mit_drift = {k: g for k, g in d["verworfen"].items() if "Drift" in g}
    assert not mit_drift, (
        f"{len(mit_drift)} Bänder sind wieder an einer Driftpruefung gescheitert: "
        f"{sorted(mit_drift)}")


def test_die_schwellen_behalten_ihre_eigene_driftpruefung():
    """⚠ `scripts/export_schwellen.py` fuehrt dieselben Konstantennamen und eine eigene
    Driftpruefung. Sie bleibt, und zwar mit Absicht: dort sind es EURO-Betraege, die Drift
    laeuft nach UNTEN (500.000 flach → 250.000 tief), und gemessen wurde sie nie. Wer die
    Begruendung vom Standardtext dorthin uebertraegt, uebertraegt eine Messung, die es
    fuer jene Zahlen nicht gibt."""
    # ⚠ AUF DIE ZUWEISUNG PRUEFEN, nicht auf das Wort. Die erste Fassung suchte
    #   `"MAX_DRIFT" in q` — und fand es in der VERWENDUNGSZEILE (`if drift > MAX_DRIFT`),
    #   auch nachdem die Definition entfernt war. Der Rueckbau lief gruen durch (F12).
    q = (WURZEL / "scripts" / "export_schwellen.py").read_text(encoding="utf-8")
    assert re.search(r"^MAX_DRIFT\s*=", q, re.M), (
        "die Driftpruefung der Geldschwellen ist mitgestrichen worden — sie war nie "
        "Gegenstand der Messung vom 2026-09-18")


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
    assert set(d) == {"leads", "baender", "verworfen", "ohne_vergleich"}
    assert d["leads"] and d["baender"]
    for v in d["leads"].values():
        assert set(v) == {"a", "median", "hoch"}
        assert 0 <= v["a"] <= 100 and v["hoch"] >= v["median"]


def test_ein_verworfenes_band_steht_im_auslieferstand():
    """⚠ WARUM DIESER TEST DEN ALTEN ERSETZT HAT. Hier stand `med[-1] >= 2 * med[0]` — „die
    Bänder müssen sich unterscheiden". Am 2026-09-17 wurde er rot und meldete „die
    Textmengen-Bänder trennen nicht mehr: [28, 44]".

    Das war richtig gemessen und falsch benannt. Die beiden Bänder trennen weiterhin
    (44 % gegen 28 %); was fehlte, war das DRITTE: `DE:gross` fiel aus der Driftpruefung
    (1,53×, tags darauf 1,62×), und die 2×-Schwelle stammte aus einer Welt mit drei Bändern,
    in der die Spanne von `klein` bis `gross` reichte.

    Die Folge war die eigentliche Nachricht und stand nirgends: **1.329 Vorgaenge** — die
    mit den meisten Unterlagen, ueber 800.000 Zeichen — verloren ihren Vergleichswert und
    tragen die Kennzahl seither gar nicht. Sichtbar nur in einer Zeile Nachtlauf-Log.

    Dieser Test prueft deshalb, was tatsaechlich schiefgehen kann: dass ein Band lautlos
    verschwindet.
    """
    if not DATEI.exists():
        return
    d = json.loads(DATEI.read_text(encoding="utf-8"))
    ordnung = [name for _, _, name in _modul().BAENDER]

    laender = {k.split(":")[0] for k in list(d["baender"]) + list(d["verworfen"])}
    for land in sorted(laender):
        for name in ordnung:
            schl = f"{land}:{name}"
            assert schl in d["baender"] or schl in d["verworfen"], (
                f"{schl} steht weder unter den tragenden noch unter den verworfenen Bändern. "
                f"Ein Band, das aus beiden Listen faellt, nimmt die Vergleichswerte seiner "
                f"Vorgaenge mit — ohne dass irgendetwas bricht.")

    for schl, grund in d["verworfen"].items():
        assert grund and len(grund) > 8, f"{schl} ist verworfen, ohne zu sagen warum"

    # ⚠ DIE FOLGERUNG GILT NUR IN EINE RICHTUNG, und die erste Fassung dieses Tests hatte
    #   sie umgedreht. Ein verworfenes Band kostet NICHT zwangslaeufig Vergleichswerte:
    #   `main()` loest ueber `lage.get(f"DE:{band}")` auf und faengt damit jedes Land ab,
    #   dessen eigene Baender zu duenn sind. Am 2026-09-18 sind alle drei LU-Baender
    #   verworfen und trotzdem `ohne_vergleich == 0` — die 45 LU-Vorgaenge bekommen die
    #   deutschen Werte.
    #
    #   Umgekehrt gilt es sehr wohl: einen Vergleichswert verliert ein Vorgang NUR, weil
    #   sein Band verworfen wurde. Steht dann nichts unter `verworfen`, fehlt die
    #   Begruendung — und genau das war der Zustand vom 17.09.
    if d["ohne_vergleich"]:
        assert d["verworfen"], (
            f"{d['ohne_vergleich']} Vorgaenge haben keinen Vergleichswert, aber kein Band "
            f"ist verworfen. Dann sagt nichts, warum sie ihn verloren haben.")


def test_mehr_text_heisst_weniger_standardtext():
    """Die inhaltliche Behauptung der Einteilung — und sie ueberlebt ein fehlendes Band.

    ⚠ Eine Verhaeltnisschwelle tut das nicht: sie haengt daran, WELCHE Bänder gerade
    tragen, und wird rot, sobald eines wegfaellt — mit einer Meldung ueber die falsche
    Sache. Die Ordnung ist die eigentliche Aussage: je mehr Text ein Vorgang hat, desto
    geringer der Anteil wiederholter Absätze. Gemessen am 2026-09-18 ueber DE:
    klein 44 % · mittel 28 % · gross 9-15 %.
    """
    if not DATEI.exists():
        return
    d = json.loads(DATEI.read_text(encoding="utf-8"))
    ordnung = [name for _, _, name in _modul().BAENDER]

    je_land = {}
    for schl, g in d["baender"].items():
        land, name = schl.split(":", 1)
        je_land.setdefault(land, []).append((ordnung.index(name), name, g["median"]))

    geprueft = 0
    for land, eintraege in sorted(je_land.items()):
        if len(eintraege) < 2:
            continue                       # ein einzelnes Band traegt keine Ordnung
        eintraege.sort()
        med = [m for _, _, m in eintraege]
        assert med == sorted(med, reverse=True), (
            f"{land}: der Standardtext-Anteil steigt mit der Textmenge statt zu fallen "
            f"({', '.join(f'{n} {m} %' for _, n, m in eintraege)}). Dann misst die Kennzahl "
            f"nicht mehr, was ihr Titel behauptet.")
        assert med[0] >= 1.3 * med[-1], (
            f"{land}: die Bänder liegen zu dicht beieinander "
            f"({', '.join(f'{n} {m} %' for _, n, m in eintraege)}) — dann war die Einteilung "
            f"umsonst und ein einziger Vergleichswert taete es auch.")
        geprueft += 1
    assert geprueft, "kein Land traegt zwei Bänder — die Einteilung vergleicht nichts mehr"
