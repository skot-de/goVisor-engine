#!/usr/bin/env python3
"""Arbeitet Antwortauftraege ab: Fragebogen + Bausteine → Entwuerfe mit Beleg.

Die Rechenseite des Knopfs (Funktion 1 der Go-live-Liste). Die Weboberflaeche legt einen Auftrag
in `user_antwortauftrag` ab (Migration 0037), dieser Arbeiter holt ihn, rechnet und schreibt das
Ergebnis zurueck. Warum nicht in der Route: die Geldwache sitzt in `llm.chat()`, und
`spawn python3` haette die fuenfte nicht-serverless-faehige Route erzeugt — s. Kopf von 0037.

    scripts/antwort_arbeiter.py --einmal          # ein Durchlauf, fuer Tests und von Hand
    scripts/antwort_arbeiter.py --takt 30         # Dauerbetrieb, alle 30 s nachsehen

Umgebung (alle drei Pflicht, sonst Abbruch VOR dem ersten Auftrag):

    SUPABASE_URL, SUPABASE_SERVICE_KEY   Zugriff auf die Auftrags- und Bausteintabelle
    BLOCKS_KEK                           Hauptschluessel, 32 Byte base64

⚠ **DIE REIHENFOLGE IM LAUF IST EINE GELDBREMSE.** `versuche` wird hochgezaehlt und geschrieben,
**bevor** das Modell gefragt wird. Die Arbeiter pausieren nie (Auto-Memory
`govisor-speicherwand`); ein Auftrag, der nach dem LLM-Aufruf immer wieder scheitert, wuerde sonst
bei jedem Durchlauf erneut Geld kosten. Bei `MAX_VERSUCHE` ist Schluss, und zwar endgueltig.

⚠ **Ein Auftrag wird beansprucht, nicht nur gelesen.** Der Anspruch ist ein `PATCH` mit der
Bedingung `status=eq.offen`: laeuft versehentlich ein zweiter Arbeiter, bekommt genau einer die
Zeile und der andere eine leere Antwort. Ohne diese Bedingung zahlen zwei Arbeiter denselben
Auftrag zweimal.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from govisor import antwortvorschlag as av                      # noqa: E402
from govisor import blockcrypto as bc                           # noqa: E402

MAX_VERSUCHE = 3
# Ein Auftrag, der so lange auf `laeuft` steht, gehoert einem abgestuerzten Arbeiter. Grosszuegig
# bemessen: ein Bogen mit vielen Fragen braucht viele Modellaufrufe, und einen laufenden Auftrag
# einem zweiten Arbeiter zu geben kostet doppelt.
VERWAIST_MIN = 30
TABELLE = "user_antwortauftrag"


def _umgebung() -> tuple[str, str]:
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or ""
    if not url or not key:
        sys.exit("SUPABASE_URL und SUPABASE_SERVICE_KEY muessen gesetzt sein.")
    try:
        bc.hauptschluessel()
    except bc.KeinSchluessel as e:
        sys.exit(str(e))                 # frueh und laut: ohne Schluessel ist kein Auftrag loesbar
    return url, key


def _ruf(url: str, key: str, pfad: str, method: str = "GET", daten=None,
         erwarte_liste: bool = True):
    leib = json.dumps(daten).encode() if daten is not None else None
    anfrage = urllib.request.Request(f"{url}/rest/v1/{pfad}", data=leib, method=method)
    for k, v in (("apikey", key), ("Authorization", f"Bearer {key}"),
                 ("Content-Type", "application/json"), ("Prefer", "return=representation")):
        anfrage.add_header(k, v)
    try:
        with urllib.request.urlopen(anfrage, timeout=60) as a:
            roh = a.read().decode()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {pfad} → {e.code}: {e.read().decode()[:300]}") from None
    if not roh.strip():
        return [] if erwarte_liste else None
    return json.loads(roh)


def _beanspruche(url: str, key: str) -> dict | None:
    """Holt genau einen Auftrag und markiert ihn als laufend. `None` heisst: nichts zu tun."""
    offen = _ruf(url, key, f"{TABELLE}?status=eq.offen&order=erstellt_at.asc&limit=1")
    if not offen:
        grenze = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                               time.gmtime(time.time() - VERWAIST_MIN * 60))
        offen = _ruf(url, key,
                     f"{TABELLE}?status=eq.laeuft&geholt_at=lt.{grenze}"
                     f"&order=erstellt_at.asc&limit=1")
        if not offen:
            return None
        print(f"  verwaister Auftrag wird erneut genommen: {offen[0]['id']}")
    auftrag = offen[0]

    # ⚠ Die Bedingung auf den ALTEN Status ist der eigentliche Anspruch. Ohne sie nehmen zwei
    #   Arbeiter dieselbe Zeile und zahlen sie zweimal.
    alt = auftrag["status"]
    frisch = _ruf(url, key, f"{TABELLE}?id=eq.{auftrag['id']}&status=eq.{alt}", "PATCH",
                  {"status": "laeuft", "geholt_at": "now()",
                   "versuche": int(auftrag.get("versuche") or 0) + 1})
    return frisch[0] if frisch else None


def _bausteine(url: str, key: str, profil_id: str) -> list[dict]:
    """Die nicht archivierten Bausteine des Profils, entschluesselt.

    ⚠ Ein Baustein, der sich nicht entschluesseln laesst, wird **uebersprungen und gemeldet** —
    nicht weggeworfen und nicht als leerer Text weitergegeben. Ein leerer Baustein saehe wie ein
    gepflegter aus, der nichts hergibt, und die Frage bliebe unbeantwortet, ohne dass jemand den
    Grund erfaehrt.
    """
    zeilen = _ruf(url, key,
                  f"profile_text_blocks?profile_id=eq.{profil_id}&archived=eq.false"
                  f"&select=id,theme,content_encrypted,keywords")
    raus, kaputt = [], 0
    for z in zeilen:
        try:
            raus.append({"id": z["id"], "theme": z.get("theme"),
                         "content": bc.entschluessele(bc.aus_hex(z["content_encrypted"])),
                         "keywords": z.get("keywords") or []})
        except Exception:
            kaputt += 1
    if kaputt:
        print(f"  ⚠ {kaputt} Baustein(e) nicht entschluesselbar, uebersprungen")
    return raus


def _fertig(url: str, key: str, auftrag_id: str, ergebnis: dict) -> None:
    nutzlast = json.dumps(ergebnis, ensure_ascii=False)
    _ruf(url, key, f"{TABELLE}?id=eq.{auftrag_id}", "PATCH", {
        "status": "fertig",
        "ergebnis_encrypted": bc.zu_hex(bc.verschluessele(nutzlast)),
        "zaehlung": ergebnis["zaehlung"],
        "fragen_gesamt": ergebnis["fragen_gesamt"],
        "fertig_at": "now()", "fehler": None})


def _gescheitert(url: str, key: str, auftrag: dict, grund: str) -> None:
    """Zurueck auf `offen`, solange Versuche bleiben — sonst endgueltig `fehler`."""
    endgueltig = int(auftrag.get("versuche") or 0) >= MAX_VERSUCHE
    _ruf(url, key, f"{TABELLE}?id=eq.{auftrag['id']}", "PATCH", {
        "status": "fehler" if endgueltig else "offen",
        "fehler": grund[:500],
        **({"fertig_at": "now()"} if endgueltig else {})})
    print(f"  {'aufgegeben' if endgueltig else 'zurueck in die Schlange'}: {grund[:160]}")


def bearbeite(url: str, key: str, auftrag: dict) -> bool:
    """Einen Auftrag rechnen. `True`, wenn er fertig wurde."""
    aid = auftrag["id"]
    print(f"Auftrag {aid} (Versuch {auftrag.get('versuche')}, Datei {auftrag.get('dateiname')!r})")
    if int(auftrag.get("versuche") or 0) > MAX_VERSUCHE:
        _gescheitert(url, key, auftrag, f"mehr als {MAX_VERSUCHE} Versuche")
        return False
    try:
        bogen = bc.entschluessele(bc.aus_hex(auftrag["fragebogen_encrypted"]))
        fragen = av.fragen_aus_text(bogen)
        if not fragen:
            # Kein Fehler des Arbeiters: der Bogen gab keine Frage her. Das ist ein ERGEBNIS
            # und muss als solches zurueck, sonst laeuft der Auftrag drei Mal gegen dieselbe Wand.
            _fertig(url, key, aid, {"vorschlaege": [], "fragen_gesamt": 0, "fertig": 0,
                                    "zaehlung": {"fertig": 0, "unbelegt": 0, "kein_baustein": 0},
                                    "hinweis": "Im Bogen wurde keine Frage erkannt."})
            print("  keine Frage erkannt — als Ergebnis vermerkt")
            return True
        bausteine = _bausteine(url, key, auftrag["profil_id"])
        if not bausteine:
            _fertig(url, key, aid, {
                "vorschlaege": [], "fragen_gesamt": len(fragen), "fertig": 0,
                "zaehlung": {"fertig": 0, "unbelegt": 0, "kein_baustein": len(fragen)},
                "hinweis": "Keine Bausteine im Profil — ohne sie gibt es keine belegten Entwuerfe."})
            print(f"  {len(fragen)} Fragen, aber keine Bausteine")
            return True

        print(f"  {len(fragen)} Fragen, {len(bausteine)} Bausteine")
        ergebnis = av.vorschlaege(fragen, bausteine)
        _fertig(url, key, aid, ergebnis)
        z = ergebnis["zaehlung"]
        print(f"  fertig: {z['fertig']} belegt, {z['unbelegt']} unbelegt, "
              f"{z['kein_baustein']} ohne Baustein")
        return True
    except Exception as e:                                   # noqa: BLE001 — Grund wandert mit
        _gescheitert(url, key, auftrag, f"{type(e).__name__}: {e}")
        return False


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--einmal", action="store_true", help="einen Durchlauf, dann beenden")
    p.add_argument("--takt", type=int, default=30, help="Sekunden zwischen den Durchlaeufen")
    p.add_argument("--hoechstens", type=int, default=0,
                   help="nach so vielen Auftraegen beenden (0 = ohne Grenze)")
    a = p.parse_args()

    url, key = _umgebung()
    getan = 0
    while True:
        auftrag = _beanspruche(url, key)
        if auftrag:
            bearbeite(url, key, auftrag)
            getan += 1
            if a.hoechstens and getan >= a.hoechstens:
                print(f"{getan} Auftraege, Grenze erreicht.")
                return 0
            continue                                   # gleich nachsehen, es koennte mehr geben
        if a.einmal:
            if not getan:
                print("Nichts zu tun.")
            return 0
        time.sleep(a.takt)


if __name__ == "__main__":
    raise SystemExit(main())
