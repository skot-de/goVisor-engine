#!/usr/bin/env python3
"""Bieterfragen und Antworten → web/data/bieterfragen.json.

DIE FRAGE. Waehrend der Angebotsfrist fragen Bewerber die Vergabestelle, und die Antworten
muessen ALLEN Bietern zugaenglich gemacht werden (§ 20 Abs. 3 EU-VgV, § 12a EU-VOB/A). Wer sie
nicht liest, rechnet auf einem ueberholten Stand — und merkt es nicht.

⚠ DIE UEBERGABE SAGT, ES GEBE SIE NICHT. Wortlaut: „existieren in unseren Daten **nicht** und
sind **nicht abgreifbar**", mit Verweis auf `docs/bieterfragen-feasibility.md`. Diese Studie
(27.07.) ist nicht falsch, sondern ueberholt: sie durchsuchte die **eForms-Attribute der
Bekanntmachungen** (475,3 Mio. Zeilen) und fand dort zu Recht nichts. Die Q&A stecken in den
**Vergabeunterlagen** — als „Bieterinformation", „Bieterfragenkatalog", „Bieterrundschreiben".
Gemessen am 2026-09-02: 257 Vorgaenge mit einer Fragerunde, 172 davon mit lesbarem Text.

    Wer eine Machbarkeitsstudie zitiert, prueft, WELCHE Quelle sie untersucht hat.

⚠ DUBLETTEN ENTSTEHEN HIER DURCH VERSIONEN, nicht durch Fehler. Ein „Bieterfragenkatalog"
liegt als Stand 10.08., 13.08. und 20.08. im Paket; ohne Entdublierung zaehlt derselbe Katalog
viermal (gemessen: 264 Marken statt 66). Entdubliert wird ueber den TEXT, nicht ueber den
Dateinamen — die Staende heissen verschieden und sagen dasselbe.

⚠ UND NICHT JEDE MARKE IST EINE FRAGE. „Im Folgenden finden Sie die Antwort zu Ihrer Frage:"
ist ein Einleitungssatz; er faellt heraus. Ebenso alles unter `MIND_ZEICHEN` — ein Abschnitt
von 43 Zeichen („Ein Schranksystem ist nicht mehr gefordert?") ist ohne den Zusammenhang, in
dem er steht, keine Auskunft.

⚠ WAS HIER STEHT, IST EIN AUSSCHNITT UND KEIN GETRENNTES FRAGE-ANTWORT-PAAR. Die Marke
(„Frage 3:", „Zu Frage 3:") trennt Abschnitte, aber sie sagt nicht zuverlaessig, ob das
Folgende die Frage oder die Antwort ist: nur 35 % der Abschnitte enthalten ein Fragezeichen.
Die Anzeige nennt sie deshalb Abschnitte und verweist auf das Dokument, statt eine Ordnung zu
behaupten, die die Daten nicht hergeben.

Aufruf: python3 scripts/export_bieterfragen.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "data" / "bieterfragen.json"

MIND_ZEICHEN = 80    # kuerzer ist ohne Zusammenhang keine Auskunft
MAX_ZEICHEN = 900    # laenger ist der halbe Vertrag, nicht mehr die Antwort
MAX_JE_LEAD = 12     # der Rest steht im Dokument; die Anzeige nennt die Gesamtzahl

# „Frage 3:" / „Frage:" / „Frage Nr. 3" / „Zu Frage 3:" — jeweils am Zeilenanfang.
MARKE = re.compile(
    r"(?:^|\n)[^\S\n]*(?:frage\s*(?:nr\.?\s*)?(?:\d{1,3})?\s*[:.\)]|zu\s+frage\s*\d{1,3}\s*[:.]?)",
    re.I)
EINLEITUNG = re.compile(r"^(im folgenden|nachfolgend|anbei|hiermit|nachstehend)\b", re.I)


def _kurz(pfad: str) -> str:
    """⚠ Kommt aus fremden Unterlagen — wer es rendert, escaped es."""
    return str(pfad or "").replace("\\", "/").split("/")[-1].split("::")[-1].strip()[:80]


def _abschnitte(text: str) -> list[str]:
    s = str(text or "")
    treffer = list(MARKE.finditer(s))
    raus = []
    for i, m in enumerate(treffer):
        ende = treffer[i + 1].start() if i + 1 < len(treffer) else min(len(s), m.end() + MAX_ZEICHEN)
        stueck = " ".join(s[m.end():ende].split())
        if MIND_ZEICHEN <= len(stueck) <= MAX_ZEICHEN and not EINLEITUNG.match(stueck):
            raus.append(stueck)
    return raus


def _laender() -> list[str]:
    docs = ROOT / "data" / "docs"
    gold = ROOT / "data" / "gold"
    return sorted(p.name for p in docs.iterdir()
                  if p.is_dir() and (p / "doc_text.parquet").exists()
                  and (gold / p.name / "doc_qa_stand.parquet").exists()) if docs.exists() else []


def main() -> int:
    con = duckdb.connect()
    raus: dict[str, dict] = {}
    for land in _laender():
        T = (ROOT / "data" / "docs" / land / "doc_text.parquet").as_posix()
        Q = (ROOT / "data" / "gold" / land / "doc_qa_stand.parquet").as_posix()
        zeilen = con.execute(f"""
            select t.notice_id, t.file, t.text
            from read_parquet('{T}') t
            join read_parquet('{Q}') q on q.notice_id = t.notice_id
            where t.status = 'ok'""").fetchall()
        # ⚠ Entdublierung ueber den TEXT: derselbe Katalog liegt unter mehreren Staenden im
        # Paket, und die Dateinamen unterscheiden sich, obwohl der Inhalt gleich ist.
        gesehen: dict[str, dict[str, str]] = {}
        for nid, datei, text in zeilen:
            for stueck in _abschnitte(text):
                gesehen.setdefault(str(nid), {}).setdefault(stueck, _kurz(datei))
        for nid, treffer in gesehen.items():
            dateien = sorted(set(treffer.values()))
            raus[nid] = {
                "n": len(treffer), "dateien": dateien[:4],
                "nDateien": len(dateien),
                "auszug": [{"text": t, "datei": d} for t, d in list(treffer.items())[:MAX_JE_LEAD]],
            }
        print(f"  {land}: {len(gesehen):,} Vorgaenge mit lesbaren Abschnitten · "
              f"{sum(len(v) for v in gesehen.values()):,} Abschnitte")

    if not raus:
        print("FEHLT: keine Datengrundlage — erst `doc_qa_stand` bauen lassen.")
        return 1
    OUT.write_text(json.dumps(raus, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Bieterfragen → {OUT.name} ({OUT.stat().st_size / 1024:.0f} kB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
