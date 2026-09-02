"""Suche nach der Nummer, die man in der Hand hält.

Wer einen Vorgang sucht, hat eine Vergabenummer vom Briefkopf („BA090-26", „EK1/LA/2026/083").
Bis zum 2026-09-02 fand die Suche keine davon — und las eine vier- bis fünfstellige Zahl sogar
als Postleitzahl.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
CORE = (WURZEL / "web" / "lib" / "explorerCore.js").read_text(encoding="utf-8")
EXPORT = (WURZEL / "scripts" / "export_web_leads.py").read_text(encoding="utf-8")
SONDE = WURZEL / "web" / "scripts" / "pruefe-kennungssuche.mjs"


def _block(name: str) -> str:
    rest = CORE[CORE.index(f"function {name}("):]
    return rest[:rest.index("\n}")]


# ── die Quelle der Nummer ───────────────────────────────────────────────────────────────

def test_der_los_zweig_ist_ausgeschlossen():
    """⚠ DIE FALLE. `ProcurementProjectLot.ProcurementProject.ID` sieht fast gleich aus und
    trägt 124.145-mal den Platzhalter `LOT-0000` plus 40.103 UUIDs; der Zweig ohne `Lot` hat
    davon 8 bzw. 826. Wer mit `%` abkürzt, baut eine Suche, die bei „LOT-0000" tausende
    Treffer meldet."""
    stelle = EXPORT[EXPORT.index("def _vergabenummern"):]
    stelle = stelle[:stelle.index("VERGABENUMMER = ")]
    assert "path not like '%ProcurementProjectLot%'" in stelle
    assert "not lower(value) like 'lot-%'" in stelle


def test_die_nummer_kommt_aus_silber():
    """⚠ `_union()` baut Gold-Pfade. Die erste Fassung zeigte damit auf
    `data/gold/DE/attributes.parquet` — existiert nicht, null Treffer, keine Fehlermeldung."""
    stelle = EXPORT[EXPORT.index("def _vergabenummern"):]
    stelle = stelle[:stelle.index("VERGABENUMMER = ")]
    assert '_silber_union("attributes")' in stelle
    assert '_union("attributes")' not in stelle.replace('_silber_union("attributes")', "")


def test_die_nummer_steht_am_lead():
    dateien = list((WURZEL / "web" / "data").glob("leads-*.json"))
    if not dateien:
        return
    mit = ges = 0
    for f in dateien:
        roh = json.loads(f.read_text(encoding="utf-8"))
        for l in (roh if isinstance(roh, list) else roh.get("leads", [])):
            ges += 1
            mit += bool(l.get("vergabenr"))
    assert ges and mit / ges > 0.15, f"nur {mit}/{ges} Leads mit Vergabenummer"


# ── die Regel, die den Unterschied macht ────────────────────────────────────────────────

def test_kennung_schlaegt_die_plz_regel():
    """⚠ DER GRUND, warum die Reihenfolge zählt: 209 Vergabenummern im Bestand sind reine
    vier- bis fünfstellige Zahlen. Stünde die Kennungsprüfung hinter der PLZ-Regel, würden
    sie dauerhaft als Ortssuche gelesen — und der Nutzer bekäme einen Umkreis statt seines
    Vorgangs."""
    b = _block("classifyQuery")
    assert b.index("kennungIndex()") < b.index("plzLookup"), "die PLZ-Regel steht davor"
    assert b.index("kennungIndex()") < b.index("ORTE[q]"), "die Ortsliste steht davor"


def test_zu_kurze_kennungen_werden_nicht_indiziert():
    """„GST" und „_ELT" schrumpfen normalisiert auf drei Zeichen und träfen zufällig. 307
    solcher Werte stehen im Bestand — sie sind Abteilungskürzel, keine Kennung."""
    b = _block("kennungIndex")
    assert "n.length >= 4" in b


def test_die_schreibweise_ist_egal():
    """Dieselbe Nummer steht als `23-091676`, `23/091676` und `23 091676`."""
    assert "replace(/[^a-z0-9]+/g, '')" in CORE
    b = _block("kennungIndex")
    assert "replace('_', '-')" in b, "die zweite Schreibweise der Veröffentlichungsnummer fehlt"


def test_eine_kennung_hebt_den_branchenfilter_auf():
    """⚠ Wer eine Nummer einfügt, sitzt fast immer in der falschen Branche. Der Grundraum ist
    eine Vermutung über das Interesse, die exakte Kennung eine Ansage."""
    b = _block("visible")
    assert "!groups.kennung && l.branche !== aktiveBranche" in b


def test_der_index_gehoert_zum_bestand():
    """Ohne Verwerfen zeigte die Suche nach einem Branchenwechsel auf Leads, die nicht mehr
    geladen sind."""
    b = _block("setLeads")
    assert "_kennIndex = null" in b


# ── die Sonde ───────────────────────────────────────────────────────────────────────────

def test_die_sonde_laeuft_gruen():
    """⚠ Sie führt die ECHTEN Funktionen gegen die ECHTEN Lead-Dateien. Eine Abschrift ginge
    grün, während die benutzte Fassung eine Vergabenummer weiter als Postleitzahl liest.
    Der Browser-Durchgang war an diesem Tag nicht möglich (keine Anmeldung)."""
    if not shutil.which("node") or not (WURZEL / "web" / "data").glob("leads-*.json"):
        return
    r = subprocess.run(["node", str(SONDE)], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stderr[-500:]
    assert "0 verfehlt" in r.stdout
    assert "schlagen die PLZ-Regel" in r.stdout
    assert "bleibt Ortssuche" in r.stdout
