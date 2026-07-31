"""Gold-Ebene: Verfahrens-Gruppierung und konfidenz-tragende Entitäten."""

from govisor import gold
from govisor.gold import Method


def test_national_id_is_the_most_reliable_key():
    e = gold.resolve_supplier("Controlware GmbH", national_id="HRB 6431")
    assert e.method == Method.TED_NATIONAL_ID
    assert e.confidence == 1.0
    assert e.is_reliable


def test_person_is_honestly_unresolved_not_fuzzy_matched():
    # 'Taxi Arians' is in no company register. A confident-looking match here
    # would be exactly the lie the confidence field exists to prevent.
    e = gold.resolve_supplier("Paul Skidmore")
    assert e.method == Method.UNRESOLVED
    assert e.confidence == 0.0
    assert not e.is_reliable


def test_exact_register_hit_beats_name_only():
    def hr(norm, plz):
        return ({"nr": "HRB 47580", "name": "EGGERS Umwelttechnik GmbH"}, False)
    e = gold.resolve_supplier("EGGERS Umwelttechnik GmbH", hr_lookup=hr)
    assert e.method == Method.HR_EXACT
    assert e.confidence == 0.9
    assert e.national_id == "HRB 47580"


def test_fuzzy_match_carries_lower_confidence():
    def hr(norm, plz):
        return ({"nr": "HRB 99", "name": "Leonhard Weiss GmbH & Co. KG"}, True)
    e = gold.resolve_supplier("LEONARD WEISS GmbH & Co.KG", postal_code="74589", hr_lookup=hr)
    assert e.method == Method.HR_FUZZY_PLZ
    assert e.confidence == 0.75


def test_no_register_falls_back_to_name_key_not_failure():
    e = gold.resolve_supplier("Kleine Firma ohne Registereintrag GmbH")
    assert e.method == Method.NAME_ONLY
    assert e.confidence == 0.4
    # Still a usable key — just one that says "trust me less".
    assert e.entity_id.startswith("name:")


def test_hr_key_beats_national_id_for_stability():
    # Same company, two generations: 2020 has no national_id, 2024 has one.
    # Both must resolve to the SAME hr: key — else incumbent analysis across the
    # generation boundary always fails (the 7% artefact).
    def hr(norm, plz):
        return ({"nr": "HRB 6431", "name": "Controlware GmbH"}, False)
    old = gold.resolve_supplier("Controlware GmbH", hr_lookup=hr)                    # 2020
    new = gold.resolve_supplier("Controlware GmbH", national_id="DE811", hr_lookup=hr)  # 2024
    assert old.entity_id == new.entity_id == "hr:HRB 6431"
    assert old.method == gold.Method.HR_EXACT


def test_national_id_only_when_no_register_match():
    # No HR match but a national_id present -> national_id is the fallback key.
    def hr(norm, plz):
        return (None, False)
    e = gold.resolve_supplier("Foreign Systems GmbH", national_id="DE999", hr_lookup=hr)
    assert e.entity_id == "id:DE999"
    assert e.method == gold.Method.TED_NATIONAL_ID


def test_consolidate_merges_name_only_into_id_when_plz_corroborates():
    """Nur-Name + Register-ID mit gleichem Namen UND geteilter PLZ → ein Merge."""
    name_only = gold.resolve_supplier("Muster Bau GmbH")               # name:...
    with_id = gold.resolve_supplier("Muster Bau GmbH", national_id="HRB 42")  # id:...
    entity_of = {name_only.entity_id: name_only, with_id.entity_id: with_id}
    plz_of = {name_only.entity_id: {"40213"}, with_id.entity_id: {"40213"}}
    merge_map, flagged = gold._consolidate_by_national_id(entity_of, plz_of)
    assert merge_map == {name_only.entity_id: with_id.entity_id}
    assert flagged == []


def test_consolidate_flags_instead_of_merging_without_plz_evidence():
    """Gleicher Name, aber keine geteilte PLZ → NICHT mergen, sondern flaggen."""
    name_only = gold.resolve_supplier("Muster Bau GmbH")
    with_id = gold.resolve_supplier("Muster Bau GmbH", national_id="HRB 42")
    entity_of = {name_only.entity_id: name_only, with_id.entity_id: with_id}
    plz_of = {name_only.entity_id: {"10115"}, with_id.entity_id: {"40213"}}
    merge_map, flagged = gold._consolidate_by_national_id(entity_of, plz_of)
    assert merge_map == {}
    assert flagged and flagged[0][3] == "kein_plz_beleg"


def test_consolidate_never_merges_when_national_id_is_ambiguous():
    """Zwei verschiedene Register-IDs zum selben Namen → Homonyme, nie mergen."""
    name_only = gold.resolve_supplier("Stadtwerke GmbH")
    id_a = gold.resolve_supplier("Stadtwerke GmbH", national_id="HRB 1")
    id_b = gold.resolve_supplier("Stadtwerke GmbH", national_id="HRB 2")
    entity_of = {e.entity_id: e for e in (name_only, id_a, id_b)}
    plz_of = {name_only.entity_id: {"10115"}, id_a.entity_id: {"10115"}, id_b.entity_id: {"80331"}}
    merge_map, flagged = gold._consolidate_by_national_id(entity_of, plz_of)
    assert merge_map == {}
    assert flagged and flagged[0][3] == "mehrdeutige_id"


def _mini_hr(entries):
    """Baut einen _HRLookup aus [(norm, nr, name, plz), ...] für Tests."""
    lk = gold._HRLookup()
    by_plz = {}
    for norm, nr, name, plz in entries:
        lk[norm] = {"nr": nr, "name": name, "plz": plz}
        if plz:
            by_plz.setdefault(plz, []).append(norm)
    lk._by_plz = by_plz
    return lk


def test_stage2_token_sim_is_order_independent():
    assert gold._hr_token_sim("muller bau", "bau muller") == 1.0
    assert gold._hr_token_sim("stadt", "stadtwerke muster versorgung") < 0.7


def test_stage2_fuzzy_matches_reordered_name_with_same_plz():
    hr = _mini_hr([("bau muller schwerin", "HRB 7", "Müller Bau Schwerin GmbH", "19053")])
    rec, fuzzy = hr.get("muller bau schwerin", "19053")
    assert rec is not None and fuzzy is True and rec["nr"] == "HRB 7"


def test_stage2_no_plz_means_no_fuzzy():
    hr = _mini_hr([("bau muller schwerin", "HRB 7", "Müller Bau Schwerin GmbH", "19053")])
    assert hr.get("muller bau schwerin", None) == (None, False)


def test_stage2_low_similarity_does_not_match_even_with_same_plz():
    hr = _mini_hr([("elektro schmidt", "HRB 9", "Elektro Schmidt GmbH", "10115")])
    assert hr.get("garten weber", "10115") == (None, False)


def test_stage2_end_to_end_yields_fuzzy_method():
    hr = _mini_hr([("mueller bau schwerin", "HRB 7", "Müller Bau Schwerin GmbH", "19053")])
    e = gold.resolve_supplier("Müller Bau Schwerin GmbH ", postal_code="19053", hr_lookup=hr.get)
    assert e.method == Method.HR_EXACT   # normalisiert deckungsgleich → exakt, nicht fuzzy
    e2 = gold.resolve_supplier("Schwerin Bau Müller GmbH", postal_code="19053", hr_lookup=hr.get)
    assert e2.method == Method.HR_FUZZY_PLZ and e2.confidence == 0.75


def test_fuzzy_gate_off_by_default_never_matches():
    """Ohne aktiven Fuzzy-Zweig (leerer PLZ-Block) fällt der Lookup auf Exakt-Match
    zurück — der 24%-Fehl-Merge-Zweig bleibt aus (gemessen 2026-07-19)."""
    lk = gold._HRLookup()
    lk["muster bau schwerin"] = {"nr": "HRB 1", "name": "Muster Bau", "plz": "19053"}
    # _by_plz leer (fuzzy=False in build_hr_index) → auch bei PLZ kein Fuzzy-Treffer
    assert lk.get("bau muster schwerin", "19053") == (None, False)
    # Exakt-Match funktioniert unverändert
    rec, fuzzy = lk.get("muster bau schwerin", "19053")
    assert rec is not None and fuzzy is False


def test_curated_alias_merges_rename_into_canonical():
    """Kuratierter Alias (DB InfraGO→DB Netz) verschmilzt in die register-getragene Entität."""
    from govisor.config import Config
    netz = gold.ResolvedEntity(entity_id="hr:HRB50879", canonical_name="DB Netz Aktiengesellschaft",
                               method=Method.HR_EXACT, confidence=0.9, national_id="HRB50879")
    infra = gold.ResolvedEntity(entity_id="name:db infrago", canonical_name="DB InfraGO AG",
                                method=Method.NAME_ONLY, confidence=0.4)
    entity_of = {netz.entity_id: netz, infra.entity_id: infra}
    aliases = gold._load_entity_aliases(Config(countries=("DE",), data_dir="data"), "DE", entity_of)
    assert aliases == {"name:db infrago": "hr:HRB50879"}
