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


def test_gruppenname_geht_an_den_stamm():
    """⚠ Eine Gruppe hiess nach der falschen Tochter.

    Sven im Testlauf mit einer @netgo.de-Adresse (2026-08-21): „ich glaube die netgo ost ist
    nicht die zentrale netgo einheit oder?" Stimmte. Die Gruppe war inhaltlich richtig
    (14 Mitglieder, 98 Zuschlaege), aber der Anzeigename kam aus der Regel „haeufigster
    canonical_name" — und „netgo Ost GmbH" klebte an SECHS Entitaeten (dieselbe Firma,
    sechsmal verschieden geschrieben: HRB84278, HRB84278B, „HRB84278B,", HRB84278BerlinCh,
    zwei Umsatzsteuer-IDs), waehrend „NETGO GmbH" nur an einer klebte, dafuer mit
    Handelsregister-Beleg und den meisten Zuschlaegen.

    Haeufigkeit misst also, wie zerfranst die Schreibweise einer Tochter ist, nicht wer die
    Mutter ist. Jetzt gewinnt der STAMM: das Mitglied, dessen Name in den Namen der anderen
    steckt.
    """
    import pathlib
    import duckdb
    wurzel = pathlib.Path(__file__).resolve().parent.parent
    quelle = (wurzel / "scripts" / "export_suppliers.py").read_text(encoding="utf-8")
    i = quelle.index('NAMEN_SQL = """') + len('NAMEN_SQL = """')
    sql = quelle[i:quelle.index('"""', i)]

    con = duckdb.connect()
    zeilen = [("grp:netgo", n, f"n{k}") for k, n in enumerate(
        ["NETGO GmbH"] * 1                      # eine Entitaet, aber die Mutter
        + ["netgo Ost GmbH"] * 6                # sechs Schreibweisen derselben Tochter
        + ["netgo Süd GmbH", "netgo Nürnberg GmbH", "netgo Gießen GmbH"])]
    con.execute("CREATE TEMP TABLE w (identity_id VARCHAR, canonical_name VARCHAR, notice_id VARCHAR)")
    con.executemany("INSERT INTO w VALUES (?, ?, ?)", zeilen)
    con.execute("CREATE TEMP TABLE tops AS SELECT DISTINCT identity_id FROM w")
    con.execute(sql)
    name = con.execute("SELECT name FROM namen").fetchone()[0]
    assert name == "NETGO GmbH", f"die Gruppe heisst nach der Tochter: {name}"

    # Gegenprobe: ohne Stamm entscheidet weiterhin die Haeufigkeit.
    con.execute("DELETE FROM w")
    con.executemany("INSERT INTO w VALUES (?, ?, ?)", [
        ("grp:x", "Meier Bau GmbH", "a"), ("grp:x", "Meier Bau GmbH", "b"),
        ("grp:x", "Schulze Tief GmbH", "c")])
    con.execute("CREATE OR REPLACE TEMP TABLE tops AS SELECT DISTINCT identity_id FROM w")
    con.execute(sql)
    assert con.execute("SELECT name FROM namen").fetchone()[0] == "Meier Bau GmbH"
