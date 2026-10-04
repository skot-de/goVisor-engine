"""Das Bausteinformat, sprachuebergreifend festgenagelt.

⚠ **Warum diese Suite ungewoehnlich aussieht.** Das Verschluesselungsformat existiert zweimal:
`web/lib/blockCrypto.ts` und `govisor/blockcrypto.py`. Ein Python-Rundlauf (verschluesseln,
entschluesseln, vergleichen) wuerde **jede** symmetrische Verwechslung durchlassen — etwa das
Auth-Tag hinten statt vorn. Python koennte sein eigenes Chiffrat weiterhin lesen, Node nicht, und
es faellt erst im Produkt auf.

Deshalb startet diese Suite einen echten `node`-Prozess und laesst ihn die **echte
TypeScript-Datei** laden (Node 23+ versteht TypeScript ohne Uebersetzungsschritt). Geprueft werden
beide Richtungen.
"""
import base64
import json
import os
import pathlib
import shutil
import subprocess

import pytest

from govisor import blockcrypto as bc

WEB = pathlib.Path(__file__).resolve().parent.parent / "web"
KEK = base64.b64encode(bytes(range(32))).decode()        # fest, damit Fehler reproduzierbar sind
TEXTE = [
    "Referenz Stadtwerke Musterstadt, 2024",
    "Umlaute und Sonderzeichen: ä ö ü ß € — „Anführungszeichen“",
    "x" * 5000,                                           # mehrere Bloecke
    "",                                                   # Grenzfall: leerer Inhalt
]


@pytest.fixture(autouse=True)
def _kek(monkeypatch):
    monkeypatch.setenv("BLOCKS_KEK", KEK)


def _node(skript: str, *args: str) -> str:
    """Fuehrt ein ESM-Schnipsel in `web/` aus und gibt stdout zurueck.

    `stderr` wird verworfen: Node warnt dort ueber das fehlende `"type": "module"` in der
    `package.json`, und diese Warnung ist kein Fehler.
    """
    p = subprocess.run(["node", "--input-type=module", "-e", skript, "--", *args],
                       cwd=WEB, capture_output=True, text=True,
                       env={**os.environ, "BLOCKS_KEK": KEK})
    if p.returncode != 0:
        raise AssertionError(f"node brach ab: {p.stderr.strip()[-400:]}")
    return p.stdout.strip()


node_fehlt = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node fehlt — der sprachuebergreifende Nachweis entfaellt, "
           "das Format ist dann NICHT gegen Drift gesichert")


# ── Die beiden Richtungen ────────────────────────────────────────────────────────────────────

@node_fehlt
@pytest.mark.parametrize("text", TEXTE)
def test_python_verschluesselt_node_liest(text):
    hex_ = bc.verschluessele(text).hex()
    raus = _node(
        "const {entschluessele} = await import('./lib/blockCrypto.ts');"
        "const h = process.argv[process.argv.length - 1];"
        "process.stdout.write(JSON.stringify(entschluessele(Buffer.from(h, 'hex'))));",
        hex_)
    assert json.loads(raus) == text


@node_fehlt
@pytest.mark.parametrize("text", TEXTE)
def test_node_verschluesselt_python_liest(text):
    hex_ = _node(
        "const {verschluessele} = await import('./lib/blockCrypto.ts');"
        "const t = JSON.parse(process.argv[process.argv.length - 1]);"
        "process.stdout.write(verschluessele(t).toString('hex'));",
        json.dumps(text))
    assert bc.entschluessele(bytes.fromhex(hex_)) == text


@node_fehlt
def test_beide_seiten_erzeugen_dieselbe_laenge():
    """Gleiche Nutzlast, gleiche Kopflaenge — faellt die Struktur auseinander, faellt es hier auf."""
    text = "Pruefsatz mit genau dieser Laenge."
    py = len(bc.verschluessele(text))
    nd = int(_node(
        "const {verschluessele} = await import('./lib/blockCrypto.ts');"
        "process.stdout.write(String(verschluessele('Pruefsatz mit genau dieser Laenge.').length));"))
    assert py == nd == 89 + len(text.encode())


# ── Eigenschaften, die auch ohne node gelten ─────────────────────────────────────────────────

@pytest.mark.parametrize("text", TEXTE)
def test_python_rundlauf(text):
    assert bc.entschluessele(bc.verschluessele(text)) == text


def test_ohne_schluessel_wird_nichts_verschluesselt(monkeypatch):
    """Kein stiller Rueckfall auf Klartext — das waere der schlimmste denkbare Ausgang."""
    monkeypatch.delenv("BLOCKS_KEK", raising=False)
    with pytest.raises(bc.KeinSchluessel):
        bc.verschluessele("geheim")


def test_falsche_schluessellaenge_wird_abgewiesen(monkeypatch):
    monkeypatch.setenv("BLOCKS_KEK", base64.b64encode(b"zu kurz").decode())
    with pytest.raises(ValueError, match="32 Byte"):
        bc.verschluessele("geheim")


def test_fremde_fassung_wird_abgewiesen():
    daten = bytearray(bc.verschluessele("x"))
    daten[0] = 9
    with pytest.raises(ValueError, match="Fassung"):
        bc.entschluessele(bytes(daten))


def test_zu_kurzes_chiffrat_wird_abgewiesen():
    with pytest.raises(ValueError, match="zu kurz"):
        bc.entschluessele(b"\x01" * 50)


def test_verfaelschter_inhalt_fliegt_auf():
    """GCM ist authentifiziert: ein gekipptes Bit darf nicht stillschweigend durchgehen."""
    daten = bytearray(bc.verschluessele("Referenz Stadtwerke"))
    daten[-1] ^= 0x01
    with pytest.raises(Exception):
        bc.entschluessele(bytes(daten))


def test_hex_transport_haelt():
    daten = bc.verschluessele("Referenz mit bytea-Reise")
    assert bc.aus_hex(bc.zu_hex(daten)) == daten
    assert bc.zu_hex(daten).startswith("\\x")


def test_zwei_chiffrate_desselben_textes_unterscheiden_sich():
    """Frischer Datenschluessel und frischer IV je Satz — sonst verraet die Gleichheit den Inhalt."""
    a, b = bc.verschluessele("gleicher Text"), bc.verschluessele("gleicher Text")
    assert a != b
    assert bc.entschluessele(a) == bc.entschluessele(b) == "gleicher Text"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
