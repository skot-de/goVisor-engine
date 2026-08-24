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
# Aus welchem Land stammen die Prüfvergaben?
#
# ⚠ **Vorgabe DE, und das ist eine Datenlage, keine Bequemlichkeit.** Die Bibel verlangt zu
# Recht, dass kein Feature nur für Deutschland gebaut wird (`docs/land-onboarding.md`).
# Hier ist die Beschränkung erzwungen: AT und CH haben **0 % Dokumentabdeckung**
# (`docs/laender/03-input-dokumente.md`) — es gibt dort schlicht keinen Volltext, an dem
# sich zwei Modelle unterscheiden könnten. Sobald ein Land Dokumente hat, genügt
# `--land XX`; der Rest der Kette ist länderunabhängig.
LAND = __import__("os").environ.get("GOVISOR_PRUEFLAND", "DE")
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


def taugt_als_pruefvergabe(rows) -> bool:
    """Beschäftigt diese Vergabe das Modell überhaupt? ``rows = [(datei, text), …]``

    Nur wenn mindestens ein Dokument einen Doktyp trägt, für den `docextract` eine Aufgabe
    kennt. Sonst gibt es keinen Extraktionsaufruf — und ohne den können zwei Modelle sich
    nicht unterscheiden.
    """
    from govisor import doctypes, docextract
    return any(doctypes.classify(f, t) in docextract._TASKS for f, t in rows)


def pruefsatz(stand: dict, n: int) -> dict:
    """Der feste Prüfsatz — dieselben Vergaben für jeden Kandidaten, dauerhaft.

    ⚠ **Fest, nicht zufällig je Lauf.** Wechselte der Satz, verglichen wir Kandidaten an
    verschiedenen Aufgaben — genau der Fehler, den der gepaarte Aufbau vermeiden soll. Der
    Satz wird deshalb einmal gewählt und in der Warteschlange festgehalten.
    """
    import duckdb
    from govisor import doctypes, docextract

    ids = stand.get("pruefsatz") or []
    if not ids:
        bestand = json.loads((ROOT / "web/data/doc-analysis.json").read_text(encoding="utf-8"))
        # Stabil und ohne Zufall: Reihenfolge des Bestands. Grosszuegig vorgemerkt, weil
        # unten aussortiert wird.
        ids = list(bestand)[: n * 20]
        stand["pruefsatz"] = ids
    con = duckdb.connect()
    src = (ROOT / f"data/docs/{LAND}/doc_text.parquet").as_posix()
    if not Path(src).exists():
        print(f"  Kein Volltext-Index für {LAND} ({src}) — Prüfsatz nicht aufbaubar.",
              file=sys.stderr)
        return {}
    aus: dict[str, list] = {}
    verworfen = 0
    for nid in ids:
        if len(aus) >= n:
            break
        rows = con.execute(
            f"""SELECT file, text FROM read_parquet('{src}')
                WHERE notice_id = ? AND {SQL_BRAUCHBAR} AND length(text) > 120""",
            [nid]).fetchall()
        if not rows:
            continue
        # ⚠ EINE VERGABE OHNE EXTRAHIERBAREN DOKTYP IST ALS PRUEFVERGABE WERTLOS.
        #
        # Gemessen am 2026-08-24 im Trockenlauf: drei der fuenfzehn Pruefvergaben bestanden
        # aus je einem einzigen Dokument — und zwar dreimal DEMSELBEN (gleiche Pruefsumme):
        # der Russland-Sanktions-Eigenerklaerung. Ihr Doktyp `eigenerklaerung` steht nicht
        # in `docextract._TASKS`, es gaebe also keinen einzigen Extraktionsaufruf. Beide
        # Modelle erzielten dort null Punkte; im Vorzeichentest ist das ein Unentschieden,
        # und Unentschiedene fallen heraus. Die wirksame Stichprobe waere still unter das
        # Mindestmass gerutscht, ohne dass irgendwo etwas Auffaelliges gestanden haette.
        if not taugt_als_pruefvergabe(rows):
            verworfen += 1
            continue
        aus[nid] = rows
    if verworfen:
        print(f"  {verworfen} Vergabe(n) übersprungen: kein extrahierbarer Doktyp — "
              f"sie könnten zwei Modelle nicht unterscheiden.")
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


def _abbruch_verbuchen(stand, eintrag, grund: str) -> str:
    """Ein Abbruch wegen Langsamkeit ist ein ENDGUELTIGES Urteil, aber kein Qualitaetsurteil.

    Ohne diese Unterscheidung waere ein Modell, das 760 s je Aufruf braucht, morgen wieder
    dran — und wuerde den naechtlichen Lauf jedes Mal aufs Neue blockieren. Budget- und
    Geldwache-Abbrueche dagegen sagen nichts ueber das Modell: die gehoeren zurueck in die
    Schlange.
    """
    if grund.startswith("zu langsam"):
        eintrag.update({"status": "zu_langsam", "urteil": grund,
                        "entschieden": date.today().isoformat()})
        ps.sichere(stand)
        print(f"    🐌 zu langsam: {grund}")
    return grund


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
            ausgeben=lambda z: print(z, flush=True), vergleich=basis)
        sichern(gemessen)
        if grund:
            return _abbruch_verbuchen(stand, eintrag, grund)
        ok, warum = ps.vorpruefung_bestanden(
            gemessen, {k: basis[k] for k in klein if k in basis})
        if not ok:
            # Ein Fristbefund ist KEIN Qualitaetsurteil — er bekommt seinen eigenen Status.
            eintrag.update({"status": "zu_langsam" if "Zeitfrist" in warum
                            else "durchgefallen", "urteil": warum,
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
        ausgeben=lambda z: print(z, flush=True), vergleich=basis)
    sichern(gemessen)
    if grund:
        return _abbruch_verbuchen(stand, eintrag, grund)

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


# ── Trockenlauf ──────────────────────────────────────────────────────────────────────

def trockenlauf(kandidaten: list[str] | None = None) -> int:
    """Der ganze Ablauf mit echtem Prüfsatz und echten Dokumenten — nur ohne Modell.

    **Wozu.** Vor dem ersten bezahlten Lauf soll beantwortbar sein: *wie viele Aufrufe
    werden das, wie viel Text geht raus, was kostet der Abend* — und vor allem: *taugen
    die Prüfvergaben überhaupt, zwei Modelle zu unterscheiden?*

    Gefälscht ist einzig `llm.chat`; alles davor ist echt: Doktyp-Erkennung, Parser-Schiene,
    Dublettenlogik, Textdeckel. Deshalb ist die **Eingabeseite exakt** und nicht geschätzt.
    Die Ausgabemenge lässt sich nicht ohne Modell wissen; sie wird aus dem Kostenbuch
    hochgerechnet und als Schätzung ausgewiesen.

    ⚠ **Eine Vergabe ohne Extraktionsaufruf ist als Prüfvergabe wertlos.** Gemessen am
    2026-08-24 standen drei solche im Prüfsatz: je ein einziges Dokument, alle drei
    dieselbe Russland-Sanktions-Eigenerklärung (gleiche Prüfsumme), Doktyp
    `eigenerklaerung` — den kennt `docextract` gar nicht. Beide Modelle hätten dort null
    Punkte erzielt, der Vergleich wäre ein Unentschieden ohne Aussage, und im
    Vorzeichentest fallen Unentschiedene heraus: die wirksame Stichprobe wäre still unter
    das Mindestmaß gerutscht. Diese Spalte deckt das auf.
    """
    import shutil
    import tempfile

    stand_echt = ps.lade()
    # Auf einer Kopie arbeiten: ein Trockenlauf darf den echten Zustand nicht anfassen.
    tmp = Path(tempfile.mkdtemp()) / "pruefstand.json"
    if ps.WARTESCHLANGE.exists():
        shutil.copy(ps.WARTESCHLANGE, tmp)
    echt_pfad, ps.WARTESCHLANGE = ps.WARTESCHLANGE, tmp
    try:
        stand = ps.lade()
        satz = pruefsatz(stand, ps.HAUPTPRUEFUNG_N)
        if not satz:
            print("  Kein Prüfsatz aufbaubar.", file=sys.stderr)
            return 1

        ad = lade_analyse()
        gezaehlt: dict[str, dict] = {}

        def stub(messages, model=None, **kw):
            nid = getattr(llm._KONTEXT, "vorgang", "?")
            g = gezaehlt.setdefault(nid, {"aufrufe": 0, "zeichen": 0, "zusammenfassung": 0})
            txt = " ".join(m.get("content", "") for m in messages)
            g["zeichen"] += len(txt)
            if "ampel" in txt.lower():
                g["zusammenfassung"] += 1
                return ('{"ampel":"gelb","ampel_grund":"Trockenlauf",'
                        '"zusammenfassung":"Trockenlauf","aufwand":"mittel"}')
            g["aufrufe"] += 1
            return "[]"

        import govisor.docextract as dx
        alt = (llm.chat, getattr(ad, "chat", None), getattr(dx, "chat", None))
        llm.chat = stub
        ad.chat = stub
        dx.chat = stub
        try:
            for nid, rows in satz.items():
                with llm.kontext(zweck="trocken", vorgang=nid):
                    ad.analyze_notice(rows, structured=ad.structured_for_notice(nid),
                                      notice_id=nid)
        finally:
            llm.chat, ad.chat, dx.chat = alt[0], alt[1] or stub, alt[2] or stub

        # ── Bericht ──────────────────────────────────────────────────────────────────
        print(f"\n  Trockenlauf über {len(satz)} Prüfvergaben — kein Modell befragt, "
              f"0 $ ausgegeben\n")
        print(f"  {'Vergabe':<18}{'Dok.':>6}{'Extraktion':>12}{'Zusammenf.':>12}"
              f"{'Zeichen raus':>14}  Eignung")
        print("  " + "─" * 82)
        taub = []
        for nid in satz:
            g = gezaehlt.get(nid, {"aufrufe": 0, "zeichen": 0, "zusammenfassung": 0})
            eignung = "✓" if g["aufrufe"] else "✖ kein Extraktionsaufruf"
            if not g["aufrufe"]:
                taub.append(nid)
            print(f"  {nid[:17]:<18}{len(satz[nid]):>6}{g['aufrufe']:>12}"
                  f"{g['zusammenfassung']:>12}{g['zeichen']:>14,}  {eignung}"
                  .replace(",", "."))

        zeichen = sum(g["zeichen"] for g in gezaehlt.values())
        aufrufe = sum(g["aufrufe"] + g["zusammenfassung"] for g in gezaehlt.values())
        ein_tok = zeichen / ad.CHARS_PER_TOKEN
        print("  " + "─" * 82)
        print(f"  {'zusammen':<18}{'':>6}{aufrufe:>12} Aufrufe {ein_tok:>17,.0f} Token ein"
              .replace(",", "."))

        if taub:
            print(f"\n  ⚠ {len(taub)} von {len(satz)} Vergaben lösen KEINEN "
                  f"Extraktionsaufruf aus.")
            print(f"    Dort erzielen beide Modelle null Punkte — im Vorzeichentest ein "
                  f"Unentschieden,\n    das herausfällt. Die wirksame Stichprobe ist damit "
                  f"{len(satz) - len(taub)}, nicht {len(satz)}"
                  + (f" — UNTER dem Mindestmaß von {ps.MIN_N}." if len(satz) - len(taub)
                     < ps.MIN_N else "."))

        # ── Kostenvorschau ───────────────────────────────────────────────────────────
        v_ein, v_aus = _ausgabeverhaeltnis()
        aus_tok = ein_tok * v_aus / v_ein
        print(f"\n  Kostenvorschau (Ausgabe hochgerechnet mit {v_aus / v_ein:.2f}× der "
              f"Eingabe, {_verhaeltnis_herkunft()})\n")
        print(f"  {'Modell':<40}{f'Vorprüfung ({ps.VORPRUEFUNG_N})':>18}"
              f"{f'voller Satz ({len(satz)})':>20}")
        print("  " + "─" * 78)
        from govisor import modellkatalog as mk
        liste = kandidaten or ([AMTIEREND] + ps.naechste(stand, 2))
        for m in dict.fromkeys(liste):
            b = mk.bodenpreis(m)
            if not b:
                print(f"  {m:<40}{'✖ kein lieferbarer Endpunkt — wird übersprungen':>38}")
                continue
            voll = ein_tok * b["ein"] / 1e6 + aus_tok * b["aus"] / 1e6
            vor = voll * ps.VORPRUEFUNG_N / max(len(satz), 1)
            print(f"  {m:<40}{vor:>17.4f} ${voll:>19.4f} $")
        print(f"\n  Der echte Lauf misst zuerst die Grundlinie ({AMTIEREND}), dann je "
              f"Kandidat\n  erst die Vorprüfung und nur bei Bestehen den vollen Satz.")
        print(f"  Tagestopf: {TEST_USD:.2f} $ · heute schon verbraucht: "
              f"{heute_ausgegeben():.4f} $")
        # Die Grundlinie ist der Brocken — und sie faellt nur alle 14 Tage an.
        grund_kosten = None
        b_amt = mk.bodenpreis(AMTIEREND)
        if b_amt:
            grund_kosten = ein_tok * b_amt["ein"] / 1e6 + aus_tok * b_amt["aus"] / 1e6
            if grund_kosten > TEST_USD * 0.8:
                print(f"  ⚠ Die Grundlinie allein ({grund_kosten:.4f} $) füllt den Topf "
                      f"fast aus. Der erste Abend misst\n    dann nur sie; Kandidaten "
                      f"kommen ab morgen dran. Schneller mit GOVISOR_TEST_USD.")
        print()
        return 0
    finally:
        ps.WARTESCHLANGE = echt_pfad
        assert ps.lade() is not None            # der echte Zustand ist unberuehrt


def _ausgabeverhaeltnis() -> tuple[float, float]:
    """(Eingabe, Ausgabe) aus dem Kostenbuch — sonst der gemessene Vorgabewert 1:1,33."""
    ein = aus = 0
    for z in kostenbuch.lies():
        if z.get("zweck") not in ("analyse", "bench", "pruefstand"):
            continue
        ein += int(z.get("eingabe_token") or 0)
        aus += int(z.get("ausgabe_token") or 0)
    return (ein, aus) if ein and aus else (100.0, 75.0)


def _verhaeltnis_herkunft() -> str:
    ein, aus = _ausgabeverhaeltnis()
    n = sum(1 for z in kostenbuch.lies()
            if z.get("zweck") in ("analyse", "bench", "pruefstand"))
    return f"gemessen an {n} Buchungen" if n else "Vorgabe, noch keine Buchungen"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kandidat", help="gezielt dieses Modell prüfen")
    ap.add_argument("--stand", action="store_true", help="nur die Warteschlange zeigen")
    ap.add_argument("--land", default=LAND,
                    help="Land der Prüfvergaben (Vorgabe DE — nur dort gibt es Volltext)")
    ap.add_argument("--trocken", action="store_true",
                    help="kompletter Ablauf ohne Modell: Aufrufe zählen, Kosten vorhersagen")
    ap.add_argument("--budget-usd", type=float, default=TEST_USD)
    ap.add_argument("--hoechstens", type=int, default=ps.MAX_JE_TAG)
    a = ap.parse_args()
    globals()["LAND"] = a.land

    if a.trocken:
        return trockenlauf([a.kandidat] if a.kandidat else None)

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

    from govisor import modellkatalog as mk
    for modell in dran:
        # ⚠ IM KATALOG HEISST NICHT LIEFERBAR. `inclusionai/ling-2.6-flash` stand am
        # 2026-08-24 als guenstigster Kandidat in der Schlange und hatte NULL Endpunkte —
        # niemand liefert es aus. Ohne diese Pruefung haette es einen der zwei Tagesplaetze
        # verbraucht, an jedem Aufruf scheitern und als `durchgefallen` enden muessen:
        # ein Urteil ueber die Qualitaet eines Modells, das wir nie gesehen haben.
        if mk.bodenpreis(modell) is None:
            # ⚠ KEIN PREIS HEISST NICHT AUTOMATISCH KEIN ENDPUNKT. `bodenpreis` liefert
            # `None` sowohl bei „niemand liefert dieses Modell" als auch bei einem
            # Netzfehler. Wer beides gleich behandelt, schreibt bei einem Aussetzer die
            # halbe Warteschlange dauerhaft ab. Der Amtierende ist die Gegenprobe: er hat
            # garantiert Endpunkte — antwortet auch seine Abfrage nicht, liegt es am Netz.
            if mk.bodenpreis(AMTIEREND) is None:
                print(f"\n  {modell}: Endpunkte nicht abfragbar (Netz?) — heute "
                      f"übersprungen, ohne Urteil.", file=sys.stderr)
                continue
            stand["kandidaten"].setdefault(modell, {})["status"] = "nicht_lieferbar"
            stand["kandidaten"][modell]["urteil"] = (
                "kein lieferbarer Endpunkt bei OpenRouter — nicht bestellbar, "
                "kein Urteil über die Qualität")
            stand["kandidaten"][modell]["entschieden"] = date.today().isoformat()
            ps.sichere(stand)
            print(f"\n  {modell}: kein lieferbarer Endpunkt — übersprungen.")
            continue
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
