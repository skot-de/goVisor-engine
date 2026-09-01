"""Der Beleg aus dem Dokument, und die Sicherheitsregel, die er mitbringt.

⚠ Diese Datei steht vor allem gegen EIN Loch. Damit der Beleg-Span durchkommt, ist das
`esc()` aus der Zeilendarstellung verschwunden. Seitdem muss JEDE `rows.push`-Stelle selbst
escapen. Zertifikatsnamen und das Bindefrist-Datum kommen aus Vergabeunterlagen, also aus
Text, den jemand anderes geschrieben hat.
"""
from __future__ import annotations

from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
CORE = (WURZEL / "web" / "lib" / "explorerCore.js").read_text(encoding="utf-8")


def _anforderungsblock() -> str:
    return CORE[CORE.index("const anforderungen"):CORE.index("// Leistungsumfang")]


def test_jede_zeile_escaped_selbst():
    """⚠ Der eigentliche Wächter. Eine neue Zeile ohne `esc()` ist ein XSS über den Inhalt
    einer Vergabeunterlage — und sie sieht im Code völlig harmlos aus."""
    zeilen = _anforderungsblock().splitlines()
    offen = []
    for i, z in enumerate(zeilen):
        if "rows.push([" not in z:
            continue
        ganz = " ".join(zeilen[i:i + 3])
        if "esc(" not in ganz and "mitBeleg(" not in ganz:
            offen.append(z.strip()[:80])
    assert not offen, f"ungeschützte Zeilen im Anforderungs-Block: {offen}"


def test_der_beleg_wird_escaped():
    """Das Zitat selbst kommt aus dem Dokument und geht in ein `title`-Attribut."""
    block = _anforderungsblock()
    stelle = block[block.index("const mitBeleg"):]
    stelle = stelle[:stelle.index("};")]
    assert 'title="${esc(' in stelle, "das Zitat landet ungeschützt im Attribut"


def test_kein_beleg_kein_span():
    """Ohne Zitat bleibt die Zeile schlicht. Eine gepunktete Linie ohne Inhalt dahinter wäre
    ein Versprechen, das beim Zeigen bricht."""
    block = _anforderungsblock()
    stelle = block[block.index("const mitBeleg"):]
    stelle = stelle[:stelle.index("};")]
    assert "return z ?" in stelle and ": esc(wert)" in stelle


def test_defektes_json_nimmt_die_seite_nicht_mit():
    """`evidence` ist Text aus dem Parquet. Ein kaputter Satz darf den ganzen Block kosten."""
    block = _anforderungsblock()
    assert "try {" in block and "catch" in block
    assert "beleg = {}" in block


def test_evidence_steht_im_verzeichnis():
    """⚠ Es war zuerst ABSICHTLICH nicht drin („kein Messwert"), und genau deshalb hat
    niemand gemerkt, dass es nie ankommt. Die Parallelsitzung fand es am selben Tag als
    „gebaut, aber nicht verdrahtet"."""
    from govisor import kennzahlen as kz
    ev = [k for k in kz.DOC_SIGNALE if k.spalte == "evidence"]
    assert ev, "evidence fehlt im Verzeichnis"
    assert ev[0].bezug == "keine", "der Beleg vergleicht nichts, er belegt"
