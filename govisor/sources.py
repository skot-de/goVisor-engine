"""Quellen-Registry — deklarativer Katalog aller Datenquellen (Single Source of Truth).

**Warum das existiert.** Wettbewerber werben mit „200+ angeschlossenen Quellen". Das ist
überwiegend eine Vanity-Metrik: die meisten dieser „Quellen" sind einzelne Vergabeportale,
die ihrerseits über wenige **Aggregatoren** zusammenlaufen. goVisor setzt bewusst an den
Aggregatoren an — drei technische Basen (Connector) decken hunderte Einzelportale ab:

* **TED** (`ted-bulk`) aggregiert die oberschwelligen EU-Vergaben **aller** Mitgliedstaaten.
  Ein Connector, ~30 Länder — die eigentliche Breite (``bulk._walk`` filtert je ISO-Präfix).
* **DÖE** (`doe-api`) aggregiert die **deutschen** Portale unterschwellig. Gemessen (2026-07-29,
  Roh-eForms-Herkunft, n=952): cosinex/DTVP 23 %, DTAD 19 %, AI/evergabe.de 13 %, subreport 9 %,
  Staatsanzeiger 5 %, AUMASS 4 %, Healy 4 % — d. h. **ein** Connector ≈ die halbe deutsche
  Portallandschaft. Details/Reproduktion: [[govisor-negativbefunde]].
* **simap** (`simap-json`) aggregiert Bund + Kantone der Schweiz.

Der ehrliche Satz nach außen: **Quellen-Anzahl ist kein Coverage-Maß.** Drei Aggregator-
Connector schlagen 200 Portal-Konnektoren, wenn die 200 ohnehin durch die drei laufen. Diese
Registry zählt darum zwei Zahlen getrennt: **Connector** (technische Basis, Pflegeaufwand) und
**Herkunfts-Portale** (die aggregierte Breite, fürs Marketing ehrlich belegbar).

Eine **Quelle** = (Connector × Land × Schwellen-Tier). Die Registry treibt: den `sources`-CLI-
Überblick, das Web-„Quellen"-Panel und die Ausbau-Roadmap (`docs/quellen-landkarte.md`).

Nichts hier lädt Daten — es ist reine Deklaration. Der Ingest passiert über die Connector-CLIs
(`ingest`/`ingest-doe`/`ingest-simap`) bzw. `gold --bridge`.
"""
from __future__ import annotations

from dataclasses import dataclass, replace as _replace

# --- Connector = technische Basis (was gepflegt werden muss) ---------------------------------
CONNECTORS = {
    "ted-bulk":     "TED monatliche XML-Bulk-Pakete (ted.europa.eu) — oberschwellig, EU-weit",
    "doe-api":      "DÖE notice-exports API (oeffentlichevergabe.de = service.bund.de) — eForms, unterschwellig DE",
    "simap-json":   "simap.ch offene JSON-REST-API — CH Bund + Kantone + Gemeinden",
    "offeneverg-csv": "OffeneVergaben.at BULK-Kerndaten CSV (data.gv.at, BVergG2018) — unterschwellig AT >50k €",
    "kdq-xml":      "Kerndatenquelle XML im BRZ-Schema (brz.gv.at/eproc/kdq) — jeder AT-Auftraggeber "
                    "kann eine eigene führen; ANKÖ tut es. Index + eine Datei je Bekanntmachung",
    "ocds-json":    "OCDS-JSON-API (Open Contracting Data Standard 1.1) — UK Find-a-Tender/Contracts-Finder",
    "decp-bulk":    "DECP konsolidiert Parquet/CSV (data.gouv.fr) — Frankreich unterschwellig, tägl.",
    "netserver-html": "NetServer (Administration Intelligence) öffentliche Trefferliste — 4 DE-Landesportale, nur Bekanntmachungen (Unterlagen hinter Anmeldung)",
    "cosinex-html": "cosinex VMP Auftragsgegenstand-Überblick (server-gerendert) — DE-Landesportale NRW/RLP/BB, Bekanntmachungen MIT CPV-Division",
}

# --- Dokument-Abrufer = zweite Ebene (Vergabeunterlagen statt Bekanntmachungen) --------------
#
# **Warum getrennt gezählt.** Bis 2026-08-15 stand hier keiner von ihnen — die Registry kannte
# nur Bekanntmachungs-Quellen, und damit zeigten der `sources`-Überblick und das Web-Panel die
# gesamte Unterlagen-Ebene gar nicht. Für ein Produkt, dessen Unterscheidungsmerkmal die
# Dokumentenanalyse ist, war das die grössere Lücke.
#
# Sie einfach unter CONNECTORS zu mischen wäre aber genau die Vanity-Metrik, gegen die der
# Modul-Docstring oben argumentiert: aus 8 Connectoren würden 20, ohne dass eine einzige
# Bekanntmachung mehr hereinkäme. Zwei Ebenen, zwei Zahlen — `Source.ebene` trennt sie, und
# `summary()`/`dach_matrix()` rechnen sie NICHT zusammen.
DOC_CONNECTORS = {
    "docfetch-cosinex":    "cosinex/DTVP-Projektraum — Sammel-ZIP, grösste DE-Familie",
    "docfetch-rib":        "RIB »meinauftrag« — Einzeldateien über requests",
    "docfetch-evergabe":   "evergabe.de — Zustellweg-Auswahl, dann Dateiliste; WAF drosselt",
    "docfetch-evgo":       "e-Vergabe des Bundes (evergabe-online.de) — Wicket, ZIP-Knopf frei",
    "docfetch-netserver":  "NetServer — Servlet-Wechsel + Modal »Alles auswählen«",
    "docfetch-healyhudson": "Healy Hudson — je Instanz verschieden (Bahn/Hamburg liefern, bieterzugang nicht)",
    "docfetch-aumass":     "aumass — ein parametrisierter Endpunkt, ID MUSS gross geschrieben sein",
    "docfetch-staatsanz":  "Staatsanzeiger — dreistufig, »Anonym als Zip« navigiert statt herunterzuladen",
    "docfetch-dab":        "Deutsches Ausschreibungsblatt — sitzungsgebundenes getZip, frischer Kontext je Vergabe",
    "docfetch-bimedien":   "bi-medien.de — Sammel-ZIP über publictender-Dienst, Links zugeklappt im DOM",
    "docfetch-lu":         "pmp.b2g.etat.lu (LU) — zwei anonyme PRADO-Schritte; Warteschlange aus der "
                          "TED-Suche statt aus Gold, weil LU nach Fristende loescht",
    "docliste-subreport":  "subreport ELViS — NUR Dateiliste, Dateien hinter Anmeldung",
    "docliste-vergabeportal-at": "vergabeportal.at-Familie — NUR Dateiliste, hCaptcha vor den Dateien",
    "docfetch-simap":      "simap.ch — offizielle API (OIDC+PKCE), Unterlagen hinter Firma + Interessensbekundung",
}

# Was ein Abrufer tatsächlich einbringt — die Achse, auf die es beim Produkt ankommt.
#   dateien   = echte Vergabeunterlagen im Bestand
#   liste     = nur Dateinamen/Grössen/Daten (beantwortet »gibt es ein LV«, ohne eine Datei)
#   gesperrt  = gebaut, Zugang aber verweigert oder an eine Entscheidung gebunden
#   ungeprueft = SONDIERT, ABER NIE ANGEFASST. Wir kennen die Engine und ihre Groesse; ob
#               sie Dateien herausgibt, hat niemand geprueft.
#
# ⚠ `ungeprueft` ist kein Platzhalter fuer „kommt noch", sondern eine Aussage: die drei
# anderen Werte sind GEMESSEN, dieser ist es ausdruecklich nicht. Wer die drei und diesen
# in einer Tabelle nebeneinanderstellt, muss die Spalte mit ausgeben — sonst sieht eine
# Vermutung aus wie ein Befund. Deshalb darf er nur bei `status="sondiert"` stehen; eine
# Regel in `scripts/pruefe_sondierung.py` haelt das fest.
ERTRAEGE = ("dateien", "liste", "gesperrt", "ungeprueft")

# --- Status einer Quelle ---------------------------------------------------------------------
#   live      = ingestet, im Produkt sichtbar
#   prepared  = Code/Brücke fertig, wartet nur auf den Voll-Ingest (z. B. Speicher)
#   candidate = identifiziert, gleiche technische Basis, noch kein Ingest-Lauf
#   research  = Quelle existiert, technische Basis noch zu klären (eigener Spike)
#   sondiert  = ANGESEHEN UND BEURTEILT, NICHT ANGEBUNDEN. Wir wissen, welche Portale es
#               gibt und ob eine Schranke davorsteht — mehr nicht. Kein Ingest, keine
#               Tabelle, kein Konnektor.
#
# ⚠ Warum `sondiert` einen eigenen Wert braucht und nicht `research` mitbenutzt: `research`
# heisst „diese QUELLE ist noch zu klaeren", `sondiert` heisst „dieses LAND ist erkundet".
# Der Unterschied ist der, an dem Polen gestolpert ist: beim Bau der Vorgangs-Tabellen wurde
# nebenbei fuer PL und EU geschrieben, damit galten beide als aufgenommene Laender, und die
# Paritaetssonde meldete 40 bestehende Tabellen als Luecke. Niemand hatte Polen aufgenommen,
# es sah nur so aus. `scripts/pruefe_sondierung.py` haelt die Trennung maschinell.
STATUSES = ("live", "prepared", "candidate", "research", "sondiert")


@dataclass(frozen=True)
class Source:
    id: str                     # stabiler Slug, z. B. "ted-fr"
    name: str                   # Anzeigename
    connector: str              # Schlüssel aus CONNECTORS
    country: str                # ISO-2 (Vergabeland)
    tier: str                   # "oberschwellig" | "unterschwellig" | "beides"
    status: str                 # aus STATUSES
    portals: int = 1            # aggregierte Herkunfts-Portale (Breite hinter der Quelle)
    coverage: str = ""          # was sie liefert
    overlap: str = ""           # bekannte Überschneidung mit anderen Quellen (Ehrlichkeit)
    url: str = ""
    # --- zweite Ebene: Vergabeunterlagen -----------------------------------------------------
    # ⚠ DREI Ebenen, nicht zwei. CLAUDE.md verlangt sie ausdruecklich, und die
    # Portal-Sondierung hat am 2026-09-03 gezeigt, warum zwei nicht reichen: die
    # Fonds-Ebene (Vergaben von Foerdermittelempfaengern, die selbst KEINE oeffentlichen
    # Auftraggeber sind) ist weder das eine noch das andere. Als "bekanntmachung"
    # eingetragen loeste sie sofort die Sondierungs-Wache aus, weil Polen auf DIESER
    # Ebene laengst aufgenommen ist — die Taxonomie war schlicht einen Wert zu kurz.
    ebene: str = "bekanntmachung"   # "bekanntmachung" | "unterlagen" | "fonds"
    ertrag: str = ""                # nur bei ebene="unterlagen": aus ERTRAEGE
    modul: str = ""                 # nur bei ebene="unterlagen": das Python-Modul


# EU/EEA-Länder, die die TED-Bulk-Pakete führen (bulk._walk filtert je ISO-Präfix).
# DE = live, AT = prepared (build_at_gold-Brücke), Rest = candidate (gleicher Connector,
# nur `ingest --country XX` + `gold`). Das ist die Breite ohne neue technische Basis.
_TED_EU = {
    "BE": "Belgien", "BG": "Bulgarien", "CZ": "Tschechien", "DK": "Dänemark",
    "EE": "Estland", "IE": "Irland", "GR": "Griechenland", "ES": "Spanien",
    "FR": "Frankreich", "HR": "Kroatien", "IT": "Italien", "CY": "Zypern",
    "LV": "Lettland", "LT": "Litauen", "LU": "Luxemburg", "HU": "Ungarn",
    "MT": "Malta", "NL": "Niederlande", "PL": "Polen", "PT": "Portugal",
    "RO": "Rumänien", "SI": "Slowenien", "SK": "Slowakei", "FI": "Finnland",
    "SE": "Schweden", "NO": "Norwegen", "IS": "Island", "LI": "Liechtenstein",
}


def _ted_status(cc: str) -> tuple[str, str]:
    """Status eines TED-Landes aus der DATENLAGE ableiten, nicht pauschal setzen.

    ⚠ Bis 2026-08-23 bekam jedes EU-Land hier fest `candidate` — „Machbarkeit belegt,
    Connector geplant". Fuer Polen war das schlicht falsch: 326.485 Bekanntmachungen
    lagen in Silber, seit dem 2026-06-29 unberuehrt, und die Registry las sich, als haette
    niemand das Land je angefasst. Ein Status, der die Datenlage nicht kennt, ist keine
    Auskunft, sondern eine Vorgabe mit Etikett.

    Die Stufen sind dieselben wie in `docs/laender/01-quellenlandschaft.md`:
        candidate  nichts da
        prepared   Silber liegt, Gold nicht — angefangen und liegengeblieben
        live       Gold liegt, das Land ist in der Kette
    """
    from pathlib import Path as _P
    wurzel = _P(__file__).resolve().parents[1] / "data"
    silber = list((wurzel / "silver" / cc / "notices").glob("*/*.parquet")) \
        if (wurzel / "silver" / cc / "notices").is_dir() else []
    gold = (wurzel / "gold" / cc / "lead_export.parquet").exists()
    if gold:
        return "live", "in der Kette"
    if silber:
        return "prepared", (f"Silber liegt ({len(silber)} Dateien), Gold NICHT — "
                            "angefangen und liegengeblieben, s. docs/land-onboarding.md")
    return "candidate", ""


def _ted_candidates() -> list[Source]:
    out = []
    for cc, name in _TED_EU.items():
        status, hinweis = _ted_status(cc)
        out.append(Source(
            id=f"ted-{cc.lower()}", name=f"TED {name}", connector="ted-bulk",
            country=cc, tier="oberschwellig", status=status,
            coverage=("EU-pflichtige Vergaben; gleiche eForms/Legacy-Pipeline wie DE/AT"
                      + (f" — ⚠ {hinweis}" if hinweis else "")),
            overlap="", url="https://ted.europa.eu",
        ))
    return out


# ------------------------------------------------------------------------------------------
# Der Katalog. Reihenfolge: live → prepared → candidate → research.
# ------------------------------------------------------------------------------------------
REGISTRY: list[Source] = [
    # --- LIVE ---
    Source("ted-de", "TED Deutschland", "ted-bulk", "DE", "oberschwellig", "live",
           portals=1, coverage="1,83 Mio. DE-Notices 2004–laufend, lückenlos, gegen TED-API verifiziert",
           overlap="Basisquelle; DÖE ergänzt unterschwellig", url="https://ted.europa.eu"),
    Source("doe-de", "DÖE Deutschland", "doe-api", "DE", "unterschwellig", "live",
           portals=8, coverage="~384k eForms-Notices, deutsche Portale aggregiert (kommunaler Bau/Wartung)",
           overlap="oberschwellig redundant zu TED; Mehrwert = unterschwellig; cosinex 23 % der DÖE-Notices",
           url="https://oeffentlichevergabe.de"),
    Source("simap-ch", "simap.ch Schweiz", "simap-json", "CH", "beides", "live",
           portals=27, coverage="CH Bund + 26 Kantone, offene JSON-API, 280 Demo-Leads",
           overlap="eigener Rechtsraum, keine Überschneidung mit TED/DÖE", url="https://www.simap.ch"),
    Source("netserver-de", "NetServer-Landesportale", "netserver-html", "DE", "beides", "live",
           portals=4,
           coverage="Bremen, Sachsen, MV, Baden-Württemberg (LandBW) — 735 Bekanntmachungen, "
                    "388 unterschwellig; Vergabestelle bei 3 von 4 Portalen (Bremen führt "
                    "sie nicht), CPV nur aus VOB/A ableitbar",
           overlap="teilweise redundant zu TED/DÖE — gemessen 18 % neu über alle vier "
                   "Portale; Mehrwert liegt im unterschwelligen Anteil. UNTERLAGEN NICHT "
                   "abgreifbar: Detailseite hinter Anmeldung",
           url="https://vergabe.bremen.de/NetServer/"),

    # --- PREPARED (Connector gebaut, wartet auf den ersten regulären Lauf) ---
    # cosinex-Landesportale. Der Connector geht NICHT über die (clientseitige) Suchmaske,
    # sondern über den server-gerenderten Auftragsgegenstand-Überblick — deshalb `requests`
    # statt Playwright, und deshalb mit ECHTEM CPV (Division) für jede Vergabeordnung.
    Source("cosinex-de", "cosinex-Landesportale (NRW/RLP/BB)", "cosinex-html", "DE",
           "beides", "prepared", portals=3,
           coverage="NRW 6.867 · Brandenburg 2.310 · RLP 625 Bekanntmachungen im Portal "
                    "(Archiv). Trefferzeile: Veröffentlichung + Frist MIT UHRZEIT, Titel, "
                    "Vergabeordnung, Typ, Vergabestelle, CPV-Division. Unterlagen NICHT "
                    "abgreifbar (Projektraum verlangt Teilnahme)",
           overlap="gemessen 2026-08-14 an 6.520 Bekanntmachungen ab 2023 (Firewall-Regeln): "
                   "23,5 % der prüfbaren neu (NRW 19 %, BB 26 %, RLP 48 %), 972 unprüfbar "
                   "(Titel zu kurz). Offene Vorgänge: 2.064, davon 322 belegt neu. Die "
                   "Dubletten deckt überwiegend TED-eForms (2.796), dann DÖE (1.038) und "
                   "DTVP (377 — dieselben Vergaben stehen doppelt in der cosinex-Familie)",
           url="https://www.evergabe.nrw.de/VMPCenter"),

    # --- PREPARED (Brücke fertig, wartet auf Voll-Ingest / Speicher) ---
    Source("ted-at", "TED Österreich", "ted-bulk", "AT", "oberschwellig", "prepared",
           portals=1, coverage="build_at_gold-Brücke fertig (lead_export/geo/deadline), dim_plz AT-PLZ da",
           overlap="oberschwellig; AT-unterschwellig (ANKÖ) wäre separate Quelle",
           url="https://ted.europa.eu"),

    # --- CANDIDATE (technische Basis verifiziert, wartet auf Ingest) ---
    # Schließt die AT-unterschwellig-Lücke. Offizielle Pflicht-Open-Data (BVergG2018, >50k € seit
    # 2019) via data.gv.at, täglich als CSV-Bulk aggregiert von OffeneVergaben.at (FOI, Open Source).
    # Bewusst NICHT das kommerzielle ANKÖ/vergabeportal.at (3.000/Tag, aber kein offener Zugang).
    Source("offeneverg-at", "OffeneVergaben.at (AT unterschwellig)", "offeneverg-csv", "AT",
           "unterschwellig", "live", portals=1,
           # ⚠ Stand bis 2026-08-30 „prepared … wartet auf Voll-Ingest". Gewartet wurde auf den
           # externen Speicher — den es seit dem 2026-07-29 gibt. Gemessen: Bronze laedt taeglich
           # (34 MB), Silber fuehrt 238.979 atverg-Saetze, 10.947 der 18.284 AT-Gold-Leads tragen
           # die `atv-`-Kennung. Der Eintrag beschrieb den Bauzustand von Ende Juli, nicht den Betrieb.
           coverage="läuft täglich. 238.979 Sätze in Silber (158.945 can / 80.034 cn), davon "
                    "10.947 von 18.284 AT-Gold-Leads. BVergG2018-Open-Data >50k €, CSV-Bulk ~34 MB",
           overlap="füllt die AT-Lücke unter der EU-Schwelle; OSB-Anteil (~36%) überlappt TED-AT → "
                   "Gold-Filter via attributes.atverg/schwelle",
           url="https://offenevergaben.at/downloads/kerndaten_dump_daily?format=csv"),

    # --- RESEARCH (bewusster Rest / niederwertig / fragmentiert) ---
    # CH freihändig + Einladungsverfahren UNTER den CHF-Schwellen erscheinen oft NICHT auf simap;
    # einige Kantone betreiben Eigenportale. Niederwertig (Direktvergabe, kein Wettbewerb → kaum
    # Lead-Wert) und auf ~26 Kantonsportale fragmentiert. Nur bei konkretem Kundenbedarf gezielt.
    # ANKÖ: geprueft am 2026-08-30, NICHT zu bauen — und der Grund ist ein anderer als der
    # bisher notierte. `docs/quellen-at-unterschwellig.md` sagte „kommerziell, Login, kein
    # offener Feed". Das erste stimmt, das letzte nicht: ANKÖ betreibt eine offene, per BVergG
    # 2018 verpflichtende Kerndatenquelle unter CC BY 4.0 — 41.709 Bekanntmachungen seit
    # 2019-03, taeglich fortgeschrieben, ohne Anmeldung abrufbar.
    #
    # Gebaut wird sie trotzdem nicht, aus einem MESSBAREN Grund: sie ist eine Teilmenge.
    # ANKÖ veroeffentlicht die Kerndaten SEINER Auftraggeber; OffeneVergaben.at buendelt die
    # aller Publizierenden und liefert 238.979 Saetze gegen 41.709 — dasselbe Recht, dieselbe
    # Lizenz, das Fuenfeinhalbfache. Dazu sind 96 % der ANKÖ-Saetze Zuschlaege (Stichprobe 89
    # aus 2026: 85× KD_8_2_Z1, 4× KD_8_1_Z2), also genau die Schicht, die atverg schon fuehrt.
    Source("ankoe-at", "ANKÖ Kerndatenquelle (AT)", "kdq-xml", "AT",
           "unterschwellig", "research", portals=1,
           coverage="offene API http://ogd.ankoe.at/api/v1/notices (XML, CC BY 4.0), 41.709 "
                    "Bekanntmachungen seit 2019-03. 96 % Zuschläge, 4 % offene Ausschreibungen",
           overlap="⚠ TEILMENGE von offeneverg-at (238.979 Sätze aus derselben BVergG-Pflicht). "
                   "Kein eigener Zugewinn — nicht bauen, solange atverg läuft",
           url="http://ogd.ankoe.at/api/v1/notices"),

    # USP: KEINE Datenquelle. Am 2026-08-30 geprueft, weil es auf der Portalliste stand.
    # Das Unternehmensserviceportal ist das MELDEFORMULAR, mit dem oesterreichische Auftraggeber
    # ihre Kerndaten-Metadaten auf data.gv.at eintragen — mit Anmeldung und dem Rollenrecht
    # „eProcurement Metadaten-Ersteller". Die Ausschreibungssuche daneben
    # (ausschreibungen.usp.gv.at) buendelt genau die Kerndatenquellen, die dort registriert
    # wurden; eine oeffentliche Schnittstelle hat sie nicht (geprueft: /api/*, /v3/api-docs,
    # /swagger-ui, /actuator → 404 bzw. 403). Wer die Daten will, liest die Quellen selbst —
    # und das tut `offeneverg-at` bereits.
    Source("usp-at", "Unternehmensserviceportal (AT)", "", "AT",
           "beides", "research", portals=0,
           coverage="⚠ keine Quelle: Meldeformular für Auftraggeber (Login + Rollenrecht). "
                    "Die Suche darauf bündelt die Kerndatenquellen von data.gv.at",
           overlap="führt zu denselben Daten wie offeneverg-at, nur ohne Schnittstelle",
           url="https://ausschreibungen.usp.gv.at"),

    Source("ch-kantonal", "CH kantonale Eigenportale (freihändig/Einladung)", "simap-json", "CH",
           "unterschwellig", "research", portals=0,
           coverage="unter simap-Publikationspflicht; fragmentiert über Kantonsportale",
           overlap="Rest-Schwanz unter simap; niederwertig, bewusst kein 100%-Ziel",
           url=""),

    # === Über DACH hinaus (technische Basis recherchiert/verifiziert, Connector noch zu bauen) ===
    # UK ist seit Brexit NICHT in TED → echte Lücke, die unser TED-Connector nicht schließt.
    # Find-a-Tender + Contracts-Finder publizieren OCDS-JSON über offene APIs (ober- UND unterschwellig).
    Source("uk-fts", "UK Find a Tender (ober+unterschwellig)", "ocds-json", "GB", "beides", "candidate",
           portals=1, coverage="OCDS 1.1.5 JSON-API, real-time ab 2021; Procurement Act 2023",
           overlap="kein TED-Overlap (UK aus TED ausgeschieden) — kompletter Neumarkt",
           url="https://www.find-tender.service.gov.uk/api/1.0/"),
    Source("uk-cf", "UK Contracts Finder (unterschwellig)", "ocds-json", "GB", "unterschwellig",
           "candidate", portals=1, coverage="OCDS-JSON, sub-threshold; ergänzt Find-a-Tender nach unten",
           overlap="England/Wales/NI (Schottland separat); Teilüberlappung mit FTS via OCDS-ocid dedupbar",
           url="https://www.contractsfinder.service.gov.uk/apidocumentation"),
    # Frankreich: TED-FR liefert oberschwellig; DECP ergänzt unterschwellig (Pendant zu DÖE/atverg),
    # offizielle Pflicht-Open-Data, konsolidiert als Parquet (nativ zu unserem Stack) + CSV.
    Source("fr-decp", "France DECP (unterschwellig)", "decp-bulk", "FR", "unterschwellig", "candidate",
           portals=1, coverage="Données Essentielles Commande Publique, konsolidiert Parquet/CSV, "
                    "tägl. AB 40.000 EUR NETTO (README des Schemas, gemessen 2026-09-02) — also "
                    "unterhalb der EU-Schwellen, wo TED nichts hat.",
           overlap="ergänzt TED-FR nach unten (Pflicht seit 2019). ⚠ ZWEI GRENZEN, beide am "
                   "Schema v2.0.3 gemessen: (1) KEINE UNTERLAGEN — null Treffer für "
                   "dce/dossier/document/fichier/url im ganzen Schema, es führt nur `marche` "
                   "und `contrat-concession`. (2) NACH DEM ZUSCHLAG — Käufer, CPV, Laufzeit, "
                   "Unterauftragsakte, Änderungen, aber keine laufende Ausschreibung. Für die "
                   "Dokumentenfrage ist DECP keine Tür.",
           url="https://www.data.gouv.fr/datasets/donnees-essentielles-de-la-commande-publique-consolidees-format-tabulaire"),
]

# TED-EU-Breite anhaengen. Der Status kommt aus der Datenlage, nicht aus einer Vorgabe.
REGISTRY += _ted_candidates()

# ⚠ DASSELBE FUER DIE VON HAND GESCHRIEBENEN TED-EINTRAEGE. `ted-at` stand fest auf
# `prepared`, obwohl Oesterreich seit Wochen taeglich durch die Kette laeuft — ein
# getippter Status altert, sobald jemand das Land fertig baut, und niemand merkt es.
# Betroffen sind NUR die `ted-*`-Landeseintraege; Portale und nationale Quellen behalten
# ihren kuratierten Status, weil dort die Datenlage nichts ueber den Anbindungsstand sagt.
for _i, _s in enumerate(REGISTRY):
    if _s.connector == "ted-bulk":
        _status, _ = _ted_status(_s.country)
        if _status != _s.status:
            REGISTRY[_i] = _replace(_s, status=_status)


# ------------------------------------------------------------------------------------------
# EBENE 2 — Vergabeunterlagen. Zahlen gemessen 2026-08-15 am Bestand (offene Leads mit Link /
# davon mit Unterlagen auf der Platte). Sie veralten wie alle Messungen hier: das Datum steht
# deshalb dabei, statt so zu tun, als wäre es ein Live-Wert.
#
# `status` heisst hier: live = läuft im Tageslauf und liefert · prepared = gebaut, erster
# regulärer Lauf steht aus. Ob überhaupt etwas zu holen ist, sagt `ertrag`, nicht der Status —
# `docliste-*` und simap sind fertig gebaut und liefern trotzdem keine Datei.
# ------------------------------------------------------------------------------------------
DOC_REGISTRY: list[Source] = [
    # ── SONDIERT, NICHT ANGEBUNDEN ────────────────────────────────────────────────────
    #
    # ⚠ Diese Eintraege tragen `status="sondiert"` und KEINEN Konnektor. Sie sagen: wir
    # wissen, dass es diese Engine gibt und wie gross sie ist — wir holen dort nichts.
    # Wer anbindet, traegt den Konnektor ein UND hebt den Status; in dieser Reihenfolge,
    # nie umgekehrt. `scripts/pruefe_sondierung.py` haelt das fest.
    #
    # Gemessen am TED-Monatspaket 2026-06 (8.027 FR-Bekanntmachungen, 6.016 mit
    # Portal-URL). Kein franzoesisches Portal wurde dafuer beruehrt — die Engine steht im
    # URL-Pfad, den TED selbst veroeffentlicht. Kapitel: docs/sondierung/fr.md
    Source("sond-fr-aws", "AWS-Achat (marches-publics.info)", "", "FR", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="25 % der FR-Bekanntmachungen mit Portal-URL (1.682 im Juni 2026)",
           overlap="CAPTCHA. Der anonyme Abruf wird ausdruecklich angeboten (arrêté du "
                   "14/12/2009), das Formular verlangt aber `captchaVal` gegen ein Bild. "
                   "Fuer einen Menschen gangbar, fuer einen Automaten nicht — ⚠ eigene "
                   "Kategorie, KEINE Login-Wand: es braucht kein Konto.",
           url="https://www.marches-publics.info"),
    Source("sond-fr-atexo", "Atexo/MPE (PLACE, Maximilien, Mégalis, Alsace u. a.)", "", "FR",
           "beides", "sondiert", portals=6, ebene="unterlagen", ertrag="gesperrt",
           coverage="25 % — ⚠ PLACE laeuft auf derselben Engine, damit 14 % + 11 % zusammen",
           overlap="Login-Wand, an zwei Instanzen bestaetigt: „Vous devez être connecté pour "
                   "accéder aux actions ci-dessous\". Die SUCHE ist frei (PLACE listet 2.374 "
                   "laufende Vergaben anonym), die DATEIEN nicht.",
           url="https://marches.maximilien.fr"),
    Source("sond-fr-achatpublic", "achatpublic.com", "", "FR", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="12 % (830)",
           overlap="robots.txt verbietet es: `User-agent: * → Disallow: /`, Freigabeliste "
                   "nur fuer benannte Suchmaschinen. Die Seite wurde deshalb nicht aufgerufen.",
           url="https://www.achatpublic.com"),
    Source("sond-fr-securises", "marches-securises.fr (Atline)", "", "FR", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="ungeprueft",
           coverage="5 % (358)",
           overlap="unbestimmt — der von TED veroeffentlichte Einstieg fuehrt auf 404, "
                   "die Seite wurde umgebaut. Neuer Einstiegspunkt zu finden.",
           url="https://www.marches-securises.fr"),
    # ── PL, sondiert am 2026-09-02 · Kapitel: docs/sondierung/pl.md ───────────────────
    # ⚠ Polen hat Gold auf BEKANNTMACHUNGSEBENE (aus dem Vorgangs-Bau), auf Unterlagen-
    # ebene nichts. Genau deshalb unterscheidet `pruefe_sondierung.py` seit heute die
    # Ebenen — die erste Fassung haette diese vier Zeilen faelschlich beanstandet.
    Source("sond-pl-ezamowienia", "ezamowienia.gov.pl (staatliche Plattform)", "", "PL",
           "beides", "sondiert", portals=1, ebene="unterlagen", ertrag="dateien",
           coverage="19 % der PL-Bekanntmachungen mit Portal-URL — und ueber die BZP-API "
                    "zusaetzlich die UNTERSCHWELLIGE Ebene (`isTenderAmountBelowEU`).",
           overlap="✅ OFFEN, am 2026-09-02 belegt: /mo-board/api/v1/notice (ohne Antrag), "
                   "/mp-readmodels/api/Search/GetTenderDocuments und "
                   "/mp-readmodels/api/Tender/DownloadDocument liefern anonym ein PDF "
                   "(464.178 B, 25 Seiten, blankes curl). Jede Bekanntmachung traegt das "
                   "Pflichtfeld „Zamawiający zastrzega dostęp…: Nie\". ⚠ robots.txt enthaelt "
                   "nur `as` — kaputt, keine Erlaubnis: Takt selbst setzen.",
           url="https://ezamowienia.gov.pl"),
    Source("sond-pl-opennexus", "Open Nexus (platformazakupowa.pl)", "", "PL", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="30 % — die groesste PL-Engine",
           overlap="⛔ VERBOTEN, NICHT VERSCHLOSSEN. Die Dateien haengen offen an der "
                   "Vergabeseite (/file/get_new/<hash>.pdf), und genau dieser Pfad steht "
                   "in der robots.txt: `Allow: / · Disallow: /file/get_new/*` bei "
                   "`Crawl-delay: 900`. Durchsuchen erlaubt, Herunterladen untersagt. "
                   "Nicht abgerufen.",
           url="https://platformazakupowa.pl"),
    Source("sond-pl-marketplanet", "Marketplanet (*.ezamawiajacy.pl)", "", "PL", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="21 % oberschwellig, 17 % unterschwellig — mandantenfaehig",
           overlap="🟡 FREI IM BROWSER, NICHT PER SKRIPT. Keine robots.txt, Dokumentenliste "
                   "offen, Pfad heisst `/app/demand/notice/public/…/downloadsiwz`. Der "
                   "Download ist aber zweistufig: ein POST liefert `/repository/download/"
                   "zip/<token>`, und der Token ist SITZUNGSGEBUNDEN — curl bekommt 404. "
                   "Kein Konto noetig, aber kein Automat. Wie Bund/AI in DE.",
           url="https://oneplace.marketplanet.pl"),
    Source("sond-pl-eb2b", "eB2B", "", "PL", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="8 % oberschwellig, 4 % unterschwellig",
           overlap="🟡 Katalog oeffentlich (5.142 Verfahren, als „Oeffentlich\" markiert), "
                   "Verfahrensseite rendert nur Banner und Navigation. ⚠ Ob Cookie-Wand "
                   "oder Anmeldepflicht, NICHT GETRENNT: dafuer muesste die Zustimmung "
                   "erteilt werden, und der Banner laesst nur „Akzeptieren\" oder "
                   "„Seite verlassen\" zu.",
           url="https://platforma.eb2b.com.pl"),
    Source("sond-pl-logintrade", "LoginTrade", "", "PL", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="6 % ober- wie unterschwellig",
           overlap="⛔ robots.txt verbietet zweimal punktgenau die Dokumente: "
                   "`Disallow: /zalaczniki/` (poln. Anlagen) und `Disallow: /DocumentService`. "
                   "Nicht abgerufen.",
           url="https://logintrade.net"),
    Source("sond-pl-propublico", "e-propublico.pl", "", "PL", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="4 % oberschwellig, 3 % unterschwellig",
           overlap="⛔ Login-Wand: die Startseite leitet auf /Account/SignIn. (Die "
                   "Zertifikatskette wird unvollstaendig ausgeliefert — Schoenheitsfehler, "
                   "keine Schranke.)",
           url="https://e-propublico.pl"),
    # ── ES, sondiert am 2026-09-02 · Kapitel: docs/sondierung/es.md ───────────────────
    Source("sond-es-placsp", "PLACSP (contrataciondelestado.es)", "", "ES", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="63 % der ES-Ausschreibungen — die staatliche Pflichtplattform",
           overlap="⛔ robots.txt: `User-agent: * / Disallow: /` fuer die GANZE Seite. ⚠ Und "
                   "zugleich betreibt sie einen dokumentierten Open-Data-Ausgang (ZIP + "
                   "ATOM-Syndikation, CODICE-XML, Werkzeug OpenPLACSP unter EUPL) — auf "
                   "demselben gesperrten Host. Der Umweg ueber datos.gob.es traegt auch "
                   "nicht (sperrt /api/ und die Exporte), und der ZWEITE PLACSP-Host "
                   "contrataciondelsectorpublico.gob.es sperrt identisch — die Sperre ist konsistent, nicht versehentlich. Das ist eine Frage "
                   "AN DEN BETREIBER, kein Fall fuer einen Umweg. Nicht abgerufen.",
           url="https://contrataciondelestado.es"),
    Source("sond-es-catalunya", "Katalonien (contractaciopublica.cat)", "", "ES", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="dateien",
           coverage="5 % der ES-Ausschreibungen — ⚠ nach unten korrigiert, die zuerst gemeldeten 14 % stammten aus Domain-Nennungen ueber ALLE Notice-Arten",
           overlap="✅ OFFEN, am 2026-09-02 belegt: /portal-api/descarrega-document/<id>/<hash> "
                   "liefert anonym ein PDF (572.366 B, 24 Seiten, blankes curl). Die "
                   "kooperativste robots.txt der Sondierung — `Allow: /` mit Crawl-delay 1, "
                   "60/min und Wunschzeit 18:00-07:00. ✅ Am 2026-09-02 an ECHTEN Pliegos "
                   "nachgeholt: PCAP einer am selben Tag veroeffentlichten Ausschreibung, "
                   "859.193 B, 30 Seiten, anonym. ⚠ TED verlinkt hier nur das Kaeuferprofil, "
                   "nicht die Vergabe — ein Schritt mehr zur Datei.",
           url="https://contractaciopublica.cat"),
    Source("sond-es-euskadi", "Baskenland (contratacion.euskadi.eus)", "", "ES", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="8,5 %",
           overlap="⛔ robots.txt sperrt unter vielem anderen ausgerechnet "
                   "`/anuncio_contratacion/` — die Vergabebekanntmachungen selbst.",
           url="https://www.contratacion.euskadi.eus"),
    Source("sond-es-galicia", "Galicien (contratosdegalicia.gal)", "", "ES", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="1 %",
           overlap="⛔ `disallow: /` mit fuenf namentlich erlaubten Seiten.",
           url="https://www.contratosdegalicia.gal"),
    Source("sond-es-andalucia", "Andalusien (Junta de Andalucía)", "", "ES", "beides",
           "sondiert", portals=5, ebene="unterlagen", ertrag="gesperrt",
           coverage="8 % der ES-Ausschreibungen",
           overlap="🔗 NICHT GESPERRT, SONDERN KAPUTT — eine eigene Kategorie. 170 von 206 "
                   "Bezuegen (83 %) zeigen auf tote Hosts: `sirecftdpriexp.chap.junta-"
                   "andalucia.es` loest gar nicht auf (86), `ceh.junta-andalucia.es` hat ein "
                   "Zertifikat fuer *.juntadeandalucia.es OHNE Bindestrich (52), sspa gibt "
                   "403 (26). Ursache ist ein Schreibfehler im Hostnamen; derselbe Pfad auf "
                   "dem korrigierten Host antwortet mit HTTP 200. ⚠ Eine Adresse in TED ist "
                   "kein Beleg, dass es die Seite gibt.",
           url="https://www.juntadeandalucia.es"),
    Source("sond-es-madrid", "Madrid (contratos-publicos.comunidad.madrid)", "", "ES",
           "beides", "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="4 % der ES-Ausschreibungen",
           overlap="🎯 DIE ADRESSE ZEIGT AUF GAR KEINE VERGABE. Von 380 Madrider "
                   "TED-Adressen tragen 0 % eine Vergabe-Kennung; die haeufigste ist "
                   "162-mal die blosse STARTSEITE. Der Weg endet vor dem Portal, nicht "
                   "an ihm. Dazu: robots sperrt /sites/default/files/PCON/* (Pliegos de "
                   "Condiciones) und /contratos? mit Parametern; zwei Nebenhosts loesen "
                   "nicht auf (derselbe Schreibfehler wie Andalusien).",
           url="https://contratos-publicos.comunidad.madrid"),
    Source("sond-es-rest", "Navarra u. a.", "", "ES", "beides",
           "sondiert", portals=5, ebene="unterlagen", ertrag="ungeprueft",
           coverage="zusammen ~1 % — ungeprueft", overlap="ungeprueft",
           url="https://portalcontratacion.navarra.es"),
    # ── IT, sondiert am 2026-09-03 · Kapitel: docs/sondierung/it.md ───────────────────
    # ⚠ Italien hat KEIN dominantes System: 538 Domains, groesste Engine 10 %.
    Source("sond-it-soresa", "Soresa (Kampanien)", "", "IT", "beides",
           "sondiert", portals=2, ebene="unterlagen", ertrag="dateien",
           coverage="4 % der IT-Ausschreibungen — und 99 % der Adressen fuehren tief",
           overlap="✅ OFFEN, am 2026-09-03 belegt: portale.soresa.it zeigt die Vergabe, "
                   "siaps.soresa.it liefert die Dateien (dort keine robots.txt, 404). "
                   "`Disciplinare di gara.pdf` anonym geholt: 1.476.938 Bytes, 43 Seiten, "
                   "blankes curl — die Groesse stimmt aufs Byte mit der im Link genannten. "
                   "Der Link traegt Name, Groesse UND SHA256.",
           url="https://portale.soresa.it"),
    Source("sond-it-toscana", "START Toscana", "", "IT", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="4 %, Adressen zu 87 % tief",
           overlap="⛔ Blaettern erlaubt (/tendering/ frei), Herunterladen verboten: robots "
                   "sperrt */attachments/download/*, */document-requests/download/* in vier "
                   "Varianten. Dritter Fall dieser Art nach Open Nexus und LoginTrade (PL).",
           url="https://start.toscana.it"),
    Source("sond-it-aria", "ARIA/Sintel (Lombardei)", "", "IT", "beides",
           "sondiert", portals=2, ebene="unterlagen", ertrag="gesperrt",
           coverage="10 % — die groesste IT-Engine",
           overlap="🎯 KEINE SPERRE, ABER KEINE ADRESSE. Kein robots.txt (404), nichts "
                   "untersagt. Aber 89 % der Adressen zeigen nur auf die Portalwurzel oder "
                   "auf `tabsNavigation.do?selected=15` — eine Ansicht, keine Vergabe. "
                   "Dieselbe Kategorie wie Madrid: der Weg endet VOR dem Portal.",
           url="https://www.sintel.regione.lombardia.it"),
    Source("sond-it-consip", "Consip / acquistinretepa (national)", "", "IT", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="ungeprueft",
           coverage="4 % — die nationale Plattform",
           overlap="🟡 robots `Disallow: /` MIT Ausnahmen: /opencms/opencms/ (der von TED "
                   "verlinkte Pfad) und /downloadservices/ sind ausdruecklich erlaubt. "
                   "Ungeprueft, weil 57 % der Consip-Adressen nicht tiefer als die "
                   "Portalwurzel fuehren — der Weg endet vorher.",
           url="https://www.acquistinretepa.it"),
    Source("sond-it-rest", "Enel, Intercenter, Albofornitori, Lazio + Schwanz", "", "IT",
           "beides", "sondiert", portals=530, ebene="unterlagen", ertrag="ungeprueft",
           coverage="zusammen 78 % — ⚠ der 61-%-Schwanz ist der interessanteste offene "
                    "Posten: 3.339 Adressen mit 72 % Tiefe auf hunderten Domains",
           overlap="ungeprueft", url="https://www.albofornitori.it"),
    # ── CZ, sondiert am 2026-09-03 · Kapitel: docs/sondierung/cz.md ───────────────────
    Source("sond-cz-ezak", "E-ZAK (mandantenfaehig, ezak.*/zakazky.*)", "", "CZ", "beides",
           "sondiert", portals=40, ebene="unterlagen", ertrag="dateien",
           coverage="28 % der CZ-Ausschreibungen; 53 % der Adressen fuehren auf EINE Vergabe "
                    "— der beste Wert des Landes",
           overlap="✅ OFFEN, am 2026-09-03 belegt. Drei Instanzen geprueft (cuni.cz, "
                   "fnbrno.cz, vsb.cz): alle mit LEERER robots.txt (200, 0 Bytes). "
                   "contract_display_<id>.html zeigt die Vergabe, document_<id>/<hash>-<name> "
                   "liefert die Datei — 30.879 B Word-Dokument, anonym, blankes curl. "
                   "⚠ Wie Atexo in FR: viele Subdomains, EINE Software.",
           url="https://www.ezak.cz"),
    Source("sond-cz-nen", "NEN / nipez (staatliche Pflichtplattform)", "", "CZ", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="28 %, aber nur 13 % der Adressen fuehren auf eine Vergabe",
           overlap="⛔ Blaettern erlaubt, Herunterladen verboten. /verejne-zakazky/ ist frei "
                   "und zeigt die Dokumente offen an, aber alle liegen unter /file?id=… und "
                   "robots sagt `Disallow: /file*`, `/*Soubor.aspx*` (soubor = Datei), "
                   "`/*LWOpenFileAdapter.aspx*`, Crawl-delay 10. VIERTER Fall dieser Art "
                   "nach Open Nexus, LoginTrade und START Toscana. Nicht abgerufen.",
           url="https://nen.nipez.cz"),
    Source("sond-cz-kommerziell", "Tender Arena, eGordion, vhodne-uverejneni", "", "CZ",
           "beides", "sondiert", portals=3, ebene="unterlagen", ertrag="ungeprueft",
           coverage="zusammen 38 %",
           overlap="🎯 Alle drei verlinken AUSSCHLIESSLICH Kaeuferprofile, nie eine Vergabe "
                   "(0 % Tiefe bei 950 Adressen). Ungeprueft, weil der Weg vorher endet.",
           url="https://www.tenderarena.cz"),
    # ── BE, sondiert am 2026-09-03 · Kapitel: docs/sondierung/be.md ───────────────────
    Source("sond-be-bosa", "BOSA eProcurement (publicprocurement.be)", "", "BE", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="offen",
           coverage="60,5 % des BE-Unterlagen-Felds (8.141 von 13.446); 2,5 % der Links ohne "
                    "Verfahren",
           overlap="⚠ FRUEHERER EINTRAG WAR FALSCH. Er sagte, die API antworte 'AUCH AUS DEM "
                   "BROWSER' mit 500, und schloss auf einen AUSFALL. Beides stimmt nicht: im "
                   "Netzprotokoll steht dieselbe Adresse einmal mit 500 und einmal mit 200. "
                   "🟡 DER 500er IST EIN FEHLENDER KOPF. Die Anwendung schickt bei JEDEM Aufruf "
                   "'Authorization: Bearer <JWT>' — auch beim anonymen Blaettern. Ohne Token "
                   "antwortet die Schnittstelle mit 500 statt 401; das ist die schlechteste Art, "
                   "'dir fehlt ein Kopf' zu sagen, und sie hat neun Kapitel lang ein ganzes Land "
                   "gekostet. Fuenfter Fall dieser Klasse nach EE/PT/BG/RO — und der "
                   "irrefuehrendste, weil ein 500 wie ein Serverfehler aussieht. "
                   "✅ Sichtbarkeit: Dokumentenliste anonym vollstaendig (Titel, Sprache, Version, "
                   "Datum, darunter 'Question_Answer.docx'), Knopf 'Alle Dokumente herunterladen', "
                   "Endpunkte /api/dos/publication-workspaces/<uuid>/{documents,archive}. "
                   "⛔ NICHT GEGANGEN: das Token kommt aus einem Keycloak, dessen Zugangsdaten "
                   "OFFEN in env.config.js stehen (VITE_AUTH_REALM=supplier, "
                   "VITE_AUTH_CLIENTID=frontend-public, VITE_AUTH_CLIENTSECRET im Klartext). Ein "
                   "Client-Secret zu verwenden ist eine Entscheidung, keine Messung — sie gehoert "
                   "Sven. "
                   "✅ 3. ANLAUF: DER ABRUF IST BELEGT, durch normales Browsen — die Anwendung "
                   "ihre eigene Arbeit tun lassen statt selbst ein Token zu holen. EIN anonymer "
                   "Seitenaufruf lieferte /documents (2.357 B, 10 Dokumente) UND /archive "
                   "(6.113.357 B in 1,56 s). Kein Konto, keine Personendaten, kein CAPTCHA. "
                   "⚠ Ein Abrufer braucht dasselbe Token, das die App sich selbst ausstellt; nur "
                   "ICH darf den Weg in dieser Umgebung nicht gehen (Klassifikator). Fuer den "
                   "Anschluss ist das kein Hindernis. Gegenprobe: OHNE Token geben ALLE Endpunkte "
                   "500 — documents, archive, opening-reports, urls und der Vorgang selbst.",
           url="https://www.publicprocurement.be"),
    Source("sond-be-3p", "3P (cloud.3p.eu)", "", "BE", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="ungeprueft",
           coverage="26 %, Linktiefe 100 % (/Downloads/1/1649/6U/2026)",
           overlap="Kein robots.txt (404). Leitet auf eine Laenderauswahl mit Cookie-Banner; "
                   "die Laenderwahl waere ein gewoehnlicher Klick, die Cookie-Zustimmung "
                   "nicht. Ungeprueft.",
           url="https://cloud.3p.eu"),
    # ── NL, sondiert am 2026-09-03 · Kapitel: docs/sondierung/nl.md ───────────────────
    Source("sond-nl-tenderned", "TenderNed (nationale Pflichtplattform)", "", "NL", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="dateien",
           coverage="73 % der NL-Ausschreibungen; die API meldet 145.155 Publikationen",
           overlap="✅ OFFEN UEBER DIE OFFIZIELLE SCHNITTSTELLE — der beste bisher gemessene "
                   "Wert. Zwei APIs: eine XML-API MIT Zugangsdaten (nicht genutzt) und ein "
                   "OEFFENTLICHER Publikations-Webservice ohne Anmeldung. "
                   "/papi/tenderned-rs-tns/v2/publicaties/<id>/documenten liefert Name, Typ, "
                   "Groesse, Kategorie und virusIndicatie; .../<docId>/content die Datei: "
                   "51.586 B Word-Dokument, exakt die gemeldete Groesse, blankes curl. "
                   "robots sperrt nur CMS-Verwaltungspfade. ⚠ `publicatieCategorie` "
                   "kennzeichnet die Nota van Inlichtingen — die Bieterfragen als FELD, was "
                   "wir in DE aus Dateinamen erraten muessen.",
           url="https://www.tenderned.nl"),
    Source("sond-nl-mercell", "Mercell (s2c.mercell.com)", "", "NL", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="ungeprueft",
           coverage="22 % der NL-Ausschreibungen",
           overlap="⛔ GESPERRT. `s2c.mercell.com/robots.txt` = `User-agent: * / Disallow: /` "
                   "fuer die ganze Vergabeplattform. (Die Marketingseite www.mercell.com "
                   "sperrt dagegen nur neun einzelne Seiten — zwei Hosts, zwei Antworten.) "
                   "⚠ Das gilt laenderuebergreifend: Mercell bedient Nordeuropa, das "
                   "Baltikum und Benelux, ueberall dieselbe Plattform.",
           url="https://www.mercell.com"),
    # ── SE, sondiert am 2026-09-03 · Kapitel: docs/sondierung/se.md ───────────────────
    Source("sond-se-tendsign", "TendSign (Mercell Schweden)", "", "SE", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="52 % der SE-Ausschreibungen",
           overlap="⛔ `User-agent: * / Disallow: /`. Eigene Domain, aber dasselbe Urteil wie "
                   "s2c.mercell.com in NL — Mercell sperrt seine Vergabeplattformen "
                   "LAENDERUEBERGREIFEND, unabhaengig vom Hostnamen. Betrifft damit auch NO, "
                   "DK, FI und das Baltikum vorab.",
           url="https://tendsign.com"),
    Source("sond-se-eavrop", "e-avrop.com", "", "SE", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="36 %",
           overlap="⛔ `Disallow: /` mit einer einzigen Ausnahme (/Places.aspx).",
           url="https://www.e-avrop.com"),
    Source("sond-se-clira", "Clira / Esource", "", "SE", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="liste",
           coverage="11 % — der einzige nicht gesperrte Teil Schwedens",
           overlap="🟡 Keine robots-Sperre. Die oeffentliche Seite zeigt eine ZUSAMMENFASSUNG "
                   "(Titel, Fristen, Beschreibung), keine Dokumente; der Knopf „Till "
                   "upphandlingen\" fuehrt ohne href in einen nicht oeffentlichen Bereich. "
                   "Damit ist SE praktisch zu: 88 % robots-gesperrt, der Rest ohne Dateien.",
           url="https://annonser.clira.io"),
    # ── BALTIKUM, sondiert am 2026-09-03 · Kapitel: docs/sondierung/baltikum.md ───────
    # ⚠ EIN-PLATTFORM-LAENDER: LV und EE haben in einem ganzen Monat je EINE Domain, LT
    # praktisch auch. Ein Abrufer deckt ein ganzes Land — das beste Verhaeltnis von
    # Aufwand zu Ertrag der ganzen Sondierung (LV: 565 Ausschreibungen je Domain,
    # gegen 3 in Italien).
    Source("sond-lt-cvpis", "CVP IS (viesiejipirkimai.lt)", "", "LT", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="dateien",
           coverage="99 % Litauens — ein Land, eine Plattform",
           overlap="✅ OFFEN, am 2026-09-03 belegt. Keine robots.txt. Dreistufig, und der "
                   "Name sagt die Absicht: listContractDocuments.do → "
                   "downloadDocForAnonymous() → prepareAnonymousDownload.do → "
                   "downloadContractDocument.do. Geholt: 410.064 B ZIP mit SIEBEN echten "
                   "Vergabedokumenten (Vertragsentwurf, technische Spezifikation, ESPD, "
                   "Vergabebedingungen), anonym, blankes curl. ⚠ Die Dokumentenliste ist "
                   "SERVERGERENDERT — curl kommt ohne Browser aus, anders als fast ueberall "
                   "sonst. Der Aufbau gleicht dem franzoesischen AWS-Achat, nur OHNE CAPTCHA.",
           url="https://viesiejipirkimai.lt"),
    Source("sond-lv-eis", "EIS (eis.gov.lv)", "", "LV", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="offen",
           coverage="100 % Lettlands — EINE Domain im ganzen Monat",
           overlap="✅ GELOEST 2026-09-03, ZWEISTUFIG: (1) GET /EKEIS/Supplier/Procurement/<id> — "
                   "im onclick jeder Zeile steht das JSON im Klartext (Id, DocumentLinkTypeCode, "
                   "ProcurementIdentifier); (2) GET /EKEIS/Document/DownloadDocumentFilesInZip?"
                   "Id=&DocumentLinkTypeCode=&ProcurementIdentifier= → ein ZIP je Eintrag. "
                   "Belegt: 3 von 3 (39.377/19.275/65.078 B). ⚠ .edoc ist ein lettischer "
                   "SIGNATURBEHAELTER — dritte Verpackungsart nach IT .p7m und RO .p7s. "
                   "⚠ Der POST auf /Document/ViewDocument ist NICHT noetig (nur das Modal); wer "
                   "ihn geht, braucht __RequestVerificationToken ALS KOPFZEILE — als Formularfeld "
                   "abgelehnt ('Neveiksmiga drosibas parbaude'). "
                   "Frueherer Stand: Abrufweg ungeklaert. Keine robots-Sperre, die "
                   "Vergabeseite listet die Dokumente vollstaendig (im geprueften Fall 33 "
                   "Eintraege mit Typ, Datum, Bezeichnung), der Link heisst „Lejupielādēt "
                   "datni\" (Datei herunterladen). Er ruft aber viewDocument(), das ein Modal "
                   "PER POST oeffnet — der Dateiendpunkt ist so nicht greifbar. KEIN Hinweis "
                   "auf eine Schranke. Nachzuholen: ein Land mit einer einzigen Plattform "
                   "ist die Muehe wert.",
           url="https://www.eis.gov.lv"),
    Source("sond-ee-rhr", "RHR (riigihanked.riik.ee)", "", "EE", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="offen",
           coverage="100 % Estlands — EINE Domain",
           overlap="✅ GELOEST 2026-09-03: der Endpunkt heisst documents-temp-url, darauf kommt "
                   "man nicht durch Raten. (1) GET /rhr/api/public/v1/procurement/<id>/"
                   "documents-temp-url → {'value':'/filetransfer/client/shared/package/<guid>'}; "
                   "(2) GET diesen Pfad → files.zip. Belegt: 19.307.558 B, 9 Dateien "
                   "(Vergabepass, ESPD-XML, Eignungs-/Wertungskriterien, technische Beschreibung, "
                   "Vertragsbedingungen, englische Fassung als ZIP IM ZIP). "
                   "⚠ Fuenf geratene Pfade gaben 500; gefunden durch Klick auf 'Laadi alla "
                   "kehtivad hanke dokumendid' und Mitlesen. Wo Raten 500 gibt, hilft nur Zusehen. "
                   "Frueherer Stand: Dateiendpunkt nicht gefunden. Keine robots.txt. Zwei "
                   "offizielle Wege ohne Anmeldung: „Avaandmed\" (Monatspakete + "
                   "Maschinenschnittstelle, naechtlich, eForms-XSD — aber nur BEKANNTMACHUNGEN, "
                   "wie DECP in FR) und eine oeffentliche REST-API /rhr/api/public/v1/. "
                   "proc-vers/<id>/documents/general-info liefert anonym 9 Dokumente mit "
                   "name, fileName, fileSize, failservId und visibilityCode=PUBLIC. Fuenf "
                   "plausible Dateipfade probiert, alle 500 — ⚠ die API antwortet auf "
                   "UNBEKANNTE Pfade mit 500 statt 404, Raten gibt also kein Signal. "
                   "⚠ Und: `Accept: application/json` allein ergab 500, erst "
                   "`application/json, text/plain, */*` gab 200 und 586 KB. Wer bei einer "
                   "500 aufhoert, haelt eine offene Tuer fuer verschlossen.",
           url="https://riigihanked.riik.ee"),
    # ── LAENDERUEBERGREIFEND, in der Nachpruefung 2026-09-03 gefunden ─────────────────
    # ⚠ Diese drei fehlten in ALLEN zwoelf Kapiteln — der teuerste Teil des Methodenfehlers,
    # weil eine Pruefung mehrere Laender abgedeckt haette. Details: docs/sondierung/
    # 00b-nachpruefung.md
    Source("sond-proebiz", "Josephine / ProeBiz (CZ, PL, SK)", "", "CZ", "beides",
           "sondiert", portals=2, ebene="unterlagen", ertrag="dateien",
           coverage="josephine.proebiz.com: PL 849, CZ 268 · profily.proebiz.com: CZ 565 "
                    "(12 Monate). Bedient auch die Slowakei.",
           overlap="✅ OFFEN, am 2026-09-03 belegt. robots.txt: `User-agent: *` OHNE jede "
                   "Disallow-Zeile. /pl/tender/<id>/summary listet die Dokumente, "
                   ".../download/<id> liefert sie: 871.707 B ZIP mit SWZ.pdf (854 kB), "
                   "Vertragsentwurf, ESPD und Erklaerungen — anonym, blankes curl. "
                   "⚠ Ein Abrufer deckt drei Laender.",
           url="https://josephine.proebiz.com"),
    Source("sond-bravosolution", "BravoSolution / Jaggaer", "", "FR", "beides",
           "sondiert", portals=3, ebene="unterlagen", ertrag="gesperrt",
           coverage="sncf 1.237, ratp 856, seamilano — Versorger und Verkehrsbetriebe "
                    "mehrerer Laender",
           overlap="⛔ robots: `Disallow: /esop` — und /esop IST der Anwendungspfad; die "
                   "Adresse fuehrt auf /esop/guest/login.do. Gesperrt UND Login.",
           url="https://www.jaggaer.com"),
    Source("sond-vortal", "Vortal (ES, PT)", "", "ES", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="ungeprueft",
           coverage="community.vortal.biz: ES 255; Heimatmarkt Portugal",
           overlap="⚠ Der Pfad heisst /Public/public-tender-documents/<token>, klingt also "
                   "nach oeffentlichem Zugang — aber der Server verweigert schon die "
                   "robots.txt mit 403. Nicht weiter verfolgt.",
           url="https://community.vortal.biz"),
    # ── ZWEITE RUNDE 2026-09-03 · docs/sondierung/00b-nachpruefung.md §8-11 ───────────
    Source("sond-it-acquistitelematici", "acquistitelematici.it (222 Instanzen)", "", "IT",
           "beides", "sondiert", portals=222, ebene="unterlagen", ertrag="dateien",
           coverage="6,1 % Italiens ueber 222 Domains — groesser als Soresa",
           overlap="✅ OFFEN, belegt: /tender/<id> listet die Dokumente, "
                   "/tender/documenti/<id>/<name>?dmsDoc=1 liefert sie. 165.633 B "
                   "p7m-Behaelter mit 24-seitigem PDF (Capitolato speciale), anonym.",
           url="https://rovigo.acquistitelematici.it"),
    Source("sond-it-traspare", "traspare.com (137 Instanzen)", "", "IT", "beides",
           "sondiert", portals=137, ebene="unterlagen", ertrag="dateien",
           coverage="5,0 % Italiens ueber 137 Domains",
           overlap="✅ OFFEN, belegt: /announcements/<id> zeigt die Vergabe, "
                   "/fs_PUBLIC_action?do=download_document&id=… liefert die Datei — "
                   "20.788.918 B, 35-seitiges PDF, anonym.",
           url="https://montedoro.traspare.com"),
    Source("sond-it-tuttogare", "tuttogare.it (179 Instanzen)", "", "IT", "beides",
           "sondiert", portals=179, ebene="unterlagen", ertrag="gesperrt",
           coverage="4,6 % Italiens", overlap="⛔ robots sperrt die Dateipfade.",
           url="https://www.tuttogare.it"),
    Source("sond-eu-supply", "EU-Supply (NO, DK, NL, FR, IE, DE)", "", "NO", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="NO 3.389, DK 3.166, NL 154, FR 46, IE 42, DE 32 (12 Monate)",
           overlap="⛔ Die Vergabeseite ist OEFFENTLICH (Public RFT, kein Anmeldefeld) und "
                   "braucht nur einen Sitzungskeks. Aber der Download baut sich als "
                   "strDomain + '/app/docmgmt/downloadPublicDocument.asp' — und robots sagt "
                   "`Disallow: /app/docmgmt`. Der Dateiendpunkt liegt EXAKT im gesperrten "
                   "Pfad. Fuenfter Fall dieser Bauart. Nicht abgerufen.",
           url="https://eu.eu-supply.com"),
    # ── Mercell (NO/NL/DK/DE/FI/LU), sondiert am 2026-09-03 · docs/sondierung/mercell.md ─
    Source("sond-mercell", "Mercell (NO, NL, DK, DE, FI, LU)", "", "NO", "beides",
           "sondiert", portals=3, ebene="unterlagen", ertrag="gesperrt",
           coverage="groesste Laenderreichweite aller Anbieter: NO 286, NL 202, DK 39, DE 18, "
                    "FI 7, LU 2 (ein Monat)",
           overlap="⛔ KEIN HEBEL — und zwar ZWEIMAL, aus verschiedenen Gruenden. ⚠ Wer 'Mercell' "
                   "als EINE Quelle behandelt, misst falsch: es sind drei Hosts. "
                   "(1) s2c.mercell.com traegt NL 203, DE 18, LU 2 und sperrt mit 69 Bytes: "
                   "'# Tell robots not to crawl the website / User-agent: * / Disallow: /'. "
                   "(2) mercell.com (NO 285, DK 218) ERLAUBT crawlen — die robots nimmt nur DREI "
                   "einzelne Vergaben aus. Die Seite zeigt anonym Verfahrensart, Fristen, Kaeufer "
                   "UND 17 DATEINAMEN, und der Abrufweg steht im Quelltext: "
                   "/m/file/GetFile.ashx?id=<n>&version=0. Der Aufruf gibt aber HTTP 403 mit "
                   "'Just a moment… Enable JavaScript and cookies' — eine CLOUDFLARE-BOT-PRUEFUNG. "
                   "Die ist eine Grenze, keine Huerde; nicht umgangen, auch nicht mit einem "
                   "Browser, der sie bestehen wuerde. "
                   "(3) supplierportal.c1.app.mercell.com: FI 7, NO 1, DK 2 — 0,2 %, ungeprueft. "
                   "⚠ WAS BLEIBT: der KATALOG ist oeffentlich (Titel, Fristen, Kaeufer, "
                   "Dateinamen). Fuer eine Lead-Liste reicht das, fuer Dokumentenanalyse nicht.",
           url="https://www.mercell.com"),
    # ── RO, sondiert am 2026-09-03 · Kapitel: docs/sondierung/ro.md ───────────────────
    Source("sond-ro-seap", "SEAP/SICAP (RO)", "", "RO", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="offen",
           coverage="99,7 % des rumaenischen Unterlagen-Felds (3.591 von 3.603 in 3 Monaten); "
                    "1.257 Ausschreibungen/Monat; 15,1 % der Links ohne Verfahren",
           overlap="✅ OFFEN — und BIS ZUM 2026-09-03 IN DER GANZEN SONDIERUNG UNSICHTBAR: zwei "
                   "Muster-Fehler in unseren Skripten (listName='eforms-country', "
                   "Namensraum-Praefix) zeigten 5 statt 1.257 Ausschreibungen im Monat. "
                   "robots: weiches 404, nichts untersagt. Die Bekanntmachung sagt selbst "
                   "'access direct, nerestrictionat, complet si gratuit'. "
                   "⏳ ERSTE ZWEIPHASIGE QUELLE: das Archiv wird auf Anfrage gebaut. "
                   "AddArchiveForNotice → GetArchiveStatus (1=offen, 2/4=wird erzeugt, 3=fertig) "
                   "→ DownloadArchive. Von 15 Anforderungen waren nach kurzer Zeit 6 fertig. "
                   "⚠ REFERER PFLICHT: ohne ihn 403 'Referrer cannot be null'. Eine "
                   "wahrheitsgemaesse Herkunftsangabe ist keine Falschangabe. "
                   "⭐ Der Knopf heisst 'arhiva documentatie SI CLARIFICARI' — Unterlagen UND "
                   "Bieterfragen in EINEM Paket; belegt: 'Raspuns consolidat' im Archiv. "
                   "⚠ VERPACKUNG: 7 von 9 Dateien sind .p7s (PKCS#7-Signaturumschlag wie IT .p7m); "
                   "'Formulare.rar.p7s' ist RAR in Signatur in ZIP — dreifach verschachtelt. "
                   "⚠ MENGE: die groesste der Sondierung. Median 13,2 MB, Mittel 76,7 MB, "
                   "groesstes Archiv 374,9 MB je Vergabe → grob 190 GB bis 1,1 TB im Jahr. "
                   "GetArchiveStatus liefert fileSize VOR dem Abruf — zwingend nutzen. "
                   "⚠ Die Statusantwort enthaelt einen internen UNC-Pfad des Betreibers "
                   "(\\\\Fserver14\\FShare2\\SICAPPROD\\…) — gehoert NICHT in Bronze.",
           url="https://e-licitatie.ro"),
    # ── LU, sondiert am 2026-09-03 · Kapitel: docs/sondierung/lu.md ───────────────────
    Source("sond-lu-pmp", "Portail des marchés publics (LU) — Sondierungsbefund", "", "LU",
           "beides", "sondiert", portals=1, ebene="bekanntmachung", ertrag="teilweise",
           coverage="87,0 % des luxemburgischen Unterlagen-Felds (1.618 von 1.859); EIN einziges "
                    "orgAcronyme (t5y) fuer das ganze Land",
           overlap="🟡 OFFEN, ABER MIT ZEITFENSTER. robots.txt: 'User-agent: * / Disallow:' — ein "
                   "LEERES Disallow, also ausdruecklich alles erlaubt (2. Erlaubnis nach BG). "
                   "Keine Anmeldung, kein CAPTCHA. Software ist ATEXO/MPE wie Frankreichs PLACE — "
                   "dort scheiterte es an CAPTCHA+Login, hier nicht: gleiche Software, andere "
                   "Konfiguration. "
                   "⏳ ⚠ DER ENTSCHEIDENDE FUND: DIE UNTERLAGEN VERSCHWINDEN NACH FRISTENDE. Alle "
                   "30 Vergaben aus TED-Paketen der letzten 3 Monate meldeten 'Aucune piece n'a "
                   "ete jointe'; drei LAUFENDE Vergaben aus der Portalsuche trugen 'Dossier de "
                   "soumission' mit 4,41 / 1,41 / 26,15 MB. Fuer LU gibt es KEINE nachtraegliche "
                   "Ernte — ein Abrufer muss dem laufenden Bestand folgen, nicht dem TED-Archiv. "
                   "Erster Zeitfenster-Fall der Sondierung; gehoert als eigene Frage in jede "
                   "weitere Pruefung. "
                   "✅ ABRUFWEG BELEGT (2026-09-03, von Sven freigegeben): ZWEI anonyme "
                   "Formularschritte (RadioGroup=choixAnonyme → PRADO_POSTBACK_TARGET=completeDownload) "
                   "liefern 4.626.716 Bytes mit 6 Dokumenten, ohne Personendaten. ⚠ PRADO_PAGESTATE "
                   "ist 11.840 Zeichen und muss mitgefuehrt werden — Sitzung noetig, kein Adressbauplan. "
                   "⚠ ZIP-Namen mit verstuemmelten Umlauten (dritter Fall nach CY und HU). "
                   "Der Weg beginnt bei /index.php?page=Entreprise."
                   "EntrepriseDemandeTelechargementDce&id=<n> ist ohne Anmeldung erreichbar und "
                   "bietet ausdruecklich 'Je souhaite telecharger ANONYMEMENT le Dossier' "
                   "(Feld choixAnonyme), ohne Personendaten. Das ist EIN POST — nicht abgesendet, "
                   "weil ein Formular abzusenden eine Handlung ist und Svens Zustimmung braucht. "
                   "🇪🇺 BESONDERHEIT: 8 % der 'LU'-Ausschreibungen stammen von EU-Institutionen mit "
                   "Sitz in Luxemburg (ec.europa.eu 6,9 %, eib.org 1,6 %, curia.europa.eu 1,5 %) — "
                   "wer LU-Zahlen mit anderen Laendern vergleicht, vergleicht nicht dasselbe.",
           url="https://pmp.b2g.etat.lu"),
    # ── DK, sondiert am 2026-09-03 · Kapitel: docs/sondierung/dk.md ───────────────────
    Source("sond-dk-ethics", "Ethics (DK)", "", "DK", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="offen",
           coverage="17,5 % des daenischen Unterlagen-Felds (656 von 3.741); 8 von 8 Vergaben "
                    "geantwortet, 142 Dokumenteintraege",
           overlap="✅ OFFEN, zwei Aufrufe: GET /ethics/publicTenderDocs/<guid> → tenderDocs[] → "
                   "GET /ethics/publicTenderDoc/<guid>/downloadFolder/<docId> (ein ZIP je Ordner). "
                   "Seite heisst 'Offentligt udbudsmateriale', keine robots.txt (404). "
                   "🎁 Die Eintraege tragen MD5 UND SHA1 (md5, checksum) — mehr als Bulgarien, das "
                   "nur MD5 gibt — dazu length, state=PUBLISHED, cat und folderFiles. "
                   "⚠ UMFANG: ein einziger Ordner ('07-Tegninger') war 64.440.964 Bytes; eine "
                   "einzelne Bauzeichnung 7 MB. Die length-Angabe VOR dem Abruf nutzen.",
           url="https://www.ethics.dk"),
    Source("sond-dk-eusupply", "EU-Supply CTM (DK, NO, NL)", "", "DK", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="28,3 % des daenischen Unterlagen-Felds (1.058); nach der Herstellerzaehlung "
                    "auch NO 99 und NL 3",
           overlap="⛔ LISTE ERLAUBT, DATEIEN GESPERRT — der lehrreichste Fall des Kapitels. Die "
                   "robots.txt sperrt '/app/docmgmt'. Die TED-Adresse fuehrt aber auf "
                   "/app/rfq/publicpurchase_docs.asp (NICHT gesperrt), und diese Seite liefert "
                   "anonym 107 Dateinamen mit Verweisen javascript:DownloadPublicDocument(…). "
                   "⚠ Die Funktionsdefinition zeigt: strDownloadPublicDocumentURL = strDomain + "
                   "'/app/docmgmt/downloadPublicDocument.asp' — die Dateien liegen genau unter dem "
                   "gesperrten Pfad. Dieselbe Konstruktion wie GR-Διαύγεια. KEINE Datei abgerufen. "
                   "⚠ REGEL: ein Funktionsname ist keine Erlaubnis. 'DownloadPublic…' sagt, wofuer "
                   "der Betreiber die Funktion haelt; die robots.txt sagt, was er von Abrufern "
                   "will. ⚠ Gilt auch fuer NO und NL — dieselbe robots.txt, derselbe Pfad.",
           url="https://eu.eu-supply.com"),
    Source("sond-dk-rest", "comdia, Mercell, iBinder, Amgros (DK)", "", "DK", "beides",
           "sondiert", portals=4, ebene="unterlagen", ertrag="gesperrt",
           coverage="comdia 16,2 % · Mercell 14,1 % · Amgros 5,4 % · iBinder 2,9 % = 38,6 %",
           overlap="⛔ comdia leitet auf /Login.aspx mit Passwortfeld (robots sperrt nur "
                   "/keepAlive.aspx — die Grenze ist ein Konto, keine Regel). Mercell leitet auf "
                   "'Sign in / Tender access' (kommerzieller Dienst). Amgros verlinkt aus TED "
                   "AUSSCHLIESSLICH die Startseite. "
                   "⚠ iBinder ist die Warnung, die zu merken lohnt: die Adresse endet auf '/public' "
                   "und landet trotzdem auf signin.ibinder.com mit E-Mail und Passwort. "
                   "Gegenstueck zur slowenischen Lehre (CAPTCHA auf der Suchmaske heisst nicht "
                   "CAPTCHA am Abruf): DAS WORT 'public' IM PFAD IST KEIN VERSPRECHEN.",
           url="https://www.comdia.com"),
    # ── FI, sondiert am 2026-09-03 · Kapitel: docs/sondierung/fi.md ───────────────────
    Source("sond-fi-hilma", "HILMA (FI)", "", "FI", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="offen",
           coverage="9,2 % des finnischen Unterlagen-Felds (714 von 7.771); 6 von 7 Vergaben "
                    "tragen Anhaenge, 29 von 29 Dateien geladen, 0 Fehlschlaege",
           overlap="✅ OFFEN, reine Schnittstellenkette: GET /web/api/public/procedure/<pid>/"
                   "enotice/<nid> → attachments[{id,name}] → GET cdn.…/public-attachments/<id>. "
                   "⚠ Das '/web/' davor war der ganze Unterschied — vier geratene Pfade gaben "
                   "sauberes JSON-404; gefunden nur durch Mitlesen der laufenden Anwendung. "
                   "Der Dateihost (Azure) gibt auf robots.txt 401 — Antwort eines Objektspeichers "
                   "auf ein fehlendes Objekt, keine Regel (wie Bulgariens S3-403). "
                   "🎁 Beigaben: die Ansicht rendert eForms MIT BT-Feldnummern im Klartext, und "
                   "das CDN liefert die eForms-SDK-Codelisten (1.10 und 1.13) als JSON.",
           url="https://www.hankintailmoitukset.fi"),
    Source("sond-fi-cloudia", "Cloudia Tarjouspalvelu (FI)", "", "FI", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="82,4 % des finnischen Unterlagen-Felds (6.404 von 7.771)",
           overlap="⛔ ANMELDUNG. 7 von 7 TED-Adressen liefern dieselbe Huelle mit "
                   "<input type='password'>; im Browser antwortet die Anwendung 'No access right "
                   "to the function'. Keine robots-Sperre — die Grenze ist ein Konto, keine Regel. "
                   "⚠ HILMA IST KEIN HINTEREINGANG: ueber 668 FI-Ausschreibungen eines Monats "
                   "liegen 546 NUR auf Cloudia, 55 NUR auf HILMA und NULL auf beiden. HILMA hostet "
                   "Unterlagen nur fuer Verfahren, die dort selbst angelegt wurden — das sagt die "
                   "Plattform auf ihrer eigenen Seite, und die 0 Ueberschneidungen belegen es. "
                   "Finnland ist damit kein Ein-Plattform-Land, sondern ein Zwei-Klassen-Land: "
                   "offen oder zu, je nachdem welches Werkzeug die Vergabestelle gekauft hat.",
           url="https://tarjouspalvelu.fi"),
    Source("sond-fi-schwanz", "Kleinplattformen (FI)", "", "FI", "beides",
           "sondiert", portals=83, ebene="unterlagen", ertrag="teilweise",
           coverage="8,4 % ueber 83 Domains; nur drei stichprobenartig geprueft",
           overlap="🟡 GEMISCHT, und das Muster steht in den Adressen: 'rfq2REGISTRATION', "
                   "'/fi/REGISTER/<hash>', 'Quotations/SIGNUP.aspx' — die kleineren Plattformen "
                   "verlangen ein Konto und sagen es im Pfad. "
                   "⛔ bem.buildercom.net (1,9 %) sperrt ausdruecklich: robots.txt 26 Bytes, "
                   "'User-Agent: * / Disallow: /'. "
                   "sokobid.sokopro.fi und pris.haahtela.fi untersagen nichts, zeigen aber ohne "
                   "Anwendung keinen Inhalt — nicht weiter geprueft (zusammen 1,6 %).",
           url="https://bem.buildercom.net"),
    # ── HU, sondiert am 2026-09-03 · Kapitel: docs/sondierung/hu.md ───────────────────
    Source("sond-hu-ekr", "EKR (HU)", "", "HU", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="offen",
           coverage="99,3 % des ungarischen Unterlagen-Felds (4.644 von 4.678); 0,0 % der Links "
                    "ohne Verfahren; 64 % der Vergaben tragen Dokumente (16 von 25, 68 Dateien)",
           overlap="✅ OFFEN, vier ausdruecklich oeffentliche Endpunkte (/api/PUBLIC/…): eljaras, "
                   "kereso, szotar, document. Nichts musste geraten werden. "
                   "⭐ DER DATEIABRUF BUENDELT SERVERSEITIG: POST /public/document mit "
                   "{'dokumentIdList':[15 GUIDs]} gibt EIN ZIP (8,95 MB) statt 15 Abrufe — das "
                   "kann kein anderes Portal der Sondierung. "
                   "⭐ DOKUMENTTYP AN DER QUELLE VERGEBEN (dokumentumTipus.kod): "
                   "KOZBESZERZESI_DOKUMENTACIO, MUSZAKI_LEIRAS, SZERZODES_TERVEZET, "
                   "KIEGESZITO_TAJEKOZTATAS_NYUJTASA (= Bieterfragen), RESZLETES_ARTABLAZAT. "
                   "Der Doktyp-Parser darf das NICHT ueberstimmen — durchreichen, nicht raten. "
                   "⚠ ELOZETES_VITARENDEZES (vorherige Streitschlichtung) ist eine Gattung, die "
                   "goVisor NIRGENDS kennt: foermliche Ruege gegen die Vergabebedingungen vor "
                   "Angebotsabgabe, samt Antwort. Schaerferes Signal als eine Frage. 3 von 25. "
                   "⚠ Leere dokumentumList ist eine ANTWORT, kein Fehler (gueltiger Stand, 1–6 "
                   "Bekanntmachungen) — nicht als Fehlschlag wiederholen. "
                   "⚠ ZIP-Eintragsnamen kommen in alter Kodierung an (Egys+?g+?r-gy+?jtem+?ny).",
           url="https://ekr.gov.hu"),
    Source("sond-hu-ekr-kereso", "EKR Suche (HU, beide Ebenen)", "", "HU", "ausschreibung",
           "sondiert", portals=1, ebene="bekanntmachung", ertrag="offen",
           coverage="4.417 laufende Vergaben, 45 Seiten; 60 % davon erreichen TED nie",
           overlap="✅ /eljarastar/api/public/kereso?jovobeli=true&aktualis=true&offset=&limit= — "
                   "anonym, geblaettert. Nach Verfahrensordnung (Stichprobe 100): Unios 40 % "
                   "(oberschwellig), EPK 37 %, Nemzeti 23 % → 60 % NATIONAL. Zentrale Quelle fuer "
                   "beide Ebenen wie PL und SI, kein zweites Portal. "
                   "Dazu /public/szotar/{CPV_KODOK,NUTS_KODOK,ELJARAS_TIPUS,ELJARAS_SZAKASZ} — "
                   "die Referenzvokabulare oeffentlich mitgeliefert. "
                   "⚠ Reichweite des Archivs nicht ausgelotet (Filter steht auf laufend+kuenftig).",
           url="https://ekr.gov.hu/eljarastar/eljarasok"),
    # ── SI, sondiert am 2026-09-03 · Kapitel: docs/sondierung/si.md ───────────────────
    Source("sond-si-enarocanje", "Portal javnih naročil (SI)", "", "SI", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="offen",
           coverage="100,0 % des slowenischen Unterlagen-Felds (6.463 von 6.466); 0,0 % der "
                    "Links ohne Verfahren",
           overlap="✅ DER EINFACHSTE ABRUF DER SONDIERUNG. TED verlinkt nicht die Vergabeseite, "
                   "sondern die DATEI: /api/datoteka/get?id=<base64 von '552686;RD za objavo.zip'>. "
                   "Ein GET, keine Sitzung, kein Zwischenschritt. robots.txt: HTTP 404, 0 Bytes. "
                   "39 von 39 Adressen abgerufen, 150,3 MB, Schnitt 3,9 MB je Datei. "
                   "⚠ DAS PORTAL LAEDT reCAPTCHA — der Dateiendpunkt braucht KEINES (39/39 ohne). "
                   "Ein CAPTCHA auf der Suchmaske heisst nicht, dass der Abruf eines hat; wer dort "
                   "abbricht, traegt ein offenes Land als gesperrt ein. "
                   "⚠ Die Kennung ist eine laufende Nummer und damit ratbar — WIR FOLGEN NUR den "
                   "Adressen, die TED nennt; Durchprobieren waere ein Abgriff jenseits des "
                   "Veroeffentlichten und wurde nicht getan. "
                   "⚠ UMFANG: jede Datei ist ein eigener TED-Link → 6.466 x 3,9 MB ≈ 25 GB/Jahr.",
           url="https://www.enarocanje.si"),
    Source("sond-si-ejn", "e-JN Liste des Innenministeriums (SI)", "", "SI", "ausschreibung",
           "sondiert", portals=1, ebene="bekanntmachung", ertrag="offen",
           coverage="amtliche Liste laufender Vergaben; 70 % der Eintraege sind unterschwellig",
           overlap="✅ VOM MINISTERIUM SELBST HERAUSGEGEBEN (podatki.gov.si nennt sie als offene "
                   "Daten, Stelle: Ministrstvo za notranje zadeve in javno upravo). "
                   "Servergerendert, keine robots-Sperre (404), KEIN CAPTCHA, HTTP 200. Felder: "
                   "Kaeufer, Titel, Aktenzeichen, Verfahrensart, Zeitstempel, JN-Nummer. "
                   "⚠ 31 von 50 sind 'Narocilo male vrednosti' (Kleinauftrag) + 4 'Evidencno "
                   "narocilo' → 70 % erreichen TED NIE. Zentrale unterschwellige Quelle wie in PL, "
                   "nicht zersplittert wie DE. "
                   "⚠ Blaettern (PrimeFaces) und Reichweite der Liste UNGEPRUEFT.",
           url="https://ejn.gov.si"),
    # ── HR, sondiert am 2026-09-03 · Kapitel: docs/sondierung/hr.md ───────────────────
    Source("sond-hr-eojn", "EOJN (HR)", "", "HR", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="99,9 % des kroatischen Unterlagen-Felds (7.946 von 7.955); 100,0 % der "
                    "Links nennen ein Verfahren (2.062 von 2.062, kein einziger Startseiten-Link)",
           overlap="⛔ GESPERRT DURCH EINE EINZELFREIGABE. robots.txt (37 B, byte-genau gelesen): "
                   "'user-agent: * / Allow: /$ / Disallow: /'. Das $ ist eine Endverankerung — "
                   "erlaubt ist GENAU die Wurzel, jede Vergabe (/tender-eo/84749) ist untersagt. "
                   "⚠ Kein Standardartefakt: 'Allow: /$' steht in keiner Software-Vorlage, das hat "
                   "jemand so gemeint (anders als GR-nepps, wo es die Oracle-Beigabe von 2008 war). "
                   "KEIN ERSATZWEG: data.gov.hr hat keine auffindbare Schnittstelle; data.europa.eu "
                   "liefert 194 Treffer, aber nur Tabellen EINZELNER GEMEINDEN; die "
                   "Vorgaengerplattform eojn.nn.hr erlaubt zwar per robots, fuehrt aber zur "
                   "Anmeldung und ist abgeloest. "
                   "⚠ Technisch waere es der beste Fall der Sondierung gewesen — nach Volumen das "
                   "groesste noch offene Ein-Plattform-Land (1,9 % der EU).",
           url="https://eojn.hr"),
    # ── BG, sondiert am 2026-09-03 · Kapitel: docs/sondierung/bg.md ───────────────────
    Source("sond-bg-caiseop", "ЦАИС ЕОП (BG)", "", "BG", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="offen",
           coverage="100,0 % des bulgarischen Unterlagen-Felds (9.135 von 9.137); 100 % der "
                    "Links nennen ein Verfahren; 97 % der Vergaben tragen Dokumente (28 von 29)",
           overlap="✅ DER SAUBERSTE FALL DER SONDIERUNG. robots.txt sagt ausdruecklich "
                   "'User-agent: * / Allow: /' — die erste ERLAUBNIS statt Sperre oder Schweigen. "
                   "Drei anonyme Aufrufe: GetPublishedTenderDetails(tenderId, ianaTimeZone) → "
                   "GetSignedUrlByDocumentId(documentId) → vorsignierte S3-Adresse. "
                   "⚠ Die S3-Adresse gilt nur 30 min (X-Amz-Expires=1800), darf also nicht "
                   "zwischengespeichert werden. "
                   "⚠ Die Schnittstelle liefert MD5Hash UND Size je Dokument — Integritaetspruefung "
                   "frei Haus, sonst nirgends in der Sondierung. Belegt: MD5 stimmte exakt. "
                   "✅ AUFZAEHLBAR OHNE TED: GetPublishedTendersBySpecified → ResultsCount 1.403 "
                   "laufende Vergaben, geblaettert; je Treffer IsEUFunding, IsGreenCriteria und "
                   "AggregateOfferCount (= Zahl der Angebote, sonst nur aus dem Zuschlag). "
                   "⚠ PERSONENDATEN: je Dokument stehen Owner (Klarname), OwnerId, CreatedById und "
                   "PersonalDataConsent in der Antwort — gehoeren NICHT ungefiltert in Bronze. "
                   "⚠ UMFANG: 274,7 MB aus 29 Vergaben = 9,5 MB je Vergabe, grob 85 GB/Jahr. "
                   "⚠ Der erste 500er war ein FEHLENDER PARAMETER (ianaTimeZone), kein Verbot — "
                   "die Signatur steht im Klartext unter /NX1Service.svc/js.",
           url="https://app.eop.bg"),
    # ── IE/MT/CY, sondiert am 2026-09-03 · Kapitel: docs/sondierung/ie.md +
    #    docs/sondierung/european-dynamics.md ──────────────────────────────────────────
    Source("sond-ie-etenders", "eTenders (IE)", "", "IE", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="offen",
           coverage="98,9 % des irischen Unterlagen-Felds (5.845 von 5.912, 12 Monate); "
                    "99 % der Links nennen ein Verfahren — die sauberste Verlinkung der Sondierung",
           overlap="✅ OFFEN, 86 % GEMESSEN (nicht geschaetzt): 38 von 44 Vergaben anonym mit "
                   "Dokumenten (199 Dateien), 6 hinter CAS-Anmeldung. Dieselbe European-Dynamics-"
                   "Kette wie LT: listContractDocuments.do → prepareAnonymousDownload.do → "
                   "downloadContractDocument.do, servergerendert, ohne Browser. "
                   "⚠ Die 14 % Anmeldepflicht sind kein Rauschen — ein Abrufer darf die Umleitung "
                   "nicht als Fehler zaehlen. "
                   "⚠ Die mitgelieferte c4t_*.xml traegt die WERTUNGSSTRUKTUR typisiert "
                   "(procedure, eval-type, Lose, Kriterienbaum) — Zuschlagskriterien geschenkt. "
                   "Unterschwellig liegt auf DERSELBEN Plattform (Suchfilter 'Threshold: Below'), "
                   "2.931 laufende Vergaben oeffentlich. ⚠ Blaettern ungeloest: d-*-p=N liefert "
                   "bei 1, 2 und 5 dieselben zehn Kennungen.",
           url="https://www.etenders.gov.ie"),
    Source("sond-mt-etenders", "eTenders (MT)", "", "MT", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="offen",
           coverage="145 Nennungen im letzten Monat; in KEINEM frueheren Kapitel vorgekommen",
           overlap="✅ OFFEN, 7 von 7 anonym (64 Dateien, 0 Anmeldungen), keine robots.txt. "
                   "Dieselbe European-Dynamics-Kette wie LT und IE — GEFUNDEN, indem nach der "
                   "SOFTWARE statt nach dem Land gesucht wurde. "
                   "⚠ Lieferte eine 'Clarification Note 4.pdf' = Bieterfragen-Dokument, auf "
                   "Englisch (einfacher zu erkennen als das portugiesische 'Resposta Erros e "
                   "Omissoes'). ⚠ Stichprobe nur 7 — IE zeigte seine 14 % Anmeldepflicht erst "
                   "bei 44. Unterschwellige Ebene ungeprueft.",
           url="https://www.etenders.gov.mt"),
    Source("sond-cy-eprocurement", "eProcurement (CY)", "", "CY", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="offen",
           coverage="104 Nennungen im letzten Monat; in KEINEM frueheren Kapitel vorgekommen",
           overlap="✅ OFFEN, 7 von 7 anonym (46 Dateien, 0 Anmeldungen), keine robots.txt. "
                   "Dieselbe European-Dynamics-Kette. "
                   "⚠ ZEICHENSATZ-FALLE: der Dateiname kam als '------ 11 ---------- R2.docx' an "
                   "— griechischer Text, zerschossen in der Content-Disposition-KOPFZEILE (nicht "
                   "im Inhalt). Gleiche Stelle wie Łódź → ['d'] und die griechischen Kennungen. "
                   "Wer Dateien unter dem gemeldeten Namen ablegt, verliert die Bezeichnung. "
                   "⚠ Stichprobe nur 7. Unterschwellige Ebene ungeprueft.",
           url="https://www.eprocurement.gov.cy"),
    # ── GR, sondiert am 2026-09-03 · Kapitel: docs/sondierung/gr.md ───────────────────
    Source("sond-gr-esidis", "ΕΣΗΔΗΣ/Promitheus (GR)", "", "GR", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="teilweise",
           coverage="ΕΣΗΔΗΣ stellt 89,3 % des GR-Unterlagen-Felds, ABER nur nepps-search "
                    "(32,2 %, davon 97 % tief) verlinkt wirklich Verfahren",
           overlap="🟡 BEDINGT OFFEN. Ausschreibung + Dokumentenliste anonym sichtbar (Reiter "
                   "'Συννημένα Αρχεία': DIAKIRYXI, Zusammenfassung, ESPD als PDF und XML), kein "
                   "Login, kein CAPTCHA, keine robots.txt (404). ⚠ Aber der Download ist ein "
                   "Oracle-ADF-POST mit javax.faces.ViewState, kein GET — curl bekommt nur eine "
                   "JS-Huelle. DRITTE Plattform dieser Bauform nach eis.gov.lv (LV) und AnoGov "
                   "(PT): EIN sitzungsfuehrender Abrufer loest drei Laender. "
                   "⚠ PageNotFound.jspx kommt mit HTTP 200 — Titel pruefen, nicht den Code. "
                   "⚠ Kennungen sind griechische Grossbuchstaben (9Μ3ΘΩΞ2-8Λ9), nicht lateinisch.",
           url="https://nepps-search.eprocurement.gov.gr"),
    Source("sond-gr-esidis-nepps", "ΕΣΗΔΗΣ nepps + publicworks (GR)", "", "GR", "beides",
           "sondiert", portals=2, ebene="unterlagen", ertrag="gesperrt",
           coverage="14,4 % der Nennungen — aber zu 99 % Startseiten-Links (nepps: 163 von 165), "
                    "also fast wertlos",
           overlap="⛔ GESPERRT: 'User-agent: * / Disallow: /'. ⚠ Es ist die STANDARDDATEI der "
                   "Oracle E-Business Suite ('managed automatically … AutoConfig', Kopfzeile von "
                   "2008) — die Sperre ist vermutlich keine Entscheidung des Betreibers, sondern "
                   "eine Beigabe der Software; andere Namen desselben Systems haben gar keine "
                   "robots.txt. Das aendert NICHTS: 'die haben das nicht so gemeint' ist dieselbe "
                   "Umgehungslogik wie sich ClaudeBot zu nennen (s. sond-sk-uvo).",
           url="https://nepps.eprocurement.gov.gr"),
    Source("sond-gr-diavgeia", "Διαύγεια (GR, Transparenzportal)", "", "GR", "ausschreibung",
           "sondiert", portals=1, ebene="bekanntmachung", ertrag="teilweise",
           coverage="/opendata/search filterbar: type=Δ.2.1 → 17.602 Vorgaenge",
           overlap="🟡 METADATEN OFFEN, DATEIEN GESPERRT. robots (120 B, vollstaendig gelesen) "
                   "sperrt /doc/*, /decision/view, /luminapi/api/decisions/*, /f/all/ada/*. "
                   "⚠ Die ERLAUBTE Schnittstelle /opendata/decisions/<ADA> gibt als documentUrl "
                   "genau den gesperrten /doc/-Pfad heraus — ein arglos gebauter Abrufer laeuft "
                   "direkt hinein. Nicht abgerufen. "
                   "⚠ FALLE: ein falscher Parametername wird STILL ignoriert. decisionType= statt "
                   "type= gibt total 2.972.077 statt 17.602 zurueck, ohne Fehler und ohne Hinweis.",
           url="https://diavgeia.gov.gr"),
    Source("sond-gr-kimdis", "ΚΗΜΔΗΣ (GR, unterschwellig)", "", "GR", "ausschreibung",
           "sondiert", portals=1, ebene="bekanntmachung", ertrag="gesperrt",
           coverage="zentrales Register oeffentlicher Auftraege; Umfang nicht messbar",
           overlap="⛔ ANMELDUNG. cerpp.eprocurement.gov.gr liefert schon unter /robots.txt ein "
                   "Login-Formular (POST an access.eprocurement.gov.gr/oam/…, Oracle Access "
                   "Manager). Kein Konto, keine Zugangsdaten — stehende Regel.",
           url="https://cerpp.eprocurement.gov.gr"),
    # ── PT, sondiert am 2026-09-03 · Kapitel: docs/sondierung/pt.md ───────────────────
    Source("sond-pt-acingov", "AcinGov (PT)", "", "PT", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="offen",
           coverage="40,2 % des portugiesischen Unterlagen-Felds (3.791 von 9.435, 12 Monate)",
           overlap="✅ OFFEN, der einfachste Fall der Sondierung: TED verlinkt die Datei direkt, "
                   "ein GET liefert das ZIP (3 von 3 geprueft, 1,9/2,1/0,65 MB, echte Caderno de "
                   "Encargos + Programa Concurso). robots.txt 34 Bytes, sperrt NUR MJ12bot. "
                   "⚠ Der Tippfehler 'donwloadProcedurePiece' steht so beim Betreiber. "
                   "⚠ Erster Abruf gab 403 — das war der curl-Standardkopf, nicht die Tuer; mit "
                   "eigener Kennung sofort 200.",
           url="https://www.acingov.pt"),
    Source("sond-pt-vortal", "Vortal Community (PT, ES, AD)", "", "PT", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="offen",
           coverage="48,6 % des portugiesischen Unterlagen-Felds (4.585 von 9.435, 12 Monate); "
                    "Heimatmarkt PT, dazu ES und Andorra",
           overlap="✅ OFFEN ueber eine DREISTUFIGE Kette, aber hinter der falschen ersten Tuer: "
                   "GetPublicTenderInformation gibt bei 10 von 10 Vergaben documentList=[] trotz "
                   "tenderIsPublished=true. Der Weg geht ueber contractNoticeUrl → "
                   "GetContractNoticeDocuments?contractNoticeUId=PT1.NTC.* → PublicDownload?token=. "
                   "9 von 9 Vergaben, 90 Dateien; ein PDF vollstaendig (49 Seiten, 1,03 MB). "
                   "⚠ languageCode MUSS gefuellt sein, leer gibt 500 (wie in EE). "
                   "⚠ robots.txt gibt 403 — auch im echten Browser, fuer niemanden abrufbar. RFC "
                   "9309 liest 4xx als 'keine Beschraenkung', und der Betreiber nennt die Route "
                   "dreimal 'public' (PublicTenderDocuments/PublicDownload). Einschaetzung, keine "
                   "Messung — vor einem Anschluss klaeren. "
                   "🎁 Nebenfund: POST /api/Tendering/SearchTenders liefert anonym 220.826 Vergaben "
                   "inkl. UNTERSCHWELLIGER ('sem Publicacao no JOUE') und Andorra, das kein TED-Land ist.",
           url="https://community.vortal.biz"),
    Source("sond-pt-anogov", "AnoGov / compraspt (PT)", "", "PT", "beides",
           "sondiert", portals=2, ebene="unterlagen", ertrag="teilweise",
           coverage="9,3 % des portugiesischen Unterlagen-Felds; beide fahren dieselbe Software "
                    "(/faces/app/acessoDocs.jsp?codigoAcesso=)",
           overlap="🟡 Liste OFFEN ohne Anmeldung (Seitentitel 'List of Documents', kein Passwort"
                   "feld, 7 echte Dateien inkl. DEUCP.zip = ESPD), aber der Download laeuft ueber "
                   "ein JSF-Formular mit jsessionid statt per GET. Gleiche Bauform wie eis.gov.lv "
                   "(Modal per POST) — wer eines loest, loest vermutlich beide.",
           url="https://www.anogov.com"),
    Source("sond-pt-base", "Portal BASE (PT, unterschwellig)", "", "PT", "ausschreibung",
           "sondiert", portals=1, ebene="bekanntmachung", ertrag="ungeprueft",
           coverage="nationales Pflichtportal; Umfang nicht gemessen",
           overlap="⚪ UNGEPRUEFT, NICHT GESPERRT. Keine robots-Sperre (404), aber jeder Aufruf "
                   "jenseits der Startseite gab HTTP 999 mit WebKnight-Firewall-Meldung. Das ist "
                   "ein Filter, kein Verbot — nicht weiter beklopft, bis geklaert ist, was ihn "
                   "ausloest. ⚠ Vortals SearchTenders fuehrt bereits unterschwellige Verfahren; "
                   "ob das BASE ersetzt oder nur ueberlappt, ist offen.",
           url="https://www.base.gov.pt"),
    # ── SK, sondiert am 2026-09-03 · Kapitel: docs/sondierung/sk.md ───────────────────
    Source("sond-sk-uvo", "ÚVO (uvo.gov.sk)", "", "SK", "beides",
           "sondiert", portals=1, ebene="unterlagen", ertrag="gesperrt",
           coverage="95,8 % des slowakischen Unterlagen-Felds (4.383 von 4.577, 12 Monate) — "
                    "nach dem Baltikum der konzentrierteste Markt, mit tiefen Adressen "
                    "(/vyhladavanie-zakaziek/dokumenty/<id>)",
           overlap="⛔ GESPERRT DURCH EINE FREIGABELISTE, nicht durch eine Pfadsperre. Die "
                   "robots.txt nennt Googlebot, bingbot, Applebot, GPTBot, ClaudeBot, "
                   "PerplexityBot u. a. mit Crawl-delay und `Disallow: /private/` — und "
                   "schliesst mit `User-agent: * / Disallow: /`. Wer nicht genannt ist, ist "
                   "ganz gesperrt. ⚠ Dass ClaudeBot dort steht, ist KEIN Freibrief: das ist "
                   "der Suchindex-Crawler, nicht dieses Werkzeug; sich seinen Namen zu geben "
                   "waere eine Falschangabe. ⚠ Meine Vermutung „SK ist ein ProeBiz-Land\" war "
                   "falsch — ProeBiz ist dort der ABGABEORT (1.099), nicht die Unterlagen"
                   "quelle (124).",
           url="https://www.uvo.gov.sk"),
    # ── ANGEBUNDEN ────────────────────────────────────────────────────────────────────
    Source("doc-cosinex-de", "cosinex/DTVP-Unterlagen", "docfetch-cosinex", "DE", "beides",
           "live", portals=40, ebene="unterlagen", ertrag="dateien", modul="govisor.docfetch",
           coverage="3.921 offene Leads mit Link, 2.457 mit Unterlagen im Bestand (63 %) — Stand 15.08.",
           overlap="grösste DE-Familie; deckt dtvp.de + die VMP-Satelliten der Länder",
           url="https://www.dtvp.de"),
    Source("doc-rib-de", "RIB »meinauftrag«-Unterlagen", "docfetch-rib", "DE", "beides",
           "live", portals=1, ebene="unterlagen", ertrag="dateien", modul="govisor.docfetch_rib",
           coverage="793 Leads, 697 im Bestand (88 %) — die höchste Ausbeute aller Abrufer",
           overlap="", url="https://www.meinauftrag.rib.de"),
    Source("doc-netserver-de", "NetServer-Unterlagen", "docfetch-netserver", "DE", "beides",
           "live", portals=33, ebene="unterlagen", ertrag="dateien",
           modul="govisor.docfetch_netserver",
           coverage="1.696 Leads, 17 im Bestand (1 %) — grosse Pakete (10–65 MB, Ausreisser 335 MB), "
                    "der Rückstand ist Durchsatz, nicht Zugang",
           overlap="⚠ Hostliste allein greift zu kurz: erkannt wird über Pfad + Servlet + Liste",
           url="https://vergabe.bremen.de/NetServer/"),
    Source("doc-evgo-de", "e-Vergabe des Bundes — Unterlagen", "docfetch-evgo", "DE", "beides",
           "live", portals=1, ebene="unterlagen", ertrag="dateien",
           modul="govisor.docfetch_evergabe_online",
           # ⚠ Stand bis 2026-08-29 „prepared, noch kein regulärer Lauf". Gemessen am
           # Manifest: 1.287 Archive geholt, täglich 35–47 Versuche, im Tageslauf verdrahtet.
           # Der Eintrag beschrieb den Bauzustand, nicht den Betrieb — und niemand las ihn
           # nach, weil er plausibel klang.
           coverage="1.352 Versuche, 1.287 Archive (95 %), läuft täglich mit. Download frei "
                    "und ausdrücklich angeboten (»uneingeschränkter … Zugang gebührenfrei«)",
           overlap="⚠ /xvergabe/services/ existiert laut robots.txt, ist dort aber für "
                   "automatische Zugriffe gesperrt — wir sprechen es NICHT an",
           url="https://www.evergabe-online.de"),
    Source("doc-evergabe-de", "evergabe.de-Unterlagen", "docfetch-evergabe", "DE", "beides",
           "live", portals=1, ebene="unterlagen", ertrag="dateien",
           modul="govisor.docfetch_evergabe",
           coverage="890 Leads, 27 im Bestand (3 %)",
           overlap="WAF drosselt nach ~10 Vorgängen → 7 min Abkühlung, Rest über die Tage",
           url="https://www.evergabe.de"),
    Source("doc-healy-de", "Healy-Hudson-Unterlagen", "docfetch-healyhudson", "DE", "beides",
           "live", portals=5, ebene="unterlagen", ertrag="dateien",
           modul="govisor.docfetch_healyhudson",
           coverage="530 Leads, 3 im Bestand — ⚠ pro Instanz verschieden: Bahn und Hamburg "
                    "liefern, bieterzugang.deutsche-evergabe.de leitet aufs Dashboard um",
           overlap="302 weitere Leads auf www.deutsche-evergabe.de tragen eine Dashboard-URL "
                   "ohne Deeplink — gemessen 5 von 5 ohne Dateien, kein Abrufer möglich",
           url="https://www.deutsche-evergabe.de"),
    Source("doc-aumass-de", "aumass-Unterlagen", "docfetch-aumass", "DE", "beides", "live",
           portals=1, ebene="unterlagen", ertrag="dateien", modul="govisor.docfetch_aumass",
           coverage="292 Leads, 9 im Bestand. Link heisst wörtlich »Ohne Registrierung herunterladen.«",
           overlap="⚠ die aumass-ID muss GROSS geschrieben werden, sonst 404",
           url="https://plattform.aumass.de"),
    Source("doc-staatsanz-de", "Staatsanzeiger-Unterlagen", "docfetch-staatsanz", "DE", "beides",
           "live", portals=2, ebene="unterlagen", ertrag="dateien",
           modul="govisor.docfetch_staatsanzeiger",
           coverage="218 Leads, 12 im Bestand. Dreistufig; »Anonym als Zip« ist ein "
                    "input[type=submit], das NAVIGIERT (kein expect_download)",
           overlap="56 Leads liegen als BekLanding4Bund im Frameset → Status `frameset`",
           url="https://www.staatsanzeiger-eservices.de"),
    Source("doc-dab-de", "Ausschreibungsblatt-Unterlagen", "docfetch-dab", "DE", "beides",
           "live", portals=1, ebene="unterlagen", ertrag="dateien",
           modul="govisor.docfetch_ausschreibungsblatt",
           coverage="172 Leads, erste 6 geholt (6 von 6). Die Bezahlschranke der Seite gilt der "
                    "RECHERCHE, nicht den Unterlagen — der Tarif-Knopf ist im DOM unsichtbar",
           overlap="⚠ getZip trägt keine Kennung, nur Sitzungszustand → frischer Browser-"
                   "Kontext JE Vergabe, sonst kommen die Unterlagen der vorigen",
           url="https://www.deutsches-ausschreibungsblatt.de"),
    Source("doc-bimedien-de", "bi-medien-Unterlagen", "docfetch-bimedien", "DE", "beides",
           "live", portals=1, ebene="unterlagen", ertrag="dateien",
           modul="govisor.docfetch_bimedien",
           coverage="110 Leads, erste 6 geholt (6 von 6), Sammel-ZIP je Vergabe",
           overlap="⚠ Links stehen zugeklappt im DOM — auslesen, nicht klicken (Klick = Timeout)",
           url="https://bi-medien.de"),

    # --- Luxemburg: der einzige Abrufer gegen eine VERGAENGLICHE Quelle -------------------
    # ⚠ Anders gebaut als die zwoelf deutschen: die Warteschlange kommt aus der
    # TED-SUCHSCHNITTSTELLE, nicht aus data/gold — fuer LU gibt es kein Gold, und die
    # TED-Monatspakete liegen bis zu vier Wochen zurueck, waehrend LU die Unterlagen nach
    # Fristende entfernt. Sortiert nach FRIST aufsteigend: die naechste Frist ist der
    # naechste Verlust. Belegt 2026-09-03: 3 von 3, echte Cahiers des charges.
    Source("doc-lu-pmp", "Portail des marchés publics (LU) — Unterlagen", "docfetch-lu", "LU",
           "beides", "live", portals=1, ebene="unterlagen", ertrag="dateien",
           modul="govisor.docfetch_lu",
           coverage="80 Vergaben mit laufender Frist (2026-09-03); Median 6,9 MB, Mittel "
                    "90,8 MB, groesste gemessene 614 MB",
           overlap="⏳ VERGAENGLICH — nach Fristende sind die Unterlagen weg (belegt: 30 von 30 "
                   "aelteren Vergaben melden 'Aucune piece jointe'). Was hier nicht geholt "
                   "wird, ist dauerhaft verloren; Verlustrate rund 135 Vergaben im Monat. "
                   "⚠ KEINE Groessenschwelle als Vorgabe (GOVISOR_LU_MAX_MB=0): eine Schwelle "
                   "waere hier ein dauerhafter Verzicht, und die grossen Pakete sind die "
                   "Bauvorhaben mit Planunterlagen. Zwei anonyme Formularschritte "
                   "(choixAnonyme → completeDownload), PRADO-Zustand ~11.800 Zeichen. "
                   "⚠ ZIP-Namen mit verstuemmelten Umlauten.",
           url="https://pmp.b2g.etat.lu"),

    # --- Nur Dateiliste: liefert Erkenntnis, aber keine Datei -----------------------------
    Source("doc-subreport-de", "subreport ELViS — Dateiliste", "docliste-subreport", "DE",
           "beides", "live", portals=1, ebene="unterlagen", ertrag="liste",
           modul="govisor.subreport",
           coverage="985 Leads. Dateinamen/Grössen sichtbar, Dateien hinter Anmeldung",
           overlap="beantwortet »gibt es ein Leistungsverzeichnis, welche Nachweise« — "
                   "der Inhalt fehlt",
           url="https://www.subreport.de"),
    Source("doc-vergabeportal-at", "vergabeportal.at — Dateiliste", "docliste-vergabeportal-at",
           "AT", "beides", "live", portals=10, ebene="unterlagen", ertrag="liste",
           modul="govisor.vergabeportal_at",
           coverage="353 Leads (inkl. wien.gv.at — dieselbe Software). Name, Grösse, Erstell- "
                    "und Änderungsdatum, Hash je Datei",
           overlap="⚠ Dateien durch hCaptcha geschützt. Der anonyme Download ist ausdrücklich "
                   "angeboten, aber botgesichert — wird NICHT umgangen",
           url="https://gv.vergabeportal.at"),

    # --- Gebaut, Zugang an eine Entscheidung gebunden -------------------------------------
    Source("doc-simap-ch", "simap.ch-Unterlagen", "docfetch-simap", "CH", "beides", "prepared",
           portals=27, ebene="unterlagen", ertrag="gesperrt", modul="govisor.simap_docs",
           coverage="886 Leads. Einzige offizielle Unterlagen-API im Feld; OIDC+PKCE läuft, "
                    "Token wird erteilt. Öffentlich abrufbar ist immerhin, OB Unterlagen "
                    "existieren (791 von 928, 92 % treffsicher)",
           overlap="⚠ /documents antwortet 403 ohne Firmenregistrierung UND namentliche "
                   "Interessensbekundung je Vergabe — beim Auftraggeber sichtbar. "
                   "Standardmässig AUS (--interesse-bekunden), offene Geschäftsentscheidung",
           url="https://www.simap.ch"),
]

# ── EBENE 3: FONDS ────────────────────────────────────────────────────────────────────────
#
# ⚠ EIGENE LISTE, nicht in DOC_REGISTRY. Als die beiden ersten Eintraege dort landeten,
# fiel `test_registry_addiert_die_beiden_ebenen_nicht` — zu Recht: DOC_REGISTRY ist die
# Liste der DOKUMENT-ABRUFER, und ein Fonds-Register ist keiner. Derselbe Gedanke wie im
# Docstring oben: Ebenen werden nicht vermischt, damit keine Zahl entsteht, die mehr
# Abdeckung behauptet, als da ist.
FONDS_REGISTRY: list[Source] = [
    # ── FONDS-EBENE, sondiert am 2026-09-03 · Kapitel: docs/sondierung/fonds-ebene.md ──
    # ⚠ DIE DRITTE EBENE aus CLAUDE.md: Vergaben von Empfaengern oeffentlicher Foerdermittel,
    # die selbst KEINE oeffentlichen Auftraggeber sind. Sie fehlte in allen zwoelf
    # Laenderkapiteln — hier nachgearbeitet.
    Source("sond-cz-fonds", "OPPIK/OPTAK/NPO-Register (zakazky.agentura-api.org)", "", "CZ",
           "unterschwellig", "sondiert", portals=1, ebene="fonds", ertrag="",
           coverage="8.663 Vergaben von Foerdermittelempfaengern — private Firmen als "
                    "Auftraggeber. Zum Vergleich: CZ hatte im Juni 1.621 TED-Ausschreibungen.",
           overlap="✅ OEFFENTLICH UND MASCHINENLESBAR. Keine robots.txt. POST /nacist_verejny "
                   "(DataTables) liefert anonym recordsTotal 8.663 mit Auftraggeber, IČ, Titel, "
                   "Art, Frist, Veroeffentlichung und geschaetztem Wert. Der Betreiber bietet "
                   "Excel- und PDF-Export selbst an. ⚠ Ob dort auch UNTERLAGEN haengen, ist "
                   "ungeprueft. ⚠ Bauart beachten: das Register gehoert einem Programmtraeger, "
                   "nicht dem Land — andere Operationelle Programme koennen eigene fuehren.",
           url="https://zakazky.agentura-api.org"),
    Source("sond-pl-fonds", "Baza Konkurencyjności", "", "PL", "unterschwellig",
           "sondiert", portals=1, ebene="fonds", ertrag="",
           coverage="Fonds-Ebene Polens, in CLAUDE.md namentlich genannt",
           overlap="🟡 Keine robots-Sperre, API-Basis /api/ belegt (cookies, statements, "
                   "general-content antworten 200). Aber /api/announcements gibt anonym "
                   "HTTP 401. Ob die Weboberflaeche ohne Anmeldung etwas zeigt, ist offen.",
           url="https://bazakonkurencyjnosci.funduszeeuropejskie.gov.pl"),
]

REGISTRY += DOC_REGISTRY
REGISTRY += FONDS_REGISTRY


# ------------------------------------------------------------------------------------------
# Kennzahlen fürs Marketing/Produkt — ehrlich getrennt.
# ------------------------------------------------------------------------------------------
def bekanntmachungen() -> list[Source]:
    """Nur Ebene 1. Jede Kennzahl über »Quellen« meint diese — Unterlagen sind etwas anderes."""
    return [s for s in REGISTRY if s.ebene == "bekanntmachung"]


def unterlagen() -> list[Source]:
    """Nur Ebene 2 (Dokument-Abrufer)."""
    return [s for s in REGISTRY if s.ebene == "unterlagen"]


def fonds() -> list[Source]:
    """Nur Ebene 3: Vergaben von Foerdermittelempfaengern ohne Auftraggeber-Eigenschaft.

    ⚠ Wird NIE zu `bekanntmachungen()` addiert. Es ist ein anderer Markt mit anderen
    Auftraggebern (private Firmen), nicht mehr Abdeckung desselben.
    """
    return [s for s in REGISTRY if s.ebene == "fonds"]


def summary() -> dict:
    """⚠ Die Ebenen werden NICHT addiert. `quellen_*` zählt Bekanntmachungs-Quellen — die
    Dokument-Abrufer stehen getrennt unter `unterlagen_*`. Sie zusammenzuwerfen hiesse, aus
    8 Connectoren 21 zu machen, ohne dass eine Bekanntmachung mehr hereinkäme; genau die
    Vanity-Metrik, gegen die dieses Modul geschrieben ist."""
    bm = bekanntmachungen()
    live = [s for s in bm if s.status == "live"]
    ul = unterlagen()
    return {
        "connectors": len(CONNECTORS),                         # technische Basen (Pflegeaufwand)
        "quellen_total": len(bm),                              # Connector × Land × Tier
        "quellen_live": len(live),
        "by_status": {st: sum(1 for s in bm if s.status == st) for st in STATUSES},
        "herkunfts_portale_live": sum(s.portals for s in live),  # aggregierte Breite (belegbar)
        "laender_live": sorted({s.country for s in live}),
        # --- Ebene 2, bewusst eigene Schlüssel ---
        "unterlagen_connectors": len(DOC_CONNECTORS),
        "unterlagen_total": len(ul),
        "unterlagen_live": sum(1 for s in ul if s.status == "live"),
        "unterlagen_nach_ertrag": {e: sum(1 for s in ul if s.ertrag == e) for e in ERTRAEGE},
        # --- Ebene 3, wieder eigene Schluessel: anderer Markt, nicht mehr vom selben ---
        "fonds_total": len(fonds()),
        "fonds_laender": sorted({s.country for s in fonds()}),
        "unterlagen_laender": sorted({s.country for s in ul}),
    }


def dach_matrix() -> list[tuple]:
    """DACH-Abdeckung als Matrix (Land × Schwelle) → beste Quelle + Status. Fürs 100%-DACH-Ziel:
    zeigt, was live/prepared ist und wo die bewusste Restlücke bleibt."""
    def best(country, tier):
        # relevante Quellen: exakter Tier oder "beides". ⚠ NUR Ebene 1 — sonst gewänne hier
        # ein Dokument-Abrufer die Zeile »AT unterschwellig«, obwohl er keine einzige
        # Bekanntmachung liefert.
        cand = [s for s in bekanntmachungen() if s.country == country
                and (s.tier == tier or s.tier == "beides")]
        if not cand:
            return ("—", "fehlt")
        order = {st: i for i, st in enumerate(STATUSES)}
        s = min(cand, key=lambda x: order[x.status])
        return (s.name, s.status)
    rows = []
    for cc in ("DE", "AT", "CH"):
        for tier in ("oberschwellig", "unterschwellig"):
            name, status = best(cc, tier)
            rows.append((cc, tier, name, status))
    return rows


def unterlagen_matrix() -> list[tuple]:
    """DACH-Abdeckung auf der UNTERLAGEN-Ebene: Land → was wir dort tatsächlich bekommen.

    Die Gegenfrage zu `dach_matrix()`. Bei den Bekanntmachungen ist DACH gelöst; hier trennt
    sich, wo wir Dateien holen, wo nur Dateilisten, und wo gar nichts.
    """
    rows = []
    for cc in ("DE", "AT", "CH"):
        ul = [s for s in unterlagen() if s.country == cc]
        for e in ERTRAEGE:
            treffer = [s for s in ul if s.ertrag == e]
            if treffer:
                rows.append((cc, e, len(treffer), ", ".join(s.name for s in treffer)))
        if not ul:
            rows.append((cc, "—", 0, "kein Abrufer"))
    return rows


def by_country(country: str) -> list[Source]:
    return [s for s in REGISTRY if s.country == country.upper()]


def by_status(status: str) -> list[Source]:
    return [s for s in REGISTRY if s.status == status]


def format_overview() -> str:
    """Menschlesbarer Überblick für die `sources`-CLI."""
    s = summary()
    lines = [
        "goVisor Quellen-Registry",
        "=" * 60,
        f"Connector (technische Basen) : {s['connectors']}  ({', '.join(CONNECTORS)})",
        f"Quellen gesamt               : {s['quellen_total']}  "
        f"(live {s['by_status']['live']}, prepared {s['by_status']['prepared']}, "
        f"candidate {s['by_status']['candidate']}, research {s['by_status']['research']})",
        f"Herkunfts-Portale (live)     : ~{s['herkunfts_portale_live']}  "
        f"(aggregierte Breite hinter den {s['quellen_live']} Live-Quellen)",
        f"Live-Länder                  : {', '.join(s['laender_live'])}",
        "",
        f"{'Quelle':<38}{'Connector':<12}{'Land':<5}{'Tier':<15}Status",
        "-" * 78,
    ]
    order = {st: i for i, st in enumerate(STATUSES)}
    for src in sorted(bekanntmachungen(), key=lambda x: (order[x.status], x.country)):
        lines.append(f"{src.name:<38}{src.connector:<14}{src.country:<5}{src.tier:<15}{src.status}")
    # DACH-Abdeckungsmatrix (das 100%-Ziel)
    lines += ["", "DACH-Abdeckung (Land × Schwelle → beste Quelle):", "-" * 78]
    for cc, tier, name, status in dach_matrix():
        mark = {"live": "✅", "prepared": "🟡", "candidate": "🟠", "research": "⚪", "fehlt": "❌"}.get(status, "")
        lines.append(f"  {cc}  {tier:<15} {mark} {name}  [{status}]")

    # --- EBENE 2 -----------------------------------------------------------------------
    lines += [
        "", "=" * 60,
        f"EBENE 2 — Vergabeunterlagen  ({s['unterlagen_connectors']} Abrufer, "
        f"{s['unterlagen_live']} von {s['unterlagen_total']} im Tageslauf)",
        "=" * 60,
        f"{'Abrufer':<38}{'Land':<5}{'Ertrag':<13}{'Status':<11}Modul",
        "-" * 78,
    ]
    zeichen = {"dateien": "📄", "liste": "📋", "gesperrt": "🔒"}
    for src in sorted(unterlagen(), key=lambda x: (x.country, order[x.status], x.name)):
        lines.append(f"{src.name:<38}{src.country:<5}"
                     f"{zeichen.get(src.ertrag,'') + ' ' + src.ertrag:<13}"
                     f"{src.status:<11}{src.modul}")
    lines += ["", "Was jedes Land auf der Unterlagen-Ebene liefert:", "-" * 78]
    for cc, ertrag, n, namen in unterlagen_matrix():
        lines.append(f"  {cc}  {zeichen.get(ertrag,' ')} {ertrag:<10} {n:>2}  {namen[:52]}")
    lines += ["",
              "⚠ Die beiden Ebenen werden bewusst nicht addiert: ein Dokument-Abrufer bringt",
              "  keine Bekanntmachung, und eine Quelle bringt keine Unterlagen."]
    return "\n".join(lines)
