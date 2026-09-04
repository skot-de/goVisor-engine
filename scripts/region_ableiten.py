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

**Die Gegenprobe (seit 2026-09-01).** Geprüft werden auch die Leads, die schon eine
Region TRAGEN. Bis dahin galt ein dastehender Wert unbesehen als belegt und ging als
`regionQuelle='amtlich'` ins Frontend — auch wenn die Anschrift ihm offen widersprach.
So standen 172 Leads der Landeshauptstadt Magdeburg unter „Nordrhein-Westfalen": ein
Parser-Fehlgriff auf die NUTS des eSenders (behoben in
`govisor/schema._iter_named_ausserhalb`), den die ganze Kette widerspruchslos
weitergereicht hat. Solche Leads heissen jetzt `widersprüchlich`, nicht `amtlich`.
Es ist derselbe Grundsatz wie beim Selbsttest oben: **markieren statt wegwerfen** —
der Wert bleibt stehen, nur die Behauptung „belegt" fällt weg.

⚠ **Der Zeuge war zuerst der falsche (korrigiert 2026-09-02).** Die erste Fassung prüfte
gegen den ORTSNAMEN und meldete 336 Widersprüche. Jeder einzelne wurde gegen die
Käufer-PLZ aus Silber nachgeprüft — die Vollerhebung, nicht eine Stichprobe:

    entscheidbar (PLZ eindeutig)                274 von 336
      Region stimmt, der Ortsname war falsch    134   49 %   ← Fehlalarm
      Region wirklich falsch                    140   51 %
    nicht entscheidbar                           62          ← 61 davon der BER

Drei Fehlerquellen, alle behoben: der Eindeutigkeits-Riegel verglich VOLLE Schreibweisen
(„weilheim" galt als eindeutig, obwohl es „Weilheim in Oberbayern" gibt), die PLZ-Datei
enthält Firmen mit eigener Postleitzahl, und ein Ortsname ist als Zeuge ohnehin schwach:
er ist nur bei 7 % der Leads mit Region prüfbar, die PLZ bei 97 %. Seitdem prüft die
Gegenprobe die **Postleitzahl** — und schweigt, wo der Käufer mehrere Anschriften führt.

⚠️ Geschrieben wird eine eigene Datei (`lead_region_fill.parquet`), nicht `lead_export`.
Wer die Ableitung nicht mag, löscht die Datei — abgeleitete Werte tragen ausserdem ihre
Herkunft mit, damit sie in der Anzeige unterscheidbar bleiben.

Aufruf::  scripts/region_ableiten.py [--probe]
"""
from __future__ import annotations

import sys
import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# ⚠ ERST den Projektpfad, DANN `govisor` importieren. Unter launchd gibt es kein
# PYTHONPATH; ein Import davor bricht stumm ab (s. test_skripte_finden_govisor_ohne_pythonpath).
sys.path.insert(0, str(ROOT))
from govisor.laender import AKTIV as _AKTIV  # noqa: E402

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
# ⚠ Eine Stelle: `govisor/laender.py`. Hier stand eine eigene Liste — bis zum
# 2026-09-04 gab es ein Dutzend davon, und Luxemburg fehlte in der Haelfte.
LAENDER = _AKTIV
# ⚠ LU: eine einzige Region (LU/LU0/LU00/LU000, alle „Luxembourg"). Muss zu
# `gold._REGION_STELLEN` passen — ein Test haelt beides zusammen.
REGION_STELLEN = {"DE": 3, "AT": 4, "CH": 5, "LU": 3}

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


def _ortsbeleg(land: str) -> set[str]:
    """Gefaltete Namen, die ein Ortsverzeichnis als ORT (oder Verwaltungseinheit) belegt.

    ⚠ DIE PLZ-DATEI VON GEONAMES IST KEIN ORTSVERZEICHNIS. Sie fuehrt jede Postleitzahl
    auf, und die Deutsche Post vergibt eigene an Grosskunden — dort steht dann die FIRMA,
    wo man den Ort erwartet: „siemens", „bosch", „a nattermann cie gmbh", „BERLIN-
    KOELNISCHE VERSICHERUNGEN". Gemessen am 2026-09-02: **5.317 der 17.628 deutschen
    Namen sind keine Orte** (AT: 0, CH: 1 — das ist eine deutsche Eigenart).

    Ohne diesen Filter waere der Basisnamen-Riegel unten unbrauchbar: eine einzige
    Koelner Versicherung mit „BERLIN" im Namen macht „berlin" mehrdeutig und kostet
    32 belegte Widerspruchs-Funde. Die Reihenfolge ist also nicht beliebig — erst
    Firmen raus, dann Namen vergleichen.

    Belegt wird gegen den geonames-Gazetteer (`DE_gazetteer.txt`, Merkmalsklasse P
    = bewohnter Ort, A = Verwaltungseinheit; Download-URL siehe geonames-readme).
    ⚠ EU-WEIT OFFEN: der Gazetteer liegt bisher nur fuer DE. Fuer Laender ohne Datei
    bleibt der Filter aus — vertretbar, solange die PLZ-Datei dort sauber ist (fuer
    AT/CH nachgemessen), aber vor jedem neuen Land nachzuzaehlen.
    """
    quelle = ROOT / "data/reference/geonames" / f"{land}_gazetteer.txt"
    if not quelle.exists():
        return set()
    belegt: set[str] = set()
    with quelle.open(encoding="utf-8") as f:
        for z in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if len(z) <= 7 or z[6] not in ("P", "A"):
                continue
            # Name, ASCII-Name und Alternativnamen — „Zürich"/„Zurich" ist derselbe Ort.
            for name in (z[1], z[2], *(z[3].split(",") if z[3] else ())):
                k = " ".join(_worte(name))
                if k:
                    belegt.add(k)
    return belegt


def ortsverzeichnis(land: str) -> dict[str, str]:
    """Gefalteter Ortsname → Regions-Kennung, aber NUR wo der Name eindeutig ist.

    „Neustadt" gibt es in acht Bundesländern; solche Namen fliegen raus. Das kostet
    Abdeckung und ist der Punkt: eine falsche Region ist schlimmer als keine, weil danach
    gefiltert wird.

    ⚠ EINDEUTIG HEISST: AUCH DER BASISNAME IST EINDEUTIG (seit 2026-09-02). Bis dahin
    wurden VOLLE Schreibweisen verglichen, und daran ist der Riegel reihenweise
    vorbeigelaufen: die PLZ-Datei fuehrt „Weilheim an der Teck" (BW), „Weilheim in
    Oberbayern" (BY) und ein blosses „Weilheim" (BW). Drei verschiedene Zeichenketten,
    also galt „weilheim" als eindeutig BW — und „Staatliches Bauamt Weilheim", das in
    82362 Weilheim i.OB sitzt, bekam Baden-Wuerttemberg. Genauso „Heidenheim" (BY, weil
    „Heidenheim an der Brenz" anders geschrieben ist), „Esslingen", „Ehingen",
    „Dillingen", „Koenigstein", „Landsberg" — und „neustadt", das der Docstring oben als
    Musterbeispiel eines ausgeschlossenen Namens nennt und das trotzdem drinstand.

    Der Riegel prueft deshalb WORTPRAEFIXE: ein Name ist nur dann eindeutig, wenn keine
    laengere Ortsbezeichnung in einer anderen Region mit denselben Woertern beginnt.
    „weilheim" faellt (Praefix von „weilheim in oberbayern"), „weilheim an der teck"
    bleibt (es gibt kein zweites). Gemessen kostet das 10 von 5.012 Ableitungen und
    senkt die Widerspruchsquote des Selbsttests von 8,5 % auf 5,0 %.
    """
    einheiten = _verwaltungseinheiten(land)
    quelle = ROOT / "data/reference/geonames" / f"{land}.txt"
    if not einheiten or not quelle.exists():
        return {}
    belegt = _ortsbeleg(land)
    # geonames nennt die Verwaltungseinheit in Spalte 4 (admin1). Der Abgleich laeuft
    # ueber die gefaltete Schreibweise, sonst scheitert „Zürich" an „Zurich".
    gefaltet = {_ohne_vorsilbe(k): v for k, v in einheiten.items()}
    treffer: dict[str, set[str]] = {}
    praefixe: dict[tuple[str, ...], set[str]] = {}
    with quelle.open(encoding="utf-8") as f:
        for z in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if len(z) <= 3:
                continue
            code = gefaltet.get(_ohne_vorsilbe(z[3]))
            if not code:
                continue
            w = _worte(z[2])
            k = " ".join(w)
            if belegt and k not in belegt:
                continue                      # eine Firma mit eigener PLZ, kein Ort
            for i in range(1, len(w) + 1):
                praefixe.setdefault(tuple(w[:i]), set()).add(code)
            if len(k) >= 5 and k not in _KEINE_ORTE and w[0] not in _KEINE_ORTE:
                treffer.setdefault(k, set()).add(code)
    return {k: next(iter(v)) for k, v in treffer.items()
            if len(v) == 1 and len(praefixe.get(tuple(k.split()), ())) == 1}


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


def einheit_im_namen(name: str, einheiten: dict[str, str]) -> str | None:
    """Die Verwaltungseinheit (Bundesland/Kanton), die als GANZE WORTFOLGE im Namen steht.

    ⚠ WARUM ES DIESEN DRITTEN WEG GIBT. Nach `gleicher_kaeufer` und `ortsname` blieben am
    2026-09-04 noch 1.269 offene DE-Leads ohne Region — und 1.195 davon tragen nicht einmal
    eine Kaeufer-PLZ, es gibt also nichts abzuleiten. Aber 208 nennen ihr Land im NAMEN:
    „Vermoegens- und Hochbauverwaltung Baden-Wuerttemberg" (90), „Landeswohlfahrtsverband
    Hessen" (60). Der Ortsabgleich greift dort nicht, weil das keine Staedte sind.

    ⚠ ZWEI FALLEN, DIE EINE NAIVE FASSUNG STELLT — beide in der Probe schon gesehen:

      · TEILZEICHENKETTE. „Sachsen" steckt in „Sachsenforst" und in „Sachsen-Anhalt". Diese
        Fassung nutzt darum `_worte` und ganze Wortfolgen, wie `ort_im_namen`. Der Preis ist
        ehrlich: „Staatsbetrieb Sachsenforst" faellt raus, weil „sachsenforst" EIN Wort ist.
        Lieber 14 Leads weniger als ein Verfahren zur Klasse „ahlen in Zahlenwerk".
      · MEHRDEUTIGKEIT. „Deutsche Rentenversicherung Berlin-Brandenburg" nennt ZWEI Laender.
        Wer hier eines waehlt, raet — und nach diesem Wert wird gefiltert. Zwei verschiedene
        Codes heissen deshalb: kein Ergebnis.

    ⚠ Und es ist NICHT deutsch: `_verwaltungseinheiten(land)` liefert Name→Code fuer jedes
    Land (AT 9 Bundeslaender, CH 31 Kantonsnamen). Eine eigene DE-Liste waere genau die
    Sorte Altlast, die der EU-weit-Grundsatz meint.

    **Gemessen am 2026-09-04 (DE):** 116 Leads bekommen ihre Region allein ueber diesen Weg,
    240 weitere steigen von einem auf mehrere einige Wege. NETTO nur +25 abgeleitete — denn
    die Widerspruchsquote des Selbsttests steigt von 5,6 % auf 8,5 %, und 91 vorher
    abgeleitete Leads werden jetzt verworfen.
    ⚠ DAS IST EIN GEWINN, KEIN SCHADEN. An 19 pruefbaren Widerspruechen (Kaeufer-PLZ als
    Zeuge) lag in **19 von 19** der Verwaltungsname richtig und der Ortsname falsch:
    „Landgesellschaft Sachsen-Anhalt GmbH" wurde ueber das Wort „anhalt" einem BAYERISCHEN
    Ort zugeordnet. Die 91 waren also schon vorher falsch — sie sahen nur nicht so aus.
    Wo der Weg gegen die PLZ pruefbar war, lag er 30-mal von 30 richtig.
    """
    worte = _worte(name or "")
    if not worte:
        return None
    # Längste Wortfolge zuerst — „sachsen anhalt" schlägt „sachsen", weil es die
    # spezifischere Aussage ist. Dieselbe Regel wie bei `ort_im_namen`.
    treffer: list[tuple[int, int, str]] = []          # (start, laenge, code)
    for laenge in range(min(4, len(worte)), 0, -1):
        for i in range(len(worte) - laenge + 1):
            folge = " ".join(worte[i:i + laenge])
            code = einheiten.get(folge)
            if code and not any(a <= i < a + l for a, l, _ in treffer):
                treffer.append((i, laenge, code))
    codes = {c for _, _, c in treffer}
    return codes.pop() if len(codes) == 1 else None


def region_korrekturen(land: str) -> dict[tuple[str, str, str], str]:
    """Von Hand geprueft: (Kaeufername, PLZ, Kennung ALT) → Kennung NEU.

    ⚠ Die ALTE Kennung gehoert in den Schluessel, nicht in den Wert. Dieselbe Stelle
    unter derselben Anschrift kann mehrere falsche Angaben tragen: die AGES in Wien 1220
    meldete einmal Tirol und einmal Steiermark. Mit (Name, PLZ) als Schluessel haette die
    zweite Zeile die erste ueberschrieben — lautlos, und eine der beiden Korrekturen
    waere verschwunden.

    Die Gegenprobe unten kann sagen, DASS Anschrift und Regionsangabe auseinanderlaufen.
    Welche Seite recht hat, kann sie nicht sagen — dafuer braucht es einen Blick auf den
    Fall. Diese Datei ist dieser Blick, einmal getan und aufgeschrieben; dieselbe Bauart
    wie ``curated/<L>_entity_aliases.csv``: **belegt und von Hand geprueft, kein
    Namensstamm-Automatismus.**

    Am 2026-09-02 gingen so alle 80 deutschen Funde durch. Der entscheidende Zeuge war
    meist der Kaeufer selbst: die AOK PLUS nennt in 899 eigenen Saetzen Thueringen und in
    145 Sachsen, und die 20 gemeldeten Leads gehoerten zur Minderheit. Wo eine Behoerde
    ihre eigene Region hundertfach gleich angibt, ist die Ausreisserzeile der Fehler.

    ⚠ ``region_neu == region_alt`` heisst **geprueft und richtig** — dann schweigt der
    Marker, statt weiter zu melden. Die BKK VerbundPlus sitzt in Biberach (DE1) und
    fuehrt Muenchen nur als Zweitanschrift; ihre Angabe stimmt, die Anschrift auf der
    Bekanntmachung ist die schwaechere Auskunft.

    ⚠ Der Schluessel ist Name UND PLZ. Zieht eine Behoerde um, greift die Korrektur nicht
    mehr — das ist gewollt: eine neue Anschrift ist ein neuer Fall, kein stiller Erbe.
    ``tests/test_plumbing.py`` haelt tote Zeilen fest, damit die Datei nicht verrottet.
    """
    quelle = ROOT / "curated" / f"{land}_region_korrektur.csv"
    if not quelle.exists():
        return {}
    aus: dict[tuple[str, str, str], str] = {}
    with quelle.open(encoding="utf-8") as f:
        for z in csv.DictReader(f):
            name, plz = (z.get("buyer_name") or "").strip(), (z.get("plz") or "").strip()
            alt, neu = (z.get("region_alt") or "").strip(), (z.get("region_neu") or "").strip()
            if name and plz and alt and neu:
                aus[(name, plz, alt)] = neu
    return aus


def plz_verzeichnis(land: str) -> dict[str, str]:
    """Postleitzahl → Regions-Kennung, nur wo die PLZ in genau EINER Region liegt.

    Der Ortsname war der falsche Zeuge. Eine PLZ ist es nicht: gemessen am 2026-09-02
    sind **99,8 % der deutschen PLZ eindeutig** (AT 97,8 %, CH 99,4 %), sie kennt keine
    Namensvarianten, keinen Behoerdenzusatz und keine Umlautfaltung — die Falle aus
    `docs/laender/14 Schrift` (`Łódź` → `['d']`) trifft sie gar nicht erst.

    Die verbleibenden Mehrdeutigkeiten sind echt und keine Schwaeche: 12529 liegt
    gleichzeitig in Schoenefeld (Brandenburg) und in Berlin — genau die Grenzlage des
    Hauptstadtflughafens. Solche PLZ fallen raus und melden nichts.
    """
    einheiten = _verwaltungseinheiten(land)
    quelle = ROOT / "data/reference/geonames" / f"{land}.txt"
    if not einheiten or not quelle.exists():
        return {}
    gefaltet = {_ohne_vorsilbe(k): v for k, v in einheiten.items()}
    treffer: dict[str, set[str]] = {}
    with quelle.open(encoding="utf-8") as f:
        for z in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if len(z) <= 3:
                continue
            code = gefaltet.get(_ohne_vorsilbe(z[3]))
            if code:
                treffer.setdefault(z[1].strip(), set()).add(code)
    return {k: next(iter(v)) for k, v in treffer.items() if len(v) == 1}


def _kaeufer_plz(con, land: str) -> dict[str, str]:
    """notice_id → Postleitzahl des Kaeufers, aus Silber.

    ⚠ `lead_export` fuehrt die PLZ nicht, nur Ort und NUTS. Sie steht eine Ebene tiefer
    in `silver/<L>/notice_parties` und ist dort erstaunlich vollstaendig: **DE 99,4 %,
    AT 93,8 %, CH 100 %** der Leads mit Region tragen eine Kaeufer-PLZ (gemessen
    2026-09-02). Der Docstring oben sagt „von den 6.460 Leads ohne Bundesland haben 38
    eine PLZ" — das gilt fuer die ABLEITUNG, wo genau die Quellen ohne NUTS liegen. Fuer
    die GEGENPROBE, die nur Leads MIT Region ansieht, ist die Lage umgekehrt.
    """
    quelle = (ROOT / "data/silver" / land / "notice_parties").as_posix()
    if not Path(quelle).exists():
        return {}
    # ⚠ `any_value` ist hier NICHT der Fehler, den Weg 1 hatte: nachgemessen am
    # 2026-09-02 traegt keine einzige Bekanntmachung zwei verschiedene Kaeufer-PLZ
    # (0 von 1.580.051 DE, 129.214 AT, 122.152 CH). Die Gruppe hat genau einen Wert.
    return dict(con.execute(f"""
        SELECT notice_id, any_value(postal_code) FROM '{quelle}/*/*.parquet'
        WHERE role = 'buyer' AND postal_code IS NOT NULL AND postal_code <> ''
        GROUP BY 1""").fetchall())


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
    # Die gueltigen Regionskennungen des Landes — gebraucht von BEIDEN Seiten: von der
    # Ableitung (Weg 1 darf kein `ATZZ` weiterreichen) und von der Gegenprobe.
    gueltig = set(_verwaltungseinheiten(land).values())

    # ⚠ EIN WERT IM FELD IST NOCH KEINE REGION. Bis zum 2026-09-04 galt jeder nicht-leere
    # `buyer_nuts1` als „hat Region": der Lead wurde nur auf WIDERSPRUCH geprueft und nie
    # gefuellt. Damit fielen genau die Leads durch, die Hilfe gebraucht haetten —
    # gemessen: 829 CH-Leads mit rohem Kantonskuerzel („ZH", „BE") und 518 AT-Leads mit dem
    # blossen Landescode „AT" oder Extra-Regio „ATZ". Beides ist kein NUTS dieser Ebene.
    #
    # Zwei getrennte Antworten, weil es zwei verschiedene Faelle sind:
    #   CH  das Kuerzel IST auflösbar — `simap._KANTON_NUTS` deckt alle 829 zu 100 %.
    #       ⚠ „BE" ist dabei der gefaehrliche: hier Bern, im NUTS-Raum Belgien.
    #   AT  „AT" (Landesebene) und „ATZ" (Extra-Regio) sind nicht aufloesbar — sie gelten
    #       ab jetzt als KEINE Region, damit die PLZ-Ableitung sie ueberhaupt erreicht.
    #       236 der 518 tragen eine Kaeufer-PLZ.
    # ⚠ NICHT als „bundesweit" behandeln: `is_nationwide` heisst „die Leistung ist
    # ortsunabhaengig", der Landescode heisst „wir kennen den Kaeufer nur grob". Wer das
    # verwechselt, spuelt ortsgebundene Vergaben in jede Umkreissuche.
    from govisor.simap import _KANTON_NUTS as _KANTONE
    _zweige = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in _KANTONE.items())
    NORM = f"CASE upper(trim(buyer_nuts1)) {_zweige} ELSE buyer_nuts1 END"
    _in = ", ".join(f"'{g}'" for g in sorted(gueltig)) or "''"
    # ── Weg 1: derselbe Kaeufername traegt anderswo eine Region ───────────────────
    # ⚠ MEHRHEIT, NICHT `any_value` (seit 2026-09-02). Bis dahin stand hier
    # `any_value(buyer_nuts1)` — und das waehlt bei einem Kaeufer mit MEHREREN Regionen
    # beliebig. Zwei Laeufe ueber denselben Bestand lieferten deshalb einmal 5.002 und
    # einmal 5.003 deutsche Ableitungen. Es ist kein Randfall: in Oesterreich haengen
    # 8.352 von 9.373 Weg-1-Leads (89 %) an einem uneinigen Namen, weil OeBB und ASFINAG
    # bundesweit ausschreiben (gemessen 2026-09-02).
    #
    # ⚠ Und die Werte wurden nicht auf GUELTIGKEIT geprueft — der Riegel der Gegenprobe
    # weiter unten war nie auf diese Seite uebertragen worden. Ergebnis in der gebauten
    # Datei: 199 oesterreichische Leads erbten `ATZZ` (Extra-Regio), 2 Schweizer `BS`
    # (Kantonskuerzel) und **4 deutsche `BE3` — das ist Bruessel.** Sie loesen in
    # `dim_nuts` gegen nichts auf, standen im Export also als „abgeleitet" mit leerer
    # Region da. Genau die Fehlerklasse „Fix nur auf einer Seite angewandt".
    #
    # Bei GLEICHSTAND wird nichts abgeleitet — dieselbe Regel, die der Selbsttest
    # weiter unten anwendet: wer hier eine Seite waehlt, raet, und danach wird gefiltert.
    zaehlung = con.execute(f"""
        SELECT buyer_name, buyer_nuts1, count(*) FROM '{le}'
        WHERE buyer_nuts1 IS NOT NULL AND buyer_nuts1 <> '' GROUP BY 1, 2""").fetchall()
    je_name: dict[str, list[tuple[int, str]]] = {}
    for name, code, anzahl in zaehlung:
        if code in gueltig:
            je_name.setdefault(name, []).append((anzahl, code))
    mehrheit: dict[str, str] = {}
    for name, werte in je_name.items():
        # Sortierschluessel mit dem CODE als zweitem Glied: gleiche Zahlen sollen nicht
        # in Einfuegereihenfolge stehen, sonst waere die Auswahl wieder vom Zufall abhaengig.
        werte.sort(key=lambda x: (-x[0], x[1]))
        if len(werte) == 1 or werte[0][0] > werte[1][0]:
            mehrheit[name] = werte[0][1]
    zeilen = [(lead_id, name, mehrheit.get(name))
              for lead_id, name in con.execute(f"""
        SELECT lead_id, buyer_name FROM '{le}'
        WHERE buyer_nuts1 IS NULL OR buyer_nuts1 = ''
           OR {NORM} NOT IN ({_in})""").fetchall()]
    # ── Gegenprobe: die Leads, die SEHR WOHL eine Region tragen ────────────────────
    # Bis zum 2026-09-01 wurde hier nur ergaenzt, nie geprueft. Ein dastehender Wert
    # galt als belegt (`regionQuelle='amtlich'`) — auch dann, wenn der Kaeuferort ihm
    # offen widersprach. Genau so standen 172 Magdeburger Leads unter „Nordrhein-
    # Westfalen": der Parser hatte die NUTS des eSenders gegriffen (behoben in
    # `govisor/schema._iter_named_ausserhalb`), und nichts an der Kette hat widersprochen.
    vorhanden = con.execute(f"""
        SELECT lead_id, buyer_name, {NORM},
               CASE WHEN market_region_known THEN market_nuts3 END, title
        FROM '{le}' WHERE {NORM} IN ({_in})""").fetchall()

    orte = ortsverzeichnis(land)
    if not orte:
        print(f"  {land}: kein Ortsverzeichnis (geonames oder dim_nuts fehlt) — uebersprungen.")
        return 0
    # Einmal nach Länge sortieren statt je Name — 17.000 Einträge mal 6.500 Namen wäre sonst
    # eine Viertelstunde statt zwei Sekunden.
    sortiert = []                                # Wortfolgen-Abgleich braucht keine Sortierung
    aus, einig, uneinig = [], 0, 0
    # Verwaltungsnamen einmal falten — dieselbe Zerlegung wie beim Ortsabgleich, sonst
    # trifft „Baden-Württemberg" sein eigenes gefaltetes „baden wuerttemberg" nicht.
    einheiten_gefaltet = {" ".join(_worte(k)): v
                          for k, v in _verwaltungseinheiten(land).items() if _worte(k)}
    for lead_id, name, ueber_kaeufer in zeilen:
        # ⚠ DREI WEGE SEIT DEM 2026-09-04, und der Selbsttest gilt fuer ALLE. Der dritte
        # (`verwaltungsname`) ist der SCHWAECHSTE: der Name einer Landesbehoerde sagt ihre
        # Zustaendigkeit, nicht zwingend den Ort der Leistung. Genau deshalb darf er nicht
        # an der Pruefung vorbei — er wird wie die anderen verworfen, sobald er widerspricht.
        signale = {
            "gleicher_kaeufer": ueber_kaeufer,
            "ortsname": ort_im_namen(name, orte, sortiert),
            "verwaltungsname": einheit_im_namen(name, einheiten_gefaltet),
        }
        aktiv = {k: v for k, v in signale.items() if v}
        if not aktiv:
            continue
        werte = set(aktiv.values())
        if len(werte) > 1:
            # ⚠ WIDERSPRUCH HEISST VERZICHT. „Landesbetrieb Straßenbau NRW, Regionalniederlassung
            # Rhein-Sieg" — der Käufer sitzt woanders als der Ortsname im Titel. Wer hier eine
            # Seite wählt, rät; und geraten wird nach diesem Wert gefiltert.
            uneinig += 1
            continue
        nuts1 = werte.pop()
        if len(aktiv) > 1:
            einig += 1
            # ⚠ Der Wert „beide_wege" bleibt, auch wenn es jetzt drei sein koennen: er steht
            # im Bestand und in der Ausgabe. „Mehr als ein Weg war sich einig" ist dieselbe
            # Aussage; ein neuer Wert waere nur eine Umbenennung mit Folgekosten.
            quelle = "beide_wege"
        else:
            quelle = next(iter(aktiv))
        aus.append({"lead_id": lead_id, "buyer_nuts1_abgeleitet": nuts1, "quelle": quelle})

    # ── Widerspruch Anschrift ↔ Region ────────────────────────────────────────────
    # ⚠ GEPRUEFT WIRD GEGEN DIE POSTLEITZAHL, NICHT MEHR GEGEN DEN ORTSNAMEN.
    # Die erste Fassung (2026-09-01) nahm den Ortsnamen und meldete 336 Widersprueche.
    # Am 2026-09-02 wurde jeder einzelne gegen die Kaeufer-PLZ aus Silber nachgeprueft:
    # bei **134 von 274 entscheidbaren (49 %) stimmte die Region und der Ortsname war
    # der falsche Zeuge** — „Weilheim", „Heidenheim", „Esslingen", „Ehingen" gibt es
    # zweimal, und der Eindeutigkeits-Riegel verglich damals nur volle Schreibweisen.
    # Der Marker stand da schon im Frontend (`regionQuelle='widerspruechlich'`), also
    # sagte er jedem zweiten Mal etwas Falsches ueber einen richtigen Wert.
    #
    # Die PLZ ist der bessere Zeuge, und zwar in beide Richtungen:
    #   pruefbar      Ortsname 7 % der Leads mit Region   ·  PLZ 97 %
    #   eindeutig     Ortsname 95 % der Namen             ·  PLZ 99,8 %
    #
    # ⚠ NUR echte Regionskennungen vergleichen. In CH stehen im selben Feld auch
    # Kantonskuerzel („ZH", „VD", „AG") statt NUTS, in AT/DE die Extra-Regio-Codes
    # „ATZZ"/„DEZ" — 784 CH-, 513 AT-, 9 DE-Leads (gemessen 2026-09-02). Geprueft wird
    # deshalb gegen die LISTE der gueltigen Kennungen, nicht mehr ueber Praefix+Laenge:
    # „DEZ" ist drei Zeichen lang und faengt mit DE an, ist aber keine Region.
    # Die Formatluecke gehoert gesondert behandelt und steht als offener Punkt.
    plz_reg = plz_verzeichnis(land)
    plz_je_lead = _kaeufer_plz(con, land)
    # ── Tor „ein Standort" ────────────────────────────────────────────────────────
    # Eine Behoerde, deren Leads MEHRERE Anschriften tragen, hat mehrere Standorte —
    # dann ist eine abweichende Region keine Falschangabe, sondern eine andere
    # Niederlassung. Gemessen sind das die Bundesaemter und Netzbetreiber: Autobahn
    # GmbH, BWI, DB Netz, BAAINBw, Deutsche Rentenversicherung Berlin-Brandenburg.
    # Ohne dieses Tor melden sie 189 Widersprueche, mit ihm 120 — und die 69, die
    # wegfallen, sind genau die Klasse, die niemand als Fehler lesen soll.
    anschrift: dict[str, str] = {}
    standorte: dict[str, set[str]] = {}
    for lead_id, name, nuts1, _markt, _titel in vorhanden:
        reg = plz_reg.get(str(plz_je_lead.get(lead_id, "")).strip())
        if reg:
            anschrift[lead_id] = reg
            standorte.setdefault(name or "", set()).add(reg)
    stellen = REGION_STELLEN[land]
    kuratiert = region_korrekturen(land)
    widersprueche, korrigiert, pruefbar_v, fremdformat = [], [], 0, 0
    mehrere_standorte = leistungsort_stuetzt = titel_stuetzt = bestaetigt = 0
    genutzt: set[tuple[str, str]] = set()
    for lead_id, name, nuts1, markt, titel in vorhanden:
        if nuts1 not in gueltig:
            fremdformat += 1
            continue
        # ── Von Hand geprueft schlaegt jedes Tor ──────────────────────────────────
        # Bewusst VOR den Toren: eine kuratierte Zeile ist eine Aussage ueber den Fall,
        # kein Verdacht. Sie muss auch dort greifen, wo ein Tor den Verdacht gar nicht
        # erst aufkommen laesst — sonst blieben von den 20 falsch verorteten AOK-PLUS-
        # Leads genau die stehen, die der Leistungsort deckt.
        schluessel = ((name or "").strip(),
                      str(plz_je_lead.get(lead_id, "")).strip(), nuts1)
        neu = kuratiert.get(schluessel)
        if neu:
            genutzt.add(schluessel)
            if neu == nuts1:
                bestaetigt += 1                      # geprueft und richtig — nichts melden
            else:
                korrigiert.append({"lead_id": lead_id, "buyer_nuts1_abgeleitet": neu,
                                   "quelle": "korrektur_kuratiert", "widerspruch": False,
                                   "widerspruch_ort_nuts1": nuts1})
            continue
        reg = anschrift.get(lead_id)
        if reg is None:
            continue
        # `pruefbar_v` zaehlt JEDEN Lead mit Zeugen, auch die gleich uebergangenen —
        # sonst schrumpft der Nenner um die Faelle, die geprueft und fuer gut befunden
        # wurden, und die Widerspruchsquote sieht zehnmal so schlimm aus, wie sie ist.
        pruefbar_v += 1
        if len(standorte.get(name or "", ())) > 1:
            mehrere_standorte += 1
            continue
        # ── Veto des Leistungsorts ────────────────────────────────────────────────
        # Der Leistungsort (`perf_nuts`, aus den Ausfuehrungsfeldern — NICHT aus der
        # Kaeufer-NUTS abgeleitet, also ein unabhaengiger Zeuge) kann die Region
        # stuetzen, der die Anschrift widerspricht. Dann ist sie keine Falschangabe,
        # sondern eine Aussage ueber den Auftrag: die AOK PLUS sitzt in Erfurt und
        # schreibt fuer Sachsen aus. Genau die Klasse, um die es bei „Anschrift in
        # einem anderen Land als der Standort" geht.
        # ⚠ Nur als VETO, nie als Beweis: der Leistungsort ist bei DE 33 %, AT 10 %
        # der Faelle ueberhaupt gefuellt (gemessen 2026-09-02). Wer ihn zum Kronzeugen
        # macht, hat fuer neun von zehn oesterreichischen Faellen keinen.
        if markt and markt[:stellen] == nuts1:
            leistungsort_stuetzt += 1
            continue
        # ── Veto des Titels ───────────────────────────────────────────────────────
        # Dasselbe Argument, nur mit dem Zeugen, den es fast immer gibt: nennt der
        # AUFTRAGSTITEL einen Ort, der in der angegebenen Region liegt, dann steht dort
        # der Leistungsort und keine Falschangabe.
        #     „E90094/29/2-Dion7/2025 6020 Innsbruck …"          → Tirol, wie angegeben
        #     „Projektsteuerung, KZ-Gedenkstaette Gusen, 4222 …" → Oberoesterreich
        #     „Programm Knoten Bern, AS25 Wendegleis Muensingen" → Bern
        # In Oesterreich ist das die HAUPTKLASSE: von 85 Funden waren nach Durchsicht
        # 59 keine Fehler, sondern Leistungsorte (gemessen 2026-09-02). In Deutschland
        # greift dieses Veto bei 0 von 80 — es schwaecht die deutschen Funde also nicht.
        # ⚠ Es darf nur SCHWEIGEN lassen, nie etwas behaupten: ein Ortsname im Titel ist
        # ein Hinweis, kein Beleg. Als Widerspruchsgrund taugt er nicht.
        if titel and ort_im_namen(titel, orte, []) == nuts1:
            titel_stuetzt += 1
            continue
        if reg != nuts1:
            widersprueche.append({"lead_id": lead_id, "buyer_nuts1_abgeleitet": None,
                                  # `widerspruch_ort_nuts1` heisst weiter so (das
                                  # Frontend und `export_web_leads` lesen den Namen),
                                  # traegt jetzt aber die Region der ANSCHRIFT.
                                  "quelle": "widerspruch_anschrift", "widerspruch": True,
                                  "widerspruch_ort_nuts1": reg})

    for zeile in aus:
        zeile["widerspruch"] = False
        zeile["widerspruch_ort_nuts1"] = None
    df = pd.DataFrame(aus + korrigiert + widersprueche)
    gesamt = len(zeilen)
    if not gesamt:
        print(f"  {land}: kein Lead ohne Region.")
        return 0
    # ⚠ `len(aus)`, NICHT `len(df)`: seit der Gegenprobe stehen in `df` auch die
    # Widerspruchs-Zeilen, und die leiten nichts ab — sie nehmen etwas zurueck.
    print(f"  {land}: {gesamt:,} Leads ohne Region · {len(aus):,} abgeleitet "
          f"({len(aus)/gesamt:.0%})")
    if aus:
        herkunft = pd.Series([z["quelle"] for z in aus]).value_counts()
        print("  " + " · ".join(f"{k}: {v:,}" for k, v in herkunft.items()))
    pruefbar = einig + uneinig
    if pruefbar:
        print(f"  Selbsttest: wo beide Wege greifen ({pruefbar:,}), widersprechen sie sich "
              f"{uneinig:,}-mal ({uneinig/pruefbar:.1%}) — diese Leads bleiben leer.")
    if pruefbar_v:
        print(f"  Gegenprobe: von {pruefbar_v:,} Leads MIT Region widersprechen "
              f"{len(widersprueche):,} ({len(widersprueche)/pruefbar_v:.2%}) der Kaeufer-PLZ "
              f"— sie heissen im Export nicht mehr `amtlich`, sondern `widerspruechlich`.")
    if mehrere_standorte or leistungsort_stuetzt or titel_stuetzt:
        print(f"  uebergangen: {mehrere_standorte:,} Leads, deren Kaeufer mehrere Anschriften "
              f"fuehrt (Niederlassungen) · {leistungsort_stuetzt:,} mit stuetzendem "
              f"Leistungsort · {titel_stuetzt:,} mit stuetzendem Ortsnamen im Titel — "
              f"nichts davon ist ein Fehler.")
    if kuratiert:
        tot = sorted(set(kuratiert) - genutzt)
        print(f"  Kuratiert: {len(korrigiert):,} Leads korrigiert · {bestaetigt:,} geprueft "
              f"und bestaetigt · {len(kuratiert)-len(tot):,} von {len(kuratiert):,} Zeilen "
              f"greifen" + (f" · ⚠ {len(tot)} tote Zeile(n): "
                            + "; ".join(f"{n} ({z}, {a})" for n, z, a in tot[:3]) if tot else ""))
    if fremdformat:
        print(f"  ⚠ {fremdformat:,} Leads tragen im Regionsfeld KEINE gueltige "
              f"{land}-Regionskennung (Kantonskuerzel, Extra-Regio) — nicht pruefbar, "
              f"offener Punkt.")
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
