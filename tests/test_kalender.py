"""Verfahrenskalender — nur benannte Termine, und Widersprüche werden gezeigt."""
import datetime as dt

from govisor import kalender as k


def test_druckdatum_ist_kein_termin():
    """⚠ Der Grund, warum hier klassifiziert und nicht übernommen wird.

    `docextract` typisiert JEDES gefundene Datum als `frist`. Im Bestand stehen deshalb
    „Druckdatum: 30.07.2026 Seite: 1" und „Vorabzug 16.07.2026" — 334 solcher Einträge
    (2 %). Ein Kalender, der das Druckdatum einer PDF als Termin führt, ist schlimmer
    als keiner.
    """
    for rausch in ("Druckdatum:  30.07.2026   Seite: 1", "Vorabzug 16.07.2026",
                   "Stand: 01.10.2026", "Fassung vom 12.03.2026",
                   "irgendein Satz ohne Terminwort 05.05.2026"):
        assert k.art(rausch) is None, rausch


def test_die_sieben_terminarten_werden_erkannt():
    proben = {
        "bindefrist": "Bindefrist endet am: 09.09.2026",
        "bieterfragen": "Letzter Tag für Bieterfragen ist Dienstag, der 18.08.26.",
        "angebotsfrist": "Einzureichen bis (Eröffnungs-/Einreichungstermin) Datum: 13.08.2026",
        "ortstermin": "Termin für die Objektbesichtigung: 07.08.2026 09:00 Uhr",
        "ausfuehrung": "Der Vertrags- und Leistungsbeginn ist der 01.10.2026.",
        "submission_open": "Submissionstermin Datum 15.09.2026",
    }
    for erwartet, text in proben.items():
        assert k.art(text) == erwartet, f"{text!r} → {k.art(text)}"


def test_spezifisches_schlaegt_allgemeines():
    """„Frist für Bieterfragen" enthält das Wort „Frist" — ohne die Reihenfolge in
    `_REGELN` würde daraus eine Angebotsfrist, und der Bieter verpasst den früheren
    Termin."""
    assert k.art("Frist für Bieterfragen: 18.08.2026") == "bieterfragen"
    assert k.art("Die Zuschlagsfrist endet am 09.09.2026") == "bindefrist"


def test_bekanntmachung_ist_das_rueckgrat_und_wird_nicht_verdoppelt():
    cl = [{"req_type": "frist", "value": "13.08.2026",
           "quote": "Angebotsfrist endet am 13.08.2026"}]
    e = k.termine(cl, angebotsfrist="2026-08-13", heute=dt.date(2026, 8, 1))
    assert len(e["termine"]) == 1, "dasselbe Datum darf nicht zweimal dastehen"
    assert e["fristkonflikt"] is False


def test_abweichende_angebotsfrist_wird_als_konflikt_gezeigt():
    """⚠ 173 offene Leads tragen in den Unterlagen ein anderes Datum als in der
    Bekanntmachung — im Median 10 Tage, gehäuft bei ±7 und ±14 (Fristverlängerung, die
    nur eine Seite nachvollzogen hat). Wir entscheiden nicht, welche gilt; wir zeigen,
    dass es eine Abweichung gibt."""
    cl = [{"req_type": "frist", "value": "20.08.2026",
           "quote": "Die Angebotsfrist endet am 20.08.2026"}]
    e = k.termine(cl, angebotsfrist="2026-08-13", heute=dt.date(2026, 8, 1))
    assert e["fristkonflikt"] is True
    aus_unterlagen = [t for t in e["termine"] if t["quelle"] == "unterlagen"][0]
    assert aus_unterlagen["abweichung_tage"] == 7
    assert all(t.get("konflikt") for t in e["termine"] if t["art"] == "angebotsfrist")


def test_verworfene_werden_gezaehlt_nicht_verschwiegen():
    """Eine stillschweigend gekürzte Liste sieht aus wie eine vollständige."""
    cl = [{"req_type": "frist", "value": "30.07.2026", "quote": "Druckdatum: 30.07.2026 Seite: 1"},
          {"req_type": "frist", "value": "09.09.2026", "quote": "Bindefrist endet am: 09.09.2026"}]
    e = k.termine(cl, heute=dt.date(2026, 8, 1))
    assert len(e["termine"]) == 1 and e["verworfen"] == 1


def test_ical_ist_gueltig_und_maskiert():
    e = k.termine([{"req_type": "frist", "value": "09.09.2026",
                    "quote": "Bindefrist endet am: 09.09.2026; wichtig, sehr"}],
                  heute=dt.date(2026, 8, 1))
    ics = k.als_ical(e["termine"], "Sanierung, Turnhalle", "L1",
                     stand=dt.datetime(2026, 8, 25, 12, 0, tzinfo=dt.timezone.utc))
    assert ics.startswith("BEGIN:VCALENDAR") and ics.rstrip().endswith("END:VCALENDAR")
    assert "\r\n" in ics, "RFC 5545 verlangt CRLF"
    assert "DTSTART;VALUE=DATE:20260909" in ics
    assert "DTEND;VALUE=DATE:20260910" in ics, "ganztaegig endet am Folgetag"
    # Komma und Semikolon muessen maskiert sein, sonst zerfaellt die Zeile.
    assert r"Sanierung\, Turnhalle" in ics
    assert r"wichtig\, sehr" in ics and r"\;" in ics


def test_ein_fremdes_land_raeumt_unsere_dateien_nicht_weg(tmp_path, monkeypatch):
    """⚠ Der Export schreibt ALLE Länder in EIN Verzeichnis — die Reinigung darf das nicht
    vergessen.

    Am 2026-08-25 stand in `main()` sinngemäß „alles löschen, was dieser Lauf nicht
    geschrieben hat". Gemessen an echten Daten: `--country AT` hätte **alle 2.945
    DE-Dateien** entfernt. Österreich und die Schweiz haben bei den Dokumenten 0 %
    Abdeckung, ihr Ergebnis ist also leer — und eine Reinigung, die „leer" als „alles
    verwaist" liest, räumt den Bestand des Nachbarlandes ab. Gemeldet hätte sie das als
    „2.945 verwaiste entfernt", was wie Hausputz aussieht.

    Der Test hält beide Richtungen fest: fremdes Land fasst nichts an, eigenes Land räumt
    seine Karteileiche trotzdem weg. Ohne die zweite Hälfte wäre „nie löschen" ein
    bestandener Test und trotzdem falsch.
    """
    import importlib.util
    from pathlib import Path

    wurzel = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("ek", wurzel / "scripts" / "export_kalender.py")
    ek = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ek)

    monkeypatch.setattr(ek, "JE_VORGANG", tmp_path / "kalender")
    monkeypatch.setattr(ek, "MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(ek, "ROOT", tmp_path)          # nur für die Schlusszeile
    ek.JE_VORGANG.mkdir(parents=True)
    (ek.JE_VORGANG / "de-1.json").write_text('{"titel":"x","termine":[],"verworfen":0}')
    (ek.JE_VORGANG / "de-2.json").write_text('{"titel":"y","termine":[],"verworfen":0}')

    eintrag = {"titel": "DE-Lead", "termine": [], "verworfen": 0}
    # DE kennt beide Leads, AT keinen von beiden — so sieht die Wirklichkeit aus.
    import collections
    z = collections.Counter
    welt = {"DE": ({"de-1": eintrag, "de-2": eintrag}, z({"leads": 2}), {"de-1", "de-2"}),
            "AT": ({}, z({"leads": 9}), {"at-1"})}
    monkeypatch.setattr(ek, "baue", lambda c="DE": welt[c])

    ek.main(["--country", "DE"])                        # Manifest anlegen
    ek.main(["--country", "AT"])                        # der gefährliche Lauf
    uebrig = {p.stem for p in ek.JE_VORGANG.glob("*.json")}
    assert uebrig == {"de-1", "de-2"}, \
        f"ein AT-Lauf hat DE-Dateien angefasst: {sorted(uebrig)}"

    # Und die Reinigung muss trotzdem greifen, wenn ein Lead aus UNSEREM Lauf wegfällt.
    welt["DE"] = ({"de-1": eintrag}, z({"leads": 1}), {"de-1", "de-2"})
    ek.main(["--country", "DE"])
    assert {p.stem for p in ek.JE_VORGANG.glob("*.json")} == {"de-1"}, \
        "die eigene Karteileiche bleibt liegen — die Reinigung räumt gar nichts mehr"


def test_ical_zeilen_werden_gefaltet_und_zerschneiden_keine_umlaute():
    """RFC 5545 §3.1: Inhaltszeilen sollen 75 Oktett nicht überschreiten.

    Gemessen am 2026-08-25 über den ganzen Bestand: **37 % der erzeugten Zeilen** lagen
    darüber, die längste bei 198 Oktett — die DESCRIPTION trägt ein wörtliches Zitat aus
    den Vergabeunterlagen. Der Standard sagt hier SHOULD, nicht MUST; ein Ausfall träfe
    also nur strenge Clients, wäre auf einzelne Nutzer verteilt und von aussen unsichtbar.

    ⚠ Die eigentliche Falle ist nicht die Länge, sondern die EINHEIT: gezählt wird in
    Oktett, geschnitten wird an Zeichen. Wer beides verwechselt, zerlegt „ä" in zwei
    halbe Bytes.

    Zwei Seiten, beide geprüft: die Python-Fassung hier direkt, die ausgelieferte
    JS-Fassung über `node` — sonst prüfte der Test eine Abschrift.
    """
    import subprocess
    from pathlib import Path

    lang = ("Termine für eine Ortsbesichtigung können mit DWS Architekten PartGmbB "
            "Dollmann Wagner Schmidt vereinbart werden — Łódź, 🏗 und € inbegriffen.")
    ics = k.als_ical([{"art": "ortstermin", "datum": "2026-09-30",
                       "label": "Ortstermin", "quelle": "unterlagen", "beleg": lang}],
                     "Ein sehr langer Vergabetitel über Straßenbauarbeiten", "x")
    zeilen = ics.split("\r\n")
    assert all(len(z.encode("utf-8")) <= 75 for z in zeilen), \
        "Python-iCal schreibt wieder Zeilen über 75 Oktett"
    # Entfalten muss das Original herstellen — sonst ist der Text zwar kurz, aber kaputt.
    assert lang.replace(",", r"\,") in ics.replace("\r\n ", ""), \
        "die Faltung hat den Belegtext beschädigt"

    wurzel = Path(__file__).resolve().parent.parent
    skript = wurzel / "web" / "scripts" / "pruefe-ical-faltung.mjs"
    p = subprocess.run(["node", str(skript)], capture_output=True, text=True)
    assert p.returncode == 0, f"die ausgelieferte JS-Fassung faltet falsch:\n{p.stdout}{p.stderr}"
