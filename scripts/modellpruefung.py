#!/usr/bin/env python3
"""Automatischer Modelltest: neue Kandidaten bekommen Testaufträge, Bestandene übernehmen.

Sven, 2026-08-23: *„jedes neue modell bekommt x aufträge als test und wenn es bessere
auswertungen hat, als unser top modell, dann wird gewechselt."*

Der Kreis schließt sich hier:

    scripts/modellwaechter.py --pruefen   täglich, kostenlos → reiht Kandidaten ein
    scripts/modellpruefung.py             täglich, im Testtopf → prüft und entscheidet
    scripts/modellwaechter.py --waehlen   vor jedem Lauf → nimmt das beste Bestandene

Die Entscheidungsregel steht in `govisor/pruefstand.py` und nirgends sonst: Qualität zuerst
(Verwerfungsriegel, dann Vorzeichentest), danach der Preis, Geschwindigkeit nur als Messwert.

## Der Testtopf

⚠ **Ein eigenes Budget, getrennt von der Produktion.** Am 2026-08-23 fraß ein Versuch das
Guthaben des Analyse-Arbeiters auf; danach stand die Produktion, während der Versuch
weiterlief. Genau dagegen gibt es ``GOVISOR_TEST_USD`` (Vorgabe 0,50 $/Tag). Der Topf wird
aus dem Kostenbuch gezählt, über den Zweck ``pruefstand`` — die Geldwache mit ihrem
Tagesdeckel bleibt zusätzlich darüber liegen.

## Zwei Stufen, und die erste zählt mit

Die Vorprüfung fährt die **ersten** Vorgänge des festen Prüfsatzes. Besteht ein Kandidat,
werden diese Messwerte in der Hauptprüfung **weiterverwendet** — es wird nichts doppelt
bezahlt.

Aufruf::

    scripts/modellpruefung.py                       # Tagesbetrieb
    scripts/modellpruefung.py --kandidat x/y        # gezielt einen prüfen
    scripts/modellpruefung.py --stand               # nur die Warteschlange zeigen
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import kostenbuch, llm, pruefstand as ps  # noqa: E402
from govisor.docpipe import SQL_BRAUCHBAR  # noqa: E402

ZWECK = "pruefstand"
TEST_USD = float(__import__("os").environ.get("GOVISOR_TEST_USD", "0.50"))
AMTIEREND = __import__("os").environ.get("GOVISOR_AMTIEREND", "google/gemini-2.5-flash")


def heute_ausgegeben() -> float:
    """Was der Testtopf heute schon hergegeben hat — aus dem Kostenbuch."""
    heute = date.today().isoformat()
    return sum(float(z["kosten_usd"]) for z in kostenbuch.lies()
               if z.get("zweck") == ZWECK and z.get("kosten_usd") is not None
               and (z.get("ts") or "").startswith(heute))


def lade_analyse():
    spec = importlib.util.spec_from_file_location("ad", ROOT / "scripts/analyze_docs.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def pruefsatz(stand: dict, n: int) -> dict:
    """Der feste Prüfsatz — dieselben Vergaben für jeden Kandidaten, dauerhaft.

    ⚠ **Fest, nicht zufällig je Lauf.** Wechselte der Satz, verglichen wir Kandidaten an
    verschiedenen Aufgaben — genau der Fehler, den der gepaarte Aufbau vermeiden soll. Der
    Satz wird deshalb einmal gewählt und in der Warteschlange festgehalten.
    """
    import duckdb
    ids = stand.get("pruefsatz") or []
    if not ids:
        bestand = json.loads((ROOT / "web/data/doc-analysis.json").read_text(encoding="utf-8"))
        # Stabil und ohne Zufall: die ersten mit vorhandener Analyse. Reproduzierbar,
        # und `data/pruefstand.json` haelt sie ab jetzt fest.
        ids = list(bestand)[: n * 3]
        stand["pruefsatz"] = ids
    con = duckdb.connect()
    src = (ROOT / "data/docs/DE/doc_text.parquet").as_posix()
    aus: dict[str, list] = {}
    for nid in ids:
        if len(aus) >= n:
            break
        rows = con.execute(
            f"""SELECT file, text FROM read_parquet('{src}')
                WHERE notice_id = ? AND {SQL_BRAUCHBAR} AND length(text) > 120""",
            [nid]).fetchall()
        if rows:
            aus[nid] = rows
    return aus


def grundlinie(stand, ad, vorgaenge, rest) -> tuple[dict, str | None]:
    """Der Amtierende auf dem Prüfsatz — einmal gemessen, dann wiederverwendet."""
    if ps.grundlinie_frisch(stand):
        return stand["grundlinie"]["je_vorgang"], None
    print(f"  Grundlinie {AMTIEREND} wird erneuert (älter als {ps.GRUNDLINIE_TAGE} Tage "
          f"oder nicht vorhanden)")

    def sichern(e):
        stand["grundlinie"] = {"stand": date.today().isoformat(), "modell": AMTIEREND,
                               "je_vorgang": e}
        ps.sichere(stand)

    erg, grund = ps.messe_reihe(
        analyse=ad, llm=llm, kostenbuch=kostenbuch, modell=AMTIEREND,
        vorgaenge=vorgaenge, zweck=ZWECK,
        vorhanden=(stand.get("grundlinie") or {}).get("je_vorgang"),
        budget=rest, nach_vorgang=sichern, ausgeben=lambda z: print(z, flush=True))
    sichern(erg)
    return erg, grund


def pruefe_einen(stand, ad, modell, satz_voll, basis, rest) -> str | None:
    """Vorprüfung, dann Hauptprüfung, dann Urteil. Gibt einen Abbruchgrund oder None."""
    eintrag = stand["kandidaten"].setdefault(modell, {"status": "neu", "preis": 0})
    gemessen = eintrag.get("je_vorgang") or {}

    def sichern(e):
        eintrag["je_vorgang"] = e
        ps.sichere(stand)

    # ── Stufe 1 ──
    if eintrag["status"] == "neu":
        klein = dict(list(satz_voll.items())[: ps.VORPRUEFUNG_N])
        print(f"    Vorprüfung über {len(klein)} Vorgänge")
        gemessen, grund = ps.messe_reihe(
            analyse=ad, llm=llm, kostenbuch=kostenbuch, modell=modell, vorgaenge=klein,
            zweck=ZWECK, vorhanden=gemessen, budget=rest, nach_vorgang=sichern,
            ausgeben=lambda z: print(z, flush=True))
        sichern(gemessen)
        if grund:
            return grund
        ok, warum = ps.vorpruefung_bestanden(
            gemessen, {k: basis[k] for k in klein if k in basis})
        if not ok:
            eintrag.update({"status": "durchgefallen", "urteil": warum,
                            "entschieden": date.today().isoformat()})
            ps.sichere(stand)
            print(f"    ⛔ durchgefallen: {warum}")
            return None
        eintrag["status"] = "vorpruefung_bestanden"
        ps.sichere(stand)
        print(f"    ✓ {warum}")

    # ── Stufe 2 ── (die drei Vorprüfungs-Vorgänge zählen mit, nichts doppelt bezahlt)
    print(f"    Hauptprüfung über {len(satz_voll)} Vorgänge")
    gemessen, grund = ps.messe_reihe(
        analyse=ad, llm=llm, kostenbuch=kostenbuch, modell=modell, vorgaenge=satz_voll,
        zweck=ZWECK, vorhanden=gemessen, budget=rest, nach_vorgang=sichern,
        ausgeben=lambda z: print(z, flush=True))
    sichern(gemessen)
    if grund:
        return grund

    urteil = ps.entscheide(gemessen, basis)
    eintrag.update({"status": urteil["status"], "urteil": urteil["grund"],
                    "entschieden": date.today().isoformat(),
                    "messwerte": {k: urteil[k] for k in
                                  ("n_paare", "gewinne", "verluste", "p", "ersparnis")},
                    "sekunden": {"kandidat": urteil["sek_kandidat"],
                                 "amtierend": urteil["sek_amtierend"]}})
    ps.sichere(stand)
    zeichen = {"bestanden": "🏆", "durchgefallen": "⛔", "gleichwertig": "≈"}.get(
        urteil["status"], "·")
    print(f"    {zeichen} {urteil['status']}: {urteil['grund']}")
    print(f"       Geschwindigkeit {urteil['sek_kandidat']:.1f} s gegen "
          f"{urteil['sek_amtierend']:.1f} s (gemessen, nicht entscheidend)")
    if urteil["wechseln"]:
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "scripts/modellwaechter.py"),
                        "--freigeben", modell, "--grund",
                        f"Prüfstand {date.today().isoformat()}: {urteil['grund']}"],
                       check=False)
        print(f"    → freigegeben. Der nächste Lauf wählt es, wenn es das billigste "
              f"Freigegebene ist.")
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kandidat", help="gezielt dieses Modell prüfen")
    ap.add_argument("--stand", action="store_true", help="nur die Warteschlange zeigen")
    ap.add_argument("--budget-usd", type=float, default=TEST_USD)
    ap.add_argument("--hoechstens", type=int, default=ps.MAX_JE_TAG)
    a = ap.parse_args()

    stand = ps.lade()
    if a.stand:
        k = stand.get("kandidaten") or {}
        if not k:
            print("  Warteschlange leer.")
            return 0
        print(f"\n  {len(k)} Kandidaten\n")
        for m, v in sorted(k.items(), key=lambda x: (x[1].get("status"), x[0])):
            print(f"  {v.get('status','?'):<22} {m:<44} {v.get('preis',0):>7.3f} $/Mio")
            if v.get("urteil"):
                print(f"    └ {v['urteil']}")
        print()
        return 0

    schon = heute_ausgegeben()
    rest = a.budget_usd - schon
    print(f"\n  Testtopf: {schon:.4f} von {a.budget_usd:.2f} $ heute verbraucht, "
          f"{rest:.4f} $ frei")
    if rest <= 0:
        print("  Testtopf für heute leer — morgen wieder.", file=sys.stderr)
        return 0

    dran = [a.kandidat] if a.kandidat else ps.naechste(stand, a.hoechstens)
    if not dran:
        print("  Keine offenen Kandidaten.\n")
        return 0

    ad = lade_analyse()
    satz = pruefsatz(stand, ps.HAUPTPRUEFUNG_N)
    ps.sichere(stand)
    if not satz:
        print("  Kein Prüfsatz aufbaubar (kein brauchbarer Dokumenttext).", file=sys.stderr)
        return 1
    print(f"  Prüfsatz: {len(satz)} Vergaben (fest)\n")

    basis, grund = grundlinie(stand, ad, satz, rest)
    if grund:
        print(f"\n  ⏹ Abgebrochen beim Messen der Grundlinie: {grund}\n", file=sys.stderr)
        return 0

    for modell in dran:
        rest = a.budget_usd - heute_ausgegeben()
        if rest <= 0:
            print(f"\n  ⏹ Testtopf leer — der Rest wartet auf morgen.\n", file=sys.stderr)
            break
        print(f"\n  {modell}  (noch {rest:.4f} $ im Topf)")
        abbruch = pruefe_einen(stand, ad, modell, satz, basis, rest)
        if abbruch:
            print(f"\n  ⏹ Abgebrochen: {abbruch}. Gemessenes ist gesichert.\n",
                  file=sys.stderr)
            break
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
