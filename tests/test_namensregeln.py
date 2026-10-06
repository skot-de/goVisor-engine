"""Vertretungsklauseln im MERGE-SCHLÜSSEL, nicht nur im Anzeigenamen.

⚠ WARUM DIESE DATEI EXISTIERT. `names.clean_display_name` löste „Bundesrepublik Deutschland,
vertreten durch X" seit dem 2026-07-29 auf X auf — aber nur für die ANZEIGE.
`entities.normalize_company` schnitt die Klausel stumpf ab und behielt den GENERISCHEN Teil.
Ergebnis, gemessen am 2026-10-06 im DE-Silber: die Entität `name:freistaat bayern` trug 297
verschiedene Stellen in 71 Orten (Universität Würzburg, Bayerischer Landtag, Oberlandesgericht
München …) und zeigte daneben EINEN Namen an. Ein Name, 297 Auftraggeber dahinter.

Die Tests hier halten vier Dinge fest, die jeweils eine Messung gekostet haben:

  1. Hoheitsträger → vertretene Stelle, spezifischer Präfix → Präfix. (`test_hoheit_*`)
  2. Das Hoheitsmuster liegt im LÄNDERPROFIL. Als deutsche Modul-Regex traf es „Republik
     Österreich vertreten durch …" nie — 5.251 AT-Zeilen unter einer Entität.
  3. `endvertreten`/`dieses vertreten`: das alte Muster traf „vertreten" INNERHALB von
     „endvertreten" und liess das „end" im Schlüssel stehen. 118 DE-Schlüssel / 3.206 Zeilen,
     darunter `'land schleswig holstein end'` mit 1.679.
  4. Mehrzeilige Namen: `.*$` ohne DOTALL hielt am Umbruch. 10.038 DE-Käufernamen tragen
     einen Umbruch, 8.108 Zeilen davon zusammen mit „vertreten durch".
"""
from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest                                               # noqa: E402

from govisor import locales                                 # noqa: E402
from govisor.entities import normalize_company as N         # noqa: E402
from govisor.names import clean_display_name as D           # noqa: E402
from govisor.names import resolve_representation as R       # noqa: E402


@pytest.fixture(autouse=True)
def _de():
    """Jeder Test startet im DE-Profil — sonst erbt er das Land des vorigen."""
    locales.use("DE")
    yield
    locales.use("DE")


# ── 1. Die Entscheidung: generisch oder spezifisch? ──────────────────────────────────────

def test_hoheit_wird_zur_vertretenen_stelle():
    assert N("Freistaat Bayern vertreten durch die Julius-Maximilians-Universitaet Wuerzburg") \
        == "julius maximilians universitaet wuerzburg"
    assert N("Bundesrepublik Deutschland, vertreten durch das Beschaffungsamt des BMI") \
        == "beschaffungsamt des bmi"
    assert N("Land Baden-Wuerttemberg vertreten durch das Logistikzentrum Baden-Wuerttemberg") \
        == "logistikzentrum baden wuerttemberg"


def test_spezifischer_praefix_bleibt_der_schluessel():
    """Hier ist der Präfix die Stelle — sonst würde „Stadt Nürnberg" zu „Hochbauamt"."""
    assert N("Stadt Nuernberg, vertreten durch das Hochbauamt") == "stadt nuernberg"
    assert N("Max-Planck-Gesellschaft, vertreten durch das MPI fuer Plasmaphysik") \
        == "max planck gesellschaft"
    assert N("Bundesagentur fuer Arbeit (BA), vertreten durch den Einkauf") \
        == "bundesagentur fuer arbeit"


def test_zwei_stellen_unter_einem_hoheitstraeger_trennen_sich():
    """Der eigentliche Zweck: 297 Stellen unter `freistaat bayern` waren EINE Entität."""
    a = N("Freistaat Bayern vertreten durch den Bayerischen Landtag - Landtagsamt")
    b = N("Freistaat Bayern vertreten durch das Staatliche Hochbauamt Wuerzburg")
    assert a != b and a and b


def test_vertretungskette_nimmt_die_erste_stelle():
    assert N("Land Hessen, dieses vertreten durch Hessen Mobil, dieses vertreten durch Abt. X") \
        == "hessen mobil"


def test_anzeige_und_schluessel_meinen_dasselbe():
    """⚠ Der Kern von Fallenkatalog C9: beide müssen auf DIESELBE Stelle zeigen."""
    roh = "Bundesrepublik Deutschland, vertreten durch das Bundesministerium fuer Gesundheit"
    assert D(roh) == "Bundesministerium fuer Gesundheit"
    assert N(roh) == N(D(roh)) == "bundesministerium fuer gesundheit"


# ── 2. Das Muster gehoert ins Laenderprofil ──────────────────────────────────────────────

def test_oesterreich_hat_ein_eigenes_hoheitsmuster():
    """Als deutsche Modul-Regex traf das Muster „Republik Österreich" nie."""
    locales.use("AT")
    assert R("REPUBLIK ÖSTERREICH vertreten durch die Bundesministerin fuer Landesverteidigung") \
        == "Bundesministerin fuer Landesverteidigung"
    assert R("Republik Österreich (Bund) vertreten durch den Bundesminister fuer Inneres") \
        == "Bundesminister fuer Inneres"
    assert R("Auftraggeber ist die Republik Österreich (Bund), vertreten durch das BMF") == "BMF"
    # ⚠ Gegenprobe: die Stellen selbst bleiben die Stellen.
    assert R("Bundesimmobiliengesellschaft m.b.H. vertreten durch Unternehmensbereich Schulen") \
        == "Bundesimmobiliengesellschaft m.b.H."


def test_schweiz_kanton_ja_gemeinde_nein():
    locales.use("CH")
    assert R("Kanton Solothurn, vertreten durch das Hochbauamt") == "Hochbauamt"
    # Eine Gemeinde ist die Stelle, kein Hoheitsdach — wie „Stadt Nürnberg" in DE.
    assert R("Einwohnergemeinde Schaffhausen, vertreten durch das Baureferat") \
        == "Einwohnergemeinde Schaffhausen"


def test_land_ohne_gemessenes_muster_bleibt_beim_alten_verhalten():
    """LU: 8 Namen mit Klausel, kein wiederkehrender Hoheitsträger → kein Muster erfunden."""
    locales.use("LU")
    assert locales.active().re_sovereign.pattern == r"(?!x)x"
    assert R("Ville de Luxembourg, vertreten durch das Bauamt") == "Ville de Luxembourg"


def test_jedes_profil_hat_das_feld():
    """Ein neues Land darf das Feld leer lassen — aber nicht vergessen, dass es existiert."""
    for code in locales.LOCALES:
        assert hasattr(locales.LOCALES[code], "re_sovereign"), code


# ── 3. Die `end`/`dieses`-Falle ──────────────────────────────────────────────────────────

def test_endvertreten_laesst_kein_end_stehen():
    """⚠ `'land schleswig holstein end'` war ein echter Schlüssel mit 1.679 Zeilen."""
    k = N("Land Schleswig-Holstein endvertreten durch Gebaeudemanagement Schleswig-Holstein")
    assert k == "gebaeudemanagement schleswig holstein"
    assert not k.endswith(" end")


def test_dieses_vertreten_laesst_kein_dieses_stehen():
    k = N("Bundesrepublik Deutschland, diese vertreten durch das Bundesamt fuer Bauwesen")
    assert k == "bundesamt fuer bauwesen"
    assert "diese" not in k.split()


def test_abgeschnittener_name_wird_nicht_zum_artikel():
    """„… vertreten durch den" ohne Fortsetzung: 7 Anzeigenamen hiessen wörtlich „Den"."""
    assert N("Bundesrepublik Deutschland vertreten durch den") == "bundesrepublik deutschland"
    assert D("Bundesrepublik Deutschland vertreten durch den") == "Bundesrepublik Deutschland"


# ── 4. Mehrzeilige Namen ─────────────────────────────────────────────────────────────────

def test_zeilenumbruch_nach_der_klausel_schneidet_trotzdem_ab():
    """⚠ Ohne re.S hielt `.*$` am Umbruch: der Rest landete im Schlüssel."""
    k = N("Rhein-Main-Donau GmbH vertreten durch die RMD\nWasserstrassen GmbH Muenchen")
    assert k == "rhein main donau"
    assert "vertreten" not in k


def test_representation_ist_dotall_in_jedem_profil():
    for code, loc in locales.LOCALES.items():
        assert loc.re_representation.flags & re.S, f"{code}: re_representation ohne DOTALL"


# ── 5. Die Agent-Form zeigt in die andere Richtung ───────────────────────────────────────

def test_im_namen_und_auf_rechnung_behaelt_den_handelnden():
    """Hier ist der PRÄFIX die handelnde Stelle, nicht der Teil danach.

    Ohne das stand `'db projektbau im namen und auf rechnung der db netz'` als eigener
    Schlüssel mit 26 Orten im Bestand (232 Namen / 2.183 Zeilen über alle Varianten).
    """
    assert N("DB ProjektBau GmbH im Namen und auf Rechnung der DB Netz AG") == "db projektbau"
    assert N("DB PROJEKTBAU GMBH, IM NAMEN UND AUF RECHNUNG DER DB-NETZ AG") == "db projektbau"


# ── 6. Robustheit ────────────────────────────────────────────────────────────────────────

def test_leere_und_klauselfreie_namen_bleiben():
    assert N("") == "" and N(None) == ""
    assert R("") == "" and R(None) is None
    assert N("Stadt Koeln") == "stadt koeln"


def test_idempotent():
    roh = "Bundesrepublik Deutschland, vertreten durch das Bundesministerium des Innern"
    assert N(N(roh)) == N(roh)
    assert R(R(roh)) == R(roh)
