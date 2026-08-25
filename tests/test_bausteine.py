"""Bausteinbibliothek ↔ Supabase (Ticket #23 §9/§12.3).

Ohne Netz und ohne Node: geprüft werden die Zusicherungen, die man einer TypeScript-Datei
nicht ansieht, wenn man sie nur überfliegt — und die teuer sind, wenn sie fallen.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROUTE = (ROOT / "web" / "app" / "api" / "blocks" / "route.ts").read_text(encoding="utf-8")
KRYPTO = (ROOT / "web" / "lib" / "blockCrypto.ts").read_text(encoding="utf-8")
LIB = (ROOT / "web" / "components" / "explorer" / "BausteinLibrary.tsx").read_text(encoding="utf-8")
SCHEMA = (ROOT / "supabase" / "0006_doc_analysis.sql").read_text(encoding="utf-8")


# ── Der Inhalt darf die Datenbank nie im Klartext erreichen ────────────────────────────────

def test_inhalt_geht_nur_verschluesselt_in_die_spalte():
    """⚠ Die Spalte heisst `content_encrypted`. Ein Klartext darin fiele niemandem auf."""
    assert "verschluessele(" in ROUTE
    # Kein Satz, der `content` roh in die Tabelle schreibt.
    assert not re.search(r"content_encrypted:\s*b\.content", ROUTE)
    assert not re.search(r"\bcontent:\s*b\.content", ROUTE)


def test_ohne_schluessel_wird_nichts_gespeichert():
    """Ein stiller Rückfall auf Klartext wäre der schlimmste Ausgang: er sieht aus wie Erfolg."""
    assert "KeinSchluessel" in KRYPTO and "KeinSchluessel" in ROUTE
    assert "503" in ROUTE, "fehlender Schlüssel muss als Störung antworten, nicht als Erfolg"


def test_schluessellaenge_wird_geprueft():
    """Ein zu kurzer Schlüssel aus der Umgebung darf nicht durchrutschen."""
    assert "!== 32" in KRYPTO


def test_jeder_baustein_bekommt_einen_eigenen_datenschluessel():
    """Das „Envelope": Hauptschlüssel tauschbar, ohne einen Baustein neu zu verschlüsseln."""
    assert KRYPTO.count("randomBytes(32)") >= 1     # Datenschlüssel je Satz
    assert "aes-256-gcm" in KRYPTO                  # authentifiziert, nicht nur verschlüsselt
    assert "getAuthTag" in KRYPTO and "setAuthTag" in KRYPTO


def test_kopf_und_laengenpruefung_passen_zusammen():
    """1 + 12 + 32 + 16 + 12 + 16 = 89. Wer eine Zahl ändert, muss beide ändern."""
    assert "daten.length < 89" in KRYPTO
    assert "subarray(89)" in KRYPTO


# ── bytea reist als Hex ────────────────────────────────────────────────────────────────────

def test_bytea_wird_als_hex_uebergeben():
    """⚠ Ein Buffer landete als `{"0":72,…}` in der Spalte — und fiele erst beim nächsten
    Entschlüsseln auf, also lange nach dem Schreiben."""
    assert 'toString("hex")' in ROUTE and '\\\\x' in ROUTE


# ── Archivieren statt Löschen ──────────────────────────────────────────────────────────────

def test_geloescht_wird_nicht_sondern_archiviert():
    """So steht es im Schema (§9.2) — ein Baustein kann in einem alten Angebot stecken."""
    assert "archived: true" in ROUTE
    assert ".delete()" not in ROUTE
    assert "archived" in SCHEMA


def test_archivierte_tauchen_nicht_wieder_auf():
    assert 'eq("archived", false)' in ROUTE


# ── Lokal-first bleibt lokal-first ─────────────────────────────────────────────────────────

def test_bibliothek_zeigt_zuerst_den_browser_stand():
    """⚠ Erst laden, dann anzeigen, hiesse: die Bibliothek ist beim Aufruf kurz leer — und
    eine leere Bausteinbibliothek liest sich wie Datenverlust."""
    i_lokal = LIB.index("const lokal = load();")
    i_fetch = LIB.index('fetch("/api/blocks")')
    assert i_lokal < i_fetch


def test_anmelden_verliert_keine_bausteine():
    """Was nur im Browser lag, muss beim ersten Abgleich hochwandern."""
    assert "nurLokal" in LIB and "merkmal" in LIB


def test_abgleich_erkennt_denselben_baustein_ohne_zeitstempel():
    """Sonst stünde derselbe Text nach dem Abgleich zweimal da."""
    i = LIB.index("const merkmal =")
    zeile = LIB[i:LIB.index("\n", i)]
    assert "theme" in zeile and "content" in zeile
    assert "saved_at" not in zeile and "Date" not in zeile
