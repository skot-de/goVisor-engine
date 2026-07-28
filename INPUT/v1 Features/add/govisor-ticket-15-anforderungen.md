# Feature #15: Anforderungen & Vergabeunterlagen

**Produkt:** goVisor
**Version:** Phase 1 — Aufholen
**Status:** Draft
**Erstellt:** 2026-07-27
**Baut auf:** Ticket #13 (Dokumentlink), Ticket #12 (Losebene), Ticket #3 (Anforderungs-Check)
**Aufwand:** groß, zweistufig

---

## 1. Warum dieses Ticket

Der Anforderungs-Check in Ticket #3 ist heute **CPV-basiert** — er prüft nur, ob der Haupt-CPV zum Profil passt. Das war eine bewusste V1-Entschärfung, weil die echten Anforderungen (Zertifikate, Eignung, Zuschlagskriterien) im Freitext liegen und die Vergabeunterlagen nicht vorlagen.

Die Wettbewerber sind hier weiter: Vergabepilot, Patterno und Adjudica lesen die Unterlagen und beantworten „passt das zu uns" auf Anforderungsebene, nicht nur auf CPV-Ebene. Adjudica zitiert jede Anforderung mit Seitenzahl aus dem Dokument.

**Das ist Aufholen, nicht Vorpreschen** (Schicht 1 der Marktanalyse). Aber es ist notwendig: Ohne echten Anforderungs-Check fehlt goVisor die Tiefe, die der Markt erwartet — und die Datengrundlage für die Fähigkeiten-Sektion (Strategie) und die Treffergüte-Erhebung.

---

## 2. Die zentrale Erkenntnis: zwei Wege, nicht einer

Es gibt **zwei Quellen** für Anforderungen, mit sehr unterschiedlichem Aufwand-Nutzen-Verhältnis:

| Weg | Quelle | Abdeckung | Aufwand |
|---|---|---|---|
| **A — Strukturiert** | eForms-Felder direkt | 33–45 % | niedrig |
| **B — Volltext** | Vergabeunterlagen hinter dem Link | 83 % (Link), Inhalt variabel | hoch |

Die Versuchung ist, sofort Weg B zu bauen (die Dokumente parsen). Der klügere Start ist Weg A — die strukturierten Felder sind schon da, sauber, ohne Crawling, und decken die wichtigsten Anforderungen ab.

**Reihenfolge:** Erst Weg A vollständig ausschöpfen, dann Weg B für das, was A nicht abdeckt.

---

## 3. Weg A — Strukturierte Anforderungen aus eForms

### 3.1 Was strukturiert vorliegt

Aus dem Feldinventar:

| Anforderung | Feld | Abdeckung |
|---|---|---|
| **Zuschlagskriterien-Typ** | `AwardingCriterionTypeCode` | 42,7 % |
| **Kriterien-Gewichtung** | `AwardCriterionParameter` (`number-weight`) | 33,7 % |
| **Eignungskriterien-Typ** | `SelectionCriteria.CriterionTypeCode` | 35,0 % |
| **Ausschlussgründe** | `TendererRequirementTypeCode` (`exclusion-ground`) | 43,8 % |
| **Bietergemeinschaft erlaubt** | `TendererQualificationRequest.CompanyLegalFormCode` | 43,7 % |
| **Bürgschaft** | `RequiredFinancialGuarantee` (aus #12) | 59,7 % |
| **Nebenangebote** | `VariantConstraintCode` (aus #12) | 59,7 % |
| **Rechtsrahmen** | `ProcurementLegislationDocumentReference` | 44–53 % |

### 3.2 Die Gewichtung ist der Durchbruch

Der wichtigste Einzelpunkt: `AwardCriterionParameter` mit `number-weight` (33,7 %) trägt die **Gewichtung** der Zuschlagskriterien.

Heute weiß goVisor (aus `AC_AWARD_CRIT`) nur die Kategorie: „wirtschaftlichstes Angebot". Mit diesem Feld weiß es:

> Preis 40 % · Konzept 35 % · Referenzen 25 %

Das ist der Unterschied zwischen einer Kategorie und einer Bid/No-Bid-Entscheidung. Ein Anbieter, der über den Preis nicht gewinnt, aber ein starkes Konzept hat, sieht sofort, ob sich die Bewerbung lohnt. Das kann sonst niemand im deutschen Markt strukturiert zeigen.

### 3.3 Anforderungs-Check erweitern (Ticket #3)

Der bestehende Check wird von CPV-only auf strukturierte Anforderungen erweitert:

```
ANFORDERUNGS-CHECK

  Fachgebiet (CPV)              ✓ passt zu eurem Profil
  Rechtsrahmen                  VgV — ihr habt VgV-Erfahrung
  Bürgschaft                    €50.000 gefordert · euer Rahmen: €250.000 ✓
  Nebenangebote                 zugelassen
  Bietergemeinschaft            erlaubt

  Zuschlagskriterien
  ├── Preis         40 %
  ├── Konzept       35 %
  └── Referenzen    25 %

  Ausschlussgründe              Standard (§123/124 GWB)
```

Jede Zeile mit Provenance: strukturiert vorhanden = echt, fehlend = „nicht veröffentlicht".

### 3.4 Abgleich gegen das Nutzerprofil

Wo das Nutzerprofil (aus Treffergüte #11) Angaben hat, wird abgeglichen:

| Anforderung | Nutzerangabe | Ergebnis |
|---|---|---|
| Bürgschaft €50k | Rahmen €250k | ✓ erfüllbar |
| Rechtsrahmen VgV | VgV-Erfahrung | ✓ |
| Bietergemeinschaft erlaubt | — | Info |

Fehlt eine Nutzerangabe, wird sie im Moment des Bedarfs erhoben (Treffergüte-Mechanik) — nicht vorausgesetzt.

---

## 4. Weg B — Volltext-Vergabeunterlagen

Erst wenn Weg A ausgeschöpft ist. Das ist der große, aufwändige Teil.

### 4.1 Die Realität des Zugriffs

Aus Ticket #13: Der Dokumentlink liegt zu 83 % vor, mit Zugänglichkeits-Markierung. Das teilt die Dokumente in drei Klassen:

| Klasse | Anteil (grob) | Crawlbar? |
|---|---|---|
| `non-restricted` | Teilmenge | Ja, ohne Login |
| `restricted` (Registrierung) | Teilmenge | Nur mit Login-Automatisierung |
| kein Link | 17 % | Nein |

**V1-Scope für Weg B: nur `non-restricted`.** Login-Automatisierung über Dutzende Portalsysteme ist ein eigenes großes Projekt und steht hier ausdrücklich außen vor. Das reduziert die Abdeckung, hält den Aufwand aber beherrschbar.

### 4.2 Pipeline

```
Dokumentlink (aus #13, non-restricted)
    │
    ▼
Download (PDF, teils DOCX/ZIP)
    │
    ▼
Text-Extraktion (PDF→Text, OCR falls Scan)
    │
    ▼
LLM-Extraktion mit Belegkette
    ├── geforderte Zertifikate
    ├── geforderte Referenzen (Anzahl, Größenordnung)
    ├── Eignungskriterien im Detail
    ├── Fristen (falls nicht strukturiert)
    └── Vertragsbesonderheiten (Pönalen, SLA)
    │
    ▼
Speicherung mit Quell-Seitenzahl (Grounding)
```

### 4.3 Grounding ist Pflicht (Adjudica-Lektion)

Jede extrahierte Anforderung muss die **Quellstelle** tragen — Dokumentname und Seite. Ohne Beleg wird nichts angezeigt. Das ist konsistent mit der Provenance-Regel und der stärkste Vertrauensanker gegen „die KI hat sich das ausgedacht".

```
Geforderte Zertifikate
  ISO 27001        (Eignung.pdf, S. 12)
  C5-Testat        (Eignung.pdf, S. 14)
  BSI-Grundschutz  (Leistung.pdf, S. 3)
```

Fehlt die Belegstelle, wird die Anforderung nicht als Fakt geführt.

### 4.4 LLM-Halluzination begrenzen

Die harte Regel für die Extraktion:

- Nur extrahieren, was im Text steht — nichts ergänzen
- Bei Unsicherheit weglassen, nicht raten
- Jede Aussage mit Seitenbeleg oder gar nicht
- Widersprüche im Dokument werden als Widerspruch markiert, nicht aufgelöst

Das ist dieselbe Haltung wie Adjudicas „fragt nach statt zu erfinden" — nur bei goVisor beim Extrahieren statt beim Antworten.

---

## 5. Anforderungs-Extraktion je Los

Anschluss an Ticket #12: Anforderungen können je Los verschieden sein. Ein Los fordert C5, ein anderes nicht. Die Extraktion läuft deshalb los-genau, wo Los-Dokumente vorliegen (aus #13, Dokumentlink auf Losebene).

Für den Nutzer relevant: Sein passendes Los (aus #12) bekommt seinen eigenen Anforderungs-Check — nicht der der gesamten Vergabe.

---

## 6. Datenmodell

### 6.1 Neu: `lead_requirements`

| Feld | Typ | Bedeutung |
|---|---|---|
| `id` | uuid | PK |
| `lead_id` | string | FK |
| `lot_id` | string | FK, nullable (los-genau) |
| `req_type` | enum | `certificate` / `reference` / `guarantee` / `award_criterion` / `exclusion` / `legal_regime` / `consortium` |
| `req_key` | string | z. B. `iso_27001`, `price_weight` |
| `req_value` | jsonb | typabhängig (Gewicht, Betrag, Anzahl) |
| `source` | enum | `eforms` (Weg A) / `document` (Weg B) |
| `source_ref` | string | bei `document`: Dateiname + Seite |
| `extraction_confidence` | decimal | bei LLM-Extraktion |

### 6.2 Neu: `lead_documents`

| Feld | Typ | Bedeutung |
|---|---|---|
| `id` | uuid | PK |
| `lead_id` / `lot_id` | string | FK |
| `url` | string | aus #13 |
| `access` | enum | `non_restricted` / `restricted` (aus #13) |
| `download_status` | enum | `pending` / `done` / `failed` / `skipped_restricted` |
| `text_extracted` | bool | |
| `page_count` | int | |
| `fetched_at` | timestamp | |

---

## 7. Auswirkung auf andere Tickets

| Ticket | Auswirkung |
|---|---|
| **#3 Lead-Detail** | Anforderungs-Check von CPV-only auf strukturiert + Volltext |
| **#10 Strategie** | Fähigkeiten-Sektion nutzt echte Anforderungen (Untergrenze-Formulierung entschärft sich) |
| **#11 Treffergüte** | Anforderungs-Check ist der Erhebungsmoment für Nutzerangaben |
| **#12 Losebene** | Anforderungen los-genau |
| **#13 Dokumentlink** | liefert URL + Zugänglichkeit als Eingabe |

**Wichtig für #10:** Die Fähigkeiten-Sektion musste bisher alles als „Untergrenze" formulieren (Eignung nur ~37 % im Freitext). Mit Weg A steigt der strukturierte Anteil deutlich — die Untergrenze-Formulierung bleibt korrekt, wird aber seltener nötig.

---

## 8. Provenance

| Wert | Weg | Kennzeichnung |
|---|---|---|
| Zuschlagskriterien-Gewicht | A (eForms) | echt (33,7 %) |
| Eignungskriterien | A (eForms) | echt (35 %) |
| Bürgschaft, Nebenangebote | A (eForms) | echt (59,7 %) |
| Zertifikate aus Dokument | B (LLM) | echt **mit Seitenbeleg**, sonst nicht angezeigt |
| Referenzen aus Dokument | B (LLM) | echt mit Seitenbeleg |
| fehlend | — | „nicht veröffentlicht" |

**Regel:** Weg-B-Extraktion ohne Seitenbeleg wird nie angezeigt. Weg A (strukturiert) und Weg B (extrahiert) werden im UI unterschieden — strukturiert ist härter als extrahiert.

---

## 9. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Anforderungs-Check nutzt strukturierte eForms-Felder (Weg A) |
| 2 | Zuschlagskriterien mit Gewichtung angezeigt, wo vorhanden |
| 3 | Bürgschaft, Nebenangebote, Rechtsrahmen, Ausschlussgründe im Check |
| 4 | Abgleich gegen Nutzerprofil, wo Angaben vorliegen |
| 5 | Weg B nur für `non-restricted`-Dokumente |
| 6 | Jede Weg-B-Anforderung trägt Seitenbeleg, sonst nicht angezeigt |
| 7 | LLM extrahiert nur Belegtes, rät nicht |
| 8 | Anforderungen los-genau, wo Los-Dokumente vorliegen |
| 9 | Weg A (strukturiert) und Weg B (extrahiert) im UI unterschieden |
| 10 | Fehlende Anforderung als „nicht veröffentlicht", nicht als „erfüllt" |
| 11 | `restricted`-Dokumente als `skipped_restricted` geführt, nicht als Fehler |

---

## 10. Edge Cases

| # | Case | Verhalten |
|---|---|---|
| 1 | Kein Dokumentlink | Nur Weg A, Hinweis „Detailanforderungen nicht verfügbar" |
| 2 | Link `restricted` | Weg A nutzen, Weg B übersprungen mit Hinweis |
| 3 | Dokument ist Scan (kein Text) | OCR; falls fehlschlägt, `text_extracted=false` |
| 4 | Dokument-ZIP mit mehreren Dateien | Alle extrahieren, je Datei Beleg |
| 5 | Widerspruch im Dokument | Beide Werte zeigen, als Widerspruch markiert |
| 6 | Gewichtung fehlt, nur Kriterien-Typen | Typen zeigen, „Gewichtung nicht veröffentlicht" |
| 7 | Los-Dokument vs. Gesamt-Dokument | Los-genau bevorzugen |
| 8 | Download-Timeout / 404 | `download_status=failed`, Weg A bleibt |
| 9 | Sehr großes Dokument (>100 S.) | Extraktion auf relevante Abschnitte fokussieren |
| 10 | Nutzerprofil hat Angabe nicht | Anforderung zeigen, Erhebung anstoßen (#11) |

---

## 11. Out of Scope

| Was | Wann / Warum |
|---|---|
| Login-Automatisierung für `restricted` | Eigenes Großprojekt — frühestens V2 |
| Angebotserstellung aus Anforderungen | Phase 4 (Adjudica-Territorium) |
| Preisblatt-Extraktion für Kalkulation | V2 |
| Vertragsbedingungen tief parsen (Pönalen etc.) | V2, erst Basisanforderungen |
| Dokument-Chat („frag die Unterlagen") | V2 — Vergabepilot hat das, nicht kritisch |
| Nicht-DE-Dokumente | Erst bei Multi-Country |

---

## 12. Abhängigkeiten

| Abhängigkeit | Status |
|---|---|
| Ticket #13 Dokumentlink + Zugänglichkeit | Voraussetzung |
| eForms-Felder im Gold Layer | vorhanden (33–45 %) |
| Ticket #12 Losebene | für los-genaue Anforderungen |
| LLM-Zugang für Extraktion | vorhanden |
| PDF/OCR-Pipeline | neu aufzubauen |
| Nutzerprofil (#11) für Abgleich | parallel |

---

## 13. Testfälle

| # | Test | Erwartung |
|---|---|---|
| 1 | Lead mit `AwardCriterionParameter` | Gewichtung „Preis 40 % / Konzept 35 %" |
| 2 | Lead ohne Gewichtung, mit Kriterien-Typ | Typen, „Gewichtung nicht veröffentlicht" |
| 3 | Bürgschaft €50k, Nutzer-Rahmen €250k | „✓ erfüllbar" |
| 4 | `non-restricted`-PDF mit ISO 27001 | „ISO 27001 (Datei, S. X)" |
| 5 | `restricted`-Dokument | Weg A, „Details erfordern Registrierung" |
| 6 | Scan-PDF | OCR, dann Extraktion |
| 7 | LLM findet Anforderung ohne klare Seite | Nicht anzeigen |
| 8 | Los 4 fordert C5, Los 1 nicht | Los-genauer Check |
| 9 | Kein Link, keine eForms-Kriterien | „Anforderungen nicht veröffentlicht" |
| 10 | Widerspruch im Dokument | Beide Werte, markiert |

---

## 14. Reihenfolge der Umsetzung

| Schritt | Inhalt | Warum zuerst |
|---|---|---|
| 1 | Weg A: strukturierte eForms-Anforderungen | Sofort verfügbar, kein Crawling, hoher Wert |
| 2 | Anforderungs-Check UI (Ticket #3 erweitern) | Zeigt Weg-A-Ergebnisse |
| 3 | Abgleich gegen Nutzerprofil | Anschluss #11 |
| 4 | Weg B: Download-Pipeline (`non-restricted`) | Der große Brocken |
| 5 | LLM-Extraktion mit Grounding | Kern von Weg B |
| 6 | Los-genaue Extraktion | Feinschliff |

Schritt 1–3 liefern bereits den Großteil des Werts. Schritt 4–6 sind der aufwändige Rest — falls Ressourcen knapp werden, ist nach Schritt 3 ein sinnvoller Zwischenstand erreicht.

---

## 15. Zusammenfassung

Der Anforderungs-Check wird von CPV-only auf echte Anforderungen gehoben — in zwei Wegen. Weg A nutzt die strukturierten eForms-Felder (Zuschlagskriterien mit Gewichtung, Eignung, Bürgschaft, Ausschlussgründe), ist sofort verfügbar und liefert den Großteil des Werts ohne Crawling. Weg B erschließt die Volltext-Unterlagen der `non-restricted`-Dokumente per LLM mit Pflicht-Seitenbeleg. Die Gewichtung der Zuschlagskriterien ist der eigentliche Durchbruch — sie macht aus „wirtschaftlichstes Angebot" eine echte Bid/No-Bid-Grundlage, die sonst niemand strukturiert zeigt. Das ist Aufholen zum Markt, aber notwendiges Aufholen, und die Basis für Fähigkeiten-Sektion und Treffergüte-Erhebung.
