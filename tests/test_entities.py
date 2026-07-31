"""Klassifikator-Tests. Jeder Fall stammt aus echten TED-Daten (DE 2023-06)."""

import pytest

from govisor.entities import Kind, blocking_key, classify, normalize_company


@pytest.mark.parametrize("name,expected", [
    # 'Stiftung & Co. KG' is a legal form, not a foundation. Max Bögl builds roads.
    ("Max Bögl Stiftung & Co.KG", Kind.COMPANY),
    ("AWO Kreisverband Heinsberg e.V.", Kind.ASSOCIATION),
    # 'Internationaler Bund' is a charity, not a federal body — bare 'bund' must
    # not trigger the public-body rule. The gGmbH is still a company though:
    # charitable status does not change the legal form, and it is registered.
    ("Internationaler Bund - IB Südwest gGmbH", Kind.COMPANY),
    ("Bundesanstalt für Immobilienaufgaben", Kind.PUBLIC),
    ("Zweckverband VHS Unteres Pegnitztal", Kind.PUBLIC),
    ("ARGE Hentschke Bau/Amand/Gleisbau Bautzen", Kind.CONSORTIUM),
    ("Bietergemeinschaft Ecosoil Ost GmbH V & C Metzner GmbH", Kind.CONSORTIUM),
    # Sole proprietorships are companies, just usually too small for the register.
    ("Autohaus Schlingmann", Kind.COMPANY),
    ("Elektro Hansen", Kind.COMPANY),
    ("Malerfachbetrieb Richter", Kind.COMPANY),
    ("Ingenieurbüro Heinrichs", Kind.COMPANY),
    # Actual natural persons — freelancers. No register will ever hold them.
    ("Paul Skidmore", Kind.PERSON),
    ("Juliet Claire Weenink-Griffiths", Kind.PERSON),
    ("Sächsische Bau GmbH", Kind.COMPANY),
])
def test_classify(name, expected):
    assert classify(name).kind is expected


def test_german_compounds_defeat_word_boundaries():
    # 'Ingenieurbüro' contains 'büro', but \bbüro\b never matches it. Substring
    # matching is not sloppiness here, it is the only thing that works.
    assert classify("Ingenieurbüro Floecksmühle").kind is Kind.COMPANY
    assert classify("Malerfachbetrieb Richter").kind is Kind.COMPANY


@pytest.mark.parametrize("name,expected", [
    ("Leonhard Weiss GmbH & Co. KG", "leonhard weiss"),
    ("Philips GmbH", "philips"),
    ("Ed. Züblin Aktiengesellschaft", "ed zueblin"),
    ("Zittauer Bildungsgesellschaft gemeinnützige GmbH", "zittauer bildungsgesellschaft"),
    # Long form must collapse before the bare 'gesellschaft' rule sees it.
    ("Muster Gesellschaft mit beschränkter Haftung", "muster"),
])
def test_normalize_company(name, expected):
    assert normalize_company(name) == expected


def test_normalisation_bridges_spelling_noise():
    # Same firm, two spellings in TED. Normalisation alone must not need fuzzy.
    assert normalize_company("Rhiem & Sohn Kies und Sand GmbH & Co. KG") == \
           normalize_company("Rhiem und Sohn Kies und Sand GmbH & Co. KG")


def test_blocking_key_skips_noise_tokens():
    assert blocking_key("Fa.Hentrich GmbH Gebäudereinigung") == "hentrich"
