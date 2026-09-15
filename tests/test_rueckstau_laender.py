"""Der Rückstau entscheidet, wer drankommt — und er rechnete nur Deutschland.

⚠ WARUM ES DIESE DATEI GIBT. Sven am 2026-09-15, beim Lesen des Lageberichts: „in LU gibts
erst 3 Zips?" Ja — und der Grund war nicht der Abrufer, sondern die Liste, auf der er nicht
stand. `rueckstau.py` las `data/gold/DE/lead_export.parquet`, fest verdrahtet. Luxemburgische,
österreichische und schweizerische Adressen kommen in deutschen Leads nicht vor, also stand
der Rückstau dieser drei Abrufer dauerhaft auf **0** — und der Dauerarbeiter wählt nach
Rückstau.

Seit dem 2026-08-18 holt der Tageslauf keine Unterlagen mehr („das macht der Dauerarbeiter").
Vier Wochen lang hat damit niemand die Unterlagen von LU, AT und CH geholt:

    LU    169 abrufbare Vorgänge   (Manifest kannte 3, auf der Platte lagen 3)
    AT    254
    CH  1.599

⚠ Bei Luxemburg ist das nicht nachholbar — dort verschwinden die Unterlagen nach Fristende.
Ein Abrufer, der nicht auf der Liste steht, sieht aus wie einer, der nichts zu tun hat.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

WURZEL = pathlib.Path(__file__).resolve().parent.parent
SKRIPT = WURZEL / "scripts" / "rueckstau.py"
QUELLE = SKRIPT.read_text(encoding="utf-8")


def _modul():
    spec = importlib.util.spec_from_file_location("_rs", SKRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_kein_land_ist_fest_verdrahtet():
    """⚠ Der Kern des Fehlers, und er ist mit dem Auge zu sehen: ein Pfad mit `"DE"` darin.
    Die Zählung muss über `laender.AKTIV` laufen, sonst ist das nächste Land wieder blind."""
    kern = QUELLE.split("def rueckstand(")[1].split("\ndef ")[0]
    assert "from govisor.laender import AKTIV" in QUELLE, \
        "die Länderliste kommt nicht aus `govisor/laender.py`"
    assert '"DE"' not in kern and "'DE'" not in kern, (
        "in `rueckstand()` steht wieder ein festes DE — dann zählt sie nur deutsche Leads "
        "und alle anderen Abrufer bekommen Rückstau 0")


def test_das_manifest_liegt_beim_land_des_abrufers():
    """`docfetch_lu` schreibt nach `data/docs/LU`, nicht nach `data/docs/DE`. Wer im falschen
    Verzeichnis nachsieht, hält jeden Fehlschlag für einen Erstversuch."""
    m = _modul()
    assert m._land_von("lu") == "LU"
    assert m._land_von("vergabeportal_at") == "AT"
    assert m._land_von("simap_docs") == "CH"
    assert m._land_von("cosinex") == "DE"
    assert m._manifest_ort("lu").name == "LU"


def test_die_anderen_laender_tauchen_im_rueckstau_auf():
    """Die Gegenprobe am echten Bestand: LU, AT und CH müssen sichtbar werden, sobald es
    dort offene Leads mit Unterlagen-Link gibt."""
    if not (WURZEL / "data" / "gold" / "LU" / "lead_export.parquet").exists():
        pytest.skip("kein Gold — frische Arbeitskopie")
    m = _modul()
    zahlen = {k: roh for k, _erw, roh in m.rueckstand()}
    fremd = {k: v for k, v in zahlen.items() if k in ("lu", "vergabeportal_at", "simap_docs")}
    assert fremd, "kein einziger Abrufer ausserhalb Deutschlands in der Rechnung"
    assert any(v > 0 for v in fremd.values()), (
        f"alle nicht-deutschen Abrufer stehen auf 0: {fremd} — genau der Zustand, in dem "
        f"Luxemburg vier Wochen lang keine Unterlagen bekam")
