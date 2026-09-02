"""Der eSender-Fehlgriff und sein Waechter.

Der Fehler, den diese Datei festnagelt (gemessen 2026-09-01): der Kaeufer traegt im
DÖE-eForms-XML KEIN NUTS-Feld, der eSender-Block darunter schon. Ein Suchlauf ueber den
ganzen Teilbaum fand dessen Wert und schrieb Bonn an Kaeufer in ganz Deutschland —
33.966 Silber-Zeilen, 393 Orte, EIN einziger NUTS-Wert im gesamten DÖE-Bestand. Derselbe
Griff holte auch die Kennung des eSenders, worauf 1.831 verschiedene Kaeufer zu EINER
Entitaet verschmolzen.

⚠ Ein Unit-Test allein haette das nie gefunden — jedes Stueck war fuer sich korrekt, und
der Fehler machte die Abdeckung BESSER statt schlechter. Deshalb hier beides: der Parser
am echten XML-Ausschnitt UND die Schranken des Waechters, der es im Bestand wiedererkennt.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from govisor import schema  # noqa: E402

import pruefe_nuts_vorgabe as waechter  # noqa: E402

# Der echte Aufbau aus data/raw_doe/DE/2026-07.eforms.zip, gekuerzt: der Kaeufer sitzt in
# Magdeburg und hat KEIN CountrySubentityCode; das einzige im Dokument gehoert dem eSender.
_DOE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ContractNotice xmlns="urn:oasis:names:specification:ubl:schema:xsd:ContractNotice-2"
                xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
                xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:RegulatoryDomain>de-uvgo</cbc:RegulatoryDomain>
  <cbc:NoticeTypeCode listName="competition">cn-standard</cbc:NoticeTypeCode>
  <cac:ContractingParty>
    <cac:Party>
      <cbc:WebsiteURI>http://www.lhw.sachsen-anhalt.de</cbc:WebsiteURI>
      <cac:PartyName>
        <cbc:Name>Landesbetrieb fuer Hochwasserschutz Sachsen-Anhalt</cbc:Name>
      </cac:PartyName>
      <cac:PostalAddress>
        <cbc:CityName>Magdeburg</cbc:CityName>
        <cbc:PostalZone>39104</cbc:PostalZone>
        <cac:Country><cbc:IdentificationCode>DEU</cbc:IdentificationCode></cac:Country>
      </cac:PostalAddress>
      <cac:Contact>
        <cbc:ElectronicMail>vergabestelle.nord@lhw.sachsen-anhalt.de</cbc:ElectronicMail>
      </cac:Contact>
      <cac:ServiceProviderParty>
        <cbc:ServiceTypeCode listName="organisation-role">ted-esen</cbc:ServiceTypeCode>
        <cac:Party>
          <cac:PartyName><cbc:Name>Beschaffungsamt des BMI</cbc:Name></cac:PartyName>
          <cac:PostalAddress>
            <cbc:CityName>Bonn</cbc:CityName>
            <cbc:PostalZone>53119</cbc:PostalZone>
            <cbc:CountrySubentityCode listName="nuts">DEA22</cbc:CountrySubentityCode>
          </cac:PostalAddress>
          <cac:PartyLegalEntity><cbc:CompanyID>0204: 991-1405-10</cbc:CompanyID></cac:PartyLegalEntity>
          <cac:Contact><cbc:ElectronicMail>ticket@bescha.bund.de</cbc:ElectronicMail></cac:Contact>
        </cac:Party>
      </cac:ServiceProviderParty>
    </cac:Party>
  </cac:ContractingParty>
</ContractNotice>
"""


def _kaeufer():
    notice = schema.parse(_DOE_XML.encode("utf-8"), "pruef-1")
    kaeufer = [p for p in notice.parties if p.role == "buyer"]
    assert len(kaeufer) == 1, "genau eine Kaeuferzeile erwartet"
    return kaeufer[0]


def test_kaeufer_erbt_die_nuts_des_esenders_nicht():
    """Der Kern. Kein eigenes NUTS-Feld heisst NICHTS — nicht „das des Absenders"."""
    assert _kaeufer().nuts is None


def test_kaeufer_erbt_die_kennung_des_esenders_nicht():
    """Die teurere Haelfte desselben Fehlgriffs: eine geteilte Kennung verschmilzt
    fremde Kaeufer zu einer Entitaet. 1.831 Namen hingen an dieser einen."""
    assert _kaeufer().national_id != "0204: 991-1405-10"


def test_die_eigenen_felder_des_kaeufers_bleiben_erhalten():
    """Der Riegel darf nicht mehr abschneiden als noetig — sonst tauscht man einen
    stillen Fehler gegen einen stillen Verlust."""
    k = _kaeufer()
    assert k.town == "Magdeburg"
    assert k.postal_code == "39104"
    assert k.email == "vergabestelle.nord@lhw.sachsen-anhalt.de"
    assert k.url == "http://www.lhw.sachsen-anhalt.de"
    assert "Hochwasserschutz" in (k.name or "")


def test_kaeufer_ohne_eigene_anschrift_erbt_nicht_die_des_esenders():
    """Der Fall, der ohne den Riegel Ort UND PLZ des Absenders uebernaehme."""
    ohne = _DOE_XML.replace(
        """      <cac:PostalAddress>
        <cbc:CityName>Magdeburg</cbc:CityName>
        <cbc:PostalZone>39104</cbc:PostalZone>
        <cac:Country><cbc:IdentificationCode>DEU</cbc:IdentificationCode></cac:Country>
      </cac:PostalAddress>
""", "")
    assert ohne != _DOE_XML
    notice = schema.parse(ohne.encode("utf-8"), "pruef-2")
    k = [p for p in notice.parties if p.role == "buyer"][0]
    assert k.town is None and k.postal_code is None and k.nuts is None


def test_iter_named_ausserhalb_laesst_den_fremden_teilbaum_aus():
    import xml.etree.ElementTree as ET
    wurzel = ET.fromstring(_DOE_XML)
    partei = next(iter(schema._iter_named(wurzel, "Party")))
    alle = [e for e in schema._iter_named(partei, "CityName")]
    eigene = [e for e in schema._iter_named_ausserhalb(
        partei, "CityName", schema._FREMDE_PARTEI_TAGS)]
    assert [e.text for e in alle] == ["Magdeburg", "Bonn"]
    assert [e.text for e in eigene] == ["Magdeburg"]


# ── Der Waechter ────────────────────────────────────────────────────────────────────

def _urteil(aufgeloest):
    treffer = waechter.bewerte("DE", aufgeloest, stellen=3)
    assert len(treffer) == 1
    return treffer[0]


def test_waechter_erkennt_den_vorgabewert():
    """Die Signatur von DEA22, nachgebaut: eine Handvoll echter Bonner Kaeufer, dazu
    Masse aus ganz Deutschland — Mehrheit fremd, ueber viele Regionen verstreut."""
    zeilen = [("DEA22", "Bonn", "DEA", 300)]
    for ort, region in (("Magdeburg", "DEE"), ("Erfurt", "DEG"), ("Berlin", "DE3"),
                        ("Nuernberg", "DE2"), ("Hannover", "DE9"), ("Mainz", "DEB")):
        zeilen.append(("DEA22", ort, region, 500))
    b = _urteil(zeilen)
    assert b["verdaechtig"] is True
    assert len(b["fremde_regionen"]) == 6


def test_waechter_schweigt_bei_einer_blossen_namensdoppelung():
    """DEE02, echt gemessen: Halle (Saale) ist Sachsen-Anhalt, Halle (Westf.) ist NRW.
    95 % „fremd" — aber alles in EINE Richtung. Das ist ein mehrdeutiger Ortsname,
    kein Vorgabewert, und genau hier trennt sich der Waechter von einer Quoten-Schranke."""
    b = _urteil([("DEE02", "Halle", "DEA", 750), ("DEE02", "Halle (Saale)", "DEE", 40)])
    assert b["fremd_quote"] > 0.9
    assert b["verdaechtig"] is False


def test_waechter_schweigt_bei_einer_ehrlichen_kennung_mit_vielen_orten():
    """DED42 (Erzgebirgskreis) traegt 110 verschiedene Orte — mehr als DEA22 je hatte.
    Alle liegen in Sachsen. Viele Orte allein sind KEIN Befund."""
    zeilen = [("DED42", f"Ort {i}", "DED", 20) for i in range(110)]
    b = _urteil(zeilen)
    assert b["orte"] == 110 and b["verdaechtig"] is False


def test_waechter_ignoriert_zu_kleine_kennungen():
    """Unter der Mindestzahl ist jede Quote Zufall — dann lieber nichts sagen."""
    zeilen = [("DEA22", ort, reg, 5) for ort, reg in
              (("Magdeburg", "DEE"), ("Erfurt", "DEG"), ("Berlin", "DE3"), ("Mainz", "DEB"))]
    assert waechter.bewerte("DE", zeilen, stellen=3) == []


def test_eine_blosse_ortszahl_haette_den_fehler_nicht_gefunden():
    """Festgenagelt, damit niemand die Regel spaeter zu „viele Orte" vereinfacht:
    DEA22 spannte 92 Orte, der ehrliche Hoechstwert im Bestand lag bei 110."""
    quelltext = (ROOT / "scripts" / "pruefe_nuts_vorgabe.py").read_text(encoding="utf-8")
    assert "110" in quelltext, "die gemessene Gegenzahl gehoert in die Begruendung"


@pytest.mark.parametrize("schluessel,grund", sorted(waechter.AUSNAHMEN.items()))
def test_jede_ausnahme_hat_eine_begruendung(schluessel, grund):
    assert grund and len(grund) > 20, f"{schluessel} braucht einen echten Grund"


def test_ausnahmen_treffen_noch_zu():
    """Eine Ausnahme fuer etwas, das nicht mehr anschlaegt, ist ein Persilschein.

    Sie darf nur stehenbleiben, solange der Befund wirklich auftritt — sonst waechst
    die Liste still weiter, bis sie alles enthaelt.
    """
    if not waechter.AUSNAHMEN:
        pytest.skip("keine Ausnahmen eingetragen")
    if not (ROOT / "data" / "silver").exists():
        pytest.skip("kein Silber-Bestand")
    getroffen = set()
    for land in {k[0] for k in waechter.AUSNAHMEN}:
        getroffen |= {(land, b["nuts"]) for b in waechter.befunde(land) if b["verdaechtig"]}
    veraltet = set(waechter.AUSNAHMEN) - getroffen
    assert not veraltet, f"Ausnahme ohne Befund: {sorted(veraltet)}"
