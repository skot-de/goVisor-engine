#!/usr/bin/env python3
"""Wächter: Kennzahlen, die über ein GANZES Land keine Streuung haben.

⚠ WARUM ES DIESE SONDE GIBT. Am 2026-09-01 trugen in der Schweiz alle 104 ausgewerteten
Vergabestellen denselben KMU-Anteil — 100 %. Rechnerisch korrekt, als Aussage wertlos, und
im Produkt als Marktbefund zu lesen: „in der Schweiz gehen alle Aufträge an KMU". Die
Ursache war ein stiller Stichprobenfilter (Details am `kmu`-Bauschritt in
`scripts/export_strategie.py`), nicht ein Rechenfehler.

Genau deshalb hat es niemand gemerkt: **die Zahl war nicht falsch, sie war leer.** Kein
Test schlägt an, kein Fremdschlüssel bricht, kein Feld ist NULL. Eine Kennzahl ohne
Unterschied sieht exakt aus wie eine Kennzahl — bis man zwei Länder nebeneinanderlegt.

DER DETEKTOR. Streuung null über ein ganzes Land. Er unterscheidet nicht, WOHER die
Entartung kommt (Vorgabewert, Vokabel-Konstante, entarteter Stichprobenfilter, ein
Connector, der ein Feld nie füllt) — er misst nur, ob die Kennzahl überhaupt etwas
unterscheidet. Das ist die Eigenschaft, auf die es ankommt.

EU-WEIT, nicht DE-fest: geprüft wird jedes Land, das in der Datei steht — auch eines, das
es heute noch nicht gibt. Ein neues Land, dessen Quelle ein Feld nie füllt, fällt hier auf,
bevor es im Produkt als Marktaussage steht.

    python3 scripts/pruefe_streuung.py [--offen] [--json]

Rückgabe 1, wenn eine Kennzahl ohne Streuung NICHT als `konstant` markiert ist. Eine
markierte Entartung ist kein Fehlschlag — sie ist der dokumentierte Zustand, den das
Frontend als „nicht unterscheidend" ausweist (markieren statt wegwerfen).
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

DATEI = pathlib.Path(__file__).resolve().parent.parent / "web" / "data" / "strategie.json"

# Dieselben Schwellen wie Anzeige (`StrategieView.tsx`) und Bauschritt — an EINER Stelle
# geändert, an drei Stellen geprüft, deshalb hier noch einmal benannt statt importiert
# (die Anzeige ist TypeScript, der Bauschritt läuft ohne dieses Modul).
MIND_FAELLE = 8       # unter 8 Fällen ist eine Quote grob (0/8, 4/8, 8/8) → kein Alarm
MIND_STELLEN = 10     # unter 10 Stellen ist Gleichheit Zufall, kein Befund

# Quoten tragen ihre Fallzahl mit (`{pct, n, treffer}`), Skalare nicht. Beide können
# entarten, aber nur die Quote lässt sich im JSON markieren — beim Skalar ist der Wert
# selbst die ganze Angabe. Deshalb zwei Listen, ein Detektor.
QUOTEN = ("kmu", "preis", "wechsel", "neuAnteil")
SKALARE = ("bieterMedian", "top1", "vergabenJahr")


def werte_je_stelle(landblock: dict, feld: str, ist_quote: bool) -> tuple[dict, int]:
    """Ein Wert je Vergabestelle. Dieselbe Stelle steht in mehreren Branchen — ohne die
    Entdopplung zählte eine breit aufgestellte Stelle mehrfach und verschöbe das Urteil."""
    je_stelle, markiert = {}, 0
    for branche in landblock.values():
        if not isinstance(branche, dict):
            continue
        for st in branche.get("stellen") or []:
            if ist_quote:
                q = st.get(feld)
                if isinstance(q, dict) and (q.get("n") or 0) >= MIND_FAELLE:
                    je_stelle[st["id"]] = q["pct"]
                    markiert += 1 if q.get("konstant") else 0
            else:
                v = st.get(feld)
                if v is not None:
                    je_stelle[st["id"]] = v
    return je_stelle, markiert


def pruefe(daten: dict) -> list[dict]:
    befunde = []
    for land in sorted(daten):
        landblock = daten[land]
        if not isinstance(landblock, dict):
            continue
        for feld in QUOTEN + SKALARE:
            ist_quote = feld in QUOTEN
            je_stelle, markiert = werte_je_stelle(landblock, feld, ist_quote)
            if len(je_stelle) < MIND_STELLEN:
                continue
            verschieden = set(je_stelle.values())
            if len(verschieden) > 1:
                continue
            befunde.append({
                "land": land, "kennzahl": feld, "stellen": len(je_stelle),
                "wert": next(iter(verschieden)), "quote": ist_quote,
                "markiert": bool(markiert) if ist_quote else False,
            })
    return befunde


def markieren(landblock: dict, land: str, sagen=print) -> list[str]:
    """Quoten ohne jede Streuung ueber das ganze Land als `konstant` kennzeichnen.

    ⚠ Diese Funktion ruft der BAUSCHRITT auf (`scripts/export_strategie.py`), damit die
    Markierung in der Datei landet und nicht erst in der Anzeige entsteht. Detektor und
    Markierung stehen bewusst in DERSELBEN Datei: sie teilen zwei Schwellen (`MIND_FAELLE`,
    `MIND_STELLEN`), und zwei Kopien davon waeren genau die Sorte doppelt gepflegter Wert,
    die spaeter auseinanderlaeuft — ohne dass irgendetwas rot wird.

    MARKIEREN STATT WEGWERFEN: der Rohwert bleibt stehen, er bekommt nur `konstant: true`.
    Ein Loeschen saehe aus wie fehlende Datenlage und verwechselte ein ARTEFAKT mit einer
    LUECKE."""
    getroffen = []
    for feld in QUOTEN:
        je_stelle, _ = werte_je_stelle(landblock, feld, True)
        if len(je_stelle) < MIND_STELLEN or len(set(je_stelle.values())) > 1:
            continue
        wert = next(iter(set(je_stelle.values())))
        sagen(f"  ⛔ {land}/{feld}: {len(je_stelle)} Stellen, EIN Wert ({wert} %) — "
              f"keine Streuung, wird als `konstant` markiert.")
        getroffen.append(feld)
        for branche in landblock.values():
            if not isinstance(branche, dict):
                continue
            for st in branche.get("stellen") or []:
                q = st.get(feld)
                if isinstance(q, dict) and (q.get("n") or 0) >= MIND_FAELLE:
                    q["konstant"] = True
    return getroffen


def haeufigste(daten: dict, land: str, feld: str, ist_quote: bool) -> str:
    je_stelle, _ = werte_je_stelle(daten[land], feld, ist_quote)
    c = collections.Counter(je_stelle.values())
    return ", ".join(f"{w}×{n}" for w, n in c.most_common(3))


# ═══ SPUR 2: die Rohspalten je Land ═══════════════════════════════════════════════════
#
# Die Strategie-Kennzahlen sind nur die Spitze. Dieselbe Krankheit sitzt eine Ebene tiefer,
# in `gold/<Land>/lead_export.parquet`: eine Spalte, die in EINEM Land etwas unterscheidet
# und im naechsten genau einen Wert traegt, wird dort nicht gemessen — sie wird geerbt.
#
# DER DISKRIMINATOR IST DER LAENDERVERGLEICH, nicht die Spalte fuer sich. Eine Spalte, die
# ueberall konstant ist, kann eine Konstante SEIN (`country`). Eine, die in DE 3 Werte hat
# und in CH einen, ist ein Befund — genau die Asymmetrie, an der der KMU-Fall haengt.
#
# ⚠ EIN KONSTANTES FELD SCHEITERT NICHT, ES BLEIBT LEER. Das ist der Grund, warum diese
# Klasse in CLAUDE.md als haeufigste des Projekts steht und trotzdem immer wieder durchgeht:
# `has_documents = False` sieht aus wie „dieser Auftrag hat keine Unterlagen", nicht wie
# „wir haben hier nie nachgesehen". Der Nutzer kann die beiden nicht unterscheiden — und
# die Datei auch nicht.
#
# BEKANNTE BEFUNDE stehen als Code hier, mit Grund und Datum, nicht in einer Textdatei.
# Sie sind ABGEHAKT, nicht behoben: die Sonde soll den NAECHSTEN Fall fangen, nicht taeglich
# dieselben vier melden. `tests/test_marktwert.py` haelt die Liste ehrlich — ein Eintrag
# ohne Grund oder fuer eine Spalte, die es nicht mehr gibt, macht die Suite rot.
BEKANNT: dict[tuple[str, str], str] = {
    # ── Unterlagen-Block: gebaut fuer die Schweiz (simap), fuer DE/AT nie verdrahtet.
    # Gemessen 2026-09-01: CH hat has_documents True/False, documents_source vier Werte,
    # documents_languages de/fr/it. DE (90.969 Leads) und AT (18.054) tragen durchweg
    # False bzw. NULL — obwohl unter data/docs/DE ein grosser Bestand liegt.
    # ⚠ Das liest sich als NEGATIVE Aussage („keine Unterlagen"), nicht als Luecke.
    ("DE", "has_documents"): "Unterlagen-Block nur fuer CH/simap verdrahtet (2026-09-01)",
    ("AT", "has_documents"): "Unterlagen-Block nur fuer CH/simap verdrahtet (2026-09-01)",
    ("DE", "documents_paid"): "s. has_documents (2026-09-01)",
    ("AT", "documents_paid"): "s. has_documents (2026-09-01)",
    ("DE", "documents_source"): "s. has_documents (2026-09-01)",
    ("AT", "documents_source"): "s. has_documents (2026-09-01)",
    ("DE", "documents_languages"): "s. has_documents (2026-09-01)",
    ("AT", "documents_languages"): "s. has_documents (2026-09-01)",
    # ── Nur-positives Vokabular: das Feld kennt in CH ausschliesslich „erlaubt".
    # 397 bzw. 536 CH-Leads tragen 1, kein einziger 0; DE/AT durchweg NULL. Wer die
    # Abwesenheit als „nicht erlaubt" liest, liegt falsch — dieselbe Verwechslung wie KMU.
    ("CH", "consortium_allowed"): "nur-positives Vokabular, DE/AT unversorgt (2026-09-01)",
    ("CH", "subcontracting_allowed"): "nur-positives Vokabular, DE/AT unversorgt (2026-09-01)",
    ("CH", "market_region_known"): "in CH nie False, DE hat True/False (2026-09-01)",
    # ── Anreicherung, die es nur fuer DE gibt. Untertreibt (meldet zu wenig), statt zu
    # behaupten — trotzdem heisst es: die Funktion ist fuer AT/CH nicht fertig.
    ("AT", "category_source"): "Kategorie-Anreicherung nur fuer DE gebaut (2026-09-01)",
    ("CH", "category_source"): "Kategorie-Anreicherung nur fuer DE gebaut (2026-09-01)",
    ("AT", "incumbent_group_size"): "Gruppenaufloesung findet ausserhalb DE nie eine Gruppe (2026-09-01)",
    ("CH", "incumbent_group_size"): "Gruppenaufloesung findet ausserhalb DE nie eine Gruppe (2026-09-01)",
    ("CH", "cost_weight_pct"): "Kriteriengewichte in simap nicht erhoben (2026-09-01)",
    ("CH", "selection_types"): "Eignungskriterien-Typen in simap nicht erhoben (2026-09-01)",
    # ── KEIN Datenfehler, aber auch kein Freibrief. Nachgemessen 2026-09-01: der
    # Klassifizierer (`gold._open_house_sql`) hat zwei Regeln, und in CH feuert keine —
    # 0 Titeltreffer, 0 Fristen jenseits +5 Jahren bei 1.642 Leads mit Frist. Das ist die
    # richtige Antwort, aber nur zur Haelfte aus dem richtigen Grund:
    #   · Fristregel: sprachunabhaengig, greift ueberall (in AT 371 Treffer) — CH hat
    #     schlicht keine Platzhalter-Fristen. Sauber gemessen.
    #   · Titelregel: sucht `rabatt|130a|130c|open house` — DEUTSCHE Rechtsworte. Fuer die
    #     franzoesisch- und italienischsprachige Schweiz (2.846 bzw. 206 Leads) gibt es
    #     kein Gegenstueck. Faende es dort je ein Open-House-Analogon statt, saehe das
    #     Ergebnis genauso aus wie heute: konstant `wettbewerb`.
    # ⚠ AT gehoert NICHT auf diese Liste — es hat 371 open_house (Fristregel) und ist
    # damit gar nicht konstant. Der Eintrag stand hier und war falsch.
    ("CH", "procedure_kind"): "beide Regeln feuern in CH zu Recht nicht; Titelregel ist "
                              "aber deutschsprachig und haette in FR/IT kein Gegenstueck "
                              "(2026-09-01)",
}

# Spalten, die per Bauart in JEDEM Land konstant sind — kein Vergleich moeglich, kein Befund.
IMMER_KONSTANT = ("country",)

GOLD = pathlib.Path(__file__).resolve().parent.parent / "data" / "gold"


def spalten_scan() -> list[dict]:
    """Spalten, die in einem Land nichts unterscheiden, in einem anderen aber schon."""
    try:
        import duckdb
    except ImportError:
        return []
    laender = sorted(p.name for p in GOLD.glob("*") if (p / "lead_export.parquet").exists())
    if len(laender) < 2:
        return []                      # ohne Vergleichsland gibt es keinen Diskriminator
    con = duckdb.connect()
    con.execute("SET threads=4")
    lage: dict[str, dict[str, tuple[int, int, int]]] = {}
    for land in laender:
        e = f"read_parquet('{GOLD / land / 'lead_export.parquet'}')"
        spalten = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {e}").fetchall()]
        sel = ", ".join(f'count(distinct "{c}"), count("{c}")' for c in spalten)
        zeile = con.execute(f"SELECT count(*), {sel} FROM {e}").fetchone()
        n = zeile[0]
        lage[land] = {c: (zeile[1 + 2 * i], zeile[2 + 2 * i], n) for i, c in enumerate(spalten)}

    gemeinsam = set.intersection(*(set(v) for v in lage.values())) - set(IMMER_KONSTANT)
    befunde = []
    for spalte in sorted(gemeinsam):
        # ZWEI KLASSEN, beide echte Befunde:
        #
        # (a) Die Spalte unterscheidet irgendwo etwas, in DIESEM Land aber nicht — der
        #     Laendervergleich ist der Diskriminator (s. Kopf).
        #
        # (b) Sie unterscheidet NIRGENDS etwas, traegt aber irgendwo einen Wert. Das ist
        #     kein schwaecherer Fall, sondern der gefaehrlichere: ein nur-positives
        #     Vokabular. `consortium_allowed` steht in CH 397-mal auf 1 und kein einziges
        #     Mal auf 0, in DE/AT nirgends. Wer die Abwesenheit als „nicht erlaubt" liest,
        #     liegt falsch — und nichts in der Datei widerspricht ihm. Genau die Form, in
        #     der der KMU-Wert drei Wochen ueberlebt hat.
        #
        # Eine Spalte, die ueberall komplett NULL ist, faellt durch beide Raster: sie
        # behauptet nichts. Sie gehoert in die Verdrahtungspruefung, nicht hierher.
        irgendwo_verschieden = any(lage[l][spalte][0] > 1 for l in laender)
        irgendwo_gefuellt = any(lage[l][spalte][1] > 0 for l in laender)
        if not irgendwo_verschieden and not irgendwo_gefuellt:
            continue
        for land in laender:
            versch, gefuellt, n = lage[land][spalte]
            if versch > 1:
                continue
            if not irgendwo_verschieden and gefuellt == 0:
                continue          # in DIESEM Land schlicht leer — das meldet Spur „leer"
            befunde.append({
                "land": land, "spalte": spalte, "verschieden": versch,
                "klasse": "laendervergleich" if irgendwo_verschieden else "nur_positiv",
                "gefuellt": gefuellt, "zeilen": n,
                "grund": BEKANNT.get((land, spalte)),
                "andere": {l: lage[l][spalte][0] for l in laender if l != land},
            })
    return befunde


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--offen", action="store_true",
                    help="nur unmarkierte Entartungen zeigen")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if not DATEI.exists():
        print(f"⚠ {DATEI} fehlt — nichts zu prüfen (kein Fehlschlag).")
        return 0
    daten = json.loads(DATEI.read_text(encoding="utf-8"))
    befunde = pruefe(daten)
    offen = [b for b in befunde if not b["markiert"]]
    spalten = spalten_scan()
    spalten_offen = [b for b in spalten if not b["grund"]]

    if a.json:
        print(json.dumps({"befunde": befunde, "spalten": spalten,
                          "offen": len(offen) + len(spalten_offen)},
                         ensure_ascii=False, indent=2))
        return 1 if (offen or spalten_offen) else 0

    print("── Streuung je Kennzahl und Land ──")
    for land in sorted(daten):
        if not isinstance(daten[land], dict):
            continue
        zeilen = []
        for feld in QUOTEN + SKALARE:
            je_stelle, _ = werte_je_stelle(daten[land], feld, feld in QUOTEN)
            if not je_stelle:
                zeilen.append(f"{feld}=—")
                continue
            n_versch = len(set(je_stelle.values()))
            mark = "⛔" if n_versch == 1 and len(je_stelle) >= MIND_STELLEN else ""
            zeilen.append(f"{feld}={n_versch}/{len(je_stelle)}{mark}")
        print(f"  {land}: " + "  ".join(zeilen))
    print("  (verschiedene Werte / auswertbare Stellen)")

    if not befunde:
        print("\n✓ keine Kennzahl ohne Streuung.")

    print()
    for b in befunde:
        zustand = "markiert (`konstant`)" if b["markiert"] else "⛔ NICHT markiert"
        if a.offen and b["markiert"]:
            continue
        print(f"⛔ {b['land']}/{b['kennzahl']}: {b['stellen']} Stellen, EIN Wert "
              f"({b['wert']}) — {zustand}")
        print(f"     Verteilung: {haeufigste(daten, b['land'], b['kennzahl'], b['quote'])}")
        if not b["markiert"]:
            print("     → Die Kennzahl unterscheidet in diesem Land nichts. Entweder liefert "
                  "die Quelle\n"
                  "       das Merkmal nicht, oder die Stichprobe ist entartet. Beides gehört "
                  "als\n"
                  "       unbekannt geführt, nicht als erfüllt: `scripts/export_strategie.py`, "
                  "`streuung_markieren`.")

    if befunde:
        if offen:
            print(f"\n⛔ {len(offen)} unmarkierte Entartung(en).")
        else:
            print("\n✓ jede Entartung ist markiert — das Frontend weist sie als "
                  "nicht unterscheidend aus.")

    # ── Spur 2 ───────────────────────────────────────────────────────────────────────
    print("\n── Rohspalten je Land (gold/<Land>/lead_export.parquet) ──")
    if not spalten:
        print("  ✓ keine Spalte, die in einem Land nichts unterscheidet.")
    else:
        bekannt = [b for b in spalten if b["grund"]]
        for b in spalten_offen:
            andere = ", ".join(f"{l}={v}" for l, v in sorted(b["andere"].items()))
            print(f"  ⛔ {b['land']}/{b['spalte']} [{b['klasse']}]: {b['verschieden']} Wert(e), "
                  f"gefüllt {b['gefuellt']}/{b['zeilen']} — andere Länder: {andere}")
            print("     → In diesem Land unterscheidet die Spalte nichts. Entweder liefert die "
                  "Quelle sie nicht,\n"
                  "       oder die Funktion ist für dieses Land nie verdrahtet worden. Beides "
                  "gehört als\n"
                  "       unbekannt geführt — und mit Grund in `BEKANNT` "
                  "(`scripts/pruefe_streuung.py`) abgehakt.")
        if bekannt and not a.offen:
            print(f"  · {len(bekannt)} bekannte Befunde (mit Grund abgehakt):")
            for b in bekannt:
                print(f"      {b['land']}/{b['spalte']}: {b['grund']}")
        elif bekannt:
            print(f"  · {len(bekannt)} bekannte Befunde ausgeblendet (ohne --offen sichtbar).")

    if offen or spalten_offen:
        print(f"\n⛔ {len(offen) + len(spalten_offen)} offene(r) Befund(e).")
        return 1
    print("\n✓ jede Entartung ist erklärt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
