#!/usr/bin/env python3
"""Strukturierte Anforderungs-Signale aus den Vergabeunterlagen → web/data/doc-signals.json.

Quelle: data/docs/<country>/doc_signals.parquet (aus `signals-docs`), je notice_id ein Satz:
guarantee_required, binding_days, eligibility_count, certificates (komma-sep), variants_allowed,
framework, award_weights (JSON). Ausgabe pro notice_id ein kompaktes Objekt für die Detail-
Anzeige (Anforderungs-Check aus den Unterlagen). Leichter Pfad analog doc-text.json — die
/api/lead-detail hängt es je Lead an, kein Voll-Reexport nötig.

Aufruf: python3 scripts/export_doc_signals.py
"""
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "docs" / "DE" / "doc_signals.parquet"
OUT = ROOT / "web" / "data" / "doc-signals.json"


def main() -> int:
    if not SRC.exists():
        print(f"FEHLT: {SRC} — erst `signals-docs` laufen lassen.")
        return 1
    con = duckdb.connect()
    rows = con.execute(
        f"""SELECT notice_id, guarantee_required, binding_days, eligibility_count,
                   certificates, variants_allowed, framework, award_weights
            FROM read_parquet('{SRC.as_posix()}')"""
    ).fetchall()

    out = {}
    for nid, guar, binding, elig, certs, variants, framework, weights in rows:
        w = None
        if weights:
            try:
                w = json.loads(weights)
            except (json.JSONDecodeError, TypeError):
                w = None
        obj = {
            "guarantee": guar,                                        # bool | None
            "bindingDays": binding,                                   # int | None
            "eligibility": elig,                                      # int | None
            "certificates": [c.strip() for c in certs.split(",")] if certs else [],
            "variants": variants,                                     # bool | None
            "framework": framework,                                   # bool | None
            "weights": w,                                             # {kriterium: prozent} | None
        }
        # Nur Vorgänge mit mindestens EINEM belegten Signal aufnehmen.
        if any(v not in (None, [], {}) for v in obj.values()):
            out[nid] = obj

    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    covered = {k: sum(1 for v in out.values() if v.get(k) not in (None, [], {}))
               for k in ("guarantee", "bindingDays", "eligibility", "certificates", "variants", "framework", "weights")}
    print(f"Doc-Signale: {len(out)} Vorgänge → {OUT.name}")
    print("  Belegung:", ", ".join(f"{k}={n}" for k, n in covered.items() if n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
