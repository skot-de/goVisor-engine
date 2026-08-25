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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── JE LAND ──────────────────────────────────────────────────────────────────────────
# Bis 2026-08-23 lief dieses Skript ausschliesslich fuer Deutschland. Gemessen fielen
# dadurch 6.856 von 10.891 oesterreichischen Leads (63 %) aus JEDER Regions- und
# Umkreissuche — nicht weil sie nicht passten, sondern weil sie nichts sagten.
#
# ⚠ „Bundesland" sitzt nicht in jedem Land auf derselben NUTS-Stelle, und das ist der
# Grund, warum eine blosse Schleife ueber die Laender nicht genuegt haette:
#     DE  NUTS-1 (3 Stellen)  DE2  = Bayern
#     AT  NUTS-2 (4 Stellen)  AT13 = Wien       (AT1 waere „Ostoesterreich", drei Laender)
#     CH  NUTS-3 (5 Stellen)  CH021 = Bern      (CH0 waere die ganze Schweiz)
# Dieselbe Tabelle steht in `govisor/gold.py` als `_REGION_STELLEN`; sie MUESSEN
# uebereinstimmen, sonst leitet dieses Skript eine Ebene ab, die der Export nicht liest.
#
# Die Namensliste je Land kommt aus `dim_nuts` des Landes und nicht aus einer getippten
# Konstante: die 9 oesterreichischen Bundeslaender und 26 Schweizer Kantone stehen dort
# bereits, in der Schreibweise, die auch die Anzeige verwendet („Bern / Berne").
LAENDER = ("DE", "AT", "CH")
REGION_STELLEN = {"DE": 3, "AT": 4, "CH": 5}

# DE bleibt auf der getippten Liste: geonames fuehrt die deutschen Laender auch auf
# Englisch, und die Zuordnung Name→NUTS ist hier historisch geprueft (s. u.).
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
               "wasserverband", "abfallwirtschaft", "verwaltung", "bezirk", "region",
               # Oesterreich, 2026-08-23 nachgemessen: derselbe Fehlertyp, anderes
               # Behoerdendeutsch. „stadt" ist in AT ein Ortsname und stand allein fuer 46
               # der 80 Widersprueche des Selbsttests („Magistrat der Stadt Wien" landete
               # damit in Kaernten). Ohne diese Zeilen widersprachen sich die beiden Wege
               # in 58 % der pruefbaren Faelle — gegenueber 6,5 % in Deutschland.
               "stadt", "kammer", "hochbau", "strassen", "strasse", "steuer", "wildbach",
               "stiftung", "magistrat", "landesregierung", "direktion", "teilunternehmung",
               "abteilung", "marktgemeinde", "bezirkshauptmannschaft"}


def _verwaltungseinheiten(land: str) -> dict[str, str]:
    """geonames-Bezeichnung der Verwaltungseinheit → NUTS-Kennung, je Land.

    DE steht als geprueft getippte Liste (`LAND_NUTS1`) da. Fuer AT und CH kommt die
    Zuordnung aus `dim_nuts` des Landes und wird ueber den NAMEN an geonames geknuepft:
    „Wien" → AT13, „Zürich" → CH040. Das ist noetig, weil geonames keine NUTS kennt,
    sondern nur Verwaltungsnamen.

    ⚠ Die Schweizer `dim_nuts`-Namen sind MEHRSPRACHIG („Bern / Berne", „Valais /
    Wallis"), geonames fuehrt je Kanton nur eine Schreibweise und die auch noch
    unterschiedlich („Canton de Berne", „Kanton Aargau"). Deshalb wird jeder Namensteil
    einzeln eingehaengt und die Vorsilben „Kanton"/„Canton de"/„Canton du" entfernt —
    ohne das griffe die Zuordnung fuer die Haelfte der Kantone nicht.
    """
    if land == "DE":
        return dict(LAND_NUTS1)
    import duckdb
    stellen = REGION_STELLEN[land]
    quelle = (ROOT / "data/gold" / land / "dim_nuts.parquet")
    if not quelle.exists():
        return {}
    zeilen = duckdb.connect().execute(
        f"SELECT nuts_code, name FROM '{quelle.as_posix()}' WHERE length(nuts_code) = {stellen}"
    ).fetchall()
    aus: dict[str, str] = {}
    for code, name in zeilen:
        for teil in str(name or "").split("/"):
            if teil.strip():
                aus[_ohne_vorsilbe(teil)] = code
    return aus


def _ohne_vorsilbe(name: str) -> str:
    """„Canton de Berne" → „berne", „Kanton Zürich" → „zuerich", „Bern" → „bern".

    ⚠ Die Vorsilbe steht auf der GEONAMES-Seite, nicht in `dim_nuts` — dort heisst der
    Kanton „Bern / Berne". Der erste Versuch schnitt sie auf der falschen Seite ab und
    erkannte deshalb nur 646 von 4.520 Schweizer Zeilen; die vier groessten Kantone
    (Bern, Vaud, Zuerich, Wallis) fielen komplett aus.
    """
    return " ".join(_worte(re.sub(r"^\s*(kanton|canton\s+d[eu])\s+", " ", name.strip(),
                                  flags=re.I)))


def ortsverzeichnis(land: str) -> dict[str, str]:
    """Gefalteter Ortsname → Regions-Kennung, aber NUR wo der Name eindeutig ist.

    „Neustadt" gibt es in acht Bundesländern; solche Namen fliegen raus. Das kostet
    Abdeckung und ist der Punkt: eine falsche Region ist schlimmer als keine, weil danach
    gefiltert wird.
    """
    einheiten = _verwaltungseinheiten(land)
    quelle = ROOT / "data/reference/geonames" / f"{land}.txt"
    if not einheiten or not quelle.exists():
        return {}
    # geonames nennt die Verwaltungseinheit in Spalte 4 (admin1). Der Abgleich laeuft
    # ueber die gefaltete Schreibweise, sonst scheitert „Zürich" an „Zurich".
    gefaltet = {_ohne_vorsilbe(k): v for k, v in einheiten.items()}
    treffer: dict[str, set[str]] = {}
    with quelle.open(encoding="utf-8") as f:
        for z in csv.reader(f, delimiter="\t"):
            if len(z) <= 3:
                continue
            code = gefaltet.get(_ohne_vorsilbe(z[3]))
            if not code:
                continue
            w = _worte(z[2])
            k = " ".join(w)
            if len(k) >= 5 and k not in _KEINE_ORTE and w[0] not in _KEINE_ORTE:
                treffer.setdefault(k, set()).add(code)
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


def fuer_land(land: str, probe: bool) -> int:
    import duckdb
    import pandas as pd

    G = ROOT / "data/gold" / land
    ZIEL = G / "lead_region_fill.parquet"
    con = duckdb.connect()
    le = (G / "lead_export.parquet").as_posix()
    if not Path(le).exists():
        print(f"  {land}: keine Gold-Ebene — uebersprungen.")
        return 0
    zeilen = con.execute(f"""
        WITH bekannt AS (SELECT buyer_name, any_value(buyer_nuts1) AS nuts1
                         FROM '{le}' WHERE buyer_nuts1 IS NOT NULL AND buyer_nuts1 <> ''
                         GROUP BY 1)
        SELECT l.lead_id, l.buyer_name, b.nuts1
        FROM '{le}' l LEFT JOIN bekannt b ON b.buyer_name = l.buyer_name
        WHERE l.buyer_nuts1 IS NULL OR l.buyer_nuts1 = ''""").fetchall()

    orte = ortsverzeichnis(land)
    if not orte:
        print(f"  {land}: kein Ortsverzeichnis (geonames oder dim_nuts fehlt) — uebersprungen.")
        return 0
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
    if not gesamt:
        print(f"  {land}: kein Lead ohne Region.")
        return 0
    print(f"  {land}: {gesamt:,} Leads ohne Region · {len(df):,} abgeleitet ({len(df)/gesamt:.0%})")
    if not df.empty:
        print("  " + " · ".join(f"{k}: {v:,}" for k, v in df.quelle.value_counts().items()))
    pruefbar = einig + uneinig
    if pruefbar:
        print(f"  Selbsttest: wo beide Wege greifen ({pruefbar:,}), widersprechen sie sich "
              f"{uneinig:,}-mal ({uneinig/pruefbar:.1%}) — diese Leads bleiben leer.")
    if probe:
        print("  (Probe — nichts geschrieben)")
        return len(df)
    df.to_parquet(ZIEL, index=False)
    print(f"  ✓ {ZIEL.relative_to(ROOT)} — `lead_export` bleibt unverändert.")
    return len(df)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--laender", default=",".join(LAENDER),
                    help="Komma-Liste, Vorgabe: alle (DE,AT,CH)")
    a = ap.parse_args()
    for land in [x.strip().upper() for x in a.laender.split(",") if x.strip()]:
        fuer_land(land, a.probe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
