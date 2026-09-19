#!/usr/bin/env python3
"""Was ist an einem laufenden Vergabeverfahren seit seiner Veroeffentlichung passiert?

⚠ WARUM ES DIESE TABELLE GIBT. Bis zum 2026-09-19 kannte goVisor kein einziges Ereignis
nach der Veroeffentlichung. Das Feld `aktualitaet` stand in allen 85.168 Leads auf `None`,
weil der Export es als feste Null schreibt, und `notice_kind='corrigendum'` traf seit
Februar 2024 nichts mehr:

    Jahr   Ausschreibungen   erkannte Berichtigungen
    2023        171.607              14.835
    2024        172.605                 790
    2025        168.884                   0
    2026        132.048                   0

Kein Rueckgang im Markt, sondern ein Formatwechsel: eForms kennt kein eigenes
Berichtigungsformular. Eine Berichtigung IST eine vollstaendige, neu veroeffentlichte
`ContractNotice` mit einem `<efac:Changes>`-Block. Gemessen ueber 37.398 Meldungen aus
2026-07 bis 2026-09 sind **13,4 % aller Meldungen Berichtigungen**.

⚠ DIE ZUORDNUNG LAEUFT UEBER DIE VERFAHRENSKENNUNG, NICHT UEBER DEN VERWEIS.
`efbc:ChangedNoticeIdentifier` traegt zwei verschiedene Dinge: meist die eForms-UUID der
geaenderten Fassung, gelegentlich die Veroeffentlichungsnummer (gemessen 172 zu 3). Die
UUID steht in keiner unserer Tabellen — wer sie als Schluessel nimmt, braucht erst einen
zweiten Index. `cbc:ContractFolderID` (BT-04) dagegen teilen ALLE Bekanntmachungen eines
Verfahrens, sie steht in 593 von 600 Meldungen, und sie loest nebenbei den Fall mit, dass
mehrere Berichtigungen aufeinander folgen.

⚠ DAS FENSTER IST BEGRENZT, UND ZWAR ABSICHTLICH. Gelesen werden die Monate unter
`data/raw_live/<land>/`, nicht der Gesamtbestand. Ein Ereignis braucht ein laufendes
Verfahren; 8.990 der 14.282 offenen DE-Leads (63 %) sind in den letzten zwei Monaten
veroeffentlicht worden. Wer das Fenster aufzieht, zahlt den Scan des ganzen Archivs fuer
Verfahren, deren Frist laengst vorbei ist.

⚠ WAS HIER NICHT ENTSCHIEDEN WIRD: ob eine Berichtigung ein eigener Lead bleibt. Gemessen
sind 81 von 195 Berichtigungen ein eigener Lead im Export, und 39 davon haben dort einen
Zwilling mit gleichem Titel und Kaeufer — dieselbe Ausschreibung zweimal in der Liste. Das
ist ein echter Befund, aber seine Reparatur heisst Lead-Erzeugung umbauen (die Berichtigung
traegt die AKTUELLE Frist, das Original die veraltete) und gehoert nicht in denselben
Schritt wie das Erkennen.

Aufruf:  python3 scripts/baue_aenderungen.py [--land DE] [--monate 3] [--trocken]
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from govisor.schema import eforms_changes   # noqa: E402  (nach sys.path)

# Aenderungsgrund → Ereignisart. Gemessen ueber 5.028 Berichtigungen aus 2026-07..09;
# die Haeufigkeiten stehen daneben, damit sichtbar bleibt, was hier Alltag ist und was
# Ausnahme.
#
# ⚠ DIE ART IST NICHT DER GRUND. Der haeufigste Code (`update-add`, 2.626) sagt nur
# „etwas wurde ergaenzt" — ob das eine neue Frist, ein nachgereichtes Leistungsverzeichnis
# oder eine geaenderte Referenzanforderung war, steht im Klartext daneben. Deshalb
# entscheidet ueber „Frist neu" NICHT der Code, sondern der Vergleich der Fristen.
_ART = {
    "cancel":        "aufgehoben",     #     3   „Aufhebung des Vergabeverfahrens"
    "cancel-intent": "aufgehoben",     #     3   „Das Vergabeverfahren wird aufgehoben, da …"
    "susp-review":   "ausgesetzt",     #     4   „… aufgrund rechtlicher Hinweise der Vergabekammer"
    "update-add":    "geaendert",      # 2.626
    "cor-buy":       "geaendert",      # 1.550
    "cor-pub":       "geaendert",      #   509
    "info-release":  "geaendert",      #   259
    "cor-esen":      "geaendert",      #     7
}


def _text(root: ET.Element, name: str) -> str | None:
    for elem in root.iter():
        tag = elem.tag
        if (tag.split("}")[-1] if "}" in tag else tag) == name and elem.text and elem.text.strip():
            return elem.text.strip()
    return None


def _frist(root: ET.Element) -> str | None:
    """Angebotsfrist als `YYYY-MM-DD`.

    ⚠ Nur aus `TenderSubmissionDeadlinePeriod`. Ein blosses `cbc:EndDate` gibt es in einer
    eForms-Meldung mehrfach (Vertragslaufzeit, Bindefrist, Rahmenvertragsende); die erste
    Fundstelle ist mit hoher Wahrscheinlichkeit die falsche.
    """
    for elem in root.iter():
        tag = elem.tag
        if (tag.split("}")[-1] if "}" in tag else tag) != "TenderSubmissionDeadlinePeriod":
            continue
        d = _text(elem, "EndDate")
        return d.split("+")[0].split("Z")[0] if d else None
    return None


def sammle(ordner: pathlib.Path) -> tuple[dict, list]:
    """Je Verfahren die Meldungen, und alle Berichtigungen mit ihren Angaben."""
    verfahren: dict[str, list] = defaultdict(list)
    berichtigungen: list[dict] = []
    for datei in sorted(ordner.glob("*.xml")):
        try:
            root = ET.parse(datei).getroot()
        except ET.ParseError:
            continue
        kennung = _text(root, "ContractFolderID")
        nid = datei.stem.replace("-", "_")
        datum = (_text(root, "IssueDate") or "")[:10] or None
        frist = _frist(root)
        if kennung:
            verfahren[kennung].append({"notice_id": nid, "am": datum, "frist": frist})
        c = eforms_changes(root)
        if c is None:
            continue
        berichtigungen.append({
            "notice_id": nid, "verfahren": kennung, "am": datum, "frist": frist,
            "grund_code": c.get("grund_code"),
            "text": c.get("grund_text") or c.get("beschreibung"),
        })
    return verfahren, berichtigungen


def baue(land: str, monate: int) -> tuple[list[dict], list[dict]]:
    wurzel = WURZEL / "data" / "raw_live" / land
    if not wurzel.is_dir():
        print(f"  (kein raw_live fuer {land})")
        return [], []
    ordner = sorted([p for p in wurzel.iterdir() if p.is_dir()])[-monate:]
    print(f"  Lese {land}: {', '.join(p.name for p in ordner)}")
    verfahren: dict[str, list] = defaultdict(list)
    berichtigungen: list[dict] = []
    for o in ordner:
        v, b = sammle(o)
        for k, zeilen in v.items():
            verfahren[k].extend(zeilen)
        berichtigungen.extend(b)
        print(f"    {o.name}: {sum(len(x) for x in v.values()):>6,} Meldungen, {len(b):>5,} Berichtigungen")

    raus: list[dict] = []
    for b in berichtigungen:
        art = _ART.get(b["grund_code"] or "", "geaendert")
        geschwister = verfahren.get(b["verfahren"] or "", [])
        # ⚠ „Frist neu" entscheidet der VERGLEICH, nicht der Grundcode. Frueher steht die
        # alte Frist, in der Berichtigung die neue; unterscheiden sie sich, ist das die
        # Aussage, die den Bieter interessiert — und sie schlaegt jedes „geaendert".
        vorher = [g["frist"] for g in geschwister
                  if g["notice_id"] != b["notice_id"] and g["am"] and b["am"]
                  and g["am"] <= b["am"] and g["frist"]]
        frist_alt = max(vorher) if vorher else None
        if art == "geaendert" and frist_alt and b["frist"] and frist_alt != b["frist"]:
            art = "frist"
        # Das Ereignis gilt fuer JEDE Bekanntmachung des Verfahrens: der Lead im Export
        # kann das Original sein oder die Berichtigung selbst (gemessen 81 von 195).
        for g in geschwister or [{"notice_id": b["notice_id"]}]:
            raus.append({
                "land": land, "lead_id": g["notice_id"], "verfahren": b["verfahren"],
                "art": art, "am": b["am"], "text": b["text"],
                "grund_code": b["grund_code"], "frist_alt": frist_alt, "frist_neu": b["frist"],
                "quelle_id": b["notice_id"],
            })
    # ⚠ Die Verfahrenszuordnung geht SEPARAT heraus, nicht als Nebenprodukt der Ereignisse.
    # Zwei Bekanntmachungen desselben Verfahrens sind auch dann Geschwister, wenn keine von
    # beiden eine Berichtigung traegt — und genau die braucht der Dublettenschritt.
    zuordnung = [{"land": land, "notice_id": g["notice_id"], "verfahren": k,
                  "am": g["am"], "frist": g["frist"]}
                 for k, zeilen in verfahren.items() if len(zeilen) > 1
                 for g in zeilen]
    print(f"    Verfahren mit mehreren Bekanntmachungen: {len({z['verfahren'] for z in zuordnung}):,}"
          f" ({len(zuordnung):,} Zeilen)")
    return raus, zuordnung


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--land", default="DE")
    ap.add_argument("--monate", type=int, default=3)
    ap.add_argument("--trocken", action="store_true", help="nur zaehlen, nichts schreiben")
    a = ap.parse_args()

    zeilen, zuordnung = baue(a.land, a.monate)
    if not zeilen:
        print("  keine Ereignisse gefunden")
        return 0
    import collections
    arten = collections.Counter(z["art"] for z in zeilen)
    leads = len({z["lead_id"] for z in zeilen})
    print(f"\n  {len(zeilen):,} Ereigniszeilen auf {leads:,} Bekanntmachungen")
    for k, n in arten.most_common():
        print(f"    {k:<12} {n:>6,}")
    if a.trocken:
        print("\n  (trocken — nichts geschrieben)")
        return 0

    import duckdb
    ziel = WURZEL / "data" / "gold" / a.land / "notice_changes.parquet"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    teil = ziel.with_suffix(".parquet.part")
    c = duckdb.connect()
    c.execute("create table t (land varchar, lead_id varchar, verfahren varchar, art varchar,"
              " am varchar, text varchar, grund_code varchar, frist_alt varchar,"
              " frist_neu varchar, quelle_id varchar)")
    c.executemany("insert into t values (?,?,?,?,?,?,?,?,?,?)",
                  [[z["land"], z["lead_id"], z["verfahren"], z["art"], z["am"], z["text"],
                    z["grund_code"], z["frist_alt"], z["frist_neu"], z["quelle_id"]] for z in zeilen])
    # ⚠ Ein Verfahren kann mehrfach berichtigt werden. Fuer die Liste zaehlt das JUENGSTE
    # Ereignis; die aelteren bleiben in der Tabelle, damit die Detailansicht sie zeigen kann.
    c.execute(f"copy (select * from t order by lead_id, am) to '{teil}' (format parquet)")
    teil.replace(ziel)
    print(f"\n  → {ziel}")

    # ── Verfahrensgeschwister ────────────────────────────────────────────────────────
    #
    # ⚠ DAS IST DER BELEG, DEN DIE DUBLETTEN-FIREWALL NICHT HAT. Sie vergleicht Titel und
    # Kaeufer und hat eine Sperre gegen das Zusammenlegen zweier Saetze DERSELBEN Quelle —
    # zu Recht, denn TED fuehrt legitim mehrere Verfahren mit gleichem Titel. Die
    # Verfahrenskennung (BT-04) ist dagegen kein Indiz, sondern eine Aussage des
    # Auftraggebers: dieselbe Kennung heisst dasselbe Verfahren.
    if zuordnung:
        ziel2 = WURZEL / "data" / "gold" / a.land / "notice_procedures.parquet"
        teil2 = ziel2.with_suffix(".parquet.part")
        c.execute("create table v (land varchar, notice_id varchar, verfahren varchar,"
                  " am varchar, frist varchar)")
        c.executemany("insert into v values (?,?,?,?,?)",
                      [[z["land"], z["notice_id"], z["verfahren"], z["am"], z["frist"]]
                       for z in zuordnung])
        c.execute(f"copy (select * from v order by verfahren, am) to '{teil2}' (format parquet)")
        teil2.replace(ziel2)
        print(f"  → {ziel2}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
