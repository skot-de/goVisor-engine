# Rohdaten-Potenzial — vollständige Auswertung

**Alle 4.123 ungenutzten Sachdaten-Pfade** über fünf Schema-Generationen, thematisch
geclustert. Gemessen 2026-07-23 gegen 1.832.998 DE-Notices (2004–2026).

Die Zuordnung „genutzt / ungenutzt" ist **gemessen, nicht aus dem Code gelesen**: für eine
Stichprobe je Generation und Jahr wird jeder Silber-Wert gegen jeden Rohwert derselben
Notice gejoint. Trifft ein Wert, ist der Pfad die Quelle.

| Generation | Zeitraum | Notices | Pfade | genutzt | **ungenutzte Sachdaten** |
|---|---|---:|---:|---:|---:|
| legacy | 2010–2024 | 1.154.568 | 4.622 | 1.156 | **2.452** |
| ojs | 2008 | 3.232 | 1.546 | 208 | **1.010** |
| eforms | 2023–2026 | 439.045 | 1.294 | 487 | **478** |
| doe | 2023–2026 | 384.034 | 364 | 132 | **163** |
| text | 2004–2010 | 246.908 | 31 | 11 | **20** |

Prozentangaben sind Abdeckung über die Notices **der jeweiligen Generation**.

---

## 1 · Käufer-Segmentierung — der größte Einzelfund

Zwei Achsen, die in **jeder** Generation bei nahezu 100 % liegen und in **keiner** gelesen
werden:

| Generation | Behördentyp | Tätigkeitsfeld |
|---|---|---|
| legacy | `CODIF_DATA.AA_AUTHORITY_TYPE` **100 %** — Regional/local 41 % · Body governed by public law 19 % · Utilities | `CODIF_DATA.MA_MAIN_ACTIVITIES` **99,3 %** — General public services 34 % · Health 11 % · Railway 6 % |
| eforms | `ContractingPartyType.PartyTypeCode` **50,6 %** — la 34 % · body-pl-la 13 % · pub-undert 10 % | `ContractingActivity.ActivityTypeCode` **54,1 %** — gen-pub 57 % · health 12 % · education 6 % |
| ojs | `BIB_DOC_S/MARKET_ORG` **100 %** | `BIB_DOC_S/MAIN_ACTIVITIES` **88,2 %** |
| text | — | `TEXT.MA` **52,5 %** — „S - Allgemeine öffentliche Verwaltung" 32 % |

**Warum das zählt:** Die Profil-Skizze führt „4D · Ähnliche Auftraggeber" als offene Frage
(*„Ist ein Käufer-Ähnlichkeitsmaß aus `buyer_profile` bildbar?"*). Antwort: ja, und die
beiden entscheidenden Achsen liegen **über die gesamte Historie** vor, nicht nur ab 2024.
Zusammen mit `main_nuts3`, `total_awards` und dem CPV-Mix ergibt das direkt:
*„Vergabestellen wie eure bestehenden Kunden, bei denen ihr noch nicht seid."*

Ergänzend: `CONTRACTING_BODY/CA_ACTIVITY_OTHER` (legacy, 2,7 %) und
`TYPE_AND_ACTIVITIES/TYPE_OF_ACTIVITY_OTHER` (1,0 %) tragen Freitext-Tätigkeiten
(„Straßenbau", „Forschung und Entwicklung") für die Fälle außerhalb der Codeliste.

---

## 2 · Zuschlagskriterien — auch historisch vorhanden

Wir haben die eForms-Kriterien heute gebaut (78 % Typ, 67 % Gewicht). Die groben
Vorgänger liegen in **jeder** Generation bei 100 %:

| Generation | Feld | Werte |
|---|---|---|
| legacy | `CODIF_DATA.AC_AWARD_CRIT` **100 %** | **Lowest price 45 %** · Most economic tender 39 % |
| ojs | `BIB_DOC_S/AWARD_CRIT` **100 %** | 2 (wirtschaftlichstes) 61 % · 1 (niedrigster Preis) 28 % |
| text | `TEXT.AC` **100 %** | „2 - Wirtschaftlichstes Angebot" 65 % · „1 - Niedrigster Preis" |

Damit lässt sich der KPI **„diese Vergabestelle entscheidet historisch zu X % rein über
den Preis"** über 20 Jahre bilden — nicht nur über die eForms-Jahre.

Feiner, ebenfalls ungenutzt:

- `CRITERIA_DEFINITION/CRITERIA` + `/WEIGHTING` + `/ORDER_C` (legacy, 9,1 %) — „Preis" 19 %,
  Gewichte 10/100/20/30. Eine zweite Legacy-Struktur neben `AC_PRICE`/`AC_QUALITY`, die
  unser Parser liest — **hier fehlt uns ein Teil der Kriterien.**
- `MAIN_FEATURES_AWARD/P` (legacy, 0,6 %) — Beschreibung der Gewichtungslogik.
- `CRITERIA_EVALUATION/P` (0,1 %), `OPE_OBJECTIVE_CRITERIA/P` (1,5 %) — Bewertungsverfahren.

---

## 3 · Partner-Netzwerk und Untervergabe

Der Cluster, aus dem ein eigenständiges Produkt wird. **Der Unterschwellenmarkt ist die
bessere Datenbasis** — die Bietergemeinschafts-Klausel ist dort siebenfach besser gefüllt.

### Bietergemeinschaft

| Generation | Feld | Abd. | Inhalt |
|---|---|---:|---|
| **doe** | `TendererQualificationRequest.CompanyLegalForm` | **43,7 %** | „gesamtschuldnerisch haftend mit bevollmächtigtem Vertreter" 51 % |
| legacy | `LEGAL_FORM/P` | **11,3 %** | dieselbe Klausel, 31 % |
| ojs | `LEGAL_FORM/P` | **33,3 %** | dieselbe Klausel, 45 % |
| eforms | `TendererQualificationRequest.CompanyLegalForm` | 5,8 % | |

### Los-Obergrenzen — der eigentliche Auslöser

| Feld | Gen. | Abd. | Werte |
|---|---|---:|---|
| `LotDistribution.MaximumLotsAwardedNumeric` | eforms | 5,8–7,7 % | **2 (34–42 %)** · 3 · 4 |
| `MaximumLotsSubmittedNumeric` | eforms | 6,0–7,9 % | 2 (37–41 %) · 3 |
| `LOT_DIVISION/LOT_MAX_ONE_TENDERER` | legacy | 0,5 % | 2 (41 %) · 3 (22 %) |
| `LOT_COMBINING_CONTRACT_RIGHT/P` | legacy | 0,3 % | „All lots will be awarded to one bidder" 18 % |
| `TY_TYPE_BID` / `TEXT.TY` / `BIB_DOC_S/TYPE_BID` | legacy/text/ojs | **100 %** | Submission for all lots 37 % · for one or more lots 3 % |

Eine 12-Los-Ausschreibung, bei der ein Bieter höchstens 3 Lose gewinnen darf, **erzwingt**
Partner. Das ist die konkreteste Kaufauslösung im ganzen Dokument.

### Untervergabe — wer arbeitet mit wem

| Feld | Gen. | Abd. | Inhalt |
|---|---|---:|---|
| `SubcontractingTerm.TermCode` | eforms/doe | 30,3–32,6 % | no 70 % · not-known 26 % · **yes 3–4 %** |
| `SubcontractingTerm.TermPercent` / `.TermAmount` | eforms | 0,2 % | **21 % · 30 % · 6.295.445 €** |
| `CONTRACT_LIKELY_SUB_CONTRACTED/EXCLUDING_VAT_PRCT` / `_VALUE` | legacy | 0,2 % | 30 % · 99 % · 12.500 € |
| `AWARDED_CONTRACT/PCT_SUBCONTRACTING` | legacy | 0,1 % | 14 % · 25 % |
| `TenderSubcontractingRequirements` | eforms | 0,1 % | `shar-subc` 67 % — Untervergabe **vorgeschrieben** |
| `AllowedSubcontractTerms.SubcontractingConditionsCode` | eforms | 0,1 % | Bedingungen für Nachunternehmerwechsel |
| `INFO_ADD_SUBCONTRACTING/P` | legacy | 0,1 % | Freitext |
| `ECONOMIC_OPERATORS_PERSONAL_SITUATION_SUBCONTRACTOR/P` | legacy | 0,2 % | Nachweise für Nachunternehmer |

### Wie viele kommen überhaupt rein

| Feld | Gen. | Abd. | Werte |
|---|---|---:|---|
| `FrameworkAgreement.MaximumOperatorQuantity` | eforms | 3,9 % | **1 (44 %)** · 114 (21 %) · 5 (8 %) |
| `FRAMEWORK/NB_PARTICIPANTS` | legacy | 0,3 % | 8 (30 %) · 999 (16 %) · 3 (15 %) |
| `SEVERAL_OPERATORS/MAX_NUMBER_PARTICIPANTS` | legacy | 0,2 % | 3 · 50 · 12 |
| `EconomicOperatorShortList.Min/MaximumQuantity` | eforms | 3,3–4,2 % | min 3 (63 %) · max 5 (63 %) |
| `MAXIMUM_NUMBER_INVITED/OPE_MIN/MAX/ENVISAGED_NUMBER` | legacy | 0,5–1,2 % | min 3 (82 %) · max 5 (67 %) |
| `OBJECT_DESCR/NB_MIN/MAX_LIMIT_CANDIDATE` | legacy | 1,4 % | 3 (69 %) / 5 (67 %) |
| **`EconomicOperatorShortList.PreSelectedParty.PartyName`** | eforms | 0,1 % | **Wer schon eingeladen ist, namentlich** |

`MaximumOperatorQuantity = 1` heißt winner-takes-all, `= 114` heißt fast jeder kommt rein.
Das ist eine echte Wahrscheinlichkeit statt eines Gefühls.

### Firmengröße des Gewinners

`Organization.Company.CompanySizeCode` (eforms, **32,5–37,2 %**): small 38 % · medium 30 % ·
large 26 % · micro 6 %. Erlaubt *„bei dieser Vergabestelle gewinnen zu 68 % KMU"* — die
ehrlichste Annäherung an die strukturell unmögliche Gewinnquote.

Historisch dazu: `TENDERS/NB_TENDERS_RECEIVED_SME` (legacy, 8,8 %) und
`AWARDED_CONTRACT/NB_TENDERS_RECEIVED_SME` (1,6 %) — wie viele **KMU geboten** haben.

---

## 4 · Wert und Volumen — wir haben nur 9 % `estimated_value`

| Feld | Gen. | Abd. | Inhalt |
|---|---|---:|---|
| **`RequestedTenderTotal.FrameworkMaximumAmount`** | eforms | 1,2–1,8 % | **Höchstwert der Rahmenvereinbarung**, bis 146.326.846 € |
| `EXT/FrameworkMaximumAmount` | eforms | 0,1 % | dasselbe auf Notice-Ebene |
| `OverallApproximateFrameworkContractsAmount` | eforms | 1,1 % | Gesamtvolumen aller Abrufe |
| `FrameworkAgreementValues.ReestimatedValue` | eforms | 1,2 % | nachträglich korrigiert |
| `NOTICE_DATA.VALUES_LIST.VALUES.SINGLE_VALUE.VALUE` | legacy | **15,2 %** | Wert (4.352 versch.) |
| `NOTICE_DATA.VALUES_LIST.VALUES.RANGE_VALUE.VALUE` | legacy | 1,5 % | Wertspanne |
| `COSTS_RANGE_AND_CURRENCY_WITH_VAT_RATE/VALUE_COST` | legacy | **9,9 %** | Wert inkl. MwSt |
| `INCLUDING_VAT/VAT_PRCT` | legacy | 6,6 % | 19 % (64 %) |
| **`INITIAL_ESTIMATED_TOTAL_VALUE_CONTRACT/VALUE_COST`** | legacy | 4,1 % | **ursprünglicher Schätzwert** — gegen den Zuschlagswert = Preisniveau je Stelle |
| `INFO_MODIFICATIONS/VAL_TOTAL_AFTER` | legacy | 0,5 % | Wert **nach** Nachtrag |
| `RANGE_VALUE_COST/HIGH_VALUE` / `LOW_VALUE` | legacy | 0,5 % | Spanne |
| `OBJECT_CONTRACT/VAL_ESTIMATED_TOTAL` | legacy | 0,1 % | |
| `PAYABLE_DOCUMENTS/DOCUMENT_COST` | legacy | **7,6 %** | Die Vergabeunterlagen **kosteten Geld** (25 € · 10 € · 30 €) |

Bei Rahmenverträgen ist `FrameworkMaximumAmount` der einzige belastbare Volumenanker — und
wir lesen ihn nicht. Legacy `SINGLE_VALUE.VALUE` bei 15,2 % würde die historische
Wert-Abdeckung spürbar heben (heute 55,8 % unbekannt).

---

## 5 · Fristen und Termine — mehrere eigene Alert-Typen

| Feld | Gen. | Abd. | Alert |
|---|---|---:|---|
| **`AdditionalInformationRequestPeriod.EndDate`** | eforms/doe | 13,8–24,9 % | **Frist für Bieterfragen** — liegt vor der Angebotsfrist und wird ständig verpasst |
| `OpenTenderEvent.OccurrenceDate` / `.OccurrenceTime` | eforms/doe | 9,6–34 % | **Submissionstermin** (öffentliche Angebotsöffnung) |
| `OpenTenderEvent.Description` | eforms/doe | 3,8–7,7 % | „gemäß §14 VOB/A sind keine Bieter zugelassen" — darf man dabei sein? |
| `EXISTENCE_AUTHORISED_PERSONS/P` | legacy | 7,4 % | „Bieter und ihre Bevollmächtigten" |
| `PLACE_OPENING/PLACE_NOT_STRUCTURED` | legacy | 0,3 % | **wo** die Öffnung stattfindet |
| `TenderValidityPeriod.DurationMeasure` | eforms/doe | 31,6–59,1 % | **Bindefrist** (60 Tage 15–21 %) = gebundene Kapazität |
| `MINIMUM_TIME_MAINTAINING_TENDER/PERIOD_DAY` / `_MONTH` | legacy | 0,3–0,4 % | dasselbe historisch |
| `ParticipationRequestReceptionPeriod.EndDate` | eforms/doe | 1,3–10,6 % | Teilnahmeantragsfrist |
| `InvitationSubmissionPeriod.StartDate` | eforms | 5,2 % | ab wann eingeladen wird |
| **`Changes.Change.ProcurementDocumentsChangeDate`** | eforms | 1,1 % | **Unterlagen wurden geändert** |
| `PROCEDURE/DATE_AWARD_SCHEDULED` | legacy | 0,3 % | geplantes Zuschlagsdatum |
| `CODIF_DATA.DD_DATE_REQUEST_DOCUMENT` | legacy | 12,7 % | Frist zur Unterlagen-Anforderung |
| `LatestSecurityClearanceDate` | eforms | 0,1 % | Frist für die Sicherheitsüberprüfung |
| `InterestExpressionReceptionPeriod.EndDate` | eforms (PIN) | 0,1 % | Interessensbekundungsfrist |

---

## 6 · Eignung und Aufwand — der Sprung von Liste zu Empfehlung

| Feld | Gen. | Abd. | Inhalt |
|---|---|---:|---|
| **`SelectionCriteria.TendererRequirementTypeCode`** | eforms | 9,1–24,4 % | **32 typisierte Codes**: `slc-abil-ref-services`, `slc-suit-reg-trade`, `slc-stand-ins`, `slc-stand-other` |
| `SelectionCriteria.Name` | eforms | 1,2 % | „Wirtschaftliche und finanzielle Leistungsfähigkeit" 21 % |
| `SelectionCriteria.CriterionParameter.*` | eforms | 2,1–3,3 % | Punktesystem der Eignungsprüfung |
| `RequiredCurriculaCode` | eforms | 29,9–32,6 % | **Lebensläufe gefordert?** t-requ 21–24 % |
| `ECONOMIC_OPERATORS_PERSONAL_SITUATION/P` | legacy/ojs | 13,0–37,3 % | Eignung, Freitext |
| `EAF_CAPACITY_INFORMATION/P` | legacy/ojs | 12,5–37,5 % | wirtschaftliche Leistungsfähigkeit |
| `T_CAPACITY_INFORMATION/P` | legacy/ojs | 12,2–37,9 % | technische Leistungsfähigkeit |
| `T_CAPACITY_MIN_LEVEL/P` / `EAF_CAPACITY_MIN_LEVEL/P` | legacy | 1,6–2,0 % | **Mindestanforderungen** („Zwingend:", „Referenzen über…") |
| `CRITERIA_CANDIDATE/P` | legacy | 1,9 % | Auswahlkriterien Teilnahmewettbewerb |
| `CRITERIA_SELECTION_PARTICIPANTS/P` | legacy | 0,1 % | dasselbe feiner |
| **`RequiredFinancialGuarantee.GuaranteeTypeCode`** | **doe** | **59,7 %** | **provisional 53 %** — Bietungsbürgschaft = Kapitalhürde |
| `RequiredFinancialGuarantee.Description` | eforms | 1,4–4,6 % | „Sicherheitsleistung für die Vertragserfüllung" |
| `DEPOSITS_GUARANTEES_REQUIRED/P` | legacy | 10,6 % | dasselbe historisch |
| `SecurityClearanceTerm.Code` / `.Description` | doe | 0,2–26,2 % | Sicherheitsüberprüfung / Verschwiegenheitserklärung |
| `PARTICIPATION_RESERVED_PROFESSION/P` | legacy | 0,1 % | Berufsvorbehalt |
| `EXECUTION_SERVICE_RESERVED_PARTICULAR_PROFESSION/P` | legacy | 1,0 % | PBefG u. ä. |
| `SubmissionMethodCode` | eforms/doe | 45,2–59,5 % | elektronische Abgabe Pflicht → Portal-Registrierung nötig |
| `DOCUMENT_METHOD_OF_PAYMENT/P` | legacy | 0,2 % | wie die Unterlagen zu bezahlen waren |

`TendererRequirementTypeCode` ist der Schlüssel: Freitext lässt sich nicht filtern, 32 Codes
schon. *„Zeig mir nur Aufträge, deren Eignungsanforderungen ich erfülle."*

---

## 7 · Verfahren und Rechtsrahmen — der Ein-Klick-Filter

| Feld | Gen. | Abd. | Werte |
|---|---|---:|---|
| **`RegulatoryDomain`** | doe | **84,2 %** | de-vob 53 % · **de-uvgo 39 %** · de-vol 6 % |
| **`RegulatoryDomain`** | eforms | 45,2–53,6 % | 32014L0024 76–90 % · **32014L0025 (Sektoren) 8–23 %** |
| `ProcurementLegislationDocumentReference.ID` | eforms | 43,7–53,9 % | vgv 39–53 % · vob-a-eu 20–30 % · sektvo 7–19 % · CrossBorderLaw |
| `CODIF_DATA.PR_PROC` | legacy | **100 %** | Open 69 % · Negotiated 10 % · Competitive w/ negotiation 6 % |
| `CODIF_DATA.RP_REGULATION` | legacy | **100 %** | GPA-Teilnahme 53 % |
| `TP.ProcedureCode` | doe | **84,2 %** | de-open 94 % |
| `BIB_DOC_S/PROC` | ojs | 100 % | |
| `TEXT.RP` / `TEXT.NC` | text | 100 % | Regelwerk / Auftragsart |
| `ContractingSystem.ContractingSystemTypeCode` | eforms | 38,3–46,5 % | none 87 % · **fa-wo-rc 9–11 %** (Rahmen ohne erneuten Wettbewerb) |
| `FrameworkAgreement.Justification` | eforms | 0,1–0,6 % | warum die Laufzeit so lang ist |
| `F02_FRAMEWORK/DURATION_FRAMEWORK_MONTH` | legacy | 0,4 % | 48 Monate 45 % |
| `ACCELERATED_PROC/P` | legacy | 0,4 % | Begründung beschleunigtes Verfahren |
| **`D_JUSTIFICATION/P`** | legacy | 1,5 % | **Begründung für die Direktvergabe** — die Aufträge ohne Wettbewerb |
| `REASON_CONTRACT_LAWFUL/P` · `ANNEX_D/REASON_CONTRACT_LAWFUL` | legacy | 0,1 % | dasselbe |
| `ProcessJustification.ProcessReason` / `.Description` | eforms/doe | 0,2–1,3 % | „§ 15 Abs. 4 VgV…" |
| `TITLE_QUALIFICATION_SYSTEM/P` | legacy | 0,3 % | **Präqualifikationsverfahren** — die Skizze wünschte sich PQ-Register |
| `RENEWAL_QUALIFICATION_SYSTEM/P` · `CONDITIONS/P` · `METHODS/P` | legacy | 0,1–0,3 % | PQ-Bedingungen |

`de-vob` gegen `de-uvgo` gegen `vgv` ist der Filter, der für einen Bauunternehmer die halbe
Liste wegräumt — bei **84 %** Abdeckung im Unterschwellenmarkt.

---

## 8 · Wettbewerbe — eine unbediente Zielgruppe

Für Architektur- und Planungsbüros ist der Wettbewerb das Kerngeschäft. Die Abdeckung ist
klein, aber **bezogen auf die Nische vollständig**:

| Feld | Gen. | Abd. | Inhalt |
|---|---|---:|---|
| **`AwardingTerms.Prize.ValueAmount`** | eforms | 0,1 % | **Preisgeld** (30.000 € · 5.250 €) |
| `AwardingTerms.Prize.RankCode` / `.Description` | eforms | 0,1 % | Preisstaffel |
| `AWARD_PRIZES/PARTICIPANTS_NUMBER` | legacy | 0,2 % | Teilnehmerzahl |
| `NUMBER_VALUE_PRIZE/P` | legacy | 0,1 % | Preissumme historisch |
| **`AwardingTerms.TechnicalCommitteePerson.FamilyName`** | eforms | 0,1 % | **Die Preisrichter namentlich** |
| `PROCEDURE/MEMBER_NAME` | legacy | 0,1 % | „Rainer Kriebel, Architekt, Würzburg" |
| `AwardingTerms.FollowupContractIndicator` | eforms | 0,2 % | **true 42 %** — Folgeauftrag in Aussicht |
| `AwardingTerms.BindingOnBuyerIndicator` | eforms | 0,2 % | Jury-Entscheid bindend? |
| `CRITERIA_EVALUATION_PROJECTS/P` | legacy | 0,1 % | Bewertungsmaßstab des Preisgerichts |
| `CONTEST_TITLE/P` · `TITLE_DESIGN_CONTACT_NOTICE/P` · `RESULT_CONTEST/CONTEST_NUMBER` | legacy | 0,1 % | Wettbewerbs-Metadaten |

Wer die Jury kennt und weiß, dass ein Folgeauftrag winkt, entscheidet anders über die
Teilnahme. Das ist ein eigenes Produkt für eine klar abgegrenzte Kundschaft.

---

## 9 · Änderungen, Nachträge, Aufhebung

| Feld | Gen. | Abd. | Inhalt |
|---|---|---:|---|
| **`ContractModification.ChangeReason.ReasonCode`** | eforms | 7,2–9,7 % | **add-wss 74–76 %** (zusätzliche Leistungen) · mod-cir 19–25 % |
| `ContractModification.ChangeReason.ReasonDescription` | eforms | 9,7 % | **„Ein AN-Wechsel verursacht erhebliche Termin…"** — Auftragnehmerwechsel im Klartext |
| `ContractModification.Change.ChangeDescription` | eforms | 9,7 % | was geändert wurde |
| `ADDITIONAL_NEED/P` | legacy | 5,6 % | zusätzliche Leistungen historisch |
| `UNFORESEEN_CIRCUMSTANCE/P` | legacy | 1,8 % | unvorhersehbare Umstände |
| `Changes.ChangeReason.ReasonCode` | eforms | 8,8 % | update-add 51 % · cor-buy 31 % |
| **`EXT/Change.ChangeReason.ReasonCode`** | **doe** | 16,8 % | update-add 75 % · **cancel 25 %** — **Aufhebung, amtlich** |
| `DEL/MIXED` | legacy | 1,3 % | „Incomplete procedure" · „The awarding procedure has been discontinued" |
| `WHERE/SECTION` + `WHERE/LABEL` + `OLD_VALUE/*` + `NEW_VALUE/*` | legacy | 1,8–3,2 % | **Berichtigungs-Diff**: „Schlusstermin für den Eingang der Angebote" alt → neu |
| `ProcedureRelaunchIndicator` | eforms | 2,7–5,0 % | Wiederholung eines gescheiterten Verfahrens, **amtlich** |

Der Berichtigungs-Diff ist konkret nutzbar: *„Die Angebotsfrist wurde vom 12.03. auf den
26.03. verschoben."* Heute merken wir davon nichts.

---

## 10 · Wiederkehr und Frühindikatoren

| Feld | Gen. | Abd. | Inhalt |
|---|---|---:|---|
| **`RecurringProcurementDescription`** | eforms | 0,5–1,0 % | **„Schülerbeförderung"**, **„IV. Quartal 2027"** — der Käufer nennt den nächsten Termin selbst |
| `RECURRENT_PROCUREMENT/P` | legacy | 0,1 % | „1/2018", „2019" |
| `RECURRENT_CONTRACT/NUMBER_POSSIBLE_RENEWALS` | legacy | 1,1 % | 1 (47 %) · 2 (39 %) |
| `ESTIMATED_TIMING/P` | legacy | 0,3 % | „2024", „2025" |
| `PIN.PlannedDate` | eforms | 0,7 % | geplantes Veröffentlichungsdatum der Ausschreibung |
| `OPTIONS/PROVISIONAL_TIMETABLE_MONTH` | legacy | 0,3 % | vorläufiger Zeitplan |
| `ContractExtension.MaximumNumberNumeric` | eforms | 2,0–3,7 % | Verlängerungsoptionen (0 → 57–59 %) |
| `ContractExtension.OptionsDescription` | eforms | 0,1–0,9 % | was die Option umfasst |
| `OPTION_DESCRIPTION/P` | legacy | 2,1 % | dasselbe historisch |
| `OPTIONS/NUMBER_POSSIBLE_RENEWALS` | legacy | 0,1 % | |

Die Wiederkehr-Prognose, die die Profil-Skizze unter 10.3 als Eigenleistung führt
(*„Zeitreihenanalyse je buyer × CPV"*), steht in 0,5–1 % der Fälle **wörtlich in den Daten**.

---

## 11 · Ergebnis und Wettbewerbsintensität

| Feld | Gen. | Abd. | Inhalt |
|---|---|---:|---|
| `LotResult.TenderResultCode` | eforms | 36,4–43,6 % | selec-w 89 % · **clos-nw 9 %** (kein Gewinner) je Los |
| `ReceivedSubmissionsStatistics` | eforms | 36,2–43,5 % | Bieterstatistik **je Los** — feiner als unser `num_tenders` |
| `TENDERS/NB_TENDERS_RECEIVED_EMEANS` | legacy | 10,0 % | elektronisch eingereichte Angebote |
| `TENDERS/NB_TENDERS_RECEIVED_SME` | legacy | 8,8 % | **KMU-Angebote** |
| `TENDERS/NB_TENDERS_RECEIVED_OTHER_EU` / `_NON_EU` | legacy | 7,8–7,9 % | ausländische Bieter (93–97 % null) |
| `AWARD_OF_CONTRACT/OFFERS_RECEIVED_NUMBER_MEANING` | legacy | 2,4 % | Bieterzahl |
| **`LotTender.RankCode`** | eforms | 5,4–6,0 % | **Rang 1 (95 %) · 2 · 3 … bis 6** — 651 Notices mit einem *unterlegenen* Bieter |
| **`AppealRequestsStatistics.StatisticsNumeric`** | eforms | 0,3 % | **Nachprüfungsanträge** — 0 (86 %) · 1 (14 %) |
| `FieldsPrivacy.FieldIdentifierCode` + `.ReasonCode` | eforms | 1,9–5,2 % | **warum ein Feld leer ist**: `win-ten-val` + `eo-int` = „Wert zurückgehalten, Geschäftsgeheimnis" |
| `FieldsPrivacy.ReasonDescription` | eforms | 1,0–1,3 % | im Klartext |

`RankCode` korrigiert eine frühere Aussage von mir: Verliererdaten gibt es **in Spuren**.
Zu wenig für eine Gewinnquote, aber „wer wurde Zweiter" ist gelegentlich sichtbar.

`FieldsPrivacy` passt exakt zu unseren Herkunfts-Flags: statt „unbekannt" steht dort
*„zurückgehalten, Grund: Geschäftsgeheimnis"*. Ehrlichkeit als Feature.

---

## 12 · Nachhaltigkeit, Förderung, Strategie

| Feld | Gen. | Abd. | Inhalt |
|---|---|---:|---|
| **`ProcurementAdditionalType.ProcurementTypeCode`** | eforms | **53,3 %** | none 83 % · **env-imp 3 %** · **soc-obj 2 %** |
| `ProcurementAdditionalType.ProcurementType` | eforms | 2,3 % | Freitext: „Tariftreue", „Verpflichtungserklärung über…" |
| `StrategicProcurement.StrategicProcurementInformationCode` | eforms | 0,1–1,0 % | `veh-acq` · `pass-tran-serv` · `enrg-lab` · `eed-spec` · `computer` · `building` |
| `StrategicProcurement…` (Fahrzeuge) | eforms | 0,7 % | `vehicles-clean` · `vehicles-zero-emission` · Klassen m1/n1/n3 |
| `FundingProgramCode` | eforms/doe | 9,8–45,4 % | no-eu-funds 95–98 % · **eu-funds 2–5 %** |
| **`SettledContract.Funding.FundingProgramCode`** | eforms | 0,1 % | **ERDF · ERDF_2021 · JTF** — die Programme namentlich |
| `SettledContract.Funding.FinancingIdentifier` | eforms | 0,3 % | Fördermittel-Kennung |
| `EXT/Funding.FinancingIdentifier` | eforms | 0,1 % | Projektkennung |
| `EU_PROGR_RELATED/P` · `RELATES_TO_EU_PROJECT_YES/P` | legacy | 1,1–1,5 % | „EFRE", „FAG-Förderung des Freistaates…" |
| `OBJECT_DESCR/EU_PROGR_RELATED` | legacy | 0,2 % | Förderkennzeichen |
| `TAX_/ENVIRONMENTAL_/EMPLOYMENT_PROTECTION_LEGISLATION_VALUE/P` | legacy | 0,5 % | Verweise auf BMF/BMU/BMAS |

Die Profil-Skizze wünscht sich unter 10.2 „Förderprogramme" als **externe Quelle**. Ein
Teil davon steht bereits in den Daten — inklusive Programmnamen (ERDF, JTF).

---

## 13 · Ort und Menge

| Feld | Gen. | Abd. | Inhalt |
|---|---|---:|---|
| **`RealizedLocation.Address.Region`** | eforms | 3,7–8,5 % | **`anyw-cou` 80–95 %** — ortsunabhängig erbringbar. **Unsere Radius-Suche filtert diese Leads heute fälschlich weg.** |
| `RealizedLocation.Address.CityName` | doe | **24,5 %** | Leistungsort als Ortsname; wir haben nur NUTS |
| `RealizedLocation.Address.AdditionalStreetName` | eforms | 3,1–6,5 % | **Straßenadresse** des Leistungsorts |
| `RealizedLocation.Address.AddressLine.Line` | eforms | 0,1–0,2 % | mehrere Standorte in einem Feld |
| `RealizedLocation.Description` | eforms (PIN) | 0,2 % | „B 4, Ortsumgehung Lüneburg AS Häcklinger…" |
| `Address.CountrySubentityCode` | doe | 19,3 % | NUTS-1 des Leistungsorts |
| `LOCATION/P` · `PLACE_NOT_STRUCTURED/P` | legacy | 0,2–1,2 % | Ort als Freitext |
| `TEXT.RC` | text | 56,5 % | NUTS historisch |
| **`EstimatedOverallContractQuantity`** | eforms | 0,5–0,7 % | **Menge** (1.000, …) — die „wie viele Lizenzen"-Frage |
| `TOTAL_QUANTITY_OR_SCOPE/P` | legacy | 1,9 % | **Menge und Umfang** als Freitext |
| `PERIOD_WORK_DATE_STARTING/MONTHS` / `/DAYS` | legacy | 0,3–2,4 % | Ausführungsdauer |
| `PlannedPeriod.StartDate` / `.EndDate` | eforms | 2,3–33,9 % | **geplanter Vertragsbeginn/-ende aus der Ausschreibung** statt geschätzt |
| `PlannedPeriod.DurationMeasure` | eforms | 1,1 % | 36 Monate 18 % |
| `PlannedPeriod.DescriptionCode` | eforms/doe | 0,7–27,8 % | `UNKNOWN` · `UNLIMITED` (unbefristet!) |

`anyw-cou` ist ein konkreter Fehler in unserem Produkt: eine bundesweit erbringbare
Dienstleistung wird von der Umkreissuche aussortiert, obwohl sie für jeden passt.

---

## 14 · Verweise zwischen Bekanntmachungen

| Feld | Gen. | Abd. | Nutzung |
|---|---|---:|---|
| `TP.NoticeDocumentReference.ID` | eforms | 6,0–14,0 % | Verweis auf die Ausschreibung (cn→can) |
| `PREVIOUS_PUBLICATION_NOTICE_F2/F3/F5/F6/NOTICE_NUMBER_OJ` | legacy | 0,2–5,9 % | **Vorgänger-Bekanntmachung, amtlich** |
| `PROCEDURE/NOTICE_NUMBER_OJ` · `COMPLEMENTARY_INFO/NOTICE_NUMBER_OJ` | legacy | 3,3–5,5 % | dasselbe |
| `CNT_NOTICE_INFORMATION/NOTICE_NUMBER_OJ` | legacy | 14,3 % | |
| `REF_NOTICE/NO_DOC_OJS` | ojs | 50,5 % | |
| `TEXT.RN` | text | 46,4 % | |
| `Changes.ChangedNoticeIdentifier` | eforms/doe | 0,2–10,9 % | geänderte Bekanntmachung |
| `ContractModification.ChangedNoticeIdentifier` | eforms | 7,2–9,7 % | |

Unser `award_tender_link` deckt heute 51 %. Diese Felder sind **amtliche** Verweise statt
Rekonstruktion — sie würden die Verkettung messbar verbessern, gerade historisch.

---

## ⚠️ 15 · Was NICHT ins Produkt gehört

`UltimateBeneficialOwner` (eforms, 22–25 %) löst Konzernstrukturen ohne Handelsregister
auf — trägt aber **Personendaten natürlicher Personen**:

- `.FirstName` — Vor- und Nachname
- `.ResidenceAddress` — **Privatanschrift**
- `.Contact.Telefax` — private Kontaktdaten

Verwendbar ist allenfalls die *Existenz* einer UBO-Verknüpfung für die Konzernauflösung,
niemals die Personendaten selbst.

Grenzfall, aber vertretbar: `TechnicalCommitteePerson.FamilyName` (Preisrichter) und
`PROCEDURE/MEMBER_NAME` — das sind berufliche Funktionsangaben aus einer amtlichen
Bekanntmachung, deren Veröffentlichung Zweck der Bekanntmachung ist.

Ebenfalls Vorsicht: `CONTACT_DATA*/ATTENTION` und `.Contact.Name` (Ansprechpartner) sind
personenbezogen, aber dienstlich und zur Kontaktaufnahme veröffentlicht — nutzbar, jedoch
nicht für Massen-Export oder Profilbildung über die Person.

---

## 16 · Technisches Rauschen — bewusst nicht weiterverfolgt

Rund **2.400 der 4.123** Pfade tragen keine Sachinformation:

- Dokument-IDs und UUIDs: `ID`, `ContractFolderID`, `NOTICE_UUID`, `NoticePublicationID`
- Schema-/Formatangaben: `UBLVersionID`, `CustomizationID`, `ProfileID`, `VersionID`
- Publikations-Metadaten: `GazetteID`, `IssueTime`, `RequestedPublicationDate`, `DELETION_DATE`
- Dokumentinterne Zeiger: `ORG-000x`, `RES-000x`, `TPA-000x`, `CON-000x`, `TEN-000x`,
  `LOT-000x` — die werden über `notice_parties` und `lots` bereits aufgelöst
- Layout-/Übersetzungsfragmente: `BLK_BTX`, `TI_GRSEQ`, `MLI_OCCUR`, `TXT_MARK`, `P/FT`,
  `OBJ_NOT/INT_OBJ_NOT`, `READ/INT_READ` — mehrsprachige Amtsblatt-Formatierung
- Adress- und Datumsfragmente (`/YEAR`, `/MONTH`, `/DAY`, `/FAX`, `/POSTAL_CODE`), soweit
  die zusammengesetzten Werte bereits in `notices` und `notice_parties` stehen

**Ein Datenfund am Rande:** `TenderResult.AwardDate` trägt in **33 %** (eForms) bzw.
**51 %** (DÖE) den Platzhalter `2000-01-01`. Unser Parser liest einen anderen Pfad — im
Silber sind **0 von 494.361** `award_date` betroffen. Wichtig, falls jemand die Extraktion
umstellt.

---

## Empfohlene Reihenfolge

⚠️ **Wichtig für die Bewertung:** Die Abdeckungen oben sind über **Notices** gemessen.
Unsere 85.947 Leads bestehen aber zu 86 % aus `expiring` (historische Zuschläge) und nur
zu 14 % aus `open` (12.123 laufende Ausschreibungen). Felder aus der *Bekanntmachung* gibt
es naturgemäß nur bei `open`. Auf Lead-Ebene gemessen:

| Feld | alle Leads | **`open`** | `expiring` |
|---|---:|---:|---:|
| `RegulatoryDomain` | **98,7 %** | 97,2 % | 99,0 % |
| Tätigkeitsfeld der Behörde | **85,3 %** | 67,0 % | 88,3 % |
| Käufertyp | **79,4 %** | 65,4 % | 81,7 % |
| Unterlagen-Direktlink | 13,7 % | **96,8 %** | 0 % |
| Bindefrist | 9,4 % | **66,7 %** | 0 % |
| Submissionstermin | 6,0 % | **42,4 %** | 0 % |
| Bieterfragen-Frist | 4,1 % | **28,7 %** | 0 % |
| Los-Obergrenze | 1,4 % | 10,1 % | 0 % |
| Bietergemeinschafts-Klausel | 1,4 % | 10,0 % | 0 % |
| ortsunabhängig (`anyw*`) | 4,8 % | 6,0 % | 4,6 % |

Daraus die Reihenfolge:

| # | Was | Wirkt auf | Aufwand |
|---|---|---|---|
| 1 | **`RegulatoryDomain`** — VOB / UVgO / VgV / SektVO | **98,7 % aller Leads** | 1 Spalte |
| 2 | **Käufertyp + Tätigkeitsfeld** | **79–85 % aller Leads**, alle Generationen | 2 Spalten |
| 3 | **Unterlagen-Direktlink** | **96,8 % der offenen Leads** (unser `portal_url`: 44,5 % / DÖE 0 %) | 1 Spalte |
| 4 | **Bindefrist + Submissionstermin + Bieterfragen-Frist** | 29–67 % der offenen Leads | 3 Spalten + 1 Alert |
| 5 | **`anyw-cou`-Fix** | 4,8 % — aber es behebt einen **Fehler**, kein fehlendes Feature | Filter-Logik |
| 6 | **Partner-Cluster** | 10 % der offenen Leads, dort aber kaufauslösend | 7 Felder + UI |
| 7 | **`TendererRequirementTypeCode`** | 24 % der Notices | 32 Codes abbilden |
| 8 | **Wettbewerbe** | Nische, dort vollständig | eigene Ansicht |

Die ersten drei sind je ein bis zwei Spalten und wirken auf fast jeden Lead — zusammen
vermutlich ein Arbeitstag. Punkt 5 ist der einzige, der einen bestehenden **Fehler**
behebt statt etwas hinzuzufügen.

---

# Nachtrag: lückenloser Durchgang (2026-07-23)

Der Durchgang oben arbeitete mit Cluster-Vertretern und einer „technisch"-Heuristik.
Beides ist jetzt aufgelöst — **alle 4.123 Pfade** einzeln bzw. als vollständige
Clusterliste angesehen: DÖE 163/163 · text 20/20 · eForms 478/478 · legacy 601/601
Cluster (2.452 Pfade) · ojs 299/299 Cluster (1.010 Pfade).

## Was der lückenlose Durchgang zusätzlich gefunden hat

### Die „technisch"-Heuristik lag viermal falsch

| Feld | Abd. | Warum es kein Rauschen ist |
|---|---:|---|
| **`NR.TenderingParty.SubContractor.ID`** + **`.MainContractor.ID`** | 0,2 % | **Die Nachunternehmer-Beziehung, explizit modelliert**: welche Organisation ist Sub von welchem Hauptauftragnehmer. Das ist der Partner-Graph in Reinform, nicht ein Dokumentzeiger. |
| **`FieldsPrivacy.PublicationDate`** | 0,1–1,4 % | **2034-01-02 · 2035-01-01** — der Tag, an dem ein zurückgehaltener Wert öffentlich wird. „Wert wird 2035 veröffentlicht" ist ehrlicher als „unbekannt". |
| `LotResult.PayerParty` / `.FinancingParty` | 0,9–1,2 % | **Wer zahlt, wer finanziert** — nicht immer der Käufer. Relevant, wenn ein Dritter das Projekt trägt. |
| `AdditionalNoticeLanguage.ID` | 0,0–0,1 % | Zusätzliche Sprachen (LAV, HRV, MLT) = grenzüberschreitendes Interesse |

### Ein kompletter Fachbereich: ÖPNV-Direktvergaben (legacy)

Ein eigener Formulartyp nach VO (EG) 1370/2007 mit **Qualitätskennzahlen als Pflichtfeld**
— in keiner unserer Tabellen:

`PUBLIC_SERVICE_OBLIGATIONS/P` · `PUNCTUALITY_RELIABILITY/P` · `CLEANLINESS_ROLLING_STOCK/P` ·
`CUST_SATISFACTION_SURVEY/P` · `COMPLAINT_HANDLING/P` · `CANCELLATIONS_SERVICES/P` ·
`ASSIST_PERSONS_REDUCTED_MOB/P` · `INFORMATION_TICKETS/P` · `REWARDS_PENALITIES/P` ·
`COST_PARAMETERS/P` · `QUANTITY_SCOPE_MOVE/KM_TRANSPORT_SERVICES` (390.000–8,1 Mio. km) ·
`AWARDED_CONTRACT/NB_KILOMETRES` · `EXCLUSIVE_RIGHTS_GRANTED/P` · `PREDOMINANCE/P` ·
`CONTRACTOR/OWNERSHIP` (Eigentümerstruktur des Betreibers)

Winzige Abdeckung (0,01–0,03 %), aber für Verkehrsunternehmen und Aufgabenträger ist das
der gesamte Vertragsinhalt. Und `CONTRACTOR/OWNERSHIP` ist Konzernauflösung ohne
Handelsregister — bei einer Kundschaft, die genau daran interessiert ist.

### Wer die Ausschreibung tatsächlich abwickelt

| Feld | Gen. | Abd. | Nutzung |
|---|---|---:|---|
| **`SENDER/LOGIN`** | ojs | 28,0 % | `DE002` · **`SIMAP2_rwparch`** — der **eSender**. Kennzeichnet das Büro oder die zentrale Stelle, die das Verfahren fährt. Ein Architekturbüro als eSender heißt: dieses Büro betreut die Vergabe. |
| `SENDER/NO_DOC_EXT` | ojs | 28,0 % | dessen interne Vorgangsnummer |
| `USER/ORGANISATION` · `/ATTENTION` | ojs | 1,5 % | RWE Power AG, Vattenfall — die einreichende Stelle |
| `CONTACT_DATA_OTHER_BEHALF_CONTRACTING_AUTORITHY/*` | legacy | 0,7 % | **zentrale Beschaffungsstelle handelt für andere** |
| `ADDRESS_CONTRACTING_BODY_ADDITIONAL/OFFICIALNAME` | legacy | 0,3 % | zweiter Auftraggeber (Sammelvergabe) |
| `ContractingRepresentationType.RepresentationTypeCode` | doe | 1,0 % | `cpb-awa` — zentrale Beschaffungsstelle vergibt im eigenen Namen |

Das ist ein eigener Lead-Typ: nicht die Behörde, sondern **das Büro, das für sie
ausschreibt** — und das laufend weitere Verfahren betreut.

### Wiederkehr-Intervall, explizit in Monaten

| Feld | Gen. | Abd. | Werte |
|---|---|---:|---|
| **`RECURRENT_CONTRACT/TIME_FRAME_SUBSEQUENT_CONTRACTS_MONTHS`** | legacy | 0,69 % | **12 (56 %)** · 24 (20 %) · 36 (7 %) |
| `OPTIONS/TIME_FRAME_SUBSEQUENT_CONTRACTS_MONTH` | legacy/ojs | 0,06–0,87 % | 12 (50–62 %) · 24 · 48 |

Kein Modell nötig: der Käufer nennt das Intervall in Monaten.

### Elektronische Auktion

`USE_ELECTRONIC_AUCTION/P` · `ELECTRONIC_AUCTION/P` · `INFO_ADD_EAUCTION/P` (legacy/ojs,
0,01–0,13 %) und `AuctionTerms.AuctionURI` / `.AuctionConstraintIndicator` (eforms,
0,1–0,4 %). Bei einer E-Auktion gewinnt man **live über den Preis** — eine völlig andere
Angebotsvorbereitung. Wer das nicht vorher weiß, verliert.

### Wettbewerbe, historisch vollständiger als in eForms

| Feld | Gen. | Abd. | Inhalt |
|---|---|---:|---|
| `RESULT_CONTEST/PRIZE_VALUE` | legacy/ojs | 0,08–0,53 % | **66.000 € · 70.000 €** Preissumme |
| `AWARDED_PRIZE/VAL_PRIZE` | legacy | 0,05 % | 107.000 € · 913.150 € |
| `AWARDED_PRIZE/DATE_DECISION_JURY` | legacy | 0,08 % | Datum des Preisgerichts |
| **`PARTICIPANTS_NAME/NAME`** | legacy/ojs | 0,03–0,40 % | **Teilnehmer namentlich**: „Ingenhoven Architekten", „Asal und Traub, Pforzheim" |
| `MEMBERS_NAME/NAME` + `/ORDER` | legacy/ojs | 0,07–0,47 % | Preisgericht namentlich, in Reihenfolge |
| `AWARD_PRIZES/PARTICIPANTS_NUMBER` | legacy/ojs | 0,17–0,53 % | **335 Teilnehmer** im Extremfall |
| `AWARD_PRIZES/FOREIGN_PARTICIPANTS_NUMBER` · `NB_PARTICIPANTS_SME` | legacy | 0,01–0,06 % | Ausländer- und KMU-Anteil |
| `RESTRICTED_CONTEST/PARTICIPANTS_NUMBER` | legacy/ojs | 0,06–0,33 % | Teilnehmerzahl bei begrenzten Wettbewerben |
| `DETAILS_PAYMENTS_PARTICIPANTS/P` | legacy/ojs | 0,04–0,33 % | Aufwandsentschädigung |

Für ein Architekturbüro ist „335 Teilnehmer, 66.000 € Preissumme, Jury bekannt" die
komplette Entscheidungsgrundlage — und sie liegt seit 2008 in den Daten.

### Weitere Einzelfunde

| Feld | Gen. | Abd. | Inhalt |
|---|---|---:|---|
| `TECHNICAL_SECTION/FORM_LG_LIST` | legacy | **100 %** | DE 95 %, aber **13-sprachige Veröffentlichung 3 %** = bewusst grenzüberschreitend ausgeschrieben |
| `OBJECT_CONTRACT/REFERENCE_NUMBER` · `FILE_REFERENCE_NUMBER/P` | legacy | 0,8–2,7 % | **Aktenzeichen des Käufers** („VOB GB3 23/024-36 EU") — Anknüpfung an Kundenunterlagen |
| `AWARDED_CONTRACT/DATE_CONCLUSION_CONTRACT` | legacy | 0,01 % | Vertragsunterzeichnung ≠ Zuschlag |
| `PROCEDURE/DATE_DISPATCH_INVITATIONS` · `DISPATCH_INVITATIONS_DATE/*` | legacy/ojs | 0,06–5,9 % | wann die Einladungen rausgehen |
| `CLEARING_LAST_DATE/*` | legacy | 0,04 % | Klärungsfrist |
| `SOCIAL_STANDARDS/P` · `PERFORMANCE_CONDITIONS/P` | legacy | 0,01–0,06 % | Tariftreue, Vergabemindestentgelt |
| `LOCATION_NUTS/LOCATION` | ojs | 0,07 % | Adresse **mit** NUTS in einem Feld |
| `DOCUMENT_METHOD_OF_PAYMENT/P` | ojs | **27,7 %** | „Das eingezahlte Entgelt wird nicht erstattet" — Unterlagen kosteten Geld |
| `PLACE_OPENING/P` | ojs | 23,5 % | Ort der Submission |

## Was auch der lückenlose Durchgang nicht leisten kann

`is_used` wird über einen **Wert-Join** bestimmt: ein Rohwert gilt als genutzt, wenn er
identisch in einer Silber-Spalte auftaucht. Felder, die der Parser **umformt**, erscheinen
dadurch fälschlich als ungenutzt:

- zusammengesetzte Datumsangaben (`/YEAR` + `/MONTH` + `/DAY` → ein `DATE`)
- gesäuberte Texte (HTML-Entities, Whitespace)
- übersetzte Codes (`1` → `works`)

Belegt am ojs-Titel: „Personenbeförderung per Bahn" steht in `notices.title`, aber in
keinem Rohpfad mit exakt diesem Wert. Die Zahl **4.123 ist deshalb eine Obergrenze** —
die tatsächlich ungenutzte Menge ist kleiner, vor allem bei Datums- und Adressfragmenten.
Für die *inhaltlichen* Funde oben spielt das keine Rolle: dort wurde jeweils geprüft, dass
kein entsprechendes Silber-Feld existiert.


## Nachweis der Vollständigkeit (2026-07-23)

Nach einer Rückfrage habe ich die Abdeckung nachgerechnet statt behauptet. Alle Blöcke
aus **derselben** korrigierten Datenbasis (`bronze_inventory` nach beiden Messfehler-Fixes),
in lückenlosen, nicht überlappenden Bereichen angezeigt:

| Generation | Bereiche | Summe |
|---|---|---|
| eforms | 1–160 · 161–330 · 331–478 | **478 / 478** |
| legacy | 1–140 · 141–300 · 301–601 (Cluster) | **601 / 601** (= 2.452 Pfade) |
| ojs | 1–45 · 46–180 · 181–299 (Cluster) | **299 / 299** (= 1.010 Pfade) |
| doe | 1–55 · 56–163 | **163 / 163** |
| text | 1–20 | **20 / 20** |

Beim Nachrechnen fiel ein **methodischer Mangel im Vorgehen** auf, auch wenn er sich
inhaltlich nicht ausgewirkt hat: Teile der eForms- und ojs-Listen hatte ich in Bereichen
angezeigt, die über `grep`-Filter und überlappende `sed`-Bereiche liefen — dabei ist nicht
prüfbar, ob etwas durchfällt. Die Wiederholung oben ist arithmetisch nachvollziehbar und
hat **keine neuen inhaltlichen Funde** ergeben; einzige Ergänzung:
`AppealRequestsStatistics.StatisticsCode` (`complainants` 94 % · `ncompl-awcrit` 6 %) —
die *Art* des Nachprüfungsantrags neben seiner Anzahl.

**Was weiterhin gilt:** die Grenze des Wert-Joins (s. voriger Abschnitt). 4.123 ist eine
Obergrenze, weil umgeformte Felder fälschlich als ungenutzt erscheinen.

---

## Endgültige Abdeckungs-Bilanz (2026-07-23)

Auf mehrfache Nachfrage sauber ausgerechnet statt behauptet:

| | Pfade |
|---|---:|
| **einzeln als Zeile gelesen** (eForms 478 · DÖE 163 · text 20 · legacy 601 Cluster · ojs 299 Cluster) | **1.561** |
| **nach Abzug der Bekanntmachungstyp-Wurzel identisch** mit einem gelesenen Pfad | **2.471** |
| **in 7 Clustern mit abweichender Verschachtelung** — vollständig geprüft, s. unten | **91** |
| **Summe** | **4.123** ✓ |

Die 2.471 sind kein blinder Fleck: `…CONTRACT.FD_CONTRACT.PROCEDURE…RECEIPT_LIMIT_DATE/YEAR`
und `…CONTRACT_UTILITIES.FD_CONTRACT_UTILITIES.PROCEDURE…RECEIPT_LIMIT_DATE/YEAR` sind
**dasselbe Feld in der Sektoren-Variante desselben Formulars**. Nach Entfernen der
Typ-Wurzel (`CONTRACT`, `CONTRACT_UTILITIES`, `CONCESSION`, `DESIGN_CONTEST`,
`PERIODIC_INDICATIVE_UTILITIES`, `BUYER_PROFILE`, `VOLUNTARY_EX_ANTE_TRANSPARENCY_NOTICE` …)
sind sie zeichengleich.

### Die 7 Cluster mit echter Abweichung

| Cluster | Varianten | Bewertung |
|---|---|---|
| `AC_PRICE/AC_WEIGHTING` | `AC.AC_PRICE.…` **und** `AC_PRICE.…` | **relevant** — eine *dritte* Verschachtelungsvariante der Zuschlagskriterien neben `AC_*` und `CRITERIA_DEFINITION`. Unser `_legacy_criteria` liest `AC_PRICE` direkt; die Variante mit `AC.`-Wrapper faellt durch. |
| `AC_QUALITY/AC_CRITERION` · `/AC_WEIGHTING` | dito | dito |
| `AC_COST/AC_CRITERION` · `/AC_WEIGHTING` | dito | dito |
| `P/FT` (legacy) | `NEW.P.FT` · `P.FT` · `P.P.P.FT` | Layout-Fragment, ohne Wert |
| `P/P` (ojs) | `NEW.P.P` · `P.P` | Layout-Fragment, ohne Wert |

**Konkreter Handlungspunkt:** fuenf der sieben betreffen die Zuschlagskriterien. Beim
Nachziehen der Legacy-Kriterien (Cluster 2) muessen **drei** Verschachtelungen abgedeckt
werden — `AC_PRICE/AC_QUALITY/AC_COST` direkt, dieselben unter einem `AC.`-Wrapper, und
`CRITERIA_DEFINITION`. Sonst fehlt wieder ein Teil.
