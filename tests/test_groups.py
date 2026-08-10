"""Editierbare, persistente Gruppen-Kuration."""

import csv

import pyarrow as pa
import pyarrow.parquet as pq

from govisor import gold
from govisor.config import Config


def _entities(cfg, rows):
    p = cfg.gold_dir / "DE" / "entities.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    t = pa.table({"entity_id": [r[0] for r in rows],
                  "canonical_name": [r[1] for r in rows],
                  "national_id": [r[2] for r in rows]})
    pq.write_table(t, p)


def _party_emails(cfg, links):
    """links: (notice_id, role, seq, entity_id, email) → party_entity + notice_parties."""
    pe = cfg.gold_dir / "DE" / "party_entity.parquet"
    pe.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table({
        "notice_id": [l[0] for l in links], "role": [l[1] for l in links],
        "seq": [l[2] for l in links], "entity_id": [l[3] for l in links]}), pe)
    npq = cfg.silver_dir / "DE" / "notice_parties" / "year=2024" / "p.parquet"
    npq.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table({
        "notice_id": [l[0] for l in links], "role": [l[1] for l in links],
        "seq": [l[2] for l in links], "email": [l[4] for l in links]}), npq)


def test_seed_groups_by_confirmed_domain(tmp_path):
    cfg = Config(data_dir=tmp_path)
    _entities(cfg, [("hr:1", "CANCOM Managed Services GmbH", "DE1"),
                    ("hr:2", "CANCOM IT Solutions GmbH", "DE2"),
                    ("hr:3", "Bechtle GmbH", "DE3")])
    _party_emails(cfg, [("n1", "winner", 0, "hr:1", "info@cancom.de"),
                        ("n2", "winner", 0, "hr:2", "support@cancom.de"),
                        ("n3", "winner", 0, "hr:3", "x@bechtle.de")])
    total, added = gold.seed_groups(cfg, "DE")
    assert added == 3
    rows = {r["entity_id"]: r for r in csv.DictReader(cfg.group_csv("DE").open())}
    # Domain bestätigt den Namen → Gruppe. Beide CANCOM-Einheiten → dieselbe Gruppe.
    assert rows["hr:1"]["group_label"] == "CANCOM"
    assert rows["hr:2"]["group_label"] == "CANCOM"
    assert rows["hr:1"]["source"] == "auto_domain"
    assert rows["hr:3"]["group_label"] == "BECHTLE"


def test_name_stem_alone_does_not_group(tmp_path):
    # Ohne bestätigende Domain KEIN geratenes Label (Namensstamm ist zu rauschig).
    cfg = Config(data_dir=tmp_path)
    _entities(cfg, [("hr:1", "CANCOM Managed Services GmbH", "DE1")])
    gold.seed_groups(cfg, "DE")
    rows = {r["entity_id"]: r for r in csv.DictReader(cfg.group_csv("DE").open())}
    assert rows["hr:1"]["group_label"] == ""     # gelistet, aber ungruppiert
    assert rows["hr:1"]["source"] == "seed"


def test_manual_edit_survives_reseed(tmp_path):
    cfg = Config(data_dir=tmp_path)
    _entities(cfg, [("hr:1", "CANCOM Managed Services GmbH", "DE1")])
    gold.seed_groups(cfg, "DE")
    # Nutzer korrigiert: haengt Pironet (anderer Name) an CANCOM.
    path = cfg.group_csv("DE")
    lines = path.read_text().splitlines()
    lines.append("hr:9,Pironet AG,DE9,CANCOM,manual")
    path.write_text("\n".join(lines) + "\n")

    # Neue Firma taucht auf -> Re-Seed. Die Handkorrektur darf NICHT verschwinden.
    _entities(cfg, [("hr:1", "CANCOM Managed Services GmbH", "DE1"),
                    ("hr:9", "Pironet AG", "DE9"),
                    ("hr:5", "Neue Firma GmbH", "DE5")])
    gold.seed_groups(cfg, "DE")
    rows = {r["entity_id"]: r for r in csv.DictReader(path.open())}
    assert rows["hr:9"]["group_label"] == "CANCOM"      # Kuration erhalten
    assert rows["hr:9"]["source"] == "manual"
    assert "hr:5" in rows                                # Neue Firma geseedet


def test_build_entity_groups_from_csv(tmp_path):
    cfg = Config(data_dir=tmp_path)
    path = cfg.group_csv("DE")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "entity_id,canonical_name,national_id,group_label,source\n"
        "hr:1,CANCOM MS,DE1,CANCOM,manual\n"
        "hr:2,CANCOM IT,DE2,CANCOM,seed\n"
        "hr:3,Einzel GmbH,DE3,,seed\n")     # kein Label -> keine Gruppe
    g, links = gold.build_entity_groups(cfg, "DE")
    assert g == 1 and links == 2            # eine Gruppe CANCOM, 2 Einheiten


def test_domain_label_strips_www_as_prefix_not_charset():
    """`lstrip("www.")` entfernt eine ZEICHENMENGE, keinen Präfix.

    Der Bug hat jede Domain verstümmelt, die mit w oder . beginnt: „wienerlinien.at"
    wurde zu „ienerlinien.at" → Gruppe IENERLINIEN. Gemessen waren 2.986 DE-Domains
    mit 52.748 Kontakten betroffen; „wbm.de" verlor seine Gruppe sogar ganz, weil der
    Rest „bm" unter die 3-Zeichen-Grenze fiel. Ein Tippfehler in einer Zeile, der die
    Firmengruppen-Bildung still verzerrt — deshalb festgenagelt.
    """
    from govisor import locales
    locales.use("DE")
    assert gold.domain_group_label("wienerlinien.at") == "WIENERLINIEN"
    assert gold.domain_group_label("weber-bau.de") == "WEBER-BAU"
    assert gold.domain_group_label("wbm.de") == "WBM"
    # Der eigentliche Zweck bleibt erhalten: ein echtes www.-Präfix fällt weg.
    assert gold.domain_group_label("www.cancom.de") == "CANCOM"
    assert gold.domain_group_label("cancom.de") == "CANCOM"


def test_at_locale_matches_austrian_reality():
    """Die AT-Locale muss die drei gemessenen Österreich-Eigenheiten treffen.

    Ohne sie liefe der AT-Ingest auf dem deutschen Profil: „Ges.m.b.H." wäre keine
    erkannte Rechtsform (die Punkte brechen `\\bmbh\\b`), und ASFINAG — mit 20.293
    Nennungen der größte Auftraggeber des Landes — gälte als privat, weil es dort
    ausgeschrieben als „Autobahnen- und Schnellstraßen-Finanzierungs-AG" firmiert.
    """
    from govisor import entities as ent, locales
    at = locales.use("AT")
    try:
        for name in ("Wiener Wohnen Ges.m.b.H.", "Bundesimmobiliengesellschaft m.b.H.",
                     "Maier OG", "Gruber e.U.", "Alpha Bau KEG"):
            assert at.re_legal.search(ent.strip_accents(name.lower())), name
        for name in ("Autobahnen- und Schnellstraßen-Finanzierungs-Aktiengesellschaft",
                     "ÖBB-Infrastruktur AG", "Magistrat der Stadt Wien",
                     "Bezirkshauptmannschaft Melk", "Reinhalteverband Großraum Linz"):
            assert gold.looks_public(name), name
        assert not gold.looks_public("Kapsch TrafficCom AG")
    finally:
        locales.use("DE")
