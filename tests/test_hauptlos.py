"""Die Hauptlos-Markierung: gebaut, und dann nirgends gelesen.

`gold.py` berechnet je Cluster gleichartiger Lose ein `ist_hauptlos` und eine `lose_im_cluster`.
Der Kommentar dort behauptete bis zum 2026-09-06: „der Radar zeigt per Default nur Hauptlose,
die anderen sind über ein Flag da." Gemessen stimmt beides nicht — die Spalten fallen eine
Stufe vor dem Export weg, und in der Trefferliste steht jedes Los als eigener Lead.

Ob die Filterung fehlt, ist eine Produktfrage: jedes Los ist ein eigenes Angebot, und wer nur
Hauptlose sieht, verpasst 10.367 Gelegenheiten. Falsch war nur die Behauptung.
"""
import glob
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GOLD_PY = (ROOT / "govisor" / "gold.py").read_text(encoding="utf-8")


def _verbraucher() -> list[str]:
    """Wer liest die Markierung ausserhalb von `gold.py`?"""
    treffer = []
    for rel in ("scripts/export_web_leads.py", "web/lib/explorerCore.js",
                "web/lib/leadIndex.ts", "scripts/export_web_awards.py"):
        p = ROOT / rel
        if p.exists() and ("ist_hauptlos" in p.read_text(encoding="utf-8")
                           or "hauptlos" in p.read_text(encoding="utf-8")):
            treffer.append(rel)
    return treffer


def test_die_behauptung_haengt_am_verbraucher():
    """Ein Satz über das Verhalten des Produkts braucht das Verhalten.

    ⚠ Der Satz stand ueber vier Wochen im Code und war falsch. Wer ihn liest, haelt die
    Trefferliste fuer entdoppelt und sucht den Fehler woanders — genau die Sorte Irrfuehrung,
    die teurer ist als gar kein Kommentar.
    """
    behauptet = "per Default nur Hauptlose" in GOLD_PY
    if behauptet:
        assert _verbraucher(), (
            "`gold.py` behauptet, der Radar zeige nur Hauptlose — aber niemand liest "
            "`ist_hauptlos`. Entweder die Filterung bauen oder den Satz streichen.")


def test_die_markierung_endet_heute_in_gold():
    """Der gemessene Zustand, festgehalten.

    Faellt dieser Test, hat jemand die Markierung verdrahtet — dann gehoert der Kommentar in
    `gold.py` berichtigt, denn dort steht heute ausdruecklich, dass sie hier endet.
    """
    assert "ist_hauptlos" in GOLD_PY, "die Markierung wird nicht mehr berechnet"
    v = _verbraucher()
    if v:
        pytest.fail(f"`ist_hauptlos` hat jetzt Verbraucher: {v}. Der Kommentar in gold.py "
                    "sagt, die Markierung ende dort — das gehoert nachgezogen.")


@pytest.mark.skipif(not glob.glob("data/gold/DE/leads.parquet"),
                    reason="keine Gold-Ebene")
def test_der_anteil_der_nebenlose_stimmt_noch():
    """Die Zahl, auf der die Produktentscheidung ruht.

    Gemessen am 2026-09-06: 10.367 von 91.143 Leads sind KEIN Hauptlos (11,4 %). Sinkt der
    Anteil gegen null, ist die Frage erledigt; steigt er stark, wird sie dringender. Eine
    Zahl im Kommentar altert still — diese hier nicht.
    """
    import duckdb
    con = duckdb.connect()
    n, neben = con.execute(
        "SELECT count(*), count(*) FILTER (WHERE NOT ist_hauptlos) "
        "FROM read_parquet('data/gold/DE/leads.parquet')").fetchone()
    anteil = neben / max(n, 1)
    assert 0.03 <= anteil <= 0.25, (
        f"Neben-Lose machen jetzt {anteil:.1%} aus ({neben:,} von {n:,}), am 2026-09-06 "
        f"waren es 11,4 %. Die Begruendung im Kommentar von `gold.py` ruht auf dieser Zahl.")
