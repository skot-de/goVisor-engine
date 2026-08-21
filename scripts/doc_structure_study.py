#!/usr/bin/env python3
"""Struktur-Studie der Vergabeunterlagen — beantwortet Q1–Q7 (Spec Sven).

Geht die heruntergeladenen ZIPs (data/docs/DE/<notice>/) EINMAL durch: Dateiliste + Text +
PDF-Seiten + Größe + AcroForm. Aggregiert je Dokumenttyp und je Branche, mit Fallzahlen.
Schreibt CSVs nach data/docs/study/ und druckt Tabellen. Kleine Branchen (n<20) sind Hinweis,
keine Statistik.

Aufruf:  python3 scripts/doc_structure_study.py
"""
import csv
import glob
import io
import json
import os
import re
import statistics as st
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import pypdf

ROOT = Path(__file__).resolve().parent.parent
import sys; sys.path.insert(0, str(ROOT))
from govisor import docpipe, doctypes  # noqa: E402

OUT = ROOT / "data" / "docs" / "study"; OUT.mkdir(parents=True, exist_ok=True)
BRANCHES = ["bau", "beratung", "medizin", "it", "energie", "sicherheit"]

# ── Dokumenttyp-Klassifikation: EINE Quelle, `govisor.doctypes` ──
# Dieses Skript trug bis 2026-08-21 eine eigene, eingefrorene Kopie der Regeln. Seine
# Extratypen `technische_anlage` und `informationsblatt` haben sich als richtig erwiesen und
# sind in den Betriebs-Klassifikator uebernommen worden; sein `bewerbungsbedingungen` faellt
# dort unter `eignung`.
_KRIT_TXT = re.compile(r"zuschlagskriteri|wertungskriteri|zuschlag erfolgt|bewertet.{0,20}nach|gewichtung", re.I)
_EIGN_TXT = re.compile(r"eignungskriteri|eignungsnachweis|geeignetheit|mindestanforderung.{0,20}eignung", re.I)
_LOS = re.compile(r"\blos[\s_\-]?\d|\blos[\s_\-]?[ivx]+\b|fachlos|gewerk", re.I)
_VERSION = re.compile(r"\bv\.?\d\b|version|änderung|korrektur|nachtrag|update|berichtig|_neu\b|rev\.?\d", re.I)
_DATE = re.compile(r"\b20\d{2}[-_.]?\d{2}[-_.]?\d{2}\b|\b\d{2}[-_.]\d{2}[-_.]20\d{2}\b")
_GAEB = re.compile(r"\.(d8[1-4]|x8[1-3]|p8[0-9])$|gaeb", re.I)


def classify(name: str) -> str:
    return doctypes.classify(name)


def norm_text(t: str) -> str:
    t = re.sub(r"\d+", " ", (t or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def analyze_file(name: str, ext: str, data: bytes) -> dict:
    fn = docpipe._EXTRACT.get(ext)
    text, status = "", "unknown_type"
    if fn:
        try:
            text = fn(data) or ""
        except Exception:
            text = ""
        status = "ok" if text.strip() else ("image_only" if ext == ".pdf" else "empty")
    elif ext in docpipe._KNOWN_NOEXTRACT:
        status = "unsupported"
    pages, fillable = None, False
    if ext == ".pdf":
        try:
            r = pypdf.PdfReader(io.BytesIO(data))
            pages = len(r.pages)
            try:
                fillable = bool(r.get_fields())
            except Exception:
                fillable = False
        except Exception:
            pass
    return {"name": name, "ext": ext, "size": len(data), "text": text,
            "status": status, "pages": pages, "fillable": fillable, "doctype": classify(name)}


# Manche PDFs bringen pypdf/pdfminer in eine Endlosschleife (malformed xref, „Multiple definitions").
# SIGALRM-Zeitlimit pro Datei (pure-Python → am nächsten Bytecode unterbrechbar); Treffer werden
# als status='timeout' übersprungen statt den ganzen Lauf zu blockieren.
import signal


class _FileTimeout(Exception):
    pass


def _on_alarm(signum, frame):
    raise _FileTimeout()


signal.signal(signal.SIGALRM, _on_alarm)


def safe_analyze(name: str, ext: str, data: bytes, limit: int = 25) -> dict:
    try:
        signal.alarm(limit)
        return analyze_file(name, ext, data)
    except _FileTimeout:
        return {"name": name, "ext": ext, "size": len(data), "text": "",
                "status": "timeout", "pages": None, "fillable": False, "doctype": classify(name)}
    finally:
        signal.alarm(0)


def main() -> int:
    id2br, id2lose = {}, {}
    for f in glob.glob(str(ROOT / "web/data/leads-*.json")):
        br = os.path.basename(f).split("leads-")[1].split(".")[0]
        for r in (json.load(open(f)) or []):
            id2br[r.get("id")] = br
            id2lose[r.get("id")] = len(r.get("lose") or [])

    notices = []  # {nid, branche, files:[...]}
    dirs = [d for d in glob.glob(str(ROOT / "data/docs/DE/*/"))]
    print(f"Scanne {len(dirs)} Ordner …", flush=True)
    for i, d in enumerate(dirs, 1):
        nid = os.path.basename(d.rstrip("/"))
        zips = [z for z in glob.glob(os.path.join(d, "*.zip")) if os.path.getsize(z) > 10240]
        if not zips:
            continue
        files = []
        for z in zips:
            try:
                blob = Path(z).read_bytes()
            except Exception:
                continue
            for name, ext, data in docpipe.iter_docs(blob):
                files.append(safe_analyze(name, ext, data))
        if not files:
            continue
        notices.append({"nid": nid, "branche": id2br.get(nid, "?"),
                        "lose": id2lose.get(nid, 0), "files": files})
        if i % 25 == 0:
            print(f"  {i}/{len(dirs)} …", flush=True)

    N = len(notices)
    by_br = Counter(n["branche"] for n in notices)
    print(f"\n=== BASIS: {N} Vorgänge mit Inhalt | je Branche: {dict(by_br)} ===\n")

    # ══ Q2 — Paketgröße & Parsbarkeit ══
    def dist(vals):
        vals = sorted(v for v in vals if v is not None)
        if not vals:
            return (0, 0, 0, 0)
        return (round(st.median(vals), 1), round(vals[int(len(vals)*0.75)], 1), max(vals), round(sum(vals)/len(vals), 1))
    files_per = [len(n["files"]) for n in notices]
    pages_per = [sum(f["pages"] or 0 for f in n["files"]) for n in notices]
    size_per = [sum(f["size"] for f in n["files"])/1e6 for n in notices]
    chars_per = [sum(len(f["text"]) for f in n["files"]) for n in notices]
    pdfs = [f for n in notices for f in n["files"] if f["ext"] == ".pdf"]
    img_pdfs = [f for f in pdfs if f["status"] == "image_only"]
    notices_with_ocr = sum(1 for n in notices if any(f["status"] == "image_only" for f in n["files"]))
    with open(OUT/"q2_paketgroesse.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["metrik", "median", "p75", "max", "mittel"])
        for lbl, v in [("dateien_je_vorgang", files_per), ("pdf_seiten_je_vorgang", pages_per),
                       ("groesse_MB_je_vorgang", size_per), ("textzeichen_je_vorgang", chars_per)]:
            w.writerow([lbl, *dist(v)])
    print("── Q2 Paketgröße/Parsbarkeit (über alle Vorgänge) ──")
    print(f"  {'Metrik':28}{'Median':>10}{'p75':>10}{'Max':>10}{'Mittel':>10}")
    for lbl, v in [("Dateien/Vorgang", files_per), ("PDF-Seiten/Vorgang", pages_per),
                   ("Größe MB/Vorgang", size_per), ("Textzeichen/Vorgang", chars_per)]:
        m = dist(v); print(f"  {lbl:28}{m[0]:>10}{m[1]:>10}{m[2]:>10}{m[3]:>10}")
    ocr_pg = sum(f["pages"] or 0 for f in img_pdfs); all_pg = sum(f["pages"] or 0 for f in pdfs)
    print(f"  PDFs gesamt: {len(pdfs)} | davon nur-Bild (OCR nötig): {len(img_pdfs)} "
          f"({100*len(img_pdfs)/max(len(pdfs),1):.0f}% der PDFs, {100*ocr_pg/max(all_pg,1):.0f}% der PDF-Seiten)")
    print(f"  Vorgänge mit ≥1 OCR-PDF: {notices_with_ocr}/{N} ({100*notices_with_ocr/N:.0f}%)")
    print(f"  → LLM-Tokens/Vorgang (Textzeichen/4): Median {dist(chars_per)[0]/4:.0f}, p75 {dist(chars_per)[1]/4:.0f}, Max {dist(chars_per)[2]/4:.0f}\n")

    # ══ Q3 — Dokumentklassen + Dateinamen-Trefferquote (+ Branche) ══
    file_types = Counter(f["doctype"] for n in notices for f in n["files"])
    tot_files = sum(file_types.values())
    classnoun = sum(v for k, v in file_types.items() if k != "sonstiges")
    # je Branche: Anteil Vorgänge, die den Typ enthalten
    brtype = {b: Counter() for b in BRANCHES}
    for n in notices:
        if n["branche"] not in brtype:
            continue
        for t in {f["doctype"] for f in n["files"]}:
            brtype[n["branche"]][t] += 1
    with open(OUT/"q3_doktypen_je_branche.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["doctype", "anteil_dateien_%"]+[f"{b}(n={by_br[b]})_%" for b in BRANCHES])
        for t, _ in DOCTYPES + [("sonstiges", None)]:
            w.writerow([t, round(100*file_types[t]/tot_files, 1)]+[round(100*brtype[b][t]/max(by_br[b], 1)) for b in BRANCHES])
    print("── Q3 Dokumentklassen — Anteil der VORGÄNGE je Branche (%), n je Spalte ──")
    print(f"  {'Doctype':22}"+"".join(f"{b[:5]+'/'+str(by_br[b]):>10}" for b in BRANCHES))
    for t, _ in DOCTYPES:
        print(f"  {t:22}"+"".join(f"{100*brtype[b][t]//max(by_br[b],1):>9}%" for b in BRANCHES))
    print(f"  → Dateiname-Trefferquote (klassifizierbar ohne Inhalt): {100*classnoun/tot_files:.0f}% "
          f"({classnoun}/{tot_files} Dateien); Rest 'sonstiges' braucht Inhaltsblick.\n")

    # ══ Q1 — Wiederkehrung + Inhaltsähnlichkeit je Doctype ══
    dt_notices = defaultdict(set); dt_branches = defaultdict(set); dt_texts = defaultdict(list)
    for n in notices:
        for f in n["files"]:
            dt = f["doctype"]
            dt_notices[dt].add(n["nid"]); dt_branches[dt].add(n["branche"])
            if f["status"] == "ok" and len(f["text"]) > 200:
                dt_texts[dt].append(norm_text(f["text"])[:1200])

    def similarity(texts):
        s = texts[:40]
        if len(s) < 3:
            return None
        import random; random.seed(7)
        pairs = [(i, j) for i in range(len(s)) for j in range(i+1, len(s))]
        random.shuffle(pairs); pairs = pairs[:300]
        rs = [SequenceMatcher(None, s[i], s[j]).ratio() for i, j in pairs]
        return round(st.median(rs), 2)
    rows = []
    for dt in sorted(dt_notices, key=lambda d: -len(dt_notices[d])):
        sim = similarity(dt_texts[dt])
        verdict = "—" if sim is None else ("weitgehend identisch" if sim > .82 else "teils gleich" if sim > .5 else "nur namensgleich")
        rows.append([dt, len(dt_notices[dt]), round(100*len(dt_notices[dt])/N), len(dt_branches[dt]), sim if sim is not None else "", verdict])
    with open(OUT/"q1_wiederkehrung.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["doctype", "n_vorgaenge", "anteil_%", "n_branchen", "median_aehnlichkeit", "urteil"]); w.writerows(rows)
    print("── Q1 Wiederkehrung + Inhaltsähnlichkeit (Ranking) ──")
    print(f"  {'Doctype':22}{'Vorg.':>7}{'%':>5}{'Bran.':>6}{'Ähnl.':>7}  Urteil")
    for r in rows:
        print(f"  {r[0]:22}{r[1]:>7}{r[2]:>5}{r[3]:>6}{str(r[4]):>7}  {r[5]}")
    print()

    # ══ Q4 — Ort der Zuschlagskriterien/Eignung ══
    loc = Counter()
    for n in notices:
        has_own = any(f["doctype"] == "zuschlagskriterien" for f in n["files"])
        emb = any(_KRIT_TXT.search(f["text"] or "") for f in n["files"] if f["doctype"] in ("eignung", "leistungsbeschreibung", "vertrag"))
        loc["eigenes Dokument" if has_own else "eingebettet (Bewerbung/LB)" if emb else "nicht gefunden"] += 1
    crit_names = Counter(re.sub(r"\d+", "#", os.path.basename(f["name"]).lower())
                         for n in notices for f in n["files"] if f["doctype"] == "zuschlagskriterien")
    with open(OUT/"q4_kriterien_ort.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["ort", "n_vorgaenge", "anteil_%"])
        for k, v in loc.most_common():
            w.writerow([k, v, round(100*v/N)])
    print("── Q4 Wo stehen die Zuschlagskriterien? (n=%d) ──" % N)
    for k, v in loc.most_common():
        print(f"  {k:30}{v:>5}  ({100*v/N:.0f}%)")
    print("  Typische Dateinamen (eigenes Kriterien-Dok):", ", ".join(f"{k}×{v}" for k, v in crit_names.most_common(3)) or "—")
    print()

    # ══ Q5 — Los-Spezifik ══
    lot_any = [n for n in notices if any(_LOS.search(f["name"]) for f in n["files"])]
    multilot = [n for n in notices if n["lose"] > 1]
    ml_lotdocs = Counter()
    for n in multilot:
        for f in n["files"]:
            if _LOS.search(f["name"]):
                ml_lotdocs[f["doctype"]] += 1
    print("── Q5 Los-Spezifik ──")
    print(f"  Vorgänge mit los-benannten Dateien: {len(lot_any)}/{N} ({100*len(lot_any)/N:.0f}%)")
    print(f"  Mehr-Los-Vergaben (lose>1, aus Metadaten): {len(multilot)}")
    print(f"  In Mehr-Los-Paketen los-spezifische Doctypes: " + (", ".join(f"{k}×{v}" for k, v in ml_lotdocs.most_common(5)) or "—"))
    print()

    # ══ Q6 — Strukturierte Formate je Branche ══
    print("── Q6 Maschinenlesbare Formate — Anteil VORGÄNGE je Branche (%), n je Spalte ──")
    print(f"  {'Format':22}"+"".join(f"{b[:5]+'/'+str(by_br[b]):>10}" for b in BRANCHES))
    q6 = {}
    for lbl, test in [("GAEB (Bau-LV)", lambda f: bool(_GAEB.search(f["name"]))),
                      ("ausfüllbares PDF", lambda f: f["fillable"]),
                      ("Excel (xls/xlsx)", lambda f: f["ext"] in (".xlsx", ".xls"))]:
        rowb = {}
        for b in BRANCHES:
            cnt = sum(1 for n in notices if n["branche"] == b and any(test(f) for f in n["files"]))
            rowb[b] = 100*cnt//max(by_br[b], 1)
        q6[lbl] = rowb
        print(f"  {lbl:22}"+"".join(f"{rowb[b]:>9}%" for b in BRANCHES))
    with open(OUT/"q6_formate_je_branche.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["format"]+[f"{b}(n={by_br[b]})_%" for b in BRANCHES])
        for lbl, rowb in q6.items():
            w.writerow([lbl]+[rowb[b] for b in BRANCHES])
    print()

    # ══ Q7 — Versionierung ══
    v_ver = sum(1 for n in notices if any(_VERSION.search(f["name"]) for f in n["files"]))
    v_chg = sum(1 for n in notices if any(re.search(r"änderung|changes|korrektur|nachtrag|berichtig", f["name"], re.I) for f in n["files"]))
    v_multidate = sum(1 for n in notices if len({m.group(0) for f in n["files"] for m in [_DATE.search(f["name"])] if m}) > 1)
    print("── Q7 Versionierung ──")
    print(f"  Vorgänge mit Versions-/Änderungs-Markern im Dateinamen: {v_ver}/{N} ({100*v_ver/N:.0f}%)")
    print(f"  Vorgänge mit expliziter Änderungs-/Nachtrags-Datei: {v_chg}/{N} ({100*v_chg/N:.0f}%)")
    print(f"  Vorgänge mit mehreren Datumsständen in Dateinamen: {v_multidate}/{N} ({100*v_multidate/N:.0f}%)")
    print(f"\nCSVs geschrieben nach {OUT.relative_to(ROOT)}/  (q1…q6)")
    print("Hinweis: energie (n=%d) und sicherheit (n=%d) sind zu klein für Prozent-Statistik → als Indiz lesen." % (by_br['energie'], by_br['sicherheit']))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
