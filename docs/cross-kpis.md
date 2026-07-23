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

---

# Zweite Runde (2026-07-23)

Weitere Kombinationen, entlang von Achsen, die in Runde 1 nicht gekreuzt wurden: **Zeit**,
**Konzernstruktur**, **Losvergabe-Realität** und **Herkunft der Bieter**.

## D · Gemessen — tragfähig

### D1 · „Lose nur auf dem Papier" ⭐⭐
**UI: Liste + Vergabestelle** · Zutaten: Losanzahl × Anzahl distinkter Gewinner je Vergabe

Losaufteilung gilt als Mittelstandsförderung. Gemessen an 33.664 Vergaben mit mindestens
drei Losen (ab 2018):

| Verteilung | Vergaben | Ø Lose | Ø Gewinner |
|---|---:|---:|---:|
| **alle Lose an EINEN** | **7.769** | 4,9 | 1,0 |
| stark gebündelt | 2.932 | 18,4 | 4,2 |
| teilweise gebündelt | 11.952 | 6,4 | 3,4 |
| breit gestreut | 11.011 | 4,8 | 4,7 |

**Bei 7.769 Vergaben war die Losaufteilung kosmetisch** — ein Bieter nahm alles. Je
Vergabestelle aggregiert: 215 Stellen mit ≥5 Mehrlos-Vergaben, im Schnitt gehen **24,7 %**
komplett an einen, **bei 26 Stellen ist das die Mehrheit**.

Zwei Aussagen: für den Bieter *„hier bringt dir das Bieten auf ein einzelnes Los nichts"*,
für die Vergabestellen-Analyse *„diese Stelle teilt formal auf, vergibt aber gebündelt."*
Das ist die direkte Gegenprobe zur Einstiegsschwelle (A3) — beide zusammen ergeben erst
ein ehrliches Bild.

### D2 · Konzern-Kannibalisierung (Scheinwettbewerb)
**UI: Markt** · Zutaten: `entity_identity` (Konzerngruppen) × `buyer_contractor_history`

**4.138 Fälle**, in denen bei **einem** Käufer mehrere Firmen **derselben Konzerngruppe**
gewinnen — betrifft **18.058 Siege**. Der beobachtete Wettbewerb ist dort teilweise
konzernintern.

Relevanz: Ein KPI „5 verschiedene Auftragnehmer, gesunder Wettbewerb" ist falsch, wenn drei
davon zum selben Konzern gehören. Der Fund knüpft direkt an die Erkenntnis aus dem
Nachfolge-Modell an (naiv gerechnet ergäbe Siemens AG ↔ Siemens Mobility eine Verdrängung,
die keine ist).

### D3 · Ausländischer Wettbewerb je Gewerk
**UI: Markt** · Zutaten: `num_tenders_other_eu` × CPV-Division

| CPV | Vergaben | mit EU-Bietern | Ø Bieter |
|---|---:|---:|---:|
| 18 Bekleidung | 389 | **32,9 %** | 4,4 |
| 35 Sicherheit/Verteidigung | 591 | **28,3 %** | 2,1 |
| 77 Land-/Forstwirtschaft | 1.242 | 16,1 % | 5,8 |
| 39 Möbel | 711 | 13,4 % | 3,6 |
| 33 Medizin | 751 | 10,8 % | 2,8 |
| 34 Fahrzeuge | 1.822 | 10,5 % | 2,2 |

Bau liegt bei nahezu null. *„In deinem Gewerk bietet in jedem dritten Verfahren ein
ausländisches Unternehmen mit"* ist eine Aussage über das Preisniveau, die ein Anbieter
nirgends bekommt.

### D4 · Auslauf-Dichte je Gewerk, Region und Quartal
**UI: Chance** · Zutaten: `contract_end` × CPV-Division × `market_nuts3` × Quartal

19.956 Zellen in den nächsten drei Jahren, Ø 3,2 auslaufende Verträge je Zelle,
**2.733 Zellen mit mindestens fünf**, Maximum **485 in einem Quartal**.

Das ist Kapazitätsplanung: *„Q2/2027 laufen in deinem Gewerk und deiner Region 14 Verträge
aus — bereite dich jetzt vor."* Ein einzelner auslaufender Vertrag ist ein Lead; vierzehn
im selben Quartal sind eine Personalentscheidung.

---

## E · Gemessen und verworfen

### E1 · Elektronik-Reifegrad der Vergabestelle ❌
`num_tenders_electronic ÷ num_tenders` seit 2020: **93,6 % vollelektronisch**, nur 3,1 %
gar nicht. Der Indikator war 2018 vielleicht ein Differenzierer, heute ist er es nicht mehr.

### E2 · Bearbeitungsdauer × Wettbewerbslage ❌
`avg_decision_days` je `competition_flag`: 98 · 106 · 106 · 109 Tage. **Flach.** Die
Kreuzung bringt nichts gegenüber dem Median allein. Die Bearbeitungsdauer als solche bleibt
nützlich (Median 87–91 Tage), aber nicht als Kombination.

### E3 · Bürgschaft × Gewinnergröße ❌ (strukturell)
`RequiredFinancialGuarantee` steht in der **Ausschreibung**, `CompanySizeCode` im
**Zuschlag**. Beide existieren in eForms (108.585 bzw. 140.690 Notices), aber die
Verkettung über `award_tender_link` findet **keine einzige** Überschneidung.

Verallgemeinert: **manche Cross-KPIs scheitern nicht an der Idee, sondern daran, dass ihre
Zutaten auf verschiedenen Dokumenten liegen und die Verkettung sie nicht zusammenbringt.**
Das ist vor dem Bauen zu prüfen, nicht danach.

### E4 · Käufer-Bindungsgrad ⚠️ (Messfehler meinerseits)
Klassifiziert nach `wins_total ÷ n_contractors` — dabei misst die Kennzahl in Wahrheit die
**Käufergröße** (die „stark gebundene" Gruppe hat Ø 168 Auftragnehmer). Verwertbar ist nur
der Einzelbieter-Gradient: 60,5 % bei Stellen mit genau einem Auftragnehmer gegen 20,7 %
bei stark rotierenden. Die Kennzahl braucht eine Normierung auf die Käufergröße.

---

## F · Weitere Vorschläge, noch ungetestet

| # | Cross-KPI | Zutaten | UI |
|---|---|---|---|
| F1 | **Termin-Kollision** — „diese Woche kollidieren 4 Fristen in deiner Merkliste" | `deadline_date` über die eigene Liste × `TenderValidityPeriod` | Liste + Team |
| F2 | **Kapitalbindung** — Zahlungsbedingungen × Laufzeit × Wert: „12 Monate Vorleistung bei 500 k" | `PaymentTerms` / `MAIN_FINANCING_CONDITIONS` × `duration_months` × Wert | Bewertung |
| F3 | **Schätzwert-Treffsicherheit → Abbruchrisiko** — Stellen, die systematisch zu niedrig schätzen, heben häufiger auf | `INITIAL_ESTIMATED_VALUE` vs. Marktmedian × `retender_signal` | Vergabestelle |
| F4 | **Marktanteils-Verschiebung** — „Firma X kam von 5 % auf 22 % in drei Jahren" | `contractor_stats` über rollende Fenster | Markt + Position |
| F5 | **CPV-Drift des Käufers** — „diese Stelle beschafft zunehmend IT statt Bau" | CPV-Mix je Käufer über Zeit | Vergabestelle |
| F6 | **Verfahrensart × Gewinnergröße** — „bei Verhandlungsverfahren gewinnen überwiegend Große" | `procedure_type` × `CompanySizeCode` | Markt |
| F7 | **Frist-Verschiebungs-Rate** — „diese Stelle verschiebt jede dritte Frist" | `Changes` mit Friständerung je Käufer | Vergabestelle |
| F8 | **Grenzüberschreitungs-Signal** — 13-sprachige Veröffentlichung als Absicht | `FORM_LG_LIST` × Wert × CPV | Markt |
| F9 | **Komplexitäts-Index in Personentagen** — Beschreibungstiefe + Losanzahl + Anzahl Eignungskriterien + Lebenslauf-Pflicht | mehrere | Bewertung |
| F10 | **Vergabekammer-Zuständigkeit** — welche Kammer, wie schnell entscheidet sie | `AppealReceiverParty` × `AppealRequestsStatistics` | Vergabestelle |

F1 ist der billigste und unmittelbar spürbar: er braucht **kein einziges neues Feld**,
nur eine Auswertung über die Merkliste des Nutzers.
