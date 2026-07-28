# Quelle CH — simap.ch API (Discovery, 2026-07-28)

**Ergebnis: offene JSON-REST-API, keine Auth, kein Key, kein Login.** Ideal anzubinden.
Ganze Schweiz (Bund + Kantone + Gemeinden publizieren seit 2011 hier) über *einen* Zugang.

## Such-Endpoint (verifiziert, HTTP 200 ohne Auth)
```
GET https://www.simap.ch/rest/publications/v2/project/project-search
    ?lang=de&lang=fr&lang=it&lang=en
    &orderAddressCountryOnlySwitzerland=false
    &page=0&size=20
```
- **Pfad ist `/rest/…`**, NICHT `/api/…` (letzterer gibt 400 — häufige Falle).
- Antwort: `{ "projects": [ … ], "pagination": { "lastItem": "20260728|33405", "itemsPerPage": 20 } }`
- **Cursor-Paginierung:** `pagination.lastItem` als Cursor für die nächste Seite mitgeben
  (nicht offset-basiert). Standard 20/Seite.

## Projekt-Objekt (Trefferliste)
```
id, title{de,fr,it,en}, projectNumber, projectType (tender|…), projectSubType (construction|…),
processType (open|…), lotsType, publicationId, publicationDate, publicationNumber,
pubType (tender|award|revocation|…), corrected, procOfficeName{de,fr,it,en} (=Auftraggeber),
lots, orderAddressOnlyDescription, orderAddress (=Leistungsort)
```
- **Mehrsprachig** (de/fr/it/en) — passt auf unser i18n-Fundament; `land='CH'` aktiviert den
  DACH-Länderfilter.
- **JSON, NICHT eForms** — braucht einen EIGENEN Parser (`schema_gen='simap'`), der eForms-Parser
  ist NICHT wiederverwendbar (frühere Hypothese widerlegt).

## Detail-Endpoint (verifiziert, HTTP 200, offen)
SPA-Route `/de/project-detail/{projectId}` feuert drei Calls; der reiche ist:
```
GET https://www.simap.ch/rest/publications/v1/project/{projectId}/publication-details/{publicationId}?lang=de
```
(zusätzlich: `…/project/{projectId}/project-header` = Kopf, `…/publication/{publicationId}/past-publications`
= Historie/Korrekturen.) ~11 KB JSON je Publikation.

**Reiche Felder unter `procurement`:**
- `orderDescription{de,en,fr,it}` — Beschreibungstext (mehrsprachig)
- `cpvCode` + `additionalCpvCodes` — **CPV** (direkt auf unser Vokabular mappbar!) · `cpcCode` — CPC (WTO)
- `bkpCodes / ebkphCodes / ebkptCodes / npkCodes / oagCodes` — CH-Bau-Klassifikationen (Zusatzsignal)
- `constructionType / constructionCategory / orderType / processType`
- `executionPeriod / executionDays / contractPeriod / contractDays / canContractBeExtended` — Laufzeit (→ `lead_duration`)
- `variants / partialOffers / options` (+ `…Note`) — Angebotsbedingungen (→ Anforderungs-Check)
- `orderAddress` — Leistungsort · `base.title{lang}`, `base.publicationTed` (auch auf TED? → Dedup-Signal)

**Befund:** **kein Schätzwert** im Detail (Feld fehlt — CH publiziert ihn meist nicht, analog TED-Lücke).
Unser Band-Imputations-Pfad (`value_band_effektiv`) fängt das ab. Submission-/Angebotsfrist: in diesem
Beispiel nicht unter den Standardnamen — beim Parser-Bau an einer echten offenen Ausschreibung final
verorten (evtl. eigener Termin-Block je pubType).

## CH-Extras — Signale, die TEILS BESSER sind als unser TED-Pfad
Vollständige Feld-Inventur über `tender` + `award`. Die Award-Publikation liefert strukturiert,
was bei TED unsere härtesten Lücken sind:

**Award-Block (`decision`) — Gold wert:**
- `decision.vendors[].vendorName` + volle Adresse → **Gewinner direkt** (kein NER/Extraktion nötig)
- `decision.vendors[].price.{price,currency,vatType}` → **echter Zuschlagspreis** (z. B. 152 652.35 CHF) —
  füllt genau die Wert-Lücke (bei TED 55 % unbekannt)
- `decision.numberOfSubmissions` → **Bieterzahl direkt** (z. B. 4) — unser Single-Bidder-/Wettbewerbs-
  signal ohne jede Schätzung. Das ist bei TED der größte Schmerz — hier geschenkt.
- `decision.awardDecisionDate`, `decision.totalPriceSelection`

**Tender-Block — reicher als TED:**
- `dates.offerDeadline` = **Angebotsfrist MIT Uhrzeit** (`…T11:00:00+02:00`) → #9-Alert + Uhrzeit (#16)
- `dates.qnas[].date` = **Fragefrist** (#16) · `dates.offerValidityDeadlineDate` = **Bindefrist** (anf)
- `terms.consortiumAllowed / subContractorAllowed` = ARGE-/Nachunternehmer-Regeln (Anforderungs-Check)
- `criteria.qualificationCriteria[] / awardCriteria[]` = Eignungs-/Zuschlagskriterien (oft „in documents")
- `terms.remediesNotice` = **Rechtsmittel-Hinweis** — Signal, das wir aus TED gar nicht haben
- `correction.correctionDiffKeys[]` = **welche Felder eine Korrektur geändert hat** (präziser als unser „geändert")
- `procurement.bkpCodes[]` (+ eBKP/NPK) = CH-Bau-Taxonomie, feiner als CPV bei Bau

**Kontaktdaten (⚠️ PII — Security-Gate beachten):**
- `project-info.procOfficeAddress.{contactPerson,phone,email,url,street}` — Ansprechpartner + Mail/Tel.
  Lead-Gen-Wert, aber **personenbezogen** → nicht in den Free-Tier/öffentlich (analog §9-Blur, nie ins Bundle).

**Sonstige:** `stateContractArea` (WTO/GPA-Abdeckung), `publicationTed` (Dedup-Flag), `offerLanguages`,
`documentsWithCosts` (Unterlagen kostenpflichtig?), `documentsSourceType`.

**Konsequenz:** CH-Daten könnten unsere **Nachfolge-/Wettbewerbs-KPIs für Schweizer Segmente sogar
verbessern** (Gewinner+Preis+Bieterzahl strukturiert). DE/AT müssen die Felder null-tolerant behandeln.

## Feld-Mapping simap → Silber (Skizze fürs Bauen)
| Silber | simap-Quelle |
|---|---|
| notice_id | `publicationNumber` (z. B. `1185-03`) bzw. `publicationId` |
| title | `base.title` (mehrsprachig — de bevorzugt, sonst fr/it) |
| buyer | `procOfficeName` / `project-info.procOfficeAddress` |
| cpv | `procurement.cpvCode` (+ `additionalCpvCodes`) |
| beschreibung | `procurement.orderDescription` |
| geo (nuts/plz) | `orderAddress.{countryId,cantonId,postalCode,city}` (CH-Kanton → NUTS-CH) |
| laufzeit | `procurement.contractPeriod / contractDays` |
| land | `'CH'` konstant |

## Quellen
- [simap.ch — Veröffentlichungen suchen](https://www.simap.ch/) (SPA, ruft den REST-Endpoint)
- [Wikipedia: Simap.ch](https://en.wikipedia.org/wiki/Simap.ch)

---

## Umsetzungsstand (2026-07-28) — F1 Schritt 1–4 fertig
- **Schritt 1** Discovery ✅ (dieser Doc)
- **Schritt 2** Downloader ✅ — `govisor/simap.py::download`, Bronze `raw_simap/CH/YYYY-MM.jsonl`, CLI `ingest-simap`
- **Schritt 3** Parser ✅ — `parse_publication`/`build_silver`, Silber `schema_gen='simap'`, CH-Extras→attributes
- **CH-Geo** ✅ — `dim_plz` liest DE+CH (GeoNames CH.txt), `build_lead_geo` länder-PLZ-Stellen
- **Schritt 4** Gold-Brücke ✅ — `build_ch_gold` (lead_export/geo/deadline), Export vereint DE+CH per
  `union_by_name`, `land` aus country-Spalte, Nicht-DE umgeht den Branchen-CAP, `l.extras[]`-Block
- **Verifiziert:** 25-Seiten-Backfill → **280 CH-Leads** über alle Branchen, 100 % Geo+Extras,
  Land-Filter „Schweiz" greift, Detail zeigt „Land: Schweiz" + „Zusätzliche Angaben (🇨🇭)".

**Voll-Backfill** (Produktion): `python -m govisor.cli ingest-simap --gold` (ohne `--max-pages`),
dann `python3 scripts/export_web_leads.py`. Awards (~50–80 %) tragen Gewinner/Preis/Bieterzahl —
noch NICHT als Markt-Kontext an die Tender geknüpft (offener Folgeschritt über `ref_publication_number`).

**Offen/Folge:** Award→Tender-Verknüpfung (Incumbent/Bieterzahl-Kontext) · Angebotsfrist-Uhrzeit +
Frage-/Bindefrist aus simap in die Standard-Slots (statt nur date) · Kontaktdaten (PII) server-gegated.
