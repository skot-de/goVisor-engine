#!/usr/bin/env python3
"""Eine hochgeladene Vergabeunterlage → §5-Prüfkette → Pipeline → Ergebnis je notice_id.

Verarbeitet NUR den einen ``notice_id`` (kein Korpus-Rebuild): Dateien in
``data/docs/DE/<notice_id>/`` → Sicherheitsprüfungen (§5, in Reihenfolge) → Volltext (docpipe)
→ Parser-Schiene (docparse) + typisierte LLM-Extraktion (analyze_docs) → Signale (docsignals).
Aktualisiert web/data/{doc-text,doc-signals,doc-analysis}.json und gibt die Detail-Felder
(lbText/lbSignals/lbAnalyse) als JSON auf stdout aus.

Aufruf:  python3 scripts/process_upload.py <notice_id>
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from govisor import docpipe, docsignals, docparse, docupload   # noqa: E402
import analyze_docs as ad                                       # noqa: E402  (analyze_notice + LLM/Multi-Key)

DATA = ROOT / "web" / "data"
CAP_TEXT = 60_000


def collect(nid: str) -> list[tuple[str, str, bytes]]:
    """Alle Dateien des Vorgangs als (name, ext, bytes) — ZIPs entpackt (docpipe, nested-safe)."""
    d = ROOT / "data" / "docs" / "DE" / nid
    out = []
    if not d.exists():
        return out
    for f in sorted(d.glob("*")):
        if not f.is_file():
            continue
        if f.suffix.lower() == ".zip":
            for name, ext, data in docpipe.iter_docs(f.read_bytes()):
                out.append((name, ext, data))
        else:
            out.append((f.name, f.suffix.lower(), f.read_bytes()))
    return out


def _load(name: str) -> dict:
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save(name: str, obj: dict) -> None:
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _err(msg: str) -> int:
    print(json.dumps({"error": msg}, ensure_ascii=False))
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "notice_id fehlt"})); return 1
    nid = sys.argv[1]
    raw = collect(nid)
    if not raw:
        return _err("keine Dateien im Vorgangs-Ordner")

    # ── §5 Prüfkette (Reihenfolge einhalten) ──────────────────────────────────────────────
    # 1 Malware
    for name, ext, data in raw:
        if not docupload.scan_malware(name, data):
            return _err(f"Malware erkannt ({name}) — Paket verworfen")
    # 2 Pfadprüfung (Zip-Slip)
    slip = [n for n, _, _ in raw if docupload.is_zip_slip(n)]
    if slip:
        return _err(f"unsichere Pfade im Paket ({slip[0]}) — abgebrochen")
    # Grenzwerte (§4.2)
    total = sum(len(d) for _, _, d in raw)
    viol = docupload.check_limits(total, len(raw))
    if viol:
        return _err(f"Grenzwert überschritten: {', '.join(viol)}")

    # Volltext je Datei extrahieren
    texts = {}
    for name, ext, data in raw:
        fn = docpipe._EXTRACT.get(ext)
        try:
            texts[name] = (fn(data) if fn else "") or ""
        except Exception:
            texts[name] = ""
    fulltext = "\n\n".join(t for t in texts.values() if t.strip())
    if not fulltext.strip():
        return _err("kein verwertbarer Text — evtl. nur gescannte Bild-PDFs oder unbekannte Dateien")

    # 3 Eigenes Angebot
    if docupload.detect_own_offer(fulltext):
        return _err("Das sieht nach einem eigenen Angebot aus. Für die Bibliothek nutze bitte den "
                    "Import unter Profil.")
    # 4 Lead-Zuordnung (§5-4): kommt der Käufer des Leads in den Unterlagen vor? Heuristik →
    # Rückfrage (kein stiller Durchlauf), kein harter Abbruch (Käufernamen weichen oft ab).
    lead_buyer = sys.argv[2] if len(sys.argv) > 2 else ""
    lead_mismatch = None
    if lead_buyer:
        import re
        stop = {"gmbh", "stadt", "der", "die", "und", "des", "fuer", "amt", "eigenbetrieb", "aoer"}
        toks = {t for t in re.findall(r"[a-zäöüß]{4,}", lead_buyer.lower()) if t not in stop}
        low = fulltext.lower()
        hit = sum(1 for t in toks if t in low)
        if toks and hit / len(toks) < 0.34:            # weniger als ein Drittel der Käufer-Wörter im Text
            lead_mismatch = {"expected_buyer": lead_buyer}
    # 5 Doppelung: Paket-Hash (Dedup/Herkunft §5-5, §12.2)
    package_hash = docupload.package_hash([(n, d) for n, _, d in raw])

    # ── Pipeline ──────────────────────────────────────────────────────────────────────────
    nfiles = sum(1 for t in texts.values() if t.strip())
    # EINE DATEI JE VORGANG, wie `scripts/export_doc_text.py`. Die frueher hier gepflegte
    # Sammeldatei `doc-text.json` gibt es nicht mehr (zuletzt 294 MB); sie weiterzuschreiben
    # hiesse, sie fuer JEDEN Upload komplett zu lesen und komplett zurueckzuschreiben.
    eintrag = {"chars": len(fulltext), "files": nfiles, "text": fulltext[:CAP_TEXT],
               "truncated": len(fulltext) > CAP_TEXT}
    dt = {nid: eintrag}
    sicher = "".join(c for c in nid if c.isalnum() or c in "-_")
    (DATA / "doc-text").mkdir(parents=True, exist_ok=True)
    (DATA / "doc-text" / f"{sicher}.json").write_text(
        json.dumps(eintrag, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    res = {"lbText": dt[nid]["text"], "lbFiles": nfiles, "lbChars": len(fulltext),
           "lbTruncated": dt[nid]["truncated"], "packageHash": package_hash}
    if lead_mismatch:
        res["leadMismatch"] = lead_mismatch          # §5-4: Käufer nicht in den Unterlagen → Rückfrage

    # Regelbasierte Signale
    sig = docsignals.extract_signals(fulltext)
    obj = {"guarantee": sig.get("guarantee_required"), "bindingDays": sig.get("binding_days"),
           "eligibility": sig.get("eligibility_count"), "certificates": sig.get("certificates") or [],
           "variants": sig.get("variants_allowed"), "framework": sig.get("framework"),
           "weights": sig.get("award_weights")}
    if any(v not in (None, [], {}) for v in obj.values()):
        ds = _load("doc-signals.json"); ds[nid] = obj; _save("doc-signals.json", ds)
        res["lbSignals"] = obj

    # Typisierte Analyse: Parser-Schiene + priorisierte LLM-Extraktion (§6)
    structured = {n: r for n, e, d in raw if (r := docparse.parse(n, e, d))}
    files = [(n, texts.get(n, "")) for n, _, _ in raw]
    an = ad.analyze_notice(files, structured=structured)
    if an:
        da = _load("doc-analysis.json"); da[nid] = an; _save("doc-analysis.json", da)
        res["lbAnalyse"] = an

    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
