"""Ticket #23 Phase 1 — Extraktions-Kern: Schema-Validierung + Zitat-Verifikation (§6a).

Der LLM ist injiziert (Fake-chat_fn) — geprüft wird die belegpflichtige, schema-gebundene
Verarbeitung, nicht das Modell.
"""
import json

from govisor import doctax, docextract
from govisor.doctypes import classify, PRIORITY, priority_rank, sprachraeume


DOC = (
    "Bewerbungsbedingungen\n\n"
    "Der Bieter hat ein gültiges Zertifikat nach DIN EN ISO 9001 vorzulegen.\n"
    "Mindestens drei vergleichbare Referenzen aus den letzten fünf Jahren mit einem Volumen von je "
    "mindestens 500.000 EUR sind nachzuweisen.\n"
)


def _fake(items):
    def chat_fn(messages, model=None):
        return json.dumps(items, ensure_ascii=False)
    return chat_fn


def test_verify_quote_normalizes_and_rejects_fabricated():
    assert docextract.verify_quote("ISO 9001 vorzulegen", DOC)
    # Whitespace/Umbruch-Normalisierung: mehrfacher Space + andere Groß-/Kleinschreibung findet trotzdem
    assert docextract.verify_quote("gültiges   Zertifikat nach DIN EN ISO 9001", DOC)
    assert not docextract.verify_quote("Mindestumsatz von 2 Millionen EUR jährlich", DOC)  # nicht im Text
    assert not docextract.verify_quote("ISO", DOC)                                          # zu kurz


def test_verify_quote_survives_pdf_hyphenation():
    # PDF-Zeilenumbruch-Trennstrich + Interpunktion dürfen den Beleg nicht scheitern lassen
    src = "Der Auftragnehmer erbringt die Leistungs-\nbeschreibung gemäß Anlage 3 zum Vertrag."
    assert docextract.verify_quote("Leistungsbeschreibung gemäß Anlage 3", src)
    assert docextract.verify_quote("Auftrag-\nnehmer erbringt die Leistungsbeschreibung", src)
    assert not docextract.verify_quote("Leistungsbeschreibung gemäß Anlage 7", src)   # 7 ≠ 3 → nicht belegt


def test_validate_item_schema():
    ok = {"req_type": "zertifikat", "quote": "…", "marking": "Zitat"}
    assert docextract.validate_item(ok)
    assert not docextract.validate_item({"req_type": "quatsch", "quote": "x", "marking": "Zitat"})
    assert not docextract.validate_item({"req_type": "zertifikat", "quote": "x", "marking": "Erfunden"})
    assert not docextract.validate_item({"req_type": "zertifikat", "quote": "", "marking": "Zitat"})  # Beleg fehlt
    # allowed-Liste greift
    assert not docextract.validate_item(ok, allowed_req_types={"mindestumsatz"})
    # Abgeleitet darf ohne quote
    assert docextract.validate_item({"req_type": "haftung", "marking": "Abgeleitet"})


def test_extract_keeps_verified_drops_unverified_and_invalid():
    items = [
        {"req_type": "zertifikat", "value": "ISO 9001", "unit": None,
         "quote": "Der Bieter hat ein gültiges Zertifikat nach DIN EN ISO 9001 vorzulegen.",
         "marking": "Zitat"},                                             # verifizierbar → behalten
        {"req_type": "mindestumsatz", "value": "2 Mio", "unit": "EUR",
         "quote": "Ein Mindestumsatz von 2 Mio EUR ist nachzuweisen.", "marking": "Zitat"},  # Zitat NICHT im Text → verworfen
        {"req_type": "quatsch", "value": None, "unit": None, "quote": "…", "marking": "Zitat"},  # Schema-invalid → verworfen
    ]
    res = docextract.extract("eignung", DOC, "Teil_A_Bewerbungsbedingungen.pdf", chat_fn=_fake(items))
    assert res["rejected"] == 2
    assert len(res["items"]) == 1
    it = res["items"][0]
    assert it["req_type"] == "zertifikat"
    assert it["theme"] == doctax.theme_for("zertifikat") == "zertifikate_qm"
    assert it["source_file"] == "Teil_A_Bewerbungsbedingungen.pdf"


def test_extract_parse_error_and_unsupported():
    def garbage(messages, model=None):
        return "das ist kein JSON"
    assert docextract.extract("eignung", DOC, "x.pdf", chat_fn=garbage).get("parse_error")
    assert docextract.extract("sonstiges", DOC, "x.pdf", chat_fn=_fake([])).get("skipped")


def test_extract_allowed_req_types_enforced():
    # zuschlagskriterium ist bei doctype 'eignung' nicht erlaubt → verworfen
    items = [{"req_type": "zuschlagskriterium", "value": "Preis", "unit": "60%",
              "quote": "Der Bieter hat ein gültiges Zertifikat nach DIN EN ISO 9001 vorzulegen.",
              "marking": "Zitat"}]
    res = docextract.extract("eignung", DOC, "x.pdf", chat_fn=_fake(items))
    assert res["items"] == [] and res["rejected"] == 1


def test_classifier_and_priority():
    assert classify("Teil_B_Leistungsbeschreibung.pdf") == "leistungsbeschreibung"
    assert classify("Bewerbungsbedingungen.pdf") == "eignung"
    assert classify("Zuschlagskriterien_Wertung.pdf") == "zuschlagskriterien"
    assert classify("random_anlage_b1_bilder.pdf") == "sonstiges"
    # Priorität: Eignung vor Aufforderung
    assert priority_rank("eignung") < priority_rank("aufforderung")
    assert priority_rank("sonstiges") > priority_rank("aufforderung")
    assert PRIORITY[0] == "eignung"


def test_classify_kennt_die_sprachraeume_von_at_ch_und_pl():
    """Der Parser war deutsch — nicht nur sprachlich, sondern bis in die VOB/VOL-Kuerzel.

    Gemessen am 2026-08-21 fielen 75,7 % echter oesterreichischer Dateinamen in
    ``sonstiges``, franzoesische und italienische zu 100 %. Diese Faelle sind Stellvertreter:
    jeder stammt aus einem realen Bestand oder aus der Portal-Terminologie.
    """
    # Oesterreich sagt „Bestimmungen", wo Deutschland „Bedingungen" sagt.
    assert classify("Allgemeine_Angebotsbestimmungen.pdf") == "aufforderung"
    assert classify("Teilnahmebestimmungen_Stufe1.pdf") == "eignung"
    assert classify("Ausschreibungsunterlage_Gesamt.pdf") == "leistungsbeschreibung"
    assert classify("Rahmenvereinbarung_Entwurf.pdf") == "vertrag"
    # ... und kuerzt „Erklaerung" zu „Erkl".
    assert classify("BieErkl_Bietergemeinschaft.pdf") == "eigenerklaerung"
    assert classify("SolidarhaftErkl.pdf") == "eigenerklaerung"

    # Westschweiz / Tessin.
    assert classify("Cahier_des_charges.pdf") == "leistungsbeschreibung"
    assert classify("Conditions_de_participation.pdf") == "eignung"
    assert classify("Bordereau_des_prix.xlsx") == "leistungsbeschreibung"
    assert classify("Capitolato_onere.pdf") == "leistungsbeschreibung"
    assert classify("Criteri_di_aggiudicazione.pdf") == "zuschlagskriterien"

    # Polen — Bekanntmachungen liegen vor, Unterlagen noch nicht; Muster ungeprueft.
    assert classify("Opis_przedmiotu_zamowienia.pdf") == "leistungsbeschreibung"
    assert classify("Wzor_umowy.pdf") == "vertrag"

    assert set(sprachraeume()) == {"de", "at", "fr", "it", "pl"}


def test_allgemeine_behaelterwoerter_stehlen_den_spezifischen_regeln_nichts():
    """Die teuerste Falle beim Sprachausbau: Wortlisten, die fast ueberall passen.

    ``beilage``, ``annexe``, ``formular`` stehen vor beliebigen Anhaengen. Als Regel weit
    vorne verschlucken sie die Treffer der genauen Typen — und weil beide betroffenen Typen
    nicht priorisiert sind, faellt es in keiner Vollstaendigkeitspruefung auf.
    """
    assert classify("Vergabeformulare/222 Preisermittlung bei Kalkulation.pdf") == "preisblatt"
    assert classify("Formulare/Information nach Art. 13 DSGVO.pdf") == "datenschutz"
    assert classify("Datenschutzerklaerung.odt") == "datenschutz"
    assert classify("Beilage G - Kalkulationsgrundlage.xlsx") == "preisblatt"
    # `\blb\b` traf „234 2027 LB Anschreiben" — LB war dort der Projektname, nicht der Typ.
    assert classify("234 2027 LB Anschreiben 260703.pdf") == "aufforderung"
    assert classify("234 2027 LB Anl A 04 Verkehrsvertrag.pdf") == "vertrag"


def test_fragenbeantwortung_ist_ein_eigener_typ():
    """128 Treffer allein im AT-Bestand — in der deutschen Taxonomie gab es ihn nicht."""
    assert classify("Fragenbeantwortung_Runde_2.pdf") == "fragenantworten"
    assert classify("Bieterfragen_und_Antworten.pdf") == "fragenantworten"
    assert classify("Formblätter_Anhang.pdf") == "formblatt"   # Umlaut-Plural traf frueher nicht


def test_deutsche_klassifikation_bleibt_unveraendert():
    """Der Sprachausbau darf den gewachsenen DE-Bestand nicht umsortieren.

    Gemessen gegen 16.537 echte deutsche Dateinamen: 0 vorher erkannte fallen in ``sonstiges``.
    """
    assert classify("Teil_B_Leistungsbeschreibung.pdf") == "leistungsbeschreibung"
    assert classify("Bewerbungsbedingungen.pdf") == "eignung"
    assert classify("Zuschlagskriterien_Wertung.pdf") == "zuschlagskriterien"
    assert classify("Aufforderung_zur_Angebotsabgabe.pdf") == "aufforderung"
    assert classify("VOB_B_2019.pdf") == "vertrag"
    assert classify("random_anlage_b1_bilder.pdf") == "sonstiges"


def test_dateiname_schlaegt_ordner():
    """77,6 % der Namen im Bestand tragen einen Pfad, und die Portale benennen die Ordner
    nach Doktyp. Wird der ganze Pfad in einem Rutsch geprueft, entscheidet die
    Regelreihenfolge statt der Naehe zur Datei — gemessen 1.845 Faelle.
    """
    assert classify("anschreiben/Information_Datenschutz.pdf") == "datenschutz"
    assert classify("vertragsbedingungen/FB2_Erklaerung Bietergemeinschaft.pdf") == "eigenerklaerung"
    assert classify("leistungsbeschreibungen/Anlage 810_44_Kanalplan.pdf") == "technische_anlage"
    # Der Ordner bleibt Rueckfallebene — 19.565 Dateien sind NUR ueber ihn erkennbar.
    assert classify("leistungsbeschreibungen/Anlage 3.pdf") == "leistungsbeschreibung"
    # `::` trennt Archiv und Eintrag und zaehlt wie ein Pfadtrenner.
    assert classify("Vergabeunterlagen.zip::02 Einrichtungsplan Kueche.pdf") == "technische_anlage"


def test_vhb_nummer_schlaegt_das_wort_formblatt():
    """„VE17_VHB 211_EU.pdf" traegt kein Typwort, ist aber die Aufforderung zur Angebotsabgabe.

    Ohne die Nummerntabelle gewinnt ``\bvhb\b`` und macht daraus ein Formblatt.
    """
    assert classify("VE17_VHB 211_EU.pdf") == "aufforderung"
    assert classify("VHB 212 EU.pdf") == "eignung"
    assert classify("Formblatt 244.pdf") == "datenschutz"
    assert classify("VHB_223.pdf") == "preisblatt"
    # ⚠ Steht ein echtes Typwort im Namen, gewinnt das Wort: es beschreibt den Inhalt,
    # die Nummer nur das Formular, in dem er steckt.
    assert classify("26-08-10 - FB 211_EU LV - Akustikrollos.pdf") == "leistungsbeschreibung"
    # Ohne Formblatt-Marker ist eine dreistellige Zahl kein Signal.
    assert classify("Anlage 213 Grundriss.pdf") == "technische_anlage"


def test_zuschlagskalkulation_ist_ein_preisformular():
    """VHB 221 heisst „Preisermittlung bei ZUSCHLAGSkalkulation" — das Wort taeuscht.

    948 Dateien tragen es, nur 406 tragen „Zuschlagskriterien". Ohne den Ausschluss
    bekamen 252 Vorgaenge faelschlich Zuschlagskriterien bescheinigt.
    """
    assert classify("VHB 221 - Preisermittlung bei Zuschlagskalkulation.pdf") == "preisblatt"
    assert classify("Zuschlagskriterien_Gewichtung.pdf") == "zuschlagskriterien"
    # „Eignungskriterien" ist Eignung, nicht Zuschlag — das blanke `kriterien` traf beides.
    assert classify("CSX 41 - Eignungskriterien.pdf") == "eignung"


def test_vob_ohne_teilbuchstabe_ist_kein_vertrag():
    """Blankes „VOB" ist bei 1.340 Dateien ein Vergabe-Praefix, keine Vertragsordnung."""
    assert classify("VOB_B_2019.pdf") == "vertrag"
    assert classify("VOB/A Ausgabe 2019.pdf") == "vertrag"
    assert classify("VOB ANGEBOTSSCHREIBEN.pdf") == "aufforderung"
    assert classify("VOB KVHB KEV 179 Eigenerklaerung zur Eignung.pdf") == "eignung"


def test_gaeb_endung_als_letzte_rueckfallebene():
    """„3923240.d83" traegt keinerlei Wort — die Endung ist ein Leistungsverzeichnis."""
    assert classify("3923240.d83") == "leistungsbeschreibung"
    assert classify("Angebotsaufforderung.X83") == "aufforderung"   # Wort schlaegt Endung


def test_fragenbeantwortung_wird_ausgewertet_und_kommt_zuerst():
    """Die Fragenbeantwortung ist der einzige Doktyp, der die anderen ueberschreibt.

    Die Bekanntmachung sagt das Alte, sie das Geltende: verschobene Fristen, korrigierte
    Mengen, zurueckgenommene Anforderungen. Gemessen am 2026-08-21 lagen 29 Mio. Zeichen
    davon im Bestand und wurden nie gelesen — der Typ existierte in der Taxonomie nicht.

    Zwei Eigenschaften werden hier festgehalten:
    1. Sie wird ueberhaupt ausgewertet.
    2. Sie steht VOR den priorisierten Typen. Der Token-Deckel schneidet von hinten ab
       (10,3 % der Vorgaenge liegen darueber); stuende sie hinten, fiele der geltende
       Stand als Erstes weg.
    """
    import importlib.util
    import sys
    from pathlib import Path

    from govisor import docextract

    assert docextract.supported("fragenantworten"), "keine Extraktionsaufgabe hinterlegt"

    wurzel = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("_ad", wurzel / "scripts" / "analyze_docs.py")
    ad = importlib.util.module_from_spec(spec)
    sys.modules["_ad"] = ad
    spec.loader.exec_module(ad)

    assert ad.AUSWERTUNG[0] == "fragenantworten", ad.AUSWERTUNG
    assert set(PRIORITY) <= set(ad.AUSWERTUNG)
    # ... aber NICHT in der Vollstaendigkeitspruefung: die meisten Vergaben haben keine.
    assert "fragenantworten" not in PRIORITY


def test_fragenbeantwortung_holt_die_geltende_frist():
    """Der Fall, um den es geht: eine verlaengerte Angebotsfrist im Nachtrag."""
    from govisor import docextract

    text = ("Fragenbeantwortung Nr. 2\n\nFrage 7: Kann die Angebotsfrist verlaengert werden?\n"
            "Antwort: Die Angebotsfrist wird auf den 12.09.2026, 10:00 Uhr verlaengert.")

    def falscher_chat(messages, model=None):
        return ('[{"req_type": "frist", "value": "Angebotsfrist", '
                '"unit": "12.09.2026, 10:00 Uhr", '
                '"quote": "Die Angebotsfrist wird auf den 12.09.2026, 10:00 Uhr verlaengert.", '
                '"source_page": 1, "marking": "Zitat"}]')

    r = docextract.extract("fragenantworten", text, "Fragenbeantwortung_2.pdf",
                           chat_fn=falscher_chat)
    assert not r.get("skipped"), "die Aufgabe wurde uebersprungen"
    assert r["rejected"] == 0, "das Zitat steht woertlich im Text und darf nicht verworfen werden"
    assert r["items"] and r["items"][0]["req_type"] == "frist"


def test_pflichtordner_beantworten_was_eingereicht_werden_muss():
    """Der Ordner sagt die PFLICHT, nicht nur die Art — und wir lasen ihn nicht.

    Gemessen am 2026-08-21: 27.130 Dateien in 3.157 von 5.726 Vorgaengen (55 %) liegen in
    einem Ordner wie „Vom Unternehmen auszufuellende Dokumente" (allein 21.760). Das ist die
    direkte Antwort auf die praktisch wichtigste Frage, und sie steht in der Struktur — kein
    Modell, keine Unsicherheit, kein Zitat.
    """
    from govisor import doctypes

    assert doctypes.pflicht("V/Vom Unternehmen auszufuellende Dokumente/FB 124.pdf") == "einzureichen"
    assert doctypes.pflicht("V/Zwingend erforderliche Angebotsdateien/LV.x83") == "einzureichen"
    assert doctypes.pflicht("Paket.zip::Dateien fuer Angebot/Preisblatt.xlsx") == "einzureichen"

    # ⚠ Die UMKEHRUNG darf nicht im selben Topf landen: „verbleibt beim Bieter" heisst
    # NICHT einreichen. Zusammengeworfen wird aus einer Entlastung eine Anforderung.
    assert doctypes.pflicht("V/Verbleibt beim Bieter/VOB B.pdf") == "verbleibt_beim_bieter"

    # Nur ORDNER zaehlen. Eine Datei dieses Namens ist eine Beschreibung, kein Auftrag.
    assert doctypes.pflicht("Angebotsunterlagen.pdf") is None
    assert doctypes.pflicht("V/Leistungsbeschreibungen/Anlage 3.pdf") is None


def test_pflicht_eintraege_tragen_die_richtige_markierung():
    """Aus der Ablage geschlossen, nicht aus dem Text zitiert."""
    import importlib.util
    import sys
    from pathlib import Path

    wurzel = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("_ad2", wurzel / "scripts" / "analyze_docs.py")
    ad = importlib.util.module_from_spec(spec)
    sys.modules["_ad2"] = ad
    spec.loader.exec_module(ad)

    items = ad._pflicht_items([
        "V/Vom Unternehmen auszufuellende Dokumente/FB 124.pdf",
        "V/Verbleibt beim Bieter/VOB B.pdf",
        "V/Leistungsbeschreibungen/Anlage 3.pdf",
    ])
    assert len(items) == 2
    for i in items:
        assert i["marking"] == "Abgeleitet", "weder zitiert noch extrahiert — geschlossen"
        assert i["quote"] == ""
        assert i["req_type"] == "einzureichendes_dokument"
    arten = {i["pflicht"] for i in items}
    assert arten == {"einzureichen", "verbleibt_beim_bieter"}

    # Ausreisser werden gekappt, aber nicht verschwiegen.
    viele = [f"V/Zwingend erforderliche Angebotsdateien/D{i}.pdf" for i in range(ad.PFLICHT_MAX + 5)]
    aus = ad._pflicht_items(viele)
    assert len(aus) == ad.PFLICHT_MAX + 1
    assert "5 weitere" in aus[-1]["label"]


def test_pflicht_eintrag_verdraengt_nicht_den_parser_eintrag():
    """Dieselbe Datei darf nicht zweimal in der Checkliste stehen.

    Ein ausfuellbares Formular in „Vom Unternehmen auszufuellende Dokumente" wird von beiden
    Schienen erfasst: die Parser-Schiene meldet „Ausfuellbares Formular (12 Felder, 4
    Pflicht)", die Ablage meldet den Dateinamen. Beides ist richtig, aber der Parser-Eintrag
    sagt mehr — und zwei Eintraege zu einer Datei liest sich wie zwei Anforderungen.
    """
    import importlib.util
    import sys
    from pathlib import Path

    wurzel = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("_ad3", wurzel / "scripts" / "analyze_docs.py")
    ad = importlib.util.module_from_spec(spec)
    sys.modules["_ad3"] = ad
    spec.loader.exec_module(ad)

    datei = "V/Vom Unternehmen auszufuellende Dokumente/Angebot.pdf"
    r = ad.analyze_notice(
        [(datei, "")],
        structured={datei: {"parser": "pdf_fields", "n_fields": 12,
                            "fields": [{"required": True}] * 4}},
    )
    treffer = [i for i in r["checklist"] if i.get("source_file") == datei]
    assert len(treffer) == 1, [t["label"] for t in treffer]
    assert "Formular" in treffer[0]["label"], treffer[0]["label"]
    assert treffer[0].get("parser") == "pdf_fields"
