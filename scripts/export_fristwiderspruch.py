#!/usr/bin/env python3
"""Widerspruch bei der Angebotsfrist → web/data/fristwiderspruch.json (Kennzahl 9).

DIE FRAGE. Die Bekanntmachung sagt „Angebotsfrist 02.09.2026". Die Unterlagen sagen „Ablauf der
Angebotsfrist: 01.09.2026, 18:00 Uhr". Wer der Bekanntmachung folgt, kommt einen Tag zu spät.

⚠ EIN FEHLALARM IST HIER TEURER ALS EIN VERPASSTER BEFUND. Deshalb drei Filter, und alle drei
sind an den Belegen geprueft, nicht geschaetzt.

FILTER 1 — NUR DIE ANGEBOTSFRIST. `req_type='frist'` mischt alles: Bindefrist, Zuschlagsfrist,
Ausfuehrungsfrist, Rueckfragefrist, Lieferfristen aus der Vertragsphase. Der Beleg unterscheidet
sie; von 33.399 Fristzeilen benennen 4.586 eindeutig die Angebotsfrist (13,7 %), 6.247 eindeutig
etwas anderes, der Rest bleibt unklar und faellt heraus.

FILTER 2 — HOECHSTENS `MAX_TAGE` ABWEICHUNG. Das ist die wichtigste Grenze, und sie stammt aus
den Belegen. Innerhalb von 30 Tagen lauten die Zitate durchweg „Ablauf der Angebotsfrist Datum
… Uhrzeit …". Darueber steht anderes:

     -66 Tage   „11.07.2026 VERGABEUNTERLAGE · ZUR ANGEBOTSABGABE Seite 26 von 653"  (Seitenkopf)
     +88 Tage   „Die fachliche Eignung des Notarztpersonals hat der …"               (Fehlgriff)
    +435 Tage   „Bereitstellung der geprueften Revierdaten … 2027"                   (Lieferfrist)
   -1268 Tage   „Bewerber, die bis zum 12.07.2023 ihre Bewerbung einreichen …"       (Rueckblick)

⚠ Die ±365-Tage-Faelle („Die Angebotsfrist endet am 10.09.2027") koennten echte Jahresdreher in
den Unterlagen sein — und genau das ist der Grund, sie NICHT zu melden: ohne das Dokument zu
oeffnen laesst sich ein Tippfehler des Auftraggebers nicht von einem Lesefehler von uns
unterscheiden. Bei einer Frist ist Schweigen billiger als Raten.

FILTER 3 — KEINE SEITENKOEPFE. Ein Zitat mit „Seite 7 von 653" nennt das Druckdatum, nicht die
Frist.

FILTER 4 — DER BELEG MUSS DAS DATUM TRAGEN, das er belegen soll. 93 % tun das ohnehin, 0 %
nennen ein ANDERES Datum (das waere das Alarmzeichen), 7 % gar keines: dort stammt der Wert aus
einem Formularfeld und das Zitat ist nur dessen Etikett („Ablauf der Angebotsfrist Datum
Uhrzeit"). Das ist nicht falsch, aber es beweist dem Nutzer nichts — und bei einer Frist soll
er selbst nachschlagen koennen. Kostet 7 von 100 Faellen.

⚠ SIE SAGT NIE „DIE FRIST STIMMT". Ein Widerspruch, den wir sehen, ist da; einer, den wir nicht
sehen, kann trotzdem existieren — wir haben nur bei 1.958 von 14.994 Vorgaengen ueberhaupt beide
Seiten. Dieselbe Anwesenheits-Asymmetrie wie bei Kennzahl 4, und deshalb Bezug `keine`.

GEMESSEN (2026-09-02, alle Vorgaenge mit beiden Seiten): 94,5 % stimmen ueberein, 4,1 % nennen in
den Unterlagen eine FRUEHERE Frist, 1,4 % eine SPAETERE. Die Uebergabe nennt 4,2 % und 1,6 % —
dieselbe Groessenordnung.

⚠ UND DIE RICHTUNG ERKLAERT SICH MEIST DURCH EINE VERLAENGERUNG. „Ablauf der Angebotsfrist nach
Verlaengerung: 23.09.2026" steht so in den Unterlagen: dort ist das Dokument die neuere Wahrheit,
nicht die Bekanntmachung. Umgekehrt bleibt nach einer Verlaengerung oft das alte Dokument liegen.
Die Anzeige behauptet deshalb NICHT, welche Seite recht hat — sie nennt beide Daten und die
einzige Aussage, die immer stimmt: die fruehere ist die sichere.

Aufruf: python3 scripts/export_fristwiderspruch.py
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "data" / "fristwiderspruch.json"

MAX_TAGE = 30        # darueber sind es Lieferfristen, Seitenkoepfe und Jahresdreher
BELEG_MAX = 150

ANGEBOT = re.compile(
    r"angebotsfrist|ablauf der angebots|angebotsabgabe|abgabe(termin|frist)"
    r"|einreichungsfrist|submissions?termin", re.I)
# ⚠ Diese Woerter schliessen aus, auch wenn oben etwas passt. „Abgabefrist fuer saemtliche
# geforderten Daten" ist eine Lieferfrist aus der Vertragsphase, keine Angebotsfrist.
ANDERE = re.compile(
    r"bindefrist|zuschlagsfrist|ausführungsfrist|ausfuehrungsfrist|rückfrag|rueckfrag"
    r"|bieterfrag|fertigstellung|leistungszeit|vertragslaufzeit|gewährleistung", re.I)
SEITENKOPF = re.compile(r"seite\s+\d+\s+von\s+\d+", re.I)


def _schreibweisen(tag: dt.date) -> tuple[str, ...]:
    return (f"{tag.day:02d}.{tag.month:02d}.{tag.year}", f"{tag.day}.{tag.month}.{tag.year}",
            tag.isoformat(), f"{tag.day:02d}.{tag.month:02d}.{str(tag.year)[2:]}")


def _beleg_traegt(zitat: str, tag: dt.date) -> bool:
    """⚠ FILTER 4. Ein Beleg, der das Datum nicht enthaelt, belegt nichts."""
    return any(f in zitat for f in _schreibweisen(tag))


def _ausschnitt(zitat: str, tag: dt.date, breite: int = BELEG_MAX) -> str:
    """Der Ausschnitt liegt UM DAS DATUM, nicht am Satzanfang.

    ⚠ Sonst schneidet die Kuerzung genau das weg, was den Widerspruch belegt: ein Zitat wie
    „Angebotsfrist Angebote, die nicht fristgerecht eingegangen sind, werden ausgeschlossen …
    Ablauf: 25.08.2026" traegt das Datum erst nach 150 Zeichen. Dieselbe Falle hat in diesem
    Projekt schon einmal aus „Bindefrist: 30.10.2026" ein „Bindefrist: …" gemacht."""
    if len(zitat) <= breite:
        return zitat
    stelle = min((zitat.find(f) for f in _schreibweisen(tag) if f in zitat), default=-1)
    if stelle < 0:
        return zitat[:breite]
    start = max(0, stelle - breite // 2)
    ende = min(len(zitat), start + breite)
    stueck = zitat[start:ende]
    # ⚠ Vorn das angebrochene Wort wegnehmen — „… eschlossen, es sei denn" ist kein Satzanfang.
    # Hinten NICHT: dort steht das Datum, und genau darum geht es (dieselbe Regel wie in
    # `explorerCore.js`, wo das Abschneiden hinten schon einmal die Bindefrist gekostet hat).
    if start and " " in stueck:
        stueck = stueck.split(" ", 1)[1]
    return ("… " if start else "") + stueck.strip() + (" …" if ende < len(zitat) else "")

_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})")
_DE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})")


def _datum(roh) -> dt.date | None:
    """⚠ Beide Schreibweisen kommen vor: `2026-09-29 11:00` und `31.03.2027`."""
    if isinstance(roh, dt.date):
        return roh
    s = str(roh or "").strip()
    for muster, (a, b, c) in ((_ISO, (1, 2, 3)), (_DE, (3, 2, 1))):
        m = muster.match(s)
        if m:
            try:
                return dt.date(int(m[a]), int(m[b]), int(m[c]))
            except ValueError:
                return None
    return None


def _ist_angebotsfrist(zitat: str) -> bool:
    return bool(ANGEBOT.search(zitat)) and not ANDERE.search(zitat) and not SEITENKOPF.search(zitat)


def _laender() -> list[str]:
    gold = ROOT / "data" / "gold"
    return sorted(p.name for p in gold.iterdir()
                  if p.is_dir() and (p / "doc_checklist.parquet").exists()) if gold.exists() else []


def main() -> int:
    con = duckdb.connect()
    raus: dict[str, dict] = {}
    for land in _laender():
        C = (ROOT / "data" / "gold" / land / "doc_checklist.parquet").as_posix()
        L = ROOT / "data" / "gold" / land / "lead_export.parquet"
        if not L.exists():
            continue
        bekannt = {str(a): b for a, b in con.execute(
            f"select lead_id, deadline_date from read_parquet('{L.as_posix()}') "
            "where deadline_date is not null").fetchall()}
        geprueft = treffer = 0
        for nid, wert, zitat, datei in con.execute(
                f"select notice_id, value, quote, source_file from read_parquet('{C}') "
                "where req_type = 'frist' and value is not null").fetchall():
            text = " ".join(str(zitat or "").split())
            if not _ist_angebotsfrist(text):
                continue
            dok, bek = _datum(wert), _datum(bekannt.get(str(nid)))
            if not dok or not bek:
                continue
            geprueft += 1
            tage = (dok - bek).days
            if tage == 0 or abs(tage) > MAX_TAGE or not _beleg_traegt(text, dok):
                continue
            # ⚠ Die GROESSTE belegte Abweichung gewinnt: nennen zwei Dokumente verschiedene
            # Termine, ist der weiter entfernte der, der die Planung umwirft.
            alt = raus.get(str(nid))
            if alt and abs(alt["tage"]) >= abs(tage):
                continue
            treffer += 1
            raus[str(nid)] = {"dok": dok.isoformat(), "bek": bek.isoformat(), "tage": tage,
                              "beleg": _ausschnitt(text, dok),
                              "datei": str(datei or "").replace("\\", "/").split("/")[-1][:80]}
        print(f"  {land}: {geprueft:,} belegte Angebotsfristen geprueft · "
              f"{len([k for k in raus]):,} Vorgaenge mit Widerspruch bis {MAX_TAGE} Tage")

    if not raus:
        print("FEHLT: keine Datengrundlage — erst `doc_checklist` bauen lassen.")
        return 1
    frueher = sum(1 for v in raus.values() if v["tage"] < 0)
    OUT.write_text(json.dumps(raus, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Fristwiderspruch → {OUT.name} ({OUT.stat().st_size / 1024:.0f} kB) · "
          f"{frueher:,} Unterlagen frueher, {len(raus) - frueher:,} spaeter")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
