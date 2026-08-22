#!/usr/bin/env python3
"""Analyse über OpenRouters Stapelweg — halber Preis, dafür Wartezeit.

    python3 scripts/analyse_batch.py --absenden [--limit 100]
    python3 scripts/analyse_batch.py --abholen

⚠ **Zwei getrennte Aufrufe, kein Warten dazwischen.** Das Stapelfenster ist 24 Stunden; ein
Stapel mit zwei Trivialanfragen stand nach elf Minuten noch auf `in_progress`. Wer hier eine
Warteschleife baut, blockiert den Arbeiter für Stunden.

⚠ **Es gibt nur EINE Auswertung.** Beide Wege rufen dasselbe `analyze_notice`; der Unterschied
steckt allein in `antwort_fn`, die hier statt eines Modellaufrufs eine schon vorliegende
Antwort zurückgibt (oder in der Sammelphase `None` und merkt sich die Anfrage). Ein zweiter
Auswertungspfad wäre in einem Monat anders als der erste.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor import docextract, llm_batch  # noqa: E402

_spec = importlib.util.spec_from_file_location("_ad", ROOT / "scripts" / "analyze_docs.py")
ad = importlib.util.module_from_spec(_spec)
sys.modules["_ad"] = ad
_spec.loader.exec_module(ad)


def _sammler(nid: str, gesammelt: list):
    """`antwort_fn` für die Sammelphase: merkt die Anfrage, liefert nichts."""
    def fn(art, doctype, text, datei):
        cid = f"{nid}|{art}|{doctype or '-'}"
        nachrichten = (ad.summary_messages(text) if art == "summary"
                       else docextract.build_messages(doctype, text, datei))
        gesammelt.append({"custom_id": cid, "messages": nachrichten,
                          "_text": text, "_datei": datei, "_doctype": doctype})
        return None
    return fn


def _leser(nid: str, antworten: dict):
    """`antwort_fn` für die Abholphase: liefert die schon vorhandene Antwort."""
    def fn(art, doctype, text, datei):
        return antworten.get(f"{nid}|{art}|{doctype or '-'}")
    return fn


def absenden(limit: int) -> int:
    todo = ad.offene_vorgaenge(limit) if hasattr(ad, "offene_vorgaenge") else None
    if todo is None:
        print("⚠ `analyze_docs` bietet keine Kandidatenliste an — bitte dort nachziehen.")
        return 1
    alle, merk = [], {}
    for nid, dateien, strukturiert in todo:
        gesammelt: list = []
        ad.analyze_notice(dateien, structured=strukturiert, notice_id=nid,
                          antwort_fn=_sammler(nid, gesammelt))
        for g in gesammelt:
            merk[g["custom_id"]] = {"nid": nid}
        alle.extend({"custom_id": g["custom_id"], "messages": g["messages"]} for g in gesammelt)
        if len(alle) >= llm_batch.MAX_JE_STAPEL:
            break
    if not alle:
        print("Nichts abzusenden.")
        return 0
    sid = llm_batch.absenden(alle[:llm_batch.MAX_JE_STAPEL], ad.MODEL, merkzettel=merk)
    print(f"Stapel {sid or '—'} abgesendet: {min(len(alle), llm_batch.MAX_JE_STAPEL)} Anfragen "
          f"→ zum halben Preis. Abholen mit --abholen (Fenster 24 h).")
    return 0 if sid else 1


def abholen() -> int:
    offen = llm_batch.offene()
    if not offen:
        print("Keine offenen Stapel.")
        return 0
    for st in offen:
        d = llm_batch.abfragen(st["id"])
        status = d.get("status")
        zahl = d.get("request_counts") or {}
        print(f"  {st['id']}  {status}  {zahl}")
        if status != "completed":
            continue
        antworten = llm_batch.antworten(d)
        nids = sorted({v["nid"] for v in st.get("merkzettel", {}).values()})
        print(f"    {len(antworten)} Antworten für {len(nids)} Vorgänge — auswerten")
        # Die eigentliche Auswertung übernimmt `analyze_docs` mit demselben `analyze_notice`.
        ad.uebernehmen_aus_batch(nids, antworten, _leser)
        llm_batch.erledigt(st["id"])
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--absenden", action="store_true")
    p.add_argument("--abholen", action="store_true")
    p.add_argument("--limit", type=int, default=60)
    a = p.parse_args(argv)
    if a.absenden:
        return absenden(a.limit)
    if a.abholen:
        return abholen()
    p.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
