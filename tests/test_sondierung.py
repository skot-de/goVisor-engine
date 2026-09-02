"""Die Trennung zwischen sondiert und aufgenommen — vier Regeln, vier Nachweise.

⚠ Eine Prüfung, die nur auf einer leeren Registry laeuft, beweist nichts. Jede Regel
hier wird mit einem kuenstlichen Eintrag zum Anschlagen gebracht; PL dient dabei als
echter Fall, weil dieses Land tatsaechlich Gold-Tabellen hat, ohne aufgenommen zu sein.
"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor.sources import Source                                   # noqa: E402


def _wache():
    spec = importlib.util.spec_from_file_location(
        "psond", ROOT / "scripts" / "pruefe_sondierung.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _eintrag(**kw) -> Source:
    grund = dict(id="sond-xx", name="Sondierung XX", connector="", country="XX",
                 tier="beides", status="sondiert")
    grund.update(kw)
    return Source(**grund)


def test_sondiertes_land_mit_tabellen_faellt_auf(monkeypatch):
    """Regel 1 — der Polen-Fall aus Sicht der Registry.

    PL hat seit dem Vorgangs-Bau echte Gold-Tabellen. Wuerde jemand PL als „sondiert"
    fuehren, waere das genau die Verwechslung, die 40 Tabellen als Luecke meldete.
    """
    w = _wache()
    monkeypatch.setattr(w.sources, "REGISTRY", [_eintrag(id="sond-pl", country="PL")])
    b = w.befunde()
    # ⚠ Auf den Wortlaut pruefen, der NUR zu Regel 1 gehoert. Die erste Fassung pruefte
    # auf „data/gold/PL" — das steht auch in der Meldung der Regel 4, und deshalb blieb
    # der Test gruen, als Regel 1 zum Versuch abgeschaltet wurde. Ein Test, der von einer
    # anderen Regel miterfuellt wird, prueft die eigene nicht.
    assert any("Polen-Fall" in z for z in b), b


def test_sondierter_eintrag_ohne_konnektor(monkeypatch):
    """Regel 2 — ein Befund ist kein Anschluss.

    Wer einen Konnektor eintraegt, hat angebunden; dann gehoert der Status gehoben.
    Beides zugleich behauptet Arbeit, die nicht getan ist.
    """
    w = _wache()
    monkeypatch.setattr(w.sources, "REGISTRY",
                        [_eintrag(country="XX", connector="docfetch-irgendwas")])
    assert any("docfetch-irgendwas" in z for z in w.befunde())


def test_sondiertes_land_nicht_im_onboarding_handbuch(tmp_path, monkeypatch):
    """Regel 3 — `docs/laender` ist das Handbuch der AUFGENOMMENEN Laender."""
    w = _wache()
    hb = tmp_path / "laender"
    hb.mkdir()
    (hb / "03-fr.md").write_text("Kapitel", encoding="utf-8")
    monkeypatch.setattr(w, "HANDBUCH", str(hb))
    monkeypatch.setattr(w.sources, "REGISTRY", [_eintrag(id="sond-fr", country="FR")])
    assert any("03-fr.md" in z for z in w.befunde())


def test_laendercode_als_silbe_schlaegt_nicht_an(tmp_path, monkeypatch):
    """Die Teilwort-Falle, zum vierten Mal in diesem Projekt.

    `12-fallenkatalog.md` enthaelt „at" in „katalog", `05-gold-kette.md` enthaelt „de"
    nirgends als Wort. Ein Laendercode zaehlt nur als eigenes Wort im Dateinamen.
    """
    w = _wache()
    hb = tmp_path / "laender"
    hb.mkdir()
    for name in ("12-fallenkatalog.md", "05-gold-kette.md", "14-zeichen-und-schrift.md"):
        (hb / name).write_text("x", encoding="utf-8")
    monkeypatch.setattr(w, "HANDBUCH", str(hb))
    monkeypatch.setattr(w.sources, "REGISTRY",
                        [_eintrag(id="sond-at", country="AT"),
                         _eintrag(id="sond-de", country="DE")])
    ohne_handbuch = [z for z in w.befunde() if "fallenkatalog" in z or "gold-kette" in z
                     or "zeichen-und-schrift" in z]
    assert not ohne_handbuch, ohne_handbuch


def test_land_mit_tabellen_darf_nicht_nur_sondiert_sein(monkeypatch):
    """Regel 4 — derselbe Fehler von der anderen Seite.

    Regel 1 fragt die Registry, Regel 4 die Platte. Bei Polen war die Platte schneller:
    die Tabellen standen da, bevor irgendjemand den Status angefasst hatte.
    """
    w = _wache()
    monkeypatch.setattr(w.sources, "REGISTRY", [_eintrag(id="sond-pl", country="PL")])
    assert any("hinter der Wirklichkeit" in z for z in w.befunde())


def test_saubere_sondierung_meldet_nichts(monkeypatch):
    """Ein Land ohne Tabellen, ohne Konnektor, ohne Handbuchkapitel: kein Befund."""
    w = _wache()
    monkeypatch.setattr(w.sources, "REGISTRY", [_eintrag(country="XX")])
    assert w.befunde() == []


def test_der_echte_bestand_ist_sauber():
    """Und die Registry, wie sie heute wirklich aussieht."""
    w = _wache()
    assert w.befunde() == []


def test_ungeprueft_gehoert_allein_der_sondierung(monkeypatch):
    """Regel 5 — `ertrag='ungeprueft'` heisst „nie gemessen".

    Stuende es an einer angebundenen Quelle, saehe eine Vermutung in der Ertragstabelle
    aus wie ein Befund — dieselbe Vermischung, die `fassung_quelle` und `sprecher`
    anderswo verhindern.
    """
    w = _wache()
    monkeypatch.setattr(w.sources, "REGISTRY",
                        [_eintrag(id="doc-xx", country="XX", status="live",
                                  connector="docfetch-xx", ebene="unterlagen",
                                  ertrag="ungeprueft")])
    assert any("ungeprueft" in z and "doc-xx" in z for z in w.befunde())
