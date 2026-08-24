"""e-Vergabe des Bundes — den Grund lesen, nicht das Ergebnis.

Ohne Netz. Die Unterlagenseite antwortet auf jeden Fehlgriff mit demselben nichtssagenden
Satz; 23 Vorgänge standen deshalb als „keine Unterlagen" im Manifest, obwohl kein einziger
davon eine Vergabe ohne Unterlagen war.
"""
from __future__ import annotations

import datetime as dt

from govisor import docfetch_evergabe_online as eo
from govisor import docfetch_queue as q

HEUTE = dt.date(2026, 8, 24)

RUMPF = ("Ausschreibungsdetails\nRahmenvereinbarung Schutzweste\n"
         "Veröffentlichungsdatum:\n\n01.06.2026\n\nAbgabefrist Angebot:\n\n{frist}\n\n"
         "Vergabestelle:\n\nFachstelle Maschinenwesen Süd\n")

VERTRAULICH = ("Meine e-Vergabe\n Teilnahme aktivieren\n"
               " Aus Gründen der Vertraulichkeit sind die Vergabeunterlagen nicht frei "
               "zugänglich.\nDer nachfolgenden Bekanntmachung können Sie entnehmen, wie die "
               "vollständigen Unterlagen anzufordern sind.\n")


def test_vertraulichkeit_ist_blockiert_nicht_leer():
    """Die Unterlagen EXISTIEREN — sie werden bewusst zurückgehalten."""
    r = eo.grund_von_detailseite(RUMPF.format(frist="31.08.2026 11:00") + VERTRAULICH, HEUTE)
    assert r["status"] == "gated"
    assert q.BLOCKIERT.get(r["status"]) == "konto"


def test_vertraulichkeit_schlaegt_die_frist():
    """Auch mit verstrichener Frist bleibt der Grund die Vertraulichkeit."""
    r = eo.grund_von_detailseite(RUMPF.format(frist="09.06.2026 11:00") + VERTRAULICH, HEUTE)
    assert r["status"] == "gated"


def test_verstrichene_frist_ist_dauerhaft():
    r = eo.grund_von_detailseite(RUMPF.format(frist="09.06.2026 11:00"), HEUTE)
    assert r["status"] == "abgelaufen"
    assert r["status"] in q.DAUERHAFT
    assert "09.06.2026" in r["note"]


def test_offene_frist_bleibt_offen():
    """⚠ Kein Grund gefunden heißt „nachsehen", nicht „nichts da"."""
    r = eo.grund_von_detailseite(RUMPF.format(frist="31.08.2026 11:00"), HEUTE)
    assert r["status"] == "leer"
    assert r["status"] not in q.DAUERHAFT
    assert r["status"] not in q.KEIN_FEHLSCHLAG


def test_frist_am_selben_tag_ist_nicht_verstrichen():
    r = eo.grund_von_detailseite(RUMPF.format(frist="24.08.2026 11:00"), HEUTE)
    assert r["status"] == "leer"


def test_auch_die_vorgangsseite_weg():
    r = eo.grund_von_detailseite("Hinweis\nDiese Information steht aktuell nicht zur "
                                 "Verfügung.\n", HEUTE)
    assert r["status"] == "leer"
    assert "Vorgangsseite" in r["note"]


def test_leerer_text_behauptet_nichts():
    assert eo.grund_von_detailseite("", HEUTE)["status"] == "leer"


# ── URL-Ableitung ─────────────────────────────────────────────────────────────────────────

def test_detailseite_wird_abgeleitet():
    assert eo.detailseite("https://www.evergabe-online.de/tenderdocuments.html?id=880614") \
        == "https://www.evergabe-online.de/tenderdetails.html?id=880614"


def test_tenderer_zweig_bleibt_gesperrt():
    """Die robots.txt sperrt /tenderer/ ausdrücklich."""
    assert eo.unterlagen_url("https://www.evergabe-online.de/tenderer/x.html?id=1") is None
