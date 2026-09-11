#!/usr/bin/env python3
"""Baut aus dem Vollbestand einen Demo-Datensatz — klein genug fuer ein Deployment.

    python3 scripts/demo_datensatz.py [--ziel web/data-demo] [--firma Klostermann]

WARUM NICHT EINFACH DIE ERSTEN N. Der Vollbestand ist 4,4 GB in 118.000 Dateien; `next build`
stirbt bei rund 156.000, und Vercel nimmt 100 MB Quell-Upload je Deployment. Man muss also
ausduennen — und wer dabei zufaellig kuerzt, landet ueberwiegend bei Vorgaengen OHNE
Dokumentanalyse. Genau die sind aber das Vorzeigbare.

DIE AUSWAHLREGEL, gemessen am 2026-09-11:

    9.766  Dokumentanalysen vorhanden
    4.723  davon mit einem Lead in den ausgelieferten Listen
    2.915  davon mit Frist, die am Demo-Tag noch laeuft
      233  davon mit ALLEN SIEBEN Bloecken gefuellt        ← der Kern

Die sieben Bloecke sind belegte Zitate, K.-o.-Kriterien, Eignung, Zuschlag, Fristen,
LV-Positionen, Aufwand. Sie werden EINZELN gezaehlt, nicht summiert: ein Vorgang mit 88
Checklistenpunkten und null Zuschlagskriterien sieht in der Summe gut aus und in der
Vorfuehrung duenn.

⚠ ZITATE ZAEHLEN, NICHT ZEILEN. Ein Checklistenpunkt ohne `quote` ist in der Oberflaeche ein
Etikett. Das ist F5 im Fallenkatalog („nur den Fuellgrad messen": CH-Kriterien 100 % gefuellt,
29 % davon reine Etiketten).

⚠ DER DATENSATZ HAT EIN HALTBARKEITSDATUM. Die fruehesten Fristen laufen in Tagen ab. Wer ihn
zwei Wochen vor der Vorfuehrung baut, zeigt abgelaufene Vorgaenge — genau der Fehler, den
`outreach.json` gerade vorfuehrt (Stand 17.08., alle sechs gezeigten Fristen abgelaufen).
Deshalb schreibt der Lauf `_stand.json` mit dem Tag und der fruehesten Frist.
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import shutil
import sys

sys.dont_write_bytecode = True                    # ⚠ F9: nicht gegen alten Bytecode messen

ROOT = pathlib.Path(__file__).resolve().parent.parent
QUELLE = ROOT / "web" / "data"
BLOECKE = ("belegt", "ko", "eig", "zus", "fri", "pos", "auf")

# Tabellen, die der Explorer neben den Leads liest. Sie sind klein und werden GANZ kopiert —
# ein Ausduennen brachte nichts und koennte Bezuege reissen.
NEBEN = ("branchen.json", "plz-geo.json", "anforderungsprofil.json", "bieterfragen.json",
         "schwellen.json", "standardtext.json", "stellenprofil.json", "umfang.json",
         "unterlagenstand.json", "fenster.json", "fristwiderspruch.json", "landing.json",
         "doc-signals.json", "doc-struktur.json", "regionen.json", "marktpuls.json")


def bloecke(d: dict) -> dict:
    """Die sieben Achsen einer Analyse — einzeln, nicht als Summe."""
    return {
        "belegt": sum(1 for c in (d.get("checklist") or []) if (c.get("quote") or "").strip()),
        "ko": len(d.get("ko_kriterien") or []), "eig": len(d.get("eignung") or []),
        "zus": len(d.get("zuschlag") or []), "fri": len(d.get("fristen") or []),
        "pos": len(d.get("positions") or []), "auf": len(d.get("aufwand") or []),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ziel", default="web/data-demo")
    ap.add_argument("--firma", default="Klostermann",
                    help="Teilstring des Firmennamens; ihre Landing bleibt erhalten")
    ap.add_argument("--puffer-tage", type=int, default=7,
                    help="Fristen muessen so viele Tage nach HEUTE noch laufen")
    ap.add_argument("--breite", type=int, default=7, help="Mindestzahl gefuellter Bloecke")
    args = ap.parse_args()

    ziel = ROOT / args.ziel
    heute = datetime.date.today()
    stichtag = (heute + datetime.timedelta(days=args.puffer_tage)).isoformat()

    # ── Leads einlesen ────────────────────────────────────────────────────────
    je_fach: dict[str, list] = {}
    for p in sorted(QUELLE.glob("leads-*.json")):
        if p.name == "leads-fristen.json":
            continue
        je_fach[p.stem.replace("leads-", "")] = json.loads(p.read_text(encoding="utf-8"))
    alle = {str(e.get("id")): (fach, e) for fach, ls in je_fach.items() for e in ls}
    print(f"Vollbestand: {len(alle):,} Leads in {len(je_fach)} Fachgebieten")

    def frist(e) -> str:
        return str(e.get("deadlineAktuell") or e.get("frist") or "")[:10]

    # ── Analysen bewerten ─────────────────────────────────────────────────────
    kern, knapp = [], 0
    dateien = sorted((QUELLE / "doc-analysis").glob("*.json"))
    for p in dateien:
        eintrag = alle.get(p.stem)
        if eintrag is None or frist(eintrag[1]) < stichtag:
            continue
        try:
            b = bloecke(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
        gefuellt = sum(1 for k in BLOECKE if b[k] > 0)
        if gefuellt >= args.breite:
            kern.append((p.stem, eintrag[0], b, gefuellt))
        elif gefuellt == args.breite - 1:
            knapp += 1
    print(f"Analysen: {len(dateien):,} vorhanden · {len(kern):,} mit >= {args.breite} Bloecken "
          f"und Frist ab {stichtag}  (knapp verfehlt: {knapp:,})")
    if not kern:
        print("⛔ Nichts ausgewaehlt — Stichtag zu spaet oder Bestand veraltet?")
        return 1

    behalten = {k[0] for k in kern}

    # ── Umfeld: die Liste darf nicht aus lauter Spitzenwerten bestehen ────────
    # ⚠ Eine Trefferliste, in der JEDER Vorgang vollstaendig ausgewertet ist, ist keine
    # Demo, sondern eine Behauptung. Im Echtbetrieb liegt die Quote bei 233 von 43.636.
    # Deshalb kommt je Fachgebiet ein Umfeld dazu — sonst zeigt die Vorfuehrung ein
    # Produkt, das es nicht gibt.
    for fach, ls in je_fach.items():
        offen = [e for e in ls if frist(e) >= stichtag and str(e.get("id")) not in behalten]
        offen.sort(key=lambda e: frist(e))
        behalten.update(str(e.get("id")) for e in offen[:120])

    # ── Schreiben ─────────────────────────────────────────────────────────────
    if ziel.exists():
        shutil.rmtree(ziel)
    (ziel / "doc-analysis").mkdir(parents=True)

    gesamt = 0
    for fach, ls in je_fach.items():
        aus = [e for e in ls if str(e.get("id")) in behalten]
        (ziel / f"leads-{fach}.json").write_text(
            json.dumps(aus, ensure_ascii=False), encoding="utf-8")
        d = QUELLE / f"detail-{fach}.json"
        if d.exists():
            roh = json.loads(d.read_text(encoding="utf-8"))
            if isinstance(roh, dict):
                schlank = {k: v for k, v in roh.items() if k in behalten}
            else:
                schlank = [e for e in roh if str(e.get("id")) in behalten]
            (ziel / f"detail-{fach}.json").write_text(
                json.dumps(schlank, ensure_ascii=False), encoding="utf-8")
        gesamt += len(aus)
        print(f"  {fach:<12}{len(aus):>6} von {len(ls):>6}")

    for lid in behalten:
        q = QUELLE / "doc-analysis" / f"{lid}.json"
        if q.exists():
            shutil.copy2(q, ziel / "doc-analysis" / q.name)

    fristen = QUELLE / "leads-fristen.json"
    if fristen.exists():
        roh = json.loads(fristen.read_text(encoding="utf-8"))
        schlank = ({k: v for k, v in roh.items() if k in behalten} if isinstance(roh, dict)
                   else [e for e in roh if str(e.get("id")) in behalten])
        (ziel / "leads-fristen.json").write_text(json.dumps(schlank, ensure_ascii=False),
                                                 encoding="utf-8")
    for n in NEBEN:
        if (QUELLE / n).exists():
            shutil.copy2(QUELLE / n, ziel / n)

    # ── outreach: nur die Demo-Firma ──────────────────────────────────────────
    # ⚠ Der Vollbestand traegt 9.456 Firmen mit ihrer Auswertung. In ein Deployment, das
    # jemand Fremdes sieht, gehoert davon genau die eine, die vorgefuehrt wird.
    oq = QUELLE / "outreach.json"
    if oq.exists():
        d = json.loads(oq.read_text(encoding="utf-8"))
        treffer = {t: v for t, v in d.items()
                   if args.firma.lower() in (v.get("name") or "").lower()}
        (ziel / "outreach.json").write_text(json.dumps(treffer, ensure_ascii=False),
                                            encoding="utf-8")
        print(f"\noutreach: {len(treffer)} von {len(d):,} Firmen (Filter: {args.firma!r})")
        for t, v in treffer.items():
            print(f"  /t/{t}   {v.get('name')}")

    frueheste = min(frist(alle[i][1]) for i in behalten if i in alle)
    (ziel / "_stand.json").write_text(json.dumps({
        "gebaut_am": heute.isoformat(), "stichtag": stichtag,
        "leads": gesamt, "analysen": len(behalten & {k[0] for k in kern}),
        "frueheste_frist": frueheste,
        "regel": f">= {args.breite} von 7 Bloecken, Frist ab {stichtag}, plus 120 je Fach",
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    mb = sum(f.stat().st_size for f in ziel.rglob("*")) / 1e6
    n = sum(1 for _ in ziel.rglob("*"))
    print(f"\n{ziel.relative_to(ROOT)}: {gesamt:,} Leads · {len(kern):,} dichte Analysen "
          f"· {mb:.1f} MB in {n:,} Dateien")
    print(f"⚠ Frueheste Frist im Datensatz: {frueheste} — danach zeigt die Demo Abgelaufenes.")
    if mb > 95:
        print("⛔ ueber 95 MB — Vercel nimmt auf Hobby nur 100 MB Quell-Upload je Deployment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
