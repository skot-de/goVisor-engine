# Quellen-Landkarte — Ausbau-Strategie

**Stand 2026-07-29.** Deklarativer Katalog: `govisor/sources.py` (Registry) · Überblick:
`python -m govisor.cli sources`. Dieses Dokument erklärt die **Strategie** hinter der Registry.

## Der „200 Quellen"-Einwand — ehrlich eingeordnet

Wettbewerber werben mit „200+ angeschlossenen Quellen". Das klingt nach 100× unserem Stand,
ist aber überwiegend eine **Vanity-Metrik**. Die meisten dieser „Quellen" sind einzelne
Vergabeportale (DTVP, cosinex, subreport, evergabe.de, vergabe24, …), die ihrerseits über
wenige **Aggregatoren** zusammenlaufen. Wer 200 Portale einzeln anschließt, pflegt 200
Konnektoren für Daten, die zu großen Teilen durch dieselben drei, vier Kanäle fließen.

goVisor setzt bewusst an den **Aggregatoren** an. Gemessen statt behauptet:

| Connector (technische Basis) | aggregiert | Beleg |
|---|---|---|
| **TED** (`ted-bulk`) | oberschwellige Vergaben **aller ~30 EU/EEA-Länder** | `bulk._walk` filtert je ISO-Präfix; DE lückenlos 2004– verifiziert |
| **DÖE** (`doe-api`) | die **deutsche Portallandschaft** unterschwellig | Roh-eForms-Herkunft n=952 (2026-07-29): cosinex/DTVP **23 %**, DTAD 19 %, AI/evergabe.de 13 %, subreport 9 %, Staatsanzeiger 5 %, AUMASS 4 %, Healy 4 % |
| **simap** (`simap-json`) | CH **Bund + 26 Kantone** | offene JSON-API |

**Kernsatz:** *Quellen-Anzahl ist kein Coverage-Maß.* Drei Aggregator-Connector decken hunderte
Einzelportale ab. Die Registry zählt darum **zwei Zahlen getrennt**:

- **Connector** = technische Basen, die wir pflegen (heute **3**). Das ist der ehrliche Aufwand.
- **Herkunfts-Portale** = die aggregierte Breite dahinter (heute **~36 live**, wächst mit jedem
  Land/Portal). Das ist die Zahl, die „200 Quellen" ehrlich kontert.

Eine **Quelle** in der Registry = (Connector × Land × Schwellen-Tier). Heute: **33 Quellen**
(3 live, 1 prepared, 28 candidate, 1 research).

## DACH zu 100 % — der konkrete Plan (recherchiert 2026-07-29)

Ziel von Sven: **DACH lückenlos.** Abdeckung als Matrix (`python -m govisor.cli sources` zeigt sie live):

| Land × Schwelle | beste Quelle | Status |
|---|---|---|
| DE oberschwellig | TED | ✅ live |
| DE **unterschwellig** | DÖE | ✅ live |
| AT oberschwellig | TED (`build_at_gold`) | 🟡 prepared |
| AT **unterschwellig** | **OffeneVergaben.at** (neu) | 🟠 candidate |
| CH oberschwellig | simap | ✅ live |
| CH unterschwellig | simap | ✅ live |

**Ergebnis der Portal-Recherche: 100 % DACH braucht genau EINE neue Quelle** — der Rest ist
entweder schon abgedeckt oder bewusst niederwertig.

- **DE ist fertig.** `service.bund.de` **ist** der Datenservice Öffentlicher Einkauf = unser DÖE.
  Er zieht die unterschwelligen Portale über den XVergabe-Proxy des Beschaffungsamts zusammen
  (offene Schnittstelle in eForms/OCDS/CSV). **Kein deutsches Einzelportal** (DTVP, subreport,
  evergabe.de …) bringt nicht-redundante Abdeckung — gemessen laufen sie alle durch DÖE
  (cosinex 23 %, AI 13 %, subreport 9 %; [[govisor-negativbefunde]]).
- **AT unterschwellig = die eine Lücke.** Schließbar über offizielle Pflicht-Open-Data:
  Auftraggeber müssen Vergaben >50k € seit 2019 (BVergG2018) auf `data.gv.at` publizieren;
  **OffeneVergaben.at** (Forum Informationsfreiheit, Open Source) aggregiert das täglich als
  CSV-Bulk (~32 MB). Verifiziert, integrierbar. Kontrakt: `docs/quellen-at-unterschwellig.md`.
  **Nicht** das kommerzielle ANKÖ (kein offener Zugang, redundant oberhalb 50k).
- **CH ist praktisch fertig.** simap ist die rechtsverbindliche Plattform (Bund+Kantone+Gemeinden).
  Rest-Lücke: freihändige/Einladungs-Vergaben **unter** den CHF-Schwellen erscheinen oft nicht auf
  simap und liegen auf ~26 Kantonsportalen. Das ist **Direktvergabe ohne Wettbewerb** → kaum
  Lead-Wert, stark fragmentiert. **Bewusst kein 100%-Ziel** (Registry `ch-kantonal` = research,
  nur bei konkretem Kundenbedarf gezielt je Kanton).

**Fahrplan DACH-100 %:** (1) AT-TED voll ingesten (Brücke steht), (2) `offeneverg-csv`-Connector
bauen (~1 Modul, analog `simap.py`) + AT-unterschwellig ingesten. Danach sind 5/6 Boxen live und
die 6. (CH-freihändig) bewusst offen. Beide Schritte hängen am **Speicher** (externe SSD).

## Die zwei Ausbau-Achsen

### Achse 1 — Breite: TED über alle EU/EEA-Länder (billig, eine Basis)

Der `ted-bulk`-Connector läuft für **jedes** Land per `ingest --country XX` → `gold`. Kein neuer
Code, nur Ingest-Läufe + (optional) ein Locale-Profil für besseres Parsen. Das ist der **größte
Breiten-Hebel**: 28 weitere nationale Märkte oberschwellig, alle über eine gepflegte Basis.

- **DE** live · **AT** prepared (`build_at_gold`-Brücke fertig) · **FR** Locale-Profil existiert
  bereits (`locales.py`) → nächster natürlicher Ingest.
- Rest EU/EEA = `candidate` in der Registry. Reihenfolge nach Marktgröße/Kundennähe: FR, IT, NL,
  ES, PL, BE …
- **Blocker:** Voll-Ingest über alle Länder braucht Speicher (externe SSD, s. `docs/web-data-storage.md`).
  Die Brücke/Registry ist fertig; der Ingest wartet bewusst auf den Speicher.

### Achse 2 — Tiefe: unterschwellige nationale Portale (echte Lücken)

Oberschwellig ist über TED gelöst. Der genuine Mehrwert liegt **unterschwellig**, je Land eine
eigene Landschaft:

- **DE** → DÖE **live** (deckt die deutsche unterschwellige Landschaft ab).
- **AT** → ANKÖ / lieferanzeiger.at = `research` (Pendant zu DÖE, Datenzugang zu klären).
- **CH** → simap deckt beides; kantonale Sonderportale bei Bedarf.

**Was cosinex & Co. als eigene Quelle NICHT bringen** (gemessen, [[govisor-negativbefunde]]):
oberschwellig sind sie über TED + DÖE bereits drin (cosinex = 23 % der DÖE-Notices). Ein eigener
cosinex-Scraper wäre dort überwiegend redundant. **Offen** bleibt nur ihr **unterschwelliger**
Anteil, der nicht in DÖE läuft — den müsste man direkt gegen cosinex stichprobenmessen, bevor man
den Connector baut. Nicht auf Verdacht bauen.

## Reihenfolge (wenn der Speicher da ist)

1. **AT-TED** voll ingesten (Brücke steht) → erstes Nicht-DE-Land live, validiert die Pipeline.
2. **FR-TED** (Locale-Profil da) → zweitgrößter EU-Markt.
3. Weitere TED-Länder nach Kundennähe (IT/NL/ES/PL/BE …).
4. **AT-unterschwellig** (ANKÖ-Spike) — nur wenn ein Kunde AT-Tiefe braucht.
5. cosinex/DTVP unterschwellig — **nur** nach positiver Stichprobenmessung gegen DÖE.

## Neue Quelle anschließen — Checkliste

1. **Registry-Eintrag** in `govisor/sources.py` (`Source(...)`, Status `candidate`/`research`).
2. Gleiche technische Basis? → nur `ingest --country XX` + `gold` (bzw. `--bridge`). Fertig.
3. Neue Basis? → eigener Connector-Modul (`download`/`parse`/`build_silver`) wie `simap.py`,
   Kontrakt-Doku unter `docs/quellen-*.md`, CLI-Subcommand, Silber-Schema-Mapping.
4. Land-spezifisches Parsen nötig? → `Locale`-Profil in `locales.py` (sonst generischer Fallback).
5. Web-Export unioniert neue `gold/<CC>/…` automatisch (`scripts/export_web_leads.py::_union`).
6. Status in der Registry auf `live` setzen.
