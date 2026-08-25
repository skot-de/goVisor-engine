"""Verfahrenskalender — alle Termine einer Vergabe, chronologisch und benannt.

**Warum es das gibt.** Die Bekanntmachung kennt genau einen Termin: die Angebotsfrist.
In den Unterlagen stehen mehr, und zwei davon entscheiden über Erfolg oder Ausschluss:

* die **Bieterfragen-Frist** — sie liegt VOR der Angebotsfrist. Wer sie verpasst, bietet
  auf eine Leistungsbeschreibung, die er nicht mehr klären lassen kann.
* die **Bindefrist** — wie lange man an sein Angebot gebunden bleibt. Sie bindet Kapazität
  und ist bei der Preiskalkulation ein Risiko, das man kennen muss.

Beide stehen in keiner Bekanntmachung. Gemessen am 2026-08-25: 3.813 Bindefristen und
615 Bieterfragen-Fristen im Dokumentbestand.

⚠ **DIE ROHDATEN TAUGEN NICHT UNGEPRÜFT.** `docextract` typisiert jedes gefundene Datum
als `frist`, und die Bezeichnung landet nur im Zitat. Unter den 14.885 datierten
Einträgen stehen deshalb auch:

    „Druckdatum:  30.07.2026   Seite: 1"
    „Vorabzug 16.07.2026"

Ein Kalender, der das Druckdatum einer PDF als Termin führt, ist schlimmer als keiner.
Deshalb wird hier **klassifiziert statt übernommen**: nur was sich einer Terminart
zuordnen lässt, kommt durch. Gemessen:

    angebotsfrist     4.335   29 %        vertragslaufzeit    218    1 %
    bindefrist        3.813   26 %        ortstermin           55    0 %
    bieterfragen        615    4 %        submission_open      25    0 %
    ausfuehrung         477    3 %
    ------------------------------------------------------------------
    Rauschen            334    2 %   (verworfen)
    nicht zuzuordnen  5.013   34 %   (verworfen)

64 % kommen durch. Die verworfene Drittelmenge wird GEZÄHLT und mit ausgegeben — eine
stillschweigend gekürzte Liste sieht aus wie eine vollständige.
"""
from __future__ import annotations

import datetime as _dt
import re

from . import normwerte

#: Terminarten in der Reihenfolge, in der sie im Verfahren auftreten. Der Schlüssel ist
#: stabil (Frontend/iCal), der Text ist Anzeige.
ARTEN: dict[str, str] = {
    "ortstermin": "Ortstermin / Besichtigung",
    "bieterfragen": "Letzter Tag für Bieterfragen",
    "angebotsfrist": "Angebotsfrist",
    "submission_open": "Öffnung der Angebote",
    "bindefrist": "Ende der Bindefrist",
    "ausfuehrung": "Ausführungs-/Lieferbeginn",
    "vertragslaufzeit": "Vertragslaufzeit",
}

# ⚠ REIHENFOLGE IST BEDEUTUNG. Der erste Treffer gewinnt, deshalb steht das Spezifische
# vor dem Allgemeinen: „Frist für Bieterfragen" enthält das Wort „Frist", und ohne diese
# Reihenfolge würde daraus eine Angebotsfrist.
_REGELN: tuple[tuple[str, str], ...] = (
    ("ortstermin", r"ortstermin|ortsbesichtigung|objektbesichtigung|besichtigungstermin"),
    # ⚠ ZWISCHEN „Fragen" UND „bis" STEHEN WOERTER. Die erste Fassung verlangte sie
    # unmittelbar nebeneinander und verfehlte damit den Normalfall: „Die Fragen sollten
    # bis spaetestens zum 02.09.2026 gestellt werden, damit diese rechtzeitig bis sechs
    # Tage vor Ablauf der Angebotsfrist beantwortet werden koennen." Weil im selben Satz
    # „Angebotsfrist" steht, landete dieser Termin als ANGEBOTSFRIST im Kalender — und
    # erzeugte dort einen Fristkonflikt, den es gar nicht gab. Ein Fehlalarm, der einen
    # Bieter eine Frist nachpruefen laesst, die stimmt.
    ("bieterfragen", r"bieterfrage|fragefrist|letzter tag f(?:ü|ue)r frage|auskunftsersuchen"
                     r"|frage[n]?\b[^.;]{0,45}?(?:bis|sp(?:ä|ae)testens|frist)"),
    ("bindefrist", r"bindefrist|zuschlagsfrist|gebunden bis|bindung.{0,15}angebot"),
    ("submission_open", r"(?:er)?(?:ö|oe)ffnung(?:stermin)? der angebote|submissionstermin"),
    ("angebotsfrist", r"angebots(?:ab)?(?:gabe)?frist|einzureichen bis|einreichungstermin"
                      r"|schlusstermin.{0,25}eingang|abgabetermin|angebotsabgabe bis"),
    ("ausfuehrung", r"ausf(?:ü|ue)hrungsbeginn|baubeginn|leistungsbeginn|ausf(?:ü|ue)hrungsfrist"
                    r"|fertigstellung|lieferung|inbetriebnahme|vertrags- und leistungsbeginn"),
    ("vertragslaufzeit", r"vertragsbeginn|vertragsende|laufzeit.{0,15}(?:von|bis)"),
)
_KOMPILIERT = tuple((k, re.compile(p, re.I)) for k, p in _REGELN)

# ⚠ Was wie ein Termin aussieht und keiner ist. Diese Prüfung läuft VOR den Regeln —
# „Druckdatum: 30.07.2026" enthält kein Terminwort, aber „Stand: 01.10.2026" stünde
# sonst als Ausführungsbeginn im Kalender.
_RAUSCHEN = re.compile(
    r"(?i)druckdatum|vorabzug|seite:?\s*\d|stand:?\s*\d{1,2}\.|fassung|"
    r"version|erstellt am|ausgabe\s*\d|zuletzt ge(?:ä|ae)ndert")


def art(text: str) -> str | None:
    """Terminart aus dem Beleg. ``None``, wenn nicht zuzuordnen — dann fällt er raus."""
    if not text or _RAUSCHEN.search(text):
        return None
    for schluessel, rx in _KOMPILIERT:
        if rx.search(text):
            return schluessel
    return None


def aus_eintrag(item: dict) -> tuple[str, str] | None:
    """Ein Checklisten-Eintrag → ``(art, ISO-Datum)`` oder ``None``.

    Gelesen wird über `quote` UND `value`: das Modell legt die Bezeichnung mal in das
    eine, mal in das andere Feld (gemessen: 99,6 % tragen im `value` nur das Datum, die
    Art steht dann allein im Zitat).
    """
    if item.get("req_type") != "frist":
        return None
    tag = item.get("wert_datum") or normwerte.normalisiere(item).get("wert_datum")
    if not tag:
        return None
    a = art(f"{item.get('quote') or ''} {item.get('value') or ''}")
    return (a, tag) if a else None


def termine(checkliste: list[dict], angebotsfrist: str | None = None,
            heute: _dt.date | None = None) -> dict:
    """Alle Termine einer Vergabe, chronologisch, ohne Dubletten.

    ``angebotsfrist`` ist der Termin aus `lead_deadline` — das RÜCKGRAT. Er liegt für
    jeden offenen Lead vor (861k Zeilen, 0 NULL), während die Unterlagen nur für einen
    Teil ausgelesen sind. Steht er auch im Dokument, bleibt er ein Eintrag.

    Rückgabe: ``{"termine": [...], "verworfen": n}`` — die verworfenen werden mitgezählt,
    damit eine gekürzte Liste nicht wie eine vollständige aussieht.
    """
    heute = heute or _dt.date.today()
    gefunden: dict[tuple[str, str], dict] = {}
    verworfen = 0

    if angebotsfrist:
        gefunden[("angebotsfrist", str(angebotsfrist))] = {
            "art": "angebotsfrist", "datum": str(angebotsfrist),
            "label": ARTEN["angebotsfrist"], "quelle": "bekanntmachung"}

    for item in checkliste or []:
        if item.get("req_type") != "frist":
            continue
        treffer = aus_eintrag(item)
        if treffer is None:
            if item.get("wert_datum") or normwerte.normalisiere(item).get("wert_datum"):
                verworfen += 1
            continue
        a, tag = treffer
        schluessel = (a, tag)
        if schluessel in gefunden:
            continue
        gefunden[schluessel] = {
            "art": a, "datum": tag, "label": ARTEN[a], "quelle": "unterlagen",
            "beleg": (item.get("quote") or "")[:180] or None,
            "datei": item.get("source_file")}

    liste = sorted(gefunden.values(), key=lambda t: (t["datum"], t["art"]))
    for t in liste:
        t["vorbei"] = t["datum"] < heute.isoformat()

    # ⚠ WENN BEIDE SEITEN EINE ANGEBOTSFRIST NENNEN UND SIE SICH UNTERSCHEIDEN, IST DAS
    # KEIN DOPPELEINTRAG, SONDERN EINE WARNUNG. Gemessen am 2026-08-25: 173 offene Leads,
    # bei denen die Unterlagen ein anderes Datum tragen als die Bekanntmachung — im
    # Median 10 Tage auseinander, gehäuft bei ±7 und ±14. Das ist das Muster einer
    # Fristverlängerung, die nur eine der beiden Seiten nachvollzogen hat. (Ein paar
    # Ausreißer sind Jahresdreher in der Unterlage: „19.08.2025" statt 2026.)
    #
    # Wir entscheiden NICHT, welche gilt — das kann nur die Vergabestelle. Wir zeigen,
    # dass es eine Abweichung gibt: wer sich auf die falsche verlässt, bietet zu spät.
    fristen = [t for t in liste if t["art"] == "angebotsfrist"]
    if len({t["datum"] for t in fristen}) > 1:
        amtlich = next((t["datum"] for t in fristen if t["quelle"] == "bekanntmachung"), None)
        for t in fristen:
            t["konflikt"] = True
            if amtlich and t["quelle"] == "unterlagen":
                t["abweichung_tage"] = (_dt.date.fromisoformat(t["datum"])
                                        - _dt.date.fromisoformat(amtlich)).days
    return {"termine": liste, "verworfen": verworfen,
            "fristkonflikt": len({t["datum"] for t in fristen}) > 1}


def _ics_zeit(tag: str) -> str:
    return tag.replace("-", "")


def als_ical(termine_liste: list[dict], titel: str, uid_praefix: str,
             stand: _dt.datetime | None = None) -> str:
    """Termine als iCal-Text (RFC 5545), ganztägig.

    ⚠ Ganztägig mit Absicht. Die Uhrzeit steht in den Unterlagen oft daneben („11:00
    Uhr"), aber nicht verlässlich genug, um sie in einen Kalender zu schreiben: ein
    Termin, der um 11 statt um 10 Uhr eingetragen ist, ist schlimmer als einer ohne
    Uhrzeit. Die Uhrzeit gehört in den Beschreibungstext, wo sie als Zitat steht.
    """
    stand = stand or _dt.datetime.now(_dt.timezone.utc)
    zeilen = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//goVisor//Verfahrenskalender//DE",
              "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    for i, t in enumerate(termine_liste):
        ende = (_dt.date.fromisoformat(t["datum"]) + _dt.timedelta(days=1)).isoformat()
        beschreibung = t.get("beleg") or ""
        zeilen += [
            "BEGIN:VEVENT",
            f"UID:{uid_praefix}-{t['art']}-{i}@govisor.eu",
            f"DTSTAMP:{stand.strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART;VALUE=DATE:{_ics_zeit(t['datum'])}",
            f"DTEND;VALUE=DATE:{_ics_zeit(ende)}",
            f"SUMMARY:{_escape(t['label'])} — {_escape(titel)[:70]}",
        ]
        if beschreibung:
            zeilen.append(f"DESCRIPTION:{_escape(beschreibung)}")
        zeilen.append("END:VEVENT")
    zeilen.append("END:VCALENDAR")
    return "\r\n".join(zeilen) + "\r\n"


def _escape(s: str) -> str:
    """RFC 5545: Komma, Semikolon, Backslash und Zeilenumbruch müssen maskiert werden."""
    return (str(s).replace("\\", "\\\\").replace(";", r"\;")
            .replace(",", r"\,").replace("\n", r"\n").replace("\r", ""))
