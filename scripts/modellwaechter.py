#!/usr/bin/env python3
"""Täglicher Blick auf den Modellmarkt — und die Wahl des Modells VOR jedem Lauf.

**Warum täglich.** Preise sind veränderlich. Wer im Monatstakt schaut, zahlt im Schnitt
zwei Wochen zu viel und erfährt von einer Abkündigung erst, wenn die Aufrufe scheitern.
Der ganze Katalog kommt in einem HTTP-Aufruf — kein Token, kein Guthaben, keine Geldwache.

**Zwei Betriebsarten, und sie tun bewusst Verschiedenes:**

``--pruefen``  Katalog holen, Tagesstand ablegen, mit gestern vergleichen, Befunde melden.
               Meldet, ändert nichts. Gehört an den Anfang von `scripts/daily_leads.sh`.

``--waehlen``  Gibt auf **stdout** den Modellnamen aus, mit dem der folgende Lauf fahren
               soll. Alles andere geht nach stderr, damit ``OR_MODEL=$(… --waehlen)``
               funktioniert.

---

## Was sich automatisch anpasst — und was nicht

**Der Anbieter: vollautomatisch, ohne Zutun.** Die Endung ``:floor`` lässt OpenRouter bei
*jeder einzelnen Anfrage* den billigsten Endpunkt wählen. Fällt der billigste aus, greift
der nächste. Es gibt hier nichts zu entscheiden und nichts zu pflegen — gleiches Modell,
gleiche Gewichte, kein Qualitätsrisiko. Der Wächter prüft nur, ob der Bodenpreis **gestiegen**
ist; das wäre eine Meldung wert.

**Das Modell: automatisch nur unter Freigaben.** ``data/modellfreigabe.json`` führt die
Modelle, die den gepaarten Versuch (`scripts/llm_bench.py`) bestanden haben. Aus dieser
Liste wählt ``--waehlen`` das billigste, das heute noch taugt. Ein Modell, das der Katalog
als billiger meldet, aber nie gemessen wurde, wird **gemeldet und nicht genommen**.

⚠ Der Grund steht in unseren eigenen Zahlen. Am 2026-08-18 gemessen: die Modelle, die am
**wenigsten** fanden, erklärten am **meisten** für grün — sie behaupteten flüssig und
belegten wenig. Ein Wechsel nach Preis allein hätte genau dorthin geführt, und der Schaden
wäre erst Wochen später im Bestand aufgefallen. Preis ist keine Güte.

⚠ **Fail-open bei der Wahl.** Netz weg, Katalog kaputt, Datei unlesbar → es wird der
Amtierende ausgegeben und weitergefahren. Ein Wächter, der den Lauf verhindert, ist teurer
als jedes Modell. Beim *Melden* gilt das Gegenteil: dort wird laut geklagt.

Aufruf::

    scripts/modellwaechter.py --pruefen
    OR_MODEL=$(scripts/modellwaechter.py --waehlen) scripts/analyse_arbeiter.sh
    scripts/modellwaechter.py --freigeben openai/gpt-5-mini --grund "Bench 2026-09-01, p=0.01"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import kostenbuch, modellkatalog as mk, pruefstand as ps  # noqa: E402

AMTIEREND = os.environ.get("GOVISOR_AMTIEREND", "google/gemini-2.5-flash")
FREIGABE = Path(os.environ.get("GOVISOR_MODELLFREIGABE",
                               ROOT / "data" / "modellfreigabe.json"))
BEFUNDE = mk.ORDNER / "befunde.json"
# Die getroffene Wahl, hinterlegt statt bei jedem Lauf neu erfragt.
#
# ⚠ WARUM ALS DATEI UND NICHT ALS HTTP-AUFRUF IM ANALYSELAUF. `scripts/analyse_arbeiter.sh`
# startet rund um die Uhr Runden; ein Katalogabruf je Runde waere ueberfluessiger Verkehr und
# eine zusaetzliche Stelle, an der ein Netzfehler die Produktion aufhaelt. Der Waechter
# entscheidet einmal taeglich, der Lauf liest nur ab.
WAHL = ROOT / "data" / "modellwahl.json"

# Gewichtung von Eingabe- gegen Ausgabepreis.
#
# ⚠ HIER STAND 15:1 UND DAS WAR UM DEN FAKTOR 11 DANEBEN. Die Annahme „Vergabeunterlagen
# sind eingabelastig, rund 90.000 Token hinein und 6.000 heraus" klang plausibel und war
# falsch: die ersten vier Produktionsbuchungen am 2026-08-23 zeigen **74.950 ein / 56.452
# aus = 1,33:1**. Der Grund liegt auf der Hand, sobald man ihn sieht — die typisierte
# Extraktion gibt strukturiertes JSON MIT den wörtlichen Belegzitaten zurück; ein Beleg ist
# fast so lang wie die Stelle, die er belegt. Bei einem Ausgabepreis, der acht- bis
# zehnmal ueber dem Eingabepreis liegt, entscheidet damit die AUSGABE ueber die Kosten.
#
# Was der Fehler angerichtet haette: die Rangfolge der Kandidaten. Ein Modell mit billiger
# Eingabe und teurer Ausgabe waere zu gut bewertet worden. Deshalb steht die Schaetzung
# jetzt bei 1,5:1, und die Messung uebernimmt frueh — nach 20 statt nach 50 Buchungen.
STANDARD_MISCHUNG = (1.5, 1.0)
MISCHUNG_AB = 20               # ab so vielen Buchungen wird gemessen statt geschaetzt

# Obergrenze der QUALITAETSSPUR: bis zum Wievielfachen unseres Preises lohnt der Versuch,
# ein BESSERES Modell zu finden? Sven, 2026-08-24: „eig ist qualitaet zuerst, dann die
# kosten". Ohne diese Spur konnte der Pruefstand das gar nicht erfuellen — er liess nur
# billigere Modelle herein und haette einen Qualitaetsgewinn strukturell nie gesehen.
#
# Zusaetzlich muss ein Kandidat NEUER sein als unser Modell. Das sagt nichts ueber Guete,
# aber ein aelteres Modell als Verbesserung zu bezahlen ist unplausibel genug, um den
# Suchraum damit zu halbieren: 52 Modelle bis 3×, davon 35 bis 2×.
QUALITAET_DECKEL = float(os.environ.get("GOVISOR_QUALITAET_DECKEL", "2.0"))


def _z(n: float | int) -> str:
    """Tausenderpunkte. ⚠ Nicht `.replace(",", ".")` auf den ganzen Satz anwenden — das
    erwischt auch die Kommas im Fließtext („422 Modelle. davon 243 tauglich")."""
    return f"{int(n):,}".replace(",", ".")


def mischung() -> tuple[float, float, str]:
    """(Eingabe-, Ausgabegewicht, Herkunft) — gemessen wenn möglich, sonst geschätzt."""
    ein = aus = 0
    n = 0
    for z in kostenbuch.lies():
        if z.get("zweck") != "analyse":
            continue
        ein += int(z.get("eingabe_token") or 0)
        aus += int(z.get("ausgabe_token") or 0)
        n += 1
    if n >= MISCHUNG_AB and aus > 0:
        return ein / aus, 1.0, f"gemessen an {_z(n)} Buchungen"
    return (*STANDARD_MISCHUNG, f"geschätzt ({n} Buchungen, ab {MISCHUNG_AB} wird gemessen)")


def mischpreis(ein: float, aus: float, g_ein: float, g_aus: float) -> float:
    """Preis je Mio Token bei unserem Mischungsverhältnis."""
    return (ein * g_ein + aus * g_aus) / (g_ein + g_aus)


# ── Freigaben ────────────────────────────────────────────────────────────────────────

def lade_freigaben() -> dict:
    if FREIGABE.exists():
        try:
            return json.loads(FREIGABE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  ⚠ {FREIGABE} unlesbar — es gilt nur der Amtierende.", file=sys.stderr)
    return {AMTIEREND: {"grund": "Titelverteidiger (Vorgabe)", "seit": "2026-08-18"}}


def freigeben(modell: str, grund: str) -> int:
    f = lade_freigaben()
    f[modell] = {"grund": grund, "seit": date.today().isoformat()}
    FREIGABE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FREIGABE.with_suffix(".json.teil")
    tmp.write_text(json.dumps(f, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(FREIGABE)
    print(f"  ✓ {modell} freigegeben: {grund}")
    return 0


# ── Wählen ───────────────────────────────────────────────────────────────────────────

def waehle() -> int:
    """Modellname auf stdout. Bei JEDEM Zweifel der Amtierende."""
    g_ein, g_aus, herkunft = mischung()
    try:
        stand = mk.verdichte(mk.hole())
    except Exception as e:                               # noqa: BLE001
        print(f"  ⚠ Katalog nicht erreichbar ({type(e).__name__}) — es bleibt bei "
              f"{AMTIEREND}.", file=sys.stderr)
        print(AMTIEREND)
        return 0

    frei = lade_freigaben()
    kandidaten = []
    for mid in frei:
        m = stand.get(mid)
        if m is None:
            print(f"  ⚠ {mid} ist freigegeben, steht aber nicht mehr im Katalog.",
                  file=sys.stderr)
            continue
        if not mk.taugt(m):
            print(f"  ⚠ {mid} erfüllt den Bedarf nicht mehr "
                  f"(Kontext {_z(m['kontext'])}).", file=sys.stderr)
            continue
        # ⚠ KEIN RUECKFALL AUF DEN LISTENPREIS. Der erste Entwurf setzte bei einer
        # fehlgeschlagenen Endpunktabfrage den Katalogpreis ein — typisch das Doppelte des
        # Bodens. Das ist ASYMMETRISCH: schlaegt die Abfrage nur beim Amtierenden fehl,
        # steht er mit dem doppelten Preis da, ein Kandidat mit dem echten, und der Waechter
        # meldet „spart 50 %" und wechselt. Nachgestellt am 2026-08-24: beide Modelle mit
        # identischem echten Preis, ein Netzaussetzer beim Amtierenden — es wurde gewechselt.
        #
        # `bodenpreis` liefert None sowohl bei „niemand liefert das" als auch bei einem
        # Netzfehler; unterscheiden kann man es hier nicht. Beide Faelle werden deshalb
        # gleich behandelt, aber je nach Rolle verschieden:
        #   · der AMTIERENDE ohne Preis  → gar nicht wechseln (er hat garantiert Endpunkte,
        #     also liegt es am Netz)
        #   · ein KANDIDAT ohne Preis    → diesen Kandidaten auslassen
        # Beides kann nur einen Wechsel VERHINDERN, nie einen falschen ausloesen. Das ist
        # die Lesart von „bei JEDEM Zweifel der Amtierende", die im Docstring steht.
        boden = mk.bodenpreis(mid)
        if boden is None:
            if mid == AMTIEREND:
                print(f"  ⚠ Endpunktpreis des Amtierenden nicht abfragbar (Netz?) — "
                      f"es wird nicht gewechselt.", file=sys.stderr)
                hinterlege(AMTIEREND, "Endpunktpreise nicht abfragbar — unveraendert")
                print(AMTIEREND)
                return 0
            print(f"  ⚠ {mid}: kein Endpunktpreis — ausgelassen.", file=sys.stderr)
            continue
        kandidaten.append((mischpreis(boden["ein"], boden["aus"], g_ein, g_aus), mid, boden))
    if not kandidaten:
        print(f"  ⚠ Kein freigegebenes Modell verfügbar — es bleibt bei {AMTIEREND}.",
              file=sys.stderr)
        print(AMTIEREND)
        return 0

    kandidaten.sort()
    preis, gewaehlt, boden = kandidaten[0]
    print(f"  Mischung {g_ein:.1f}:{g_aus:.0f} Eingabe/Ausgabe ({herkunft})", file=sys.stderr)
    for p, mid, b in kandidaten:
        zeichen = "→" if mid == gewaehlt else " "
        print(f"  {zeichen} {mid:<40} {p:>7.3f} $/Mio  über {b['endpunkt']}"
              f"  ({b['haeuser']} Häuser)", file=sys.stderr)
    if gewaehlt != AMTIEREND:
        amt = next((p for p, mid, _ in kandidaten if mid == AMTIEREND), None)
        spar = f", spart {(1 - preis / amt) * 100:.0f} %" if amt else ""
        print(f"  ⇄ Wechsel von {AMTIEREND} auf {gewaehlt}{spar} — beide freigegeben.",
              file=sys.stderr)
    hinterlege(gewaehlt, f"billigstes freigegebenes Modell, {preis:.3f} $/Mio gemischt "
                         f"über {boden['endpunkt']}")
    print(gewaehlt)                                       # ← das Einzige auf stdout
    return 0


def hinterlege(modell: str, grund: str) -> None:
    WAHL.parent.mkdir(parents=True, exist_ok=True)
    tmp = WAHL.with_suffix(".json.teil")
    tmp.write_text(json.dumps({"modell": modell, "grund": grund,
                               "stand": date.today().isoformat()},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(WAHL)


# ── Prüfen ───────────────────────────────────────────────────────────────────────────

def waehle_still() -> None:
    """Wie `waehle()`, aber ohne Ausgabe auf stdout — fuer den Aufruf aus `--pruefen`."""
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        waehle()


def pruefen(schwelle: float) -> int:
    heute = date.today().isoformat()
    try:
        stand = mk.verdichte(mk.hole())
    except Exception as e:                               # noqa: BLE001
        print(f"  ⚠ Modellkatalog nicht erreichbar: {type(e).__name__}: {e}",
              file=sys.stderr)
        return 1
    frei = lade_freigaben()
    beobachtet = set(frei) | {AMTIEREND}

    vortag, alt = mk.lies_vorherigen(heute)
    mk.schreibe(stand, heute)
    befunde = mk.vergleiche(alt, stand, schwelle=schwelle, beobachtet=beobachtet)

    tauglich = sum(1 for m in stand.values() if mk.taugt(m))
    print(f"\n  Modellkatalog {heute} · {len(stand)} Modelle, davon {tauglich} tauglich "
          f"(Kontext ≥ {_z(mk.MIN_KONTEXT)}, strukturierte Ausgabe)")
    if alt is None:
        print(f"  Erster Stand — ab morgen wird verglichen.\n")
    else:
        print(f"  Verglichen mit {vortag}: {len(befunde)} Befund(e)\n")

    for b in befunde:
        art = b["art"]
        if art == "weg":
            print(f"  ⛔ WEG        {b['modell']} — steht nicht mehr im Katalog")
        elif art == "auslauf":
            print(f"  ⏳ AUSLAUF    {b['modell']} — abgekündigt zum {b['auslauf']}")
        elif art == "preis_rauf":
            print(f"  ↑  TEURER    {b['modell']} {b['feld']}: {b['von']:.3f} → "
                  f"{b['auf']:.3f} $/Mio ({b['delta']:+.0%})")
        elif art == "preis_runter":
            print(f"  ↓  BILLIGER  {b['modell']} {b['feld']}: {b['von']:.3f} → "
                  f"{b['auf']:.3f} $/Mio ({b['delta']:+.0%})")
        elif art == "neu":
            print(f"  ✦  NEU       {b['modell']} — {b['ein']:.3f}/{b['aus']:.3f} $/Mio, "
                  f"Kontext {_z(b['kontext'])}")
        elif art == "kontext":
            print(f"  ⚙  KONTEXT   {b['modell']}: {_z(b['von'])} → {_z(b['auf'])}")

    # Der Bodenpreis unseres eigenen Modells — die Zahl, die wir wirklich zahlen.
    boden = mk.bodenpreis(AMTIEREND)
    if boden:
        print(f"\n  Unser Modell {AMTIEREND}:")
        print(f"    Listenpreis {stand.get(AMTIEREND, {}).get('ein', 0):.3f}/"
              f"{stand.get(AMTIEREND, {}).get('aus', 0):.3f} · "
              f"Boden {boden['ein']:.3f}/{boden['aus']:.3f} $/Mio "
              f"über {boden['endpunkt']} ({boden['haeuser']} Häuser, "
              f"{boden['endpunkte']} Endpunkte)")

    # Billigere Taugliche — als HINWEIS, nicht als Auftrag.
    if boden:
        g_ein, g_aus, _ = mischung()
        latte = mischpreis(boden["ein"], boden["aus"], g_ein, g_aus)
        besser = [(mid, m) for mid, m in mk.guenstiger_als(stand, boden["ein"], boden["aus"],
                                                           ausser=beobachtet)]
        if besser:
            print(f"\n  {len(besser)} taugliche Modelle sind laut Katalog billiger als unser "
                  f"Boden ({latte:.3f} $/Mio gemischt). Die fünf günstigsten:")
            for mid, m in besser[:5]:
                print(f"    {mid:<46} {m['ein']:>6.3f}/{m['aus']:>6.3f} $/Mio · "
                      f"Kontext {_z(m['kontext'])}")
            # ── In die Warteschlange, statt es dem Menschen zu ueberlassen ──────
            #
            # ⚠ Nicht alle 47 einreihen. Ein Modell, das 5 % billiger ist, spart weniger,
            # als sein Test kostet; und eine Warteschlange, die jeden Tag um Dutzende
            # waechst, wird nie abgearbeitet. Es kommt nur hinein, wer die Latte
            # `MIN_ERSPARNIS` reisst — gemessen am MISCHPREIS, nicht an einem der beiden
            # Einzelpreise, denn unsere Last ist eingabelastig.
            pstand = ps.lade()
            neu_eingereiht = []
            for mid, m in besser:
                kpreis = mischpreis(m["ein"], m["aus"], g_ein, g_aus)
                if kpreis > latte * (1 - ps.MIN_ERSPARNIS):
                    continue
                if ps.einreihen(pstand, mid, preis=kpreis,
                                grund=f"laut Katalog {(1 - kpreis / latte):.0%} billiger "
                                      f"als unser Boden"):
                    neu_eingereiht.append((mid, kpreis))
            ps.sichere(pstand)
            offen = len(ps.naechste(pstand, hoechstens=999))
            if neu_eingereiht:
                print(f"\n  {len(neu_eingereiht)} davon reissen die Latte von "
                      f"{ps.MIN_ERSPARNIS:.0%} und sind eingereiht:")
                for mid, kp in neu_eingereiht[:5]:
                    print(f"    + {mid:<46} {kp:>6.3f} $/Mio gemischt "
                          f"({(1 - kp / latte):.0%} unter Boden)")
                if len(neu_eingereiht) > 5:
                    print(f"    … und {len(neu_eingereiht) - 5} weitere")
            # ── Zweite Spur: teurer, aber neuer — Kandidaten fuer QUALITAET ─────
            unser_alter = (stand.get(AMTIEREND) or {}).get("erschienen") or 0
            stark = []
            for mid, m in stand.items():
                if mid in beobachtet or not mk.taugt(m) or m["ein"] <= 0:
                    continue
                kp = mischpreis(m["ein"], m["aus"], g_ein, g_aus)
                if not (latte < kp <= latte * QUALITAET_DECKEL):
                    continue
                if (m.get("erschienen") or 0) <= unser_alter:
                    continue          # aelter als unseres — als Verbesserung unplausibel
                if ps.einreihen(pstand, mid, preis=kp, spur="qualitaet",
                                grund=f"neuer als unser Modell, {kp / latte:.1f}× der Preis "
                                      f"— Kandidat für bessere Qualität"):
                    stark.append((mid, kp))
            ps.sichere(pstand)
            if stark:
                stark.sort(key=lambda x: x[1])
                print(f"\n  {len(stark)} neuere Modelle bis {QUALITAET_DECKEL:.0f}× unseres "
                      f"Preises — Qualitätsspur:")
                for mid, kp in stark[:5]:
                    print(f"    + {mid:<46} {kp:>6.3f} $/Mio ({kp / latte:.1f}×)")
                if len(stark) > 5:
                    print(f"    … und {len(stark) - 5} weitere")
            offen = len(ps.naechste(pstand, hoechstens=999))
            print(f"\n  → {offen} Kandidat(en) offen. Keiner wird verwendet, bevor er den "
                  f"gepaarten Versuch bestanden hat:")
            print(f"     scripts/modellpruefung.py     (prüft höchstens "
                  f"{ps.MAX_JE_TAG} je Tag im eigenen Testtopf)")

    # Die Wahl gleich mit auffrischen: der Tageslauf ruft nur `--pruefen`, und die
    # Produktion soll am selben Tag von einer neuen Freigabe profitieren.
    try:
        waehle_still()
    except Exception as e:                               # noqa: BLE001
        print(f"  ⚠ Modellwahl nicht aufgefrischt: {type(e).__name__}", file=sys.stderr)

    BEFUNDE.parent.mkdir(parents=True, exist_ok=True)
    BEFUNDE.write_text(json.dumps(
        {"stand": heute, "vortag": vortag,
         "geprueft": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "tauglich": tauglich, "befunde": befunde}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pruefen", action="store_true", help="Katalog holen und vergleichen")
    ap.add_argument("--waehlen", action="store_true", help="Modellnamen auf stdout")
    ap.add_argument("--freigeben", metavar="MODELL", help="Modell für die Wahl zulassen")
    ap.add_argument("--grund", default="", help="Begründung zur Freigabe (Pflicht)")
    ap.add_argument("--schwelle", type=float, default=mk.SCHWELLE)
    a = ap.parse_args()

    if a.freigeben:
        if not a.grund:
            print("  --freigeben braucht --grund (welcher Bench, welches Ergebnis).",
                  file=sys.stderr)
            return 2
        return freigeben(a.freigeben, a.grund)
    if a.waehlen:
        return waehle()
    return pruefen(a.schwelle)


if __name__ == "__main__":
    raise SystemExit(main())
