# Spike: Datenservice Öffentlicher Einkauf (DÖE) als zweite Lead-Quelle

**Frage:** Können wir in v1 weitere Quellen hinzunehmen, um die Lead-Anzahl zu erhöhen?
**Antwort:** Ja — DÖE (oeffentlichevergabe.de) bringt ~6.200 **unterschwellige** Leads/Monat,
die TED strukturell nie enthält. Gemessen, nicht angenommen.

## Die Quelle
- **Endpunkt:** `GET https://oeffentlichevergabe.de/api/notice-exports?pubMonth=YYYY-MM&format={eforms.zip|ocds.zip|csv.zip}`
  (auch `pubDay=YYYY-MM-DD`). Keine Auth. **Lizenz CC0.** OpenAPI: `/documentation/api/opendata`.
- CSV-Variante = 12 normalisierte Tabellen (notice, lot, organisation, purpose, classification,
  placeOfPerformance, duration, procedure, submissionTerms, noticeResult …), verlinkt über
  `noticeIdentifier + noticeVersion + lotIdentifier`. Sauberer als rohes TED-XML.

## Messung an 2026-05 (24.302 Bekanntmachungen)
Klassifikation nach `procedureLegalBasis`: EU-Richtlinie (`3…`) = oberschwellig → auf TED;
`de-*` (de-vob/de-vol/de-uvgo/de-hhr) = national → unterschwellig, **nicht** auf TED.

| Segment | Leads (cn/qu) | Nicht-Leads |
|---|---|---|
| oberschwellig (→ TED-Dublette) | 7.777 | 6.270 |
| **national/unterschwellig (netto-neu)** | **6.219** | 1.639 |
| unklar (None/other) | 1.862 | 535 |

**Validierung:** DÖE-oberschwellige Leads (7.777) ≈ unser TED-Bestand 2026-05 (7.365 cn/pin) →
gleiche Grundgesamtheit, die Klassifikation stimmt.

**Netto-neu:** ~6.219 unterschwellige Leads/Monat = **~+84 %** auf TEDs ~7.400 cn/pin.
Hochgerechnet ~74k unterschwellige Leads/Jahr.

## Sind sie brauchbar? (Coverage auf den 6.219 Unterschwellen-Leads)
| Feld | Coverage |
|---|---|
| CPV | 94 % |
| Käufer-Name | 98 % |
| Ort/NUTS/PLZ | 75 % |
| Käufer nationale ID | 0 % |

→ Für Radar/Radius/Lead-Produkt sofort nutzbar (CPV+Käufer+Ort stark). Nationale ID fehlt —
gleiche Entity-Resolution-Schwäche wie bei TED, kein Blocker für Leads.

## Ehrliche Caveats
1. **Historie (gemessen):** Ziehbar **2023-01 → aktueller Monat** (`pubMonth`/`pubDay`; davor HTTP 400).
   Ramp: 2023-01…10 = unterschwellig schon voll (~10k/Monat de-*), oberschwellig dünn (~2k); ab 2023-11
   (eForms-Pflicht) Vollspektrum, 2024 ff. ~27k/Monat. → **Unterschwellen-Historie reicht bis 2023-01
   (~3,5 J)** — genug für Auslauf-/Nachfolge-Signale, nicht nur Live-Feed. Aber DÖE geht NICHT vor 2023;
   für tiefe Historie (Ketten, Tenure) bleibt TED (2004–2026) das Rückgrat.
2. **Dedup nötig bei Oberschwelle:** die oberschwelligen DÖE-Notices SIND TED-Dubletten (UUID ≠
   TED-publication_number → kein direkter ID-Join im CSV-Summary). **Sauberster v1-Weg: nur das
   `de-*`-Subset ingesten** → per Definition kein Overlap mit TED, kein Dedup-Problem.
3. Klassifikation via Rechtsgrundlage ist ein starker Proxy (oberschwellige Zahlen matchen), aber
   kein ID-Level-Join.

## Ist DÖE wirklich alles? (Landschaft geprüft)
Die 800+ einzelnen Vergabeportale kollabieren auf **zwei Aggregatoren + eine Zusatzschicht** —
man ingestet nicht 800 Portale:

| Ebene | Quelle | Status für uns |
|---|---|---|
| Oberschwellig EU | **TED** | haben wir (2004–2026) |
| National-Aggregator | **DÖE** (oeffentlichevergabe.de) | primäre Netto-Neu-Quelle; **schluckt service.bund.de bereits automatisch** |
| Länder-Open-Data | **NRW (open.nrw)** u. a. | einzige *echt zusätzliche* offene Quelle — Lückenfüller |
| Redundant/geschlossen | service.bund.de (nur RSS, fließt in DÖE); DTVP/subreport/Vergabe24/cosinex-VMP (kommerziell, zu) | ignorieren |

- **service.bund.de ist keine separate Quelle** — Bekanntmachungen darüber erscheinen laut
  DÖE-Doku automatisch im Bekanntmachungsservice. Nur ein RSS-Feed, redundant.
- **NRW** bietet seit 2018 eine eigene Open-Data-API (open.nrw, VMP-basiert, cosinex) — ebenso
  BW/Bayern (viele Länder-VMPs teilen die cosinex-Technik). Genuine Zusatzquelle, FALLS DÖE
  unterschwellig regional noch lückt.

**Länder-Feeds gemessen (NRW):** Der NRW-Vergabemarktplatz (evergabe.nrw.de, cosinex) liefert
Open Data als `VMPSatellite/opendata`-XML (7 regionale Feeds, täglich, Datenlizenz DE-Zero) —
aber im **eForms-DE-Format** (`CustomizationID=eforms-de-2.1`), also **dieselbe Pipeline wie DÖE**.
Gegenprobe: In DÖE 2026-05 stecken **578 unterschwellige Leads mit NRW-Leistungsort** (von 4.667
mit NUTS). → **NRW-Unterschwelliges fließt bereits in DÖE.** Die Länder-Portale sind ein
dezentraler Kanal derselben Daten, **keine Zusatzquelle**. Länder-Konnektoren zu bauen (NRW allein
= 7 Feeds) brächte fast nichts.

**Offen bleibt nur:** ob DÖEs Länder-Abdeckung 100 % ist (zeit-alignter NRW-Feed vs. DÖE) — für v1
irrelevant, da NRW nachweislich drin ist.

**Datenqualitäts-Caveat (gemessen):** Bei Unterschwellen-Leads ist der **Käufer-NUTS zu 0 %**
befüllt (nur Leistungsort-NUTS 75 %). Für die Käufer-Achse der Radius-/Regionssuche müssten wir die
Käufer-Region aus Name/PLZ ableiten — kein Blocker, aber ein Mapping-Schritt.

## Empfehlung für v1
**Machbar und lohnend.** Bounded Increment: ein DÖE-Bronze/Silver-Pfad, der **nur `de-*`-Leads**
zieht (kein Dedup), auf unser `notices`/`leads`-Modell mappt (CPV/Käufer/Ort vorhanden), Quelle
per `source='doe_unter'` geflaggt. Monatlicher ZIP-Pull wie beim TED-Ingest. Verdoppelt grob den
laufenden Lead-Zufluss. Kein Rechts-Risiko (CC0).
