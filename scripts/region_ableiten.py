#!/usr/bin/env python3
"""Fehlende Bundesländer aus dem ableiten, was da ist. Ohne Modell, ohne Netz.

**Das Problem, in Zahlen.** Gemessen am 2026-08-18 über `lead_export`:

    ohne Bundesland   im ganzen Bestand   7 %
    ohne Bundesland   bei den OFFENEN    40 %   ← 6.460 von 16.096

Der Unterschied ist die eigentliche Nachricht: die offenen Ausschreibungen kommen
überwiegend aus den unterschwelligen Quellen, und die liefern keine NUTS-Kennung. Wer im
Explorer nach Bundesland filtert, verliert damit **vier von zehn aktuellen** Ausschreibungen
— nicht weil sie nicht passen, sondern weil sie nichts sagen.

**Warum nicht über die Postleitzahl.** Naheliegend, aber gemessen wertlos: von den 6.460
Leads haben **38** eine Käufer-PLZ (1 %) und ebenso wenige einen Ortsnamen. Was sie haben,
ist zu 100 % der KÄUFERNAME — „Landeshauptstadt München", „Hansestadt Stralsund",
„Landkreis Märkisch-Oderland". Daran hängen die beiden Wege:

    Weg 1  Derselbe Käufername trägt in einem ANDEREN Lead ein Bundesland  → übernehmen.
    Weg 2  Im Käufernamen steckt ein Ortsname, der eindeutig zu einem Land gehört
           (geonames, 17.078 von 17.632 Ortsnamen sind eindeutig).

Gemessen: Weg 1 allein 32 %, Weg 2 allein 20 %, beide 29 %, gar nicht 19 % — zusammen
**81 %**.

**Der eingebaute Selbsttest.** Wo beide Wege greifen (1.854 Fälle), müssen sie dasselbe
sagen. Die Abweichungsquote steht im Lauf und ist die einzige ehrliche Auskunft über die
Verlässlichkeit dieser Ableitung; ohne sie wäre es Raten mit Nachkommastellen.

⚠️ Geschrieben wird eine eigene Datei (`lead_region_fill.parquet`), nicht `lead_export`.
Wer die Ableitung nicht mag, löscht die Datei — abgeleitete Werte tragen ausserdem ihre
Herkunft mit, damit sie in der Anzeige unterscheidbar bleiben.

Aufruf::  scripts/region_ableiten.py [--probe]
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
G = ROOT / "data/gold/DE"
ZIEL = G / "lead_region_fill.parquet"
GEONAMES = ROOT / "data/reference/geonames/DE.txt"

LAND_NUTS1 = {
    "Baden-Württemberg": "DE1", "Bayern": "DE2", "Berlin": "DE3", "Brandenburg": "DE4",
    "Bremen": "DE5", "Hamburg": "DE6", "Hessen": "DE7", "Mecklenburg-Vorpommern": "DE8",
    "Niedersachsen": "DE9", "Nordrhein-Westfalen": "DEA", "Rheinland-Pfalz": "DEB",
    "Saarland": "DEC", "Sachsen": "DED", "Sachsen-Anhalt": "DEE",
    "Schleswig-Holstein": "DEF", "Thüringen": "DEG",
}
# ⚠ geonames führt dieselben Länder auch auf Englisch („Bavaria", „Lower Saxony"). Die
# Zeilen sind Dubletten der deutschen und werden übersprungen, nicht übersetzt — sonst
# zählte man denselben Ort zweimal und hielte ihn für mehrdeutig.


def _worte(s: str) -> list[str]:
    """Kleinschreiben, Umlaute auflösen, in Wörter zerlegen.

    ⚠ WORTFOLGEN, NICHT ZEICHENKETTEN. Die Zwischenfassung faltete alles zu einem Wort
    zusammen und suchte den Ortsnamen als Teilzeichenkette darin. Gemessen stieg die
    Widerspruchsquote des Selbsttests damit von 8,8 % auf 21,7 %: ohne Wortgrenzen findet
    „senden" sich in „Wiesendendorf" und „ahlen" in „Zahlenwerk". Ein Ortsname muss als
    ganze Wortfolge dastehen, sonst ist er keiner.
    """
    s = s.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return [w for w in re.split(r"[^a-z]+", s) if w]


# Ortsnamen, die im Behördendeutsch etwas anderes bedeuten. Gemessen am Selbsttest: sie
# waren die Hauptquelle der Widersprüche, weil sie in JEDEM zweiten Käufernamen vorkommen
# und dort keinen Ort bezeichnen.
#
#   „Studentenwerk Leipzig"      → „studentenwerk" ist ein Ort in Schleswig-Holstein
#   „Verkehrsbetriebe Grafschaft" → „grafschaft" ist eine Gemeinde in Rheinland-Pfalz
_KEINE_ORTE = {"studentenwerk", "grafschaft", "bauamt", "landkreis", "gemeinde", "stadtwerke",
               "kreis", "amt", "hochschule", "universitaet", "klinikum", "zweckverband",
               "wasserverband", "abfallwirtschaft", "verwaltung", "bezirk", "region"}


def ortsverzeichnis() -> dict[str, str]:
    """Gefalteter Ortsname → NUTS-1, aber NUR wo der Name eindeutig zu einem Land gehört.

    „Neustadt" gibt es in acht Ländern; solche Namen fliegen raus. Das kostet Abdeckung und
    ist der Punkt: ein falsches Bundesland ist schlimmer als keines, weil danach gefiltert
    wird.
    """
    treffer: dict[str, set[str]] = {}
    with GEONAMES.open(encoding="utf-8") as f:
        for z in csv.reader(f, delimiter="\t"):
            if len(z) > 3 and z[3] in LAND_NUTS1:
                w = _worte(z[2])
                k = " ".join(w)
                if len(k) >= 5 and k not in _KEINE_ORTE and w[0] not in _KEINE_ORTE:
                    treffer.setdefault(k, set()).add(LAND_NUTS1[z[3]])
    return {k: next(iter(v)) for k, v in treffer.items() if len(v) == 1}


def ort_im_namen(name: str, orte: dict[str, str], sortiert: list[str]) -> str | None:
    """Der LÄNGSTE Ortsname, der im Käufernamen steckt.

    ⚠ Die erste Fassung zerlegte den Namen in Wörter und nahm den ersten Treffer. Gemessen
    widersprach sie in 8,8 % der prüfbaren Fälle dem anderen Weg, und die Beispiele zeigten
    warum: „Stadt Neustadt am Rübenberge" traf auf „neustadt" (in Thüringen) statt auf den
    vollen Namen, „Staatliches Bauamt Weilheim" auf ein anderes Weilheim. Der längste
    zusammenhängende Treffer ist die spezifischere Aussage — „neustadtamruebenberge" schlägt
    „neustadt", weil es nur einen davon gibt.
    """
    worte = _worte(name or "")
    # Alle zusammenhängenden Wortfolgen des Namens, längste zuerst: „neustadt am ruebenberge"
    # gewinnt gegen „neustadt", weil es die spezifischere Aussage ist.
    for laenge in range(min(5, len(worte)), 0, -1):
        for i in range(len(worte) - laenge + 1):
            folge = " ".join(worte[i:i + laenge])
            if folge in orte:
                return orte[folge]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    a = ap.parse_args()

    import duckdb
    import pandas as pd

    con = duckdb.connect()
    le = (G / "lead_export.parquet").as_posix()
    zeilen = con.execute(f"""
        WITH bekannt AS (SELECT buyer_name, any_value(buyer_nuts1) AS nuts1
                         FROM '{le}' WHERE buyer_nuts1 IS NOT NULL AND buyer_nuts1 <> ''
                         GROUP BY 1)
        SELECT l.lead_id, l.buyer_name, b.nuts1
        FROM '{le}' l LEFT JOIN bekannt b ON b.buyer_name = l.buyer_name
        WHERE l.buyer_nuts1 IS NULL OR l.buyer_nuts1 = ''""").fetchall()

    orte = ortsverzeichnis()
    # Einmal nach Länge sortieren statt je Name — 17.000 Einträge mal 6.500 Namen wäre sonst
    # eine Viertelstunde statt zwei Sekunden.
    sortiert = []                                # Wortfolgen-Abgleich braucht keine Sortierung
    aus, einig, uneinig = [], 0, 0
    for lead_id, name, ueber_kaeufer in zeilen:
        ueber_ort = ort_im_namen(name, orte, sortiert)
        if ueber_kaeufer and ueber_ort:
            if ueber_kaeufer == ueber_ort:
                einig += 1
                quelle, nuts1 = "beide_wege", ueber_kaeufer
            else:
                # ⚠ WIDERSPRUCH HEISST VERZICHT. „Landesbetrieb Straßenbau NRW, Regionalniederlassung
                # Rhein-Sieg" — der Käufer sitzt woanders als der Ortsname im Titel. Wer hier eine
                # Seite wählt, rät; und geraten wird nach diesem Wert gefiltert.
                uneinig += 1
                continue
        elif ueber_kaeufer:
            quelle, nuts1 = "gleicher_kaeufer", ueber_kaeufer
        elif ueber_ort:
            quelle, nuts1 = "ortsname", ueber_ort
        else:
            continue
        aus.append({"lead_id": lead_id, "buyer_nuts1_abgeleitet": nuts1, "quelle": quelle})

    df = pd.DataFrame(aus)
    gesamt = len(zeilen)
    print(f"  {gesamt:,} Leads ohne Bundesland · {len(df):,} abgeleitet ({len(df)/gesamt:.0%})")
    if not df.empty:
        print("  " + " · ".join(f"{k}: {v:,}" for k, v in df.quelle.value_counts().items()))
    pruefbar = einig + uneinig
    if pruefbar:
        print(f"  Selbsttest: wo beide Wege greifen ({pruefbar:,}), widersprechen sie sich "
              f"{uneinig:,}-mal ({uneinig/pruefbar:.1%}) — diese Leads bleiben leer.")
    if a.probe:
        print("  (Probe — nichts geschrieben)")
        return 0
    df.to_parquet(ZIEL, index=False)
    print(f"  ✓ {ZIEL.relative_to(ROOT)} — `lead_export` bleibt unverändert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
