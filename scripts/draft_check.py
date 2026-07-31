#!/usr/bin/env python3
"""Ticket #23 §B.2 — Entwurf einer Vergabestelle → Nachweisdichte (JSON auf stdout).

Der Ausschreibungscheck (/api/draft-check) reicht die hochgeladene Entwurfsdatei hierher.
Volltext extrahieren (docpipe), distinkte Nachweis-Arten zählen (docsignals.nachweis_count).
Der Entwurf wird NICHT gespeichert — der Aufrufer verwirft die Datei nach der Prüfung.

Aufruf: python3 scripts/draft_check.py <dateipfad>
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor import docpipe, docsignals  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "dateipfad fehlt"})); return 0
    p = Path(sys.argv[1])
    if not p.exists():
        print(json.dumps({"error": "datei fehlt"})); return 0
    parts, nfiles = [], 0
    data = p.read_bytes()
    ext = p.suffix.lower()
    if ext == ".zip":
        for name, e, blob in docpipe.iter_docs(data):
            fn = docpipe._EXTRACT.get(e)
            try:
                t = (fn(blob) if fn else "") or ""
            except Exception:
                t = ""
            if t.strip():
                parts.append(t); nfiles += 1
    else:
        fn = docpipe._EXTRACT.get(ext)
        try:
            t = (fn(data) if fn else "") or ""
        except Exception:
            t = ""
        if t.strip():
            parts.append(t); nfiles = 1
    full = "\n".join(parts)
    if not full.strip():
        print(json.dumps({"error": "kein verwertbarer Text"})); return 0
    print(json.dumps({"nachweis_count": docsignals.nachweis_count(full), "files": nfiles,
                      "chars": len(full)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
