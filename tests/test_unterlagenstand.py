"""Änderungen an den Vergabeunterlagen — und die Kennzahl, die dafür nicht rechenbar ist.

Das Übergabepapier führt eine „Anforderungs-Drift" (dieselbe Stelle, zwei Runden). Die ist mit
den heutigen Daten strukturell nicht rechenbar: `contract_succession` und `doc_checklist` sind
disjunkt, weil Unterlagen nur während laufender Frist existieren und ein Vorgänger per
Definition abgeschlossen ist. Gebaut ist stattdessen die Drift INNERHALB des Verfahrens — sie
ist früher da und näher an der Entscheidung.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SKRIPT = WURZEL / "scripts" / "export_unterlagenstand.py"
QUELLE = SKRIPT.read_text(encoding="utf-8")
CORE = (WURZEL / "web" / "lib" / "explorerCore.js").read_text(encoding="utf-8")
DATEI = WURZEL / "web" / "data" / "unterlagenstand.json"
SONDE = WURZEL / "web" / "scripts" / "pruefe-unterlagenstand.mjs"


def _modul():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_us", SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _block(name: str) -> str:
    rest = CORE[CORE.index(f"function {name}("):]
    return rest[:rest.index("\n}")]


# ── die Falle, an der die erste Messung scheiterte ──────────────────────────────────────

def test_die_fassung_wird_im_ganzen_pfad_normalisiert():
    """⚠ DIE FALLE. Der Pfad lautet `Z42-2025-0209_Version 1.zip::Anlage 510-…` — die Fassung
    steckt AUCH im ZIP-Namen. Wer nur das Verzeichnis `Version 1/` normalisiert, hält jede
    Datei der neuen Fassung für neu: gemessen „56 neu, 54 weg", von denen 47 byte-gleich waren.
    Der dritte Namensartefakt an einem Tag, nach den Lastgängen und den Katalog-Ständen."""
    m = _modul()
    a = "Z42-2025-0209_Version 1.zip::Anlage 510-5 - Nachweis.pdf"
    b = "Z42-2025-0209_Version 3.zip::Anlage 510-5 - Nachweis.pdf"
    assert m._ohne_version(a) == m._ohne_version(b), "die Fassung im ZIP-Namen bleibt stehen"
    assert m._version(a) == 1 and m._version(b) == 3
    c = "Vergabeunterlagen/Version 10/26_Bieterfragen.pdf"
    assert m._version(c) == 10 and "Version" not in m._ohne_version(c)
    assert m._version("Vergabeunterlagen/Leistungsverzeichnis.pdf") is None


def test_die_hoechste_fassung_im_pfad_gewinnt():
    """Ein Pfad kann die Fassung zweimal tragen (ZIP-Name UND Verzeichnis)."""
    m = _modul()
    assert m._version("X_Version 2.zip::Vergabeunterlagen/Version 2/a.pdf") == 2


# ── die Vergleichsrichtung ──────────────────────────────────────────────────────────────

def test_verglichen_wird_der_letzte_schritt():
    """⚠ Nicht Fassung 1 gegen die neueste: wer die Unterlagen gestern gezogen hat, will
    wissen, was seitdem passiert ist. Über alle Fassungen summiert ginge das Wichtige unter
    (Median 3 Dateien je Schritt, max 37)."""
    k = QUELLE[QUELLE.index("def main("):]
    assert "stufen[-2]" in k and "stufen[-1]" in k, "es wird nicht der letzte Schritt verglichen"
    assert "stufen[0]" not in k, "vergleicht gegen die erste Fassung"


def test_geaendert_wird_benannt_neu_nur_gezaehlt():
    """⚠ „Geändert" ist der gefährliche Fall: gleicher Dateiname, anderer Inhalt. Wer die Datei
    schon hat, sieht keinen Anlass, sie noch einmal zu ziehen. Eine neue Datei fällt dagegen
    beim Blick in die Liste auf."""
    b = _block("renderUnterlagenstand")
    assert "u.geaendert" in b and "esc(x)" in b, "die geänderten Dateien werden nicht genannt"
    assert "u.neu.map" not in b, "Neuzugänge werden namentlich aufgeführt statt gezählt"


def test_schweigt_ohne_aenderung():
    b = _block("renderUnterlagenstand")
    assert "if(!u || !(u.nGeaendert || u.nNeu || u.nWeg)) return ''" in b


# ── die Abgrenzung zur Übergabe ─────────────────────────────────────────────────────────

def test_anforderungsdrift_bleibt_offen():
    """⚠ Sie wird NICHT abgehakt. Das Papier meint zwei Runden derselben Stelle; das ist etwas
    anderes und mit den heutigen Daten nicht rechenbar. Wer es hier abhakt, verliert die
    Information, dass die Aufbewahrung von Dokumenten nach Zuschlag noch fehlt."""
    from govisor import kennzahlen as K
    offen = {x.schluessel for x in K.ALLE if x.flaeche == "geplant"}
    assert "anforderungsDrift" in offen, "die nicht rechenbare Kennzahl wurde stillschweigend abgehakt"
    gebaut = [x for x in K.ALLE if x.schluessel == "unterlagenAenderung"]
    assert gebaut and gebaut[0].bezug == "vorwert"


def test_der_grund_steht_im_verzeichnis():
    """Damit die nächste Sitzung nicht dieselbe Sackgasse noch einmal ausmisst."""
    txt = (WURZEL / "govisor" / "kennzahlen.py").read_text(encoding="utf-8")
    stelle = txt[txt.index("_UNTERLAGENSTAND") - 2200:txt.index("_UNTERLAGENSTAND")]
    assert "contract_succession" in stelle and "0 Paare" in stelle


def test_huerdenwirkung_bleibt_offen_mit_grund():
    """⚠ ZWEITER NEGATIVBEFUND, gemessen am 2026-09-02. Die Wirkung von Hürden auf die
    Bieterzahl ist nicht da: über die Hürdenzahl kein Signal, je Anforderungsart nur der
    Lesetiefe-Effekt, und der einzige Treffer innerhalb einer Wertklasse dreht in den
    Nachbarklassen die Richtung um.

    Der Eintrag bleibt offen — aber der Grund steht daneben, damit die nächste Sitzung nicht
    dieselbe Messung noch einmal fährt und beim vorletzten Schritt stehenbleibt."""
    from govisor import kennzahlen as K
    offen = {x.schluessel for x in K.ALLE if x.flaeche == "geplant"}
    assert "wirkungHuerdenBieterzahl" in offen
    txt = (WURZEL / "govisor" / "kennzahlen.py").read_text(encoding="utf-8")
    assert "NEGATIVBEFUND" in txt and "Replikation" in txt.replace("REPLIKATION", "Replikation")


# ── die Sonde ───────────────────────────────────────────────────────────────────────────

def test_die_sonde_laeuft_gruen():
    if not shutil.which("node") or not DATEI.exists():
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stderr[-400:]
    assert "0 ungeschuetzte Zeichen" in r.stdout and "schweigt" in r.stdout


def test_ausgabe_haelt_die_form():
    if not DATEI.exists():
        return
    m = _modul()
    d = json.loads(DATEI.read_text(encoding="utf-8"))
    assert d
    for v in d.values():
        assert set(v) == {"version", "vorige", "nVersionen", "geaendert", "nGeaendert",
                          "neu", "nNeu", "nWeg"}
        assert v["version"] > v["vorige"] and v["nVersionen"] >= 2
        assert len(v["geaendert"]) <= m.MAX_NENNEN <= max(v["nGeaendert"], m.MAX_NENNEN)
        assert v["nGeaendert"] or v["nNeu"] or v["nWeg"], "Eintrag ohne Änderung"
