"""Der Word-Export — von einem fremden Leser geprueft, nicht von unserem eigenen XML.

⚠ **Warum diese Suite so gebaut ist.** Eine `.docx` ist ein ZIP mit festgelegter XML-Struktur.
Fehlt ein Teil oder stimmt ein Namensraum nicht, oeffnet Word die Datei **gar nicht** — ohne
brauchbare Meldung. Pruefte diese Suite nur, ob unser eigenes XML das enthaelt, was wir
hineingeschrieben haben, bewiese sie nichts: der Fehler steckt immer in der Struktur, nicht im
Inhalt.

Deshalb drei Stufen, jede strenger als die vorige:

1. Das Paket enthaelt alle fuenf Pflichtteile.
2. Jeder XML-Teil ist wohlgeformt (sonst ist die Datei schon formal kaputt).
3. **`textutil` liest sie.** Das ist der Dokumentwandler von macOS, ein von uns voellig
   unabhaengiger Leser. Kommt der Text dort heraus, hat ein echter Leser die Datei akzeptiert.

⚠ **Und warum Stufe 1 trotz Stufe 3 bleibt, gemessen bei der Selbstprobe am 2026-10-05:** laesst
man `word/_rels/document.xml.rels` weg, **liest `textutil` die Datei weiterhin anstandslos** —
Word waere strenger. Ein nachsichtiger Leser beweist also nicht, dass die Datei in Ordnung ist.
Erst die Strukturpruefung faengt die Luecke. Wer hier spaeter aufraeumt und Stufe 1 als
„redundant" streicht, nimmt genau den Teil weg, der den Fehler findet.
"""
import pathlib
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile

import pytest

WEB = pathlib.Path(__file__).resolve().parent.parent / "web"
PFLICHT = ["[Content_Types].xml", "_rels/.rels", "word/document.xml",
           "word/styles.xml", "word/_rels/document.xml.rels"]

node_fehlt = pytest.mark.skipif(shutil.which("node") is None, reason="node fehlt")
textutil_fehlt = pytest.mark.skipif(
    shutil.which("textutil") is None,
    reason="textutil fehlt — der UNABHAENGIGE Lesetest entfaellt, die Datei ist dann nur "
           "gegen unsere eigenen Erwartungen geprueft")


def _baue(tmp_path, titel, teile) -> pathlib.Path:
    """Laesst Node die echte `lib/docx.ts` benutzen und legt die Datei ab."""
    import json
    ziel = tmp_path / "ausgabe.docx"
    skript = (
        "const {writeFileSync} = await import('node:fs');"
        "const {baueDocx} = await import('./lib/docx.ts');"
        "const [titel, teile, ziel] = process.argv.slice(-3);"
        "writeFileSync(ziel, baueDocx(titel, JSON.parse(teile)));"
    )
    p = subprocess.run(["node", "--input-type=module", "-e", skript, "--",
                        titel, json.dumps(teile), str(ziel)],
                       cwd=WEB, capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(f"node brach ab: {p.stderr.strip()[-500:]}")
    return ziel


def _text(datei: pathlib.Path) -> str:
    """Liest die Datei mit textutil — also mit einem fremden Leser."""
    raus = datei.with_suffix(".txt")
    p = subprocess.run(["textutil", "-convert", "txt", "-output", str(raus), str(datei)],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(f"textutil konnte die Datei nicht lesen: {p.stderr.strip()[:300]}")
    return raus.read_text(encoding="utf-8", errors="replace")


BEISPIEL = [
    {"art": "ueberschrift", "text": "1. Unternehmen und Referenzen", "ebene": 2},
    {"art": "absatz", "text": "Fuer die Stadtwerke haben wir 140 Trafostationen gewartet."},
    {"art": "absatz", "text": "Zeile eins\nZeile zwei"},
]


# ── Stufe 1 und 2: Struktur ──────────────────────────────────────────────────────────────────

@node_fehlt
def test_alle_pflichtteile_sind_da(tmp_path):
    with zipfile.ZipFile(_baue(tmp_path, "Angebot", BEISPIEL)) as z:
        fehlend = [t for t in PFLICHT if t not in z.namelist()]
    assert not fehlend, f"fehlende Teile: {fehlend}"


@node_fehlt
def test_jeder_xml_teil_ist_wohlgeformt(tmp_path):
    with zipfile.ZipFile(_baue(tmp_path, "Angebot", BEISPIEL)) as z:
        for name in z.namelist():
            ET.fromstring(z.read(name))      # wirft bei kaputtem XML


@node_fehlt
def test_mehrzeiliger_text_wird_zu_mehreren_absaetzen(tmp_path):
    """Ein `w:br` wuerde den Block an eine Formatvorlage haengen; getrennte Absaetze nicht."""
    with zipfile.ZipFile(_baue(tmp_path, "T", [{"art": "absatz", "text": "a\nb\nc"}])) as z:
        xml = z.read("word/document.xml").decode()
    assert xml.count("<w:p>") >= 4, "Titel plus drei Zeilen erwartet"


# ── Stufe 3: ein fremder Leser ───────────────────────────────────────────────────────────────

@node_fehlt
@textutil_fehlt
def test_textutil_liest_die_datei(tmp_path):
    t = _text(_baue(tmp_path, "Angebot Schulsanierung", BEISPIEL))
    assert "Angebot Schulsanierung" in t
    assert "1. Unternehmen und Referenzen" in t
    assert "140 Trafostationen" in t
    assert "Zeile eins" in t and "Zeile zwei" in t


@node_fehlt
@textutil_fehlt
def test_umlaute_und_sonderzeichen_ueberleben(tmp_path):
    teile = [{"art": "absatz",
              "text": "Gebäude & Außenanlagen <Los 3>, Preis \"netto\", 100 % Verfügbarkeit"}]
    t = _text(_baue(tmp_path, "Prüfung äöü ß", teile))
    assert "Prüfung äöü ß" in t
    assert "Gebäude & Außenanlagen <Los 3>" in t, t[:400]
    assert "100 % Verfügbarkeit" in t


@node_fehlt
@textutil_fehlt
def test_steuerzeichen_machen_die_datei_nicht_kaputt(tmp_path):
    """⚠ Ein einziges verbotenes Steuerzeichen — etwa aus einer kopierten PDF — macht die Datei
    unlesbar, und Word sagt nur „Inhalt unlesbar". Sie werden vorher entfernt."""
    teile = [{"art": "absatz", "text": "vor\x00\x07nach"}]
    t = _text(_baue(tmp_path, "Steuerzeichen", teile))
    assert "vornach" in t.replace("\u0000", ""), t[:200]


@node_fehlt
@textutil_fehlt
def test_leerer_titel_und_leeres_dokument(tmp_path):
    t = _text(_baue(tmp_path, "", []))
    assert "Ohne Titel" in t


# ── Dateiname ────────────────────────────────────────────────────────────────────────────────

@node_fehlt
@pytest.mark.parametrize("titel,erwartet", [
    ("Angebot Schulsanierung", "Angebot-Schulsanierung.docx"),
    ("Los 3 / Teil 2: Dach", "Los-3-Teil-2-Dach.docx"),
    ("", "Dokument.docx"),
    ("///", "Dokument.docx"),
])
def test_dateiname(tmp_path, titel, erwartet):
    import json
    skript = ("const {dateiname} = await import('./lib/docx.ts');"
              "process.stdout.write(dateiname(JSON.parse(process.argv[process.argv.length-1])));")
    p = subprocess.run(["node", "--input-type=module", "-e", skript, "--", json.dumps(titel)],
                       cwd=WEB, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[-300:]
    assert p.stdout.strip() == erwartet


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
