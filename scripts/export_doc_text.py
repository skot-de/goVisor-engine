#!/usr/bin/env python3
"""LB-Volltext je Vorgang → web/data/doc-text.json für die Lead-Detail-Anzeige.

Quelle: data/docs/<country>/doc_text.parquet (aus `index-docs`). Ein Vorgang (notice_id) hat
mehrere Dateien; hier je notice_id zusammengefügt (nur status='ok'), mit Dateiüberschriften.
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
OUT = ROOT / "web" / "data" / "doc-text.json"
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
            WHERE status='ok' AND text IS NOT NULL AND length(text) > 0
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

    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"LB-Volltext: {len(out)} Vorgänge → {OUT.name} "
          f"({sum(v['chars'] for v in out.values()):,} Zeichen gesamt)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
