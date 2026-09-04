"""Die eine Laenderliste (`govisor/laender.py`) und ihre Gegenprobe.

⚠ Zwei Listen beschreiben dasselbe aus verschiedenen Richtungen:
  · `laender.AKTIV`      — die ERKLAERUNG: dieses Land wollen wir bauen
  · `data/gold/*/lead_export.parquet` — der BESTAND: dieses Land ist gebaut
Laufen sie auseinander, hat entweder jemand ein Land erklaert und nie gebaut, oder eines
gebaut und nie erklaert. Beides gehoert gesagt.
"""
import importlib.util
import pathlib
import re

import pytest

from govisor import laender

WURZEL = pathlib.Path(__file__).resolve().parent.parent

# Die Dateien, die ihre Liste seit dem 2026-09-04 ABLEITEN statt zu halten.
ABGELEITET = (
    "scripts/export_strategie.py",
    "scripts/export_web_leads.py",
    "scripts/region_ableiten.py",
    "scripts/pruefe_verdrahtung.py",
    "scripts/process_upload.py",
    "scripts/export_anforderungsprofil.py",
    "scripts/export_fenster.py",
    "scripts/export_stellenprofil.py",
    "scripts/export_landing.py",
)


def test_aktiv_ist_nicht_leer_und_kennt_nur_echte_codes():
    from govisor import countries
    echte = {c.alpha2 for c in countries.all_countries()}
    assert laender.AKTIV, "eine leere AKTIV-Liste wuerde jede Pruefung stumm gruen machen"
    for cc in laender.AKTIV:
        assert cc in echte, f"{cc} steht in keiner Laender-Registry"
    assert len(set(laender.AKTIV)) == len(laender.AKTIV), "doppelter Eintrag"


def test_erklaerung_und_bestand_stimmen_ueberein():
    """⚠ Die eigentliche Gegenprobe. `AKTIV` ist ausdruecklich, weil eine abgeleitete Liste
    zirkulaer waere — Luxemburg haette nie Gold bekommen, weil es kein Gold hatte. Genau
    deshalb braucht es DIESEN Test: sonst kann die Erklaerung vom Bestand wegdriften, ohne
    dass etwas rot wird.
    """
    gold = WURZEL / "data" / "gold"
    if not gold.exists():
        pytest.skip("kein data/gold — frische Arbeitskopie")
    gebaut = {d.name for d in gold.iterdir()
              if d.is_dir() and (d / "lead_export.parquet").exists()}
    if not gebaut:
        pytest.skip("noch nichts gebaut")

    erklaert_nicht_gebaut = set(laender.AKTIV) - gebaut
    gebaut_nicht_erklaert = gebaut - set(laender.AKTIV)
    assert not gebaut_nicht_erklaert, (
        f"{sorted(gebaut_nicht_erklaert)} ist gebaut, steht aber nicht in AKTIV — "
        f"entweder aufnehmen oder in UNVOLLSTAENDIG begruenden")
    assert not erklaert_nicht_gebaut, (
        f"{sorted(erklaert_nicht_gebaut)} steht in AKTIV, ist aber nicht gebaut")


def test_unvollstaendige_tragen_eine_begruendung():
    """⚠ „fehlt" darf nicht wie „vergessen" aussehen."""
    for cc, grund in laender.UNVOLLSTAENDIG.items():
        assert cc not in laender.AKTIV, f"{cc} kann nicht zugleich aktiv und unvollstaendig sein"
        assert len(grund) > 40, f"{cc}: Begruendung zu duenn"


def test_die_abgeleiteten_leiten_wirklich_ab():
    """⚠ Sonst schreibt jemand die Literalliste zurueck, und niemand merkt es.

    Die vier Dateien, die frueher im Waechter standen, sind dort seit dem Umbau NICHT mehr
    registriert — sie koennen also nicht mehr auf dem ueblichen Weg auffallen. Dieser Test
    ist ihr Ersatz.
    """
    literal = re.compile(r'(LAENDER|_ERLAUBT)\s*[:=]\s*[\(\[]\s*["\']DE["\']')
    for datei in ABGELEITET:
        t = (WURZEL / datei).read_text(encoding="utf-8")
        assert "laender import AKTIV" in t, f"{datei} leitet nicht mehr ab"
        assert not literal.search(t), (
            f"{datei} traegt wieder eine Literalliste — dann kann sie abdriften")
