#!/usr/bin/env python3
"""Vorgaenge zur Neu-Auswertung freigeben — gezielt, mit Sperre und Kostenvorschau.

⚠ WOFUER. `NEU_AB_MODELL` in `analyze_docs.py` waehlt ueber den MODELLNAMEN und rechnet nur
Vorgaenge mit laufender Frist neu. Beides ist richtig fuer seinen Zweck und trifft nicht,
was am 2026-09-18 aufgefallen ist: 566 Vorgaenge aus dem Altbestand tragen 913 Dokumente,
deren Doktyp laengst in `AUSWERTUNG` steht (254 Bieterfragen-Antworten, 128
VHB-124-Eignungsnachweise, 174 Leistungsverzeichnisse). Sie stammen von vor der
Verbesserung des Klassifizierers und wurden als „Weitere Dokumente" abgelegt.

Die Freigabe ist ein LOESCHEN aus `doc-analysis.json`: was dort fehlt, rechnet der
Analyse-Arbeiter in seiner naechsten Runde neu.

⚠ ZWEI SCHREIBER AUF EINE 354-MB-DATEI sind genau der Fehler, den die Dubletten- und
Profil-Wettlaeufe an anderer Stelle gezeigt haben. Deshalb bricht dieses Skript ab, solange
eine Analyse laeuft — es wartet nicht, es sagt es.

    python3 scripts/neu_auswerten.py --nur-offene            Vorschau (nichts geaendert)
    python3 scripts/neu_auswerten.py --nur-offene --wirklich  freigeben
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from govisor import doctypes  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SPEICHER = ROOT / "web" / "data" / "doc-analysis.json"
JE_VORGANG = ROOT / "web" / "data" / "doc-analysis"
AUSWERTUNG = {"aufforderung", "eignung", "fragenantworten",
              "leistungsbeschreibung", "vertrag", "zuschlagskriterien"}
ZEICHEN_JE_TOKEN = 4         # deutscher Fliesstext, konservativ
USD_JE_TOKEN = 0.000482 / 1000   # gemini-2.5-flash, aus data/llm_kosten.jsonl


def _laeuft_eine_analyse() -> int | None:
    r = subprocess.run(["ps", "-eo", "pid,command"], capture_output=True, text=True)
    for z in r.stdout.splitlines():
        if "analyze_docs.py" in z and " -c " not in z and "neu_auswerten" not in z:
            try: return int(z.split()[0])
            except ValueError: pass
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nur-offene", action="store_true",
                    help="nur Vorgaenge mit laufender Frist (Vorgabe: alle betroffenen)")
    ap.add_argument("--wirklich", action="store_true", help="tatsaechlich freigeben")
    a = ap.parse_args(argv)

    # ── Wen betrifft es? ──────────────────────────────────────────────────────
    ziel: set[str] = set()
    dok = 0
    for p in JE_VORGANG.glob("*.json"):
        try: j = json.loads(p.read_text(encoding="utf-8"))
        except Exception: continue
        if j.get("analysiert_am"):
            continue                        # nur Altbestand
        fehl = [x for x in (j.get("other_documents") or [])
                if doctypes.classify(str(x).replace("\\", "/").split("/")[-1], "") in AUSWERTUNG]
        if fehl:
            ziel.add(p.stem)
            dok += len(j.get("parsed_files") or []) + len(fehl)

    if a.nur_offene:
        import duckdb
        offen = {r[0] for r in duckdb.connect().execute(
            f"""SELECT lead_id FROM read_parquet('{(ROOT / 'data/gold/DE/lead_export.parquet').as_posix()}')
                WHERE phase='open' AND deadline_date > current_date""").fetchall()}
        vorher = len(ziel)
        ziel &= offen
        print(f"  --nur-offene: {vorher:,} → {len(ziel):,} (abgelaufene bleiben stehen)")

    print(f"\n  Vorgaenge zur Neuberechnung : {len(ziel):,}")
    if not ziel:
        print("\n  Nichts zu tun.")
        return 0

    # ⚠ NICHT ueber eine Dokumentpauschale schaetzen. Eine erste Fassung rechnete mit
    #   „8 Dokumente je Vorgang à 4.096 Token" und kam auf 0,09 USD; nachgemessen waren es
    #   234 Dateien mit 4,9 Mio. Zeichen — das Sechsfache. Vorgaenge streuen extrem
    #   (19 bis 60 Dateien, 116k bis 2,2 Mio. Zeichen). Wer Geld ankuendigt, zaehlt den
    #   Text, der tatsaechlich hingeschickt wird.
    liste = ",".join(f"'{z}'" for z in sorted(ziel))
    import duckdb
    zeichen, dateien = duckdb.connect().execute(
        f"""SELECT coalesce(sum(length(text)), 0), count(*)
            FROM read_parquet('{(ROOT / 'data/docs/DE/doc_text.parquet').as_posix()}')
            WHERE notice_id IN ({liste})""").fetchone()
    kosten = zeichen / ZEICHEN_JE_TOKEN * USD_JE_TOKEN
    print(f"  Text dafuer                 : {dateien:,} Dateien, {zeichen:,} Zeichen")
    print(f"  geschaetzte Kosten          : {kosten:.2f} USD")

    # ⛔ OHNE TEXT KEINE FREIGABE. Ein Eintrag ohne Text im Index laesst sich loeschen, aber
    #   nicht neu rechnen — man verlaere die vorhandene Auswertung ersatzlos. Genau davor
    #   warnt `govisor/kennzahlen.py`: die Auszuege sind der Rohstoff, die PDFs sind es nicht.
    mit_text = {r[0] for r in duckdb.connect().execute(
        f"""SELECT DISTINCT notice_id
            FROM read_parquet('{(ROOT / 'data/docs/DE/doc_text.parquet').as_posix()}')
            WHERE notice_id IN ({liste})""").fetchall()}
    ohne = ziel - mit_text
    if ohne:
        print(f"\n  ⚠ {len(ohne):,} ohne Text im Index — bleiben stehen "
              f"(loeschen waere ein Verlust ohne Gegenwert)")
        ziel &= mit_text
        if not ziel:
            return 0
    if not a.wirklich:
        print("\n  (Vorschau — nichts geaendert. Mit `--wirklich` freigeben.)")
        return 0

    # ── DAS FENSTER NEHMEN, STATT DARUM ZU RENNEN ────────────────────────────
    #
    # ⚠ `analyse_arbeiter.sh` ist ein DAUER-Arbeiter, keine einmalige Aufgabe. Er dreht
    # bei vorhandenem Rueckstau alle 30 Sekunden eine Runde. Auf „gerade laeuft keine
    # Analyse" zu warten heisst deshalb, auf eine Luecke von Sekunden zu zielen — und
    # zwischen der Pruefung und dem Schreiben einer 354-MB-Datei liegen mehr davon.
    # Gemessen: PID 6144 war durch und PID 7624 lief bereits, als nachgesehen wurde.
    #
    # Der Arbeiter hat aber eine eingebaute Bremse: `[ -e data/.daily_leads.lock ]` →
    # 10 Minuten Pause, geprueft VOR JEDER RUNDE. Diese Sperre zu nehmen ist der
    # vorgesehene Weg, sich Ruhe zu verschaffen, und sie bremst zugleich den
    # Dokumenten-Arbeiter und den Tageslauf. Ein Riegel statt drei Wettlaeufe.
    #
    # ⚠ VERZEICHNIS, nicht Datei: `mkdir` ist atomar, `[ -e ] && touch` ist es nicht.
    # Dieselbe Form benutzen daily_leads.sh und analyse_arbeiter.sh.
    sperre = ROOT / "data" / ".daily_leads.lock"
    try:
        sperre.mkdir()
    except FileExistsError:
        fremd = (sperre / "pid").read_text(errors="ignore").strip() if (sperre / "pid").exists() else "?"
        sys.exit(f"\n  ⛔ Tageslauf-Sperre liegt schon (PID {fremd}). Das ist nicht meine — "
                 f"spaeter noch einmal.")
    (sperre / "pid").write_text(str(os.getpid()))
    try:
        # Die LAUFENDE Runde faellt nicht unter die Sperre, die sieht sie erst beim
        # naechsten Durchgang. Also abwarten, bis sie von selbst fertig ist.
        for _ in range(240):                      # hoechstens 20 min
            pid = _laeuft_eine_analyse()
            if not pid:
                break
            print(f"\r  warte auf die laufende Runde (PID {pid}) …", end="", flush=True)
            time.sleep(5)
        else:
            sys.exit("\n  ⛔ Die Runde laeuft seit 20 min. Abgebrochen, statt hineinzuschreiben.")
        print("\r" + " " * 60 + "\r", end="")
        _freigeben(ziel)
    finally:
        # ⚠ IMMER zurueckgeben, auch bei einem Fehler. Eine liegengebliebene Sperre
        # legt Tageslauf UND beide Arbeiter still, und zwar lautlos: sie melden
        # „Tageslauf aktiv" und warten, ohne dass je einer laeuft.
        shutil.rmtree(sperre, ignore_errors=True)
    return 0


def _freigeben(ziel: set[str]) -> None:

    daten = json.loads(SPEICHER.read_text(encoding="utf-8"))
    weg = [k for k in ziel if k in daten]
    sicherung = ROOT / "data" / f"doc-analysis-freigabe-{len(weg)}.json"
    sicherung.write_text(json.dumps({k: daten[k] for k in weg}, ensure_ascii=False),
                         encoding="utf-8")
    for k in weg:
        del daten[k]
        (JE_VORGANG / f"{k}.json").unlink(missing_ok=True)
    tmp = SPEICHER.with_suffix(".json.part")
    tmp.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    tmp.replace(SPEICHER)
    print(f"\n  {len(weg):,} Vorgaenge freigegeben. Sicherung: {sicherung.relative_to(ROOT)}")
    print("  Der Analyse-Arbeiter nimmt sie in seiner naechsten Runde.")


if __name__ == "__main__":
    sys.exit(main())
