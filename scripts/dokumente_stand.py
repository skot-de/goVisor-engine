#!/usr/bin/env python3
"""Wie weit ist der Dokumenten-Rückstau — und was hat er bisher gekostet?

**Warum getrennt vom Arbeiter.** Der Arbeiter soll arbeiten, nicht rechnen. Dieser Bericht
läuft nach jeder Runde und einmal von Hand, wenn man wissen will, wo man steht. Sven am
2026-08-18 zum Budget: „freie fahrt" — genau deshalb gehört der Verbrauch sichtbar
daneben. Nicht als Bremse, sondern damit niemand im Anbieter-Dashboard nachsehen muss.

Der Trichter ist die eigentliche Auskunft. Eine einzelne Zahl („4.259 ZIPs") sagt nicht,
wo es klemmt; erst die Stufen zeigen, ob das Abholen hinterherhinkt oder das Auswerten.

Aufruf::

    scripts/dokumente_stand.py
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
G = ROOT / "data/gold/DE"
W = ROOT / "web/data"


def lade(name: str) -> set:
    """Kennungen aus einem Web-Artefakt.

    ⚠ Kennt BEIDE Formen. `export_doc_text.py` hat am 2026-08-18 den 294-MB-Sammelblock
    `doc-text.json` durch Einzeldateien je Vorgang plus `doc-text-index.json` ersetzt —
    diese Funktion suchte weiter die Sammeldatei und meldete deshalb seither
    „Volltext 0 (0 %)", waehrend 5.593 Vorgaenge Volltext hatten. Die naechste Stufe
    bekam dadurch „404500 %". Ein Trichter, der eine Stufe auf null zeigt, laesst genau
    dort suchen, wo nichts fehlt.
    """
    for kandidat in (W / f"{name}.json", W / f"{name}-index.json"):
        try:
            d = json.loads(kandidat.read_text(encoding="utf-8"))
            return set(d)                      # dict → Schluessel, Liste → Werte
        except Exception:
            continue
    verz = W / name                            # dritte Form: ein Verzeichnis je Vorgang
    if verz.is_dir():
        return {f.stem for f in verz.glob("*.json")}
    return set()


def _preis_je_vorgang() -> tuple[float | None, str]:
    """Was ein analysierter Vorgang WIRKLICH gekostet hat — aus dem Kostenbuch.

    ``(None, "")``, wenn das Kostenbuch nichts hergibt; dann faellt der Aufrufer auf den
    Listenpreis zurueck und sagt in der Ausgabe, dass geschaetzt wird.

    ⚠ Gerechnet wird je VORGANG, nicht je Aufruf. Eine Vergabe kostet mehrere Aufrufe
    (einen je Dokumentgattung), gemessen rund vier — wer je Aufruf hochrechnet, liegt um
    diesen Faktor daneben.

    ⚠ Das Kostenbuch reicht nur so weit zurueck, wie es aufbewahrt wird (90 Tage bzw.
    32 MB, s. `govisor/kostenbuch.py`). Fuer einen Durchschnittspreis genuegt das; als
    Gesamtsumme des Projekts taugt es nicht, und deshalb steht hier auch keine.
    """
    try:
        import sys
        sys.path.insert(0, str(ROOT))
        from govisor import kostenbuch
    except Exception:                                       # noqa: BLE001
        return None, ""
    summe = 0.0
    vorgaenge: set[str] = set()
    try:
        for zeile in kostenbuch.lies():
            if zeile.get("zweck") != "analyse":
                continue
            betrag = zeile.get("kosten_usd")
            if not isinstance(betrag, (int, float)) or betrag <= 0:
                continue
            summe += float(betrag)
            v = zeile.get("vorgang")
            if v:
                vorgaenge.add(str(v))
    except Exception:                                       # noqa: BLE001
        return None, ""
    if not vorgaenge or summe <= 0:
        return None, ""
    return summe / len(vorgaenge), f"bezahlt, gemessen an {len(vorgaenge):,} Vorgaengen"


def main() -> int:
    con = duckdb.connect()
    le = (G / "lead_export.parquet").as_posix()
    offen = {r[0] for r in con.execute(
        f"SELECT lead_id FROM '{le}' WHERE phase='open' AND coalesce(country,'DE')='DE'").fetchall()}
    mit_link = {r[0] for r in con.execute(
        f"""SELECT lead_id FROM '{le}' WHERE phase='open' AND coalesce(country,'DE')='DE'
            AND documents_url IS NOT NULL""").fetchall()}
    zips = {d.name for d in (ROOT / "data/docs/DE").iterdir()
            if d.is_dir() and any(d.glob("*.zip"))} if (ROOT / "data/docs/DE").exists() else set()

    # ⚠ DIE KETTE ENDET AM VOLLTEXT — danach zweigt sie sich. Bis zum 2026-08-25 stand
    # hier eine Reihe von sechs Stufen, jede als Prozent „der Stufe davor". Zwei Fehler
    # in einer Zeile:
    #
    #   1. Signale standen VOR dem Volltext, obwohl `signals-docs` genau den liest, den
    #      `index-docs` vorher schreibt. Ergebnis: „Volltext 102 % der Stufe davor" —
    #      eine Stufe, die mehr enthaelt als die, aus der sie hervorgeht.
    #   2. Auch richtig sortiert bleibt es falsch: Signale und LLM-Analyse sind
    #      GESCHWISTER, keine Folge. Beide lesen `doc_text.parquet`, keiner den anderen.
    #      Gemessen am 25.08.: 90 Vorgaenge haben eine Auswertung ohne Signale — kein
    #      Defekt, sondern zwei Wege, die verschieden viel finden.
    #
    # Ein Trichter, der Geschwister uebereinanderstapelt, laesst genau dort suchen, wo
    # nichts fehlt — dieselbe Falle, vor der der Docstring von `lade()` oben warnt.
    volltext = offen & lade("doc-text")
    kette = [("offene Leads", offen), ("mit Unterlagen-Link", mit_link),
             ("ZIP geholt", offen & zips), ("Volltext", volltext)]
    zweige = [("Signale", offen & lade("doc-signals")),
              ("LLM-Analyse", offen & lade("doc-analysis"))]
    print("\n  Dokumenten-Trichter (offene Leads):")
    vor = None
    for name, s in kette:
        n = len(s)
        anteil = f"  {n/vor:>5.0%} der Stufe davor" if vor else ""
        print(f"    {name:<22}{n:>7,}{anteil}")
        vor = n or 1
    basis = len(volltext) or 1
    for name, s in zweige:
        print(f"    ├ {name:<20}{len(s):>7,}  {len(s)/basis:>5.0%} des Volltexts")

    # ⚠ `token_cost` sind TOKEN, keine Dollar.
    #
    # Der erste Anlauf summierte das Feld und meldete „5.455.635 $ bisher, 103 Mio $
    # hochgerechnet". Das ist offensichtlicher Unsinn, aber genau die Sorte Zahl, die
    # jemand ungeprueft weitererzaehlt. In `analyze_docs.py:159` steht:
    #     "token_cost": round(sent_chars / CHARS_PER_TOKEN)
    # also die geschaetzte Zahl GESENDETER Token je Vorgang.
    #
    # ⚠ EIN SICHTBARER PREIS IST BESSER ALS EIN VERSTECKTER — UND EIN GEMESSENER BESSER
    # ALS BEIDE. Hier stand bis zum 2026-08-29 ein fester Listenpreis, und daneben lag die
    # ganze Zeit das Kostenbuch mit dem, was wirklich abgerechnet wurde. Gemessen ueber
    # 16.140 echte Analyse-Aufrufe:
    #
    #     angenommen   0,30 $ je Mio Eingabe-Token, Ausgabe ausdruecklich nicht enthalten
    #     bezahlt      0,64 $ je Mio Eingabe-Token, plus 56,7 Mio Ausgabe-Token
    #     → die Hochrechnung lag um Faktor 3,6 zu niedrig (11 $ statt 40 $)
    #
    # Das ist genau die Zahl, nach der jemand entscheidet, ob er Guthaben auflaedt. Wer ihr
    # glaubt, laedt ein Viertel des Noetigen auf und wundert sich, warum der Lauf steht.
    #
    # Der Listenpreis bleibt als Rueckfall, wenn das Kostenbuch nichts hergibt — dann sagt
    # die Ausgabe aber dazu, dass geschaetzt wird.
    PREIS_JE_MIO_EINGABE = 0.30   # google/gemini-2.5-flash, Stand 2026-08 (OpenRouter)
    ana = W / "doc-analysis.json"
    if not ana.exists():
        return 0
    d = json.loads(ana.read_text(encoding="utf-8"))
    tok = [v.get("token_cost") for v in d.values()
           if isinstance(v, dict) and isinstance(v.get("token_cost"), (int, float))]
    if not tok:
        print(f"\n  Analysierte Vorgaenge: {len(d):,} · keine Token-Angabe im Ergebnis")
        return 0
    summe = sum(tok)
    je_vorgang, herkunft = _preis_je_vorgang()
    if je_vorgang is None:                       # kein Kostenbuch → ehrlich schaetzen
        je_vorgang = summe / len(tok) / 1e6 * PREIS_JE_MIO_EINGABE
        herkunft = (f"geschaetzt, {PREIS_JE_MIO_EINGABE} $/Mio Eingabe, "
                    f"OHNE Ausgabe-Token")
    print(f"\n  Analysiert: {len(d):,} Vorgaenge · {summe/1e6:.1f} Mio Eingabe-Token")
    print(f"  Kosten je Vorgang: {je_vorgang:.4f} $ ({herkunft})")
    # ⚠ ZWEI ZAHLEN, WEIL NUR EINE DAVON BEZAHLT WIRD. Hier stand bis zum 2026-08-25
    # allein `len(zips - d)` — also JEDER Vorgang mit ZIP ohne Auswertung, samt
    # abgelaufener Frist. Der Produktionslauf faehrt aber mit `NUR_OFFENE=1` und ruehrt
    # die abgelaufenen nie an (die Vorgabe kam am 21.08. dazu, nachdem 350 $ genau dafuer
    # ausgegeben waren). Eine Hochrechnung ueber Arbeit, die niemand machen wird, ist
    # eine Zahl, die nur erschreckt.
    rest_offen = len(offen & zips - set(d))
    rest_zu = len(zips - set(d)) - rest_offen
    print(f"  Noch offen: {rest_offen:,} Vorgaenge mit laufender Frist "
          f"→ hochgerechnet ~{rest_offen * je_vorgang:.2f} $")
    if rest_zu:
        print(f"  Dazu {rest_zu:,} mit abgelaufener Frist (~{rest_zu * je_vorgang:.2f} $) — "
              f"die faehrt der Lauf mit NUR_OFFENE=1 nicht an.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
