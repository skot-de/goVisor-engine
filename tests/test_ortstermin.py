"""Pflicht-Ortstermin außerhalb des eigenen Gebiets: ein Zulassungsgrund, kein Detail.

Wer nicht erscheint, darf nicht bieten. Innerhalb des eigenen Gebiets ist das ein Vormittag;
weit ausserhalb kippt es die Rechnung, und zwar bevor jemand die Unterlagen liest.
"""
from __future__ import annotations

from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
WEB = WURZEL / "web"


def _ohne_kommentar(text: str) -> str:
    raus, im_block = [], False
    for z in text.splitlines():
        t = z.strip()
        if t.startswith("/*"):
            im_block = True
        if im_block:
            if "*/" in t:
                im_block = False
            continue
        if t.startswith("//") or t.startswith("*"):
            continue
        raus.append(z)
    return "\n".join(raus)


ENGINE = _ohne_kommentar((WEB / "lib" / "profileEngine.js").read_text(encoding="utf-8"))


def test_der_blocker_existiert():
    assert "'ortstermin'" in ENGINE
    assert "ortsterminPflicht === true" in ENGINE


def test_er_greift_nur_ausserhalb_des_gebiets():
    """Ein Pflichttermin im eigenen Gebiet ist normal und keine Meldung wert. Ohne die
    Bedingung stünde der Hinweis an tausenden Vorgängen und wäre binnen einer Woche Tapete."""
    block = ENGINE[ENGINE.index("ortsterminPflicht"):]
    block = block[:block.index("}")]
    assert "region === 'no'" in block


def test_er_schliesst_nicht_aus():
    """⚠ Man KANN hinfahren, und bei einem grossen Auftrag lohnt es sich. Die Relevanz zu
    nullen hiesse, dem Nutzer eine Entscheidung abzunehmen, die ihm gehört. `hartBlock`
    hört weiterhin nur auf die Bürgschaft."""
    assert "b.art === 'buergschaft'" in ENGINE or "b.art==='buergschaft'" in ENGINE
    hart = ENGINE[ENGINE.index("hartBlock"):]
    hart = hart[:hart.index("\n")]
    assert "ortstermin" not in hart


def test_dreiwertig_gelesen():
    """⚠ `null` heisst „die Unterlagen sagen nichts", nicht „kein Termin". Ein `if (x)` statt
    `=== true` wäre hier dasselbe Ergebnis, aber die falsche Aussage — und beim nächsten
    Feld, wo `false` vorkommt, ein Fehler."""
    assert "ortsterminPflicht === true" in ENGINE


def test_der_export_traegt_das_feld_in_die_liste():
    """⚠ Ein Blocker, den man erst nach dem Öffnen sieht, filtert nichts. Das Signal muss
    schon im Lead-Export liegen, nicht erst in `lbSignals` der Detailansicht."""
    exp = (WURZEL / "scripts" / "export_web_leads.py").read_text(encoding="utf-8")
    assert "site_visit_mandatory AS doc_ortstermin_pflicht" in exp
    assert '"ortsterminPflicht"' in exp
    # Nur setzen, wenn ueberhaupt ein Termin erkannt wurde — sonst waere „nicht
    # verpflichtend" eine Aussage ueber einen Termin, den es nicht gibt.
    block = exp[exp.index('"ortsterminPflicht"'):]
    assert 'g("doc_ortstermin")' in block[:220]


def test_das_briefing_zaehlt_sie():
    """Der Leerzustand ist die Stelle, an der Blocker zu einer Arbeitsliste werden."""
    dp = (WEB / "components" / "explorer" / "DetailPanel.tsx").read_text(encoding="utf-8")
    assert 'blockerArt(l, "ortstermin")' in dp


def test_kein_gedankenstrich_im_oberflaechentext():
    """Sven-Vorgabe. ⚠ Beim Bauen genau hier zugeschlagen: der erste Entwurf trug einen."""
    zeilen = [z for z in (WEB / "lib" / "profileEngine.js").read_text(encoding="utf-8").splitlines()
              if "blocker.push" in z or "text:" in z]
    for z in zeilen:
        assert "—" not in z and "–" not in z, f"Gedankenstrich im Oberflächentext: {z.strip()[:80]}"
