#!/usr/bin/env python3
"""Zwei gleichzeitige Schreiber auf dasselbe Profil — verliert einer den anderen?

⚠ WARUM DAS NICHT STRUKTURELL ZU BEWEISEN IST. `tests/test_profilschreiber.py` prueft,
dass es genau EINEN Schreibweg gibt und dass der Patch minimal ist. Beides ist richtig und
beides sagt nichts darueber, was bei echter Nebenlaeufigkeit passiert: ob der Merge in der
Datenbank stattfindet oder im Client, sieht man dem Quelltext an — ob er unter Last haelt,
nicht.

Der Auftrag verlangt deshalb ausdruecklich „zwei Schreibvorgaenge absichtlich ueberlappen
lassen und belegen, dass keiner den anderen verliert". Genau das tut dieses Skript, gegen
die ECHTE Datenbank.

⚠ DER REALISTISCHE AUSLOESER SIND ZWEI TABS, kein konstruierter Testfall. Deshalb schreiben
beide Seiten VERSCHIEDENE Felder — so wie Onboarding (`saveProfile`) und Eignungs-Check
(`patchProfil`) es tun. Wer denselben Schluessel schreibt, misst nur, wer spaeter dran war.

    python3 scripts/pruefe_profil_nebenlaeufig.py            der eine Weg (merge_profile)
    python3 scripts/pruefe_profil_nebenlaeufig.py --alt      der alte Weg, zum Vergleich

⚠ Schreibt NUR in das Profil von `pruef@govisor.invalid` (scripts/pruefkonto.py). Fehlt
das Konto, bricht es ab, statt sich ein anderes zu suchen.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADRESSE = "pruef@govisor.invalid"
RUNDEN = 12


def env() -> dict[str, str]:
    e: dict[str, str] = {}
    for zeile in (ROOT / "web" / ".env.local").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*([A-Za-z_]+)\s*=\s*\"?([^\"\n]*)\"?", zeile)
        if m:
            e.setdefault(m.group(1), m.group(2))
    return e


def _curl(args: list[str]) -> str:
    return subprocess.run(["curl", "-s", *args], capture_output=True, text=True).stdout


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--alt", action="store_true",
                    help="den alten Weg nachstellen (lesen, aendern, ganzen Blob schreiben)")
    a = ap.parse_args(argv)

    e = env()
    url, key = e["NEXT_PUBLIC_SUPABASE_URL"].rstrip("/"), e["SUPABASE_SECRET_KEY"]
    kopf = ["-H", f"apikey: {key}", "-H", f"Authorization: Bearer {key}",
            "-H", "Content-Type: application/json"]

    nutzer = json.loads(_curl([*kopf, f"{url}/auth/v1/admin/users?per_page=200"]))
    uid = next((u["id"] for u in nutzer.get("users", [])
                if (u.get("email") or "").lower() == ADRESSE), None)
    if not uid:
        sys.exit(f"  ✖ {ADRESSE} gibt es nicht. Erst `python3 scripts/pruefkonto.py`.")

    # ⚠ ALS DER NUTZER ANMELDEN, NICHT MIT DEM DIENSTSCHLUESSEL. `merge_profile` traegt
    #    `security invoker` und trifft ueber `auth.uid()` genau die eigene Zeile — mit dem
    #    Dienstschluessel ist `auth.uid()` NULL und die Funktion aendert nichts. Ein Test,
    #    der sie so aufruft, saehe gruen aus, weil er GAR NICHTS misst.
    pw_datei = ROOT / ".secrets" / "pruefkonto.txt"
    if not pw_datei.exists():
        sys.exit("  ✖ .secrets/pruefkonto.txt fehlt. Erst `python3 scripts/pruefkonto.py`.")
    anmeldung = json.loads(_curl([
        "-X", "POST", "-H", f"apikey: {e['NEXT_PUBLIC_SUPABASE_ANON_KEY']}",
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"email": ADRESSE, "password": pw_datei.read_text().strip()}),
        f"{url}/auth/v1/token?grant_type=password"]))
    jeton = anmeldung.get("access_token")
    if not jeton:
        sys.exit(f"  ✖ Anmeldung fehlgeschlagen: {str(anmeldung)[:160]}")
    nutzerkopf = ["-H", f"apikey: {e['NEXT_PUBLIC_SUPABASE_ANON_KEY']}",
                  "-H", f"Authorization: Bearer {jeton}",
                  "-H", "Content-Type: application/json"]

    # ⚠ DER BLOB LIEGT SEIT MIGRATION 0025 IM AKTIVEN PROFIL, NICHT MEHR IN user_profiles.
    #
    # Gemessen am 2026-10-01: die Sonde meldete 12 von 12 Runden „verloren" — und zwar BEIDE
    # Felder, nicht eins gegen das andere. Das ist kein Wettlauf, sondern ein Schreibvorgang,
    # der dort landet, wo niemand liest. `merge_profile` schreibt seit 0025 nach
    # `profiles.profile`, sobald `active_profile_id` gesetzt ist (bei 13 von 13 Nutzern ist
    # sie es); die Sonde las weiter `user_profiles.profile`.
    #
    # ⚠ DAS WAR EIN FEHLALARM, ABER DER TEUERSTE DENKBARE: er behauptete Datenverlust in
    # einem Weg, der am 2026-09-17 wirklich einmal Daten verloren hat. Der Produktionscode
    # liest richtig (`web/lib/supabase/auth.ts:163` holt `profiles.profile`, wenn ein aktives
    # Profil gesetzt ist) — nur die Pruefung war stehen geblieben.
    #
    # Die Sonde folgt deshalb derselben Weiche wie auth.ts: aktives Profil, sonst Rueckfall.
    aktiv = None
    try:
        d = json.loads(_curl([*kopf,
            f"{url}/rest/v1/user_profiles?id=eq.{uid}&select=active_profile_id"]))
        aktiv = (d[0].get("active_profile_id") if d else None) or None
    except Exception:                                      # noqa: BLE001
        aktiv = None                                       # tolerant gegen den Stand vor 0024

    ziel = (f"profiles?id=eq.{aktiv}" if aktiv else f"user_profiles?id=eq.{uid}")

    def blob() -> dict:
        d = json.loads(_curl([*kopf, f"{url}/rest/v1/{ziel}&select=profile"]))
        return (d[0].get("profile") or {}) if d else {}

    def setze(p: dict) -> None:
        _curl(["-X", "PATCH", *kopf, "-d", json.dumps({"profile": p}),
               f"{url}/rest/v1/{ziel}"])

    def neu(feld: str, wert) -> None:
        """Ein Schreiber. `--alt` stellt den Zyklus nach, den dieser Commit abgeschafft hat."""
        if a.alt:
            vorher = blob()                    # LESEN
            time.sleep(0.15)                   # ⚠ das Fenster, um das es geht
            vorher[feld] = wert                # AENDERN
            setze(vorher)                      # ganzen Blob ZURUECKSCHREIBEN
        else:
            # Die ECHTE Funktion, ueber die ECHTE Anmeldung — so laeuft sie in der App.
            antwort = _curl(["-X", "POST", *nutzerkopf,
                             "-d", json.dumps({"p_patch": {feld: wert}}),
                             f"{url}/rest/v1/rpc/merge_profile"])
            # ⚠ Ein stiller Fehlschlag saehe aus wie ein verlorenes Feld — und man behebt
            #   dann die falsche Seite. `merge_profile` liefert nichts zurueck; alles
            #   andere ist ein Fehler und gehoert gesagt.
            if antwort.strip():
                print(f"      ⚠ merge_profile antwortete: {antwort.strip()[:120]}")

    print(f"  Weg: {'ALT (lesen-aendern-schreiben)' if a.alt else 'merge_profile (atomar)'}")
    print(f"  {RUNDEN} Runden, je zwei gleichzeitige Schreiber auf VERSCHIEDENE Felder\n")

    verloren = 0
    for i in range(RUNDEN):
        setze({"grundstand": i})               # sauberer Ausgangspunkt je Runde
        with ThreadPoolExecutor(max_workers=2) as tp:
            f1 = tp.submit(neu, "vom_onboarding", i)
            f2 = tp.submit(neu, "vom_check", i)
            f1.result(); f2.result()
        d = blob()
        ok = d.get("vom_onboarding") == i and d.get("vom_check") == i
        if not ok:
            verloren += 1
            fehlt = [k for k in ("vom_onboarding", "vom_check") if d.get(k) != i]
            print(f"    Runde {i + 1:>2}: ⚠ verloren → {', '.join(fehlt)}")
    print(f"\n  {RUNDEN - verloren} von {RUNDEN} Runden vollstaendig, {verloren} mit Verlust")
    setze({})
    return 1 if verloren else 0


if __name__ == "__main__":
    sys.exit(main())
