# Was in den ungenutzten Rohfeldern steckt

Ausgangslage: von **1.585 eForms-Pfaden nutzen wir 516**. Diese Liste geht die **632
offenen Sachdaten-Pfade** durch (ohne XML-Attribute) und bewertet jeden nach Verkaufswert.
Alle Prozentzahlen sind Abdeckung über die Notices, gemessen 2026-07-23 an 2025er-Daten.

Sortiert nach **Verkaufsargument**, nicht nach Abdeckung — ein Feld mit 8 % Abdeckung, das
eine Kaufentscheidung auslöst, schlägt eines mit 54 %, das niemanden interessiert.

---

## A · Partner-Netzwerk — der stärkste Cluster

Sieben Felder, die zusammen ein Produkt ergeben, das es sonst nirgends gibt: **wer muss
sich mit wem zusammentun, um diesen Auftrag zu gewinnen.**

| Feld | Abd. | Werte | Verkaufsargument |
|---|---:|---|---|
| `LotDistribution.MaximumLotsAwardedNumeric` | **7,7 %** | 2 (42 %) · 3 (21 %) · 4 (11 %) | **Der Auslöser.** Eine 10-Los-Ausschreibung, bei der ein Bieter höchstens 2 Lose gewinnen darf, *erzwingt* Partner. Wer das vorher weiß, baut das Konsortium — wer es übersieht, bietet auf 10 und gewinnt 2. |
| `MaximumLotsSubmittedNumeric` | 7,9 % | 2 (41 %) · 3 (20 %) | Wie viele Lose man überhaupt anbieten *darf* — begrenzt den Aufwand und die Strategie. |
| `TendererQualificationRequest.CompanyLegalForm` | 8,6 % | „gesamtschuldnerisch haftend mit bevollmächtigtem Vertreter" (17 %) | **Die Bietergemeinschafts-Klausel im Klartext.** Sagt, ob und unter welcher Haftung ein Konsortium bieten darf. Ohne das ist jede Partnerempfehlung Raten. |
| `SubcontractingTerm.TermCode` | 30,3 % | no 70 % · not-known 26 % · **yes 4 %** | Wurde tatsächlich untervergeben. Rückwärts gelesen: **welche Firmen arbeiten mit Subunternehmern** — die Kandidatenliste fürs Netzwerk. |
| `VariantConstraintCode` | 53,9 % | not-allowed 92 % · **allowed 8 %** | Nebenangebote. Die 8 % sind die Ausschreibungen, in denen ein *anderer* Lösungsweg gewinnen kann — genau dort lohnt ein Partner mit anderer Technologie. |
| `Organization.Company.CompanySizeCode` | **32,5 %** | medium 36 % · small 31 % · large 25 % · micro 9 % | **Firmengröße des Gewinners.** Erlaubt den KPI „bei dieser Vergabestelle gewinnen zu 67 % KMU" — die ehrlichste Annäherung an „spiele ich hier in der richtigen Liga". |
| `EconomicOperatorShortList.Maximum/MinimumQuantity` | 6,9 / 5,8 % | min 3 (82 %) · max 5 (60 %) | Bei nicht-offenen Verfahren: **wie viele werden eingeladen.** Eine echte Wahrscheinlichkeit statt eines Gefühls. |

**Produktidee:** ein Reiter *Partner* am Lead. „Diese Ausschreibung hat 12 Lose, du darfst
höchstens 3 gewinnen. Bietergemeinschaft ist zugelassen (gesamtschuldnerisch). Diese
6 Firmen haben in deiner Region CPV-benachbarte Lose gewonnen und sind klein genug, um
nicht mit dir zu konkurrieren." Datenbasis dafür ist **vollständig vorhanden**:
`cpv_adjacency` (40.716 Kanten) × `lead_lot` × `CompanySizeCode` × diese Felder.

---

## B · Angebots-Aufwand — „lohnt sich das für mich?"

Der Kern der Lead-Qualifikation, den wir heute nur über CPV und Wert beantworten.

| Feld | Abd. | Werte | Verkaufsargument |
|---|---:|---|---|
| `SelectionCriteria.TendererRequirementTypeCode` | **24,4 %** | 32 Codes: `slc-abil-ref-services`, `slc-suit-reg-trade`, `slc-stand-ins` … | **Typisierte Eignungskriterien.** Heute haben wir nur Freitext. Codiert wird daraus ein Filter: „zeig mir nur Aufträge, deren Anforderungen ich erfülle". Das ist der Sprung von *Liste* zu *Empfehlung*. |
| `RequiredCurriculaCode` | 32,6 % | not-requ 64 % · **t-requ 24 %** | Lebensläufe gefordert? Bei 24 % ja — das sind mehrere Personentage Angebotsaufwand mehr. |
| `TenderValidityPeriod.DurationMeasure` | 39,7 % | 60 Tage (17 %) | **Bindefrist** = wie lange Kapazität gebunden bleibt. Für einen Mittelständler ein echter Kostenfaktor. |
| `AdditionalInformationRequestPeriod.EndDate` | **24,9 %** | — | **Frist für Bieterfragen.** Liegt immer vor der Angebotsfrist und wird ständig verpasst. Ein eigener Alert-Typ. |
| `OpenTenderEvent.OccurrenceDate/Time` | 34,0 % | 10:00 Uhr (15 %) | Submissionstermin (öffentliche Angebotsöffnung) — bei VOB-Verfahren darf man dabei sein und sieht die Konkurrenz. |
| `SubmissionMethodCode` | 54,2 % | required 70 % · allowed 29 % | Elektronische Abgabe Pflicht → Portal-Registrierung nötig, dauert. |
| `CallForTendersDocumentReference.DocumentType` | **54,2 %** | non-restricted 97 % · restricted 3 % | ⚠️ **KORREKTUR (2026-07-23):** BT-14 heisst „nicht **rechtlich** beschraenkt" (kein Verschlusssachen-Vorbehalt) — **nicht** „ohne Konto ladbar". An fuenf Plattformen geprueft: dtvp/Cosinex und Brandenburg verlangen die Bestaetigung der Verfahrensteilnahme, RIB liefert nur die eigenen AGB, subreport und evergabe.de sind JS-Anwendungen mit Formular davor. Kein Verkaufsargument. Der **Link selbst** ist eines (s. Nachtrag). |
| `ContractExtension.MaximumNumberNumeric` | 3,7 % | 0 (59 %) · 2 (18 %) · 1 (15 %) | Zahl der Verlängerungsoptionen → echter Vertragswert über die Grundlaufzeit. |

---

## C · Rechtsrahmen — segmentiert die Kundschaft

| Feld | Abd. | Werte | Verkaufsargument |
|---|---:|---|---|
| `RegulatoryDomain` | **54,2 %** | 32014L0024 (48 %) · **de-vob (37 %)** · de-vol (6 %) · 32014L0025 (4 %) | **VOB gegen VgV gegen SektVO.** Ein Bauunternehmer will nur VOB-Verfahren sehen, ein IT-Dienstleister nur VgV. Ein Ein-Klick-Filter, der die halbe Liste wegräumt. |
| `ProcurementLegislationDocumentReference.ID` | 53,9 % | vgv 53 % · vob-a-eu 30 % · sektvo 8 % | Dasselbe feiner, inkl. `CrossBorderLaw` (7 %). |
| `ContractingSystem.ContractingSystemTypeCode` | 38,3 % | none 89 % · **fa-wo-rc 9 %** · fa-mix 1 % | Rahmenvereinbarung **ohne** erneuten Wettbewerb = wer drin ist, ruft ab; wer draußen ist, hat Jahre keine Chance. Das ändert die Dringlichkeit komplett. |
| `ProcedureRelaunchIndicator` | 5,0 % | false 100 % · true 0,4 % | Wiederholung eines gescheiterten Verfahrens — ergänzt unser `retender_signal` mit einem **amtlichen** Flag statt einer Rekonstruktion. |

---

## D · Käufer-Segmentierung — beantwortet Frage 4 der Profil-Skizze

| Feld | Abd. | Werte | Verkaufsargument |
|---|---:|---|---|
| `ContractingPartyType.PartyTypeCode` | **50,6 %** | la 34 % · body-pl-la 13 % · pub-undert 10 % · ra 10 % | **Art der Vergabestelle** (Kommune / Land / öffentliches Unternehmen). |
| `ContractingActivity.ActivityTypeCode` | **54,1 %** | gen-pub 57 % · health 11 % · econ-aff 6 % · education 5 % · rail 4 % | **Tätigkeitsfeld der Behörde.** |

Zusammen mit `main_nuts3`, `total_awards` und dem CPV-Mix aus `buyer_profile` ist das
**genau das Käufer-Ähnlichkeitsmaß**, das die Profil-Skizze unter „4D · Ähnliche
Auftraggeber" als offene Frage geführt hat. Verkaufsargument: *„Vergabestellen wie eure
bestehenden Kunden, bei denen ihr noch nicht seid."* Beide Achsen liegen seit Jahren in
den Daten und wurden nie gelesen.

---

## E · Wettbewerb und Ergebnis

| Feld | Abd. | Werte | Verkaufsargument |
|---|---:|---|---|
| `LotResult.TenderResultCode` | **36,4 %** | selec-w 89 % · **clos-nw 9 %** · open-nw 2 % | „Kein Gewinner" **je Los**, amtlich. Unser `verfahren_status='erfolglos'` ist heute erschlossen — das hier ist die Quelle. |
| `LotTender.RankCode` | 6,0 % | 1 (95 %) · 2 (2 %) · 3 (1 %) … bis 6 | **Rang der Angebote.** 651 Notices tragen einen Rang > 1 — also *einen* unterlegenen Bieter. Zu wenig für eine Gewinnquote, aber „wer wurde Zweiter" ist gelegentlich sichtbar. Korrigiert meine frühere Aussage, Verliererdaten gebe es strukturell nicht. |
| `ReceivedSubmissionsStatistics` | 36,2 % | 0 (37 %) · 1 (15 %) · 2 (11 %) | Bieterstatistik je Los — feiner als unser `num_tenders` auf Notice-Ebene. |
| `ContractModification.ChangeReason.ReasonCode` | 7,2 % | **add-wss 74 %** · mod-cir 25 % | **Nachträge.** „Dieser Auftrag wurde nachträglich um Leistungen erweitert" — ein Beziehungs- *und* Volumensignal: wer drin ist, wächst mit. |
| `FieldsPrivacy.FieldIdentifierCode` | 4,2 % | win-ten-val 66 % · win-ten-var 34 % | **Warum ein Feld leer ist.** Statt „unbekannt" steht dort: „Wert zurückgehalten, Grund: Geschäftsgeheimnis". Ehrlichkeit als Feature — passt exakt zu unseren Herkunfts-Flags. |
| `Organization.UltimateBeneficialOwner.ID` | 22,4 % | UBO-0001 (77 %) | Wirtschaftlich Berechtigter des Gewinners → Konzernauflösung ohne Handelsregister. |
| `Changes.ChangeReason.ReasonCode` | 10,7 % | update-add 52 % · cor-buy 31 % | Berichtigungen — „diese Ausschreibung wurde nach Veröffentlichung geändert, Frist beachten". |

---

## F · Kleiner, aber verkaufbar

| Feld | Abd. | Verkaufsargument |
|---|---:|---|
| `RealizedLocation.Address.Region` | 5,2 % | `anyw-cou` 65 % · `anyw` 30 % — **ortsunabhängig zu erbringen.** Für Dienstleister der Unterschied zwischen „nicht meine Region" und „egal wo ich sitze". Unsere Radius-Suche filtert diese Leads heute fälschlich weg. |
| `PlannedPeriod.StartDate` / `EndDate` | 34,3 / 33,9 % | Geplanter Vertragsbeginn und -ende **aus der Ausschreibung** statt geschätzt — hebt `duration_source` von „geschätzt" auf „echt". |
| `StrategicProcurement.…InformationCode` | 1,0 % | `veh-acq`, `pass-tran-serv` — Clean-Vehicles-Richtlinie. Winzig, aber wer E-Busse verkauft, will genau diese Liste. |
| `FrameworkAgreement.SubsequentProcessTenderRequirementCode` | 3,8 % | `buyer-categories` — Abrufmechanik der Rahmenvereinbarung. |
| `ContractExecutionRequirement.ExecutionRequirementCode` | 5,8 % | Ausführungsbedingungen (Tariftreue, Nachhaltigkeit). |
| `TenderRecipientParty` / `TenderEvaluationParty` | 31,6 / 7,5 % | Wer nimmt entgegen, wer bewertet — nicht immer die ausschreibende Stelle. |

---

## Was ich NICHT weiterverfolgen würde

Rund 400 der 632 offenen Pfade sind technische Metadaten ohne Verkaufswert:
`UBLVersionID`, `ContractFolderID`, `IssueTime`, `GazetteID`, `NoticePublicationID`,
`CustomizationID`, `ProfileID`, sämtliche `ORG-000x`-Referenz-IDs (die sind nur
dokumentinterne Zeiger und werden über `notice_parties` bereits aufgelöst) sowie die
`RES-`/`TPA-`/`CON-`/`TEN-`-IDs der eForms-Ergebnisstruktur.

**Ein Datenfund am Rande:** `TenderResult.AwardDate` trägt in **33 % der Fälle den
Platzhalter `2000-01-01`**. Unser Parser liest einen anderen Pfad — im Silber sind 0 von
494.361 `award_date` betroffen. Wichtig zu wissen, falls jemand die Extraktion umstellt.

---

## Empfohlene Reihenfolge

1. **Cluster D** (2 Felder, ~52 % Abdeckung) — beantwortet eine offene Design-Frage,
   kostet einen Parser-Zusatz und zwei Spalten. Bestes Verhältnis im ganzen Dokument.
2. **Cluster C, `RegulatoryDomain`** (54 %) — ein Filter, der für Bauunternehmer die
   halbe Liste wegräumt. Ein Feld, sofort spürbar.
3. **Cluster A** (Partner-Netzwerk) — der eigentliche Produktsprung, aber sieben Felder
   und ein neues UI. Sobald das Netzwerk-Thema ansteht.
4. **`SelectionCriteria.TendererRequirementTypeCode`** (24 %) — der Weg von der Liste zur
   Empfehlung, aber 32 Codes wollen sauber abgebildet werden.

---

# Nachtrag: vollständiger Durchgang (2026-07-23)

Der erste Durchgang oben war **unvollständig** und beruhte auf einer fehlerhaften Messung.
Zwei Fehler im Inventar:

- Die Stichprobe lief ab 2024 → die Legacy-Auswertung beruhte auf **1.602 von 1.154.568**
  Notices (0,14 %), `text` (246.908) und `ojs` (3.232) fehlten ganz.
- Die Silber-Seite des Wert-Joins filterte weiterhin auf `year >= 2024`, während die
  Stichprobe alle Jahre umfasste → `text` und `ojs` zeigten „0 genutzt" als **Artefakt**.

Korrigiert sind es **4.123 ungenutzte Sachdaten-Pfade** (nicht 632), verteilt auf
legacy 2.452 · ojs 1.010 · eforms 478 · doe 163 · text 20.

## DÖE (163 Pfade, vollständig)

| Feld | Abd. | Wert · Nutzung |
|---|---:|---|
| **`CallForTendersDocumentReference.Attachment.ExternalReference.URI`** | **96,9 %** | Direktlink zum Auftrag auf der Vergabeplattform. Unser `portal_url` ist bei DÖE zu **0 %** gefüllt — wir lesen seit jeher das schlechtere Feld. **Sofort baubar.** |
| `RegulatoryDomain` | 84,2 % | de-vob 53 % · **de-uvgo 39 %** · de-vol 6 %. Der Filter, mit dem ein Bauunternehmer 39 % wegräumt. |
| `TP.ProcedureCode` | 84,2 % | de-open 94 % — Verfahrensart unterschwellig. |
| **`RequiredFinancialGuarantee.GuaranteeTypeCode`** | **59,7 %** | **provisional 53 %** · none 47 %. Bietungsbürgschaft = Kapitalhürde. Ein K.-o.-Kriterium, das man vor dem Angebot kennen will. |
| **`TendererQualificationRequest.CompanyLegalForm`** | **43,7 %** | Bietergemeinschafts-Klausel im Klartext — **7× besser gefüllt als in eForms (5,8 %)**. Fürs Partner-Netzwerk ist der Unterschwellenmarkt die bessere Datenbasis. |
| `VariantConstraintCode` | 59,7 % | allowed **19 %** (eForms nur 6 %) |
| `MultipleTendersCode` | 26,2 % | true 38 % |
| `EXT/Change.ChangeReason.ReasonCode` | 16,8 % | update-add 75 % · **cancel 25 %** — Aufhebung, amtlich. |
| `RealizedLocation.Address.CityName` | 24,5 % | Leistungsort als Ortsname; wir haben bisher nur NUTS. |
| `Proj.Note` | 56,2 % | Freitext Ausführungszeitraum |
| `SecurityClearanceTerm.Code` | 26,2 % | Sicherheitsüberprüfung (1 % ja) |
| `OpenTenderEvent.Description` | 7,7 % | „gemäß §14 VOB/A sind keine Bieter zugelassen" — Submissionsteilnahme |

**Parser-Fehler dabei gefunden und behoben:** DÖE-Käuferkontakte waren zu **0 %** gefüllt
(258.246 Zeilen), obwohl E-Mail/Telefon/Web im XML zu 60 / 48 / 39 % stehen. Nach dem Fix
94 % E-Mail.

## eForms (478 Pfade, vollständig)

Zusätzlich zu den oben schon genannten Clustern:

### Wert — wir haben nur 9 % `estimated_value`

| Feld | Abd. | Nutzung |
|---|---:|---|
| **`RequestedTenderTotal.EXT/FrameworkMaximumAmount`** | 1,8 % (CN) · 1,2 % (Los) | **Höchstwert der Rahmenvereinbarung** — Werte bis 146.326.846 €. Bei Rahmenverträgen ist das der einzige belastbare Volumenanker, und wir haben ihn nicht. |
| `OverallApproximateFrameworkContractsAmount` | 1,1 % | Gesamtvolumen aller Abrufe |
| `FrameworkAgreementValues.ReestimatedValue` | 1,2 % | nachträglich korrigierter Wert |

### Wettbewerbe — eine eigene Zielgruppe (Architektur, Planung)

| Feld | Abd. | Nutzung |
|---|---:|---|
| **`AwardingTerms.Prize.ValueAmount`** | 0,1 % | **Preisgeld** (30.000 €, 5.250 €). Für ein Architekturbüro *die* Zahl. |
| `AwardingTerms.Prize.RankCode` / `.Description` | 0,1 % | Preisstaffel |
| **`AwardingTerms.TechnicalCommitteePerson.FamilyName`** | 0,1 % | **Die Preisrichter namentlich.** Wer die Jury kennt, weiß, ob sich die Teilnahme lohnt. |
| **`EconomicOperatorShortList.PreSelectedParty.PartyName`** | 0,1 % | **Wer bereits eingeladen ist, namentlich** („Cityförster, Hannover mit TREIBHAUS…"). Direkte Wettbewerbsaufklärung. |
| `AwardingTerms.FollowupContractIndicator` | 0,2 % | true **42 %** — Folgeauftrag in Aussicht |
| `AwardingTerms.BindingOnBuyerIndicator` | 0,2 % | true 42 % — Jury-Entscheid bindend? |

### Partner-Netzwerk — Ergänzung zu Cluster A

| Feld | Abd. | Nutzung |
|---|---:|---|
| **`FrameworkAgreement.MaximumOperatorQuantity`** | 3,9 % | **1 (44 %)** · 114 (21 %) · 5 (8 %). Wie viele Firmen in die Rahmenvereinbarung kommen — bei „1" gewinnt einer alles, bei „114" kommt fast jeder rein. Eine echte Wahrscheinlichkeit. |
| `SubcontractingTerm.TermPercent` / `.TermAmount` | 0,2 % | **Wie viel wurde untervergeben** — 21 %, 30 %, 6.295.445 €. Wer regelmäßig untervergibt, ist Partner-Kandidat. |
| `TenderSubcontractingRequirements` | 0,1 % | `shar-subc` 67 % — Untervergabe-Anteil vorgeschrieben |
| `AllowedSubcontractTerms.SubcontractingConditionsCode` | 0,1 % | Bedingungen für Nachunternehmerwechsel |

### Wiederkehr — der Frühindikator

| Feld | Abd. | Nutzung |
|---|---:|---|
| **`RecurringProcurementDescription`** | 1,0 % (Los) · 0,5 % (Notice) | **„Schülerbeförderung", „IV. Quartal 2027"** — der Käufer sagt selbst, wann es wiederkommt. Das ist die Wiederkehr-Prognose ohne Modell. |
| `PIN.PlannedDate` | 0,7 % | Geplantes Veröffentlichungsdatum der eigentlichen Ausschreibung |
| `Changes.Change.ProcurementDocumentsChangeDate` | 1,1 % | **Unterlagen wurden geändert** — eigener Alert |

### KMU-Eignung

| Feld | Abd. | Nutzung |
|---|---:|---|
| `PIN.Proj.SMESuitableIndicator` | 0,4 % | **true 57 %** — „für KMU geeignet", amtlich |
| `PIN.LOT/Proj.Note` | 0,4 % | `#Besonders geeignet für:selbst#` / `#other-sme#` |

### Risiko und Nachhaltigkeit

| Feld | Abd. | Nutzung |
|---|---:|---|
| **`AppealRequestsStatistics.StatisticsNumeric`** | 0,3 % | 0 (86 %) · **1 (14 %)** — **Nachprüfungsanträge**. „Diese Stelle wird angegriffen" = Verfahrensrisiko. |
| **`ProcurementAdditionalType.ProcurementTypeCode`** | **53,3 %** | none 83 % · **env-imp 3 %** · **soc-obj 2 %** — Umwelt- und Sozialziele als Vergabekriterium |
| `StrategicProcurement.*` | 0,1–1 % | `veh-acq`, `vehicles-clean`, `vehicles-zero-emission`, Fahrzeugklassen m1/n1/n3, `enrg-lab`, `eed-spec`. Clean-Vehicles- und Energieeffizienz-Richtlinie — winzig, aber wer E-Busse verkauft, will genau diese Liste. |
| `SettledContract.Funding.FundingProgramCode` | 0,1 % | **ERDF · ERDF_2021 · JTF** — die Förderprogramme namentlich |

## ⚠️ Datenschutz: was NICHT ins Produkt gehört

`UltimateBeneficialOwner` (22–25 % Abdeckung) löst zwar Konzernstrukturen ohne
Handelsregister auf — trägt aber **`FirstName`, `ResidenceAddress` und
`Contact.Telefax`** natürlicher Personen. Die **Privatanschrift eines wirtschaftlich
Berechtigten** darf nicht ins Frontend. Verwendbar ist allenfalls die *Existenz* einer
UBO-Verknüpfung für die Konzernauflösung, nicht die Personendaten selbst.

Ebenso: `TechnicalCommitteePerson.FamilyName` (Preisrichter) ist eine berufliche
Funktionsangabe aus einer amtlichen Bekanntmachung — vertretbar. `UltimateBeneficialOwner`
ist es nicht.
