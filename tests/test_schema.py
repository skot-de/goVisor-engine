"""Parser tests, one per schema generation plus the traps found in real data."""

from govisor import normalize, schema

LEGACY_2014 = b"""<?xml version="1.0" encoding="UTF-8"?>
<TED_EXPORT VERSION="R2.0.9">
  <CODED_DATA_SECTION>
    <NOTICE_DATA>
      <ISO_COUNTRY VALUE="DE"/>
      <ORIGINAL_CPV CODE="72000000"/>
    </NOTICE_DATA>
  </CODED_DATA_SECTION>
  <FORM_SECTION>
    <F03_2014 LG="DE" CATEGORY="ORIGINAL">
      <OBJECT_CONTRACT>
        <TITLE><P>Rahmenvertrag IT</P></TITLE>
        <CPV_MAIN><CPV_CODE CODE="72000000"/></CPV_MAIN>
        <NC_CONTRACT_NATURE CODE="4">Services</NC_CONTRACT_NATURE>
        <SHORT_DESCR><P>Betrieb und Wartung fuer 48 Monate.</P></SHORT_DESCR>
        <OBJECT_DESCR>
          <LOT_NO><P>1</P></LOT_NO>
          <TITLE><P>Los 1 Betrieb</P></TITLE>
          <SHORT_DESCR><P>Betrieb der Rechenzentren an drei Standorten.</P></SHORT_DESCR>
        </OBJECT_DESCR>
        <OBJECT_DESCR>
          <LOT_NO><P>2</P></LOT_NO>
          <TITLE><P>Los 2 Wartung</P></TITLE>
          <SHORT_DESCR><P>Wartung der Netzwerkinfrastruktur.</P></SHORT_DESCR>
        </OBJECT_DESCR>
      </OBJECT_CONTRACT>
    </F03_2014>
  </FORM_SECTION>
</TED_EXPORT>"""

# ~1% of the archive ships translations alongside the original, up to 24 of
# them. Taking the first form section would yield the wrong language.
LEGACY_TRANSLATED = """<?xml version="1.0" encoding="UTF-8"?>
<TED_EXPORT VERSION="R2.0.9">
  <CODED_DATA_SECTION>
    <NOTICE_DATA><ISO_COUNTRY VALUE="DE"/></NOTICE_DATA>
  </CODED_DATA_SECTION>
  <FORM_SECTION>
    <F03_2014 LG="BG" CATEGORY="TRANSLATION">
      <OBJECT_CONTRACT>
        <TITLE><P>ИТ услуги</P></TITLE>
        <SHORT_DESCR><P>Преведен текст.</P></SHORT_DESCR>
      </OBJECT_CONTRACT>
    </F03_2014>
    <F03_2014 LG="DE" CATEGORY="ORIGINAL">
      <OBJECT_CONTRACT>
        <TITLE><P>IT-Dienstleistungen</P></TITLE>
        <SHORT_DESCR><P>Originaltext.</P></SHORT_DESCR>
      </OBJECT_CONTRACT>
    </F03_2014>
  </FORM_SECTION>
</TED_EXPORT>""".encode("utf-8")

# Pre-2014 forms name the same field differently.
LEGACY_OLD_FORM = b"""<?xml version="1.0" encoding="UTF-8"?>
<TED_EXPORT VERSION="R2.0.8">
  <CODED_DATA_SECTION>
    <NOTICE_DATA><ISO_COUNTRY VALUE="DE"/></NOTICE_DATA>
  </CODED_DATA_SECTION>
  <FORM_SECTION>
    <CONTRACT_AWARD LG="DE" CATEGORY="ORIGINAL">
      <FD_CONTRACT_AWARD>
        <OBJECT_CONTRACT_INFORMATION_CONTRACT_AWARD_NOTICE>
          <DESCRIPTION_AWARD_NOTICE_INFORMATION>
            <TITLE_CONTRACT><P>Unterstuetzung IT</P></TITLE_CONTRACT>
            <SHORT_CONTRACT_DESCRIPTION><P>Leistungen fuer die IT-Bereiche.</P></SHORT_CONTRACT_DESCRIPTION>
          </DESCRIPTION_AWARD_NOTICE_INFORMATION>
        </OBJECT_CONTRACT_INFORMATION_CONTRACT_AWARD_NOTICE>
      </FD_CONTRACT_AWARD>
    </CONTRACT_AWARD>
  </FORM_SECTION>
</TED_EXPORT>"""

# A CAN carries two NO_DOC_OJS: its own under NOTICE_DATA, and its CN's under
# NOTICE_DATA/REF_NOTICE. Mixing them up would link every award to itself.
LEGACY_WITH_REF = b"""<?xml version="1.0" encoding="UTF-8"?>
<TED_EXPORT VERSION="R2.0.9">
  <CODED_DATA_SECTION>
    <REF_OJS>
      <COLL_OJ>S</COLL_OJ><NO_OJ>105</NO_OJ><DATE_PUB>20230602</DATE_PUB>
    </REF_OJS>
    <NOTICE_DATA>
      <NO_DOC_OJS>2023/S 105-327209</NO_DOC_OJS>
      <ISO_COUNTRY VALUE="DE"/>
      <URI_LIST>
        <URI_DOC LG="DE">https://ted.europa.eu/udl?uri=TED:NOTICE:327209-2023:TEXT:DE:HTML</URI_DOC>
      </URI_LIST>
      <REF_NOTICE><NO_DOC_OJS>2023/S 060-175907</NO_DOC_OJS></REF_NOTICE>
    </NOTICE_DATA>
  </CODED_DATA_SECTION>
  <FORM_SECTION>
    <F03_2014 LG="DE" CATEGORY="ORIGINAL">
      <OBJECT_CONTRACT><SHORT_DESCR><P>Vergabe.</P></SHORT_DESCR></OBJECT_CONTRACT>
    </F03_2014>
  </FORM_SECTION>
</TED_EXPORT>"""

# CONTRACT_AWARD_UTILITIES uses SHORT_DESCRIPTION — a third spelling again.
LEGACY_UTILITIES = b"""<?xml version="1.0" encoding="UTF-8"?>
<TED_EXPORT VERSION="R2.0.8">
  <CODED_DATA_SECTION>
    <NOTICE_DATA><ISO_COUNTRY VALUE="DE"/></NOTICE_DATA>
  </CODED_DATA_SECTION>
  <FORM_SECTION>
    <CONTRACT_AWARD_UTILITIES LG="DE" CATEGORY="ORIGINAL">
      <FD_CONTRACT_AWARD_UTILITIES>
        <SHORT_DESCRIPTION><P>Lieferung von Transformatoren.</P></SHORT_DESCRIPTION>
      </FD_CONTRACT_AWARD_UTILITIES>
    </CONTRACT_AWARD_UTILITIES>
  </FORM_SECTION>
</TED_EXPORT>"""

# The trap: CONTRACT carries SHORT_CONTRACT_DESCRIPTION *and*
# TOTAL_QUANTITY_OR_SCOPE (81% of the time). Priority must pick the former.
LEGACY_WITH_QUANTITY = b"""<?xml version="1.0" encoding="UTF-8"?>
<TED_EXPORT VERSION="R2.0.8">
  <CODED_DATA_SECTION>
    <NOTICE_DATA><ISO_COUNTRY VALUE="DE"/></NOTICE_DATA>
  </CODED_DATA_SECTION>
  <FORM_SECTION>
    <CONTRACT LG="DE" CATEGORY="ORIGINAL">
      <FD_CONTRACT>
        <TOTAL_QUANTITY_OR_SCOPE><P>Menge: ca. 4000 Stueck.</P></TOTAL_QUANTITY_OR_SCOPE>
        <SHORT_CONTRACT_DESCRIPTION><P>Beschaffung von Buerostuehlen.</P></SHORT_CONTRACT_DESCRIPTION>
      </FD_CONTRACT>
    </CONTRACT>
  </FORM_SECTION>
</TED_EXPORT>"""

# PRIOR_INFORMATION has no description field at all — the scope text is it.
LEGACY_PRIOR_INFO = b"""<?xml version="1.0" encoding="UTF-8"?>
<TED_EXPORT VERSION="R2.0.8">
  <CODED_DATA_SECTION>
    <NOTICE_DATA><ISO_COUNTRY VALUE="DE"/></NOTICE_DATA>
  </CODED_DATA_SECTION>
  <FORM_SECTION>
    <PRIOR_INFORMATION LG="DE" CATEGORY="ORIGINAL">
      <FD_PRIOR_INFORMATION>
        <TOTAL_QUANTITY_OR_SCOPE><P>Rahmenvertrag ueber Bueromaterial.</P></TOTAL_QUANTITY_OR_SCOPE>
      </FD_PRIOR_INFORMATION>
    </PRIOR_INFORMATION>
  </FORM_SECTION>
</TED_EXPORT>"""

EFORMS = b"""<?xml version="1.0" encoding="UTF-8"?>
<ContractAwardNotice
    xmlns="urn:oasis:names:specification:ubl:schema:xsd:ContractAwardNotice-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns:efac="http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1"
    xmlns:efext="http://data.europa.eu/p27/eforms-ubl-extensions/1">
  <cbc:NoticeLanguageCode>DEU</cbc:NoticeLanguageCode>
  <!-- The buyer appears here ONLY as a reference. -->
  <cac:ContractingParty>
    <cac:Party>
      <cac:PartyIdentification>
        <cbc:ID schemeName="organization">ORG-0001</cbc:ID>
      </cac:PartyIdentification>
    </cac:Party>
  </cac:ContractingParty>
  <efext:UBLExtensions><efac:Organizations>
    <efac:Organization>
      <efac:Company>
        <cac:PartyIdentification>
          <cbc:ID schemeName="organization">ORG-0001</cbc:ID>
        </cac:PartyIdentification>
        <cac:PartyName><cbc:Name>Beschaffungsamt des BMI</cbc:Name></cac:PartyName>
        <cac:PostalAddress>
          <cbc:CityName>Bonn</cbc:CityName>
          <cac:Country>
            <cbc:IdentificationCode listName="country">DEU</cbc:IdentificationCode>
          </cac:Country>
        </cac:PostalAddress>
      </efac:Company>
    </efac:Organization>
    <efac:Organization>
      <efac:Company>
        <cac:PartyIdentification>
          <cbc:ID schemeName="organization">ORG-0002</cbc:ID>
        </cac:PartyIdentification>
        <cac:PostalAddress>
          <cac:Country>
            <cbc:IdentificationCode listName="country">FRA</cbc:IdentificationCode>
          </cac:Country>
        </cac:PostalAddress>
      </efac:Company>
    </efac:Organization>
  </efac:Organizations></efext:UBLExtensions>
  <cac:ProcurementProject>
    <cbc:Name>Beschaffung Akustikkabinen</cbc:Name>
    <cbc:Description>Lieferung von Kabinen fuer die Gebaeude.</cbc:Description>
    <cbc:ProcurementTypeCode listName="contract-nature">supplies</cbc:ProcurementTypeCode>
    <cac:ProcurementAdditionalType>
      <cbc:ProcurementTypeCode listName="strategic-procurement">env-imp</cbc:ProcurementTypeCode>
    </cac:ProcurementAdditionalType>
    <cac:MainCommodityClassification>
      <cbc:ItemClassificationCode>48000000</cbc:ItemClassificationCode>
    </cac:MainCommodityClassification>
    <cac:RealizedLocation>
      <cac:Address><cac:Country><cbc:IdentificationCode>FRA</cbc:IdentificationCode></cac:Country></cac:Address>
    </cac:RealizedLocation>
  </cac:ProcurementProject>
  <cac:ProcurementProjectLot>
    <cbc:ID schemeName="Lot">LOT-0001</cbc:ID>
    <cac:ProcurementProject>
      <cbc:Name>Los 1 Nord</cbc:Name>
      <cbc:Description>Kabinen fuer den Standort Nord.</cbc:Description>
    </cac:ProcurementProject>
  </cac:ProcurementProjectLot>
  <cac:TenderingTerms>
    <cac:AppealTerms>
      <cbc:Description>Sehr langer Standardtext zu Rechtsbehelfen, der laenger ist als die Projektbeschreibung und daher eine Laengen-Heuristik in die Irre fuehren wuerde.</cbc:Description>
    </cac:AppealTerms>
  </cac:TenderingTerms>
</ContractAwardNotice>"""


def test_legacy_contract_nature_from_code():
    """Standard-Forms: NC_CONTRACT_NATURE@CODE 4 → services (BT-23)."""
    notice = schema.parse(LEGACY_2014, "1-2023")
    assert notice.contract_nature == "services"


def test_eforms_contract_nature_ignores_strategic_code():
    """eForms: nur das contract-nature-ProcurementTypeCode zählt, nicht der
    BT-774-Strategiecode (env-imp) unter ProcurementAdditionalType."""
    notice = schema.parse(EFORMS, "00100001_2024")
    assert notice.contract_nature == "supplies"


def test_legacy_2014_uses_short_descr():
    notice = schema.parse(LEGACY_2014, "1-2023")
    assert notice.schema == "legacy"
    assert notice.form_type == "F03_2014"
    assert notice.country == "DE"
    assert notice.description_field == "SHORT_DESCR"
    assert "48 Monate" in notice.description
    assert notice.cpv_main == "72000000"


def test_notice_level_description_excludes_lot_text():
    # OBJECT_CONTRACT nests one OBJECT_DESCR per lot, each with its own
    # SHORT_DESCR. II.1.4 must not swallow II.2.4.
    notice = schema.parse(LEGACY_2014, "1-2023")
    assert notice.description == "Betrieb und Wartung fuer 48 Monate."


def test_lot_descriptions_are_kept():
    # Taking only the first SHORT_DESCR dropped 67% of all freetext.
    notice = schema.parse(LEGACY_2014, "1-2023")
    assert [lot.lot_id for lot in notice.lots] == ["1", "2"]
    assert [lot.title for lot in notice.lots] == ["Los 1 Betrieb", "Los 2 Wartung"]
    assert notice.lots[1].description == "Wartung der Netzwerkinfrastruktur."
    assert len(notice.descriptions) == 3
    assert notice.text_length == sum(len(t) for t in notice.descriptions)


def test_translated_notice_yields_original_language():
    notice = schema.parse(LEGACY_TRANSLATED, "2-2023")
    # Seit der Sprachcode-Vereinheitlichung ISO-639-1 klein (vorher "DE"/"DEU"
    # nebeneinander fuer dieselbe Sprache).
    assert notice.language == "de"
    assert notice.description == "Originaltext."
    assert notice.title == "IT-Dienstleistungen"


def test_pre_2014_form_uses_short_contract_description():
    notice = schema.parse(LEGACY_OLD_FORM, "3-2016")
    assert notice.description_field == "SHORT_CONTRACT_DESCRIPTION"
    assert "IT-Bereiche" in notice.description
    assert notice.title == "Unterstuetzung IT"


def test_own_oj_number_is_not_the_referenced_one():
    notice = schema.parse(LEGACY_WITH_REF, "327209_2023")
    assert notice.oj_ref == "2023/S 105-327209"
    assert notice.publication_number == "327209-2023"
    assert notice.ref_oj == "2023/S 060-175907"
    assert notice.ref_publication_number == "175907-2023"


def test_links_point_at_the_canonical_page_not_the_legacy_redirect():
    notice = schema.parse(LEGACY_WITH_REF, "327209_2023")
    assert notice.ted_url == "https://ted.europa.eu/de/notice/-/detail/327209-2023"
    assert notice.ref_ted_url == "https://ted.europa.eu/de/notice/-/detail/175907-2023"
    assert notice.publication_date == "2023-06-02"


def test_publication_number_falls_back_to_the_filename():
    # eForms and odd legacy forms carry no NO_DOC_OJS; the package filename does.
    notice = schema.parse(EFORMS, "00100001_2024")
    assert notice.publication_number == "100001-2024"
    assert notice.ted_url.endswith("/detail/100001-2024")


def test_utilities_award_uses_short_description():
    notice = schema.parse(LEGACY_UTILITIES, "5-2016")
    assert notice.form_type == "CONTRACT_AWARD_UTILITIES"
    assert notice.description_field == "SHORT_DESCRIPTION"
    assert notice.description == "Lieferung von Transformatoren."


def test_quantity_field_never_beats_the_real_description():
    # TOTAL_QUANTITY_OR_SCOPE sits next to the description on 81% of CONTRACT
    # forms. Priority order — not document order — must decide.
    notice = schema.parse(LEGACY_WITH_QUANTITY, "6-2016")
    assert notice.description_field == "SHORT_CONTRACT_DESCRIPTION"
    assert notice.description == "Beschaffung von Buerostuehlen."


def test_prior_information_falls_back_to_quantity_field():
    notice = schema.parse(LEGACY_PRIOR_INFO, "7-2016")
    assert notice.description_field == "TOTAL_QUANTITY_OR_SCOPE"
    assert notice.description == "Rahmenvertrag ueber Bueromaterial."


def test_eforms_prefers_project_description_over_longer_boilerplate():
    notice = schema.parse(EFORMS, "4-2024")
    assert notice.schema == "eforms"
    assert notice.description == "Lieferung von Kabinen fuer die Gebaeude."
    assert notice.title == "Beschaffung Akustikkabinen"


def test_eforms_lots_are_kept_and_not_merged_into_notice_level():
    notice = schema.parse(EFORMS, "4-2024")
    assert [lot.lot_id for lot in notice.lots] == ["LOT-0001"]
    assert notice.lots[0].description == "Kabinen fuer den Standort Nord."
    assert notice.description == "Lieferung von Kabinen fuer die Gebaeude."


def test_eforms_country_resolves_the_organization_reference():
    # ContractingParty holds only 'ORG-0001'. The country lives in the separate
    # Organizations block. Looking inside ContractingParty finds nothing — and
    # dropped every DE notice from 2024 on.
    notice = schema.parse(EFORMS, "4-2024")
    assert notice.country == "DE"


def test_eforms_picks_the_buyers_org_not_just_any():
    # ORG-0002 is French. Resolving the wrong reference would file this notice
    # under FR, or drop it from a DE run.
    orgs = schema._eforms_org_countries(schema.ET.fromstring(EFORMS))
    assert orgs == {"ORG-0001": "DE", "ORG-0002": "FR"}
    assert schema._eforms_buyer_org_id(schema.ET.fromstring(EFORMS)) == "ORG-0001"


# Joint procurement: led from Brussels, buying for an agency in Frankfurt.
# TED counts this towards DE. Reading only the first ContractingParty files it
# under BE and hides it from a DE run.
EFORMS_JOINT = """<?xml version="1.0" encoding="UTF-8"?>
<ContractAwardNotice
    xmlns="urn:oasis:names:specification:ubl:schema:xsd:ContractAwardNotice-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns:efac="http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1">
  <cac:ContractingParty><cac:Party><cac:PartyIdentification>
    <cbc:ID schemeName="organization">ORG-0001</cbc:ID>
  </cac:PartyIdentification></cac:Party></cac:ContractingParty>
  <cac:ContractingParty><cac:Party><cac:PartyIdentification>
    <cbc:ID schemeName="organization">ORG-0002</cbc:ID>
  </cac:PartyIdentification></cac:Party></cac:ContractingParty>
  <efac:Organizations>
    <efac:Organization><efac:Company>
      <cac:PartyIdentification><cbc:ID schemeName="organization">ORG-0001</cbc:ID></cac:PartyIdentification>
      <cac:PostalAddress><cac:Country>
        <cbc:IdentificationCode listName="country">BEL</cbc:IdentificationCode>
      </cac:Country></cac:PostalAddress>
    </efac:Company></efac:Organization>
    <efac:Organization><efac:Company>
      <cac:PartyIdentification><cbc:ID schemeName="organization">ORG-0002</cbc:ID></cac:PartyIdentification>
      <cac:PostalAddress><cac:Country>
        <cbc:IdentificationCode listName="eforms-country">DEU</cbc:IdentificationCode>
      </cac:Country></cac:PostalAddress>
    </efac:Company></efac:Organization>
    <efac:Organization><efac:Company>
      <cac:PartyIdentification><cbc:ID schemeName="organization">ORG-0009</cbc:ID></cac:PartyIdentification>
      <cac:PostalAddress><cac:Country>
        <cbc:IdentificationCode listName="country">FRA</cbc:IdentificationCode>
      </cac:Country></cac:PostalAddress>
    </efac:Company></efac:Organization>
  </efac:Organizations>
</ContractAwardNotice>""".encode("utf-8")

# A company registering itself. No ContractingParty, no Organizations block —
# and the address hides under PartyLegalEntity, not PostalAddress.
EFORMS_BRIN = """<?xml version="1.0" encoding="UTF-8"?>
<BusinessRegistrationInformationNotice
    xmlns="urn:oasis:names:specification:ubl:schema:xsd:BusinessRegistrationInformationNotice-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:NoticeTypeCode listName="bri">brin-ecs</cbc:NoticeTypeCode>
  <cac:BusinessParty>
    <cac:PartyLegalEntity>
      <cbc:RegistrationName>SmartFactoryEU EWIV</cbc:RegistrationName>
      <cbc:CompanyID schemeName="EU">HRA 30700, Amtsgericht Kaiserslautern</cbc:CompanyID>
      <cac:CorporateRegistrationScheme><cac:JurisdictionRegionAddress>
        <cbc:CityName>Kaiserlautern</cbc:CityName>
        <cac:Country>
          <cbc:IdentificationCode listName="country">DEU</cbc:IdentificationCode>
        </cac:Country>
      </cac:JurisdictionRegionAddress></cac:CorporateRegistrationScheme>
    </cac:PartyLegalEntity>
  </cac:BusinessParty>
</BusinessRegistrationInformationNotice>""".encode("utf-8")


# A German NGO procuring in Kyiv. The buyer's country is Ukraine — which this
# registry does not list — so the buyer resolves to nothing. A German org
# elsewhere in the document must not make the notice German.
EFORMS_FOREIGN_BUYER = """<?xml version="1.0" encoding="UTF-8"?>
<ContractAwardNotice
    xmlns="urn:oasis:names:specification:ubl:schema:xsd:ContractAwardNotice-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns:efac="http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1">
  <cac:ContractingParty><cac:Party><cac:PartyIdentification>
    <cbc:ID schemeName="organization">ORG-0001</cbc:ID>
  </cac:PartyIdentification></cac:Party></cac:ContractingParty>
  <efac:Organizations>
    <efac:Organization><efac:Company>
      <cac:PartyIdentification><cbc:ID schemeName="organization">ORG-0001</cbc:ID></cac:PartyIdentification>
      <cac:PartyName><cbc:Name>Welthungerhilfe Ukraine</cbc:Name></cac:PartyName>
      <cac:PostalAddress><cbc:CityName>Kyiv</cbc:CityName><cac:Country>
        <cbc:IdentificationCode listName="country">UKR</cbc:IdentificationCode>
      </cac:Country></cac:PostalAddress>
    </efac:Company></efac:Organization>
    <efac:Organization><efac:Company>
      <cac:PartyIdentification><cbc:ID schemeName="organization">ORG-0002</cbc:ID></cac:PartyIdentification>
      <cac:PartyName><cbc:Name>Ein Lieferant</cbc:Name></cac:PartyName>
      <cac:PostalAddress><cac:Country>
        <cbc:IdentificationCode listName="country">DEU</cbc:IdentificationCode>
      </cac:Country></cac:PostalAddress>
    </efac:Company></efac:Organization>
  </efac:Organizations>
</ContractAwardNotice>""".encode("utf-8")


def test_unresolvable_buyer_country_stays_unknown():
    # No "only one country appears, so use it" guessing: the sole resolvable
    # country here belongs to a supplier, not to the buyer in Kyiv.
    notice = schema.parse(EFORMS_FOREIGN_BUYER, "29650_2024")
    assert notice.country is None
    assert notice.buyer_countries == []


def test_joint_procurement_counts_for_every_buyer_country():
    notice = schema.parse(EFORMS_JOINT, "421563_2026")
    assert notice.country == "BE"                    # lead
    assert notice.buyer_countries == ["BE", "DE"]    # ORG-0009 is a supplier, not a buyer
    assert "DE" in notice.buyer_countries


def test_eforms_country_accepts_both_list_names():
    # TED tags the code as listName="country" AND listName="eforms-country".
    # Accepting only the first dropped plainly German buyers.
    orgs = schema._eforms_org_countries(schema.ET.fromstring(EFORMS_JOINT))
    assert orgs["ORG-0002"] == "DE"


def test_business_registration_notice_resolves_its_party():
    # No ContractingParty at all, and the country sits under PartyLegalEntity.
    notice = schema.parse(EFORMS_BRIN, "383706_2026")
    assert notice.country == "DE"
    assert notice.buyer_countries == ["DE"]
    assert notice.form_type == "BusinessRegistrationInformationNotice"


def test_probe_is_over_inclusive_by_design():
    # The probe sees DEU and FRA; only parsing can tell buyer from the rest.
    assert schema.probe_countries(EFORMS) == {"DE", "FR"}


def test_review_queue_keeps_the_evidence(tmp_path):
    from govisor import review
    q = review.ReviewQueue()
    q.add(review.ReviewItem(
        notice_id="29650_2024",
        reason=schema.Flag.NO_BUYER_COUNTRY,
        kept=False,
        probe_countries=["DE"],
        raw_country_codes=["UKR", "DEU"],
        unknown_country_codes=["UKR"],
    ), EFORMS_FOREIGN_BUYER)
    q.write(tmp_path / "q.jsonl.gz", tmp_path / "q.tar.gz")

    items = review.load(tmp_path / "q.jsonl.gz")
    assert len(items) == 1
    # 'UKR' is the whole explanation: the buyer sits in a country this registry
    # does not list. A reviewer must see that, not just "unresolved".
    assert "UKR" in items[0].raw_country_codes

    import tarfile
    with tarfile.open(tmp_path / "q.tar.gz") as tf:
        assert tf.getnames() == ["29650_2024.xml"]
        assert b"Welthungerhilfe" in tf.extractfile("29650_2024.xml").read()


def test_flags_mark_everything_that_needed_an_assumption():
    from govisor.schema import Flag
    # The Kyiv case: buyer unresolvable, and UKR is why.
    notice = schema.parse(EFORMS_FOREIGN_BUYER, "29650_2024")
    assert Flag.NO_BUYER_COUNTRY in notice.flags
    assert Flag.UNKNOWN_COUNTRY_CODE in notice.flags
    assert notice.unknown_country_codes == ["UKR"]


def test_clean_notice_carries_no_flags():
    # A flag must mean something. If the ordinary case raised one, nobody would
    # read the queue.
    notice = schema.parse(LEGACY_2014, "1-2023")
    assert notice.flags == []


def test_unknown_form_type_is_flagged_not_swallowed():
    from govisor.schema import Flag
    odd = LEGACY_2014.replace(b"F03_2014", b"F99_2099")
    notice = schema.parse(odd, "1-2023")
    assert Flag.UNKNOWN_FORM in notice.flags


def test_missing_description_is_flagged_but_kept():
    from govisor.schema import Flag
    bare = LEGACY_2014.replace(b"<SHORT_DESCR><P>Betrieb und Wartung fuer 48 Monate.</P></SHORT_DESCR>", b"")
    bare = bare.replace(b"<SHORT_DESCR><P>Betrieb der Rechenzentren an drei Standorten.</P></SHORT_DESCR>", b"")
    bare = bare.replace(b"<SHORT_DESCR><P>Wartung der Netzwerkinfrastruktur.</P></SHORT_DESCR>", b"")
    notice = schema.parse(bare, "1-2023")
    assert Flag.NO_DESCRIPTION in notice.flags
    assert notice.country == "DE"      # still perfectly usable, just worth a look


def test_category6_renewal_and_options_on_lot():
    xml = LEGACY_2014.replace(
        b"<SHORT_DESCR><P>Betrieb der Rechenzentren an drei Standorten.</P></SHORT_DESCR>",
        b"<SHORT_DESCR><P>Betrieb der Rechenzentren an drei Standorten.</P></SHORT_DESCR>"
        b"<DURATION TYPE='MONTH'>24</DURATION>"
        b"<OPTIONS><P>ja</P></OPTIONS><OPTIONS_DESCR><P>Zwei Verlaengerungen moeglich.</P></OPTIONS_DESCR>"
        b"<RENEWAL><P>ja</P></RENEWAL><RENEWAL_DESCR><P>Verlaengerung um je 12 Monate.</P></RENEWAL_DESCR>"
        b"<NUMBER_POSSIBLE_RENEWALS>2</NUMBER_POSSIBLE_RENEWALS>")
    notice = schema.parse(xml, "1-2023")
    lot = notice.lots[0]
    assert lot.duration_months == 24
    assert lot.has_options is True
    assert lot.has_renewal is True
    assert "12 Monate" in lot.renewal_description
    assert lot.max_renewals == 2


def test_category5_competition_from_award():
    xml = LEGACY_2014.replace(
        b"</OBJECT_CONTRACT>",
        b"</OBJECT_CONTRACT>"
        b"<AWARD_CONTRACT><LOT_NO><P>1</P></LOT_NO><AWARDED_CONTRACT><TENDERS>"
        b"<NB_TENDERS_RECEIVED>7</NB_TENDERS_RECEIVED>"
        b"<NB_TENDERS_RECEIVED_SME>3</NB_TENDERS_RECEIVED_SME>"
        b"<NB_TENDERS_RECEIVED_EMEANS>7</NB_TENDERS_RECEIVED_EMEANS>"
        b"</TENDERS></AWARDED_CONTRACT></AWARD_CONTRACT>")
    notice = schema.parse(xml, "1-2023")
    assert len(notice.awards) == 1
    a = notice.awards[0]
    assert a.lot_id == "1"
    assert a.num_tenders == 7
    assert a.num_tenders_sme == 3
    assert a.num_tenders_electronic == 7


def test_category9_requirements_captured_with_text():
    xml = LEGACY_2014.replace(
        b"</OBJECT_CONTRACT>",
        b"</OBJECT_CONTRACT>"
        b"<LEFTI>"
        b"<TECHNICAL_PROFESSIONAL_INFO><P>Zertifikat DIN EN ISO 9001:2015 vorzulegen.</P></TECHNICAL_PROFESSIONAL_INFO>"
        b"<ECONOMIC_FINANCIAL_INFO><P>Mindestumsatz 350 TEUR pro Jahr.</P></ECONOMIC_FINANCIAL_INFO>"
        b"</LEFTI>")
    notice = schema.parse(xml, "1-2023")
    kinds = {r.kind: r.text for r in notice.requirements}
    assert "ISO 9001" in kinds["technical"]
    assert "350 TEUR" in kinds["economic"]


def test_flatten_leaves_captures_every_value():
    from govisor import flatten
    pairs = list(flatten.leaves(LEGACY_2014))
    # Ein Wert aus jeder Ebene muss auffindbar sein — über seinen Pfad.
    # (Geprüft wird über `pairs`; das Dict daraus wurde gebaut und nie gelesen. Es wäre
    # ausserdem irreführend gewesen: ein Pfad kann mehrfach vorkommen, ein Dict behält
    # nur den letzten Wert.)
    assert any("SHORT_DESCR" in p and "48 Monate" in v for p, v in pairs)
    assert any(p.endswith("@CODE") and v == "72000000" for p, v in pairs)
    assert any("Los 1 Betrieb" in v for p, v in pairs)
    # Kein Blattwert darf leer sein.
    assert all(v.strip() for _, v in pairs)


def test_flatten_leaves_is_complete_vs_elementtree():
    import xml.etree.ElementTree as ET
    from govisor import flatten
    root = ET.fromstring(LEGACY_2014)
    # Jeder nicht-leere Text im Baum muss in leaves() auftauchen.
    tree_texts = [e.text.strip() for e in root.iter()
                  if len(e) == 0 and e.text and e.text.strip()]
    leaf_values = [v for _, v in flatten.leaves(LEGACY_2014)]
    for t in tree_texts:
        assert t in leaf_values


def test_consortium_is_per_lot_not_per_notice():
    # Zwei Lose, je EIN Gewinner = unabhängige Los-Gewinner, KEIN Konsortium.
    xml = LEGACY_2014.replace(
        b"</OBJECT_CONTRACT>",
        b"</OBJECT_CONTRACT>"
        b"<AWARD_CONTRACT><LOT_NO><P>1</P></LOT_NO><AWARDED_CONTRACT><CONTRACTOR>"
        b"<ADDRESS_CONTRACTOR><OFFICIALNAME><P>Firma A GmbH</P></OFFICIALNAME></ADDRESS_CONTRACTOR>"
        b"</CONTRACTOR></AWARDED_CONTRACT></AWARD_CONTRACT>"
        b"<AWARD_CONTRACT><LOT_NO><P>2</P></LOT_NO><AWARDED_CONTRACT><CONTRACTOR>"
        b"<ADDRESS_CONTRACTOR><OFFICIALNAME><P>Firma B GmbH</P></OFFICIALNAME></ADDRESS_CONTRACTOR>"
        b"</CONTRACTOR></AWARDED_CONTRACT></AWARD_CONTRACT>")
    notice = schema.parse(xml, "1-2023")
    winners = [p for p in notice.parties if p.role == "winner"]
    assert len(winners) == 2
    assert all(w.in_consortium is False for w in winners)


CONSORTIUM_LOT = b"""<?xml version="1.0" encoding="UTF-8"?>
<TED_EXPORT VERSION="R2.0.9">
  <CODED_DATA_SECTION><NOTICE_DATA><ISO_COUNTRY VALUE="DE"/></NOTICE_DATA></CODED_DATA_SECTION>
  <FORM_SECTION>
    <F03_2014 LG="DE" CATEGORY="ORIGINAL">
      <OBJECT_CONTRACT><SHORT_DESCR><P>Bahnbau.</P></SHORT_DESCR></OBJECT_CONTRACT>
      <AWARD_CONTRACT><LOT_NO><P>1</P></LOT_NO><AWARDED_CONTRACT>
        <CONTRACTOR><ADDRESS_CONTRACTOR><OFFICIALNAME><P>Firma A GmbH</P></OFFICIALNAME></ADDRESS_CONTRACTOR></CONTRACTOR>
        <CONTRACTOR><ADDRESS_CONTRACTOR><OFFICIALNAME><P>Firma B GmbH</P></OFFICIALNAME></ADDRESS_CONTRACTOR></CONTRACTOR>
      </AWARDED_CONTRACT></AWARD_CONTRACT>
    </F03_2014>
  </FORM_SECTION>
</TED_EXPORT>"""


def test_consortium_when_two_winners_share_one_lot():
    # Zwei Gewinner im SELBEN AWARD_CONTRACT = echtes Konsortium (real: 303070-2020,
    # Rhomberg + Swietelsky auf einem Los).
    notice = schema.parse(CONSORTIUM_LOT, "1-2023")
    winners = [p for p in notice.parties if p.role == "winner"]
    assert len(winners) == 2
    assert all(w.in_consortium is True for w in winners)


# INTERNAL_OJS (opoce, ~2008): eigenes OJS-DTD, das TED für 2008-05 statt des
# Standardschemas auslieferte. Land als Element-Text, Betrag „100 000,00",
# Datum YYYYMMDD, Land-Präfix „D-" im Titel, Gewinner unter AWARD_OF_CONTRACT.
INTERNAL_OJS_CAN = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE INTERNAL_OJS PUBLIC "-//OPOCE OJS//DTD INTERNAL_OJS XML R2.0.5//EN" "Internal_Ojs.dtd">
<INTERNAL_OJS>
  <BIB_INFO><BIB_DOC_S>
    <TI_DOC><P>D-Schwerin: Personenbefoerderung per Bahn</P><P>2008/S 85-114266</P></TI_DOC>
    <LG_ORIG>DE</LG_ORIG>
    <ORIGINAL_CPV>60111000</ORIGINAL_CPV>
    <ORIGINAL_NUTS>DE80</ORIGINAL_NUTS>
    <DATE_PUB>20080502</DATE_PUB>
    <ISO_COUNTRY>DE</ISO_COUNTRY>
    <NO_DOC_OJS>2008/S 85-114266</NO_DOC_OJS>
  </BIB_DOC_S></BIB_INFO>
  <CONTRACT_AWARD>
    <SENDER><USER><ADDRESS_NOT_STRUCT><ORGANISATION>Land Mecklenburg-Vorpommern</ORGANISATION>
      <TOWN>Schwerin</TOWN><POSTAL_CODE>19053</POSTAL_CODE>
      <E_MAIL>wrt@vmv.de</E_MAIL></ADDRESS_NOT_STRUCT></USER></SENDER>
    <AWARD_OF_CONTRACT ITEM="1">
      <CONTRACT_AWARD_DATE><DAY>15</DAY><MONTH>04</MONTH><YEAR>2008</YEAR></CONTRACT_AWARD_DATE>
      <ECONOMIC_OPERATOR_NAME_ADDRESS><CONTACT_DATA_WITHOUT_RESPONSIBLE_NAME>
        <ORGANISATION>GROSTRA Bau GmbH</ORGANISATION></CONTACT_DATA_WITHOUT_RESPONSIBLE_NAME>
      </ECONOMIC_OPERATOR_NAME_ADDRESS>
      <CONTRACT_VALUE_INFORMATION><COSTS_RANGE_AND_CURRENCY_WITH_VAT_RATE CURRENCY="EUR">
        <VALUE_COST>2 654 755,07</VALUE_COST></COSTS_RANGE_AND_CURRENCY_WITH_VAT_RATE>
      </CONTRACT_VALUE_INFORMATION>
    </AWARD_OF_CONTRACT>
  </CONTRACT_AWARD>
</INTERNAL_OJS>"""


def test_internal_ojs_award_is_fully_parsed():
    # 2008-05 kam nur als INTERNAL_OJS — ohne eigenen Zweig ging der ganze Monat verloren.
    notice = schema.parse(INTERNAL_OJS_CAN, "114266_2008")
    assert notice.country == "DE"
    assert notice.notice_kind == "can"
    assert notice.form_type == "CONTRACT_AWARD"
    assert notice.title == "Personenbefoerderung per Bahn"   # Land-Präfix „D-Schwerin:" entfernt
    assert notice.cpv_main == "60111000"
    assert notice.performance_nuts == "DE80"
    assert notice.publication_date == "2008-05-02"
    assert notice.publication_number == "114266-2008"
    assert notice.award_date == "2008-04-15"
    # Europäischer Betrag korrekt (nicht das 100-Fache).
    assert notice.final_value == 2654755.07
    assert notice.value_currency == "EUR"
    buyers = [p for p in notice.parties if p.role == "buyer"]
    winners = [p for p in notice.parties if p.role == "winner"]
    assert buyers and buyers[0].name == "Land Mecklenburg-Vorpommern"
    assert buyers[0].town == "Schwerin"
    assert winners and winners[0].name == "GROSTRA Bau GmbH"


def test_internal_ojs_country_is_probed_before_parse():
    # Der Länderfilter im Ingest läuft VOR dem Parse über die Byte-Probe. Ohne
    # OJS-Muster (Element-Text statt VALUE-Attribut) fiele der Monat vorher durch.
    assert "DE" in schema.probe_countries(INTERNAL_OJS_CAN)


def test_eforms_winner_fallback_via_signatory_party():
    """eForms-Notice ohne TenderingParty-Gewinner: SignatoryParty des SettledContract
    liefert den Gewinner — Vergabekammer/eSender werden ausgeschlossen."""
    from govisor import schema
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <ContractAwardNotice>
      <UBLExtensions><UBLExtension><ExtensionContent><EformsExtension>
        <Organizations>
          <Organization><Company>
            <PartyIdentification><ID>ORG-0002</ID></PartyIdentification>
            <PartyName><Name>Gewinner Bau GmbH</Name></PartyName>
          </Company></Organization>
          <Organization><Company>
            <PartyIdentification><ID>ORG-0003</ID></PartyIdentification>
            <PartyName><Name>Vergabekammer des Bundes</Name></PartyName>
          </Company></Organization>
        </Organizations>
        <NoticeResult>
          <LotResult><TenderResultCode>selec-w</TenderResultCode></LotResult>
          <SettledContract><SignatoryParty>
            <PartyIdentification><ID>ORG-0002</ID></PartyIdentification>
          </SignatoryParty></SettledContract>
          <SettledContract><SignatoryParty>
            <PartyIdentification><ID>ORG-0003</ID></PartyIdentification>
          </SignatoryParty></SettledContract>
        </NoticeResult>
      </EformsExtension></ExtensionContent></UBLExtension></UBLExtensions>
    </ContractAwardNotice>"""
    n = schema.parse(xml, "test_eforms_1")
    assert "Gewinner Bau GmbH" in n.winner_names
    assert "Vergabekammer des Bundes" not in n.winner_names


# ---- Zuschlagskriterien (BT-539/540/541/734/5421) ------------------------------
def _crit_xml(lots):
    """Minimales eForms-Geruest mit AwardingCriterion je Los."""
    def crit(kind, name, listname, code, num):
        par = ""
        if listname:
            par = (f'<ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent>'
                   f'<efext:EformsExtension><efac:AwardCriterionParameter>'
                   f'<efbc:ParameterCode listName="{listname}">{code}</efbc:ParameterCode>'
                   f'<efbc:ParameterNumeric>{num}</efbc:ParameterNumeric>'
                   f'</efac:AwardCriterionParameter></efext:EformsExtension>'
                   f'</ext:ExtensionContent></ext:UBLExtension></ext:UBLExtensions>')
        return (f'<cac:SubordinateAwardingCriterion>{par}'
                f'<cbc:AwardingCriterionTypeCode listName="award-criterion-type">{kind}'
                f'</cbc:AwardingCriterionTypeCode><cbc:Name>{name}</cbc:Name>'
                f'</cac:SubordinateAwardingCriterion>')

    body = ""
    for lot_id, crits in lots:
        inner = "".join(crit(*c) for c in crits)
        body += (f'<cac:ProcurementProjectLot><cbc:ID schemeName="Lot">{lot_id}</cbc:ID>'
                 f'<cac:TenderingTerms><cac:AwardingTerms><cac:AwardingCriterion>{inner}'
                 f'</cac:AwardingCriterion></cac:AwardingTerms></cac:TenderingTerms>'
                 f'</cac:ProcurementProjectLot>')
    return ('<ContractNotice xmlns:cac="a" xmlns:cbc="b" xmlns:ext="c" '
            'xmlns:efext="d" xmlns:efac="e" xmlns:efbc="f">' + body + '</ContractNotice>')


def _parse_crits(xml):
    import xml.etree.ElementTree as ET
    from govisor.schema import _eforms_criteria
    return _eforms_criteria(ET.fromstring(xml))


def test_criteria_are_attached_to_their_lot():
    """Ohne lot_id addieren sich bei Mehrlos-Notices die Gewichte aller Lose.

    Gemessen an echten Daten: 36.824 Notices summierten auf >105 %, davon 95,5 %
    mehrlosig bei Ø 4,97 Losen. Genau dieser Fall.
    """
    xml = _crit_xml([
        ("LOT-0001", [("price", "Preis", "number-weight", "per-exa", "70"),
                      ("quality", "Konzept", "number-weight", "per-exa", "30")]),
        ("LOT-0002", [("price", "Preis", "number-weight", "per-exa", "100")]),
    ])
    cs = _parse_crits(xml)
    assert len(cs) == 3
    assert {c.lot_id for c in cs} == {"LOT-0001", "LOT-0002"}
    for lot in ("LOT-0001", "LOT-0002"):
        assert sum(float(c.weight) for c in cs if c.lot_id == lot) == 100


def test_all_criteria_of_a_lot_are_captured():
    """Unter EINEM AwardingCriterion haengen mehrere SubordinateAwardingCriterion —
    die erste Fassung griff nur das erste und verlor den Rest."""
    xml = _crit_xml([("LOT-0001", [
        ("price", "Angebotspreis", "number-weight", "per-exa", "70"),
        ("quality", "Projektleiterstunden", "number-weight", "per-exa", "20"),
        ("quality", "Objektleiterstunden", "number-weight", "per-exa", "10"),
    ])])
    cs = _parse_crits(xml)
    assert len(cs) == 3
    assert [c.name for c in cs] == ["Angebotspreis", "Projektleiterstunden",
                                    "Objektleiterstunden"]


def test_thresholds_and_fixed_amounts_are_not_weights():
    """`number-threshold` (min-score) und `number-fixed` (fix-tot) sind KEINE Gewichte.
    Wer sie mitzaehlt, verfaelscht jede Summe."""
    xml = _crit_xml([("LOT-0001", [
        ("price", "Preis", "number-weight", "per-exa", "60"),
        ("quality", "Mindestpunktzahl", "number-threshold", "min-score", "50"),
        ("quality", "Festbetrag", "number-fixed", "fix-tot", "1000"),
    ])])
    cs = _parse_crits(xml)
    assert len(cs) == 3, "die Kriterien selbst bleiben erhalten"
    weighted = [c for c in cs if c.weight is not None]
    assert len(weighted) == 1 and weighted[0].weight == "60"
    assert weighted[0].weight_kind == "per-exa"


def test_ordinal_rank_is_kept_but_marked():
    """`ord-imp` ist ein Rang, kein Gewicht — er darf nicht als Prozent gelesen werden."""
    xml = _crit_xml([("LOT-0001", [
        ("price", "Preis", "number-weight", "ord-imp", "1"),
        ("quality", "Konzept", "number-weight", "ord-imp", "2"),
    ])])
    cs = _parse_crits(xml)
    assert all(c.weight_kind == "ord-imp" for c in cs)


def test_criteria_without_a_lot_are_not_lost():
    """Schlanke Dialekte haengen die Kriterien nicht unter ein Los — trotzdem behalten."""
    xml = ('<ContractNotice xmlns:cac="a" xmlns:cbc="b"><cac:AwardingTerms>'
           '<cac:AwardingCriterion><cac:SubordinateAwardingCriterion>'
           '<cbc:AwardingCriterionTypeCode>price</cbc:AwardingCriterionTypeCode>'
           '<cbc:Name>Preis</cbc:Name></cac:SubordinateAwardingCriterion>'
           '</cac:AwardingCriterion></cac:AwardingTerms></ContractNotice>')
    cs = _parse_crits(xml)
    assert len(cs) == 1 and cs[0].lot_id is None and cs[0].kind == "price"


def test_doe_inline_buyer_carries_contact_details():
    """DÖE haengt den Kaeufer inline unter ContractingParty/Party — inklusive Kontakt.

    Der Fallback las bisher nur Name/Ort/PLZ/NUTS. Gemessen waren dadurch **0 %** der
    258.246 DÖE-Kaeuferzeilen mit E-Mail/Telefon/Web, obwohl die Werte im XML zu
    60 / 48 / 39 % dastehen. Bei DÖE ist der Kontakt oft die einzige Spur zur
    zustaendigen Person — ohne ihn ist der Lead halb so wert.
    """
    import xml.etree.ElementTree as ET

    from govisor.schema import _parse_eforms

    xml = ('<ContractNotice xmlns:cac="a" xmlns:cbc="b">'
           '<cac:ContractingParty><cac:Party>'
           '<cac:PartyName><cbc:Name>Stadt Musterstadt</cbc:Name></cac:PartyName>'
           '<cbc:WebsiteURI>https://www.musterstadt.de</cbc:WebsiteURI>'
           '<cac:PostalAddress><cbc:CityName>Musterstadt</cbc:CityName>'
           '<cbc:PostalZone>12345</cbc:PostalZone></cac:PostalAddress>'
           '<cac:Contact><cbc:Name>Frau Beispiel</cbc:Name>'
           '<cbc:Telephone>+49 123 4567</cbc:Telephone>'
           '<cbc:ElectronicMail>vergabe@musterstadt.de</cbc:ElectronicMail>'
           '</cac:Contact></cac:Party></cac:ContractingParty></ContractNotice>')
    notice = _parse_eforms(ET.fromstring(xml), "doe-test")
    buyer = next(p for p in notice.parties if p.role == "buyer")
    assert buyer.name == "Stadt Musterstadt"
    assert buyer.email == "vergabe@musterstadt.de"
    assert buyer.phone == "+49 123 4567"
    assert buyer.contact_person == "Frau Beispiel"
    assert buyer.url == "https://www.musterstadt.de"


def test_ted_esender_zaehlt_nicht_als_kaeufer():
    """Der Herausgeber von TED darf keine Vergabe nach Luxemburg ziehen.

    ⚠ DER FEHLER, DEN DIESER TEST FESTHAELT. eForms haengt den Absender in dieselbe
    Huelle wie den Kaeufer — ein zweiter <cac:ContractingParty>-Block, der statt einer
    Kaeuferpartei eine <cac:ServiceProviderParty> traegt. Darin steht ORG-0000, das
    „Publications Office of the European Union", und das sitzt in LUXEMBURG.

    Solange nur DE, AT und PL eingelesen wurden, war das unsichtbar: LU stand in keiner
    Suchmenge. Beim ersten LU-Ingest (2026-09-03) schlug es sofort durch — im Paket
    2024-05 waren 3.743 von 3.922 Saetzen fremd, darunter polnische Krankenhaeuser,
    katalanische Kliniken und griechische Gemeinden. Echtes Luxemburg: 4,6 %.

    Die Bekanntmachung unten ist auf das Wesentliche gekuerzt und traegt die Struktur
    verbatim aus 303266_2024 (Miejskie Przedsiebiorstwo Oczyszczania, Torun).
    """
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<ContractNotice xmlns="urn:oasis:names:specification:ubl:schema:xsd:ContractNotice-2"
  xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
  xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
  xmlns:efac="http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1">
  <cac:ContractingParty>
    <cac:Party><cac:PartyIdentification><cbc:ID>ORG-0001</cbc:ID></cac:PartyIdentification></cac:Party>
  </cac:ContractingParty>
  <cac:ContractingParty>
    <cac:Party><cac:ServiceProviderParty>
      <cbc:ServiceTypeCode listName="organisation-role">TED eSender</cbc:ServiceTypeCode>
      <cac:Party><cac:PartyIdentification><cbc:ID>ORG-0000</cbc:ID></cac:PartyIdentification></cac:Party>
    </cac:ServiceProviderParty></cac:Party>
  </cac:ContractingParty>
  <efac:Organizations>
    <efac:Organization><efac:Company>
      <cac:PartyIdentification><cbc:ID>ORG-0001</cbc:ID></cac:PartyIdentification>
      <cac:PartyName><cbc:Name>Miejskie Przedsiebiorstwo Oczyszczania</cbc:Name></cac:PartyName>
      <cac:PostalAddress><cac:Country>
        <cbc:IdentificationCode listName="country">POL</cbc:IdentificationCode>
      </cac:Country></cac:PostalAddress>
    </efac:Company></efac:Organization>
    <efac:Organization><efac:Company>
      <cac:PartyIdentification><cbc:ID>ORG-0000</cbc:ID></cac:PartyIdentification>
      <cac:PartyName><cbc:Name>Publications Office of the European Union</cbc:Name></cac:PartyName>
      <cac:PostalAddress><cac:Country>
        <cbc:IdentificationCode listName="country">LUX</cbc:IdentificationCode>
      </cac:Country></cac:PostalAddress>
    </efac:Company></efac:Organization>
  </efac:Organizations>
</ContractNotice>"""
    notice = schema.parse(xml, "303266_2024")

    # Der Kaeufer ist polnisch — und NUR polnisch.
    assert notice.country == "PL"
    assert "LU" not in (notice.buyer_countries or []), (
        "Das Publications Office ist als Kaeufer durchgerutscht — der eSender-Riegel in "
        "_eforms_buyer_org_ids greift nicht mehr."
    )

    # Und die Laenderregel schickt sie nicht nach Luxemburg.
    assert not normalize.gehoert_zu_land(notice, "LU")
    assert normalize.gehoert_zu_land(notice, "PL")
