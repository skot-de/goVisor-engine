#!/usr/bin/env python3
"""Verfahrenskalender je offenem Lead → ``web/data/kalender/<lead_id>.json``.

Feature #16. Der Implementierungsstand führte es als „teilweise — Angebotsfrist mit Datum
im Detail, Kalenderseite + iCal offen". Es fehlte kein Datenfeld: die Termine standen in
den Unterlagen, nur als Zeichenkette ohne Typ (s. `govisor/normwerte.py` und
`govisor/kalender.py`).

Zwei Quellen, bewusst getrennt gekennzeichnet:

* ``bekanntmachung`` — die Angebotsfrist aus `lead_export`. Sie liegt für JEDEN offenen
  Lead vor und ist das Rückgrat.
* ``unterlagen`` — was in den Dokumenten steht und in keiner Bekanntmachung: vor allem
  **Bindefrist** und **Bieterfragen-Frist**. Beide entscheiden mit über Erfolg oder
  Ausschluss, und beide sind bisher nirgends sichtbar.

⚠ Nur klassifizierte Termine. `docextract` typisiert jedes gefundene Datum als `frist`,
darunter auch Druckdaten von PDF-Seiten. Was sich keiner Terminart zuordnen lässt, fällt
raus — und wird GEZÄHLT, damit eine gekürzte Liste nicht wie eine vollständige aussieht.

Aufruf::

    python3 scripts/export_kalender.py [--country DE] [--ical <lead_id>]
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor import kalender  # noqa: E402

W = ROOT / "web" / "data"
ANALYSEN = W / "doc-analysis"
# ⚠ EINE DATEI JE VORGANG, keine Sammeldatei. `doc-analysis.json` war am 2026-08-22 auf
# 252 MB gewachsen, bevor sie zerlegt wurde; der Kalender wiederholt den Fehler nicht.
# Die Terminansicht zeigt die MERKLISTE — ein Nutzer braucht eine Handvoll Dateien, nicht
# 1,6 MB fuer 2.945 Vorgaenge, von denen ihn drei interessieren.
JE_VORGANG = W / "kalender"
INDEX = W / "kalender-index.json"


def _leads(country: str) -> dict[str, dict]:
    """Offene Leads mit Titel und Angebotsfrist — das Rückgrat des Kalenders."""
    p = ROOT / "data" / "gold" / country / "lead_export.parquet"
    if not p.exists():
        return {}
    rows = duckdb.connect().execute(
        f"""SELECT lead_id, title, CAST(deadline_date AS VARCHAR)
            FROM read_parquet('{p.as_posix()}')
            WHERE phase='open' AND deadline_date IS NOT NULL""").fetchall()
    return {r[0]: {"titel": r[1] or "", "frist": r[2]} for r in rows}


def baue(country: str = "DE") -> tuple[dict, dict]:
    leads = _leads(country)
    if not leads:
        return {}, {"leads": 0}
    aus: dict[str, dict] = {}
    zahl = collections.Counter()
    for lead_id, info in leads.items():
        datei = ANALYSEN / f"{lead_id}.json"
        checkliste = []
        if datei.exists():
            try:
                checkliste = (json.loads(datei.read_text(encoding="utf-8")) or {}).get("checklist") or []
            except Exception:                                   # noqa: BLE001
                checkliste = []                                 # ein kaputter Vorgang kippt nicht den Lauf
        erg = kalender.termine(checkliste, angebotsfrist=info["frist"])
        # ⚠ Nur aufnehmen, wenn die Unterlagen etwas BEITRAGEN. Ein Kalender, der für
        # 14.000 Leads nur die Angebotsfrist wiederholt, die im Lead ohnehin steht,
        # blaeht die Datei auf und sagt nichts Neues.
        aus_unterlagen = [t for t in erg["termine"] if t["quelle"] == "unterlagen"]
        if not aus_unterlagen:
            zahl["nur_angebotsfrist"] += 1
            continue
        aus[lead_id] = {"titel": info["titel"][:120], "termine": erg["termine"],
                        "verworfen": erg["verworfen"]}
        zahl["mit_terminen"] += 1
        zahl["termine_gesamt"] += len(erg["termine"])
        zahl["verworfen"] += erg["verworfen"]
        for t in aus_unterlagen:
            zahl[f"art_{t['art']}"] += 1
    zahl["leads"] = len(leads)
    return aus, zahl


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--country", default="DE")
    ap.add_argument("--ical", metavar="LEAD_ID", help="einen Lead als .ics auf stdout")
    a = ap.parse_args(argv)

    aus, zahl = baue(a.country)
    if a.ical:
        eintrag = aus.get(a.ical)
        if not eintrag:
            print(f"  ✖ {a.ical}: kein Kalender (keine Termine aus den Unterlagen).",
                  file=sys.stderr)
            return 1
        print(kalender.als_ical(eintrag["termine"], eintrag["titel"], a.ical), end="")
        return 0

    JE_VORGANG.mkdir(parents=True, exist_ok=True)
    vorher = {q.name for q in JE_VORGANG.glob("*.json")}
    geschrieben = 0
    for lead_id, eintrag in aus.items():
        sicher = "".join(c for c in lead_id if c.isalnum() or c in "_-")
        if not sicher:
            continue
        ziel = JE_VORGANG / f"{sicher}.json"
        text = json.dumps(eintrag, ensure_ascii=False, separators=(",", ":"))
        # Nur schreiben, was sich geaendert hat — wie beim Analyse-Export daneben. Sonst
        # schiebt jede Nacht der ganze Bestand als „geaendert" in den Objektspeicher.
        if not (ziel.exists() and ziel.read_text(encoding="utf-8") == text):
            ziel.write_text(text, encoding="utf-8")
            geschrieben += 1
        vorher.discard(f"{sicher}.json")
    for verwaist in vorher:                     # Lead ist zu, Termine sind gegenstandslos
        (JE_VORGANG / verwaist).unlink(missing_ok=True)
    INDEX.write_text(json.dumps(sorted(aus), ensure_ascii=False), encoding="utf-8")
    print(f"Verfahrenskalender {a.country}: {zahl['mit_terminen']:,} Leads mit Terminen "
          f"aus den Unterlagen (von {zahl['leads']:,} offenen)")
    print(f"  {geschrieben:,} Dateien neu geschrieben · {len(vorher):,} verwaiste entfernt")
    print(f"  {zahl['termine_gesamt']:,} Termine · {zahl['verworfen']:,} nicht zuzuordnen "
          f"und verworfen")
    for art, text in kalender.ARTEN.items():
        n = zahl.get(f"art_{art}", 0)
        if n:
            print(f"    {text:<32}{n:>7,}")
    gesamt = sum(q.stat().st_size for q in JE_VORGANG.glob("*.json"))
    print(f"→ {JE_VORGANG.relative_to(ROOT)}/ ({gesamt/1e6:.1f} MB in {len(aus):,} Dateien) "
          f"+ {INDEX.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
