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
import sys
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

    stufen = [("offene Leads", offen), ("mit Unterlagen-Link", mit_link),
              ("ZIP geholt", offen & zips), ("Signale", offen & lade("doc-signals")),
              ("Volltext", offen & lade("doc-text")), ("LLM-Analyse", offen & lade("doc-analysis"))]
    print("\n  Dokumenten-Trichter (offene Leads):")
    vor = None
    for name, s in stufen:
        n = len(s)
        anteil = f"  {n/vor:>5.0%} der Stufe davor" if vor else ""
        print(f"    {name:<22}{n:>7,}{anteil}")
        vor = n or 1

    # ⚠ `token_cost` sind TOKEN, keine Dollar.
    #
    # Der erste Anlauf summierte das Feld und meldete „5.455.635 $ bisher, 103 Mio $
    # hochgerechnet". Das ist offensichtlicher Unsinn, aber genau die Sorte Zahl, die
    # jemand ungeprueft weitererzaehlt. In `analyze_docs.py:159` steht:
    #     "token_cost": round(sent_chars / CHARS_PER_TOKEN)
    # also die geschaetzte Zahl GESENDETER Token je Vorgang.
    #
    # Umgerechnet wird mit einem hier sichtbaren Preis, nicht mit einem versteckten:
    # wer das Modell wechselt, muss diese Zeile anfassen, und dann faellt ihm auf, dass
    # er sie anfassen muss.
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
    kosten = summe / 1e6 * PREIS_JE_MIO_EINGABE
    print(f"\n  Analysiert: {len(d):,} Vorgaenge · {summe/1e6:.1f} Mio Token "
          f"· ~{kosten:.2f} $ (Eingabe, {PREIS_JE_MIO_EINGABE} $/Mio)")
    rest = len(zips - set(d))
    if rest and tok:
        hoch = rest * (summe / len(tok)) / 1e6 * PREIS_JE_MIO_EINGABE
        print(f"  Noch offen: {rest:,} Vorgaenge → hochgerechnet ~{hoch:.0f} $")
    print("  Die Ausgabe-Token kommen dazu; sie sind hier NICHT enthalten, weil das "
          "Ergebnis sie nicht mitschreibt.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
