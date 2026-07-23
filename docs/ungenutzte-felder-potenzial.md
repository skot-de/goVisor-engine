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
| `CallForTendersDocumentReference.DocumentType` | **54,2 %** | **non-restricted 97 %** · restricted 3 % | **97 % der Vergabeunterlagen sind frei zugänglich.** Das relativiert unsere frühere Aussage, der Inhalt liege unerreichbar hinter dem Portal — er liegt hinter einem *offenen* Link. |
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
