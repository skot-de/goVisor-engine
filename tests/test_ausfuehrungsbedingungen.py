"""Ausfuehrungsbedingungen: der Parser paart, was die flache Tabelle verliert.

WARUM ES DIESE PARSER-AENDERUNG BRAUCHTE. `ContractExecutionRequirement` kommt je
Vorgang bis zu fuenfmal vor. Jedes Vorkommen traegt ein `ExecutionRequirementCode`,
und erst dessen `@listName` sagt, WOVON die Rede ist — elektronische Rechnung,
vorbehaltene Ausfuehrung, Geheimhaltung, E-Katalog.

In `silver/attributes` landen Wert und Listenname als getrennte Zeilen ohne Index,
beide alphabetisch. Ein echter Vorgang:

    ExecutionRequirementCode            false / no / not-allowed / required / true
    ExecutionRequirementCode@listName   ecatalog-submission / einvoicing /
                                        esignature-submission / nda /
                                        reserved-execution

Welcher Wert zu welchem Merkmal gehoert, ist dort nicht mehr feststellbar — 21.874
Leads hingen daran. Der Parser sieht beides am SELBEN Knoten; das ist der ganze
Unterschied und nur dort zu haben.

Der Beleg, dass es wirkt, ist nicht „es laeuft durch", sondern: **je Listenname ein
eigenes, geschlossenes Vokabular.** Vorher zeigte jede Liste dieselbe zusammen-
gewuerfelte Verteilung.
"""
import pathlib
import re
import xml.etree.ElementTree as ET

import pytest

WURZEL = pathlib.Path(__file__).resolve().parents[1]
GOLD = (WURZEL / "govisor" / "gold.py").read_text(encoding="utf-8")

#: Gemessen am 2026-10-05 ueber einen neu gebauten Monat (14.614 Notices). Jede Liste
#: hat ihr eigenes Vokabular — genau das war aus `attributes` nicht zu sehen.
VOKABULAR = {
    "einvoicing": {"required", "allowed", "not-allowed"},
    "reserved-execution": {"yes", "no", "not-known"},
    "nda": {"true", "false"},
    "esignature-submission": {"true", "false"},
    "fsr": {"true", "false"},
    "ecatalog-submission": {"required", "allowed", "not-allowed"},
    "conditions": {"performance"},
}

XML = """<?xml version="1.0" encoding="UTF-8"?>
<ContractNotice xmlns="urn:oasis:names:specification:ubl:schema:xsd:ContractNotice-2"
  xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
  xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
  <cbc:ID>TEST-1</cbc:ID>
  <cac:ProcurementProjectLot>
    <cbc:ID>LOT-0001</cbc:ID>
    <cac:TenderingTerms>
      <cac:ContractExecutionRequirement>
        <cbc:ExecutionRequirementCode listName="einvoicing">required</cbc:ExecutionRequirementCode>
      </cac:ContractExecutionRequirement>
      <cac:ContractExecutionRequirement>
        <cbc:ExecutionRequirementCode listName="reserved-execution">yes</cbc:ExecutionRequirementCode>
      </cac:ContractExecutionRequirement>
      <cac:ContractExecutionRequirement>
        <cbc:ExecutionRequirementCode listName="nda">false</cbc:ExecutionRequirementCode>
      </cac:ContractExecutionRequirement>
      <cac:ContractExecutionRequirement>
        <cbc:ExecutionRequirementCode>ohne-listName</cbc:ExecutionRequirementCode>
      </cac:ContractExecutionRequirement>
    </cac:TenderingTerms>
  </cac:ProcurementProjectLot>
</ContractNotice>
"""


def _bedingungen():
    from govisor import schema
    n = schema.parse(XML.encode("utf-8"), "TEST-1")
    return [(r.type_code, r.text, r.lot_id) for r in n.requirements
            if r.kind == "execution"]


def test_wert_und_merkmal_bleiben_gepaart():
    """Der Kern. Alphabetisch sortiert waeren die Werte false/required/yes und die
    Listen einvoicing/nda/reserved-execution — die naive Paarung ergaebe
    `einvoicing=false`. Das darf nicht herauskommen.
    """
    ist = dict((a, b) for a, b, _ in _bedingungen())
    assert ist.get("einvoicing") == "required", (
        f"einvoicing ist {ist.get('einvoicing')!r} statt 'required' — Wert und "
        f"Merkmal sind vertauscht. Genau dieser Fehler macht die flache Tabelle "
        f"unbrauchbar.")
    assert ist.get("reserved-execution") == "yes"
    assert ist.get("nda") == "false"


def test_ohne_listName_wird_verworfen():
    """Ein Code ohne Merkmal ist bedeutungslos — `required`, aber was denn?

    Ihn mitzunehmen hiesse, im Produkt eine Bedingung ohne Gegenstand zu zeigen.
    """
    assert all(a for a, _, _ in _bedingungen()), "ein Eintrag ohne listName kam durch"
    assert "ohne-listName" not in {b for _, b, _ in _bedingungen()}


def test_das_los_bleibt_erhalten():
    """eForms fuehrt die Bedingungen je LOS. Ohne `lot_id` waere eine Bedingung des
    einen Loses spaeter nicht von der eines anderen zu unterscheiden.
    """
    lose = {c for _, _, c in _bedingungen()}
    assert lose == {"LOT-0001"}, f"Los-Zuordnung verloren: {lose}"


# ---- Verdrahtung in Gold -----------------------------------------------------

def test_freitext_liste_schliesst_die_codes_aus():
    """`build_lead_requirement` erwartet PROSA.

    Die Ausfuehrungsbedingungen tragen im `text` einen Code (`required`,
    `not-allowed`). Ohne Ausschluss stuenden sie dort als angebliche
    Anforderungstexte — und `no`/`false` waeren am Ja/Nein-Filter stumm
    verschwunden, also eine teils falsche, teils unvollstaendige Liste.
    """
    block = GOLD.split("def build_lead_requirement", 1)[1][:2600]
    assert "r.kind <> 'execution'" in block, (
        "build_lead_requirement filtert `kind='execution'` nicht heraus")


def test_spalte_in_beiden_exportpfaden():
    code = re.sub(r"(?m)^\s*#.*$", "", GOLD)
    assert code.count("exe.execution_terms") >= 2, (
        "exe.execution_terms steht nicht in beiden Auswahllisten "
        "(build_lead_export und build_at_gold)")
    assert code.count("_execution_terms_sql(cfg, country)") >= 2, (
        "das CTE wird nicht in beiden Exportpfaden gejoint")


def test_leere_rueckfalltabelle_fuer_laender_ohne_requirements():
    block = GOLD.split("def _execution_terms_sql", 1)[1].split("GROUP BY notice_id", 1)[0]
    assert "WHERE false" in block, (
        "Ein Land ohne `requirements` wuerde den Gold-Bau mit einem IO-Fehler "
        "abbrechen statt NULL zu liefern.")


# ---- Vokabular (nur mit neu gebautem Silber) ---------------------------------

def _req_glob():
    p = WURZEL / "data" / "silver" / "DE" / "requirements"
    return (p / "**" / "*.parquet").as_posix() if p.is_dir() else None


@pytest.mark.skipif(not _req_glob(), reason="requirements nicht gebaut")
def test_jede_liste_traegt_ihr_eigenes_vokabular():
    """DER Beleg, dass die Parser-Aenderung wirkt.

    Vorher zeigte jede Liste dieselbe zusammengewuerfelte Verteilung
    (`no`/`required`/`performance`/`not-allowed`), weil die Paarung verloren war.
    Jetzt muss jede Liste in ihrem eigenen Wertebereich bleiben.
    """
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("SET memory_limit='2GB'")
    try:
        r = con.execute(
            f"SELECT type_code, text, count(*) FROM "
            f"read_parquet('{_req_glob()}', hive_partitioning=1) "
            f"WHERE kind='execution' GROUP BY 1,2").fetchall()
    except Exception as e:                                           # noqa: BLE001
        pytest.skip(f"requirements nicht lesbar: {type(e).__name__}")
    if not r:
        pytest.skip("noch keine Ausfuehrungsbedingungen in Silber")
    verstoss = []
    for liste, wert, n in r:
        erlaubt = VOKABULAR.get(liste)
        if erlaubt and wert not in erlaubt:
            verstoss.append(f"{liste}={wert} ({n}x)")
    assert not verstoss, (
        f"Werte ausserhalb des gemessenen Vokabulars: {verstoss[:6]}. Entweder hat "
        f"die Quelle ein neues Vokabular — dann gehoert es hier eingetragen — oder "
        f"die Paarung ist wieder kaputt.")
