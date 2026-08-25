#!/usr/bin/env python3
"""Qualitätsschranke: nach jeder Etappe des Rückstau-Abbaus prüfen, ob noch alles stimmt.

Sven, 2026-08-24: *„lass den rückstau abarbeiten bis das budget leer ist, aber setz alle 5
oder 10 $ qualitygates wo du auch dein modul hier nochmal prüfst."*

**Warum es das als Werkzeug gibt und nicht als Gewohnheit.** „Ich schaue kurz drüber" ist
bei jeder Etappe etwas anderes und übersieht genau das, was sich langsam verschiebt. Diese
Schranke misst **immer dieselben sieben Dinge** und vergleicht sie mit der Voretappe.
Verschiebungen fallen dadurch auf, auch wenn jede einzelne Etappe für sich plausibel aussah.

Das ist keine Theorie: am 2026-08-24 lief `:floor` bei 304 von 311 Aufrufen ins Leere und
wir zahlten 48 % zu viel. Der Kontostand fiel dabei völlig plausibel. Aufgefallen ist es
erst beim Nachrechnen einzelner Zeilen.

**Die sieben Prüfungen:**

1. **Tarif** — welcher Anteil der Aufrufe lief zum Bodenpreis? Unter 95 % ist der
   Preisdeckel undicht.
2. **Abgleich** — Kostenbuch gegen OpenRouters Abrechnung. Über 10 % Lücke heißt: es gibt
   Geldabfluss, den wir nicht sehen.
3. **Ausbeute** — belegte Punkte je Vergabe gegen die Voretappe. Ein Einbruch ist der erste
   Hinweis auf ein stillschweigend verändertes Modell.
4. **Verwerfungsquote** — die ehrlichere Zahl: steigt sie, behauptet das Modell mehr, als
   es belegt.
5. **Formatfehler und leere Antworten** — beide kosten Geld ohne Ertrag.
6. **Stückkosten** — je Vergabe. Steigen sie ohne Tarifwechsel, werden die Antworten länger.
7. **Testsuite** — grün, sonst ist alles andere Makulatur.

Der Verlauf liegt in ``data/qualitaetsschranken.jsonl``, eine Zeile je Etappe.

Aufruf::

    scripts/qualitaetsschranke.py               # prüfen und Etappe festhalten
    scripts/qualitaetsschranke.py --nur-lesen   # prüfen, ohne den Verlauf fortzuschreiben
    scripts/qualitaetsschranke.py --verlauf     # alle Etappen nebeneinander
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import kostenbuch, llm  # noqa: E402

VERLAUF = ROOT / "data" / "qualitaetsschranken.jsonl"
ANALYSE = ROOT / "web" / "data" / "doc-analysis.json"

# Schwellen. Reissen heisst nicht „sofort anhalten", sondern „hinsehen, bevor es
# weitergeht" — deshalb steht bei jedem Befund, was er bedeutet.
MIN_BODENANTEIL = 0.95
MAX_LUECKE = 0.10
MAX_AUSBEUTE_VERLUST = 0.15
MAX_VERWERFUNG_ANSTIEG = 0.05
MAX_STUECKKOSTEN_ANSTIEG = 0.30


def _zeilen_seit(ts: str | None) -> list[dict]:
    return [z for z in kostenbuch.lies()
            if z.get("zweck") == "analyse" and (not ts or (z.get("ts") or "") > ts)]


def _tarifanteil(zeilen: list[dict]) -> tuple[float, int, int]:
    """Anteil der Aufrufe, die zum Bodenpreis des jeweiligen Modells liefen."""
    treffer = gesamt = 0
    deckel: dict[str, tuple[float, float] | None] = {}
    for z in zeilen:
        if z.get("kosten_usd") is None:
            continue
        m = z.get("modell") or ""
        if m not in deckel:
            deckel[m] = llm.bodendeckel(m)
        b = deckel[m]
        if not b:
            continue
        gesamt += 1
        soll = (z.get("eingabe_token") or 0) * b[0] / 1e6 + \
               (z.get("ausgabe_token") or 0) * b[1] / 1e6
        if abs(float(z["kosten_usd"]) - soll) < 1e-8:
            treffer += 1
    return (treffer / gesamt if gesamt else 0.0), treffer, gesamt


def _ausbeute(seit: str | None) -> tuple[float, float, int]:
    """(Punkte je Vergabe, Verwerfungsquote, Anzahl) der seit `seit` analysierten Vergaben."""
    if not ANALYSE.exists():
        return 0.0, 0.0, 0
    daten = json.loads(ANALYSE.read_text(encoding="utf-8"))
    # ⚠ In Ortszeit, weil `analysiert_am` in Ortszeit steht. Der rohe UTC-Praefix haette
    # an der Tagesgrenze die falschen Vergaben in die Etappe gezogen.
    tag = (kostenbuch.lokaler_tag({"ts": seit}) or (seit or "")[:10]) if seit else ""
    ids = {z["vorgang"] for z in _zeilen_seit(seit) if z.get("vorgang")}
    passend = [v for k, v in daten.items()
               if k in ids or (not ids and (v.get("analysiert_am") or "") >= tag)]
    if not passend:
        return 0.0, 0.0, 0
    zit = sum(sum(1 for e in (v.get("checklist") or [])
                  if not e.get("parser") and e.get("marking") == "Zitat") for v in passend)
    vw = sum(v.get("rejected_items") or 0 for v in passend)
    return zit / len(passend), vw / max(zit + vw, 1), len(passend)


def _tests() -> tuple[bool, str]:
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
                       cwd=ROOT, capture_output=True, text=True, timeout=900)
    letzte = [z for z in r.stdout.strip().splitlines() if z.strip()][-1:] or ["?"]
    return r.returncode == 0, letzte[0].strip()


def _vorherige() -> dict | None:
    if not VERLAUF.exists():
        return None
    zeilen = [json.loads(z) for z in VERLAUF.read_text(encoding="utf-8").splitlines() if z.strip()]
    return zeilen[-1] if zeilen else None


def messe() -> dict:
    vor = _vorherige()
    seit = vor["ts"] if vor else None
    zeilen = _zeilen_seit(seit)
    anteil, treffer, gesamt = _tarifanteil(zeilen)
    punkte, verwerfung, n = _ausbeute(seit)
    kosten = sum(float(z["kosten_usd"]) for z in zeilen if z.get("kosten_usd") is not None)
    return {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seit": seit,
        "aufrufe": len(zeilen),
        "vergaben": n,
        "usd": round(kosten, 5),
        "usd_je_vergabe": round(kosten / n, 5) if n else None,
        "bodenanteil": round(anteil, 4),
        "boden_treffer": treffer, "boden_gesamt": gesamt,
        "punkte_je_vergabe": round(punkte, 2),
        "verwerfung": round(verwerfung, 4),
        "leer": sum(1 for z in zeilen if z.get("leer")),
        "abgebrochen": sum(1 for z in zeilen if z.get("abgebrochen")),
        "ohne_preis": sum(1 for z in zeilen if z.get("kosten_usd") is None),
    }


def bewerte(jetzt: dict, vor: dict | None, luecke: float | None,
            tests_gruen: bool) -> list[tuple[str, str]]:
    """Gibt [(Ampel, Text)] — 'rot' verlangt Hinsehen, bevor es weitergeht."""
    aus: list[tuple[str, str]] = []
    a = jetzt["bodenanteil"]
    if jetzt["boden_gesamt"] and a < MIN_BODENANTEIL:
        aus.append(("rot", f"nur {a:.0%} der Aufrufe zum Bodenpreis "
                           f"({jetzt['boden_treffer']}/{jetzt['boden_gesamt']}) — "
                           f"der Preisdeckel ist undicht"))
    else:
        aus.append(("grün", f"{a:.0%} der Aufrufe zum Bodenpreis"))

    if luecke is not None:
        if abs(luecke) > MAX_LUECKE:
            aus.append(("rot", f"{luecke:+.0%} Abweichung zwischen Buch und Abrechnung"))
        else:
            aus.append(("grün", f"Buch und Abrechnung stimmen ({luecke:+.1%})"))

    if vor and vor.get("punkte_je_vergabe"):
        d = (jetzt["punkte_je_vergabe"] - vor["punkte_je_vergabe"]) / vor["punkte_je_vergabe"]
        if d < -MAX_AUSBEUTE_VERLUST:
            aus.append(("rot", f"Ausbeute {jetzt['punkte_je_vergabe']:.1f} statt "
                               f"{vor['punkte_je_vergabe']:.1f} ({d:+.0%}) — Modell prüfen"))
        else:
            aus.append(("grün", f"Ausbeute {jetzt['punkte_je_vergabe']:.1f} Punkte/Vergabe "
                                f"({d:+.0%})"))
        dv = jetzt["verwerfung"] - vor["verwerfung"]
        if dv > MAX_VERWERFUNG_ANSTIEG:
            aus.append(("rot", f"Verwerfung {jetzt['verwerfung']:.0%} statt "
                               f"{vor['verwerfung']:.0%} — behauptet mehr, als es belegt"))
        else:
            aus.append(("grün", f"Verwerfung {jetzt['verwerfung']:.0%} ({dv:+.1%})"))
        if vor.get("usd_je_vergabe") and jetzt.get("usd_je_vergabe"):
            dk = (jetzt["usd_je_vergabe"] - vor["usd_je_vergabe"]) / vor["usd_je_vergabe"]
            aus.append((("rot" if dk > MAX_STUECKKOSTEN_ANSTIEG else "grün"),
                        f"Stückkosten {jetzt['usd_je_vergabe']:.4f} $/Vergabe ({dk:+.0%})"))
    else:
        aus.append(("grau", f"Ausbeute {jetzt['punkte_je_vergabe']:.1f} Punkte/Vergabe, "
                            f"Verwerfung {jetzt['verwerfung']:.0%} — erste Etappe, "
                            f"kein Vergleich"))

    muell = jetzt["leer"] + jetzt["abgebrochen"] + jetzt["ohne_preis"]
    aus.append((("rot" if muell > max(3, jetzt["aufrufe"] * 0.02) else "grün"),
                f"{jetzt['leer']} leere, {jetzt['abgebrochen']} abgebrochene, "
                f"{jetzt['ohne_preis']} ohne Preis"))
    aus.append((("grün" if tests_gruen else "rot"), "Testsuite"))
    return aus


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nur-lesen", action="store_true", help="Verlauf nicht fortschreiben")
    ap.add_argument("--verlauf", action="store_true", help="alle Etappen zeigen")
    ap.add_argument("--ohne-tests", action="store_true", help="Testsuite überspringen")
    a = ap.parse_args()

    if a.verlauf:
        if not VERLAUF.exists():
            print("  Noch keine Etappe festgehalten.", file=sys.stderr)
            return 1
        print(f"\n  {'Zeitpunkt':<21}{'Vergaben':>9}{'USD':>9}{'$/Verg.':>9}"
              f"{'Punkte':>8}{'verw.':>7}{'Boden':>7}")
        print("  " + "─" * 70)
        for z in (json.loads(x) for x in VERLAUF.read_text(encoding="utf-8").splitlines() if x.strip()):
            print(f"  {z['ts'][:19].replace('T', ' '):<21}{z['vergaben']:>9,}"
                  f"{z['usd']:>9.3f}{(z.get('usd_je_vergabe') or 0):>9.4f}"
                  f"{z['punkte_je_vergabe']:>8.1f}{z['verwerfung']:>6.0%}"
                  f"{z['bodenanteil']:>7.0%}".replace(",", "."))
        print()
        return 0

    jetzt = messe()
    luecke = None
    try:
        from importlib import util as _u
        spec = _u.spec_from_file_location("kb", ROOT / "scripts/kostenbericht.py")
        kb = _u.module_from_spec(spec)
        spec.loader.exec_module(kb)
        if kb.MARKE.exists():
            m = json.loads(kb.MARKE.read_text(encoding="utf-8"))
            konto = (kb._gesamtverbrauch() or 0) - float(m["total_usage"])
            buch = sum(float(z["kosten_usd"]) for z in kostenbuch.lies()
                       if z.get("kosten_usd") is not None) - float(m["buch"])
            luecke = (konto - buch) / konto if konto > 0 else 0.0
    except Exception:                                    # noqa: BLE001
        luecke = None

    tests_gruen, testzeile = (True, "übersprungen") if a.ohne_tests else _tests()
    befunde = bewerte(jetzt, _vorherige(), luecke, tests_gruen)

    print(f"\n  Qualitätsschranke · {jetzt['vergaben']} Vergaben, "
          f"{jetzt['aufrufe']} Aufrufe, {jetzt['usd']:.4f} $ seit der letzten Etappe\n")
    for ampel, text in befunde:
        zeichen = {"grün": "✓", "rot": "⛔", "grau": "·"}[ampel]
        print(f"    {zeichen} {text}")
    print(f"    {'✓' if tests_gruen else '⛔'} {testzeile}")

    rot = [t for a_, t in befunde if a_ == "rot"]
    if rot:
        print(f"\n  ⛔ {len(rot)} Befund(e) verlangen Hinsehen, bevor es weitergeht.\n")
    else:
        print("\n  ✓ Alles im Rahmen — die nächste Etappe kann laufen.\n")

    if not a.nur_lesen:
        jetzt["befunde_rot"] = rot
        VERLAUF.parent.mkdir(parents=True, exist_ok=True)
        with VERLAUF.open("a", encoding="utf-8") as f:
            f.write(json.dumps(jetzt, ensure_ascii=False) + "\n")
    return 1 if rot else 0


if __name__ == "__main__":
    raise SystemExit(main())
