#!/usr/bin/env python3
"""Welche Vorgangsakten ändern sich wirklich — und wie alt sind sie?

Schritt 2 aus `docs/effizienz-plan.md`. Die Frage ist eng und entscheidet über P2:

    Werden alte Akten je wieder angefasst?

Wenn nein, lohnt ein Bündelschlüssel mit Altersstufe: die ~77 % alten Akten lägen dann in
Bündeln, die einmal geschrieben und nie wieder berührt werden. Wenn ja, fällt P2 ersatzlos
weg — und zwei Tage Umbau sind gespart.

⚠ **WARUM ZWEI AUFNAHMEN NÖTIG SIND.** Die Frage lässt sich aus einem Stand nicht
beantworten. Zeitstempel taugen nicht: sie sagen, welche DATEI geschrieben wurde, nicht
welche AKTE sich geändert hat — und ein Bündel wird schon wegen einer einzigen von rund
dreizehn Akten neu geschrieben. Am 2026-09-04 kam dazu, dass ein Lauf von Hand um 07:57
sämtliche Archiv-Bündel anfasste; die Zeitstempel waren damit als Signal wertlos.

Deshalb: je Akte eine Prüfsumme, zweimal aufgenommen, dann verglichen. Was sich zwischen
zwei Ständen ändert, ist die Antwort.

Aufruf::

    scripts/messe_buendel_drift.py --aufnehmen          # Stand festhalten
    scripts/messe_buendel_drift.py --vergleichen        # gegen den letzten Stand
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import re
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUELLEN = ("vorgang", "vorgang-archiv")
# Die Aufnahmen liegen in `data/`, nicht in `web/data`: sie sind Betriebswissen und kein
# Ausliefergut — dieselbe Trennung wie beim Kalender-Manifest und den Sicherungen.
AUFNAHMEN = ROOT / "data" / "messungen"
# Ab wann eine Akte als „alt" gilt. Zwei Jahre, weil dort die Vergabefristen sicher
# durch sind und ein Nachtrag unwahrscheinlich wird.
ALT_AB_TAGEN = 730


def _juengste_schreibzeit() -> float:
    """Wann wurde zuletzt an einem Bündel geschrieben?"""
    juengste = 0.0
    for quelle in QUELLEN:
        verzeichnis = ROOT / "web" / "data" / quelle
        if not verzeichnis.is_dir():
            continue
        for datei in verzeichnis.glob("*.json"):
            juengste = max(juengste, datei.stat().st_mtime)
    return juengste


# Prozesse, die an den Buendeln bauen. Wer laeuft, darf nicht vermessen werden.
SCHREIBER = ("export_vorgaenge", "build_vorgaenge", "daily_leads")


def _wer_baut() -> list[str]:
    """Laeuft gerade jemand, der Buendel schreiben koennte?"""
    import subprocess
    try:
        roh = subprocess.run(["ps", "-ax", "-o", "pid=,command="],
                             capture_output=True, text=True, timeout=20).stdout
    except Exception:                                       # noqa: BLE001
        return ["ps nicht lesbar — im Zweifel warten"]
    treffer = []
    for zeile in roh.splitlines():
        if not any(w in zeile for w in SCHREIBER):
            continue
        if "messe_buendel_drift" in zeile:
            continue
        # ⚠ HUELLEN SIND KEINE PROZESSE — dieselbe Regel wie in `scripts/laeuft_was.sh`.
        # Eine Zeile der Form `<shell> -c '<grosser String>'` ENTHAELT den Namen, fuehrt ihn
        # aber nicht aus. Am 2026-09-04 hielt genau so eine Huelle diese Wache auf: der
        # Tageslauf war seit zwanzig Minuten fertig, die zsh-Huelle, aus der er gestartet
        # wurde, stand noch in `ps` — und die Aufnahme wartete weiter auf einen Lauf, den es
        # nicht mehr gab. Das echte Kind laeuft ohnehin als eigene Zeile mit.
        if re.search(r"^\s*\d+\s+\S*(ba|z|k)?sh\s+-c\s", zeile):
            continue
        treffer.append(zeile.strip()[:100])
    return treffer


def warte_auf_ruhe(ruhe_s: int = 600, geduld_s: int = 21600) -> bool:
    """Erst aufnehmen, wenn niemand mehr schreibt.

    ⚠ WARUM DAS HIER STEHT UND NICHT IM KOPF DES BEDIENERS. Eine Aufnahme mitten in einem
    Export mischt zwei Staende: ein Teil der Buendel neu, der Rest alt. Der spaetere
    Vergleich zeigt dann Aenderungen, die es nie gab — und die Zahl, die ueber P2 entscheidet,
    waere frei erfunden.

    ⚠ EINE RUHEFRIST ALLEIN REICHT NICHT — das hat der erste Entwurf teuer gelernt. Er
    verlangte drei Minuten Stille und liess eine Aufnahme durch, die MITTEN in einem
    Archiv-Neuaufbau lag: 601.260 Akten festgehalten, wo am Ende 1.734.199 standen. Der
    Export pausiert zwischen seinen Abschnitten laenger, als die Frist lang war; Stille
    heisst eben „gerade schreibt niemand", nicht „es ist fertig".

    Deshalb zwei Bedingungen, nicht eine: zehn Minuten ohne Schreibzugriff UND kein Prozess,
    der bauen koennte. Die zweite ist die eigentliche; die erste faengt nur ab, was `ps`
    nicht sieht (ein Unterprozess zwischen zwei Aufrufen etwa).
    """
    import time
    frist = time.time() + geduld_s
    while time.time() < frist:
        still = time.time() - _juengste_schreibzeit()
        baut = _wer_baut()
        if still >= ruhe_s and not baut:
            print(f"  Ruhe: seit {still/60:.0f} min kein Schreibzugriff, kein Bauprozess.")
            return True
        grund = (f"laeuft: {baut[0]}" if baut
                 else f"letzter Schreibzugriff vor {still/60:.1f} min (noetig: {ruhe_s/60:.0f})")
        # ⚠ `flush=True`, WEIL DIESE ZEILE DURCH EINE PIPE GEHT. Python puffert dann
        # blockweise: die Wartemeldungen erschienen erst am Ende — eine Wache, die nichts
        # sagt, sieht aus wie ein Haenger, und man bricht sie ab.
        print(f"  ⏳ {grund}", flush=True)
        time.sleep(120)
    print("  ✖ Keine Ruhe innerhalb der Geduld. Abgebrochen.", file=sys.stderr)
    return False


def _juengstes_datum(akte: dict) -> dt.date | None:
    """Wann ist an dieser Akte zuletzt etwas passiert?

    ⚠ NICHT „bis". Der erste Entwurf las nur `bis` und `von` — also die Vertragslaufzeit.
    Das ist das falsche Alter fuer diese Frage. Beispiel aus dem Bestand: eine Akte mit
    `bis: 2023-06-30` waere damit „aelter als 2 Jahre", auch wenn 2026 noch ein Zuschlag
    dazukam. Genau solche Akten aendern sich aber — und sie sind der Grund, aus dem P2
    scheitern koennte. Haette ich das nicht bemerkt, haette die Messung Bewegung bei alten
    Akten gefunden, die in Wahrheit gar nicht alt sind, und P2 zu Unrecht beerdigt.

    Also: das juengste Datum aus Laufzeit UND `verlauf` (Bekanntmachung, Zuschlag,
    Korrektur). Die Akte ist so alt wie ihr letztes Lebenszeichen.
    """
    juengstes = None

    def _nimm(wert) -> None:
        nonlocal juengstes
        if isinstance(wert, str) and len(wert) >= 10:
            try:
                d = dt.date.fromisoformat(wert[:10])
            except ValueError:
                return
            if juengstes is None or d > juengstes:
                juengstes = d

    for feld in ("bis", "von"):
        _nimm(akte.get(feld))
    for schritt in akte.get("verlauf") or ():
        if isinstance(schritt, dict):
            _nimm(schritt.get("datum"))
    return juengstes


def aufnehmen() -> dict:
    """Je Akte: Prüfsumme des Inhalts und ihr jüngstes Datum."""
    heute = dt.date.today()
    stand: dict[str, dict] = {}
    for quelle in QUELLEN:
        verzeichnis = ROOT / "web" / "data" / quelle
        if not verzeichnis.is_dir():
            continue
        akten: dict[str, list] = {}
        for datei in sorted(verzeichnis.glob("*.json")):
            try:
                buendel = json.loads(datei.read_text(encoding="utf-8"))
            except Exception:                                   # noqa: BLE001
                continue
            for kennung, akte in buendel.items():
                # Prüfsumme über den INHALT, nicht über die Datei: nur so unterscheidet
                # sich „das Bündel wurde geschrieben" von „diese Akte hat sich geändert".
                roh = json.dumps(akte, ensure_ascii=False, sort_keys=True)
                pruef = hashlib.sha1(roh.encode("utf-8")).hexdigest()[:12]
                datum = _juengstes_datum(akte)
                alter = (heute - datum).days if datum else None
                akten[kennung] = [pruef, alter]
        stand[quelle] = akten
    return stand


def _alterstufe(tage: int | None) -> str:
    if tage is None:
        return "ohne Datum"
    if tage > ALT_AB_TAGEN:
        return "aelter als 2 Jahre"
    if tage > 90:
        return "90 Tage bis 2 Jahre"
    return "letzte 90 Tage"


def vergleichen(alt: dict, neu: dict) -> int:
    """Was hat sich geändert, und wie alt war es?"""
    befund = 0
    for quelle in QUELLEN:
        a, n = alt.get(quelle) or {}, neu.get(quelle) or {}
        if not a or not n:
            continue
        # ⚠ ZWEI STAENDE UNGLEICHER GROESSE SIND KEIN VERGLEICH. Am 2026-09-04 standen im
        # Archiv erst 601.260, dann 1.734.199 Akten — die erste Aufnahme lag mitten im
        # Neuaufbau. Der Vergleich meldete brav „0,00 % geaendert" und war wertlos: was noch
        # gar nicht geschrieben war, kann sich auch nicht geaendert haben. Also laut sagen,
        # statt eine schoene Zahl auszugeben.
        if a and abs(len(n) - len(a)) / len(a) > 0.2:
            print(f"\n  ⚠ {quelle}: die Aktenzahl bewegte sich um "
                  f"{(len(n)-len(a))/len(a):+.0%} ({len(a):,} → {len(n):,}). Das ist kein "
                  f"Tagesgeschaeft, sondern ein Neuaufbau — die folgenden Quoten sagen "
                  f"nichts ueber taegliche Drift.")
            befund = 1
            neuaufbau = True
        else:
            neuaufbau = False
        gemeinsam = a.keys() & n.keys()
        geaendert = {k for k in gemeinsam if a[k][0] != n[k][0]}
        print(f"\n  ── {quelle} ──")
        print(f"    {len(a):,} → {len(n):,} Akten · "
              f"{len(n.keys() - a.keys()):,} neu · {len(a.keys() - n.keys()):,} weg")
        print(f"    geaendert: {len(geaendert):,} von {len(gemeinsam):,} "
              f"({len(geaendert)/max(len(gemeinsam),1):.2%})")

        bestand = collections.Counter(_alterstufe(n[k][1]) for k in gemeinsam)
        drift = collections.Counter(_alterstufe(n[k][1]) for k in geaendert)
        print(f"\n    {'Alterstufe':<24}{'im Bestand':>12}{'geaendert':>11}{'Quote':>9}")
        for stufe in ("letzte 90 Tage", "90 Tage bis 2 Jahre", "aelter als 2 Jahre",
                      "ohne Datum"):
            b, d = bestand.get(stufe, 0), drift.get(stufe, 0)
            if not b:
                continue
            print(f"    {stufe:<24}{b:>12,}{d:>11,}{d/b:>9.2%}")

        # ⚠ DIE EINE ZAHL, UM DIE ES GEHT. Aendern sich alte Akten praktisch nie, traegt P2;
        # aendern sie sich regelmaessig, faellt P2 — und der Umbau bleibt ungebaut.
        alt_ges = bestand.get("aelter als 2 Jahre", 0)
        alt_drift = drift.get("aelter als 2 Jahre", 0)
        if neuaufbau:
            # Kein Urteil aus einem Vergleich, der oben gerade fuer wertlos erklaert wurde.
            print("\n    → kein Urteil: die beiden Staende sind nicht vergleichbar.")
        elif alt_ges:
            quote = alt_drift / alt_ges
            print(f"\n    → alte Akten aendern sich zu {quote:.3%}")
            if quote < 0.001:
                print("      P2 traegt: eine Alterstufe im Schluessel wuerde sie verschonen.")
            else:
                print("      ⚠ P2 traegt NICHT: auch Altes bewegt sich, eine Alterstufe")
                print("        wuerde die Naechte kaum entlasten.")
                befund = 1
    return befund


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--aufnehmen", action="store_true", help="Stand festhalten")
    ap.add_argument("--vergleichen", action="store_true", help="gegen den letzten Stand")
    ap.add_argument("--jetzt", action="store_true",
                    help="ohne auf Ruhe zu warten (nur wenn sicher niemand schreibt)")
    a = ap.parse_args(argv)
    if not (a.aufnehmen or a.vergleichen):
        ap.error("--aufnehmen oder --vergleichen")

    AUFNAHMEN.mkdir(parents=True, exist_ok=True)
    vorhanden = sorted(AUFNAHMEN.glob("buendel-*.json"))

    if a.vergleichen:
        if not vorhanden:
            print("  ✖ Keine frühere Aufnahme. Erst `--aufnehmen`, dann einen Lauf abwarten.",
                  file=sys.stderr)
            return 1
        alt = json.loads(vorhanden[-1].read_text(encoding="utf-8"))
        print(f"  Vergleich gegen {vorhanden[-1].name}")
        # Dieselbe Wache wie bei der Aufnahme: gegen einen halb geschriebenen Stand zu
        # vergleichen liefert genau die Zahl, die niemand nachvollziehen kann.
        if not a.jetzt and not warte_auf_ruhe():
            return 1
        return vergleichen(alt, aufnehmen())

    if not a.jetzt and not warte_auf_ruhe():
        return 1
    vorher = _juengste_schreibzeit()
    stand = aufnehmen()
    if _juengste_schreibzeit() > vorher:
        print("  ✖ Waehrend der Aufnahme wurde geschrieben — der Stand ist zerrissen, "
              "nichts gespeichert.", file=sys.stderr)
        return 1
    marke = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    ziel = AUFNAHMEN / f"buendel-{marke}.json"
    ziel.write_text(json.dumps(stand, separators=(",", ":")), encoding="utf-8")
    gesamt = sum(len(v) for v in stand.values())
    print(f"  Aufnahme: {gesamt:,} Akten aus {len(stand)} Quellen → "
          f"{ziel.relative_to(ROOT)} ({ziel.stat().st_size/1e6:.0f} MB)")
    print("  Nach dem naechsten Lauf: scripts/messe_buendel_drift.py --vergleichen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
