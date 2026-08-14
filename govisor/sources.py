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

from dataclasses import dataclass, field

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


def _ted_candidates() -> list[Source]:
    out = []
    for cc, name in _TED_EU.items():
        out.append(Source(
            id=f"ted-{cc.lower()}", name=f"TED {name}", connector="ted-bulk",
            country=cc, tier="oberschwellig", status="candidate",
            coverage="EU-pflichtige Vergaben; gleiche eForms/Legacy-Pipeline wie DE/AT",
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

# TED-EU-Breite anhängen (candidate).
REGISTRY += _ted_candidates()


# ------------------------------------------------------------------------------------------
# Kennzahlen fürs Marketing/Produkt — ehrlich getrennt.
# ------------------------------------------------------------------------------------------
def summary() -> dict:
    live = [s for s in REGISTRY if s.status == "live"]
    by_status = {st: sum(1 for s in REGISTRY if s.status == st) for st in STATUSES}
    return {
        "connectors": len(CONNECTORS),                         # technische Basen (Pflegeaufwand)
        "quellen_total": len(REGISTRY),                        # Connector × Land × Tier
        "quellen_live": len(live),
        "by_status": by_status,
        "herkunfts_portale_live": sum(s.portals for s in live),  # aggregierte Breite (belegbar)
        "laender_live": sorted({s.country for s in live}),
    }


def dach_matrix() -> list[tuple]:
    """DACH-Abdeckung als Matrix (Land × Schwelle) → beste Quelle + Status. Fürs 100%-DACH-Ziel:
    zeigt, was live/prepared ist und wo die bewusste Restlücke bleibt."""
    def best(country, tier):
        # relevante Quellen: exakter Tier oder "beides"
        cand = [s for s in REGISTRY if s.country == country
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
    for src in sorted(REGISTRY, key=lambda x: (order[x.status], x.country)):
        lines.append(f"{src.name:<38}{src.connector:<14}{src.country:<5}{src.tier:<15}{src.status}")
    # DACH-Abdeckungsmatrix (das 100%-Ziel)
    lines += ["", "DACH-Abdeckung (Land × Schwelle → beste Quelle):", "-" * 78]
    for cc, tier, name, status in dach_matrix():
        mark = {"live": "✅", "prepared": "🟡", "candidate": "🟠", "research": "⚪", "fehlt": "❌"}.get(status, "")
        lines.append(f"  {cc}  {tier:<15} {mark} {name}  [{status}]")
    return "\n".join(lines)
