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
import contextlib
import datetime as _dt
import json
import os
import shutil
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
from govisor.llm import _geld as _llm_geld  # noqa: E402
from govisor.llm import (chat, letzter_anbieter, anbieter_stand,  # noqa: E402
                         kontext as llm_kontext, mit_boden as llm_mit_boden,
                         DEFAULT_MODEL as llm_default_model,
                         AllKeysExhausted)
from govisor.llm import BudgetErschoepft, kontostand as _llm_kontostand  # noqa: E402
from govisor.llm import RESERVE_USD as _llm_reserve  # noqa: E402
from govisor import doctypes, docextract, docparse, doctax, docpipe  # noqa: E402
from govisor import lbauswahl, dokdubletten  # noqa: E402
from govisor.docpipe import SQL_BRAUCHBAR  # noqa: E402

SRC = ROOT / "data" / "docs" / "DE" / "doc_text.parquet"
OUT = ROOT / "web" / "data" / "doc-analysis.json"
# Sicherungen vor einer Neuberechnung. Bewusst AUSSERHALB von `web/data`: das Verzeichnis
# wird ausgeliefert, eine Sicherung nicht. Sie werden NICHT automatisch geloescht — sie
# tragen Ergebnisse, die einmal Geld gekostet haben, und was hier weg ist, ist weg.
SICHERUNGEN = ROOT / "data" / "sicherungen"
# ⚠ NICHT den Modellnamen hier noch einmal fest eintragen. Genau das stand hier und war
# der Grund, warum der Anbieterboden die Produktion nicht erreicht haette: `llm.DEFAULT_MODEL`
# trug ihn, dieses Modul ueberschrieb ihn mit seiner eigenen Kopie. `mit_boden` haengt die
# guenstigste Route an das an, was tatsaechlich gilt — auch an ein von aussen gesetztes Modell.
def _entschiedene_wahl(hoechstens_tage: int = 7) -> str | None:
    """Das Modell, das `scripts/modellwaechter.py` zuletzt gewaehlt hat — oder None.

    Die Wahl faellt nur unter **freigegebenen** Modellen, also solchen, die den gepaarten
    Versuch am eigenen Korpus bestanden haben (`govisor/pruefstand.py`). Ein billiges
    Modell aus dem Katalog landet hier nie ungeprueft.

    ⚠ **Veraltetes wird ignoriert.** Steht die Datei laenger als eine Woche, ist der
    Waechter offenbar nicht mehr gelaufen; dann gilt wieder die Vorgabe. Eine alte
    Entscheidung stillschweigend weiterzufahren waere die schlechtere Sorte Automatik.
    """
    p = ROOT / "data" / "modellwahl.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        tag = _dt.date.fromisoformat(d["stand"])
        if (_dt.date.today() - tag).days > hoechstens_tage:
            print(f"⚠ Modellwahl vom {d['stand']} ist älter als {hoechstens_tage} Tage — "
                  f"es gilt die Vorgabe. Läuft `scripts/modellwaechter.py` noch?",
                  file=sys.stderr)
            return None
        return d.get("modell") or None
    except Exception:                                    # noqa: BLE001
        return None                                      # keine Wahl getroffen — Vorgabe


# Rangfolge, absichtlich in dieser Reihenfolge:
#   1. OR_MODEL_FEST — ausdruecklicher Zwang, schlaegt alles (Messungen, Fehlersuche)
#   2. die entschiedene Wahl — vom Waechter, nur aus freigegebenen Modellen
#   3. OR_MODEL — die Vorgabe der Aufrufer
#
# ⚠ Punkt 2 schlaegt Punkt 3 mit Absicht. `scripts/analyse_arbeiter.sh` setzt
# `OR_MODEL="${OR_MODEL:-google/gemini-2.5-flash}"` fest ein; das ist eine Vorgabe aus dem
# August, keine Entscheidung fuer heute. Stuende OR_MODEL vorn, koennte die Automatik nie
# greifen — dieselbe Falle wie beim Anbieterboden. Wer wirklich zwingen will, nimmt
# OR_MODEL_FEST, und im Lauf steht dann, welches Modell warum gilt.
_WAHL = _entschiedene_wahl()
MODEL = llm_mit_boden(os.environ.get("OR_MODEL_FEST") or _WAHL
                      or os.environ.get("OR_MODEL") or llm_default_model)
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


def _verbrauch() -> float | None:
    """Der KUMULIERTE Verbrauch (`total_usage`), sofern ermittelbar.

    ⚠ **Warum nicht das Restguthaben.** Der Etappendeckel rechnete `start - jetzt` auf dem
    Restguthaben. Laedt jemand mitten in der Etappe auf, wird die Differenz negativ und der
    Deckel loest NIE aus — genau die Falle, vor der der Docstring von `_restguthaben`
    warnt, nur mit umgekehrtem Vorzeichen. Am 2026-08-24 war das im Modul die fuenfte
    Stelle derselben Klasse (Tagesbuch, Abgleich, Lauf-Deckel, Kostenbuch-Umhaengen).
    `total_usage` steigt nur und kennt keine Aufladung.
    """
    _llm_kontostand(frisch=True)          # setzt `llm._geld["verbrauch"]` mit
    return _llm_geld.get("verbrauch")


def _budget_weg(start_usd: float | None, start_verbrauch: float | None,
                v_jetzt: float | None, r_jetzt: float | None) -> float | None:
    """Wie viel hat dieser Lauf verbraucht? ``None``, wenn es nicht zu ermitteln ist.

    ⚠ **Zwei Zahlen, zwei Richtungen — und wer sie verwechselt, hat keine Bremse.**
    Der kumulierte Verbrauch (`total_usage`) STEIGT, das Restguthaben FAELLT. Beim
    Zusammenlegen am 2026-08-21 wurde `_kontostand()` (steigend) durch `_restguthaben()`
    (fallend) ersetzt und die Rechnung stehen gelassen — die Differenz waere negativ
    gewesen und die Notbremse haette nie ausgeloest.

    ⚠ Und der Rueckfall auf das Restguthaben ueberlebt keine Aufladung: dann steigt der
    Stand ueber den Startwert und die Differenz kehrt sich um. Deshalb hat der Verbrauch
    Vorrang; das Restguthaben ist nur die zweite Wahl.

    Als eigene Funktion herausgezogen, weil der Waechter darueber vorher eine woertliche
    Quelltextzeile festnagelte (`"start_usd - jetzt >= BUDGET_USD" in quelle`). Der brach
    beim ersten legitimen Umbau und sagte nichts ueber das Verhalten — Falle F1 des
    Fallenkatalogs.
    """
    if v_jetzt is not None and start_verbrauch is not None:
        return v_jetzt - start_verbrauch
    if r_jetzt is not None and start_usd is not None:
        return start_usd - r_jetzt
    return None


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


def summary_messages(text: str) -> list[dict]:
    """Die Nachrichten der Zusammenfassung — auch der Stapelweg braucht sie."""
    return [{"role": "system", "content": _SUMMARY_SYS},
            {"role": "user", "content": text[:28_000]}]


_AMPEL = ("gruen", "gelb", "rot")


def _summary_aus(txt: str) -> dict:
    """Rohantwort → Ampel und Zusammenfassung. Von beiden Wegen benutzt."""
    txt = re.sub(r"^```json|^```|```$", "", (txt or "").strip(), flags=re.M).strip()
    try:
        d = json.loads(txt)
        # ⚠ DIE AMPEL GEGEN DIE ERLAUBTEN WERTE PRUEFEN. Sie wurde ungeprueft aus der
        # Modellantwort uebernommen; im Bestand steht deshalb ein Vorgang mit der Ampel
        # `gruuen` (gemessen 2026-08-25 ueber 7.755 Auswertungen). Ein Wert, den die
        # Oberflaeche nicht kennt, faellt dort in den Vorgabezweig — und der ist nicht
        # zwingend derselbe wie hier. Unbekanntes wird `gelb`: die vorsichtige Mitte, wie
        # schon beim unlesbaren JSON eine Zeile weiter unten.
        ampel = str(d.get("ampel", "")).strip().lower()
        return {"ampel": ampel if ampel in _AMPEL else "gelb",
                "ampel_grund": d.get("ampel_grund", ""),
                "zusammenfassung": d.get("zusammenfassung", "")}
    except json.JSONDecodeError:
        return {"ampel": "gelb", "ampel_grund": "", "zusammenfassung": ""}


def summarize(text: str) -> dict:
    return _summary_aus(chat(summary_messages(text), model=MODEL))


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
                   notice_id: str = "", antwort_fn=None,
                   dubletten: dict | None = None, fertig: dict | None = None,
                   vorlauf: dict | None = None) -> dict:
    """files = [(filename, text), …] eines Vorgangs → Analyse mit verifizierter Checkliste.

    Zwei Schienen: **Parser** (§6.2, structured={name: parser_result}) liefert strukturierte
    Fakten ohne LLM; die restlichen Text-Dateien gehen **priorisiert** ans LLM (§6.1), je
    Prioritäts-Doktyp EIN Call, bis der 200k-Token-Deckel greift.
    """
    structured = structured or {}
    by_type_text = defaultdict(list)
    by_type_docs = defaultdict(list)
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
            by_type_docs[dt].append((name, text or ""))
            by_type_file.setdefault(dt, name)

    # ⚠ FORMATFEHLER SIND NICHT DASSELBE WIE SCHLECHTE QUALITÄT. `docextract.extract`
    # gibt bei unparsbarer Antwort `{"items": [], "parse_error": True}` zurück — das sah
    # von oben exakt aus wie „das Modell hat nichts gefunden". Für den laufenden Betrieb
    # ist das gleichgültig (es gibt ohnehin keine Einträge), für den **Prüfstand** aber
    # fatal: ein fremdes Modell, das gültiges JSON in Prosa wickelt, wäre als „findet
    # nichts" durchgefallen und nie wieder geprüft worden. Deshalb wandern beide Zahlen
    # nach oben — wie viele LLM-Aufrufe es gab und wie viele davon unlesbar zurückkamen.
    llm_aufrufe, formatfehler = 0, 0
    rejected, sent_chars, truncated = 0, 0, []
    aus_dubletten = 0
    lb_art = None
    llm_started = False
    for dt in AUSWERTUNG:
        if dt not in by_type_text:
            continue
        # ── DOKUMENT-DUBLETTEN (§6.2) ──────────────────────────────────────────────────
        # Was byteweise schon ausgewertet wurde, faellt aus dem Blob und bekommt die
        # Eintraege des Masters. Gemessen 2026-08-22: 22 % des gesendeten Textes stammt aus
        # Dokumenten, die wir schon kennen — `VHB_124` allein liegt in 432 Vergaben.
        # Das Zitat bleibt gueltig, der Text ist identisch (§6a.2); umgeschrieben wird nur
        # `source_file`, damit der Eintrag auf die Datei DIESES Vorgangs zeigt.
        uebrig = by_type_docs[dt]
        if dubletten and fertig is not None:
            behalten = []
            for name_, text_ in by_type_docs[dt]:
                geerbt = dokdubletten.items_fuer(dt, text_, name_, fertig,
                                                 dubletten, vorlauf or {})
                if geerbt:
                    checklist.extend(geerbt)
                    aus_dubletten += len(geerbt)
                else:
                    behalten.append((name_, text_))
            uebrig = behalten
        blob = "\n\n".join(t for _, t in uebrig).strip()
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
        # ── EIN Pfad, zwei Bezugsquellen ───────────────────────────────────────────────
        # `antwort_fn` liefert die Rohantwort, statt sie zu holen: der Stapelweg reicht
        # damit fertige Antworten herein, und in der Sammelphase gibt er `None` zurueck
        # und merkt sich nur die Anfrage. Ohne diese Naht gaebe es zwei Auswertungen —
        # und die zweite waere in einem Monat anders als die erste.
        if antwort_fn is None:
            res = docextract.extract(dt, blob, by_type_file[dt], model=MODEL)
        else:
            roh = antwort_fn("extract", dt, blob, by_type_file[dt])
            if roh is None:
                continue
            res = docextract.verarbeite(dt, blob, by_type_file[dt],
                                        docextract._parse_array(roh) or [])
        checklist.extend(res.get("items", []))
        rejected += res.get("rejected", 0)
        if not res.get("skipped"):
            llm_aufrufe += 1
            if res.get("parse_error"):
                formatfehler += 1

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

    volltext = "\n\n".join(t for _, t in files)
    if antwort_fn is None:
        summary = summarize(volltext)
    else:
        roh = antwort_fn("summary", "", volltext, "")
        summary = _summary_aus(roh) if roh is not None else {
            "ampel": "gelb", "ampel_grund": "", "zusammenfassung": ""}
    missing = [dt for dt in doctypes.PRIORITY if dt not in seen]      # Q1a-Vollständigkeit (§4.3)
    out = {
        **summary,
        "checklist": checklist,
        "positions": positions,
        "parsed_files": parsed_files,
        "other_documents": other_docs,
        "rejected_items": rejected,
        "llm_aufrufe": llm_aufrufe,
        "formatfehler": formatfehler,
        "token_cost": round(sent_chars / CHARS_PER_TOKEN),
        "doctypes_seen": seen,
        "missing_expected": missing,
        "truncated_doctypes": truncated,
        # Welches Auswahlverfahren die LB bekommen hat — die Grundlage der laufenden
        # Pruefung (`scripts/lb_auswahl_stand.py`). Ohne dieses Feld ist die
        # Kontrollgruppe nachtraeglich nicht mehr von der Behandlung zu unterscheiden.
        "lb_auswahl": lb_art,
        # Wie viele Eintraege aus schon ausgewerteten, identischen Dokumenten stammen.
        "aus_dubletten": aus_dubletten,
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


def _bestand() -> tuple[dict, dict]:
    """(Volltexte je Vorgang, bisherige Ergebnisse). Herausgezogen, damit der Stapelweg
    (`scripts/analyse_batch.py`) dieselbe Auswahl trifft wie der synchrone Lauf."""
    import duckdb
    con = duckdb.connect()
    rows = con.execute(
        f"""SELECT notice_id, file, text FROM read_parquet('{SRC.as_posix()}')
            WHERE {SQL_BRAUCHBAR} AND text IS NOT NULL AND length(text) > 120""").fetchall()
    con.close()
    per = defaultdict(list)
    for nid, datei, text in rows:
        per[nid].append((datei, text))
    for nid, dateien in per.items():
        raus = docpipe.ueberholte(f for f, _ in dateien)
        if raus:
            per[nid] = [(f, t) for f, t in dateien if f not in raus]
    fertig = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    return per, fertig


def offene_vorgaenge(limit: int) -> list[tuple[str, list, dict]]:
    """Was noch zu analysieren ist — (Kennung, Dateien, Parser-Ergebnisse)."""
    import duckdb
    per, fertig = _bestand()
    todo = [n for n in per if n not in fertig]
    offen = {r[0] for r in duckdb.connect().execute(
        f"""SELECT lead_id FROM read_parquet('{ROOT}/data/gold/DE/lead_export.parquet')
            WHERE phase='open' AND deadline_date > current_date""").fetchall()}
    todo = [n for n in todo if n in offen][:limit]
    return [(n, per[n], structured_for_notice(n)) for n in todo]


def uebernehmen_aus_batch(nids: list, antworten: dict, leser_fabrik) -> int:
    """Stapel-Antworten → fertige Analysen, ueber DASSELBE `analyze_notice`.

    ⚠ Geschrieben wird erst, wenn alle Vorgaenge durch sind — und in eine Zwischendatei,
    die dann umbenannt wird. Ein Abbruch mittendrin darf `doc-analysis.json` nicht halb
    beschrieben zuruecklassen; sie ist die Datei, aus der das Frontend liest.
    """
    per, out = _bestand()
    n = 0
    for nid in nids:
        if nid not in per:
            continue
        res = analyze_notice(per[nid], structured=structured_for_notice(nid),
                             notice_id=nid, antwort_fn=leser_fabrik(nid, antworten))
        res["model"] = MODEL + " (batch)"
        out[nid] = res
        n += 1
    tmp = OUT.with_suffix(".teil")
    tmp.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(OUT)
    print(f"    {n} Vorgänge übernommen → {OUT.name}")
    return n


def main() -> int:
    if not SRC.exists():
        print(f"FEHLT: {SRC} — erst `index-docs` laufen lassen.")
        return 1
    with _nur_einmal():
        return _lauf()


@contextlib.contextmanager
def _nur_einmal():
    """Ein Lauf zur Zeit — die Sperre gehoert HIERHER, nicht in die Aufrufer.

    ⚠ Zwei Prozesse schreiben dieselbe `doc-analysis.json`, jeder mit seinem eigenen
    Stand im Speicher. Der zweite, der sichert, gewinnt; die Arbeit des ersten ist weg —
    und zwar lautlos, denn beide melden „Runde fertig".

    **Die Sperre gab es nur mittelbar, und die Vermittlung war falsch.** Der Kommentar
    weiter unten verwies bis zum 2026-08-25 auf `scripts/dokumente_arbeiter.sh` — der
    faehrt die Analyse aber seit dem 18.08. gar nicht mehr. Geschuetzt war seither nur,
    dass nicht zwei ARBEITER laufen. Es gibt aber drei Wege hierher: der Arbeiter,
    `scripts/rueckstau_etappen.sh` und der Aufruf von Hand. Der Arbeiter schlaeft
    zwischen den Runden 30 s — startet in diesem Fenster eine Etappe, laufen beide.

    Eine Sperre, die in einem von drei Aufrufern sitzt, ist keine. `mkdir` ist atomar,
    `[ -e ] && …` waere es nicht.
    """
    sperre = ROOT / "data" / ".analyze_docs.lock"
    try:
        sperre.mkdir()
    except FileExistsError:
        alt_pid = (sperre / "pid").read_text(encoding="utf-8").strip() if (sperre / "pid").exists() else ""
        if alt_pid.isdigit() and _laeuft(int(alt_pid)):
            print(f"⛔ Es laeuft bereits eine Analyse (PID {alt_pid}) — abgebrochen. "
                  f"Zwei Laeufe wuerden sich die Ergebnisse gegenseitig ueberschreiben.",
                  file=sys.stderr, flush=True)
            raise SystemExit(75)
        print(f"⚠ Verwaiste Sperre (PID '{alt_pid or '?'}' laeuft nicht) — uebernommen.",
              flush=True)
        shutil.rmtree(sperre, ignore_errors=True)
        sperre.mkdir()
    (sperre / "pid").write_text(str(os.getpid()), encoding="utf-8")
    try:
        yield
    finally:
        # Nur die EIGENE Sperre wegraeumen: ein spaet sterbender Vorgaenger nimmt sonst
        # die Sperre seines Nachfolgers mit.
        try:
            if (sperre / "pid").read_text(encoding="utf-8").strip() == str(os.getpid()):
                shutil.rmtree(sperre, ignore_errors=True)
        except OSError:
            pass


def _laeuft(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, ValueError):
        return False
    except PermissionError:
        return True                                        # fremder Nutzer, aber am Leben
    return True


# Was mindestens ueber der Reserve stehen muss, damit eine Runde sich lohnt.
#
# Ein Vorgang kostet gemessen rund 0,025 $ (s. `scripts/dokumente_stand.py`), 0,50 $ reichen
# also fuer etwa zwanzig. Der Wert ist eine Abwaegung, keine Naturkonstante: die Runde selbst
# kostet nichts an Geld, aber rund 1,7 GB Speicher und mehrere Minuten Maschine. Fuer eine
# Handvoll Vorgaenge lohnt das nicht — und genau dieser Fall trat ein: bei 1,41 $ Guthaben
# gegen 1,00 $ Reserve blieben 0,41 $, und eine erste Schwelle von 0,15 $ liess die Runde
# durch. Sie haette sechzehn Vorgaenge geschafft und den Rechner minutenlang belegt.
MINDEST_UEBER_RESERVE = float(os.environ.get("MINDEST_UEBER_RESERVE", "0.50"))


def _lohnt_sich() -> str | None:
    """Grund, die Runde gar nicht erst anzufangen — oder ``None``.

    ⚠ WARUM DIE PRUEFUNG GANZ VORNE STEHT. Die Geldwache sitzt in `llm.chat()`, also im
    einzelnen Aufruf. Sie verhindert Ausgaben, nicht Arbeit: eine Runde ohne Guthaben
    laedt trotzdem erst die Quelle (Volltexte aus 817 MB Parquet) und dann den Bestand
    (`doc-analysis.json`, 354 MB → rund 1,7 GB Python-Objekte), stellt danach fest, dass
    sie nichts tun darf, und schreibt alles zurueck.

    Am 29.08. lief genau das im Viertelstundentakt: drei Runden hintereinander meldeten
    unveraendert „1379 warten noch", waehrend der Rechner unbedienbar war. Bezahlt hat es
    niemand — es hat nur die Maschine gekostet.
    """
    try:
        rest = _restguthaben()
    except Exception:                                       # noqa: BLE001
        return None                                         # nicht abrufbar → lieber laufen
    if rest is None:
        return None
    frei = rest - _llm_reserve
    if frei < MINDEST_UEBER_RESERVE:
        return (f"Guthaben {rest:.2f} $ bei {_llm_reserve:.2f} $ Reserve — "
                f"{frei:.2f} $ frei, das reicht fuer keine sinnvolle Runde. "
                f"Aufladen oder MINDEST_UEBER_RESERVE senken.")
    return None


def _lauf() -> int:
    if (grund := _lohnt_sich()):
        print(f"⏸  Runde uebersprungen: {grund}", flush=True)
        return 0
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

    # Dokument-Dubletten: (doctype, Pruefsumme) → Master. Leer, wenn die Datei fehlt —
    # dann laeuft alles wie bisher, nur teurer. Erzeugt von `govisor.dokdubletten.finde`.
    _dubletten = dokdubletten.karte()
    _vorlauf = dokdubletten.master_items()
    if _dubletten or _vorlauf:
        print(f"Dokument-Dubletten: {len(_dubletten):,} über Master · "
              f"{len(_vorlauf):,} aus dem Vorlauf", flush=True)

    # NEUBERECHNUNG SCHWACHER ALTLAEUFE. `NEU_AB_MODELL` nennt Modell-Teilstrings, deren
    # Ergebnisse verworfen und neu gerechnet werden — gemessen am 2026-08-20 liefern die
    # Llama-Anbieter 16 Punkte je Vergabe, wo Gemini 43 findet, und setzen dabei 90 % der
    # Ampeln auf gruen. Solche Saetze sind schlechter als keine: sie sehen aus wie eine
    # Analyse und geben Entwarnung.
    #
    # ⚠ Die alten Saetze werden NICHT ueberschrieben, sondern zuerst weggesichert. Bricht der
    # neue Lauf ab, ist der alte Stand noch da — sonst taeusche man Fortschritt vor und haette
    # am Ende weniger als vorher.
    # Die offenen Leads werden HIER schon gebraucht, nicht erst beim Filtern unten: die
    # Neuberechnung darf nur wegwerfen, was sie auch wieder herstellt (s. gleich).
    offen: set[str] | None = None
    if NUR_OFFENE:
        import duckdb as _d
        offen = {r[0] for r in _d.connect().execute(
            f"""SELECT lead_id FROM read_parquet('{ROOT}/data/gold/DE/lead_export.parquet')
                WHERE phase='open' AND deadline_date > current_date""").fetchall()}

    neu_ab = [x.strip() for x in os.environ.get("NEU_AB_MODELL", "").split(",") if x.strip()]
    if neu_ab:
        # ⚠ „KEIN MODELL VERMERKT" IST AUCH EIN MODELL. Die Teilstring-Suche laeuft gegen
        # `v.get("model") or ""` — bei Saetzen ohne Modellangabe also gegen den leeren
        # String, den kein Token trifft. Gemessen am 2026-08-25: von 2.917 offenen Leads
        # aus abgeloesten Modellen tragen **476** gar keine Angabe. Sie waeren als einzige
        # Gruppe stehen geblieben, und zwar unsichtbar — eine Neuberechnung „aller alten"
        # haette 84 % erwischt und das gemeldet, als waere es alles.
        # Das Zeichen `(ohne)` trifft genau sie.
        _OHNE = {"(ohne)", "?"}
        treffer = [k for k, v in out.items()
                   if (not (v.get("model") or "") and any(t in _OHNE for t in neu_ab))
                   or any(t in (v.get("model") or "") for t in neu_ab if t not in _OHNE)]
        # ⚠ NUR WEGWERFEN, WAS AUCH NEU GERECHNET WIRD. Bis zum 2026-08-25 loeschte diese
        # Stelle ALLE Treffer, und der `NUR_OFFENE`-Filter weiter unten liess davon nur die
        # offenen zum Rechnen durch. Die abgelaufenen waren damit geloescht und wurden nie
        # ersetzt — beim Bestand vom 25.08. waeren das 158 Vorgaenge gewesen (3.544 Treffer,
        # davon 3.386 offen). Ein Werkzeug, das „neu rechnen" heisst, darf nicht ersatzlos
        # streichen.
        uebersprungen = 0
        if offen is not None:
            vorher = len(treffer)
            treffer = [k for k in treffer if k in offen]
            uebersprungen = vorher - len(treffer)
        if treffer:
            # ⚠ NUR DIE BETROFFENEN SICHERN, und zwar JEDES MAL. Vorher wurde die ganze
            # Ergebnisdatei kopiert (358 MB) — aber nur, wenn es die Sicherung noch nicht
            # gab. Ein zweiter Lauf lief also ohne Netz, und ausgerechnet der ist der
            # gefaehrliche, weil der erste den Stand schon veraendert hat. Die betroffenen
            # Saetze allein sind klein genug fuer eine Kopie je Lauf.
            # ⚠ NICHT NEBEN `OUT`, also nicht in `web/data`. Dort lag sie bis zum
            # 2026-08-25 — und `web/data` ist das Verzeichnis, das in den Objektspeicher
            # geht. Der Ausschluss dort trifft exakt den Namen `doc-analysis.json`; eine
            # Sicherung mit Zeitstempel heisst anders und rutschte durch. Gemessen war sie
            # mit 112 MB die GROESSTE Einzeldatei des Uploads, groesser als jede echte
            # Produktdatei — und niemand liest sie. Sicherungen sind Betriebswissen.
            marke = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
            SICHERUNGEN.mkdir(parents=True, exist_ok=True)
            sicherung = SICHERUNGEN / f"{OUT.stem}.vor_neurechnung-{marke}.json"
            sicherung.write_text(
                json.dumps({k: out[k] for k in treffer}, ensure_ascii=False), encoding="utf-8")
            print(f"Alter Stand der betroffenen Vorgänge gesichert: "
                  f"{sicherung.relative_to(ROOT)}", flush=True)
            for k in treffer:
                del out[k]
            print(f"Neuberechnung: {len(treffer)} Vorgänge von {', '.join(neu_ab)} verworfen",
                  flush=True)
        if uebersprungen:
            print(f"  {uebersprungen} Treffer mit abgelaufener Frist bleiben stehen — "
                  f"NUR_OFFENE=1 wuerde sie nicht neu rechnen.", flush=True)

    todo = [(nid, files) for nid, files in per_notice.items() if nid not in out]

    # NUR OFFENE. Gemessen 2026-08-21: von 940 nie analysierten Vorgaengen sind **110**
    # offen, bei den uebrigen 830 ist die Frist durch. Eine Analyse kostet dort dasselbe
    # und nuetzt niemandem — bei 0,42 $ je Vorgang sind das 350 $ fuer nichts.
    if offen is not None:
        vorher = len(todo)
        todo = [t for t in todo if t[0] in offen]
        print(f"Nur offene Ausschreibungen: {len(todo)} von {vorher}", flush=True)
    # ⚠ VOR dem LIMIT festhalten, wie viel wirklich anliegt. Diese Zahl geht unten in
    # `.llm_stand.json` und steuert die Pause des Analyse-Arbeiters. Der hat sie sich bis
    # zum 2026-08-25 selbst ausgerechnet — als Differenz aus Textindex und Ergebnisdatei,
    # also VOR dem NUR_OFFENE-Filter. Am 25.08. standen dort 22 Vorgaenge, von denen kein
    # einziger eine laufende Frist hatte: der Arbeiter sah 22 „Wartende", bekam „Zu
    # analysieren: 0" und drehte trotzdem alle 30 Sekunden eine Runde. 31 Leerrunden in
    # einer halben Stunde, jede mit einem Python-Start ueber eine 358-MB-Datei.
    #
    # Wer die Pause steuert, muss dieselbe Menge zaehlen wie der, der die Arbeit macht.
    # Deshalb sagt es der Lauf selbst, statt es den Arbeiter schaetzen zu lassen.
    anliegend = len(todo)
    if LIMIT:
        todo = todo[:LIMIT]
    print(f"Zu analysieren: {len(todo)} (von {len(per_notice)}) · Modell {MODEL} · {PARALLEL} parallel", flush=True)

    # ── PARALLEL, aber mit einem Schreiber ───────────────────────────────────────────
    # Die Arbeit je Vorgang ist unabhaengig; nur das Ergebnis-Dictionary und die Datei sind
    # gemeinsam. Deshalb rechnen N Faeden, und geschrieben wird unter einem Lock im Haupt-
    # faden, wenn ein Ergebnis eintrifft. Zwei PROZESSE gleichzeitig sind etwas anderes und
    # bleiben verboten — das prueft `_nur_einmal()` oben, seit dem 2026-08-25 hier und
    # nicht mehr in einem der drei Aufrufer.
    schreib_lock = threading.Lock()
    fertig = 0
    erschoepft = False

    def arbeite(auftrag):
        nid, files = auftrag
        structured = structured_for_notice(nid)            # Parser-Schiene (§6.2) über die Roh-ZIPs
        # WOFÜR das Geld ausgegeben wird — je Faden, fürs Kostenbuch. Ohne diesen Rahmen
        # steht dort der Preis, aber nicht der Anlass; Produktion und Versuch wären im
        # selben Topf, und genau diese Vermischung kostete am 2026-08-23 einen Arbeitstag.
        with llm_kontext(zweck="analyse", vorgang=nid):
            res = analyze_notice(files, structured=structured, notice_id=nid,
                                 dubletten=_dubletten, fertig=out, vorlauf=_vorlauf)
        # WER HAT ES ERZEUGT. Seit dem 2026-08-18 gibt es drei Anbieter mit verschiedenen
        # Modellen; welches gerade dran ist, entscheidet das Guthaben. Ohne diese Angabe
        # stuenden im Bestand Ergebnisse nebeneinander, deren Unterschiede niemand mehr
        # erklaeren kann — und die Verwerfungsquote unterscheidet sich messbar je Modell.
        anbieter, modell = letzter_anbieter()
        res["provider"], res["model"] = anbieter, modell
        # WANN. Ohne Datum lässt sich keine Zeitreihe bilden, und ohne Zeitreihe verschwindet
        # eine Verschlechterung, die vor drei Wochen begann, im Gesamtdurchschnitt. Modelle
        # werden auch schlechter, ohne dass es jemand ankündigt: Anbieter wechseln
        # Quantisierung, Endpunkte ändern sich. Ein Mittelwert über alles zeigt das nie.
        # ⚠ ORTSZEIT, nicht UTC. Der Nachtlauf startet um 00:30 Ortszeit und trug damit
        # einen UTC-Stempel vom VORTAG (Berlin ist im Sommer UTC+2) — die Zeitreihe in
        # `llm_qualitaet --zeitreihe` haette den groessten Teil einer Nacht dem falschen
        # Tag zugeschlagen. Gemessen am 2026-08-25: 347 von 7.123 Analysebuchungen (5 %)
        # liegen in diesem Fenster, und es sind systematisch die des Nachtlaufs.
        #
        # ⚠ Bestandsdaten vor dem 2026-08-25 tragen den UTC-Tag. Der Unterschied ist
        # hoechstens ein Tag; die Reihe fasst wochenweise zusammen, deshalb wird NICHT
        # nachtraeglich umgeschrieben — ein umdatierter Bestand waere schwerer zu
        # erklaeren als ein bekannter Bruch.
        res["analysiert_am"] = _dt.datetime.now().date().isoformat()
        return nid, res

    def sichern():
        """Zwischenstand auf die Platte — ueber eine temporaere Datei, dann umbenennen.

        ⚠ HIER STAND EIN DIREKTES `OUT.write_text(...)`. Die Datei ist 355 MB gross und
        traegt Analysen fuer rund 94 $ bezahlte Modell-Zeit; sie zu schreiben dauert
        Sekunden. Wer den Lauf in diesem Fenster abbricht — ein `launchctl bootout`, ein
        Neustart, ein voller Datentraeger — bekommt eine abgeschnittene Datei zurueck, und
        zwar ohne Fehlermeldung: sie ist einfach kuerzer und laesst sich nicht mehr lesen.

        `rename` innerhalb desselben Dateisystems ist atomar: entweder steht der alte Stand
        da oder der neue, nie ein halber. Der Stapel-Pfad zwei Funktionen weiter oben macht
        es seit jeher so (`tmp.replace(OUT)`) — diese Stelle war die Ausnahme.
        """
        tmp = OUT.with_suffix(".teil")
        tmp.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")),
                       encoding="utf-8")
        tmp.replace(OUT)

    start_usd = _restguthaben() if BUDGET_USD else None
    start_verbrauch = _verbrauch() if BUDGET_USD else None
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
                    # Bevorzugt der kumulierte Verbrauch — er ueberlebt eine Aufladung.
                    # Rueckfall auf das Restguthaben, wenn er nicht zu haben ist.
                    v_jetzt = _verbrauch()
                    weg = _budget_weg(start_usd, start_verbrauch, v_jetzt,
                                      None if v_jetzt is not None else _restguthaben())
                    if weg is not None and weg >= BUDGET_USD:
                        print(f"\n⛔ Budget erreicht: {weg:.2f} $ von "
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
            # Was NACH diesem Lauf noch anliegt — dieselbe Menge, die oben gearbeitet
            # wurde, nur um das Geschaffte vermindert. Der Analyse-Arbeiter legt sich
            # schlafen, wenn hier 0 steht.
            "wartend": max(0, anliegend - fertig),
            "erschoepft": erschoepft,
            "anbieter": anbieter_stand(),
        }, ensure_ascii=False), encoding="utf-8")
    except Exception:                                      # noqa: BLE001
        pass                                               # Anzeige ist kein Grund zu scheitern

    print(f"Vergabe-Analysen: {len(out)} Vorgänge → {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
