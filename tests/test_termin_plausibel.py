"""Was das Produkt über eine Laufzeit weiss, muss es auch sagen.

⚠ GEFUNDEN AM 2026-09-05. Die Qualitätsprüfung setzt `laufzeit_unplausibel`, wenn eine
Vertragslaufzeit nicht sein kann. Der Auslauf-Zweig des Lead-Baus liest das Flag; der Zweig
für OFFENE Ausschreibungen (f01/f02) behauptete stattdessen `true AS termin_plausibel`.

Folge, gemessen: 73 ausgelieferte f02-Leads trugen eine Vertragslaufzeit von 26 bis 169
Jahren (Median 48) — und `timing_source` stand auf `actual`, der Wert ging also UNMARKIERT
hinaus. Erkannt hatte das System sie längst: sie lagen in `review_queue`, einer Worklist mit
28.440 Einträgen, die kein Code und keine Oberfläche liest.

Das ist der Markenkern an genau der Stelle, an der er gilt: „Gemessenes ist gemessen,
Geschätztes ist markiert." Eine Laufzeit von 169 Jahren ist kein gemessener Wert, sondern
ein erkannter Datenfehler.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD = (ROOT / "govisor" / "gold.py").read_text(encoding="utf-8")


def _f02_zweig() -> str:
    """Der SELECT-Block für offene Ausschreibungen (f01/f02)."""
    i = GOLD.index("CASE n.notice_kind WHEN 'cn' THEN 'f02' ELSE 'f01' END AS source")
    return GOLD[i:i + 4000]


def test_der_offene_zweig_behauptet_plausibilitaet_nicht_mehr():
    """`true AS termin_plausibel` war eine Behauptung, keine Messung."""
    zweig = _f02_zweig()
    assert "true AS termin_plausibel" not in zweig, (
        "Der f01/f02-Zweig setzt `termin_plausibel` wieder fest auf true — damit gilt jede "
        "offene Ausschreibung als plausibel, auch die mit 169 Jahren Laufzeit.")
    assert "laufzeit_unplausibel" in zweig, (
        "Der Zweig liest die Qualitaetsflags nicht mehr.")


def test_beide_zweige_lesen_dieselbe_quelle():
    """Auslauf- und Offen-Zweig muessen dieselbe Aussage aus derselben Stelle nehmen.

    Zwei Wege, die dasselbe Feld verschieden bilden, laufen beim ersten Nachziehen
    auseinander — und zwar lautlos, weil beide ein `termin_plausibel` liefern.
    """
    treffer = re.findall(r"coalesce\(NOT list_has_any\(q\.quality_flags,", GOLD)
    assert len(treffer) == 2, (
        f"Erwartet: beide Zweige lesen die Flags (2 Fundstellen), gefunden {len(treffer)}.")


def test_alle_zeitbezogenen_flags_zaehlen_mit():
    """⚠ VIER FLAGS, NICHT EINS.

    `laufzeit_unplausibel` war das einzige, das die Zeitangabe unsicher machte.
    `ende_vor_vergabe` (Vertragsende VOR der Vergabe), `datum_absurd` und
    `datum_start_nach_ende` sagen dasselbe ueber dieselbe Zahl — und gingen trotzdem als
    gemessen hinaus. Gemessen am 2026-09-05: 2 weitere Leads.
    """
    for flag in ("laufzeit_unplausibel", "ende_vor_vergabe", "datum_absurd",
                 "datum_start_nach_ende"):
        assert f"'{flag}'" in GOLD, (
            f"`{flag}` zaehlt nicht mehr mit — dann geht eine erkannt falsche Zeitangabe "
            f"wieder unmarkiert hinaus.")


def test_der_join_steht_und_ist_zeilentreu_begruendet():
    """Ein zusaetzlicher Join im Kern der Pipeline braucht eine Begruendung.

    `quality.parquet` traegt genau eine Zeile je `notice_id` (geprueft: 2.275.460 Zeilen,
    ebenso viele Kennungen), deshalb verdoppelt der LEFT JOIN nichts. Und `build_quality`
    laeuft im Lauf des Landes VOR `build_prospective_leads` — sonst faende der Join eine
    Datei, die es noch nicht gibt.
    """
    zweig = _f02_zweig()
    assert "LEFT JOIN '{Q}' q ON q.notice_id=n.notice_id" in zweig, (
        "Der Join auf die Qualitaetstabelle fehlt — dann ist `q.quality_flags` unbekannt "
        "und der Gold-Bau bricht ab.")
    assert "Zeilentreu" in zweig or "zeilentreu" in zweig, (
        "Die Begruendung zur Zeilentreue fehlt. Ein Join ohne diese Pruefung ist die "
        "haeufigste Art, in einer Aggregation still zu verdoppeln.")


# ---- Dieselbe Klasse, anderes Feld: die Bieterzahl ------------------------------
def test_eine_unplausible_bieterzahl_gilt_nicht_als_gemessen():
    """⚠ EINE VORHANDENE ZAHL WAR IMMER „GEMESSEN".

    `competition_source` machte aus jedem vorhandenen `num_tenders` ein `actual` — auch
    dann, wenn die Qualitaetspruefung die Zahl als `bieterzahl_unplausibel` erkannt hatte.
    Gemessen am 2026-09-05: 7 ausgelieferte Leads, deren Wettbewerbsangabe damit unmarkiert
    hinausging. Dieselbe Klasse wie bei der Laufzeit, nur ein anderes Feld.
    """
    assert "bieter_plausibel" in GOLD, (
        "Die Bieter-Plausibilitaet wird nicht mehr mitgefuehrt.")
    assert "'bieterzahl_unplausibel'" in GOLD, (
        "Das Flag wird nicht mehr gelesen.")
    i = GOLD.index("AS competition_source")
    block = GOLD[max(0, i - 600):i]
    assert "bieter_plausibel" in block, (
        "`competition_source` fragt die Plausibilitaet nicht — dann ist jede vorhandene "
        "Zahl wieder „gemessen\".")


def test_unplausibel_heisst_unsicher_und_nicht_unbekannt():
    """Die Zahl steht da und wird weiter gezeigt — nur markiert.

    `unknown` waere eine andere und falsche Aussage („wir wissen es nicht"): wir wissen es,
    wir trauen es nur nicht. Die Oberflaeche kennt `unsicher` — „Unsicher · Datenlage
    widersprüchlich" (SRC_TEXT in `web/lib/explorerCore.js`).
    """
    i = GOLD.index("AS competition_source")
    block = GOLD[max(0, i - 600):i]
    assert "'uncertain'" in block, "der unplausible Fall wird nicht auf `uncertain` abgebildet"

    export = (ROOT / "scripts" / "export_web_leads.py").read_text(encoding="utf-8")
    j = export.index("KONK_SRC = {")
    tabelle = export[j:j + 200]
    assert '"uncertain": "unsicher"' in tabelle, (
        "`KONK_SRC` kennt `uncertain` nicht — der Wert erreichte die Oberflaeche dann als "
        "unbekannter Schluessel, der Punkt bliebe durchsichtig und saehe aus wie gemessen.")
