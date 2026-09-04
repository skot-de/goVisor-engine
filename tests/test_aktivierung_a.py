"""Aktivierung A: die Bitte um Unterlagen, dort wo wir nichts haben.

⚠ Der Kern ist nicht die Hochlade-Strecke — die gibt es samt eigenem Tagesdeckel und
ehrlicher Meldung, wenn er erreicht ist. Der Kern ist, dass die Bitte SPEZIFISCH wird: „ihr
wärt die ersten" ist ein anderer Satz als „dann geht es schneller", und er ist nur dort wahr,
wo wir wirklich nichts haben.
"""
from __future__ import annotations

from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
WEB = WURZEL / "web"
CORE = (WEB / "lib" / "explorerCore.js").read_text(encoding="utf-8")
EXPORT = (WURZEL / "scripts" / "export_web_leads.py").read_text(encoding="utf-8")


def test_die_bitte_haengt_an_einer_messung():
    """⚠ Kein fester Satz. „Aus Österreich haben wir keine einzige Unterlage" ist heute wahr
    und ist es an dem Tag nicht mehr, an dem die erste kommt. Ein hart geschriebener Satz
    würde ab dann lügen, ohne dass es jemand merkt."""
    assert "landOhneDocs" in CORE
    assert "_laender_ohne_unterlagen" in EXPORT
    assert '"landOhneDocs":' in EXPORT


def test_die_messung_zaehlt_wirklich():
    """Eine Datei, die es gibt, aber leer ist, zählt als „nichts" — sonst verschwände die
    Bitte, sobald jemand einen leeren Stub anlegt."""
    block = EXPORT[EXPORT.index("def _laender_ohne_unterlagen"):EXPORT.index("OHNE_UNTERLAGEN =")]
    assert "count(distinct notice_id)" in block
    assert "if not n:" in block, "eine leere Datei muss als fehlend gelten"


def test_alle_laender_werden_geprueft():
    """⚠ EU-weit-Grundsatz. Eine Messung, die nur DE kennt, meldet die anderen nie.

    ⚠ DIESER TEST PRUEFTE FRUEHER DIE FALSCHE SACHE. Er suchte die Literale „DE"/„AT"/„CH"
    im Quelltext des Blocks — und wurde damit rot, als die drei fest verdrahteten Tupel am
    2026-09-03 zu EINER Konstante zusammengefasst wurden. Der Code war besser geworden, der
    Waechter blind. Er prueft jetzt die Konstante selbst und dass der Block sie benutzt:
    das haelt dieselbe Zusicherung, ohne die Verdopplung zu erzwingen, die er eigentlich
    verhindern soll.
    """
    block = EXPORT[EXPORT.index("def _laender_ohne_unterlagen"):EXPORT.index("OHNE_UNTERLAGEN =")]
    assert "for land in LAENDER:" in block, "der Block muss die gemeinsame Liste benutzen"
    # ⚠ SEIT DEM 2026-09-04 LEITET DIE DATEI AB: `LAENDER = _AKTIV`. Auf Literale zu pruefen
    # hiesse jetzt, die Verdopplung zu ERZWINGEN, die der Umbau gerade beseitigt hat — genau
    # der Fehler, den dieser Test schon einmal gemacht hat (siehe Absatz oben).
    assert "laender import AKTIV" in EXPORT, "export_web_leads leitet die Laender nicht mehr ab"
    from govisor.laender import AKTIV
    for land in ("DE", "AT", "CH", "LU"):
        assert land in AKTIV, f"{land} fehlt in govisor.laender.AKTIV"


def test_die_hochladestrecke_bleibt_dieselbe():
    """Die Bitte ist ein anderer Text, kein zweiter Weg. Ein eigener Upload-Pfad wäre eine
    zweite Stelle, die altert."""
    block = CORE[CORE.index("l.landOhneDocs"):]
    block = block[:block.index("</section>`;")]
    assert "data-uploaddocs" in block and "data-upstatus" in block


def test_die_drei_fehlenden_arten_werden_erfragt():
    """⚠ Bis zum 2026-09-01 kannte diese Stelle nur die Zuschlagskriterien. Gemessen über
    8.675 Analysen fehlen drei Arten regelmässig: Zuschlagskriterien 5.978, Eignung 2.099,
    Aufforderung 1.431."""
    block = CORE[CORE.index("const FEHLT = {"):CORE.index("const fehlend =")]
    for art in ("zuschlagskriterien", "eignung", "aufforderung"):
        assert f"{art}:" in block, f"{art} wird nicht erfragt"


def test_die_bitte_ist_spezifisch():
    """⚠ „Ladet die Unterlagen hoch" hilft niemandem, der schon welche geschickt hat. Jede
    Bitte muss sagen, WELCHE Datei gebraucht wird."""
    block = CORE[CORE.index("const FEHLT = {"):CORE.index("const fehlend =")]
    for wort in ("Wertungsmatrix", "Eignungsformular", "Fristen und Formvorgaben"):
        assert wort in block, f"die Bitte nennt {wort} nicht"


def test_keine_sackgasse_mehr():
    """⚠ Vorher endete der Abschnitt mit „Bitte selbst prüfen" — richtig, aber der Nutzer
    erfuhr, dass etwas fehlt, und konnte nichts tun."""
    assert "Bitte selbst prüfen" not in CORE
    stelle = CORE[CORE.index("const offen = fehlend.length"):]
    stelle = stelle[:stelle.index("</details>`")]
    assert "data-uploaddocs" in stelle, "die Bitte hat keinen Knopf"


def test_die_sprungmarke_zaehlt_alle():
    """Eine „Offen 1" über drei Lücken wäre schlicht falsch."""
    assert "hasMissZ" not in CORE
    assert 'data-cljump="clg-offen"' in CORE
    stelle = CORE[CORE.index('data-cljump="clg-offen"') - 120:CORE.index('data-cljump="clg-offen"') + 160]
    assert "fehlend.length" in stelle


def test_der_deckel_und_die_ehrliche_meldung_stehen():
    """⚠ Regel 2 des Papiers: nie mehr versprechen, als wir halten. Beides war schon da, und
    es muss bleiben — ohne den eigenen Deckel liefe der Upload gegen den allgemeinen und
    hätte keinen Vorrang; ohne die Meldung stünde „gleich fertig", während nichts passiert."""
    up = (WURZEL / "scripts" / "process_upload.py").read_text(encoding="utf-8")
    assert 'zweck="upload"' in up
    assert "BudgetErschoepft" in up and "lbAnalyseWartet" in up
    llm = (WURZEL / "govisor" / "llm.py").read_text(encoding="utf-8")
    assert "UPLOAD_TAG_USD" in llm
