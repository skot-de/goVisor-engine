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
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor.llm import (chat, letzter_anbieter, anbieter_stand,  # noqa: E402
                         AllKeysExhausted)
from govisor import doctypes, docextract, docparse, doctax, docpipe  # noqa: E402

SRC = ROOT / "data" / "docs" / "DE" / "doc_text.parquet"
OUT = ROOT / "web" / "data" / "doc-analysis.json"
MODEL = os.environ.get("OR_MODEL", "google/gemini-2.5-flash")
LIMIT = int(os.environ.get("LIMIT", "0"))
# PARALLELITAET. Der Lauf ist zu ueber 90 % Warten auf die Antwort des Modells; nacheinander
# gerechnet schafft er rund 200 Vorgaenge am Tag, und bei 4.394 Vorgaengen mit Volltext waeren
# das drei Wochen. Gemessen am 2026-08-18: 2 % der offenen Leads hatten eine Analyse.
#
# Die Obergrenze ist nicht die Maschine, sondern die Gegenstelle. `govisor/llm.py` faengt 429
# mit Backoff und Key-Rotation ab, deshalb ist eine hoehere Zahl hier kein Risiko fuer die
# Richtigkeit — nur fuer die Hoeflichkeit. 8 ist die Vorgabe; wer mehr will, setzt PARALLEL.
PARALLEL = max(1, int(os.environ.get("PARALLEL", "8")))
# Wie oft das Ergebnis auf die Platte geht. Nach JEDEM Vorgang zu schreiben war bei 272
# Analysen billig und waere bei 4.000 eine Datei, die dauernd komplett neu geschrieben wird.
# Alle 10 heisst: im schlimmsten Fall gehen 10 Analysen verloren, nicht 4.000.
SICHERN_JE = int(os.environ.get("SICHERN_JE", "10"))
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
    checklist, positions, parsed_files, other_docs = [], [], [], []
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
            if not doctypes.is_priority(dt):           # nicht-priorisiert → „Weitere Dokumente" (§7.5)
                other_docs.append(name)
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
        "other_documents": other_docs,
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
    # REIHENFOLGE NACH AKTUALITAET, nicht nach notice_id.
    #
    # Sven am 2026-08-18: „fang mit den neuesten ausschreibungen an und arbeite dich zu den
    # alten durch. bis ich in die erste demo gehe, sind die jetzt aktuellen ausschreibungen
    # dann schon alt. daher lass die alten, alt sein, die werten wir fuer uebungs- und
    # nachnutzungszwecke aus."
    #
    # `notice_id` ist KEINE Zeitachse: „99_2026" sortiert vor „450024_2026", obwohl es
    # spaeter erschien. Sortiert wird deshalb ueber den Lead: offene Ausschreibungen zuerst,
    # darin die mit der spaetesten Frist — das sind die, auf die man noch bieten kann und
    # die zur Demo noch aktuell sind. Was kein Lead mehr ist, kommt zuletzt.
    LE = (ROOT / "data/gold/DE/lead_export.parquet").as_posix()
    rows = con.execute(
        f"""WITH t AS (SELECT notice_id, file, text
                       FROM read_parquet('{SRC.as_posix()}')
                       -- `ocr` zaehlt wie `ok`: ein bildreines PDF, das die Texterkennung
                       -- durchlaufen hat UND den Fachvokabeltest bestand, ist inhaltlich
                       -- dasselbe wie ein durchsuchbares. Gemessen 2026-08-18: 3,23 Mio.
                       -- Zeichen in 404 Vorgaengen, die alle auch `ok`-Text haben. Der LLM
                       -- bekommt also mehr Material je Vorgang, nicht mehr Vorgaenge.
                       WHERE status IN ('ok','ocr') AND text IS NOT NULL AND length(text) > 120)
            SELECT t.notice_id, t.file, t.text
            FROM t LEFT JOIN read_parquet('{LE}') l ON l.lead_id = t.notice_id
            ORDER BY (l.phase = 'open') DESC NULLS LAST,
                     l.deadline_date DESC NULLS LAST,
                     t.notice_id DESC"""
    ).fetchall()
    per_notice = defaultdict(list)
    for nid, file, text in rows:
        per_notice[nid].append((file, text))

    out = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    todo = [(nid, files) for nid, files in per_notice.items() if nid not in out]
    if LIMIT:
        todo = todo[:LIMIT]
    print(f"Zu analysieren: {len(todo)} (von {len(per_notice)}) · Modell {MODEL} · {PARALLEL} parallel", flush=True)

    # ── PARALLEL, aber mit einem Schreiber ───────────────────────────────────────────
    # Die Arbeit je Vorgang ist unabhaengig; nur das Ergebnis-Dictionary und die Datei sind
    # gemeinsam. Deshalb rechnen N Faeden, und geschrieben wird unter einem Lock im Haupt-
    # faden, wenn ein Ergebnis eintrifft. Zwei Prozesse gleichzeitig waeren etwas anderes und
    # blieben verboten — der Arbeiter prueft das (scripts/dokumente_arbeiter.sh).
    schreib_lock = threading.Lock()
    fertig = 0
    erschoepft = False

    def arbeite(auftrag):
        nid, files = auftrag
        structured = structured_for_notice(nid)            # Parser-Schiene (§6.2) über die Roh-ZIPs
        res = analyze_notice(files, structured=structured)
        # WER HAT ES ERZEUGT. Seit dem 2026-08-18 gibt es drei Anbieter mit verschiedenen
        # Modellen; welches gerade dran ist, entscheidet das Guthaben. Ohne diese Angabe
        # stuenden im Bestand Ergebnisse nebeneinander, deren Unterschiede niemand mehr
        # erklaeren kann — und die Verwerfungsquote unterscheidet sich messbar je Modell.
        anbieter, modell = letzter_anbieter()
        res["provider"], res["model"] = anbieter, modell
        return nid, res

    def sichern():
        OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        laeuft = {pool.submit(arbeite, t): t[0] for t in todo}
        for fut in as_completed(laeuft):
            nid = laeuft[fut]
            try:
                nid, res = fut.result()
            except AllKeysExhausted as e:
                if not erschoepft:
                    erschoepft = True
                    print(f"  Abbruch: {e} — laufende Vorgaenge werden noch fertig.", flush=True)
                continue
            except Exception as ex:                        # noqa: BLE001
                # Ein kaputtes Archiv darf den Lauf nicht beenden. Gezaehlt, benannt, weiter.
                print(f"  ✖ {nid}: {type(ex).__name__}: {ex}", flush=True)
                continue
            with schreib_lock:
                out[nid] = res
                fertig += 1
                print(f"  [{fertig}/{len(todo)}] {nid}  {res['ampel']} "
                      f"items={len(res['checklist'])} ({len(res['parsed_files'])} geparst) "
                      f"verworfen={res['rejected_items']} ~{res['token_cost']}tok", flush=True)
                if fertig % SICHERN_JE == 0:
                    sichern()
    with schreib_lock:
        sichern()

    # BETRIEBSSTAND FUER DIE ANZEIGE. Am 2026-08-18 stand die Zahl „wartet auf Analyse"
    # eine Stunde lang still, weil das OpenRouter-Guthaben leer war — sichtbar war das nur
    # im Log. Sven musste fragen, warum sich nichts tut. Wer welchen Anbieter noch hat und
    # was zuletzt schiefging, gehoert deshalb dorthin, wo die Zahl steht.
    try:
        (ROOT / "data" / ".llm_stand.json").write_text(json.dumps({
            "zeit": int(time.time()),
            "fertig": fertig,
            "erschoepft": erschoepft,
            "anbieter": anbieter_stand(),
        }, ensure_ascii=False), encoding="utf-8")
    except Exception:                                      # noqa: BLE001
        pass                                               # Anzeige ist kein Grund zu scheitern

    print(f"Vergabe-Analysen: {len(out)} Vorgänge → {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
