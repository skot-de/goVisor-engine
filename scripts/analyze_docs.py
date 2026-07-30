#!/usr/bin/env python3
"""Vergabe-Analyse: LLM über den Unterlagen-Volltext → Ampel + Bieter-Checkliste je Vorgang.

Input:  data/docs/<country>/doc_text.parquet (aus `index-docs`).
Output: web/data/doc-analysis.json {notice_id: {ampel, zusammenfassung, ko_kriterien,
        eignung[], zuschlag[], fristen[], aufwand[], vorausfuellbar[]}}.

Der Nutzen für den Nutzer: aus 80 Seiten PDF in Sekunden eine Bieter-Entscheidung — K.o.
zuerst, Eignung als abhakbare Liste, Zuschlagsgewichte, Fristen, plus was wir aus seinem
Profil vorausfüllen könnten. Das ist der Grund, die Unterlagen zu hinterlegen.

Key: $OPENROUTER_KEY_FILE (default .secrets/openrouter.key). Aufruf:
  python3 scripts/analyze_docs.py            # alle Vorgänge ohne Analyse
  LIMIT=3 python3 scripts/analyze_docs.py    # nur 3 (Test)
"""
import json
import os
import re
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor.llm import chat, AllKeysExhausted  # noqa: E402  (Multi-Key-Fallback)

SRC = ROOT / "data" / "docs" / "DE" / "doc_text.parquet"
OUT = ROOT / "web" / "data" / "doc-analysis.json"
MODEL = os.environ.get("OR_MODEL", "google/gemini-2.5-flash")
CAP = 28_000  # Zeichen Volltext je Vorgang an das LLM
LIMIT = int(os.environ.get("LIMIT", "0"))

SYS = (
    "Du bist Vergabe-Analyst und liest die Vergabeunterlagen einer öffentlichen Ausschreibung (DE/CH). "
    "Extrahiere NUR, was belegbar im Text steht — nichts erfinden. Antworte ausschließlich als JSON:\n"
    "{"
    '"ampel":"gruen|gelb|rot",'
    '"ampel_grund":"ein kurzer Satz, warum",'
    '"zusammenfassung":"1-2 Sätze: was wird beschafft",'
    '"ko_kriterien":["harte Ausschluss-/Mindestkriterien, z.B. Mindestumsatz, Pflicht-Zertifikat, Mindest-Referenzen"],'
    '"eignung":[{"nachweis":"geforderter Nachweis/Unterlage","kategorie":"rechtlich|wirtschaftlich|technisch"}],'
    '"zuschlag":[{"kriterium":"z.B. Preis","gewicht":40}],'
    '"fristen":[{"typ":"Angebotsfrist|Fragefrist|Bindefrist|...","wert":"Datum oder Angabe"}],'
    '"aufwand":["Aufwandstreiber, z.B. Bürgschaft, Präsentationstermin, Vor-Ort-Begehung, Musterlösung"],'
    '"vorausfuellbar":["Angaben, die sich aus einem Firmenprofil automatisch vorausfüllen ließen, z.B. Eigenerklärung, Referenzliste, Firmenstammdaten"]'
    "}\n"
    "Ampel: gruen = klar bietbar, überschaubarer Aufwand; gelb = machbar, aber spürbarer Aufwand/"
    "prüfen; rot = harte Hürde/K.o.-Risiko oder sehr hoher Aufwand. Leere Felder als [] bzw. \"\"."
)


def analyze(text: str) -> dict | None:
    # chat() rotiert bei leerem Guthaben automatisch auf den nächsten Key (govisor.llm).
    txt = chat([{"role": "system", "content": SYS},
                {"role": "user", "content": text[:CAP]}], model=MODEL)
    txt = re.sub(r"^```json|^```|```$", "", txt.strip(), flags=re.M).strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return None


def main() -> int:
    if not SRC.exists():
        print(f"FEHLT: {SRC} — erst `index-docs` laufen lassen.")
        return 1
    con = duckdb.connect()
    rows = con.execute(
        f"""SELECT notice_id, string_agg(text, '\n\n') AS full
            FROM read_parquet('{SRC.as_posix()}')
            WHERE status='ok' AND text IS NOT NULL AND length(text) > 200
            GROUP BY notice_id ORDER BY notice_id"""
    ).fetchall()

    out = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    todo = [(nid, full) for nid, full in rows if nid not in out]
    if LIMIT:
        todo = todo[:LIMIT]
    print(f"Zu analysieren: {len(todo)} (von {len(rows)}) · Modell {MODEL}", flush=True)

    for i, (nid, full) in enumerate(todo, 1):
        try:
            res = analyze(full or "")
        except AllKeysExhausted as e:
            print(f"  Abbruch: {e} — bisher {len(out)} Analysen gesichert.", flush=True)
            break
        if res:
            out[nid] = res
            amp = res.get("ampel", "?")
            print(f"  [{i}/{len(todo)}] {nid}  {amp}  ko={len(res.get('ko_kriterien') or [])} "
                  f"eig={len(res.get('eignung') or [])}", flush=True)
        else:
            print(f"  [{i}/{len(todo)}] {nid}  — keine Analyse", flush=True)
        OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"Vergabe-Analysen: {len(out)} Vorgänge → {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
