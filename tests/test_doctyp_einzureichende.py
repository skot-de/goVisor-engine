"""„Verzeichnis der einzureichenden Unterlagen" ist eine Anforderungsliste, kein Formblatt.

⚠ DER BEFUND. Sven am 2026-09-21: „warum werten wir nur ein teil der dokumente aus?" Beim
Nachmessen von 14.340 uebergangenen Dateien fiel eine Familie auf, die sehr wohl
Anforderungen traegt und trotzdem unter „Weitere Dokumente" landete: 160 Dateien (1,1 %)
der Art „Verzeichnis/Uebersicht/Auflistung der einzureichenden Unterlagen". In einer
gelesenen Stichprobe von 12 waren alle 12 echte Anforderungslisten; eine sagt woertlich,
dass fehlende Unterlagen zum Ausschluss fuehren.

⚠ VHB 216 IST ANDERS ABGELEITET als der Rest der Nummerntabelle. Die uebliche Methode
(Rest des Dateinamens klassifizieren) ist hier zirkulaer: der Rest lautet „VHB Verzeichnis
vorzulegende Unterlagen", und „VHB" trifft selbst die Formblatt-Regel (gemessen 74 %
formblatt). Entschieden hat der INHALT: 22 von 22 gelesenen 216-Dateien ordnet
`classify_content` als aufforderung ein.

⚠ ZWEI WOERTER, NICHT EINES. Die Wortregel verlangt ein Listenwort UND ein
Einreichungswort. „Inhaltsverzeichnis Vergabeunterlagen" ist ein Inhaltsverzeichnis und
darf NICHT greifen — das ist der Fall, an dem eine zu gierige Regel scheitern wuerde.

Wirkung ueber den Bestand gemessen (99.876 Dateinamen): 561 ordnen sich anders ein
(0,56 %), 558 kommen neu in die Auswertung, KEINE faellt heraus.
"""
from __future__ import annotations

import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
from govisor import doctypes  # noqa: E402

AUSWERTUNG = ("fragenantworten",) + tuple(doctypes.PRIORITY)


def test_das_verzeichnis_der_vorzulegenden_unterlagen_wird_ausgewertet():
    for name in (
        "VHB_216_Verzeichnis_vorzulegende_Unterlagen.pdf",
        "Auflistung einzureichenden Unterlagen National 2025.pdf",
        "Übersicht_einzureichender_Unterlagen.pdf",
        "7. 26R1826 - Liste der einzureichenden Unterlagen.pdf",
        "E_07_Übersicht vorzulegender Unterlagen.pdf",
        "Verzeichnis der weiteren vom Bieter einzureichenden Unterlagen.pdf",
    ):
        typ = doctypes.classify(name)
        assert typ in AUSWERTUNG, f"{name} faellt wieder aus der Auswertung ({typ})"


def test_ein_inhaltsverzeichnis_ist_keine_anforderungsliste():
    """⚠ Der Fall, an dem eine zu gierige Regel scheitert. Ein Inhaltsverzeichnis listet
    auf, was DA ist, keine Anforderung."""
    for name in (
        "26FEI88010 0.4-Inhaltsverzeichnis Vergabeunterlagen.pdf",
        "72_4509-3_0_Inhaltsverzeichnis technische Dokumentation.pdf",
    ):
        assert doctypes.classify(name) != "aufforderung", f"{name} wird faelschlich erfasst"


def test_die_nummer_216_steht_mit_ihrer_herleitung_in_der_tabelle():
    assert doctypes._NUMMER_TYP.get("216") == "aufforderung"
    quelle = (WURZEL / "govisor" / "doctypes.py").read_text(encoding="utf-8")
    i = quelle.index('"216": "aufforderung"')
    davor = quelle[max(0, i - 1200):i]
    assert "zirkulaer" in davor or "zirkulär" in davor, (
        "die Herleitung von 216 ist nicht mehr dokumentiert; sie weicht bewusst von der "
        "Methode der uebrigen Tabelle ab")


def test_die_anderen_formblattnummern_bleiben_wo_sie_waren():
    """⚠ Eine neue Regel in `aufforderung` steht VOR den nicht priorisierten Typen. Ohne
    diese Zusicherung koennte sie Preisblaetter und Vertraege mitreissen."""
    for name, erwartet in (
        ("VHB_221_Preisermittlung bei Zuschlagskalkulation.pdf", "preisblatt"),
        ("VHB_214_Vertragsstrafen.pdf", "vertrag"),
        ("Leistungsverzeichnis.pdf", "leistungsbeschreibung"),
        ("Verzeichnis der Nachunternehmerleistungen.pdf", "eigenerklaerung"),
        ("VHB_124_Eigenerklaerung Eignung.pdf", "eignung"),
    ):
        assert doctypes.classify(name) == erwartet, f"{name} wandert nach {doctypes.classify(name)}"
