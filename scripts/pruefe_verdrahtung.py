#!/usr/bin/env python3
"""**Verdrahtungspruefung** — findet Bausteine, die es gibt, die aber niemand aufruft.

Der Anlass ist eine Fehlerklasse, die uns wiederholt erwischt hat und die von KEINEM
Unit-Test erfasst wird, weil jedes Stueck fuer sich korrekt ist:

    build_lead_text     im DACH-Gold nie aufgerufen — Datei stand 12 Tage still
    build_lead_lot      dasselbe, 10 Tage
    dedupe/locales      `country` wurde durchgereicht, aber nie aktiviert
    simap `_pick`       Sprachfassungen lagen vor und wurden verworfen
    build_at_gold       Fix landete in einem abgeloesten Modul

Alle 608 Tests waren jedes Mal gruen. Ein Unit-Test prueft, ob ein Baustein das
Richtige tut — nicht, ob ihn jemand benutzt. Genau diese Luecke schliessen die
Sonden hier.

    Sonde 1 (Frische)     Welche Gold-Datei ist gegenueber dem Landeslauf zurueck?
                          Wer nicht mitgebaut wird, faellt zurueck — messbar, ohne
                          dass man wissen muss, WARUM.
    Sonde 2 (Paritaet)    Welche Tabelle gibt es nur in DE? Jede ist entweder eine
                          bewusste Luecke oder ein Verdrahtungsfehler. Das ist der
                          EU-weit-Grundsatz, zum ersten Mal pruefbar statt vereinbart.

⚠ **WAS DIE SONDEN NICHT SEHEN: eine Tabelle, die es noch NIE gab.** Sonde 1 misst das
ALTER vorhandener Dateien, Sonde 2 vergleicht vorhandene Dateien zwischen Laendern. Eine
Datei, die nie geschrieben wurde, hat kein Alter und steht in keinem Land — sie ist fuer
beide unsichtbar. Genau so ist `govisor/retender_link.py` durchgerutscht: vollstaendig
gebaut am 2026-08-16, von niemandem gerufen, `lead_retender.parquet` in KEINEM Land, und
alle Sonden gruen. Gefunden wurde es am 2026-08-25 nur, weil jemand nach oeffentlichen
Funktionen ohne Aufrufer gesucht hat:

    # Namen, die govisor/ als Parquet nennt, aber in data/ nirgends liegen
    grep -oE '"[a-z_]+[.]parquet"' govisor/*.py | sort -u

Ein Gegenmittel als Sonde 5 waere moeglich (Erzeuger-Name gegen data/gold + data/reference
+ data/cache), ist aber bewusst NICHT gebaut: der erste Entwurf meldete vier Fehlalarme
(Cache- und Referenztabellen liegen ausserhalb von gold/) und ein legitimes offenes Stueck
(`document_master_items` — der Vorlauf kostet Geld und laeuft von Hand). Wer sie baut,
faengt bei diesen fuenf an.

AUSNAHMEN sind hier Code, nicht Textdatei, und `tests/test_verdrahtung.py` haelt sie
ehrlich: jede Ausnahme braucht eine Begruendung, und eine Ausnahme, die nicht mehr
zutrifft, laesst die Suite rot werden. Sonst waechst so eine Liste stillschweigend,
bis sie alles enthaelt — dieselbe Krankheit in neuer Form.

    python3 scripts/pruefe_verdrahtung.py            # beide Sonden
    python3 scripts/pruefe_verdrahtung.py --sonde frische
    python3 scripts/pruefe_verdrahtung.py --offen    # auch die bekannten Luecken zeigen

Rueckgabewert 1, sobald etwas UNERKLAERTES auftaucht. Bekannte Luecken (`OFFEN`)
zaehlen nicht als Fehlschlag, werden aber gezaehlt — sie sind eine Arbeitsliste,
kein Friedhof.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
GOLD = ROOT / "data" / "gold"

# ── Sonde 1: Frische ────────────────────────────────────────────────────────
# SCHWELLE, gemessen statt geraten (2026-08-23 an 142 Gold-Dateien): 134 lagen
# innerhalb von 2 Tagen zum jeweils neuesten Stand des Landes, danach klaffte eine
# Luecke bis 4,5 Tage. Der taegliche Lauf braucht mehrere Stunden ueber drei Laender,
# 2 Tage sind also grosszuegig und trennen trotzdem sauber.
SCHWELLE_TAGE = 2.0

# Wer NICHT taeglich gebaut wird. Jede Zeile braucht einen Grund, sonst ist es keine
# Ausnahme, sondern ein vergessener Schritt mit Persilschein.
AUSNAHMEN_FRISCHE: dict[str, str] = {
    "succession_llm_edges":
        "LLM-Adjudikation, kostet Geld — laeuft von Hand ueber scripts/succession_llm.py",
    "entity_merge_map":
        "Entity-Zusammenfuehrung, laeuft nach Pruefung von Hand (scripts/entity_merge_anwenden.py)",
    "entity_merge_urteil":
        "Urteilsstand der Entity-Zusammenfuehrung, gehoert zu entity_merge_map",
    "entity_impressum_beleg":
        "Impressum-Abgleich, eigener Lauf mit Netzzugriff — nicht im Nachtlauf",
    "lead_export.vor-vollpipeline":
        "Sicherungskopie vom Umstieg auf die Vollpipeline (13.08.), bewusst eingefroren",
}

# Dateien, die NIEMAND mehr baut und niemand mehr liest. Am 2026-08-23 waren das
# `ted_dedup` und `atverg_dedup` — die erzeugenden Skripte (`dedupe_at_sources.py`,
# `dedupe_ch_sources.py`) sind seit dem 13.08. geloescht, `govisor/dedupe.py` hat sie
# abgeloest. Beide liegen jetzt in `data/archiv_geloescht_20260823/`, deshalb ist die
# Liste leer. Sie bleibt stehen, weil der naechste Fund dieselbe Form haben wird.
#
# ACHTUNG, gefundene Falle: eine Suche nach dem Dateinamen im Quelltext meldet solche
# Leichen faelschlich als „wird noch verwendet" — der einzige Treffer war ein KOMMENTAR
# in build_marktpuls.py, der erklaert, dass sie abgeloest SIND. Wer Prosa mitzaehlt,
# haelt Leichen fuer lebendig.
LEICHEN: dict[str, str] = {}

# Frontend-Daten. Sonde 1 sah zuerst NUR `data/gold` — und uebersah damit genau die
# Schicht, die der Nutzer zu sehen bekommt: `web/data/firma-profiles.json` war 23 Tage alt
# (16,6 MB, speist /firma), weil `export_firma_profiles.py` in keinem Lauf steht. Dieselbe
# Fehlerklasse wie `lead_lot`, eine Schicht weiter aussen.
WEB = ROOT / "web" / "data"

AUSNAHMEN_WEB: dict[str, str] = {
    "doc-analysis.backup.json": "Sicherungskopie vor dem Zerlegen der Dokumentanalyse",
    "nachweis-median.json": "Kennzahl aus einer einmaligen Erhebung, kein Tageslauf",
    "outreach.json": "internes Vertriebswerkzeug, laeuft von Hand",
}

# ── Sonde 2: Laenderparitaet ────────────────────────────────────────────────
LAENDER = ("DE", "AT", "CH")

# BEWUSST: gibt es zu Recht nur in DE. Der Grund muss die QUELLE nennen, nicht den
# Aufwand — „lohnt sich nicht" ist keine Begruendung, sondern eine Vertagung.
BEWUSST_NUR_DE: dict[str, str] = {
    "doe_buyer_profile": "DOeE ist eine rein deutsche Unterschwellenquelle",
    "doe_demand": "DOeE ist eine rein deutsche Unterschwellenquelle",
    "buyer_profile": "wird vom DOeE-Builder miterzeugt, haengt an derselben Quelle",
    "entity_impressum_beleg": "deutsche Impressumspflicht (§5 DDG) — kein AT/CH-Gegenstueck",
    "entity_merge_map": "Entity-Aufloesung ist auf das deutsche Handelsregister getunt",
    "entity_merge_urteil": "gehoert zu entity_merge_map",
    "succession_llm_edges": "LLM-Lauf auf dem DE-Bestand, bewusst nicht auf AT/CH ausgeweitet",
    "lead_kategorie": "Kategorie-Wasserfall liest DE-Dubletten und DE-Vokabular",
    "bronze_inventory": "Inventar der DE-Bronze-Pakete (TED-Vollabzug)",
    "document_duplicates": "Dokument-Dublettenwall; AT/CH haben 0 % Dokumentabdeckung",
    "lead_region_fill": "Bundesland-Auffuellung, deutsche NUTS-Systematik",
}

# OFFEN: bekannte Luecke — eine Tabelle, die es nur in DE gibt, obwohl sie es nicht
# muesste. Sie steht hier statt in BEWUSST_NUR_DE, damit sie sichtbar bleibt; wer eine
# davon verdrahtet, streicht die Zeile, und `test_kein_offen_eintrag_ist_laengst_erledigt`
# verlangt das auch.
#
# Am 2026-08-23 standen hier 16 Eintraege. Alle sind erledigt: die Builder waren durchweg
# country-faehig und wurden im DACH-Lauf nur nicht aufgerufen. Verdrahtet, gemessen:
#     lead_criteria    AT 22.471 / CH 13.656      value_anchor  AT 228.920 / CH 51.919
#     lead_party       AT 38.681 / CH 16.462      buyer_stats   AT  4.341 / CH  5.656
#     lead_requirement AT  2.748 / CH    595      market_opp.   AT    317 / CH    125
# Die Liste ist leer und bleibt stehen, weil der naechste Fund dieselbe Form haben wird.
OFFEN_NUR_DE: dict[str, str] = {}


# Laender, die in Silber liegen duerfen, ohne in Gold zu erscheinen. Alles andere ist ein
# halb aufgenommenes Land — und das ist die Fehlerklasse dieses Skripts auf der obersten
# Ebene: Gemessen am 2026-08-23 lagen 326.485 polnische Bekanntmachungen in Silber, seit
# zwei Monaten ohne Gold, und KEINE Sonde meldete es. Sonde 1 und 2 sehen nur, was in
# `data/gold` steht; ein Land, das es nie dorthin geschafft hat, ist fuer sie unsichtbar.
SILBER = ROOT / "data" / "silver"

BEWUSST_OHNE_GOLD: dict[str, str] = {
    "EU": "Sammelablage fuer Bekanntmachungen ohne eindeutiges Land (282 Saetze, 15 Laender)",
    "PL": "angefangen und liegengeblieben: 326.485 Saetze, letzte Publikation 2026-06-29. "
          "KEINE Entscheidung, sondern eine Baustelle — s. docs/land-onboarding.md",
}


def sonde_laender(zeige_offen: bool = False) -> list[str]:
    """Welches Land liegt in Silber, ohne in Gold anzukommen?"""
    if not SILBER.is_dir():
        return []
    fehler, offen = [], []
    for d in sorted(x for x in SILBER.iterdir() if x.is_dir()):
        if not list((d / "notices").glob("*/*.parquet")):
            continue
        if (GOLD / d.name).is_dir():
            continue
        grund = BEWUSST_OHNE_GOLD.get(d.name)
        if grund:
            offen.append(f"    OFFEN   {d.name} liegt in Silber, nicht in Gold: {grund}")
        else:
            fehler.append(f"{d.name} liegt in Silber, aber nicht in Gold — halb aufgenommen "
                          f"oder vergessen? Es steht in keiner Liste.")
    if offen:
        if zeige_offen:
            print("\n".join(offen))
        else:
            print(f"    ({len(offen)} Laender ohne Gold — mit --offen anzeigen)")
    return fehler


# ── Sonde 3: DE-feste Pfade im Nachtlauf ────────────────────────────────────
# Sonde 1 und 2 sehen die GOLD-Ebene. Sie merken nicht, wenn eine Tabelle sauber je Land
# gebaut wird und der Verbraucher trotzdem nur `data/gold/DE` liest — und genau dort sass
# die Haelfte aller Funde: `buyer_stats`, `market_opportunity`, `lead_predecessor`, `ATTR`,
# `lead_region_fill` waren alle gebaut und wurden alle nur aus DE gelesen.
#
# Geprueft wird, was im NACHTLAUF steht. Ein Analyse-Skript, das niemand taeglich ruft,
# blockiert kein Land; ein Exporter schon.
NACHTLAUF = ROOT / "scripts" / "daily_leads.sh"

# Wer zu Recht nur DE liest. Der Grund muss sagen, WARUM das Land dort nichts zu suchen
# hat — „noch nicht umgestellt" ist kein Grund, sondern der Befund selbst.
BEWUSST_NUR_DE_SKRIPTE: dict[str, str] = {
    "export_landing.py":
        "Startseiten-Zahlen: fuer AT/CH ist die Entitaeten-Aufloesung schwaecher, und eine "
        "Zahl, die zwei Qualitaeten mischt, ist keine Zahl (Kommentar steht im Skript)",
    "export_supabase.py":
        "schiebt die gov_*-Tabellen hoch; der Push ist seit 16.08. hinter "
        "GOVISOR_SUPABASE_GOV_PUSH=1 und standardmaessig AUS",
    "qualitaet_bericht.py":
        "interner Bericht ueber den DE-Bestand, kein Produktweg",
    "gap_effects.py":
        "interne Wirkungsanalyse, kein Produktweg",
    "pruefe_verdrahtung.py":
        "dieses Skript selbst; die Treffer sind die Begruendungstexte oben",
}

# OFFEN: liest nur DE, muesste es aber nicht. Jede Zeile ist eine Baustelle mit
# gemessener Auswirkung — sichtbar, damit sie nicht als erledigt durchgeht.
#
# Am 2026-08-23 standen hier drei Eintraege; alle drei sind verdrahtet:
#   export_suppliers.py       31.459 → 37.896 Firmen, Schweizer Firmen jetzt auffindbar
#   export_web_awards.py      379 → 1.019 Zuschlaege (DE 379, AT 334, CH 306)
#   export_firma_profiles.py  AT 2.685 / CH 84 Profile mit echter Hauptregion
# Die Liste bleibt leer stehen, weil der naechste Fund dieselbe Form haben wird.
OFFEN_NUR_DE_SKRIPTE: dict[str, str] = {}


def _de_feste_pfade(skript: pathlib.Path) -> int:
    """Wie oft steht `data/{gold,silver}/DE` in einer Zeichenkette, die WIRKLICH LAEUFT?

    Ein Zeilenscanner reicht dafuer nicht. Der erste Versuch zaehlte drei Fehlalarme:
    einen Docstring in `build_marktpuls.py`, der erklaert, warum dort NICHT gelesen wird,
    und die Begruendungstexte dieses Skripts selbst. Wer Prosa mitzaehlt, zwingt dazu, die
    Begruendung zu loeschen — dieselbe Falle wie schon dreimal bei Tests.

    Deshalb ueber den Syntaxbaum: gezaehlt werden nur Zeichenketten-Knoten, die keine
    Docstrings sind. Kommentare tauchen im Baum gar nicht erst auf.
    """
    import ast
    if not skript.exists():
        return 0
    try:
        baum = ast.parse(skript.read_text(encoding="utf-8"))
    except SyntaxError:
        return 0
    # Docstrings einsammeln, damit sie ausgenommen werden koennen.
    docs = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            k = knoten.body[0] if knoten.body else None
            if isinstance(k, ast.Expr) and isinstance(k.value, ast.Constant) \
                    and isinstance(k.value.value, str):
                docs.add(id(k.value))
    n = 0
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str) \
                and id(knoten) not in docs \
                and any(m in knoten.value for m in _DE_MUSTER):
            n += 1
    # ⚠ EINE Nennung ist erlaubt, WENN das Skript `_union` definiert: `G = "data/gold/DE"`
    # ist dort die BASIS, der die uebrigen Laender angehaengt werden (DE zuerst, weil es
    # das vollstaendigste Schema hat). Das als Ausnahme je Skript zu fuehren waere eine
    # Liste, die mit jedem umgestellten Exporter waechst und nichts aussagt — die Regel
    # gehoert in die Pruefung, nicht in die Ausnahmen.
    if n == 1 and any(isinstance(k, ast.FunctionDef) and k.name == "_union"
                      for k in ast.walk(baum)):
        return 0
    return n


# ⚠ `data/docs/DE` KAM ERST AM 2026-08-24 DAZU. Die Sonde sah nur Gold und Silber und war
# damit blind fuer die Dokumentebene — also fuer die Schicht, in der Abruf, Index und
# Dokumentanalyse arbeiten. Aufgefallen ist es beim Gegenlesen der Laender-Bibel: der frisch
# gebaute Pruefstand las fest aus `data/docs/DE`, die Sonde meldete „0 unerklaerte
# DE-Bindungen". Eine Sonde, die eine Ebene nicht kennt, meldet dort Ruhe.
_DE_MUSTER = ("data/gold/DE", "data/silver/DE", "data/docs/DE")


def sonde_pfade(zeige_offen: bool = False) -> list[str]:
    """Welches Skript des Nachtlaufs liest fest aus Deutschland?"""
    if not NACHTLAUF.exists():
        print("  daily_leads.sh nicht gefunden — Sonde uebersprungen")
        return []
    import re
    genannt = sorted(set(re.findall(r"scripts/([a-z_0-9]+\.py)", NACHTLAUF.read_text(encoding="utf-8"))))
    fehler: list[str] = []
    offen: list[str] = []
    for name in genannt:
        n = _de_feste_pfade(ROOT / "scripts" / name)
        if not n or name in BEWUSST_NUR_DE_SKRIPTE:
            continue
        if name in OFFEN_NUR_DE_SKRIPTE:
            offen.append(f"    OFFEN   {name} ({n} feste DE-Pfade): {OFFEN_NUR_DE_SKRIPTE[name]}")
            continue
        fehler.append(f"{name} liest an {n} Stellen fest aus data/gold/DE, data/silver/DE "
                      f"oder data/docs/DE "
                      f"und steht in keiner Liste — Absicht oder vergessen?")
    if offen:
        if zeige_offen:
            print("\n".join(offen))
        else:
            print(f"    ({len(offen)} bekannte Baustellen — mit --offen anzeigen)")
    return fehler


def _dateien(wurzel: pathlib.Path) -> dict[str, list[pathlib.Path]]:
    """Gold-Parquets je Land. Leere Laender fallen raus, nicht durch."""
    aus: dict[str, list[pathlib.Path]] = {}
    if not wurzel.is_dir():
        return aus
    for d in sorted(p for p in wurzel.iterdir() if p.is_dir()):
        fs = list(d.glob("*.parquet"))
        if fs:
            aus[d.name] = fs
    return aus


def sonde_frische(zeige_offen: bool = False,
                  wurzel: pathlib.Path = GOLD) -> list[str]:
    """Welche Gold-Datei haengt gegenueber dem Lauf ihres Landes zurueck?

    Bezug ist die NEUESTE Datei DESSELBEN Landes, nicht die Uhr: der Lauf kann
    ausfallen, ohne dass gleich alles Alarm schlaegt. Damit ein komplett stehen
    `wurzel` ist ausschliesslich fuer den Test da: eine Sonde, die man nur gegen die
    echte Datenlage laufen lassen kann, kann man nicht beweisen — und eine unbewiesene
    Pruefung ist genau das Problem, das sie loesen soll.

    Bezug ist die NEUESTE Datei DESSELBEN Landes, nicht die Uhr: der Lauf kann
    ausfallen, ohne dass gleich alles Alarm schlaegt. Damit ein komplett stehen
    gebliebenes Land trotzdem auffaellt, wird zusaetzlich Land gegen Land geprueft —
    sonst wandert der Bezugspunkt lautlos mit.
    """
    dateien = _dateien(wurzel)
    if not dateien:
        print("  keine Gold-Ebene gefunden — Sonde uebersprungen")
        return []

    neuestes = {land: max(f.stat().st_mtime for f in fs) for land, fs in dateien.items()}
    global_neu = max(neuestes.values())
    fehler: list[str] = []

    # (a) Ganzes Land zurueck?
    for land, t in sorted(neuestes.items()):
        rueck = (global_neu - t) / 86400
        if rueck > SCHWELLE_TAGE:
            fehler.append(f"Land {land} baut seit {rueck:.1f} Tagen nichts mehr "
                          f"(neueste Datei {dt.datetime.fromtimestamp(t):%d.%m. %H:%M})")

    # (b) Einzelne Datei zurueck?
    offen = 0
    for land, fs in sorted(dateien.items()):
        for f in sorted(fs):
            rueck = (neuestes[land] - f.stat().st_mtime) / 86400
            if rueck <= SCHWELLE_TAGE:
                continue
            if f.stem in LEICHEN:
                offen += 1
                if zeige_offen:
                    print(f"    LEICHE  {land}/{f.stem}: {LEICHEN[f.stem]}")
                continue
            if f.stem in AUSNAHMEN_FRISCHE:
                continue
            fehler.append(f"{land}/{f.name} haengt {rueck:.1f} Tage zurueck — "
                          f"wird der Schritt im Lauf des Landes ueberhaupt aufgerufen?")
    if offen and not zeige_offen:
        print(f"    ({offen} Leichen — mit --offen anzeigen)")

    # (c) Frontend-Daten. Bezug ist hier die NEUESTE Datei in `web/data` — derselbe
    # Gedanke wie oben, nur eine Schicht weiter aussen.
    #
    # ⚠ NICHT NUR `*.json` DIREKT IN `web/data`. Genau das stand hier bis zum 2026-08-25,
    # und damit war ein wachsender Teil der Frontend-Daten unbeobachtet:
    #
    #   · die SPLITTERVERZEICHNISSE `doc-analysis/`, `doc-text/`, `doc-listing/` — je rund
    #     8.000 Einzeldateien, aus denen das Lead-Detail seine Texte und Auswertungen holt.
    #     Der Sammelblock daneben blieb frisch, waehrend die Splitter haetten verrotten
    #     koennen; die Sonde haette geschwiegen.
    #   · die CSV-Ausgaben `kriterien/` und `lv/` (3.281 Dateien), die `/api/lead-export`
    #     ausliefert. `*.json` trifft sie per Bauart nie.
    #
    # Ein Verzeichnis zaehlt mit dem Alter seiner JUENGSTEN Datei: es ist frisch, sobald
    # sein Erzeuger ueberhaupt noch laeuft. Wer einzelne verwaiste Splitter finden will,
    # braucht einen Abgleich gegen die Leadliste — das ist eine andere Frage als diese.
    def _stand(pfad: pathlib.Path) -> float | None:
        if pfad.is_file():
            return pfad.stat().st_mtime
        kinder = [f for f in pfad.rglob("*") if f.is_file()]
        return max((f.stat().st_mtime for f in kinder), default=None)

    web = {p.name: t for p in sorted(WEB.iterdir())
           if (t := _stand(p)) is not None} if WEB.is_dir() else {}
    if web:
        neuestes_web = max(web.values())
        for name, t in sorted(web.items()):
            rueck = (neuestes_web - t) / 86400
            if rueck <= SCHWELLE_TAGE or name in AUSNAHMEN_WEB:
                continue
            fehler.append(f"web/data/{name} haengt {rueck:.1f} Tage zurueck — "
                          f"wer baut das, und laeuft er noch?")
    return fehler


def sonde_paritaet(zeige_offen: bool = False,
                   wurzel: pathlib.Path = GOLD) -> list[str]:
    """Welche Gold-Tabelle gibt es nur in DE?

    Jede ist entweder eine bewusste Luecke (dann steht sie in BEWUSST_NUR_DE mit
    Quellen-Begruendung) oder eine bekannte Baustelle (OFFEN_NUR_DE) — oder ein
    Fehler, den niemand bemerkt hat. Nur der dritte Fall laesst die Sonde fallen.
    """
    da: dict[str, set[str]] = collections.defaultdict(set)
    for p in wurzel.glob("*/*.parquet"):
        da[p.stem].add(p.parent.name)
    if not da:
        print("  keine Gold-Ebene gefunden — Sonde uebersprungen")
        return []

    fehler: list[str] = []
    offen: list[str] = []
    for tabelle, laender in sorted(da.items()):
        fehlend = [l for l in LAENDER if l not in laender]
        if not fehlend or "DE" not in laender:
            continue          # in allen Laendern da, oder gar nicht in DE (kein Paritaets-Fall)
        if tabelle in BEWUSST_NUR_DE or tabelle in AUSNAHMEN_FRISCHE or tabelle in LEICHEN:
            continue
        if tabelle in OFFEN_NUR_DE:
            offen.append(f"    OFFEN   {tabelle} fehlt in {','.join(fehlend)}: "
                         f"{OFFEN_NUR_DE[tabelle]}")
            continue
        fehler.append(f"{tabelle} gibt es nur in DE (fehlt in {','.join(fehlend)}) und "
                      f"steht in keiner Liste — bewusste Luecke oder Verdrahtungsfehler?")
    if offen:
        if zeige_offen:
            print("\n".join(offen))
        else:
            print(f"    ({len(offen)} bekannte Luecken — mit --offen anzeigen)")
    return fehler


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sonde", choices=("frische", "paritaet", "pfade", "laender", "alle"), default="alle")
    ap.add_argument("--offen", action="store_true",
                    help="bekannte Luecken und Leichen mit auflisten")
    a = ap.parse_args()

    alles: list[str] = []
    if a.sonde in ("frische", "alle"):
        print("── Sonde 1: Frische (wer wird nicht mitgebaut?) ──")
        f = sonde_frische(a.offen)
        alles += f
        print(f"    {len(f)} unerklaerte Rueckstaende")
    if a.sonde in ("paritaet", "alle"):
        print("── Sonde 2: Laenderparitaet (was gibt es nur in DE?) ──")
        f = sonde_paritaet(a.offen)
        alles += f
        print(f"    {len(f)} unerklaerte Alleingaenge")
    if a.sonde in ("laender", "alle"):
        print("── Sonde 4: Laender (wer liegt in Silber, ohne in Gold anzukommen?) ──")
        f = sonde_laender(a.offen)
        alles += f
        print(f"    {len(f)} unerklaerte Laender")
    if a.sonde in ("pfade", "alle"):
        print("── Sonde 3: DE-feste Pfade im Nachtlauf (wer liest nur DE?) ──")
        f = sonde_pfade(a.offen)
        alles += f
        print(f"    {len(f)} unerklaerte DE-Bindungen")

    if alles:
        print("\n⚠ Verdrahtungspruefung: " + str(len(alles)) + " Befund(e)")
        for z in alles:
            print(f"  · {z}")
        return 1
    print("\n✓ Verdrahtungspruefung sauber")
    return 0


if __name__ == "__main__":
    sys.exit(main())
