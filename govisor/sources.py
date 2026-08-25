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
    "docliste-subreport":  "subreport ELViS — NUR Dateiliste, Dateien hinter Anmeldung",
    "docliste-vergabeportal-at": "vergabeportal.at-Familie — NUR Dateiliste, hCaptcha vor den Dateien",
    "docfetch-simap":      "simap.ch — offizielle API (OIDC+PKCE), Unterlagen hinter Firma + Interessensbekundung",
}

# Was ein Abrufer tatsächlich einbringt — die Achse, auf die es beim Produkt ankommt.
#   dateien   = echte Vergabeunterlagen im Bestand
#   liste     = nur Dateinamen/Grössen/Daten (beantwortet »gibt es ein LV«, ohne eine Datei)
#   gesperrt  = gebaut, Zugang aber verweigert oder an eine Entscheidung gebunden
ERTRAEGE = ("dateien", "liste", "gesperrt")

# --- Status einer Quelle ---------------------------------------------------------------------
#   live      = ingestet, im Produkt sichtbar
#   prepared  = Code/Brücke fertig, wartet nur auf den Voll-Ingest (z. B. Speicher)
#   candidate = identifiziert, gleiche technische Basis, noch kein Ingest-Lauf
#   research  = Quelle existiert, technische Basis noch zu klären (eigener Spike)
STATUSES = ("live", "prepared", "candidate", "research")


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
    ebene: str = "bekanntmachung"   # "bekanntmachung" | "unterlagen"
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
           "unterschwellig", "prepared", portals=1,
           coverage="Connector gebaut (govisor/atverg.py: download+build_silver, Mapping gemessen an "
                    "236k Records); BVergG2018-Open-Data >50k €, tägl. CSV-Bulk ~34 MB. Wartet auf Voll-Ingest",
           overlap="füllt die AT-Lücke unter der EU-Schwelle; OSB-Anteil (~36%) überlappt TED-AT → "
                   "Gold-Filter via attributes.atverg/schwelle",
           url="https://offenevergaben.at/downloads/kerndaten_dump_daily?format=csv"),

    # --- RESEARCH (bewusster Rest / niederwertig / fragmentiert) ---
    # CH freihändig + Einladungsverfahren UNTER den CHF-Schwellen erscheinen oft NICHT auf simap;
    # einige Kantone betreiben Eigenportale. Niederwertig (Direktvergabe, kein Wettbewerb → kaum
    # Lead-Wert) und auf ~26 Kantonsportale fragmentiert. Nur bei konkretem Kundenbedarf gezielt.
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
           portals=1, coverage="Données Essentielles Commande Publique, konsolidiert Parquet/CSV, tägl.",
           overlap="ergänzt TED-FR nach unten (données essentielles, Pflicht seit 2019)",
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
           "prepared", portals=1, ebene="unterlagen", ertrag="dateien",
           modul="govisor.docfetch_evergabe_online",
           coverage="1.033 Leads, noch kein regulärer Lauf. Download frei und ausdrücklich "
                    "angeboten (»uneingeschränkter … Zugang gebührenfrei«), 30 von 30 mit ZIP",
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

REGISTRY += DOC_REGISTRY


# ------------------------------------------------------------------------------------------
# Kennzahlen fürs Marketing/Produkt — ehrlich getrennt.
# ------------------------------------------------------------------------------------------
def bekanntmachungen() -> list[Source]:
    """Nur Ebene 1. Jede Kennzahl über »Quellen« meint diese — Unterlagen sind etwas anderes."""
    return [s for s in REGISTRY if s.ebene == "bekanntmachung"]


def unterlagen() -> list[Source]:
    """Nur Ebene 2 (Dokument-Abrufer)."""
    return [s for s in REGISTRY if s.ebene == "unterlagen"]


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
