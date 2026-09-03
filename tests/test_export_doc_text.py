"""LB-Volltext: der zweite, feinere Merker — und was er nicht kaputtmachen darf.

`STAND` beantwortet „hat sich die Quelle überhaupt gerührt". Im Nachtlauf lautet die Antwort
IMMER ja, weil die Dokument-Arbeiter rund um die Uhr in dieselbe Datei schreiben; der grobe
Wächter greift also nie. `JE_VORGANG_STAND` hält deshalb einen Fingerabdruck je Vorgang.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SKRIPT = WURZEL / "scripts" / "export_doc_text.py"
QUELLE = SKRIPT.read_text(encoding="utf-8")


def _modul():
    spec = importlib.util.spec_from_file_location("_edt", SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _modul()


def test_dateiname_laesst_keinen_pfadwechsel_zu():
    """Der Name wird zum URL-Pfad; ein `../` in einer Kennung wäre ein Pfadwechsel."""
    assert M._sicher("../../etc/passwd") == "etcpasswd"
    assert M._sicher("123_abc-DEF") == "123_abc-DEF"


def test_fehlende_merker_sind_kein_fehler(tmp_path, monkeypatch):
    """Der erste Lauf hat keine — er muss alles lesen, nicht abbrechen."""
    monkeypatch.setattr(M, "JE_VORGANG_STAND", tmp_path / "gibtesnicht.json")
    monkeypatch.setattr(M, "INDEX", tmp_path / "auchnicht.json")
    assert M._alte_abdruecke() == {}
    assert M._alter_index() == {}


def test_kaputte_merker_sind_kein_fehler(tmp_path, monkeypatch):
    """Lieber einmal zu viel lesen als abbrechen: das kostet Zeit, nicht Daten."""
    p = tmp_path / "kaputt.json"
    p.write_text("{kein json")
    monkeypatch.setattr(M, "JE_VORGANG_STAND", p)
    monkeypatch.setattr(M, "INDEX", p)
    assert M._alte_abdruecke() == {}
    assert M._alter_index() == {}


def test_dateinamen_stehen_im_fingerabdruck():
    """⚠ `ueberholte()` entscheidet ANHAND DER NAMEN, welche Fassung ausgeliefert wird. Ein
    Nachtrag, der eine Datei ersetzt, kann Zeilenzahl und Zeichensumme unverändert lassen
    und trotzdem ein anderes Ergebnis erzeugen."""
    kern = QUELLE.split("def _abdruecke(")[1].split("\ndef ")[0]
    assert "string_agg(file" in kern
    assert "md5(" in kern


def test_fingerabdruck_fasst_den_text_nicht_an():
    """Der Sinn der Sache: 817 MB nicht durch den Speicher ziehen, um festzustellen, dass
    sich nichts geändert hat. `n_chars` steht ohnehin in der Quelle."""
    kern = QUELLE.split("def _abdruecke(")[1].split("\ndef ")[0]
    assert "sum(n_chars)" in kern
    assert "length(text)) " not in kern and "sum(length(text))" not in kern


def test_geprueft_und_nichts_auszuliefern_gilt_als_erledigt():
    """⚠ Ein Vorgang, dessen Dateien alle als überholt gelten, steht in KEINEM Index. Er
    darf trotzdem als erledigt gelten, sonst wird er jede Nacht erneut gelesen — genau
    diesen Fehler hatte ich am selben Tag in `extract_positions.py` schon einmal gebaut.
    Es entscheidet allein der Fingerabdruck."""
    kern = QUELLE.split("def main(")[1]
    assert "unveraendert = {n for n, fa in abdruecke.items() if alt_abdruck.get(n) == fa}" in kern


def test_uebernommene_dateien_gelten_nicht_als_verwaist():
    """Sonst löscht der Lauf beim Übernehmen genau die Dateien, die er behalten wollte."""
    kern = QUELLE.split("def main(")[1]
    i_disc = kern.index("vorhanden.discard(_sicher(nid))")
    i_del = kern.index("for verwaist in vorhanden:")
    assert i_disc < i_del


def test_merker_wird_nach_der_ausgabe_geschrieben():
    """Bricht der Lauf dazwischen ab, wird beim nächsten Mal zu viel gelesen — Zeit, keine
    Daten. Andersherum gälten Vorgänge als fertig, deren Zeilen nie geschrieben wurden."""
    kern = QUELLE.split("def main(")[1]
    assert kern.index("INDEX.write_text") < kern.index("JE_VORGANG_STAND.write_text")


def test_erzwingen_umgeht_beide_merker():
    kern = QUELLE.split("def main(")[1]
    assert "{} if a.erzwingen else _alte_abdruecke()" in kern
    assert "{} if a.erzwingen else _alter_index()" in kern


def test_zeichenzahl_kommt_aus_dem_index():
    """⚠ `zeichen_gesamt` zählt nur, was DIESER Lauf verarbeitet hat. Seit Unverändertes
    übernommen wird, meldete die Zeile „0 Zeichen gesamt" neben einem Index mit vier
    Milliarden. Eine Zahl, die bei gesunder Lage Null sagt, lässt einen kaputten Lauf wie
    einen gesunden aussehen."""
    kern = QUELLE.split("def main(")[1]
    assert 'gesamt = sum(int(v.get("chars") or 0) for v in index.values())' in kern
    assert "{zeichen_gesamt:,} Zeichen gesamt" not in kern
