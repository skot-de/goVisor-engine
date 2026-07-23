# Cross-KPIs — was erst aus der Kombination entsteht

Einzelne Felder beschreiben. Aussagen entstehen aus Kombinationen. Diese Liste trennt
strikt zwischen **gemessen** (an den Daten geprüft, mit Zahl) und **vorgeschlagen**
(Datenlage vorhanden, Wirkung nicht getestet). Stand 2026-07-23, 85.947 Leads.

Die UI-Zuordnung folgt den Kategorien aus `feld_inventar.csv` (Frontend v3.5).

---

## A · Gemessen

### A1 · Erwartete Bieterzahl bei offenen Ausschreibungen ⭐
**UI: Liste + Markt** · Zutaten: CPV-Division × Region × Verfahrensart (+ Käufer, wenn bekannt)

Die größte Blindstelle im Produkt: bei **12.123 offenen Leads ist `n_bidders` zu 0 %
gefüllt** — die Bieterzahl steht erst in der Zuschlags-Bekanntmachung. Der
Verdrängbarkeits-Score läuft dort ins „unbekannt"-Backoff.

Gemessen an 50.653 abgeschlossenen Vergaben, Hälfte Training / Hälfte Test:

| Prognose aus | mittl. Abweichung | Abdeckung |
|---|---:|---:|
| nur Gesamtmittel (4,50) | 2,92 | 100 % |
| Region allein | 2,90 | 100 % |
| Käufer allein | 2,80 | 72,5 % |
| CPV-Division allein | 2,64 | 100 % |
| **CPV × Region × Verfahren** | **2,55** | **90,9 %** |
| Käufer × CPV × Verfahren | 2,50 | 42,6 % |

**Die Kombination schlägt jede Einzeldimension** — aber nur um 13 % gegenüber dem
Gesamtmittel. Konsequenz fürs UI: als **Spanne** ausgeben („3–7 Bieter erwartet"), nie
als Punktwert. Ein „5 Bieter" wäre bei ±3 Abweichung eine Scheingenauigkeit.

### A2 · Preisdruck gegen Einstiegshürde ⭐
**UI: Übersicht + Bewertung** · Zutaten: Zuschlagskriterien-Gewicht × Bieterzahl

Die Intuition ist falsch, und das ist der Wert des KPI:

| Preisgewicht | Leads | Ø Bieter | Einzelbieter |
|---|---:|---:|---:|
| **100 %** | 35.092 | **5,31** | 20,9 % |
| 70–98 % | 2.476 | 3,87 | 23,4 % |
| 40–69 % | 6.864 | 4,40 | 22,0 % |
| **< 40 %** | 6.296 | **4,00** | 16,9 % |

Reine Preisvergaben ziehen **mehr** Bieter an, nicht weniger — kein Konzeptteil, keine
Referenzmappe, niedrige Einstiegshürde. Als Aussage: *„Hier kommst du leicht rein, aber du
bist einer von fünf. Dort musst du ein Konzept schreiben, konkurrierst aber nur mit drei."*

Das ist eine Angebotsstrategie-Entscheidung, die heute niemand datenbasiert trifft.

### A3 · Einstiegsschwelle bei Mehrlos-Ausschreibungen ⭐
**UI: Liste + Übersicht** · Zutaten: Losanzahl × kleinster Loswert × Gesamtwert

| Zugänglichkeit | Leads | Median Gesamtwert | Median kleinstes Los |
|---|---:|---:|---:|
| ein Los (ganz oder gar nicht) | 29.534 | 309.997 € | — |
| **Mehrlos, kleinstes < 100k** | **2.401** | **388.437 €** | **10.773 €** |
| Mehrlos, kleinstes 100–500k | 982 | 699.892 € | 189.164 € |
| Mehrlos, kleinstes ≥ 500k | 701 | 4.772.898 € | 1.317.568 € |

2.401 Ausschreibungen mit Median-Gesamtwert **388.437 €** sind ab **10.773 €** zugänglich.
Ein Kleinbetrieb sieht heute den Gesamtwert und klickt weg. Der Filter „zeig mir Aufträge,
bei denen ich ein Los ab X € nehmen kann" existiert nirgends im Markt.

### A4 · Marktverschluss-Dauer
**UI: Markt + Chance** · Zutaten: `ContractingSystemTypeCode` = `fa-wo-rc` × Vertragsende

**12.333 Leads** sind Rahmenvereinbarungen **ohne erneuten Wettbewerb**: wer drin ist,
ruft ab; wer draußen ist, hat keine Chance bis zum Ende. Ø Restlaufzeit **1,9 Jahre**,
**1.968** davon noch über 3 Jahre gesperrt.

Zwei Aussagen in einer Zahl: *„Hier lohnt kein Aufwand"* — und *„merk dir Q3/2029."*
Der zweite Teil ist ein Kalendereintrag, kein Lead.

### A5 · Quellen-Arbitrage
**UI: Liste (Quellenfilter) + Vergabestelle** · Zutaten: DÖE × TED je Käufer

Von 9.656 Vergabestellen erscheinen:

- **709 ausschließlich unterschwellig** — für einen reinen TED-Nutzer **unsichtbar**
- 708 in beiden Märkten
- 8.239 nur oberschwellig

Die 709 sind das direkteste Verkaufsargument gegen jeden Wettbewerber, der nur TED liest.
Kombiniert mit dem Gewerke-Befund (DÖE stellt 9,7 % aller Bau-Leads, aber 0 % bei
Finanz/Pharma) wird daraus eine zielgruppengenaue Aussage.

---

## B · Gemessen und **widerlegt**

### B1 · „Kurze Angebotsfrist begünstigt den Amtsinhaber" ❌
Plausible These, **mit unseren Daten nicht haltbar**. Über `award_tender_link` verkettet
(Zuschlag → Ausschreibung, um an die Frist zu kommen) bleiben nur **473 Fälle** mit
Publikationsdatum *und* Frist. Und das Muster zeigt in die Gegenrichtung:

| Angebotsfrist | n | Einzelbieter |
|---|---:|---:|
| 22–30 Tage | 198 | 37,9 % |
| 31–45 Tage | 189 | 46,0 % |
| **> 90 Tage** | 33 | **72,7 %** |

Lange Fristen haben die *höchste* Einzelbieter-Quote — vermutlich, weil komplexe
Spezialvergaben lange Fristen brauchen und ohnehin wenige Anbieter haben. Der Effekt der
Fristlänge ist von der Auftragsart überlagert und bei n=473 nicht trennbar.

**Nicht bauen**, solange `publication_date` bei nur 53 % liegt und die Verkettung bei 51 %.
Vgl. `docs/rohdaten-potenzial-gesamt.md` — das war der zweitgereihte Ersatz für die
verworfene NLP-Zuschnitt-Erkennung. Beide Wege sind damit zu.

---

## C · Vorgeschlagen — Datenlage vorhanden, Wirkung ungetestet

### C1 · Aufwand-Rendite ⭐⭐ (der stärkste Kandidat)
**UI: Liste (Sortierung!) + Bewertung**

```
Rendite  =  (Wertband × Gewinnchance)  ÷  Angebotsaufwand
```

- **Wert**: `value_band_effektiv`, bei Rahmenverträgen `FrameworkMaximumAmount`
- **Chance**: `displaceability` × erwartete Bieterzahl (A1) × `EconomicOperatorShortList`
  (bei nicht-offenen: „5 von N werden eingeladen")
- **Aufwand**: `RequiredCurricula` (Lebensläufe, 21–24 %) + Anzahl `SelectionCriteria` +
  `RequiredFinancialGuarantee` (Bürgschaft, DÖE 53 %) + `n_lots` + Beschreibungstiefe +
  `TenderValidityPeriod` (gebundene Kapazität)

Heute sortiert die Liste nach Frist oder Wert. **Nach Rendite zu sortieren wäre die
Kernfunktion des Produkts** — und jede einzelne Zutat liegt vor.

### C2 · Partner-Bedarf
**UI: Partner**

```
Partner-Bedarf  =  1 − (MaximumLotsAwardedNumeric ÷ n_lots)
```
gültig nur, wenn `CompanyLegalForm` eine Bietergemeinschaft zulässt.

12 Lose, höchstens 3 gewinnbar → 75 % des Auftrags brauchen Partner. Ergänzt um
`FrameworkAgreement.MaximumOperatorQuantity` (1 = winner-takes-all, 114 = fast jeder),
`SubcontractingTerm.TermPercent` (wer vergibt regelmäßig unter) und `CompanySizeCode`
(passt die Größe, ohne Konkurrent zu sein).

### C3 · Effektiver Markt
**UI: Liste (Umkreissuche)**

```
mein Markt  =  Leads in meinen Regionen  +  ALLE Leads mit RealizedLocation = anyw-cou
```

**4.144 Leads** sind bundesweit erbringbar und fallen heute durch die Umkreissuche. Das
ist kein neuer KPI, sondern ein **Fehler** — der Filter wirft passende Leads weg.

### C4 · Verfahrensrisiko je Vergabestelle
**UI: Vergabestelle**

`AppealRequestsStatistics` (14 % angegriffen) × `ProcedureRelaunchIndicator` ×
`TenderResultCode = clos-nw` (9 % ohne Gewinner) × `avg_decision_days` (Median 87 T).

*„Diese Stelle bricht jedes fünfte Verfahren ab und braucht im Schnitt 140 Tage."* Vier
schwache Einzelsignale, zusammen eine belastbare Ampel.

### C5 · Wiederkehr-Kalender mit Konfidenz
**UI: Chance**

Drei **unabhängige** Quellen für dieselbe Aussage:
1. `RecurringProcurementDescription` — der Käufer nennt den Termin selbst („IV. Quartal 2027")
2. `TIME_FRAME_SUBSEQUENT_CONTRACTS_MONTHS` — Intervall in Monaten (12 bei 56 %)
3. historische Kadenz aus `contract_succession` je Käufer × CPV

Stimmen zwei überein, ist die Prognose belastbar. Weichen sie ab, zeigt man die Spanne.
Das ist der Wiederkehr-Rhythmus, den die Profil-Skizze als Eigenleistung führt — mit dem
Unterschied, dass zwei der drei Quellen **wörtlich in den Daten stehen**.

### C6 · Preisniveau je Vergabestelle
**UI: Vergabestelle**

`INITIAL_ESTIMATED_TOTAL_VALUE` gegen `final_value` — beide auf derselben Notice bei
**10,7 %** (50.296 Zuschläge). *„Hier gewinnt man typisch 8 % unter Schätzwert."* Die
erste echte Preisintelligenz — aber auf schmaler Basis, deshalb nur je Vergabestelle mit
mindestens 5 Belegen.

### C7 · Nachtrags-Wachstum
**UI: Vergabestelle + Profil**

`ContractModification.ChangeReason = add-wss` (74–76 % der Nachträge) je Käufer, gegen
`INFO_MODIFICATIONS/VAL_TOTAL_AFTER`. *„Bei dieser Stelle wachsen Aufträge im Schnitt um
X %"* — verändert den wahren Auftragswert und ist ein Beziehungssignal: wer drin ist,
wächst mit.

### C8 · Käufer-Zwillinge
**UI: Vergabestelle + Chance**

`ContractingPartyType` × `ContractingActivity` × CPV-Mix × `total_awards` × `main_nuts3`.
Beantwortet Frage 4D der Profil-Skizze: *„Vergabestellen wie eure bestehenden Kunden, bei
denen ihr noch nicht seid."* Beide Codelisten liegen bei ~100 % über die **gesamte
Historie**, nicht erst ab 2024.

### C9 · Eignungs-Match
**UI: Bewertung**

`SelectionCriteria.TendererRequirementTypeCode` (32 Codes) gegen das hinterlegte
Firmenprofil. *„Du erfüllst 4 von 5 Anforderungen — es fehlt ISO 14001."* Der Sprung von
der Liste zur Empfehlung. Setzt voraus, dass der Nutzer sein Profil pflegt — genau der
Handel, den die Profil-Skizze unter „Bestand-Pflege" vorschlägt.

### C10 · eSender-Netzwerk
**UI: Neu**

`SENDER/LOGIN` × Käufer × CPV. Ein Büro, das als eSender auftritt, betreut laufend
Vergaben für mehrere Stellen. Eine Beziehung, viele Leads — ein **eigener Lead-Typ**,
den es im Produkt heute nicht gibt.

### C11 · Förderwelle
**UI: Markt**

`SettledContract.Funding.FundingProgramCode` (ERDF, ERDF_2021, JTF) × CPV × Region × Zeit.
Förderprogramme lösen Ausschreibungswellen aus. Aus der Historie ableitbar: *„Nach
Programmstart X folgten im Gewerk Y innerhalb von 18 Monaten Z Ausschreibungen."*

---

## Priorisierung

| # | Cross-KPI | Status | Aufwand | Wirkung |
|---|---|---|---|---|
| 1 | **Aufwand-Rendite** (C1) | vorgeschlagen | hoch | **Kernfunktion** — Sortierung der Liste |
| 2 | **Einstiegsschwelle** (A3) | gemessen | niedrig | 2.401 Leads werden für KMU sichtbar |
| 3 | **Effektiver Markt / anyw-cou** (C3) | gemessen | niedrig | behebt einen **Fehler** |
| 4 | **Erwartete Bieterzahl** (A1) | gemessen | mittel | schließt die 0-%-Blindstelle |
| 5 | **Preisdruck vs. Hürde** (A2) | gemessen | niedrig | Angebotsstrategie |
| 6 | **Marktverschluss** (A4) | gemessen | niedrig | spart Aufwand + Kalendereintrag |
| 7 | **Quellen-Arbitrage** (A5) | gemessen | niedrig | Verkaufsargument |
| 8 | Käufer-Zwillinge (C8) | vorgeschlagen | mittel | schließt Design-Frage 4D |
| 9 | Wiederkehr-Kalender (C5) | vorgeschlagen | mittel | Frühindikator |
| 10 | Partner-Bedarf (C2) | vorgeschlagen | hoch | Produktsprung |

Die Plätze 2, 3, 5, 6 und 7 sind **gemessen und billig** — zusammen vermutlich zwei
Arbeitstage, und sie verändern die Liste spürbar.
