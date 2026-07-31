#!/usr/bin/env python3
"""Eine hochgeladene Vergabeunterlage → durch die Pipeline → Ergebnis je notice_id.

Verarbeitet NUR den einen ``notice_id`` (kein Korpus-Rebuild): Dateien in
``data/docs/DE/<notice_id>/`` → Volltext (docpipe) → Signale (docsignals) → LLM-Analyse
(analyze_docs). Aktualisiert web/data/{doc-text,doc-signals,doc-analysis}.json für diesen
Vorgang und gibt die Detail-Felder (lbText/lbSignals/lbAnalyse) als JSON auf stdout aus.

Aufruf:  python3 scripts/process_upload.py <notice_id>
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from govisor import docpipe, docsignals          # noqa: E402
from analyze_docs import analyze as llm_analyze   # noqa: E402  (LLM + Multi-Key)

DATA = ROOT / "web" / "data"
CAP_TEXT = 60_000


def extract_notice(nid: str) -> tuple[str, int]:
    """Alle Dateien im Vorgangs-Ordner → zusammengefügter Volltext + Dateizahl."""
    d = ROOT / "data" / "docs" / "DE" / nid
    parts: list[str] = []
    n = 0
    if not d.exists():
        return "", 0
    for f in sorted(d.glob("*")):
        if not f.is_file():
            continue
        if f.suffix.lower() == ".zip":
            for row in docpipe.process_zip(f):
                if row["status"] == "ok" and (row["text"] or "").strip():
                    parts.append(f"── {row['file']} ──\n{row['text']}")
                    n += 1
        else:
            fn = docpipe._EXTRACT.get(f.suffix.lower())
            if fn:
                try:
                    text = fn(f.read_bytes()) or ""
                except Exception:
                    text = ""
                if text.strip():
                    parts.append(f"── {f.name} ──\n{text}")
                    n += 1
    return "\n\n".join(parts), n


def _load(name: str) -> dict:
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save(name: str, obj: dict) -> None:
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "notice_id fehlt"})); return 1
    nid = sys.argv[1]

    full, nfiles = extract_notice(nid)
    if not full.strip():
        print(json.dumps({"error": "kein verwertbarer Text — evtl. nur gescannte Bild-PDFs oder leere/unbekannte Dateien"}))
        return 0

    # 1) Volltext
    dt = _load("doc-text.json")
    dt[nid] = {"chars": len(full), "files": nfiles, "text": full[:CAP_TEXT], "truncated": len(full) > CAP_TEXT}
    _save("doc-text.json", dt)
    res = {"lbText": dt[nid]["text"], "lbFiles": nfiles, "lbChars": len(full), "lbTruncated": dt[nid]["truncated"]}

    # 2) Regelbasierte Signale
    sig = docsignals.extract_signals(full)
    obj = {"guarantee": sig.get("guarantee_required"), "bindingDays": sig.get("binding_days"),
           "eligibility": sig.get("eligibility_count"), "certificates": sig.get("certificates") or [],
           "variants": sig.get("variants_allowed"), "framework": sig.get("framework"),
           "weights": sig.get("award_weights")}
    if any(v not in (None, [], {}) for v in obj.values()):
        ds = _load("doc-signals.json"); ds[nid] = obj; _save("doc-signals.json", ds)
        res["lbSignals"] = obj

    # 3) LLM-Vergabe-Analyse (Ampel + Checkliste)
    an = llm_analyze(full)
    if an:
        da = _load("doc-analysis.json"); da[nid] = an; _save("doc-analysis.json", da)
        res["lbAnalyse"] = an

    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
