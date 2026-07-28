# Feature #12: Losebene

**Produkt:** goVisor
**Version:** V1 (Phase 0 — vor Launch)
**Status:** Draft
**Erstellt:** 2026-07-27
**Ändert:** Ticket #1 (Lead Explorer), Ticket #3 (Lead-Detail)

---

## 1. Warum dieses Ticket vor Launch muss

goVisor behandelt heute die **Ausschreibung** als kleinste Einheit. Gebotet wird aber auf **Lose**. Solange die Zielgruppe Tier-1-Enterprise war, war das verschmerzbar — die jagen ohnehin große Rahmenverträge als Ganzes. Mit DÖE und regionalen Anbietern wird es zum systematischen Relevanzfehler.

**Das Szenario, das den Launch gefährdet:**

Eine Vergabe über €12M mit acht Losen enthält ein Los über €180k in Oberbayern. Für ein regionales Systemhaus ist das der einzige relevante Teil. In der aktuellen Logik erscheint aber ein €12M-Brocken, der:
- beim Volumenfilter des Users rausfliegt (zu groß), oder
- als „zu groß, nicht für uns" weggeklickt wird.

Der Lead war passend. Die Darstellungsebene war falsch. Ein regionaler Nutzer, dem das am ersten Tag passiert, verlässt das Produkt.

**Konsequenz:** Relevanz und Anzeige müssen auf Losebene rechnen, nicht auf Ausschreibungsebene.

---

## 2. Datenlage — ehrlich

Bevor das Feature spezifiziert wird, die harte Wahrheit aus dem Feldinventar. Sie bestimmt, was geht und was nicht.

### 2.1 Was gut da ist (Los-Struktur)

| Feld | Abdeckung DÖE | Bedeutung |
|---|---|---|
| `ProcurementProjectLot.ID` | 84,2 % | Los existiert und ist identifizierbar |
| `ProcurementProjectLot...MainCommodityClassification` | 71,9 % | **Los-CPV** — eigenes Fachgebiet je Los |
| `ProcurementProjectLot...TenderSubmissionDeadlinePeriod` | 82,0 % | **Los-Frist** |
| `ProcurementProjectLot...RequiredFinancialGuarantee` | 59,7 % | **Los-Bürgschaft** |
| `ProcurementProjectLot...VariantConstraintCode` | 59,7 % | Nebenangebote je Los |
| `ProcurementProjectLot...ProcurementProject.Note` | 56,2 % | Los-Beschreibung |

### 2.2 Was schwach da ist (Los-Wert und Multi-Los)

| Feld | Abdeckung | Konsequenz |
|---|---|---|
| **Los-Wert** (`Lot...RequestedTenderTotal` / `EstimatedOverall`) | **0,5–1,2 %** | **Los-Volumen ist praktisch nie bekannt** |
| `MultipleTendersCode` (mehrere Lose bebietbar?) | 26 % DÖE / 44 % eForms | Nur teilweise bekannt |
| `LotDistribution.MaximumLotsAwarded` | < 6 % | Fast nie bekannt |
| `PartPresentationCode` | 2,5–7,5 % | Fast nie bekannt |

### 2.3 Was das für das Feature bedeutet

Das ist die zentrale Designeinschränkung, und sie ist unbequem:

> **Wir können Lose als Einheit zeigen (Struktur ist da), aber fast nie mit eigenem Volumen (Wert fehlt).**

Das heißt konkret:
- Los-CPV und Los-Region sind belastbar → **Relevanz auf Losebene ist möglich und richtig**
- Los-Volumen ist es nicht → **Volumen bleibt meist auf Ausschreibungsebene**, als `unbekannt` je Los markiert
- Ob mehrere Lose bebietbar sind, wissen wir nur zu ~1/3 → **im Zweifel `unbekannt`, nicht annehmen**

Das ist kein Grund, das Feature zu verschieben. Los-CPV und Los-Region allein lösen das Launch-Problem — der regionale Nutzer sieht sein €180k-Los, weil dessen CPV und Region passen, auch wenn wir den Los-Wert nicht kennen. Das Volumen des Gesamtvertrags wird transparent als solches gekennzeichnet.

---

## 3. Konzept

### 3.1 Das Los wird zur Relevanzeinheit, die Ausschreibung bleibt die Anzeigeklammer

Kein kompletter Umbau der Liste auf Lose — das würde sie fluten (eine 8-Los-Vergabe wären 8 Zeilen). Stattdessen:

- **Relevanz wird je Los berechnet.**
- **Die Ausschreibung erscheint einmal in der Liste**, aber mit der Relevanz **ihres besten Loses** und einem Hinweis, welches Los passt.
- **Im Detail** werden die Lose einzeln aufgeschlüsselt, das/die passenden hervorgehoben.

```
Liste (eine Zeile je Ausschreibung):

  ┌────────────────────────────────────────────────────────────┐
  │ BMI – IT-Rahmen (8 Lose)              🎯 hoch  ⚡ mittel   │
  │ Bund · €12M gesamt · Frist 14.09.                          │
  │ ▸ Passt über Los 4: Managed Workplace Süd · Oberbayern    │
  └────────────────────────────────────────────────────────────┘
```

Der Nutzer sieht sofort: Die Vergabe ist groß, aber **relevant ist Los 4**, und das liegt in seiner Region.

### 3.2 Ein-Los-Vergaben bleiben unverändert

Der Großteil kleiner Vergaben hat genau ein Los. Für die ändert sich in der Darstellung nichts — das Los *ist* die Ausschreibung. Der Mechanismus greift nur sichtbar bei Mehr-Los-Vergaben.

---

## 4. Relevanz auf Losebene

### 4.1 Neue Berechnung

Bisher (Ticket #1): Relevanz = f(Ausschreibungs-CPV, Ausschreibungs-Region, Volumen).

Neu: Relevanz wird **je Los** gerechnet, dann auf die Ausschreibung aggregiert.

```
für jedes Los L einer Ausschreibung A:
    cpv_match(L)    = Match(User-Schwerpunkte, Los-CPV falls vorhanden,
                            sonst Ausschreibungs-CPV)
    region_match(L) = Match(User-Regionen, Los-Leistungsort falls vorhanden,
                            sonst Ausschreibungs-Region)
    volume_match(L) = Match(User-Volumenband, Los-Wert FALLS vorhanden (~1%),
                            sonst neutral 0.5)   # ehrlich: meist neutral

    relevance(L) = 0.4*cpv_match + 0.3*region_match + 0.3*volume_match

relevance(A) = max( relevance(L) für alle L in A )
best_lot(A)  = argmax( relevance(L) )
```

**Kernpunkt:** Die Ausschreibung erbt die Relevanz ihres **besten** Loses, nicht den Durchschnitt. Sonst würde eine 8-Los-Vergabe mit einem perfekten und sieben irrelevanten Losen fälschlich als mittelmäßig erscheinen — und genau das perfekte Los ginge unter.

### 4.2 Volumen ehrlich behandeln

Da Los-Wert fast nie vorliegt:

| Situation | Volumen-Match | Anzeige |
|---|---|---|
| Los-Wert bekannt (~1 %) | echte Range-Prüfung | Los-Volumen mit Quelle |
| Los-Wert unbekannt, Gesamtwert bekannt | **neutral (0.5)** | „€12M gesamt · Los-Anteil unbekannt" |
| Beides unbekannt (55,8 %) | neutral (0.5) | „€ — " + Badge |

Das Volumen darf ein Los **niemals** aus der Relevanz werfen, wenn der Los-Wert unbekannt ist. Genau dieser Fehler versteckt heute die kleinen Lose in großen Vergaben.

### 4.3 Wechsel-Wahrscheinlichkeit bleibt auf Ausschreibungsebene

`displaceability` ist am Vertrag/Incumbent modelliert, nicht am Los. Die Wechsel-W. bleibt also auf Ausschreibungsebene und wird nicht künstlich auf Lose heruntergebrochen. Im UI klar getrennt: Relevanz je Los, Wechsel-W. je Vergabe.

---

## 5. Änderungen an Ticket #1 (Lead Explorer)

### 5.1 Datenmodell

Die `leads`-Sicht bleibt eine Zeile je Ausschreibung. Ergänzt wird eine Los-Ebene.

**Neu: `lead_lots` (oder View auf bestehende Los-Daten)**

| Feld | Typ | Quelle |
|---|---|---|
| `lot_id` | string | `ProcurementProjectLot.ID` |
| `lead_id` | string | FK → leads |
| `lot_number` | string | Los-Nummer/Bezeichnung |
| `lot_title` | string | `Lot...ProcurementProject.Name` |
| `lot_cpv` | string | `Lot...MainCommodityClassification` (71,9 %) |
| `lot_nuts` | string | Los-Leistungsort, falls vorhanden |
| `lot_value` | numeric | `Lot...RequestedTenderTotal` — **meist NULL** |
| `lot_value_source` | enum | `echt` / `unbekannt` |
| `lot_deadline` | date | `Lot...TenderSubmissionDeadlinePeriod` (82 %) |
| `lot_guarantee` | numeric | `Lot...RequiredFinancialGuarantee` (59,7 %) |
| `lot_variants_allowed` | bool | `VariantConstraintCode`, nullable |

**Erweitert: `lead_relevance`**

| Feld neu | Typ | Bedeutung |
|---|---|---|
| `best_lot_id` | string | Los mit höchster Relevanz |
| `best_lot_relevance` | int | dessen Relevanz (= Ausschreibungs-Relevanz) |
| `matching_lot_count` | int | Wie viele Lose passen (Relevanz ≥ Schwelle) |
| `multi_lot` | bool | Vergabe hat > 1 Los |

### 5.2 Berechnungsstrategie

Konsistent mit dem bestehenden Ansatz in #1: On-the-fly beim Lesen der Liste, materialisiert nur für Alerts.

- **Liste (lesen):** Los-Relevanz on-the-fly in DuckDB. Bei 70k Leads mit im Median wenigen Losen bleibt das Millisekunden.
- **Alerts/Badge:** `best_lot_relevance` materialisiert, damit „passt erstmals über ein neues Los" erkennbar ist.

### 5.3 Filter

Der Volumenfilter des Users darf eine Mehr-Los-Vergabe **nicht** ausschließen, nur weil der **Gesamtwert** über der Obergrenze liegt. Solange ein Los passen könnte (oder der Los-Wert unbekannt ist), bleibt die Vergabe in der Liste.

```
Vergabe fällt aus dem Volumenfilter NUR wenn:
    Gesamtwert bekannt UND
    kein Los-Wert bekannt UND
    Gesamtwert weit außerhalb User-Band
    (= konservativ, im Zweifel drin lassen)
```

Region- und CPV-Filter greifen auf Losebene: Passt ein Los in CPV und Region, bleibt die Vergabe.

### 5.4 Listen-Darstellung

Eine Zeile je Ausschreibung, ergänzt um die Los-Hinweiszeile bei Mehr-Los-Vergaben:

```
🎯 [Relevanz-Band]  ⚡ [Wechsel-Band]
[Titel] ([n] Lose)
[Buyer] · [Gesamtvolumen + Quelle] · Frist [best_lot deadline]
▸ Passt über Los [x]: [lot_title] · [lot_nuts]
```

Bei mehreren passenden Losen: „▸ Passt über 3 Lose: …" mit Aufklappmöglichkeit.

Bei Ein-Los-Vergaben entfällt die Los-Zeile komplett.

---

## 6. Änderungen an Ticket #3 (Lead-Detail)

### 6.1 Neue Los-Aufschlüsselung im Übersicht-Tab

Der Übersicht-Tab (Free, unbegrenzt) bekommt bei Mehr-Los-Vergaben eine Los-Tabelle:

```
LOSE (8)                                    Passend für euch: Los 4, Los 7

  #   Titel                        CPV        Region        Frist      Passt
  ──────────────────────────────────────────────────────────────────────────
  1   Clients Nord               30200000   Niedersachsen  14.09.      ○
  2   Server Nord                48800000   Niedersachsen  14.09.      ○
  3   Netzwerk Nord              32400000   Niedersachsen  14.09.      ○
  4   Managed Workplace Süd      72500000   Oberbayern     14.09.    ● hoch
  7   Support Süd                72600000   Oberbayern     21.09.    ◐ mittel
  8   Schulung                   80500000   bundesweit     14.09.      ○
  ──────────────────────────────────────────────────────────────────────────
  Los-Volumen wird selten veröffentlicht. Gesamtvolumen: €12M.
```

Die letzte Zeile ist Pflicht — sie erklärt ehrlich, warum keine Los-Beträge dastehen, statt eine Lücke zu lassen.

### 6.2 Mehr-Los-Hinweis

Falls `MultipleTendersCode` bekannt (26–44 %): Hinweis, ob mehrere Lose gemeinsam bebietbar sind. Falls unbekannt: **kein** Hinweis, nicht raten.

```
[falls bekannt] ✓ Mehrere Lose gemeinsam bebietbar
[falls bekannt] ✗ Nur ein Los pro Bieter
[falls unbekannt] (nichts anzeigen)
```

### 6.3 Los-Bürgschaft im Anforderungs-Check

Die Los-Bürgschaft (59,7 %) fließt in den Anforderungs-Check des passenden Loses ein — relevant, weil ein kleines Los oft eine niedrigere Bürgschaft hat als der Gesamtvertrag, was gerade für kleine Anbieter den Unterschied macht.

---

## 7. Provenance

Konsistent mit der bestehenden Grammatik:

| Wert | Quelle | Kennzeichnung |
|---|---|---|
| Los-CPV | `Lot...MainCommodityClassification` | echt (71,9 %) |
| Los-Region | Los-Leistungsort | echt, wo vorhanden; sonst Ausschreibungs-Region geerbt (markiert) |
| Los-Volumen | fast nie | **`unbekannt`** — nie schätzen, nie vom Gesamtwert ableiten |
| Los-Frist | `Lot...SubmissionDeadline` | echt (82 %) |
| Mehr-Los-Bebietbarkeit | `MultipleTendersCode` | echt wo vorhanden (26–44 %), sonst nicht anzeigen |

**Regel:** Der Gesamtvertragswert wird nie als Los-Wert ausgegeben, auch nicht anteilig geschätzt. „€12M gesamt" und „Los-Wert unbekannt" stehen nebeneinander, werden nie vermischt.

---

## 8. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Relevanz wird je Los berechnet, Ausschreibung erbt Relevanz des besten Loses |
| 2 | Mehr-Los-Vergabe mit einem passenden Los erscheint in der Liste, nicht ausgefiltert |
| 3 | Volumenfilter schließt Mehr-Los-Vergabe nicht aus, solange ein Los passen könnte |
| 4 | Unbekannter Los-Wert wirft ein Los nie aus der Relevanz (neutral 0.5) |
| 5 | Liste zeigt bei Mehr-Los-Vergaben, über welches Los sie passt |
| 6 | Ein-Los-Vergaben unverändert dargestellt (keine Los-Zeile) |
| 7 | Detail zeigt Los-Aufschlüsselung mit Passt-Markierung |
| 8 | Los-Volumen nie aus Gesamtwert abgeleitet |
| 9 | Los-Volumen-Lücke im UI erklärt, nicht kommentarlos leer |
| 10 | Mehr-Los-Bebietbarkeit nur angezeigt wenn bekannt, sonst nichts |
| 11 | Los-Frist und Los-Bürgschaft im Detail/Anforderungs-Check genutzt |
| 12 | Wechsel-W. bleibt auf Ausschreibungsebene, klar getrennt von Los-Relevanz |

---

## 9. Edge Cases

| # | Case | Verhalten |
|---|---|---|
| 1 | Vergabe hat genau 1 Los | Wie bisher, keine Los-UI |
| 2 | Los ohne eigenen CPV (28 %) | Ausschreibungs-CPV erben, markiert |
| 3 | Los ohne eigene Region | Ausschreibungs-Region erben, markiert |
| 4 | Alle Lose irrelevant | Vergabe erscheint mit niedriger Relevanz, kein „Passt über"-Hinweis |
| 5 | Los-Wert bekannt, aber nur bei einem von acht | Nur dieses Los mit Wert, Rest unbekannt |
| 6 | `MultipleTendersCode` unbekannt | Keinen Hinweis zur Bebietbarkeit zeigen |
| 7 | Los-Frist weicht von Ausschreibungs-Frist ab | Los-Frist im Detail nutzen, in Liste die des besten Loses |
| 8 | Sehr viele Lose (> 20) | Detail-Tabelle paginieren, passende zuerst |
| 9 | Los zurückgezogen/geändert | Bei nächstem Ingest aktualisieren |

---

## 10. Out of Scope

| Was | Warum / Wann |
|---|---|
| Los-Volumen schätzen (Gesamt / Anzahl Lose) | Verletzt Provenance-Regel — nie |
| Eigene Watchlist je Los | V2 — erst wenn Losebene sich bewährt |
| Los-genaue Wechsel-Wahrscheinlichkeit | Modell ist am Vertrag, nicht am Los |
| Bietergemeinschaft-Vorschlag je Los-Lücke | Netzwerk-Thema, Phase 3 |
| Los-genaue Alerts | V2 — V1 alertet auf Ausschreibungsebene |

---

## 11. Abhängigkeiten

| Abhängigkeit | Status |
|---|---|
| `ProcurementProjectLot`-Daten im Gold Layer | vorhanden (84 % DÖE) |
| Ticket #1 Lead Explorer | Basis, wird geändert |
| Ticket #3 Lead-Detail | Basis, wird geändert |
| Los-CPV → Branche-Mapping | nutzt bestehendes `dim_cpv` |
| NUTS-3 für Los-Region | Ticket #P0.3, parallel |

---

## 12. Testfälle

| # | Test | Erwartung |
|---|---|---|
| 1 | 8-Los-Vergabe, 1 Los passt in Region+CPV | Erscheint in Liste, „Passt über Los X" |
| 2 | User-Volumenband 50–300k, Vergabe €12M gesamt, Los-Wert unbekannt | Bleibt in Liste (nicht ausgefiltert) |
| 3 | Ein-Los-Vergabe | Keine Los-UI, wie bisher |
| 4 | Los ohne eigenen CPV | Ausschreibungs-CPV geerbt, im Detail markiert |
| 5 | Detail einer 8-Los-Vergabe | Los-Tabelle mit 8 Zeilen, passende markiert |
| 6 | Los-Wert bei keinem Los bekannt | „Gesamtvolumen: €X" + „Los-Volumen selten veröffentlicht" |
| 7 | `MultipleTendersCode=allowed` | „Mehrere Lose gemeinsam bebietbar" |
| 8 | `MultipleTendersCode` fehlt | Kein Bebietbarkeits-Hinweis |
| 9 | Los-Bürgschaft niedriger als Gesamt | Anforderungs-Check nutzt Los-Bürgschaft |
| 10 | 25-Los-Vergabe | Detail paginiert, passende Lose zuerst |

---

## 13. Offene Fragen

| # | Frage | Empfehlung |
|---|---|---|
| 1 | `lead_lots` als Tabelle oder View? | View auf bestehende Gold-Los-Daten, falls Performance reicht; sonst materialisieren |
| 2 | Schwelle „passendes Los" für `matching_lot_count`? | Relevanz ≥ 60 (analog Auto-Watchlist-Logik) |
| 3 | Los-Region erben, wenn nur Ausschreibungs-NUTS da? | Ja, aber sichtbar markieren als geerbt |
| 4 | Liste: bei vielen passenden Losen alle zeigen? | Nein, „Passt über N Lose" + Aufklappen im Detail |
| 5 | Alerts schon los-genau? | Nein, V1 auf Ausschreibungsebene (Out of Scope) |

---

## 14. Zusammenfassung

Das Los wird zur Relevanzeinheit, die Ausschreibung bleibt die Anzeigeklammer. Die Los-Struktur (CPV, Region, Frist, Bürgschaft) ist in den Daten gut abgedeckt und trägt das Feature; der Los-Wert fehlt fast immer und wird ehrlich als unbekannt geführt, nie geschätzt. Damit sieht ein regionaler Anbieter sein passendes €180k-Los in einer €12M-Vergabe — der eine Fehler, der sonst am ersten Tag Nutzer kostet, ist behoben, ohne die Provenance-Regel zu verletzen.
