#!/usr/bin/env python3
"""Vergabe-Analyse (Ticket #23) — typisierte, belegpflichtige Extraktion je Dokumenttyp.

Input:  data/docs/<country>/doc_text.parquet (aus `index-docs`).
Output: web/data/doc-analysis.json {notice_id: {ampel, zusammenfassung, checklist[],
        rejected_items, token_cost, doctypes_seen[], missing_expected[], + rückwärts-
        kompatible ko_kriterien/eignung/zuschlag/fristen/aufwand/vorausfuellbar}}.

Kern (§6a): kein Universal-Prompt mehr — je Dokumenttyp eine eigene Aufgabe mit Schema
(``govisor.docextract``), plus **Zitat-Verifikation** (jede Aussage wird im Quelltext
gegengeprüft, unbelegte verworfen). Dazu ein leichter Ampel-/Zusammenfassungs-Call fürs UI.

Key: $OPENROUTER_KEY_FILE (default .secrets/openrouter.key). Aufruf:
  python3 scripts/analyze_docs.py            # alle Vorgänge ohne Analyse
  LIMIT=3 python3 scripts/analyze_docs.py    # nur 3 (Test)
"""
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor.llm import chat, AllKeysExhausted  # noqa: E402  (Multi-Key-Fallback)
from govisor import doctypes, docextract, docparse, doctax, docpipe  # noqa: E402

SRC = ROOT / "data" / "docs" / "DE" / "doc_text.parquet"
OUT = ROOT / "web" / "data" / "doc-analysis.json"
MODEL = os.environ.get("OR_MODEL", "google/gemini-2.5-flash")
LIMIT = int(os.environ.get("LIMIT", "0"))
TOKEN_CAP = 200_000                # §6.1 Deckel für die priorisierte Extraktion
CHARS_PER_TOKEN = 4                # grobe Umrechnung Zeichen→Tokens

# K.-o.-relevante req_types (für die rückwärtskompatible ko_kriterien-Projektion, §7).
_KO = {"mindestumsatz", "referenz_anzahl", "referenz_mindestwert", "zertifikat",
       "ausschlussgrund", "eignung_technisch", "eignung_personal", "berufshaftpflicht"}
_AUFWAND = {"vertragsstrafe", "berufshaftpflicht", "haftung", "referenz_mindestwert"}

_SUMMARY_SYS = (
    "Du bist Vergabe-Analyst und liest die Vergabeunterlagen einer öffentlichen Ausschreibung "
    "(DE/CH). Antworte NUR als JSON: "
    '{"ampel":"gruen|gelb|rot","ampel_grund":"kurzer Satz","zusammenfassung":"1-2 Sätze: was wird beschafft"}. '
    "Ampel: gruen = klar bietbar; gelb = machbar, spürbarer Aufwand; rot = harte Hürde/K.o.-Risiko."
)


def summarize(text: str) -> dict:
    txt = chat([{"role": "system", "content": _SUMMARY_SYS},
                {"role": "user", "content": text[:28_000]}], model=MODEL)
    txt = re.sub(r"^```json|^```|```$", "", txt.strip(), flags=re.M).strip()
    try:
        d = json.loads(txt)
        return {"ampel": d.get("ampel", "gelb"), "ampel_grund": d.get("ampel_grund", ""),
                "zusammenfassung": d.get("zusammenfassung", "")}
    except json.JSONDecodeError:
        return {"ampel": "gelb", "ampel_grund": "", "zusammenfassung": ""}


def _derive_legacy(checklist: list) -> dict:
    """Rückwärtskompatible Felder fürs bestehende Frontend aus der typisierten Checkliste (§7)."""
    ko, eig, zus, fri, auf = [], [], [], [], []
    for it in checklist:
        rt, label, val, unit = it["req_type"], it["label"], it.get("value"), it.get("unit")
        disp = f"{label}: {val}" if val else label
        if rt in _KO:
            ko.append(disp)
        if rt in ("zertifikat", "einzureichendes_dokument", "eignung_technisch", "eignung_personal"):
            eig.append({"nachweis": val or label, "kategorie": it.get("theme", "")})
        if rt == "zuschlagskriterium":
            zus.append({"kriterium": val or label, "gewicht": unit or ""})
        if rt == "frist":
            fri.append({"typ": label, "wert": val or ""})
        if rt in _AUFWAND:
            auf.append(disp)
    return {"ko_kriterien": ko, "eignung": eig, "zuschlag": zus, "fristen": fri,
            "aufwand": auf, "vorausfuellbar": []}


def _parser_item(name: str, s: dict) -> dict | None:
    """Kompaktes Checklisten-Item aus einem Parser-Ergebnis (§6.2) — ohne LLM, kein Zitat nötig
    (deterministischer Parser, nicht LLM-Behauptung → nicht zitat-verifiziert)."""
    p = s.get("parser")
    if p == "gaeb":
        rt, lbl, val, unit = ("leistung_menge", f"Leistungsverzeichnis (GAEB, {s['n_positions']} Positionen)",
                              s["n_positions"], "Positionen")
    elif p == "xlsx":
        pos = sum(sh["n_positions"] for sh in s["sheets"])
        rt, lbl, val, unit = "leistung_menge", f"Preisblatt/Tabelle ({pos} Positionen)", pos, "Positionen"
    elif p == "pdf_fields":
        req = sum(1 for f in s["fields"] if f["required"])
        rt, lbl, val, unit = ("einzureichendes_dokument",
                              f"Ausfüllbares Formular ({s['n_fields']} Felder, {req} Pflicht)",
                              s["n_fields"], "Felder")
    else:
        return None
    return {"req_type": rt, "label": lbl, "theme": doctax.theme_for(rt), "value": val, "unit": unit,
            "quote": "", "source_file": name, "source_page": None, "marking": "Extrahiert", "parser": p}


def analyze_notice(files: list, structured: dict | None = None) -> dict:
    """files = [(filename, text), …] eines Vorgangs → Analyse mit verifizierter Checkliste.

    Zwei Schienen: **Parser** (§6.2, structured={name: parser_result}) liefert strukturierte
    Fakten ohne LLM; die restlichen Text-Dateien gehen **priorisiert** ans LLM (§6.1), je
    Prioritäts-Doktyp EIN Call, bis der 200k-Token-Deckel greift.
    """
    structured = structured or {}
    by_type_text = defaultdict(list)
    by_type_file = {}
    checklist, positions, parsed_files = [], [], []
    for name, text in files:
        s = structured.get(name)
        if s:                                          # Parser griff → kein LLM (§6.2)
            item = _parser_item(name, s)
            if item:
                checklist.append(item)
            positions.append({"file": name, **s})
            parsed_files.append(name)
        else:
            dt = doctypes.classify(name)
            if dt == "sonstiges":                      # Dateiname unklar → Inhaltsprobe (§6.1, Schritt 2)
                dt = docparse.classify_content(text or "")
            by_type_text[dt].append(text or "")
            by_type_file.setdefault(dt, name)

    rejected, sent_chars, truncated = 0, 0, []
    llm_started = False
    for dt in doctypes.PRIORITY:
        if dt not in by_type_text:
            continue
        blob = "\n\n".join(by_type_text[dt]).strip()
        if not blob:
            continue
        if sent_chars + len(blob) > TOKEN_CAP * CHARS_PER_TOKEN and llm_started:
            truncated.append(dt)                       # Deckel: nach Priorität abschneiden (§6.1)
            continue
        sent_chars += min(len(blob), 60_000)
        llm_started = True
        res = docextract.extract(dt, blob, by_type_file[dt], model=MODEL)
        checklist.extend(res.get("items", []))
        rejected += res.get("rejected", 0)

    seen = sorted(set(by_type_text) | {doctypes.classify(n) for n in parsed_files})
    summary = summarize("\n\n".join(t for _, t in files))
    missing = [dt for dt in doctypes.PRIORITY if dt not in seen]      # Q1a-Vollständigkeit (§4.3)
    out = {
        **summary,
        "checklist": checklist,
        "positions": positions,
        "parsed_files": parsed_files,
        "rejected_items": rejected,
        "token_cost": round(sent_chars / CHARS_PER_TOKEN),
        "doctypes_seen": seen,
        "missing_expected": missing,
        "truncated_doctypes": truncated,
    }
    out.update(_derive_legacy(checklist))
    return out


def structured_for_notice(notice_id: str, docs_root: Path = None) -> dict:
    """Parser-Schiene über die Roh-ZIPs eines Vorgangs → {dateiname: parser_result} (§6.2).

    Braucht die Original-Bytes (die im doc_text.parquet nicht liegen), liest daher die ZIPs
    aus data/docs/<country>/<notice_id>/ neu. Fehlende Verzeichnisse → leeres dict.
    """
    import glob
    root = docs_root or (SRC.parent)
    ndir = root / notice_id
    out = {}
    if not ndir.exists():
        return out
    for z in glob.glob(str(ndir / "*.zip")):
        try:
            blob = Path(z).read_bytes()
        except OSError:
            continue
        for name, ext, data in docpipe.iter_docs(blob):
            if name in out:
                continue
            try:
                r = docparse.parse(name, ext, data)
            except Exception:
                r = None
            if r:
                out[name] = r
    return out


def main() -> int:
    if not SRC.exists():
        print(f"FEHLT: {SRC} — erst `index-docs` laufen lassen.")
        return 1
    con = duckdb.connect()
    rows = con.execute(
        f"""SELECT notice_id, file, text FROM read_parquet('{SRC.as_posix()}')
            WHERE status='ok' AND text IS NOT NULL AND length(text) > 120
            ORDER BY notice_id"""
    ).fetchall()
    per_notice = defaultdict(list)
    for nid, file, text in rows:
        per_notice[nid].append((file, text))

    out = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    todo = [(nid, files) for nid, files in per_notice.items() if nid not in out]
    if LIMIT:
        todo = todo[:LIMIT]
    print(f"Zu analysieren: {len(todo)} (von {len(per_notice)}) · Modell {MODEL}", flush=True)

    for i, (nid, files) in enumerate(todo, 1):
        try:
            structured = structured_for_notice(nid)        # Parser-Schiene (§6.2) über die Roh-ZIPs
            res = analyze_notice(files, structured=structured)
        except AllKeysExhausted as e:
            print(f"  Abbruch: {e} — bisher {len(out)} Analysen gesichert.", flush=True)
            break
        out[nid] = res
        print(f"  [{i}/{len(todo)}] {nid}  {res['ampel']}  items={len(res['checklist'])} "
              f"({len(res['parsed_files'])} geparst) verworfen={res['rejected_items']} "
              f"~{res['token_cost']}tok", flush=True)
        OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"Vergabe-Analysen: {len(out)} Vorgänge → {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
