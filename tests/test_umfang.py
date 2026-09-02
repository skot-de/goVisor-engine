"""Umfang der Angebotsarbeit (Kennzahlen 4 und 5) — und die Irrtümer, gegen die sie stehen.

Beide beantworten dieselbe Frage („wie viel Arbeit ist dieses Angebot?") und dürfen trotzdem
nicht dasselbe tun. Der Unterschied ist gemessen, nicht gesetzt:

    Kennzahl 4  grösstes FORMULAR   Summen wachsen mit der Lesetiefe → nur Anwesenheit, kein Markt
    Kennzahl 5  LEISTUNGSVERZEICHNIS  über die Lesetiefe stabil      → Vergleich je Gewerk erlaubt

Diese Datei hält beide Regeln fest, dazu die zwei Fallen, in die der Bau tatsächlich gelaufen
ist: die Lastgang-Tabelle als „Positionen zu bepreisen", und eine zweite Kachel für eine Zahl,
die längst angezeigt wurde.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SKRIPT = WURZEL / "scripts" / "export_umfang.py"
QUELLE = SKRIPT.read_text(encoding="utf-8")
CORE = (WURZEL / "web" / "lib" / "explorerCore.js").read_text(encoding="utf-8")


def _modul():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_uf", SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _körper(name: str) -> str:
    """Der Funktionsrumpf OHNE Docstring.

    ⚠ ZWEI FALLEN AUF EINMAL, beide in dieser Sitzung zugeschlagen. Erstens zitieren die
    Kommentare absichtlich, was der Code NICHT tun darf („doc_checklist", „Summe je Vorgang")
    — ein Wächter, der den Fliesstext mitliest, schlägt auf seiner eigenen Begründung an.
    Zweitens steht die SQL in `f\"\"\"…\"\"\"`, also ebenfalls in dreifachen Anführungszeichen:
    ein Regex darauf löscht die Abfrage mit, und der Wächter prüft danach eine leere Zeile.
    Deshalb `ast`, das den Docstring als eigenen Knoten kennt."""
    baum = ast.parse(QUELLE)
    fn = next(n for n in ast.walk(baum) if isinstance(n, ast.FunctionDef) and n.name == name)
    rumpf = fn.body[1:] if ast.get_docstring(fn) else fn.body
    return "\n".join(ast.get_source_segment(QUELLE, k) or "" for k in rumpf)


def _block(name: str) -> str:
    rest = CORE[CORE.index(f"function {name}("):]
    return rest[:rest.index("\n}")]


# ── Kennzahl 4: die Regel, die sie trägt ────────────────────────────────────────────────

def test_formular_nimmt_nur_eines_je_vorgang():
    """⚠ DER WÄCHTER. `row_number() ... where r = 1` holt genau ein Formular. Eine Summe wäre
    die Zahl, die uns misst statt die Vergabe: Formulare je Vorgang wachsen 2 → 7 → 16 mit der
    Zahl gelesener Dateien, ohne Plateau. Geprüft wird die Abfrage, nicht das Wort — die
    Kommentare nennen die verbotene Summe absichtlich beim Namen."""
    k = _körper("_formulare")
    abfrage = k[k.index("with "):k.index("fetchall()")]
    assert "row_number() over (partition by notice_id order by wert_num desc)" in abfrage
    assert "where r = 1" in abfrage
    assert not re.search(r"\b(sum|count)\s*\(", abfrage), "Summe je Vorgang misst uns"


def test_formular_ohne_marktvergleich():
    """Ein marktweiter Median stammt aus derselben Untererfassung wie der eigene Wert; dagegen
    verglichen sähe jeder tief gelesene Vorgang extremer aus als er ist."""
    from govisor import kennzahlen as K
    k = [x for x in K.ALLE if x.schluessel == "formularUmfang"]
    assert k and k[0].bezug == "keine", "Kennzahl 4 darf keinen Marktbezug tragen"


def test_sagt_nie_wenig_aufwand():
    """⚠ Abwesenheit dürfen wir nicht behaupten: ein Formular, das wir nicht gelesen haben,
    fehlt in den Daten und nicht in der Ausschreibung. Geprüft wird der ausgegebene Satz, nicht
    der Kommentar — der zitiert die verbotene Aussage absichtlich."""
    sätze = re.findall(r"tk\(\"([^\"]+)\"", _block("renderUmfangBlock"))
    assert sätze, "der Block gibt gar keinen Satz aus"
    for s in sätze:
        assert not re.search(r"\bwenig\b|\bkaum\b|\bnur\b|\bgering\b", s), f"behauptet Abwesenheit: {s!r}"


# ── Kennzahl 5: die zwei Fallen ─────────────────────────────────────────────────────────

def test_lv_liest_die_geparsten_positionen():
    """⚠ DIE TEURE FALLE. Der erste Versuch zählte `leistung_menge`-Zeilen aus `doc_checklist`
    — eine zweite Ableitung derselben Sache, und die schlechtere: 2.812 statt 3.770 Vorgänge,
    und an der Spitze LASTGÄNGE (Viertelstundenwerte eines Jahres, max 200.010), die als
    „Positionen zu bepreisen" gezählt worden wären. Gelesen wird dieselbe Quelle wie der Block,
    der die Zahl anzeigt."""
    k = _körper("_verzeichnisse")
    assert "doc_positions.parquet" in k
    assert "doc_checklist" not in k, "zweite Quelle für dieselbe Zahl"
    assert "leistung_menge" not in k


def test_lv_bringt_keine_eigene_zahl_mit():
    """⚠ DIE ZWEITE FALLE. `nPositionen` stand längst im Block „Leistungsumfang"; eine Kachel
    mit derselben Zahl daneben wäre Doppelung. Der Export liefert deshalb nur den Vergleich."""
    k = _körper("_verzeichnisse")
    eintrag = k[k.index('["lv"] = {'):]
    eintrag = eintrag[:eintrag.index("}")]
    assert set(re.findall(r'"(\w+)":', eintrag)) == {"gewerk", "median", "hoch"}, eintrag


def test_lv_vergleicht_je_gewerk():
    """⚠ Ein Median über alle Bauarbeiten mischt Installation (292 Positionen) mit Anstrich
    (54), 5,4-fach auseinander. Derselbe Fehler wie ein Fristenmedian über VgV und UVgO."""
    k = _körper("_verzeichnisse")
    assert "cpv_code" in k and "substr(l.cpv_code, 1, 4)" in k, "der Vergleich läuft nicht je Gewerk"
    assert "MIND_GEWERK" in k, "dünne Gewerke werden nicht ausgeschlossen"


def test_lv_zeigt_nur_den_oberen_rand():
    """„Üblich sind 292" bei einem LV im Mittelfeld ist keine Nachricht, sondern eine Zeile
    mehr. Der Vergleich erscheint nur, wo er eine Entscheidung ändern kann."""
    b = _block("lvVergleich")
    assert "n < v.hoch" in b, "der Vergleich steht auch im Mittelfeld"


def test_die_beiden_messen_nicht_dasselbe():
    """Ein VHB 223 hat ein Feld je LV-Position, die Vermutung liegt nahe. Gemessen ist die
    Korrelation -0,02; von 803 grossen Verzeichnissen haben nur 79 auch ein grosses Formular."""
    from govisor import kennzahlen as K
    hat = {x.schluessel: x for x in K.ALLE}
    assert {"formularUmfang", "lvUmfang"} <= set(hat)
    assert hat["lvUmfang"].bezug == "markt", "Kennzahl 5 darf vergleichen, sie ist stabil"


def test_nicht_mehr_unter_geplant():
    """Wer baut und den geplant-Eintrag stehen lässt, schickt die nächste Sitzung auf die Suche
    nach Arbeit, die es nicht mehr gibt."""
    from govisor import kennzahlen as K
    offen = {x.schluessel for x in K.ALLE if x.flaeche == "geplant"}
    assert not ({"formularaufwand", "formularUmfang", "mengengeruest", "lvUmfang"} & offen)


# ── Aufbereitung ────────────────────────────────────────────────────────────────────────

def test_schwellen_stimmen_mit_der_messung():
    m = _modul()
    assert m.ZEIGEN == 100 and m.HINWEIS == 400 and m.ZEIGEN < m.HINWEIS
    assert m.MIND_GEWERK == 40


def test_sprechende_feldnamen_zuerst():
    """Ein Drittel der Formulare beginnt mit „Field0, Field1"; die sprechenden Namen stehen
    dahinter. Ein Zitat aus Platzhaltern belegt nichts."""
    m = _modul()
    namen = ["Field0", "Field1", "ag_312_1_6", "TEXTFELD_2", "EVM_B_ANG"]
    namen.sort(key=lambda n: bool(m._STUMM.match(n)))
    assert namen[:3] == ["ag_312_1_6", "EVM_B_ANG", "Field0"], namen


def test_dateiname_ohne_verzeichnis():
    m = _modul()
    assert m._kurz("sonstiges/VVB 223 - Aufgliederung.pdf") == "VVB 223 - Aufgliederung.pdf"
    assert m._kurz("Angebotsdateien/Abgabe.zip::A") == "A"
    assert m._kurz("Dateien\\fuer Angebot\\VHB 223.pdf") == "VHB 223.pdf"
    assert m._kurz("") == "Formular"


def test_laender_kommen_vom_bestand():
    """⚠ Eine Länderliste im Code lässt ein neues Land stumm herausfallen — genau der Fehler,
    den die Sonde inzwischen länderagnostisch prüft."""
    fn = next(n for n in ast.walk(ast.parse(QUELLE))
              if isinstance(n, ast.FunctionDef) and n.name == "_laender")
    text = ast.get_source_segment(QUELLE, fn)
    assert "iterdir()" in text
    assert not re.search(r"\"(DE|AT|CH)\"\s*,", text), "harte Länderliste"


# ── Sicherheit ──────────────────────────────────────────────────────────────────────────

def test_dateiname_und_beleg_werden_escaped():
    """⚠ Beide kommen aus fremden Vergabeunterlagen. Seit das `esc()` aus der kv-Zeile entfernt
    wurde, escaped jede Stelle selbst — hier auch."""
    b = _block("renderUmfangBlock")
    assert "esc(f.datei)" in b and "esc(f.beleg)" in b, "ungeschützt im DOM"


# ── Ausliefergut ────────────────────────────────────────────────────────────────────────

def test_ausgabe_haelt_die_form():
    datei = WURZEL / "web" / "data" / "umfang.json"
    if not datei.exists():
        return
    d = json.loads(datei.read_text(encoding="utf-8"))
    assert d, "leer"
    assert set().union(*(set(v) for v in d.values())) <= {"formular", "lv"}
    fo = [v["formular"] for v in d.values() if "formular" in v]
    assert set().union(*(set(x) for x in fo)) <= {"felder", "datei", "hinweis", "beleg"}
    assert all(x["felder"] >= 100 and x["hinweis"] == (x["felder"] >= 400) for x in fo)
    lv = [v["lv"] for v in d.values() if "lv" in v]
    assert set().union(*(set(x) for x in lv)) == {"gewerk", "median", "hoch"}
    assert all(x["hoch"] >= x["median"] for x in lv)
    # ⚠ Ein verkürzter CPV („45") ist kein Gewerk — er machte aus jedem Bauvorhaben eine Gruppe.
    assert all(len(x["gewerk"]) == 4 for x in lv)
