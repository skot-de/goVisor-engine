"""Der Waechter ueber die Sondierungszahlen (`scripts/pruefe_sondierungszahlen.py`).

⚠ Ein Waechter ohne Test ist eine Behauptung — und dieser hier bewacht eine Fehlerklasse,
die niemand bemerkt: Papiere, die eine ERSETZTE Messung beschreiben. Nichts stuerzt ab,
nichts wird rot, die Zahlen sehen plausibel aus. Genau so standen fuenf Laenderzeilen in
`linktiefe.md` tagelang auf den Werten vor dem Musterfix.

Die Tests arbeiten auf einer KOPIE von `docs/sondierung` und `data/sondierung` und
verbiegen darin je eine Zahl. Wer nur „auf dem echten Bestand ist es gruen" prueft, hat
bewiesen, dass der Waechter schweigt — nicht, dass er beissen kann.
"""
import importlib.util
import pathlib
import shutil

import pytest

WURZEL = pathlib.Path(__file__).resolve().parent.parent


def _modul():
    spec = importlib.util.spec_from_file_location(
        "psz", WURZEL / "scripts" / "pruefe_sondierungszahlen.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture()
def kopie(tmp_path):
    """Der echte Bestand in einer Sandkiste, mit umgebogenen Modulpfaden."""
    m = _modul()
    if not (m.DATEN / "_tief").is_dir():
        pytest.skip("keine Sondierungsdaten — frische Arbeitskopie")
    shutil.copytree(m.DATEN, tmp_path / "data")
    shutil.copytree(m.PAPIERE, tmp_path / "docs")
    m.DATEN, m.PAPIERE = tmp_path / "data", tmp_path / "docs"
    m.UEBERSICHT = m.PAPIERE / "00-uebersicht.md"
    m.LINKTIEFE = m.PAPIERE / "linktiefe.md"
    m.HALTBARKEIT = m.PAPIERE / "haltbarkeit.md"
    return m


def _ersetze(datei: pathlib.Path, alt: str, neu: str) -> None:
    t = datei.read_text(encoding="utf-8")
    assert alt in t, f"{datei.name}: '{alt}' nicht gefunden — der Test prueft ins Leere"
    datei.write_text(t.replace(alt, neu, 1), encoding="utf-8")


def test_der_echte_bestand_ist_sauber():
    """Jede Zahl der Papiere folgt aus den Messdateien."""
    m = _modul()
    if not (m.DATEN / "_tief").is_dir():
        pytest.skip("keine Sondierungsdaten")
    b, _ = m.befunde()
    assert b == [], "\n".join(b)


def test_eine_veraltete_linktiefe_zeile_faellt_auf(kopie):
    """Der Fall, der den Waechter ausgeloest hat: AT stand auf 76,4 % statt 31,5 %."""
    _ersetze(kopie.LINKTIEFE, "| **AT** | 1.130 | 519 | **31,5 %** ⚠ |",
             "| **AT** | 33 | 107 | **76,4 %** ⚠ |")
    b, _ = kopie.befunde()
    assert any("linktiefe.md" in z and "AT" in z for z in b), b


def test_ein_fehlendes_land_faellt_auf(kopie):
    """Liechtenstein fehlte in der Tabelle, ohne dass eine Zahl falsch war."""
    _ersetze(kopie.LINKTIEFE, "| **LI** | 44 | 0 | **0,0 %** |", "")
    b, _ = kopie.befunde()
    assert any("LI" in z for z in b), b


def test_eine_zahl_im_fliesstext_ohne_deckung_faellt_auf(kopie):
    """§1 rechnete im Text mit 64,0 %, in der Tabelle daneben mit 65,2 %."""
    _ersetze(kopie.UEBERSICHT, "die 65,2 % sind kein technisches Urteil",
             "die 64,0 % sind kein technisches Urteil")
    b, _ = kopie.befunde()
    assert any("64,0" in z for z in b), b


def test_ein_verschobener_eu_anteil_faellt_auf(kopie):
    _ersetze(kopie.UEBERSICHT, "| **DE** | 20,4 %", "| **DE** | 24,0 %")
    b, _ = kopie.befunde()
    assert any("DE" in z and "EU-Anteil" in z for z in b), b


def test_eine_erfundene_matrixzelle_faellt_auf(kopie):
    """Die Aufbewahrungsmatrix wird abgeleitet, nicht abgeschrieben."""
    _ersetze(kopie.HALTBARKEIT, "| **DE** | **0/3** | **0/3**", "| **DE** | **3/3** | **0/3**")
    b, _ = kopie.befunde()
    assert any("haltbarkeit.md" in z and "DE" in z for z in b), b


def test_eine_falsch_gerechnete_datenmenge_faellt_auf(kopie):
    """GB/Jahr muss aus Links × offen × MB folgen — sonst faellt der offen-Faktor weg."""
    _ersetze(kopie.UEBERSICHT, "| **BE** | 13.448 | Vergabe | 6,1 | **1** | 48 |",
             "| **BE** | 13.448 | Vergabe | 6,1 | **1** | 80 |")
    b, _ = kopie.befunde()
    assert any("§3a BE" in z for z in b), b


def test_ein_falscher_domain_beleg_faellt_auf(kopie):
    """„N von M" traegt seine Rohzahlen mit — also wird gegen die Messung gerechnet."""
    _ersetze(kopie.PAPIERE / "sk.md", "(4.383 von 4.577)", "(4.383 von 4.500)")
    b, _ = kopie.befunde()
    assert any("sk.md" in z for z in b), b


def test_eine_sammelzeile_die_nicht_aufgeht_faellt_auf(kopie):
    """Der PT-Fall: 9,3 % kamen nur mit einer stillschweigend mitgezaehlten Domain."""
    _ersetze(kopie.PAPIERE / "pt.md",
             "| `anogov.com` + `compraspt.com` (dieselbe Software) | 8,8 %",
             "| `anogov.com` + `compraspt.com` (dieselbe Software) | 9,3 %")
    b, _ = kopie.befunde()
    assert any("pt.md" in z for z in b), b


def test_ein_widerspruch_zweier_stichproben_faellt_auf(kopie):
    """Estland stand mit 67 GB da, auf EINER Vergabe — 15 spaetere Proben sagten 17."""
    _ersetze(kopie.UEBERSICHT, "| **EE** | 3.558 | Vergabe | 5,0 | 15 | 17 |",
             "| **EE** | 3.558 | Vergabe | 19,3 | **1** | 67 |")
    b, _ = kopie.befunde()
    assert any("EE" in z and "aufbewahrung.json" in z for z in b), b


def test_der_median_wird_nicht_gegen_das_mittel_gehalten(kopie):
    """⚠ Die erste Fassung meldete Rumaenien mit Faktor 8 — sie verglich den Median der
    Tabelle mit dem Mittel der Proben und beschrieb damit nur die eigene Verwechslung."""
    b, _ = kopie.befunde()
    assert not any("§3a RO" in z for z in b), b
