"""Selbstdiagnose des Dokument-Parsers: wo greifen die Regeln zu kurz?

**Die Idee.** Der Parser weiß selbst, wann er etwas verpasst: wenn ein Thema im Dokument
vorkommt (Anker trifft), aber kein Wert herauskommt (Regel trifft nicht). Diese Differenz —
die **Trefferlücke** — ist die Arbeitsliste. Genau so wurde am 2026-08-13 die Bindefrist
gefunden: „Bindefrist" stand in 392 Dokumenten, extrahiert wurde 1 Wert.

**Warum das Skript keine Regeln schreibt.** Ein Parser, der sich selbst erweitert, stürzt bei
einem Fehler nicht ab — er liefert *plausible falsche Zahlen*. „Vertragsstrafe 5 %" statt
0,5 % fällt niemandem auf, bis danach kalkuliert wird, und an diesen Zahlen hängt die
Angebotsentscheidung des Kunden. Außerdem wäre keine frühere Auswertung mehr
reproduzierbar. Deshalb:
**das Skript diagnostiziert und schlägt vor, ein Mensch entscheidet.** Dasselbe Muster wie
bei `review_queue` und der handkuratierten Entity-Alias-CSV.

**Was es tut**
  1. Je Signal: wie oft ist das Thema da (Anker), wie oft kommt ein Wert heraus (Regel)?
  2. Für die Fehlschläge: das Textumfeld einsammeln, Ziffern zu ``#`` normalisieren und die
     häufigsten FORMEN zählen. Was oft vorkommt und nicht erfasst wird, ist der nächste
     Regel-Kandidat.
  3. Ausgabe als JSON (maschinenlesbar) + Klartext-Bericht.

Die Anker stehen bewusst in ``govisor/docsignals.py`` neben den Regeln, nicht hier — beim
ersten Anlauf lagen sie getrennt und waren enger als die Regeln, worauf die Metrik negative
Lücken meldete. Man misst sonst den eigenen Messfehler.

Aufruf:  python3 scripts/parser_gaps.py [--country DE] [--top 8] [--min 10]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from govisor import docsignals  # noqa: E402  (Pfad muss zuerst stehen)

_FLAGS = re.IGNORECASE | re.DOTALL

# Signale, die DASSELBE beantworten und sich denselben Anker teilen. `binding_days` und
# `binding_until` sind Alternativen — die Bindefrist steht entweder als Tageszahl ODER als
# Datum. Ohne diese Zuordnung zeigte der Bericht für `binding_days` eine dauerhafte Lücke von
# 191, die sich nie schliessen laesst: ein rotes Feld, das man nach zwei Wochen ignoriert.
# Eine Metrik, die immer Alarm gibt, ist keine Metrik.
ALTERNATIVEN: dict[str, tuple[str, ...]] = {
    "binding_days": ("binding_until",),
    "binding_until": ("binding_days",),
}
# ⚠ SIGNALE, DEREN WERT DER BIETER LIEFERT — nicht der Auftraggeber.
#
# Gemessen am 2026-08-25 an 200 Dokumenten mit „Skonto", die keinen Wert ergaben:
#
#     30 %  blosse Erwaehnung im Angebotsformular („Skontoangebot fuer alle Zahlungen")
#     28 %  VOB/B-Regelung ohne Zahl („unter Abzug eines vereinbarten Skontos")
#     20 %  LEERES Formularfeld („Gewaehrung von FORMTEXT ______ % Skonto")
#      8 %  Prozentzahl im Umfeld — die einzigen echten Regel-Kandidaten
#      2 %  ausdruecklich kein Skonto
#
# Skonto BIETET der Bieter an; die Unterlagen fragen es ab. In rund vier von fuenf Faellen
# gibt es gar keinen Wert zu holen. Die Kennzahl las „Thema erwaehnt" als „Wert muesste da
# sein" und meldete dauerhaft eine Luecke von 2.429 — dasselbe Muster wie bei
# `binding_days` oben, nur eine Ebene tiefer: nicht zwei Felder teilen sich einen Anker,
# sondern der Anker trifft ein Thema, das per Bauart keinen Wert traegt.
BIETERANGABE: frozenset[str] = frozenset({"skonto_pct"})

# Leere Formularfelder. Sie sind der haeufigste Grund fuer einen Fehlschlag, der keiner ist:
# „Bindefrist endet am: ____" traegt in 99 von 100 Faellen nichts dahinter (gemessen an 120
# Dokumenten), und „FORMTEXT ______ %" wartet auf den Bieter.
_LEERFELD = re.compile(r"_{3,}|\.{4,}|FORMTEXT|\[\s*\]|…{2,}")

# ⚠ DER WICHTIGERE TEST: steht hinter dem Anker ueberhaupt eine ZAHL?
#
# Ein Signal, das eine Zahl sucht, kann aus einer Fundstelle ohne Ziffern nichts holen —
# keine Regel der Welt. Genau das ist der Normalfall: gemessen am 2026-08-25 tragen 97 %
# der `award_weights`-Fehlschlaege keine Ziffer im Umfeld, bei `penalty_pct` 67 %, bei
# `skonto_pct` 53 %. Der Anker trifft dort ein THEMA, keinen Wert.
#
# Ein erster Versuch suchte nur nach leeren Formularfeldern (`____`, `FORMTEXT`) und fand
# fast nichts: der haeufigste Fall sieht anders aus — „Bindefrist endet am: Liste der
# Anlagen:", also eine Beschriftung, hinter der die naechste Beschriftung kommt.
_ZAHL = re.compile(r"\d")
# Nur fuer Signale, die eine Zahl suchen. `variants_allowed` und `guarantee_required`
# beantworten ja/nein und brauchen keine.
ZAHLSIGNALE: frozenset[str] = frozenset({
    "skonto_pct", "penalty_pct", "binding_days", "binding_until", "award_weights",
    "eligibility_count",
})

_UMFELD = 55          # Zeichen links/rechts vom Ankertreffer
_MAX_FUNDE = 6        # je Dokument und Signal — sonst dominiert ein Formularsatz die Statistik


def _form(s: str) -> str:
    """Textstelle → FORM. Ziffern zu ``#``, Weißraum vereinheitlicht.

    So fallen „endet am 03.11.2026" und „endet am 25.09.2026" zu EINER Form zusammen —
    das ist der Punkt: nicht die Werte zählen, sondern die Schreibweisen.
    """
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\d", "#", s)
    return re.sub(r"#+", "#", s)


def analysiere(country: str, top: int, mindest: int) -> dict:
    import duckdb

    src = ROOT / "data" / "docs" / country / "doc_text.parquet"
    if not src.exists():
        print(f"kein {src} — erst `fetch-docs` + `index-docs` laufen lassen.")
        return {}
    con = duckdb.connect()
    docs = con.execute(
        f"""SELECT notice_id, string_agg(text, ' ' ORDER BY file) AS full
            FROM read_parquet('{src.as_posix()}') WHERE status='ok' GROUP BY notice_id""").fetchall()

    erwaehnt: Counter = Counter()
    erkannt: Counter = Counter()
    formen: dict[str, Counter] = {k: Counter() for k in docsignals.ANKER}
    formularfeld: Counter = Counter()

    for _nid, text in docs:
        t = text or ""
        sig = docsignals.extract_signals(t)
        for signal, anker in docsignals.ANKER.items():
            treffer = list(re.finditer(anker, t, _FLAGS))
            if not treffer:
                continue
            erwaehnt[signal] += 1
            if sig.get(signal) is not None or any(sig.get(x) is not None for x in ALTERNATIVEN.get(signal, ())):
                erkannt[signal] += 1
                continue
            # Fehlschlag: das Thema steht da, ein Wert kam nicht heraus → Formen sammeln.
            umfelder = []
            for m in treffer[:_MAX_FUNDE]:
                a, b = max(0, m.start() - _UMFELD), min(len(t), m.end() + _UMFELD)
                umfelder.append(t[a:b])
            # Traegt KEINE der Fundstellen etwas ausser einem leeren Feld, ist das kein
            # Regel-Kandidat, sondern ein Formular, das auf den Bieter wartet.
            def _ohne_wert(u: str) -> bool:
                if _LEERFELD.search(u):
                    return True
                return signal in ZAHLSIGNALE and not _ZAHL.search(u)

            if umfelder and all(_ohne_wert(u) for u in umfelder):
                formularfeld[signal] += 1
                continue
            for u in umfelder:
                formen[signal][_form(u)] += 1

    bericht = {"country": country, "dokumente": len(docs), "signale": {}}
    for signal in sorted(docsignals.ANKER, key=lambda s: -(erwaehnt[s] - erkannt[s])):
        e, k = erwaehnt[signal], erkannt[signal]
        ff = formularfeld[signal]
        luecke = e - k
        # Die ERREICHBARE Luecke: ohne leere Formularfelder, und ohne Signale, deren Wert
        # der Bieter liefert. Beide Zahlen stehen nebeneinander — wer die rohe braucht,
        # findet sie, und wer die Arbeitsliste braucht, wird nicht in die Irre geschickt.
        erreichbar = 0 if signal in BIETERANGABE else max(0, luecke - ff)
        bericht["signale"][signal] = {
            "erwaehnt": e, "erkannt": k, "luecke": luecke,
            "formularfeld": ff, "erreichbar": erreichbar,
            "bieterangabe": signal in BIETERANGABE,
            "quote": round(k / e, 3) if e else None,
            "unerkannte_formen": [
                {"form": f, "n": n} for f, n in formen[signal].most_common(top) if n >= mindest
            ],
        }
    return bericht


def main(country: str, top: int, mindest: int) -> int:
    b = analysiere(country, top, mindest)
    if not b:
        return 1
    ziel = ROOT / "data" / "docs" / country / "parser_gaps.json"
    ziel.write_text(json.dumps(b, ensure_ascii=False, indent=1) + "\n")

    print(f"Parser-Selbstdiagnose {country} — {b['dokumente']} Dokumente\n")
    print(f"  {'Signal':<24}{'erwähnt':>9}{'erkannt':>9}{'Lücke':>8}"
          f"{'ohne Wert':>11}{'erreichbar':>12}{'Quote':>8}")
    for name, d in b["signale"].items():
        q = f"{d['quote']:.0%}" if d["quote"] is not None else "—"
        err = "Bieter" if d.get("bieterangabe") else f"{d.get('erreichbar', 0)}"
        print(f"  {name:<24}{d['erwaehnt']:>9}{d['erkannt']:>9}{d['luecke']:>8}"
              f"{d.get('formularfeld', 0):>11}{err:>12}{q:>8}")

    print("\nHäufigste NICHT erfasste Formen (Kandidaten für neue Regeln):")
    for name, d in b["signale"].items():
        if not d["unerkannte_formen"]:
            continue
        print(f"\n  ── {name}  (Lücke {d['luecke']}, davon erreichbar {d.get('erreichbar', 0)})")
        for f in d["unerkannte_formen"]:
            print(f"     {f['n']:>4}×  {f['form'][:118]}")
    print(f"\n→ {ziel.relative_to(ROOT)}")
    print("Hinweis: Vorschläge, keine Regeln. Übernommen wird von Hand — ein selbst "
          "geschriebener Ausdruck liefert im Fehlerfall plausible falsche Zahlen.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="DE")
    ap.add_argument("--top", type=int, default=8, help="Formen je Signal")
    ap.add_argument("--min", dest="mindest", type=int, default=10, help="Mindesthäufigkeit")
    a = ap.parse_args()
    sys.exit(main(a.country, a.top, a.mindest))
