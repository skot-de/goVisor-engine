"""Was ein Upload veröffentlicht — und die Sperre, die dafür gebaut, aber nie angeschlossen wurde.

Gemessen am 2026-09-04:

    /api/lead-docs      jeder angemeldete Nutzer, beliebige notice_id, keine Nutzerpruefung
          ↓
    process_upload.py   schreibt web/data/doc-analysis/<id>.json  (GETEILTE Produktdaten)
          ↓
    /api/lead-detail    liest genau die und zeigt sie ALLEN Nutzern dieses Leads

`govisor/docsafety.py` ist gegen genau diesen Fall geschrieben (§12.2: „im selben Lead
sitzen konkurrierende Bieter, eine manipulierte Checkliste kann Wettbewerber schädigen") —
und ist das einzige Modul in `govisor/`, das ausserhalb seines eigenen Tests niemand aufruft.
"""
import json
import random
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ANALYSEN = ROOT / "web" / "data" / "doc-analysis"


def test_beide_enden_nennen_den_ruhenden_zustand():
    """Eine Lücke, die niemand mehr sieht, wird zur Eigenschaft.

    Deshalb steht sie an BEIDEN Enden: im Modul, das schläft, und an der Zeile, die
    veröffentlicht. Wer eines von beiden anfasst, liest das andere.
    """
    kopf = (ROOT / "govisor" / "docsafety.py").read_text(encoding="utf-8")
    assert "RUHEND" in kopf and "visibility_after" in kopf, (
        "govisor/docsafety.py benennt seinen Ruhezustand nicht mehr")
    schreib = (ROOT / "scripts" / "process_upload.py").read_text(encoding="utf-8")
    assert "docsafety" in schreib, (
        "Die Schreibstelle in process_upload.py nennt die fehlende Sperre nicht mehr — dann "
        "sieht der naechste Leser eine gewoehnliche Zeile.")


def test_der_anker_der_sperre_ist_noch_da():
    """⚠ DIE ZAHL, AN DER DIE ENTSCHEIDUNG HAENGT — und die still altern wuerde.

    `visibility_after()` haengt an `deadline_exact`: dem exakten Vergleich der Angebotsfrist
    aus dem Dokument mit der aus TED/DÖE. Das Modul nennt sie selbst „den stabilsten Anker".
    Gemessen am 2026-09-04 an 400 zufaelligen Analysen: **268 (67 %)** tragen ein Datum in
    `fristen[].wert`. Die Sperre ist damit baubar — und genau das steht als Begruendung im
    Kopf von `govisor/docsafety.py`.

    Faellt der Anteil, stimmt diese Begruendung nicht mehr, und wer sie liest, plant auf
    einer Zahl von gestern. Deshalb steht sie hier als Pruefung und nicht nur als Satz.

    ⚠ Beim ersten Messen danebengegriffen: die Suche ging auf ein Feld `datum`, das es nicht
    gibt, und meldete 0 von 400. Daraus waere der Schluss „die Sperre kann gar nicht tragen"
    geworden — die bequemste aller falschen Antworten. Die Werte stehen unter `wert`.
    """
    if not ANALYSEN.is_dir():
        pytest.skip("keine Analysen vorhanden (frische Arbeitskopie)")
    dateien = sorted(ANALYSEN.glob("*.json"))
    if len(dateien) < 50:
        pytest.skip(f"zu wenige Analysen fuer eine Aussage ({len(dateien)})")
    random.seed(7)
    probe = random.sample(dateien, min(400, len(dateien)))
    datum = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4}")
    mit = 0
    for f in probe:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:                                   # noqa: BLE001
            continue
        eintraege = d.get("fristen")
        if isinstance(eintraege, list) and any(
                isinstance(e, dict) and datum.search(str(e.get("wert") or ""))
                for e in eintraege):
            mit += 1
    anteil = mit / len(probe)
    assert anteil >= 0.40, (
        f"Nur noch {anteil:.0%} der Analysen tragen ein Fristdatum ({mit} von {len(probe)}), "
        "am 2026-09-04 waren es 67 %. Der Anker von `docsafety.visibility_after()` traegt "
        "damit nicht mehr — die Begruendung im Kopf von govisor/docsafety.py stimmt nicht "
        "mehr und gehoert berichtigt, BEVOR jemand darauf baut.")
