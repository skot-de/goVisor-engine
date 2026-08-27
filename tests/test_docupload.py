"""Ticket #23 Phase 3 — Upload-Sicherheitsprüfungen (§4.2/§5): reine, testbare Logik."""
import re
from pathlib import Path

from govisor import docupload as du
from govisor import doctax


def test_sql_taxonomy_seed_matches_doctax():
    """Der req_type-Seed in supabase/0006_doc_analysis.sql muss exakt doctax.REQ_TYPES spiegeln
    (sonst driftet die DB-Referenz von der Python-Taxonomie ab)."""
    sql = Path(__file__).resolve().parent.parent / "supabase" / "0006_doc_analysis.sql"
    text = sql.read_text(encoding="utf-8")
    rows = re.findall(r"\('([a-z_]+)','([^']+)','([a-z_]+)'\)",
                      text.split("insert into public.doc_requirement_types", 1)[1])
    seeded = {rt: theme for rt, _label, theme in rows}
    assert set(seeded) == set(doctax.REQ_TYPES), "SQL-Seed ≠ doctax.REQ_TYPES (Drift)"
    for rt, theme in seeded.items():
        assert theme == doctax.REQ_TYPES[rt][1] == doctax.theme_for(rt)
        assert theme in doctax.THEMES


def test_limits():
    assert du.check_limits(10, 5) == []
    assert "paket_zu_gross" in du.check_limits(du.MAX_PACKAGE_BYTES + 1, 5)[0]
    assert "zu_viele_dateien" in du.check_limits(10, du.MAX_FILES + 1)[0]


def test_zip_slip():
    assert du.is_zip_slip("../../etc/passwd")
    assert du.is_zip_slip("/absolut/pfad")
    assert du.is_zip_slip("C:/windows/x")
    assert du.is_zip_slip("unterordner/../../raus.txt")
    assert not du.is_zip_slip("unterordner/datei.pdf")
    assert not du.is_zip_slip("Teil_A/LV.x83")


def test_zip_bomb():
    assert du.check_zip_bomb(1000, 1000 * 101)          # 101:1 → verdächtig
    assert not du.check_zip_bomb(1000, 1000 * 50)        # 50:1 → ok
    assert du.check_zip_bomb(0, 100)                     # 0 komprimiert, aber Inhalt → verdächtig


def test_package_hash_order_independent():
    a = [("b.pdf", b"zwei"), ("a.pdf", b"eins")]
    b = [("a.pdf", b"eins"), ("b.pdf", b"zwei")]
    assert du.package_hash(a) == du.package_hash(b)      # Reihenfolge egal → Dedup stabil
    assert du.package_hash(a) != du.package_hash([("a.pdf", b"eins"), ("b.pdf", b"drei")])


def test_detect_own_offer():
    offer = ("Sehr geehrte Damen und Herren, hiermit bieten wir Ihnen an, die Leistung zu erbringen. "
             "Unser Angebotspreis beträgt 120.000 EUR netto. Mit freundlichen Grüßen")
    assert du.detect_own_offer(offer)                        # 2 distinkte committende Phrasen
    docs = ("Leistungsbeschreibung: Der Auftragnehmer erbringt die Reinigung. Die Angebotssumme ist "
            "in das Preisblatt einzutragen.")                # Vorlagen-Vokabular → kein Eigen-Angebot
    assert not du.detect_own_offer(docs)
    # Standard-VHB-Formblatt 124 (wiederholt „unser Angebot") darf NICHT anschlagen (§5-3-Falle):
    vhb = "Falls mein/unser Angebot in die engere Wahl kommt, werde ich/werden wir … " * 3
    assert not du.detect_own_offer(vhb)


def test_match_lead():
    lead = {"title": "Rahmenvertrag Gebäudereinigung Rathaus", "buyer": "Stadt Heidelberg",
            "aktenzeichen": "VG-2026-0815", "cpv": "90910000"}
    # gleiches Aktenzeichen → matched trotz anderem Titel
    assert du.match_lead({"aktenzeichen": "VG 2026 0815", "title": "anderes"}, lead)["matched"]
    # Titel-/Käufer-Überschneidung ohne Widerspruch → matched
    assert du.match_lead({"title": "Gebäudereinigung Rathaus Los 1", "buyer": "Stadt Heidelberg"}, lead)["matched"]
    # CPV-Widerspruch → nicht matched, mismatch gelistet
    r = du.match_lead({"title": "irgendwas", "buyer": "irgendwer", "cpv": "45000000"}, lead)
    assert not r["matched"] and "cpv" in r["mismatches"]
    # widersprüchliches Aktenzeichen → mismatch
    assert "aktenzeichen" in du.match_lead({"aktenzeichen": "XX-1", "title": lead["title"]}, lead)["mismatches"]


def test_zweifelhafte_zuordnung_wird_erkannt_und_bleibt_bei_den_daten():
    """§5-4: Kommt der Auftraggeber des Leads in den hochgeladenen Unterlagen überhaupt vor?

    Ein Nutzer kann Unterlagen zu JEDEM Vorgang hochladen; Volltext, Signale und die
    LLM-Analyse landen danach im geteilten Bestand und werden ALLEN Nutzern dieses Leads
    ausgeliefert. Die Prüfung gab es, aber ihr Ergebnis ging als einmalige Meldung an den
    Hochladenden zurück — die Daten selbst blieben unmarkiert. Wer den Lead später öffnete,
    sah eine Auswertung ohne jeden Vorbehalt, und der Vorbehalt war nach dem Seitenwechsel
    weg, während die Daten blieben.

    ⚠ Die Schwelle ist absichtlich niedrig. Käufernamen weichen zwischen Bekanntmachung und
    Unterlagen oft ab; ein Fehlalarm bei jedem zweiten Upload wäre schlimmer als keiner.
    Deshalb prüft der Test BEIDE Richtungen — sonst wäre „immer zweifeln" bestanden.
    """
    from govisor import docupload

    # Passt: der Name steht in den Unterlagen.
    assert docupload.zuordnung_zweifelhaft(
        "Stadt Wolfsburg", "Die Stadt Wolfsburg schreibt folgende Leistung aus.") is None
    assert docupload.zuordnung_zweifelhaft(
        "Universitätsklinikum Tübingen", "Das Universitätsklinikum Tübingen vergibt") is None

    # Passt nicht: ein ganz anderer Auftraggeber.
    treffer = docupload.zuordnung_zweifelhaft(
        "Stadt Wolfsburg", "Landeshauptstadt München, Baureferat, Vergabestelle")
    assert treffer and treffer["expected_buyer"] == "Stadt Wolfsburg"
    assert treffer["anteil"] == 0.0

    # ⚠ Ein Name aus lauter Allerweltswörtern gibt KEINE Aussage her. Ohne diese Grenze
    # zählte „Stadt" als Treffer und jedes kommunale Dokument passte zu jedem kommunalen
    # Lead — die Prüfung wäre da, würde aber nichts prüfen.
    assert docupload.zuordnung_zweifelhaft("Stadt", "beliebiger Text") is None
    assert docupload.zuordnung_zweifelhaft("", "beliebiger Text") is None
    assert docupload.zuordnung_zweifelhaft("Stadt Wolfsburg", "") is None

    # Und der Aufrufer muss den Befund AN DIE DATEN schreiben, nicht nur zurückgeben.
    wurzel = Path(__file__).resolve().parent.parent
    quelle = (wurzel / "scripts" / "process_upload.py").read_text(encoding="utf-8")
    assert "docupload.zuordnung_zweifelhaft(" in quelle, \
        "der Upload-Weg prüft die Zuordnung nicht mehr"
    assert '"herkunft": "upload"' in quelle and '"zuordnung_zweifelhaft"' in quelle, \
        "die Herkunft landet nicht mehr im gespeicherten Satz — der Vorbehalt wäre wieder flüchtig"
