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
