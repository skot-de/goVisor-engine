"""Kriterienmatrizen — die zwei Bauformen, und was NICHT geraten werden darf.

Ohne Netz und ohne Bestand: die Arbeitsmappen werden im Speicher gebaut.
"""
from __future__ import annotations

import importlib.util
import io
import zipfile
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("ec", ROOT / "scripts" / "extract_criteria.py")
ec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ec)


def _mappe(zeilen, blatt="Matrix"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = blatt
    for z in zeilen:
        ws.append(z)
    puffer = io.BytesIO()
    wb.save(puffer)
    return puffer.getvalue()


# ── Erste Bauform: der Buchstabe steckt im Code ───────────────────────────────────────────

ERSTE = [
    ["Kriterienhauptgruppe", "Kriteriengruppe", "Kriterium", "Gewichtung"],
    ["", "", "", ""],
    ["KHG A: Technik", "", "", ""],
    ["", "KG A.1", "allgemeine Anforderungen", ""],
    ["", "", "A.1.1", "Geräte müssen fabrikneu sein", "30"],
]


def test_erste_bauform_wird_gelesen():
    k = ec.lies_matrix(_mappe(ERSTE))
    assert len(k) == 1
    assert k[0]["code"] == "A.1.1"
    assert k[0]["art"] == "ausschluss"


def test_wort_vor_dem_code_stoert_nicht():
    """„Kriterium A.1.2" ist derselbe Code — eine Matrix von 18 schrieb ihn so."""
    zeilen = [r[:] for r in ERSTE]
    zeilen[-1][2] = "Kriterium B.1.2"
    k = ec.lies_matrix(_mappe(zeilen))
    assert len(k) == 1 and k[0]["art"] == "bewertung"


# ── Zweite Bauform: Nummer im Code, Art in eigener Spalte ─────────────────────────────────

ZWEITE = [
    ["Kriterienhauptgruppe", "", "", ""],
    ["Kennung", "Art", "Kurzbeschreibung", ""],
    ["KHG 1: Funktionales", "", "", ""],
    ["KG 1.1 Anmeldung", "", "", ""],
    ["K 1.1.1", "[ A ]", "Sind alle Muss-Anforderungen erfüllt?", ""],
    ["K 1.1.2", "[ B ]", "Beschreiben Sie auf max. 1 Seite", ""],
]


def test_zweite_bauform_liest_art_aus_der_spalte():
    k = ec.lies_matrix(_mappe(ZWEITE))
    codes = {x["code"]: x["art"] for x in k}
    assert codes == {"K 1.1.1": "ausschluss", "K 1.1.2": "bewertung"}


def test_zweite_bauform_ordnet_die_gruppen_richtig_zu():
    """⚠ `khg` und `kg` zeigen hier auf DIESELBE Spalte wie die Codes.

    Ohne Riegel würde jede Kriteriumszeile als neue Hauptgruppe gelesen.
    """
    k = ec.lies_matrix(_mappe(ZWEITE))
    assert all(x["khg"].startswith("KHG 1") for x in k)
    assert all(x["kg"].startswith("KG 1.1") for x in k)


def test_ohne_art_spalte_wird_nichts_geraten():
    """Ein falsch als Bewertungskriterium geführter Ausschluss ist ein Schaden."""
    zeilen = [r[:] for r in ZWEITE]
    zeilen[1] = ["Kennung", "Hinweis", "Kurzbeschreibung", ""]   # keine Spalte „Art"
    assert ec.lies_matrix(_mappe(zeilen)) == []


def test_zahl_allein_ist_kein_code():
    """Ohne das führende „K" ginge jede Zahl einer Gewichtungsspalte als Code durch."""
    zeilen = [r[:] for r in ZWEITE]
    zeilen[4][0] = "1.1.1"
    zeilen[5][0] = "2.2.2"
    assert ec.lies_matrix(_mappe(zeilen)) == []


# ── Blattwahl ─────────────────────────────────────────────────────────────────────────────

def test_marker_auf_einem_nebenblatt_wird_gefunden():
    """Der Marker sass gemessen auf „Erklärung", „Übersicht", „Erläuterungen"."""
    wb = openpyxl.Workbook()
    wb.active.title = "Deckblatt"
    wb.active.append(["nichts hier"])
    ws = wb.create_sheet("Erläuterungen")
    for z in ERSTE:
        ws.append(z)
    puffer = io.BytesIO()
    wb.save(puffer)
    k = ec.lies_matrix(puffer.getvalue())
    assert len(k) == 1
    assert k[0]["blatt"] == "Erläuterungen"


# ── Verschachtelte Archive ────────────────────────────────────────────────────────────────

def test_datei_im_archiv_im_archiv(tmp_path):
    """⚠ Der Volltext-Index notiert solche Pfade mit `::`; zwei Matrizen lagen so."""
    innen = io.BytesIO()
    with zipfile.ZipFile(innen, "w") as zf:
        zf.writestr("Anlage 510-3 Kriterienkatalog.xlsx", b"INHALT")
    aussen = tmp_path / "Vergabeunterlagen.zip"
    with zipfile.ZipFile(aussen, "w") as zf:
        zf.writestr("Version 3/Z42.zip", innen.getvalue())
    daten = ec.lies_datei(aussen, "Version 3/Z42.zip::Anlage 510-3 Kriterienkatalog.xlsx")
    assert daten == b"INHALT"


def test_fehlende_datei_gibt_none_statt_zu_werfen(tmp_path):
    p = tmp_path / "leer.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("egal.txt", b"x")
    assert ec.lies_datei(p, "gibtsnicht.xlsx") is None
