"""GAEB-Dateien aus fremden ZIPs duerfen keine lokalen Dateien ins Ergebnis ziehen (XXE).

⚠ DER BEFUND (2026-09-28, Pentest). `parse_gaeb` parste die Bytes einer heruntergeladenen
Vergabe-ZIP mit `etree.fromstring(data)` — dem lxml-Standardparser. Dessen historischer
Default `resolve_entities=True` loest externe Entities auf; eine vergiftete
`<!ENTITY x SYSTEM "file:///…/.secrets/openrouter.key">` waere in den geparsten Baum und
ueber die Positionen in `doc_positions` gelangt.

⚠ EHRLICHER STAND DER AUSNUTZBARKEIT. Auf der hier gemessenen lxml 6 / libxml2 2.14 weist
der Standardparser externe Entities BEREITS ab (neuer libxml2-Default). Die Luecke war also
auf dieser Bibliotheksversion nicht offen. Der Nachtlauf-Rechner kann eine aeltere Version
fahren, auf der der alte Default gilt — deshalb ist die Haertung richtig: sie macht die
Sicherheit ausdruecklich und versionsunabhaengig, statt sie dem Zufall der installierten
libxml2 zu ueberlassen.

Zwei Sorten Test, weil ein Laufzeittest allein hier keine Zaehne haette (auf dieser
Bibliothek wuerde auch der alte Code das Geheimnis nicht leaken — er wuerfe nur):
1. LAUFZEIT: die Sicherheitseigenschaft — eine XXE-Nutzlast bringt das Geheimnis NICHT ins
   Ergebnis, und ein harmloses GAEB mit vordefinierten Entities (&amp;) parst weiter sauber.
2. QUELLE: der gehaertete Parser steht wirklich im Code (Kommentare gestrippt, sonst schluege
   die Pruefung an ihrer eigenen Erklaerung an — s. [[waechter-messen-prosa-statt-code]]).
   Nimmt jemand die Flags heraus, faellt dieser Teil.
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
from govisor import docparse  # noqa: E402


def _xxe_bytes(geheim_pfad: str) -> bytes:
    # Der span-Tag ist einer der Textknoten, die parse_gaeb ausliest.
    return (
        '<?xml version="1.0"?>\n'
        f'<!DOCTYPE r [ <!ENTITY xxe SYSTEM "file://{geheim_pfad}"> ]>\n'
        '<GAEB><Item RNoPart="1"><span>&xxe;</span><Qty>1</Qty><QU>St</QU></Item></GAEB>'
    ).encode()


def test_xxe_nutzlast_zieht_kein_geheimnis_ins_ergebnis():
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("GEHEIM-openrouter-sk-xxe-9931")
        geheim = f.name
    try:
        roh = docparse.parse_gaeb(_xxe_bytes(geheim))
    finally:
        Path(geheim).unlink(missing_ok=True)
    # Egal ob der Parser die Entity leer laesst, wirft (→ Flat-Fallback) oder None gibt:
    # das Geheimnis darf NIRGENDS im Ergebnis stehen.
    text = "" if not roh else " ".join(
        f"{p.get('rno','')} {p.get('qty','')} {p.get('unit','')} {p.get('text','')}"
        for p in roh.get("positions", []))
    assert "GEHEIM-openrouter" not in text, f"XXE: lokales Geheimnis im Ergebnis: {text!r}"


def test_harmloses_gaeb_mit_vordefinierten_entities_parst_weiter():
    # &amp; ist eine VORDEFINIERTE XML-Entity — die bleibt trotz resolve_entities=False
    # erhalten. Ohne diese Zusicherung waere der Fix ein stiller Datenverlust.
    xml = ('<GAEB><Item RNoPart="1.1"><span>Kabel &amp; Zubehör</span>'
           '<Qty>3</Qty><QU>m</QU></Item></GAEB>').encode()
    roh = docparse.parse_gaeb(xml)
    assert roh and roh["positions"], "harmloses GAEB nicht mehr geparst"
    p = roh["positions"][0]
    assert p["rno"] == "1.1" and p["qty"] == "3" and p["unit"] == "m"
    assert "Kabel & Zubehör" in p["text"], f"vordefinierte Entity verloren: {p['text']!r}"


def test_der_gehaertete_parser_steht_wirklich_im_code():
    quelle = (WURZEL / "govisor" / "docparse.py").read_text(encoding="utf-8")
    # Kommentare strippen: Zeilen, die (nach Einrückung) mit # beginnen, UND inline-#.
    # (Kein # steckt hier in einem relevanten String-Literal.)
    ohne = "\n".join(re.sub(r"#.*$", "", z) for z in quelle.splitlines())
    i = ohne.index("def parse_gaeb(")
    j = ohne.index("def parse_gaeb_flat(")
    block = ohne[i:j]
    for flag in ("resolve_entities=False", "no_network=True", "load_dtd=False"):
        assert flag in block, f"Haertung fehlt im Code: {flag}"
    assert "etree.XMLParser(" in block, "kein expliziter Parser"
    # Der ungeschuetzte Aufruf darf NICHT zurueckkehren.
    assert "etree.fromstring(data)" not in block, "roher fromstring(data) ohne Parser wieder da"
