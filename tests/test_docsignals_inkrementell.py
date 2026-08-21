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


def _korpus_mit_fassungen(ziel: pathlib.Path) -> None:
    """Ein Vorgang mit Nachtrag, einer ohne — beide mit widerspruechlichen Angaben."""
    alt = ("Zuschlagskriterien: Preis 70 %, Qualität 30 %. "
           "Nebenangebote sind nicht zugelassen.")
    neu = ("Zuschlagskriterien: Preis 40 %, Qualität 60 %. "
           "Nebenangebote sind zugelassen.")
    nur_alt = "Eine Ortsbesichtigung ist verpflichtend."
    zeilen = {"notice_id": [], "archive": [], "file": [], "filetype": [],
              "n_chars": [], "status": [], "text": []}
    for nid, datei, text in (
        # ersetzt: gleicher Pfad unterhalb des Fassungsordners
        ("n1", "Vergabe/Version 1/Bedingungen.pdf", alt),
        ("n1", "Vergabe/Version 2/Bedingungen.pdf", neu),
        # steht NUR in der alten Fassung — ein Nachtrag ersetzt nur, was er selbst enthaelt
        ("n1", "Vergabe/Version 1/Zusatz.pdf", nur_alt),
        ("n2", "u.pdf", _B),
    ):
        zeilen["notice_id"].append(nid); zeilen["archive"].append("a.zip")
        zeilen["file"].append(datei); zeilen["filetype"].append(".pdf")
        zeilen["n_chars"].append(len(text)); zeilen["status"].append("ok")
        zeilen["text"].append(text)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table(zeilen), ziel, compression="zstd")


def test_ueberholte_nachtraege_gehen_nicht_in_die_signale(tmp_path):
    """Ohne Ausschluss rechnet der Schritt zwei Staende in EINEN Text zusammen.

    Gemessen am 2026-08-21: 1.291 Dateien in 84 Vorgaengen, 17,2 Mio. Zeichen. Der Vorgang
    haette dann „Preis 70 %" und „Preis 40 %" nebeneinander — und keine Angabe, was gilt.
    """
    import duckdb

    quelle = tmp_path / "docs" / "DE" / "doc_text.parquet"
    _korpus_mit_fassungen(quelle)

    con = duckdb.connect()
    n = docsignals._ueberholt_registrieren(con, quelle)
    assert n == 1, "genau die ersetzte Datei, nicht die ganze alte Fassung"

    behalten = {f for (f,) in con.execute(
        f"SELECT file FROM read_parquet('{quelle.as_posix()}') d "
        f"WHERE {docsignals.SQL_BRAUCHBAR} {docsignals._ohne_ueberholte('d')}").fetchall()}
    assert "Vergabe/Version 2/Bedingungen.pdf" in behalten
    assert "Vergabe/Version 1/Bedingungen.pdf" not in behalten
    # ⚠ Der Zusatz steht NUR in Version 1 und wurde nie ersetzt — er muss bleiben.
    assert "Vergabe/Version 1/Zusatz.pdf" in behalten


def test_ausschluss_steckt_im_fingerabdruck_sonst_bliebe_er_wirkungslos(tmp_path):
    """Der inkrementelle Schritt rechnet nur, was sich laut Abdruck geaendert hat.

    ⚠ Stuende der Ausschluss nur in der Auswertung und nicht im Abdruck, hielte der Schritt
    die alten Signale fuer gueltig — die Aenderung haette am Bestand nichts bewirkt. Die
    Regeln fuer den Voll-Lauf (`_REGEL_MARKE`) greifen hier NICHT: der Ausschluss ist
    Mechanik. Ueber den Abdruck rechnen sich genau die betroffenen Vorgaenge neu, im echten
    Bestand 84 von 5.593 — nicht alle.
    """
    import duckdb
    import pyarrow as _pa

    quelle = tmp_path / "docs" / "DE" / "doc_text.parquet"
    _korpus_mit_fassungen(quelle)

    con = duckdb.connect()
    con.register("_ueberholt", _pa.table({"notice_id": _pa.array([], _pa.string()),
                                          "file": _pa.array([], _pa.string())}))
    ohne = docsignals._fingerabdruecke(con, quelle)
    con.unregister("_ueberholt")
    docsignals._ueberholt_registrieren(con, quelle)
    mit = docsignals._fingerabdruecke(con, quelle)

    assert ohne["n1"] != mit["n1"], "der betroffene Vorgang wird sonst nicht neu gerechnet"
    assert ohne["n2"] == mit["n2"], "unbeteiligte Vorgaenge duerfen nicht neu gerechnet werden"


def test_signale_folgen_dem_geltenden_stand(tmp_path):
    """Am Ende zaehlt, was in den Signalen steht — nicht, welche Datei gelesen wurde."""
    quelle = tmp_path / "docs" / "DE" / "doc_text.parquet"
    _korpus_mit_fassungen(quelle)
    cfg = Config(countries=("DE",), data_dir=tmp_path)
    docsignals.build_signals(cfg, country="DE")
    tab = _ausgabe(tmp_path)
    zeile = {n: i for i, n in enumerate(tab.column("notice_id").to_pylist())}
    assert "n1" in zeile
    # Version 2 laesst Nebenangebote zu, Version 1 nicht. Es gilt Version 2.
    spalten = tab.column_names
    assert "variants_allowed" in spalten, spalten
    assert tab.column("variants_allowed")[zeile["n1"]].as_py() is True
