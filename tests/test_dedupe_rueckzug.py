"""Die Dubletten-Firewall muss zurueckgezogene Bekanntmachungen wieder loslassen.

Hintergrund: `schreibe(..., vereinigen=True)` (der naechtliche Fensterlauf) fuegt zum
Bestand hinzu und nimmt nie etwas weg. Kennungen, die eine nationale Quelle
zurueckzieht, blieben deshalb als Waisen stehen — gemessen am 2026-09-02 in AT:
28 Zeilen auf 7 Kennungen, die offenevergaben.at zwischen dem 31.08. und dem 02.09.
aus seinem Tagesdump genommen hatte. `verify.gold_integrity(cfg, "AT")` meldete sie
als `notice_duplicates.duplicate → quality`.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _silber(tmp_path: Path, country: str, ids: list[str]) -> None:
    """Minimales `silver/<C>/notices` — nur die Spalte, auf die der Abgleich schaut."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    d = tmp_path / "data" / "silver" / country / "notices" / "year=2026"
    d.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table({"notice_id": pa.array(ids, pa.string())}), d / "2026-x.parquet")


def _paar(master: str, duplicate: str) -> dict:
    return {"master_id": master, "duplicate_id": duplicate,
            "master_quelle": "eforms", "duplicate_quelle": "atverg",
            "enthaltung": 0.9, "gleicher_kaeufer": True, "beleg": "kaeufer_und_titel",
            "tage_abstand": 1, "ergaenzt": None}


@pytest.fixture()
def ded(tmp_path, monkeypatch):
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from govisor import dedupe as d       # Paketmodul: dedupe nutzt relative Importe

    monkeypatch.setattr(d, "ROOT", tmp_path)
    return d


def _gelesen(tmp_path: Path, country: str) -> list[dict]:
    import pyarrow.parquet as pq
    return pq.read_table(
        tmp_path / "data" / "gold" / country / "notice_duplicates.parquet").to_pylist()


def test_vereinigen_laesst_zurueckgezogene_kennung_los(ded, tmp_path):
    """Der Kern: was in Silber fehlt, darf der Bestand nicht weitertragen."""
    ded.schreibe([_paar("atv-1", "atv-2"), _paar("atv-3", "atv-9")], "AT")
    _silber(tmp_path, "AT", ["atv-1", "atv-2", "atv-3"])     # atv-9 zurueckgezogen

    # Fensterlauf: findet nur das frische Paar, der Rest kommt aus dem Bestand.
    ded.schreibe([_paar("atv-1", "atv-2")], "AT", vereinigen=True)

    ids = {(z["master_id"], z["duplicate_id"]) for z in _gelesen(tmp_path, "AT")}
    assert ("atv-1", "atv-2") in ids, "lebendes Paar darf nicht verschwinden"
    assert ("atv-3", "atv-9") not in ids, "Paar auf zurueckgezogener Kennung muss weg"


def test_master_seite_zaehlt_genauso(ded, tmp_path):
    """Ein Paar ist auch dann wertlos, wenn der MASTER zurueckgezogen wurde."""
    ded.schreibe([_paar("atv-9", "atv-2")], "AT")
    _silber(tmp_path, "AT", ["atv-1", "atv-2"])
    ded.schreibe([], "AT", vereinigen=True)
    assert _gelesen(tmp_path, "AT") == []


def test_leeres_silber_loescht_den_bestand_nicht(ded, tmp_path):
    """Die Schutzbedingung. Ein halb gebautes Silber darf die Firewall nicht ausloeschen.

    Ohne sie waere der Schnitt gefaehrlicher als der Fehler, den er behebt: ein Lauf
    waehrend eines Silber-Neubaus wuerde die ueber Jahre gesammelten Paare wegwerfen.
    """
    ded.schreibe([_paar("atv-1", "atv-2")], "AT")
    _silber(tmp_path, "AT", [])                    # Datei da, aber ohne eine einzige Zeile
    ded.schreibe([], "AT", vereinigen=True)
    assert len(_gelesen(tmp_path, "AT")) == 1

    # Und ohne jede Silber-Datei ebenso.
    for p in (tmp_path / "data" / "silver" / "AT" / "notices").rglob("*.parquet"):
        p.unlink()
    ded.schreibe([], "AT", vereinigen=True)
    assert len(_gelesen(tmp_path, "AT")) == 1


def test_ohne_vereinigen_wird_nicht_geschnitten(ded, tmp_path):
    """Der Sonntagslauf ersetzt die Datei; sein Ergebnis kommt frisch aus Silber.

    Ein zweiter Abgleich waere dort nur Laufzeit — und wuerde bei einem Silber-Wechsel
    mitten im Lauf sogar frisch gefundene Paare wegwerfen.
    """
    _silber(tmp_path, "AT", ["atv-1"])
    ded.schreibe([_paar("atv-1", "atv-2")], "AT")          # vereinigen=False
    assert len(_gelesen(tmp_path, "AT")) == 1
