#!/usr/bin/env python3
"""LB-Volltext je Vorgang → web/data/doc-text.json für die Lead-Detail-Anzeige.

Quelle: data/docs/<country>/doc_text.parquet (aus `index-docs`). Ein Vorgang (notice_id) hat
mehrere Dateien; hier je notice_id zusammengefügt (status='ok' und 'ocr'), mit Dateiüberschriften.
Ausgabe: {notice_id: {chars, files, text}}. Pro Vorgang auf CAP Zeichen gekürzt (Payload zähmen —
für den Volltext-Download gibt es später die echte Datei/Objektspeicher).

Aufruf: python3 scripts/export_doc_text.py
"""
import json
import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "docs" / "DE" / "doc_text.parquet"
# Eine Datei je Vorgang — der einzige Weg, auf dem der Volltext ausgeliefert wird.
JE_VORGANG = ROOT / "web" / "data" / "doc-text"
# Verzeichnis OHNE Text: wer da ist, wie viele Zeichen, aus wie vielen Dateien. Rund 200 KB
# statt 294 MB. Es beantwortet alle Fragen, die nicht den Text selbst brauchen (Trichter im
# Lauf-Monitor, `scripts/dokumente_stand.py`).
INDEX = ROOT / "web" / "data" / "doc-text-index.json"
# Der alte Sammelblock. Wird nur noch geloescht, nie geschrieben.
ALT = ROOT / "web" / "data" / "doc-text.json"
CAP = 60_000  # Zeichen je Vorgang im JSON

_WS = re.compile(r"[ \t]+")
_NL = re.compile(r"\n{3,}")


def clean(t: str) -> str:
    t = t.replace("\x00", " ").replace("\r", "\n")
    t = _WS.sub(" ", t)
    t = _NL.sub("\n\n", t)
    return t.strip()


def main() -> int:
    if not SRC.exists():
        print(f"FEHLT: {SRC} — erst `index-docs` laufen lassen.")
        return 1
    con = duckdb.connect()
    rows = con.execute(
        f"""SELECT notice_id, file, filetype, text
            FROM read_parquet('{SRC.as_posix()}')
            -- `ocr` wie `ok` — s. govisor/docpipe.py: der Zustand entsteht nur, wenn die
            -- Texterkennung Fachvokabular fand (>= 3 Begriffe der Vergabesprache).
            -- Gemessen 2026-08-18: 404 Vorgaenge bekommen dadurch zusaetzlichen Text,
            -- 3,23 Mio. Zeichen. KEIN Vorgang haengt allein daran — wer nur OCR-Text hat,
            -- existiert nicht (0 von 404). Es ist Tiefe, nicht Abdeckung.
            WHERE status IN ('ok','ocr') AND text IS NOT NULL AND length(text) > 0
            ORDER BY notice_id, file"""
    ).fetchall()

    docs: dict[str, dict] = {}
    for nid, file, ftype, text in rows:
        d = docs.setdefault(nid, {"files": [], "parts": []})
        d["files"].append(file)
        d["parts"].append(f"── {file} ──\n{clean(text)}")

    out = {}
    for nid, d in docs.items():
        full = "\n\n".join(d["parts"])
        out[nid] = {
            "chars": len(full),
            "files": len(d["files"]),
            "text": full[:CAP],
            "truncated": len(full) > CAP,
        }

    # ── EINE DATEI JE VORGANG ────────────────────────────────────────────────────────
    # Der Sammelblock `doc-text.json` war am 2026-08-18 auf 294 MB gewachsen. Lokal ist das
    # ein Lesevorgang von der Platte; in der Cloud laedt `app/api/lead-detail/route.ts` die
    # GANZE Datei ueber das Netz und haelt sie im Speicher — je Serverless-Instanz, bei jedem
    # Kaltstart, fuer EINEN angefragten Vorgang. Aufgeteilt sind es ein paar Kilobyte.
    #
    # Der Sammelblock bleibt trotzdem stehen: `scripts/dokumente_stand.py` und der
    # Lauf-Monitor zaehlen darueber, und die Route faellt auf ihn zurueck, wenn eine
    # Einzeldatei fehlt. Verschwinden soll er erst, wenn ihn nichts mehr liest.
    JE_VORGANG.mkdir(parents=True, exist_ok=True)
    vorhanden = {f.stem for f in JE_VORGANG.glob("*.json")}
    geschrieben = 0
    for nid, v in out.items():
        # Der Dateiname wird zum URL-Pfad. Alles, was dort nichts zu suchen hat, faellt weg —
        # ein `../` in einer notice_id waere sonst ein Pfadwechsel beim Ausliefern.
        sicher = "".join(c for c in nid if c.isalnum() or c in "-_")
        if not sicher:
            continue
        ziel = JE_VORGANG / f"{sicher}.json"
        neu_inhalt = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        if ziel.exists() and ziel.read_text(encoding="utf-8") == neu_inhalt:
            vorhanden.discard(sicher)
            continue
        ziel.write_text(neu_inhalt, encoding="utf-8")
        vorhanden.discard(sicher)
        geschrieben += 1
    # Was der Lauf nicht mehr kennt, fliegt raus: eine alte Einzeldatei wuerde sonst ewig
    # weiter ausgeliefert, obwohl der Vorgang laengst aus dem Bestand ist.
    for verwaist in vorhanden:
        (JE_VORGANG / f"{verwaist}.json").unlink(missing_ok=True)

    # ⚠ KEIN SAMMELBLOCK MEHR. `doc-text.json` lag zuletzt bei 294 MB und stand neben den
    # Einzeldateien — dieselbe Menge zweimal, jede Nacht neu hochzuladen. Wer zaehlen will,
    # nimmt den Index; wer Text will, die Einzeldatei. Die alte Datei wird aktiv entfernt,
    # damit nicht irgendwo ein Monat alter Stand weiterlebt und wie aktuell aussieht.
    ALT.unlink(missing_ok=True)
    INDEX.write_text(json.dumps(
        {nid: {"chars": v["chars"], "files": v["files"], "truncated": v["truncated"]}
         for nid, v in out.items()}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"LB-Volltext: {len(out)} Vorgänge "
          f"({sum(v['chars'] for v in out.values()):,} Zeichen gesamt)")
    print(f"  je Vorgang: {geschrieben:,} geschrieben, {len(vorhanden):,} verwaiste entfernt "
          f"→ {JE_VORGANG.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
