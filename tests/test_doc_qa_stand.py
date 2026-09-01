"""Fragenkatalog-Zaehlschicht: die zwei Stellen, an denen sie still falsch wird.

⚠ Beide Pruefungen stehen hier, weil der Fehler beim Bauen TATSAECHLICH passiert ist,
nicht weil er denkbar waere. Die Zahlen im Kommentar sind gemessen.
"""
import datetime as _dt
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _modul():
    spec = importlib.util.spec_from_file_location(
        "bqs", ROOT / "scripts" / "build_doc_qa_stand.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


LEERFORMULAR = """Formblatt FB6 - Bieterfrage
Vergabeverfahren: 2026-000123
Frage Nr. 1:
_______________________________________
Bitte reichen Sie dieses Formular ueber das Vergabeportal ein."""

ECHTER_KATALOG = """Beantwortung der Bieterfragen, Stand 12.08.2026
Frage 1: Ist das Zertifikat ISO 27001 zwingend erforderlich?
Antwort: Nein, ein gleichwertiger Nachweis wird anerkannt.
Frage 2: Wie viele Standorte sind zu betreuen?
Antwort: Vierzehn Standorte, siehe Anlage 3."""


def test_leerformular_zaehlt_nicht_als_fragenkatalog():
    """1.510 der 2.217 Treffer des Doktyps sind Vordrucke ohne jede Antwort.

    Wer nur den Doktyp zaehlt, meldet dreimal so viele Fragenkataloge wie es gibt —
    und die Kennzahl „Fortschreibungsdichte" waere von Anfang an wertlos.
    """
    m = _modul()
    assert not (m.FRAGE.search(LEERFORMULAR) and m.ANTWORT.search(LEERFORMULAR)), (
        "Ein Leerformular hat keine Antwort und darf nicht als Fragenkatalog zaehlen")
    assert m.FRAGE.search(ECHTER_KATALOG) and m.ANTWORT.search(ECHTER_KATALOG), (
        "Ein echter Katalog mit Frage und Antwort muss erkannt werden")


def test_fassungszahl_greift_keine_fragennummern_und_daten():
    """Die entfernte Regel „Bieterinformation Nr. N" mass in der Mehrzahl etwas anderes.

    Gemessen an 257 Vorgaengen war sie mit 102 Treffern die groesste Gruppe und lag
    unter anderem hier daneben:
      · `Beantwortete Bieterfragen Nr. 82-87.pdf` → 82 ist eine Fragennummer
      · `Bieterfragen_Stand_30.07.2026.pdf`       → 30 ist ein Kalendertag
      · `260811_ENSPE_50_Bieterfragen.pdf`        → 50 ist ein Projektkuerzel
    Kaeme sie zurueck, staende im Produkt „82 Fortschreibungen" an einem Verfahren
    mit zweien.
    """
    m = _modul()
    for datei in ("Vergabeunterlagen/32_P1000_Beantwortete Bieterfragen Nr. 82-87.pdf",
                  "Bieterfragen_Stand_30.07.2026_Antwort.pdf",
                  "260811_ENSPE_50_Bieterfragen.pdf",
                  "Beantwortung von Bieterfragen29.07.2027.pdf"):
        for _name, rx in m.FASSUNG:
            treffer = rx.search(datei)
            assert not treffer, (
                f"{datei!r} liefert eine Fassungszahl {treffer.group(0)!r} — "
                "das ist eine Fragennummer, ein Datum oder ein Projektkuerzel")
    # Der belastbare Weg bleibt: die Fassung aus dem Pfad des Portals.
    assert any(rx.search("Vergabeunterlagen/Version 3/30 Bieterfragen-Antworten.pdf")
               for _n, rx in m.FASSUNG), "Die Pfad-Fassung muss weiterhin greifen"


def test_unplausibler_antwortabstand_wird_verworfen():
    """Ohne Fenster stand in der Tabelle „656 Tage vor der Frist" und „114 danach".

    Beides waren falsch gegriffene Daten (ein Vertragsbeginn im Fliesstext). Eine
    Kennzahl, die solche Werte mitrechnet, ist als Fairness-Mass unbrauchbar.
    """
    m = _modul()
    frist = _dt.date(2026, 9, 30)
    weit = [("Bieterfragen_Stand_01.01.2025.pdf", ECHTER_KATALOG)]
    danach = [("Bieterfragen_Stand_31.12.2026.pdf", ECHTER_KATALOG)]
    nah = [("Bieterfragen_Stand_20.09.2026.pdf", ECHTER_KATALOG)]
    assert m.zeile("x", "DE", weit, frist)[10] is None, "656-Tage-Fall nicht verworfen"
    assert m.zeile("x", "DE", danach, frist)[10] is None, "Datum nach der Frist nicht verworfen"
    assert m.zeile("x", "DE", nah, frist)[10] == 10, "plausibler Abstand faelschlich verworfen"


def test_fassungsquelle_wird_immer_mitgefuehrt():
    """Eine Zahl ohne ihre Herkunft ist hier wertlos: 65 Vorgaenge haben eine belegte
    Fassung aus dem Portal-Pfad, 192 nur die Zahl ihrer Dokumente. Wer beide gleich
    behandelt, verkauft eine Schaetzung als Messung."""
    m = _modul()
    ohne = m.zeile("x", "DE", [("Bieterfragen.pdf", ECHTER_KATALOG)], None)
    mit = m.zeile("x", "DE", [("Version 3/Bieterfragen.pdf", ECHTER_KATALOG)], None)
    assert ohne[4] == "dokumentzahl" and mit[4] == "version"
