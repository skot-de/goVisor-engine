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
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
# ⚠ ERST den Projektpfad, DANN `govisor` importieren. Unter launchd gibt es kein
# PYTHONPATH; ein Import davor bricht stumm ab (s. test_skripte_finden_govisor_ohne_pythonpath).
sys.path.insert(0, str(ROOT))
from govisor.laender import AKTIV as _AKTIV  # noqa: E402
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

# ⚠ ZWEI TABELLEN, DIE ES NUR MIT FUND GIBT. `govisor.dedupe` schreibt `notice_duplicates`
# und `notice_enrichment` erst, wenn es etwas zu schreiben gibt. Fuer LU lief der Wall am
# 2026-09-03 ueber 6.115 Bekanntmachungen und meldete „Keine Dubletten gefunden" — die
# Dateien fehlen also aus dem richtigen Grund.
# ⚠ Das widerspricht dem Grundsatz, den die DACH-KETTE selbst notiert („leere Tabelle, wenn
# keine kuratierte CSV — Nachfolger brauchen die DATEI"). Bewusst NICHT hier geradegezogen:
# das Schreibverhalten von dedupe zu aendern trifft DE, AT und CH mit, und dafuer ist heute
# Abend der falsche Zeitpunkt. Steht als offener Punkt.
OHNE_FUND_KEINE_DATEI: dict[str, set[str]] = {
    "LU": {"notice_duplicates", "notice_enrichment"},
}

BEWUSST_OHNE_GOLD: dict[str, str] = {
    "EU": "Sammelablage fuer Bekanntmachungen ohne eindeutiges Land (282 Saetze, 15 Laender)",
    "PL": "angefangen und liegengeblieben: 326.485 Saetze, letzte Publikation 2026-06-29. "
          "KEINE Entscheidung, sondern eine Baustelle — s. docs/land-onboarding.md",
    # ⚠ LU STAND HIER BIS ZUM 2026-09-03 ABEND und ist bewusst raus: Gold ist gebaut
    # (42 Schritte ueber build_dach_gold, 279 Leads) und das Locale-Profil existiert. Der
    # Eintrag behauptete beides als fehlend — eine Ausnahme, die laenger lebt als ihr Grund,
    # ist schlimmer als keine: sie entschuldigt eine Luecke, die es nicht mehr gibt, und
    # deckt kuenftige zu. ⚠ Die Suite hat das NICHT gemeldet; sie prueft, ob eine Ausnahme
    # begruendet ist, nicht ob die Begruendung noch stimmt.
}


# ── Sonde 2: Laenderparitaet ────────────────────────────────────────────────
# ⚠ DIE LAENDER STEHEN NICHT MEHR HIER. Bis zum 2026-09-02 war die Liste fest
# (`("DE","AT","CH")`), und damit haette ein viertes Land die Sonde stillschweigend
# ausgehebelt: seine Tabellen waeren in keiner Pruefung vorgekommen, weil das Land nicht in
# der Liste stand. Genau die Fehlerklasse, die diese Datei sonst jagt — nur eine Ebene
# hoeher, im Pruefwerkzeug selbst.
#
# Die Laender kommen jetzt aus dem, was auf der Platte liegt. Wer Polen aufnimmt, muss hier
# nichts eintragen; die Sonde bemerkt es beim naechsten Lauf von allein.
def _laender(wurzel: pathlib.Path) -> tuple[str, ...]:
    """Welche Laender sind AUFGENOMMEN? Aus dem Verzeichnis, nicht aus einer Liste.

    ⚠ EINE ANGEFANGENE BAUSTELLE IST KEIN AUFGENOMMENES LAND. Am 2026-09-02 hat
    `build_vorgaenge.py` als erster laenderagnostischer Schritt auch fuer EU und PL
    geschrieben — beide stehen in `BEWUSST_OHNE_GOLD`. Damit galten sie ploetzlich als
    Gold-Laender, und die Paritaetspruefung meldete 40 bestehende Tabellen als Luecke. Die
    Sonde ertrank in Befunden, die alle schon dokumentiert waren.

    Wer hier ausgenommen wird, verschwindet NICHT: Sonde 4 meldet ihn weiter als offene
    Baustelle, mit Grund. Faellt der Eintrag aus `BEWUSST_OHNE_GOLD` (weil das Land fertig
    aufgenommen wurde), zaehlt es ab dem naechsten Lauf wieder voll mit."""
    return tuple(sorted(p.name for p in wurzel.iterdir()
                        if p.is_dir() and any(p.glob("*.parquet"))
                        and p.name not in BEWUSST_OHNE_GOLD))


# Rueckfall fuer Aufrufer, die ohne Wurzel arbeiten (und fuer die Tests). Kein Ersatz fuer
# die Messung oben, nur eine Notleine, wenn es gar keine Gold-Ebene gibt.
# ⚠ Eine Stelle: `govisor/laender.py`. Hier stand eine eigene Liste — bis zum
# 2026-09-04 gab es ein Dutzend davon, und Luxemburg fehlte in der Haelfte.
LAENDER = _AKTIV

# BEWUSST: gibt es zu Recht nur in DE. Der Grund muss die QUELLE nennen, nicht den
# Aufwand — „lohnt sich nicht" ist keine Begruendung, sondern eine Vertagung.
BEWUSST_NUR_DE: dict[str, str] = {
    "doe_buyer_profile": "DOeE ist eine rein deutsche Unterschwellenquelle",
    "doe_demand": "DOeE ist eine rein deutsche Unterschwellenquelle",
    "buyer_profile": "wird vom DOeE-Builder miterzeugt, haengt an derselben Quelle",
    "entity_impressum_beleg": "deutsche Impressumspflicht (§5 DDG) — kein AT/CH-Gegenstueck",
    # ⚠ NICHT „lohnt sich nicht", sondern gemessen: am 2026-09-01 lagen in AT und CH NULL
    # Vergabeunterlagen im Volltext (DE: 9.788 Vorgaenge) bei zusammen 2.783 offenen
    # Vergaben. Eine Dokumentanalyse ohne Dokumente ergibt keine Tabelle, nicht einmal eine
    # leere. Kommt die erste Unterlage herein (die Bitte dafuer steht seit dem 01.09. in der
    # Vergabe-Analyse), gehoert dieser Eintrag geprueft.
    "doc_analysis": "keine Vergabeunterlagen in AT/CH (0 gegen 9.788 Vorgaenge, 2026-09-01)",
    "doc_checklist": "gehoert zu doc_analysis, dieselbe Quelle",
    "doc_verworfen": "gehoert zu doc_analysis, dieselbe Quelle",
    "doc_qa_stand": "gehoert zu doc_analysis, dieselbe Quelle",
    "entity_merge_map": "Entity-Aufloesung ist auf das deutsche Handelsregister getunt",
    "entity_merge_urteil": "gehoert zu entity_merge_map",
    "succession_llm_edges": "LLM-Lauf auf dem DE-Bestand, bewusst nicht auf AT/CH ausgeweitet",
    "lead_kategorie": "Kategorie-Wasserfall liest DE-Dubletten und DE-Vokabular",
    "bronze_inventory": "Inventar der DE-Bronze-Pakete (TED-Vollabzug)",
    "document_duplicates": "Dokument-Dublettenwall; AT/CH haben 0 % Dokumentabdeckung",
    # Dieselbe Ursache wie eine Zeile darueber: AT und CH haben kein `doc_text`.
    #
    # ⚠ ABER NICHT DERSELBE WEG HINAUS — hier stand bis zum 2026-09-03, die Erzeuger seien
    # „laenderfaehig (`--land`)" und die Tabellen entstuenden „von selbst", sobald Dokumente
    # ankommen. Das gilt fuer den Dublettenwall eine Zeile darueber, NICHT fuer die
    # LLM-Auswertung: `scripts/analyze_docs.py:45` haelt `SRC` fest auf
    # data/docs/DE/doc_text.parquet — eine Modulkonstante, kein Parameter — und liest
    # dreimal `gold/DE/lead_export.parquet`. Sein eigener Docstring verspricht in Zeile 4
    # „data/docs/<country>/doc_text.parquet"; der Code loest das nicht ein.
    # ✅ AM 2026-09-03 ABEND BEHOBEN. Die Kette liest jetzt ALLE Laender, die Text haben —
    # analyze_docs, export_doc_text und export_doc_signals vereinigen `data/docs/*/`, statt
    # DE fest zu verdrahten; `signals-docs` und `index-docs` laufen im Tageslauf je Land.
    # ⚠ BEWUSST KEIN LAENDERPARAMETER MIT VORGABE DE: den muss jemand SETZEN, und genau das
    # wird vergessen — am selben Tag lief der LU-Abrufer, waehrend der LU-Indexer fehlte.
    # `LAND=LU` bleibt als FILTER fuer gezielte Messungen, nicht als Voraussetzung.
    # Diese vier Zeilen bleiben trotzdem stehen, solange AT/CH/LU keine Dokumente HABEN —
    # jetzt aber aus dem richtigen Grund: keine Daten, nicht kein Code.
    "doc_analysis": "Auswertung der Vergabeunterlagen; AT/CH haben 0 % Dokumentabdeckung",
    "doc_checklist": "gehoert zu doc_analysis, dieselbe Quelle",
    "doc_verworfen": "gehoert zu doc_analysis, dieselbe Quelle",
    "doc_qa_stand": "zaehlt Fragenkataloge aus doc_text; AT/CH haben 0 % Dokumentabdeckung",
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
                  wurzel: pathlib.Path = GOLD,
                  web_wurzel: pathlib.Path | None = None) -> list[str]:
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

    # ⚠ NICHT ALLES IN `web/data` IST UNSER. macOS legt dort `.DS_Store` ab, sobald jemand
    # den Ordner im Finder oeffnet — die Datei altert dann vor sich hin und meldete sich am
    # 2026-08-29 als „haengt 3.8 Tage zurueck, wer baut das?". Niemand baut das, und die
    # Frage hat keine Antwort. Ein Fehlalarm in einer Sonde ist teurer als anderswo: er
    # gewoehnt einen daran, ihre Meldungen zu ueberfliegen.
    # ⚠ AUCH DIE WEB-HAELFTE MUSS PRUEFBAR SEIN. `wurzel` war fuer das Gold da, mit der
    # Begruendung oben im Docstring — die Web-Haelfte las trotzdem fest `WEB`. Damit hing
    # jeder synthetische Sonde-1-Test zusaetzlich an der ECHTEN Datenlage: am 2026-08-29
    # wurden drei davon rot, weil die Dokumentanalyse seit vier Tagen stillstand. Der
    # Befund war richtig, die Tests hatten damit nur nichts zu tun.
    ziel_web = web_wurzel if web_wurzel is not None else WEB
    web = {p.name: t for p in sorted(ziel_web.iterdir())
           if not p.name.startswith(".") and (t := _stand(p)) is not None} if ziel_web.is_dir() else {}
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
    # Gemessen statt gelistet, s. `_laender`.
    laender_da = _laender(wurzel) or LAENDER

    fehler: list[str] = []
    offen: list[str] = []
    for tabelle, laender in sorted(da.items()):
        fehlend = [l for l in laender_da if l not in laender]
        # ⚠ FRUEHER STAND HIER `"DE" not in laender`. Eine Tabelle, die es in AT und CH gibt
        # und in DE nicht, galt damit als „kein Paritaetsfall" und fiel durch — obwohl das
        # genauso eine Luecke ist. Die Sonde fragt jetzt nur noch, ob eine Tabelle in ALLEN
        # Laendern liegt, die eine Gold-Ebene haben, und nicht mehr, welches Land das erste ist.
        if not fehlend:
            continue
        if tabelle in BEWUSST_NUR_DE or tabelle in AUSNAHMEN_FRISCHE or tabelle in LEICHEN:
            continue
        # Tabellen, die es nur mit Fund gibt (s. OHNE_FUND_KEINE_DATEI): fehlen sie GENAU
        # in den dort genannten Laendern, ist das kein Befund.
        erwartet_leer = {l for l, tn in OHNE_FUND_KEINE_DATEI.items() if tabelle in tn}
        if fehlend and set(fehlend) <= erwartet_leer:
            continue
        if tabelle in OFFEN_NUR_DE:
            offen.append(f"    OFFEN   {tabelle} fehlt in {','.join(fehlend)}: "
                         f"{OFFEN_NUR_DE[tabelle]}")
            continue
        # ⚠ Sagen, WO sie liegt, nicht „nur in DE". Der alte Satz war eine Annahme ueber das
        # Ergebnis: bei einer Tabelle, die es in AT und CH gibt und in DE nicht, stand dort
        # „gibt es nur in DE" — und wer das las, suchte am falschen Ort.
        fehler.append(f"{tabelle} gibt es in {','.join(sorted(laender))}, fehlt in "
                      f"{','.join(fehlend)} und steht in keiner Liste — bewusste Luecke "
                      f"oder Verdrahtungsfehler?")
    if offen:
        if zeige_offen:
            print("\n".join(offen))
        else:
            print(f"    ({len(offen)} bekannte Luecken — mit --offen anzeigen)")
    return fehler


# ── Sonde 5: Nutzlast (wer liest, was wir ausliefern?) ──────────────────────
#
# Sonde 1 fragt, ob eine Datei in `web/data` FRISCH ist. Sie fragt nicht, ob sie ueberhaupt
# jemand holt — und das ist eine eigene Fehlerklasse, mit eigenem Preis: `web/data` geht
# als Ganzes in den Objektspeicher, taeglich, rund 1,4 GB (gemessen 2026-08-25).
#
# Der Anlass: an einem einzigen Tag entstanden `kalender-index.json` (45 kB, von mir, keine
# vier Stunden alt) und daneben lagen `firma-index.json`, `doc-analysis-index.json` und
# `doc-listing-index.json` — alle vier geschrieben, keine einzige gelesen. Das faellt nicht
# auf, weil eine ungelesene Datei nichts kaputt macht. Sie wird nur bezahlt, und irgendwann
# baut jemand auf ihr auf, weil sie aussieht wie eine Schnittstelle.
#
# ⚠ WIE GEMESSEN WIRD, und wo die Grenze liegt. Aus dem Web-Code werden die Muster der
# `loadDataFile(...)`-Aufrufe gezogen (`leads-${b}.json` → `leads-[^/]+\.json`), dazu jeder
# blanke String, der auf `.json`/`.csv` endet — den braucht es fuer Leser, die nicht ueber
# `loadDataFile` gehen. Das ist absichtlich GROSSZUEGIG: ein falscher Alarm kostet Zeit und
# Vertrauen, ein uebersehener Eintrag nur Speicher. Der Aufruf `${art.dir}/${id}.csv` deckt
# deshalb jedes CSV-Verzeichnis ab; wer dort etwas Totes vermutet, muss von Hand nachsehen.
AUSNAHMEN_NUTZLAST: dict[str, str] = {
    "doc-analysis.json": "Arbeitsstand des Analyse-Laufs, per NICHT_HOCH vom Upload ausgenommen",
    "doc-analysis.backup.json": "Sicherungskopie vor dem Zerlegen der Dokumentanalyse",
    # ⚠ DIE DREI SIND EIN OFFENER PUNKT, KEIN ERLEDIGTER. Sie stehen hier, damit die Sonde
    # gruen ist und ein NEUER toter Posten auffaellt — nicht, weil die Sache geklaert waere.
    # Alle drei sind Verzeichnisse ihrer Scherben und waeren plausibel nuetzlich (Suche,
    # Ampel-Abzeichen in der Liste); gebaut wurde nur die Datei, nie der Leser. Zusammen
    # 3,1 MB von 1,4 GB — der Preis ist nicht das Problem, der Anschein ist es: was wie eine
    # Schnittstelle aussieht, wird irgendwann als eine benutzt. Entscheidung (2026-08-25):
    # verdrahten oder streichen.
    "firma-index.json": "2,6 MB Verzeichnis der Firmenprofile — geschrieben, nie gelesen (offen seit 2026-08-25)",
    "doc-analysis-index.json": "Ampel je Vorgang — geschrieben, nie gelesen (offen seit 2026-08-25)",
    "doc-listing-index.json": "Dateizahl je Vorgang — geschrieben, nie gelesen (offen seit 2026-08-25)",
}


def _leser_muster() -> list[re.Pattern]:
    """Woran der Web-Code Datendateien erkennt — als Regex, aus dem Quelltext gezogen."""
    muster: list[re.Pattern] = []
    for datei in (ROOT / "web").rglob("*"):
        if (not datei.is_file() or datei.suffix not in {".ts", ".tsx", ".js", ".mjs"}
                or "node_modules" in datei.parts):
            continue
        text = datei.read_text(encoding="utf-8", errors="replace")
        for roh in re.findall(r'loadDataFile\(\s*[`"\']([^`"\']+)[`"\']', text):
            muster.append(re.compile("^" + re.sub(r"\\\$\\\{[^}]*\\\}", "[^/]+",
                                                  re.escape(roh)) + "$"))
        for roh in re.findall(r'[`"\']([A-Za-z0-9_./-]+\.(?:json|csv))[`"\']', text):
            muster.append(re.compile("^" + re.escape(roh) + "$"))
    return muster


def sonde_nutzlast(zeige_offen: bool = False, wurzel: pathlib.Path | None = None) -> list[str]:
    ziel = wurzel or WEB
    if not ziel.exists():
        return []                       # frische Arbeitskopie ohne Export — kein Befund
    muster = _leser_muster()
    if len(muster) < 10:
        return ["Nutzlast: keine Leser-Muster gefunden — die Sonde misst sich selbst kaputt"]

    def gelesen(pfad: str) -> bool:
        return any(m.match(pfad) for m in muster)

    befunde: list[str] = []
    for eintrag in sorted(ziel.iterdir()):
        if eintrag.name.startswith("."):
            continue
        if eintrag.name in AUSNAHMEN_NUTZLAST:
            if zeige_offen:
                print(f"    (erklaert) {eintrag.name}: {AUSNAHMEN_NUTZLAST[eintrag.name]}")
            continue
        if eintrag.is_dir():
            # Ein Verzeichnis gilt als gelesen, wenn EIN Beispiel darin passt — die Muster
            # enthalten die Kennung als Platzhalter, ein Name allein sagt nichts.
            beispiel = next((f for f in eintrag.iterdir() if f.is_file()), None)
            if beispiel is None or gelesen(f"{eintrag.name}/{beispiel.name}"):
                continue
            groesse = sum(f.stat().st_size for f in eintrag.rglob("*") if f.is_file())
        else:
            if eintrag.suffix not in {".json", ".csv"} or gelesen(eintrag.name):
                continue
            groesse = eintrag.stat().st_size
        befunde.append(f"Nutzlast: {eintrag.name} ({groesse/1e6:.1f} MB) wird ausgeliefert, "
                       f"aber von keinem Aufrufer geholt")
    return befunde


# Ab dieser Dateizahl unter `web/data` ist `next build` reproduzierbar gestorben — SIGABRT,
# Stapel in `node::fs::AfterStat`. Die Zahl steht so in `scripts/export_vorgaenge.py` und
# `web/lib/vorgangsakte.ts`; sie ist der Grund, aus dem Vorgangsakten gebuendelt werden.
BAUGRENZE = 156_000
# Ab hier melden. 130.000 sind 83 % der Grenze und lassen bei der gemessenen Rate von rund
# 340 neuen Dateien am Tag etwa zwei Monate Zeit — genug, um zu handeln statt zu hetzen.
BAUWARNUNG = 130_000


def sonde_baugrenze(zeige_offen: bool = False,
                    wurzel: pathlib.Path | None = None) -> list[str]:
    """Wie nah ist `web/data` an der Dateizahl, an der `next build` stirbt?

    ⚠ WARUM DAS EINE SONDE BRAUCHT UND KEIN TEST. Die Grenze ist an zwei Stellen im Code
    beschrieben und war trotzdem unbewacht: NICHTS zaehlte die Dateien. Der Deckel schlaegt
    erst beim Bauen ein — und kein Alltagslauf faehrt `next build`. Genau daran war der
    `/login`-Fehler vierzehn Tage lang unsichtbar. Ein Absturz im Node-Heap sieht ausserdem
    nach einem Speicherproblem aus, nicht nach zu vielen Dateien; ohne diese Zahl sucht man
    an der falschen Stelle.

    ⚠ UND WARUM NICHT DIE TAGESRATE ALARMIERT. Gemessen am 2026-09-04 wachsen die
    Verzeichnisse um rund 340 Dateien am Tag — damit reichte die Luft ueber hundert Tage.
    Gefaehrlich ist nicht das Rinnsal, sondern das naechste „eine Datei je X": `firma/` und
    `suppliers/` legten an EINEM Tag 75.389 Dateien an, fast das Doppelte der heutigen
    Restluft. Deshalb misst die Sonde den Stand, nicht die Rate, und nennt die groessten
    Verzeichnisse — dort entscheidet sich, wo man buendelt.
    """
    ziel = wurzel or WEB
    if not ziel.exists():
        return []                       # frische Arbeitskopie ohne Export — kein Befund

    je_verzeichnis: dict[str, int] = {}
    for pfad, _, dateien in os.walk(ziel):
        teil = os.path.relpath(pfad, ziel).split(os.sep)[0]
        name = "(direkt)" if teil == "." else teil
        je_verzeichnis[name] = je_verzeichnis.get(name, 0) + len(dateien)
    gesamt = sum(je_verzeichnis.values())

    groesste = sorted(je_verzeichnis.items(), key=lambda kv: -kv[1])[:5]
    if zeige_offen:
        print(f"    {gesamt:,} Dateien unter web/data · Luft bis {BAUGRENZE:,}: "
              f"{BAUGRENZE - gesamt:,}")
        for name, n in groesste:
            print(f"      {name:<20}{n:>9,}")

    if gesamt < BAUWARNUNG:
        return []
    return [f"Baugrenze: {gesamt:,} Dateien unter web/data — `next build` stirbt bei rund "
            f"{BAUGRENZE:,} (SIGABRT im Node-Heap). Noch {BAUGRENZE - gesamt:,} frei. "
            f"Groesste: " + ", ".join(f"{n} {v:,}" for n, v in groesste[:3])]


# Module unter `web/lib`, die heute niemand importiert. JEDER Eintrag braucht einen Grund;
# eine Ausnahme fuer eine Datei, die es nicht mehr gibt, laesst die Suite rot werden.
AUSNAHMEN_MODULE: dict[str, str] = {
    "lib/stripe.ts": "Zahlungs-Stub (UMGESETZT=false), noch an keiner Route; der Riegel "
                     "dagegen steht in tests/test_golive_riegel.py",
    "lib/identityGate.ts": "Leiche der am 2026-08-21 gestrichenen Erfolgspraemie; wird beim "
                           "Scharfschalten von Stripe eingefordert (tests/test_golive_riegel.py)",
}


def sonde_module(zeige_offen: bool = False,
                 wurzel: pathlib.Path | None = None) -> list[str]:
    r"""Welches Modul unter `web/lib` importiert niemand?

    ⚠ DIE HAUSFEHLERKLASSE, IM EINEN BEREICH OHNE SONDE. Sonde 1 bis 5 sehen die Datenkette
    und die Ausliefergueter; im Frontend-CODE schaute bisher nichts hin. Gefunden hat diese
    Sonde am 2026-09-04 zwei Faelle, darunter `identityGate.ts`: ein fail-closed gebautes
    Sicherheitstor mit eigenem Sperrtext, das KEINE Stelle aufruft. Wer die Datei liest,
    haelt die Zugaenge fuer geschuetzt.

    ⚠ MODULE, NICHT EINZELNE EXPORTE — und das ist eine Entscheidung gegen einen Fehlschlag.
    Der erste Entwurf zaehlte je EXPORT die Fundstellen im Quelltext. Er musste dafuer
    Kommentare und Zeichenketten entfernen (sonst gilt ein Name in seiner eigenen
    Fehlermeldung als Benutzung) — und daran ist er gescheitert: ein regulaerer Ausdruck in
    `impressum.ts` (`href\s*=\s*["\']…`) sieht fuer jeden linearen Filter wie eine
    Zeichenkette aus, verschluckte 9.797 Zeichen und liess fuenf lebende Pruefschritte als
    Leichen erscheinen. Regex von Division zu unterscheiden braucht einen Parser.

    Auf Modulebene braucht es das alles nicht: ein Import ist eine `from "…"`-Zeile, die
    steht eindeutig da. Zwei Befunde statt achtzehn, beide echt, kein Fehlalarm.
    """
    web = (wurzel or ROOT / "web")
    if not (web / "lib").is_dir():
        return []

    ENDUNGEN = {".ts", ".tsx", ".js", ".mjs"}
    quellen = [p for p in web.rglob("*")
               if p.suffix in ENDUNGEN and "node_modules" not in p.parts]
    text = {p: p.read_text(encoding="utf-8", errors="replace") for p in quellen}

    befunde: list[str] = []
    for modul in sorted(web.glob("lib/**/*")):
        if modul.suffix not in ENDUNGEN or "node_modules" in modul.parts:
            continue
        rel = modul.relative_to(web).as_posix()
        ohne = modul.relative_to(web).with_suffix("").as_posix()
        # ⚠ EIN `index` WIRD UEBER SEIN VERZEICHNIS IMPORTIERT. `lib/i18n/index.tsx` heisst
        # im Import `@/lib/i18n` — ohne diese Zeile meldet die Sonde jedes Index-Modul.
        wege = {ohne, modul.stem}
        if modul.stem == "index":
            wege.add(modul.parent.relative_to(web).as_posix())
            wege.add(modul.parent.name)
        # ⚠ DIE ENDUNG DARF MITSTEHEN. Der erste Entwurf verlangte das schliessende
        # Anfuehrungszeichen unmittelbar nach dem Modulnamen — ein Import der Form
        # `from "@/lib/ladegrund.js"` fiel damit durch, und die Sonde meldete in ihrer
        # ERSTEN Nacht prompt ein Modul als Leiche, das an fuenf Stellen importiert wird
        # (daily-2026-09-05-0030.log). Ein Fehlalarm ist hier besonders teuer: eine Sonde,
        # die grundlos anschlaegt, liest nach zwei Wochen niemand mehr.
        muster = re.compile("|".join(
            rf'["\'][^"\']*(?:@/)?{re.escape(w)}(?:\.(?:js|mjs|ts|tsx))?["\']'
            for w in sorted(wege)))
        if any(muster.search(q) for datei, q in text.items() if datei != modul):
            continue
        if rel in AUSNAHMEN_MODULE:
            if zeige_offen:
                print(f"    (erklaert) {rel}: {AUSNAHMEN_MODULE[rel]}")
            continue
        befunde.append(f"Module: {rel} wird von niemandem importiert")
    return befunde


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sonde", choices=("frische", "paritaet", "pfade", "laender",
                                       "nutzlast", "baugrenze", "module", "alle"),
                    default="alle")
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

    if a.sonde in ("nutzlast", "alle"):
        print("── Sonde 5: Nutzlast (wer liest, was wir ausliefern?) ──")
        f = sonde_nutzlast(a.offen)
        alles += f
        print(f"    {len(f)} unerklaerte Ausliefergueter")

    if a.sonde in ("module", "alle"):
        print("── Sonde 7: Module (welche Datei in web/lib importiert niemand?) ──")
        f = sonde_module(a.offen)
        alles += f
        print(f"    {len(f)} unerklaerte Leichen")

    if a.sonde in ("baugrenze", "alle"):
        print("── Sonde 6: Baugrenze (wie nah ist web/data an der Dateizahl, die `next build` toetet?) ──")
        f = sonde_baugrenze(a.offen)
        alles += f
        print(f"    {len(f)} Befund(e)")

    if alles:
        print("\n⚠ Verdrahtungspruefung: " + str(len(alles)) + " Befund(e)")
        for z in alles:
            print(f"  · {z}")
        return 1
    print("\n✓ Verdrahtungspruefung sauber")
    return 0


if __name__ == "__main__":
    sys.exit(main())
