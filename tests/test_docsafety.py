"""Ticket #23 Phase 6 — Sicherheit & Quote (§12/§14): Plausibilität, Bestätigungsschwelle, Quote, Zeitkanal."""
from govisor import docsafety as ds


def test_quota():
    assert ds.quota_remaining(0, False) == 3
    assert ds.quota_remaining(3, False) == 0
    assert ds.quota_remaining(5, True) is None       # Pro = unbegrenzt
    assert ds.can_analyze(2, False) and not ds.can_analyze(3, False)
    assert ds.can_analyze(99, True)


def test_plausibility_deadline_anchor():
    lead = {"deadline": "2026-08-15 12:00", "cpv": "90910000", "buyer": "Stadt Heidelberg", "value_band": "medium"}
    ok = ds.plausibility_check({"deadline": "2026-08-15T12:00", "cpv": "9091", "buyer": "Stadt Heidelberg",
                                "value_band": "medium"}, lead)
    assert ok["deadline_exact"] and ok["consistent"] and "deadline" in ok["checked"]
    bad = ds.plausibility_check({"deadline": "2026-09-01", "buyer": "Stadt Heidelberg"}, lead)
    assert not bad["deadline_exact"] and "deadline" in bad["mismatches"] and not bad["consistent"]
    cpvbad = ds.plausibility_check({"deadline": "2026-08-15 12:00", "cpv": "45000000"}, lead)
    assert "cpv" in cpvbad["mismatches"]


def test_visibility_confirmation_threshold():
    lead = {"deadline": "2026-08-15 12:00", "cpv": "90910000", "buyer": "Stadt Heidelberg"}
    # widerspruchsfrei + exakte Frist → shared
    assert ds.visibility_after({"deadline": "2026-08-15 12:00", "cpv": "9091", "buyer": "Stadt Heidelberg"}, lead) == "shared"
    # Frist weicht ab → private, trotz sonst passendem Käufer
    assert ds.visibility_after({"deadline": "2026-08-20", "buyer": "Stadt Heidelberg"}, lead) == "private"
    # zweiter unabhängiger Upload matcht → shared, auch ohne perfekten Abgleich
    assert ds.visibility_after({"buyer": "irgendwer"}, lead, independent_match=True) == "shared"
    # gar nichts prüfbar → private (kein blindes Freischalten)
    assert ds.visibility_after({}, {}) == "private"


def test_timing_channel_padding():
    assert ds.padded_delay(2.0) == 6.0               # 8s Mindestdauer → 6s nachlegen
    assert ds.padded_delay(10.0) == 0.0              # schon länger → keine Zusatzwartezeit
    assert ds.padded_delay(-1.0) == 8.0
