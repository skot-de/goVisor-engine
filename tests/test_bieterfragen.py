"""Bieterfragen und Antworten — und die Studie, die sie für unerreichbar erklärt hat.

Das Übergabepapier führt sie als „stärkstes Ziel überhaupt" und behauptet zugleich, sie
„existieren in unseren Daten **nicht** und sind **nicht abgreifbar**". Die zitierte
Machbarkeitsstudie ist nicht falsch, sondern überholt: sie durchsuchte die eForms-Attribute der
**Bekanntmachungen** und fand dort zu Recht nichts. Die Q&A stecken in den **Unterlagen**.

    Wer eine Machbarkeitsstudie zitiert, prüft, WELCHE Quelle sie untersucht hat.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SKRIPT = WURZEL / "scripts" / "export_bieterfragen.py"
QUELLE = SKRIPT.read_text(encoding="utf-8")
CORE = (WURZEL / "web" / "lib" / "explorerCore.js").read_text(encoding="utf-8")
DATEI = WURZEL / "web" / "data" / "bieterfragen.json"
SONDE = WURZEL / "web" / "scripts" / "pruefe-bieterfragen.mjs"


def _modul():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_bf", SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _block(name: str) -> str:
    rest = CORE[CORE.index(f"function {name}("):]
    return rest[:rest.index("\n}")]


# ── die Extraktion ──────────────────────────────────────────────────────────────────────

def test_marke_findet_beide_schreibweisen():
    m = _modul()
    for text in ("\nFrage 1: Ist das gefordert?", "\nFrage: Ist das gefordert?",
                 "\nFrage Nr. 12: Ist das gefordert?", "\nZu Frage 3: Ja, das ist gefordert."):
        assert m.MARKE.search(text), text


def test_einleitungssaetze_fallen_raus():
    """⚠ „Im Folgenden finden Sie die Antwort zu Ihrer Frage:" ist keine Auskunft, sondern der
    Satz davor. Ohne diesen Filter stand er als erster Abschnitt im Block."""
    m = _modul()
    lang = "x" * 200
    assert m._abschnitte("\nFrage: Im Folgenden finden Sie die Antwort " + lang) == []
    assert m._abschnitte("\nFrage: Ist die Umladestation täglich leerzufahren? " + lang)


def test_zu_kurze_abschnitte_fallen_raus():
    """Ein Abschnitt von 43 Zeichen („Ein Schranksystem ist nicht mehr gefordert?") ist ohne
    den Zusammenhang, in dem er steht, keine Auskunft."""
    m = _modul()
    assert m.MIND_ZEICHEN >= 80
    assert m._abschnitte("\nFrage 1: Zu kurz.") == []


def test_entdubliert_ueber_den_text_nicht_den_dateinamen():
    """⚠ DIE FALLE: derselbe Bieterfragenkatalog liegt als Stand 10.08., 13.08. und 20.08. im
    Paket. Die Dateinamen unterscheiden sich, der Inhalt nicht — gemessen 264 Marken statt 66.
    Entdubliert wird deshalb über den Abschnittstext."""
    k = QUELLE[QUELLE.index("def main("):]
    assert "setdefault(stueck, _kurz(datei))" in k, "die Entdublierung hängt nicht am Text"
    assert "setdefault(_kurz(datei)" not in k
    if DATEI.exists():
        d = json.loads(DATEI.read_text(encoding="utf-8"))
        for v in d.values():
            texte = [x["text"] for x in v["auszug"]]
            assert len(texte) == len(set(texte)), "doppelte Abschnitte im Auszug"


# ── die Aussage ─────────────────────────────────────────────────────────────────────────

def test_behauptet_keine_frage_antwort_zuordnung():
    """⚠ Die Marke trennt Abschnitte, sie ordnet sie nicht: nur 35 % enthalten überhaupt ein
    Fragezeichen, der Rest sind Antworten oder Fortsetzungen. Eine Tabelle mit den Spalten
    „Frage" und „Antwort" behauptete eine Ordnung, die die Daten nicht hergeben."""
    b = _block("renderBieterfragen")
    assert "Abschnitt" in b, "der Block nennt sie nicht Abschnitte"
    assert not re.search(r'"[^"]*\bFrage\b[^"]*"\s*,\s*"[^"]*\bAntwort\b', b), "Paar-Zuordnung behauptet"


def test_nennt_die_rechtslage_und_die_datei():
    """Warum das den Leser angeht (§ 20 Abs. 3 EU-VgV: gilt für alle Bieter) und wo er
    nachschlagen kann."""
    b = _block("renderBieterfragen")
    assert "allen Bietern zugänglich" in b
    assert "esc(x.datei)" in b and "esc(x.text)" in b


# ── die Sonde ───────────────────────────────────────────────────────────────────────────

def test_die_sonde_faehrt_die_echte_funktion():
    """⚠ Die Nachbarsonde `pruefe-marktwert.mjs` warnt vor Abschriften und ist selbst eine.
    Diese hier schneidet `renderBieterfragen` aus `explorerCore.js` heraus und führt sie aus —
    fällt die Funktion weg, schlägt die Sonde fehl statt still weiterzulaufen."""
    txt = SONDE.read_text(encoding="utf-8")
    assert "explorerCore.js" in txt and "renderBieterfragen" in txt
    assert "new Function" in txt, "die Sonde schreibt die Funktion ab, statt sie zu benutzen"


def test_die_sonde_laeuft_gruen():
    """⚠ Sie trägt an diesem Tag die Last: der Browser-Durchgang war nicht möglich, weil die
    Anmeldung beim Neustart des Dev-Servers verloren ging. Sie prüft die Escapung auf echtem
    Text — 6 von 1.712 Abschnitten enthalten `<`, `>` oder `&`, darunter ein kaputtes `&n`."""
    if not shutil.which("node") or not DATEI.exists():
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stderr[-400:]
    assert "0 ungeschuetzte Zeichen" in r.stdout


# ── Ausliefergut ────────────────────────────────────────────────────────────────────────

def test_ausgabe_haelt_die_form():
    if not DATEI.exists():
        return
    m = _modul()
    d = json.loads(DATEI.read_text(encoding="utf-8"))
    assert d
    for v in d.values():
        assert set(v) == {"n", "dateien", "nDateien", "auszug"}
        assert 0 < len(v["auszug"]) <= m.MAX_JE_LEAD <= v["n"] or len(v["auszug"]) == v["n"]
        for x in v["auszug"]:
            assert set(x) == {"text", "datei"}
            assert m.MIND_ZEICHEN <= len(x["text"]) <= m.MAX_ZEICHEN


def test_steht_im_verzeichnis():
    from govisor import kennzahlen as K
    k = [x for x in K.ALLE if x.schluessel == "bieterfragen"]
    assert k, "nicht im Verzeichnis — genau so verschwindet Gebautes lautlos"
    assert k[0].bezug == "keine"
