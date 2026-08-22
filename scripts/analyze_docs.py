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
from govisor.llm import BudgetErschoepft, kontostand as _llm_kontostand  # noqa: E402
from govisor import doctypes, docextract, docparse, doctax, docpipe  # noqa: E402
from govisor import lbauswahl  # noqa: E402
from govisor.docpipe import SQL_BRAUCHBAR  # noqa: E402

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

# ── BUDGET-WAECHTER ─────────────────────────────────────────────────────────────────────
# Am 2026-08-21 lief ein Analyse-Arbeiter 15 Stunden unbemerkt durch und verbrauchte rund
# 50 $/Stunde. Niemand hat es gemerkt, weil der Lauf keine Obergrenze kennt und niemand die
# Rechnung mitliest. `BUDGET_USD` setzt eine harte Grenze: der Lauf fragt den Kontostand,
# merkt sich den Startwert und bricht ab, sobald die Differenz die Grenze reisst.
#
# ⚠ Der Stand ist KONTOWEIT. Laeuft parallel etwas anderes, zaehlt dessen Verbrauch mit —
# genau daran habe ich mich am 21.08. selbst getaeuscht und eine Messung um Faktor 30
# verrissen. Vor dem Start `scripts/laeuft_was.sh` pruefen; die Grenze ist eine Notbremse,
# kein Messinstrument.
BUDGET_USD = float(os.environ.get("BUDGET_USD", "0") or 0)
NUR_OFFENE = os.environ.get("NUR_OFFENE", "") == "1"


def _restguthaben() -> float | None:
    """VERBLEIBENDES Guthaben in Dollar, aus :mod:`govisor.llm`.

    ⚠ **Andere Bedeutung als die Vorgaengerin.** Die alte Fassung gab den VERBRAUCH zurueck
    (`/key` → `data.usage`), eine STEIGENDE Zahl. Hier steht das Restguthaben, das FAELLT.
    Wer die alte Rechnung `jetzt - start >= BUDGET` stehen laesst, bekommt eine negative
    Differenz — und eine Bremse, die NIE ausloest.
    """
    return _llm_kontostand(frisch=True)


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


# Wie viele Pflichtdateien je Vorgang in die Checkliste wandern. Ein Vorgang traegt im
# Mittel rund sieben; die Grenze faengt die Ausreisser ab, ohne sie zu verschweigen — was
# darueber liegt, steht als Zahl im Eintrag.
PFLICHT_MAX = 40


def _pflicht_items(dateien: list[str]) -> list[dict]:
    """Checklisten-Eintraege aus den PFLICHT-Ordnern (§7.5).

    Ohne Modell und ohne Zitat: die Aussage steht in der Verzeichnisstruktur, nicht im Text.
    Markierung ``Abgeleitet`` — sie ist weder woertlich zitiert noch aus dem Text extrahiert,
    sondern aus der Ablage geschlossen. `_parser_item` ist der Praezedenzfall fuer
    Eintraege, die kein LLM erzeugt hat.

    ⚠ `verbleibt_beim_bieter` ist die UMKEHRUNG und wird als solche benannt. Wer sie unter
    die Pflichtdateien mischt, macht aus einer Entlastung eine Anforderung.
    """
    nach_art: dict[str, list[str]] = {}
    for name in dateien:
        art = doctypes.pflicht(name)
        if art:
            nach_art.setdefault(art, []).append(name)
    items = []
    for art, liste in nach_art.items():
        pflichtig = art == "einzureichen"
        for name in liste[:PFLICHT_MAX]:
            kurz = name.replace("::", "/").split("/")[-1]
            items.append({
                "req_type": "einzureichendes_dokument",
                "label": kurz if pflichtig else f"{kurz} (verbleibt beim Bieter)",
                "theme": doctax.theme_for("einzureichendes_dokument"),
                "value": kurz, "unit": None, "quote": "", "source_file": name,
                "source_page": None, "marking": "Abgeleitet",
                "pflicht": art,
            })
        if len(liste) > PFLICHT_MAX:
            items.append({
                "req_type": "einzureichendes_dokument",
                "label": f"... und {len(liste) - PFLICHT_MAX} weitere Dateien in „{art}\"",
                "theme": doctax.theme_for("einzureichendes_dokument"),
                "value": len(liste) - PFLICHT_MAX, "unit": "Dateien", "quote": "",
                "source_file": "", "source_page": None, "marking": "Abgeleitet",
                "pflicht": art,
            })
    return items


# ── WAS AUSGEWERTET WIRD, UND IN WELCHER REIHENFOLGE ────────────────────────────────────
#
# Nicht deckungsgleich mit `doctypes.PRIORITY`. Das sind zwei verschiedene Fragen:
#   · PRIORITY  = „dieser Typ MUSS da sein, sonst ist es eine Luecke" (§4.3)
#   · AUSWERTUNG = „aus diesem Typ holen wir Anforderungen"
#
# ⚠ **Die Fragenbeantwortung steht VORNE, nicht hinten.** Sie ueberschreibt die anderen
# Unterlagen: verschobene Fristen, korrigierte Mengen, zurueckgenommene Anforderungen. Der
# Token-Deckel schneidet von hinten ab (10,3 % der Vorgaenge liegen darueber, gemessen
# 2026-08-21) — stuende sie hinten, fiele ausgerechnet der geltende Stand als Erstes weg.
# Sie ist ausserdem kurz: Ø rund 20.000 Zeichen, der Vorrang kostet also fast nichts.
#
# Sie gehoert NICHT in PRIORITY: die meisten Vergaben haben keine Fragenbeantwortung, und
# ihr Fehlen ist keine Luecke.
AUSWERTUNG = ("fragenantworten",) + tuple(doctypes.PRIORITY)


def analyze_notice(files: list, structured: dict | None = None,
                   notice_id: str = "") -> dict:
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
            # Name zuerst, Inhaltsprobe als Rueckfall — beides in classify() (§6.1).
            dt = doctypes.classify(name, text or "")
            if dt not in AUSWERTUNG:                   # nicht ausgewertet → „Weitere Dokumente" (§7.5)
                other_docs.append(name)
            by_type_text[dt].append(text or "")
            by_type_file.setdefault(dt, name)

    rejected, sent_chars, truncated = 0, 0, []
    lb_art = None
    llm_started = False
    for dt in AUSWERTUNG:
        if dt not in by_type_text:
            continue
        blob = "\n\n".join(by_type_text[dt]).strip()
        if not blob:
            continue
        # ── AUSWAHL INNERHALB DER LB (§6.1) ────────────────────────────────────────────
        # Nur hier: die LB ist der einzige Typ, dessen Blob den Deckel regelmaessig reisst
        # (54 % der Vorgaenge), und der einzige, bei dem gemessen ist, dass die Auswahl
        # etwas aendert. Die uebrigen Typen bleiben unangetastet.
        if dt == "leistungsbeschreibung":
            blob, lb_art = lbauswahl.waehle(blob, notice_id)
        if sent_chars + len(blob) > TOKEN_CAP * CHARS_PER_TOKEN and llm_started:
            truncated.append(dt)                       # Deckel: nach Priorität abschneiden (§6.1)
            continue
        sent_chars += min(len(blob), 60_000)
        llm_started = True
        res = docextract.extract(dt, blob, by_type_file[dt], model=MODEL)
        checklist.extend(res.get("items", []))
        rejected += res.get("rejected", 0)

    # Pflicht aus der Ablage — unabhaengig davon, was das Modell im Text gefunden hat.
    #
    # ⚠ ABER NICHT DOPPELT. Ein ausfuellbares Formular in „Vom Unternehmen auszufuellende
    # Dokumente" bekommt sonst zwei Eintraege desselben Typs zur selben Datei: einen aus der
    # Parser-Schiene („Ausfuellbares Formular, 12 Felder") und einen aus der Ablage. Der
    # Parser-Eintrag sagt mehr, also gewinnt er.
    schon = {(i.get("req_type"), i.get("source_file")) for i in checklist}
    checklist.extend(i for i in _pflicht_items([n for n, _ in files])
                     if (i["req_type"], i["source_file"]) not in schon)

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
        # Welches Auswahlverfahren die LB bekommen hat — die Grundlage der laufenden
        # Pruefung (`scripts/lb_auswahl_stand.py`). Ohne dieses Feld ist die
        # Kontrollgruppe nachtraeglich nicht mehr von der Behandlung zu unterscheiden.
        "lb_auswahl": lb_art,
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
                       WHERE {SQL_BRAUCHBAR} AND text IS NOT NULL AND length(text) > 120)
            SELECT t.notice_id, t.file, t.text
            FROM t LEFT JOIN read_parquet('{LE}') l ON l.lead_id = t.notice_id
            ORDER BY (l.phase = 'open') DESC NULLS LAST,
                     l.deadline_date DESC NULLS LAST,
                     t.notice_id DESC"""
    ).fetchall()
    per_notice = defaultdict(list)
    for nid, file, text in rows:
        per_notice[nid].append((file, text))

    # ── NACHTRAEGE: ueberholte Fassungen aussortieren ───────────────────────────────────
    #
    # `docpipe` markiert sie seit dem 21.08. schon beim Indizieren (`status='ueberholt'`).
    # Der Filter hier gilt dem, was VORHER indiziert wurde: 1.291 Dateien in 84 Vorgaengen,
    # 17,2 Mio. Zeichen. Ohne ihn saehe das Modell dort zwei Angebotsfristen nebeneinander
    # und haette keine Angabe, welche gilt.
    #
    # ⚠ Je DATEI, nicht je Fassung — s. `docpipe.ueberholte`. Von 4.464 Dateien in aelteren
    # Fassungen fehlen 3.173 in der juengsten; Portale liefern Nachtraege, keine Neuausgaben.
    _weg = 0
    for nid, dateien in per_notice.items():
        raus = docpipe.ueberholte(f for f, _ in dateien)
        if raus:
            per_notice[nid] = [(f, t) for f, t in dateien if f not in raus]
            _weg += len(raus)
    if _weg:
        print(f"  {_weg:,} überholte Dateien aus Nachträgen übersprungen", flush=True)

    out = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}

    # NEUBERECHNUNG SCHWACHER ALTLAEUFE. `NEU_AB_MODELL` nennt Modell-Teilstrings, deren
    # Ergebnisse verworfen und neu gerechnet werden — gemessen am 2026-08-20 liefern die
    # Llama-Anbieter 16 Punkte je Vergabe, wo Gemini 43 findet, und setzen dabei 90 % der
    # Ampeln auf gruen. Solche Saetze sind schlechter als keine: sie sehen aus wie eine
    # Analyse und geben Entwarnung.
    #
    # ⚠ Die alten Saetze werden NICHT ueberschrieben, sondern zuerst weggesichert. Bricht der
    # neue Lauf ab, ist der alte Stand noch da — sonst taeusche man Fortschritt vor und haette
    # am Ende weniger als vorher.
    neu_ab = [x.strip() for x in os.environ.get("NEU_AB_MODELL", "").split(",") if x.strip()]
    if neu_ab:
        treffer = [k for k, v in out.items()
                   if any(t in (v.get("model") or "") for t in neu_ab)]
        if treffer:
            sicherung = OUT.with_suffix(f".vor_neurechnung.json")
            if not sicherung.exists():
                sicherung.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
                print(f"Alter Stand gesichert: {sicherung.name}", flush=True)
            for k in treffer:
                del out[k]
            print(f"Neuberechnung: {len(treffer)} Vorgänge von {', '.join(neu_ab)} verworfen",
                  flush=True)

    todo = [(nid, files) for nid, files in per_notice.items() if nid not in out]

    # NUR OFFENE. Gemessen 2026-08-21: von 940 nie analysierten Vorgaengen sind **110**
    # offen, bei den uebrigen 830 ist die Frist durch. Eine Analyse kostet dort dasselbe
    # und nuetzt niemandem — bei 0,42 $ je Vorgang sind das 350 $ fuer nichts.
    if NUR_OFFENE:
        import duckdb as _d
        offen = {r[0] for r in _d.connect().execute(
            f"""SELECT lead_id FROM read_parquet('{ROOT}/data/gold/DE/lead_export.parquet')
                WHERE phase='open' AND deadline_date > current_date""").fetchall()}
        vorher = len(todo)
        todo = [t for t in todo if t[0] in offen]
        print(f"Nur offene Ausschreibungen: {len(todo)} von {vorher}", flush=True)
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
        res = analyze_notice(files, structured=structured, notice_id=nid)
        # WER HAT ES ERZEUGT. Seit dem 2026-08-18 gibt es drei Anbieter mit verschiedenen
        # Modellen; welches gerade dran ist, entscheidet das Guthaben. Ohne diese Angabe
        # stuenden im Bestand Ergebnisse nebeneinander, deren Unterschiede niemand mehr
        # erklaeren kann — und die Verwerfungsquote unterscheidet sich messbar je Modell.
        anbieter, modell = letzter_anbieter()
        res["provider"], res["model"] = anbieter, modell
        return nid, res

    def sichern():
        OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    start_usd = _restguthaben() if BUDGET_USD else None
    if BUDGET_USD:
        print(f"Budget: {BUDGET_USD:.2f} $ ab Stand "
              + (f"{start_usd:.2f} $" if start_usd is not None else "(nicht lesbar — ungebremst!)"),
              flush=True)

    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        laeuft = {pool.submit(arbeite, t): t[0] for t in todo}
        for fut in as_completed(laeuft):
            nid = laeuft[fut]
            try:
                nid, res = fut.result()
            except (AllKeysExhausted, BudgetErschoepft) as e:
                # Beides heisst „hier geht nichts mehr" — der eine Fall aus Sicht der
                # Anbieter, der andere als Entscheidung der Geldwache. Weiterprobieren
                # waere in beiden Faellen nur Laerm.
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
                # Notbremse: alle 10 Vorgaenge nachsehen, was der Lauf gekostet hat.
                if BUDGET_USD and start_usd is not None and fertig % 10 == 0:
                    jetzt = _restguthaben()
                    # Restguthaben FAELLT — verbraucht ist `start - jetzt`.
                    if jetzt is not None and start_usd - jetzt >= BUDGET_USD:
                        print(f"\n⛔ Budget erreicht: {start_usd - jetzt:.2f} $ von "
                              f"{BUDGET_USD:.2f} $ — Lauf wird beendet, Stand ist gesichert.",
                              flush=True)
                        for f in laeuft:
                            f.cancel()
                        break
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
