"""Der Signal-Schritt rechnet nur Neues — und liefert dabei dasselbe wie ein Voll-Lauf.

**Warum das ein Test sein muss.** Am 2026-08-15 brauchte `signals-docs` **232 Minuten** und
war damit 40 % des gesamten Tageslaufs, obwohl sich pro Tag nur eine Handvoll Vorgänge
ändert. Die Kosten stecken nicht in der Zahl der Vorgänge (3.437), sondern in der Textmasse:
~30 Regexe mit `DOTALL` über 1,38 Mrd. Zeichen.

Inkrementell heisst: ein Fehler wird nicht mehr sofort sichtbar, sondern **konserviert** —
ein Vorgang, der faelschlich als „unveraendert" gilt, traegt seine alten Signale unbegrenzt
weiter, und keine Anzeige verraet es. Deshalb prueft dieser Test nicht nur „es war schnell",
sondern jedes Mal die Gleichheit mit dem Voll-Lauf.
"""
import pathlib
import sys

import pytest

pytest.importorskip("duckdb")
pytest.importorskip("pyarrow")
import pyarrow as pa            # noqa: E402
import pyarrow.parquet as pq    # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from govisor import docsignals          # noqa: E402
from govisor.config import Config       # noqa: E402

# Zwei Vorgaenge mit echtem Vergabe-Vokabular — knapp, aber sie loesen mehrere Regeln aus.
_A = ("Die Vertragserfüllungsbürgschaft ist beizubringen. Die Bindefrist endet am 30.10.2026. "
      "Nebenangebote sind nicht zugelassen. Eigenerklärung und Referenzen sind vorzulegen. "
      "Bei Verzug wird eine Vertragsstrafe von 0,2 % je Werktag fällig.")
_B = ("Es handelt sich um eine Rahmenvereinbarung. Eine Ortsbesichtigung ist verpflichtend. "
      "Zuschlagskriterien: Preis 70 %, Qualität 30 %. Präqualifikation nach PQ-VOB wird anerkannt.")


def _korpus(ziel: pathlib.Path, saetze: dict[str, str]) -> None:
    zeilen = {"notice_id": [], "archive": [], "file": [], "filetype": [],
              "n_chars": [], "status": [], "text": []}
    for nid, text in saetze.items():
        zeilen["notice_id"].append(nid); zeilen["archive"].append("a.zip")
        zeilen["file"].append("u.pdf"); zeilen["filetype"].append(".pdf")
        zeilen["n_chars"].append(len(text)); zeilen["status"].append("ok")
        zeilen["text"].append(text)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table(zeilen), ziel, compression="zstd")


@pytest.fixture()
def umgebung(tmp_path):
    quelle = tmp_path / "docs" / "DE" / "doc_text.parquet"
    _korpus(quelle, {"n1": _A, "n2": _B})
    return Config(countries=("DE",), data_dir=tmp_path), tmp_path, quelle


def _ausgabe(wurzel):
    return pq.read_table(wurzel / "docs" / "DE" / "doc_signals.parquet").sort_by("notice_id")


def test_zweiter_lauf_rechnet_nichts_und_aendert_nichts(umgebung):
    cfg, wurzel, _ = umgebung
    docsignals.build_signals(cfg, country="DE")
    voll = _ausgabe(wurzel)

    r = docsignals.build_signals(cfg, country="DE")
    assert r["gerechnet"] == 0, "unveränderter Eingang darf nichts neu rechnen"
    assert _ausgabe(wurzel).equals(voll), "Ausgabe änderte sich ohne Eingangsänderung"


def test_geaenderter_vorgang_wird_neu_gerechnet_und_trifft_denselben_wert(umgebung):
    cfg, wurzel, quelle = umgebung
    docsignals.build_signals(cfg, country="DE")
    voll = _ausgabe(wurzel)

    # Denselben Text noch einmal schreiben, aber mit anderer Dateilänge → Abdruck kippt.
    _korpus(quelle, {"n1": _A + " ", "n2": _B})
    r = docsignals.build_signals(cfg, country="DE")
    assert r["gerechnet"] == 1, f"genau ein Vorgang war fällig, gerechnet: {r['gerechnet']}"
    # Ein angehängtes Leerzeichen ändert kein einziges Signal — die Zeile muss gleich bleiben.
    assert _ausgabe(wurzel).equals(voll), "neu gerechneter Vorgang weicht vom Voll-Lauf ab"


def test_regelaenderung_erzwingt_vollen_neulauf(umgebung):
    cfg, wurzel, _ = umgebung
    docsignals.build_signals(cfg, country="DE")

    stand = wurzel / "docs" / "DE" / docsignals._STAND
    d = pq.read_table(stand).to_pydict()
    d["regel_version"] = ["veraltet"] * len(d["regel_version"])
    pq.write_table(pa.table(d), stand, compression="zstd")

    r = docsignals.build_signals(cfg, country="DE")
    assert r["gerechnet"] == 2, "veraltete Regel-Version muss ALLE Vorgänge neu rechnen"


def test_entfallener_vorgang_faellt_aus_der_ausgabe(umgebung):
    cfg, wurzel, quelle = umgebung
    docsignals.build_signals(cfg, country="DE")
    assert _ausgabe(wurzel).num_rows == 2

    _korpus(quelle, {"n1": _A})            # n2 verschwindet aus dem Eingang
    docsignals.build_signals(cfg, country="DE")
    ids = _ausgabe(wurzel).column("notice_id").to_pylist()
    assert ids == ["n1"], f"entfallener Vorgang blieb stehen: {ids}"


def test_regelmarke_existiert_und_trennt_regeln_von_mechanik():
    """Ohne die Marke wäre der Fingerabdruck stumm — Regeländerungen blieben unbemerkt."""
    quelle = pathlib.Path(docsignals.__file__).read_text(encoding="utf-8")
    assert quelle.count("\n" + docsignals._REGEL_MARKE) == 1
    kopf = quelle.split("\n" + docsignals._REGEL_MARKE, 1)[0]
    assert "def extract_signals" in kopf, "die Extraktionsregeln müssen ÜBER der Marke stehen"
    assert "def build_signals" not in kopf, "die Mechanik gehört UNTER die Marke"
