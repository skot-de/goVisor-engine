"""Feld-Inventar als CSV — Arbeitsdokument für die Roadmap.

Eine Zeile je Rohdaten-Pfad über alle fünf Schema-Generationen, mit Abdeckung,
Beispielwerten, Nutzungsstatus und Bewertung. Gedacht zum Sortieren und Filtern in
Excel/Numbers, nicht zum Lesen im Terminal.

**Zwei Arten von Bewertung, klar getrennt** — das ist der Punkt dieser Datei:

- ``kategorie`` ist **regelbasiert** (Endungen, Pfadmuster). Sie trifft jede Zeile, ist
  aber nur so gut wie die Regel. `technisch`/`datum_fragment`/`adresse_kontakt` heisst
  „mit hoher Wahrscheinlichkeit kein Produktwert" — nicht „geprueft".
- ``bewertung`` + ``cluster`` + ``idee`` sind **von Hand vergeben**, nach dem
  vollstaendigen Durchgang durch alle 4.123 ungenutzten Sachdaten-Pfade
  (s. `docs/rohdaten-potenzial-gesamt.md`). Wo sie leer sind, hat das Feld **keine
  Einzelbewertung** bekommen — es fiel in eine Regel-Kategorie oder war inhaltlich
  unauffaellig.

Wer die Datei auswertet, sollte auf `bewertung` filtern, nicht auf `kategorie`.

**Grenze, die in der Datei nicht sichtbar ist:** `is_used` wird ueber einen Wert-Join
bestimmt (Rohwert = Silber-Wert). Felder, die der Parser umformt — zusammengesetzte
Datumsangaben, gesaeuberte Texte, uebersetzte Codes — erscheinen faelschlich als
ungenutzt. Die Zahl der ungenutzten Pfade ist deshalb eine **Obergrenze**.

Aufruf:  python3 scripts/export_field_inventory.py [--out data/export/feld_inventar.csv]
"""
import argparse
import csv
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import duckdb  # noqa: E402

INVENTORY = "data/gold/DE/bronze_inventory.parquet"

# ---------------------------------------------------------------- Regel-Kategorien
# Bewusst konservativ: im Zweifel `inhaltlich`, damit nichts vorschnell wegfaellt.
# Die Regel hat sich beim Durchgang viermal geirrt (SubContractor.ID, MainContractor.ID,
# FieldsPrivacy.PublicationDate, PayerParty) — die stehen deshalb in AUSNAHMEN.
AUSNAHMEN = ("SubContractor", "MainContractor", "FieldsPrivacy.PublicationDate",
             "PayerParty", "FinancingParty", "AdditionalNoticeLanguage")

_TECHNISCH = re.compile(
    r"(UBLVersionID|CustomizationID|ProfileID|VersionID|ContractFolderID|NOTICE_UUID"
    r"|GazetteID|NoticePublicationID|RECEPTION_ID|DELETION_DATE|IssueTime"
    r"|\bID$|PartyIdentification\.ID$|URI_DOC|FORM_LG_LIST|COMMENTS)")
_DATUM = re.compile(r"/(YEAR|MONTH|DAY|TIME)$|IssueDate$|PublicationDate$"
                    r"|RequestedPublicationDate$|DATE_PUB$|DS_DATE_DISPATCH$")
_ADRESSE = re.compile(
    r"/(ADDRESS|FAX|PHONE|E_MAIL|POSTAL_CODE|TOWN|ATTENTION|CONTACT_POINT|URL"
    r"|OFFICIALNAME|ORGANISATION|NATIONALID)$"
    r"|PostalAddress|Contact\.(Telephone|Telefax|ElectronicMail)|WebsiteURI|EndpointID")
_PERSON = re.compile(r"UltimateBeneficialOwner.*(FirstName|ResidenceAddress|Contact)")
_LAYOUT = re.compile(r"BLK_BTX|TI_GRSEQ|MLI_OCCUR|TXT_MARK|/FT$|INT_OBJ_NOT|INT_READ"
                     r"|INT_FOR|NO_MARK$|/P/P$")


def kategorie(path: str) -> str:
    if any(a in path for a in AUSNAHMEN):
        return "inhaltlich"
    if _PERSON.search(path):
        return "personenbezogen"
    if _LAYOUT.search(path):
        return "layout"
    if _DATUM.search(path):
        return "datum_fragment"
    if _ADRESSE.search(path):
        return "adresse_kontakt"
    if _TECHNISCH.search(path):
        return "technisch"
    return "inhaltlich"


# ------------------------------------------------- Hand-Bewertung aus dem Durchgang
# (cluster, bewertung, idee). Schluessel ist ein Teilstring des Pfades; erster Treffer
# gewinnt, deshalb stehen spezifischere Muster oben.
# bewertung: hoch | mittel | niedrig | nicht_nutzbar
KURATIERT: list[tuple[str, str, str, str]] = [
    # --- Kaeufer-Segmentierung -------------------------------------------------
    ("AA_AUTHORITY_TYPE", "kaeufer_segment", "hoch",
     "Behoerdentyp, 100 % ueber die gesamte Legacy-Historie. Achse 1 des Kaeufer-Aehnlichkeitsmasses (offene Frage 4D der Profil-Skizze)."),
    ("MA_MAIN_ACTIVITIES", "kaeufer_segment", "hoch",
     "Taetigkeitsfeld der Behoerde, 99,3 %. Achse 2 desselben Masses."),
    ("ContractingPartyType.PartyTypeCode", "kaeufer_segment", "hoch",
     "Behoerdentyp eForms (la/ra/body-pl/pub-undert)."),
    ("ContractingActivity.ActivityTypeCode", "kaeufer_segment", "hoch",
     "Taetigkeitsfeld eForms (gen-pub/health/education/rail)."),
    ("BIB_DOC_S/MAIN_ACTIVITIES", "kaeufer_segment", "mittel", "Taetigkeitsfeld ojs."),
    ("TEXT.MA", "kaeufer_segment", "mittel", "Taetigkeitsfeld Textformat."),
    ("CA_ACTIVITY_OTHER", "kaeufer_segment", "niedrig",
     "Freitext-Taetigkeit fuer Faelle ausserhalb der Codeliste."),
    # --- Rechtsrahmen ----------------------------------------------------------
    ("RegulatoryDomain", "rechtsrahmen", "hoch",
     "VOB / UVgO / VgV / SektVO. 98,7 % aller Leads. Ein-Klick-Filter, raeumt fuer einen Bauunternehmer die halbe Liste weg."),
    ("ProcurementLegislationDocumentReference.ID", "rechtsrahmen", "hoch",
     "Dasselbe feiner (vgv/vob-a-eu/sektvo/CrossBorderLaw)."),
    ("PR_PROC", "rechtsrahmen", "mittel", "Verfahrensart legacy, 100 %."),
    ("TP.ProcedureCode", "rechtsrahmen", "mittel", "Verfahrensart DÖE (de-open 94 %)."),
    ("ContractingSystemTypeCode", "rechtsrahmen", "hoch",
     "Rahmenvereinbarung OHNE erneuten Wettbewerb (fa-wo-rc 9-11 %): wer drin ist ruft ab, wer draussen ist hat Jahre keine Chance."),
    ("ProcedureRelaunchIndicator", "rechtsrahmen", "mittel",
     "Amtliches Flag fuer Wiederholung eines gescheiterten Verfahrens — ergaenzt unser rekonstruiertes retender_signal."),
    ("RP_REGULATION", "rechtsrahmen", "niedrig", "GPA-Teilnahme (WTO-Abkommen)."),
    # --- Zuschlagskriterien ----------------------------------------------------
    ("AC_AWARD_CRIT", "zuschlagskriterien", "hoch",
     "Lowest price 45 % / most economic 39 %, 100 % legacy. Erlaubt 'diese Stelle entscheidet historisch zu X % rein ueber den Preis' ueber 20 Jahre."),
    ("BIB_DOC_S/AWARD_CRIT", "zuschlagskriterien", "mittel", "Dasselbe fuer ojs."),
    ("TEXT.AC", "zuschlagskriterien", "mittel", "Dasselbe fuers Textformat."),
    ("CRITERIA_DEFINITION/CRITERIA", "zuschlagskriterien", "hoch",
     "Zweite Legacy-Struktur neben AC_PRICE/AC_QUALITY — hier fehlt uns ein Teil der Kriterien."),
    ("CRITERIA_DEFINITION/WEIGHTING", "zuschlagskriterien", "hoch", "Gewichte dazu (10/100/20/30)."),
    ("MAIN_FEATURES_AWARD", "zuschlagskriterien", "niedrig", "Beschreibung der Gewichtungslogik."),
    # --- Partner-Netzwerk ------------------------------------------------------
    ("MaximumLotsAwardedNumeric", "partner", "hoch",
     "DER Ausloeser: 12 Lose, hoechstens 3 gewinnbar -> Konsortium zwingend. Wer das vorher weiss, baut das Team."),
    ("MaximumLotsSubmittedNumeric", "partner", "hoch", "Wie viele Lose man ueberhaupt anbieten darf."),
    ("LOT_MAX_ONE_TENDERER", "partner", "mittel", "Dasselbe historisch."),
    ("LOT_COMBINING_CONTRACT_RIGHT", "partner", "mittel", "'All lots will be awarded to one bidder'."),
    ("TY_TYPE_BID", "partner", "mittel", "Gesamt- vs. Teilangebot, 100 % legacy/text/ojs."),
    ("CompanyLegalForm", "partner", "hoch",
     "Bietergemeinschafts-Klausel im Klartext. In DÖE 43,7 % — siebenfach besser als in eForms."),
    ("LEGAL_FORM", "partner", "hoch", "Dieselbe Klausel historisch (legacy 11,3 %, ojs 33,3 %)."),
    ("SubcontractingTerm.TermCode", "partner", "hoch",
     "Wurde untervergeben? Rueckwaerts gelesen: welche Firmen arbeiten mit Subunternehmern = Kandidatenliste."),
    ("SubcontractingTerm.TermPercent", "partner", "hoch", "Wie viel untervergeben wurde (21 %, 30 %)."),
    ("SubcontractingTerm.TermAmount", "partner", "hoch", "Dasselbe in Euro (bis 6,3 Mio)."),
    ("SubContractor", "partner", "hoch",
     "Die Nachunternehmer-BEZIEHUNG explizit modelliert: welche Org ist Sub von welchem Hauptauftragnehmer. Der Partner-Graph in Reinform."),
    ("PCT_SUBCONTRACTING", "partner", "mittel", "Untervergabe-Anteil historisch."),
    ("CONTRACT_LIKELY_SUB_CONTRACTED", "partner", "mittel", "Geplante Untervergabe in % und EUR."),
    ("TenderSubcontractingRequirements", "partner", "mittel", "shar-subc: Untervergabe vorgeschrieben."),
    ("AllowedSubcontractTerms", "partner", "niedrig", "Bedingungen fuer Nachunternehmerwechsel."),
    ("FrameworkAgreement.MaximumOperatorQuantity", "partner", "hoch",
     "1 (44 %) = winner-takes-all, 114 (21 %) = fast jeder kommt rein. Eine echte Wahrscheinlichkeit."),
    ("FRAMEWORK/NB_PARTICIPANTS", "partner", "mittel", "Dasselbe historisch."),
    ("EconomicOperatorShortList.PreSelectedParty", "partner", "hoch",
     "Wer bereits eingeladen ist, NAMENTLICH. Direkte Wettbewerbsaufklaerung."),
    ("EconomicOperatorShortList", "partner", "mittel", "Wie viele eingeladen werden (min 3 / max 5)."),
    ("MAXIMUM_NUMBER_INVITED", "partner", "mittel", "Dasselbe historisch."),
    ("NB_MIN_LIMIT_CANDIDATE", "partner", "mittel", "Dasselbe."),
    ("NB_MAX_LIMIT_CANDIDATE", "partner", "mittel", "Dasselbe."),
    ("CompanySizeCode", "partner", "hoch",
     "Firmengroesse des GEWINNERS (small 38 / medium 30 / large 26 / micro 6). KPI: 'hier gewinnen zu 68 % KMU' — die ehrlichste Naeherung an die unmoegliche Gewinnquote."),
    ("NB_TENDERS_RECEIVED_SME", "partner", "mittel", "Wie viele KMU geboten haben."),
    ("VariantConstraintCode", "partner", "hoch",
     "Nebenangebote erlaubt (eForms 6-8 %, DÖE 19 %) — dort kann ein anderer Loesungsweg gewinnen, also lohnt ein Partner mit anderer Technologie."),
    ("MultipleTendersCode", "partner", "mittel", "Darf man auf mehrere Lose bieten (32-38 % ja)."),
    # --- Wert ------------------------------------------------------------------
    ("FrameworkMaximumAmount", "wert", "hoch",
     "Hoechstwert der Rahmenvereinbarung, bis 146 Mio EUR. Bei Rahmenvertraegen der einzige belastbare Volumenanker — wir haben nur 9 % estimated_value."),
    ("OverallApproximateFrameworkContractsAmount", "wert", "mittel", "Gesamtvolumen aller Abrufe."),
    ("FrameworkAgreementValues.ReestimatedValue", "wert", "mittel", "Nachtraeglich korrigierter Wert."),
    ("SINGLE_VALUE/VALUE", "wert", "hoch", "Wert legacy, 15,2 % — hebt die historische Wert-Abdeckung spuerbar."),
    ("RANGE_VALUE/VALUE", "wert", "mittel", "Wertspanne legacy."),
    ("INITIAL_ESTIMATED_TOTAL_VALUE_CONTRACT", "wert", "hoch",
     "Urspruenglicher Schaetzwert. Gegen den Zuschlagswert gerechnet = Preisniveau je Vergabestelle."),
    ("COSTS_RANGE_AND_CURRENCY", "wert", "mittel", "Wert inkl. MwSt."),
    ("VAT_PRCT", "wert", "niedrig", "MwSt-Satz (19 % bei 64 %)."),
    ("VAL_TOTAL_AFTER", "wert", "mittel", "Wert NACH dem Nachtrag."),
    ("PAYABLE_DOCUMENTS/DOCUMENT_COST", "wert", "niedrig",
     "Die Vergabeunterlagen kosteten frueher Geld (10-30 EUR). Historisch interessant, heute obsolet."),
    ("EstimatedOverallContractQuantity", "wert", "mittel", "Menge — die 'wie viele Lizenzen'-Frage. Nur 0,5-0,7 %."),
    ("TOTAL_QUANTITY_OR_SCOPE", "wert", "mittel", "Menge und Umfang als Freitext."),
    # --- Unterlagen und Fristen ------------------------------------------------
    ("CallForTendersDocumentReference.Attachment", "unterlagen", "hoch",
     "DIREKTLINK zu den Vergabeunterlagen: 96,8 % der OFFENEN Leads. Unser portal_url liegt bei 44,5 % / DÖE 0 % — wir lesen das schlechtere Feld."),
    ("CallForTendersDocumentReference.DocumentType", "unterlagen", "niedrig",
     "ACHTUNG: 'non-restricted' heisst nicht RECHTLICH beschraenkt, NICHT 'ohne Konto ladbar'. An 5 Plattformen geprueft: alle verlangen Registrierung. Kein Verkaufsargument."),
    ("AdditionalInformationRequestPeriod.EndDate", "fristen", "hoch",
     "Frist fuer Bieterfragen — liegt vor der Angebotsfrist und wird staendig verpasst. Eigener Alert-Typ (28,7 % der offenen Leads)."),
    ("TenderValidityPeriod.DurationMeasure", "fristen", "hoch",
     "Bindefrist (60 Tage) = wie lange Kapazitaet gebunden bleibt. 66,7 % der offenen Leads."),
    ("MINIMUM_TIME_MAINTAINING_TENDER", "fristen", "mittel", "Bindefrist historisch."),
    ("OpenTenderEvent.Occurrence", "fristen", "mittel",
     "Submissionstermin (oeffentliche Angebotsoeffnung), 42,4 % der offenen Leads."),
    ("OpenTenderEvent.Description", "fristen", "mittel",
     "Darf man bei der Oeffnung dabei sein? 'gemaess §14 VOB/A sind keine Bieter zugelassen'."),
    ("EXISTENCE_AUTHORISED_PERSONS", "fristen", "niedrig", "Dasselbe historisch."),
    ("PLACE_OPENING", "fristen", "niedrig", "Wo die Submission stattfindet."),
    ("ProcurementDocumentsChangeDate", "fristen", "mittel", "Die Unterlagen wurden geaendert — eigener Alert."),
    ("DD_DATE_REQUEST_DOCUMENT", "fristen", "niedrig", "Frist zur Unterlagen-Anforderung (historisch)."),
    ("ParticipationRequestReceptionPeriod", "fristen", "mittel", "Teilnahmeantragsfrist."),
    ("DATE_AWARD_SCHEDULED", "fristen", "niedrig", "Geplantes Zuschlagsdatum."),
    ("DISPATCH_INVITATIONS", "fristen", "niedrig", "Wann die Einladungen rausgehen."),
    # --- Eignung ---------------------------------------------------------------
    ("SelectionCriteria.TendererRequirementTypeCode", "eignung", "hoch",
     "32 TYPISIERTE Eignungskriterien statt Freitext. Der Sprung von der Liste zur Empfehlung: 'zeig mir nur, was ich erfuelle'."),
    ("SelectionCriteria.Name", "eignung", "mittel", "Benannte Eignungskriterien."),
    ("RequiredCurriculaCode", "eignung", "mittel",
     "Lebenslaeufe gefordert (21-24 % ja) = mehrere Personentage Angebotsaufwand mehr."),
    ("RequiredFinancialGuarantee.GuaranteeTypeCode", "eignung", "hoch",
     "Bietungsbuergschaft gefordert (DÖE 59,7 %, davon provisional 53 %). Kapitalhuerde und K.-o.-Kriterium VOR dem Angebot."),
    ("RequiredFinancialGuarantee.Description", "eignung", "mittel", "Welche Sicherheit genau."),
    ("DEPOSITS_GUARANTEES", "eignung", "mittel", "Sicherheiten historisch."),
    ("CAPACITY_MIN_LEVEL", "eignung", "mittel", "Mindestanforderungen ('Zwingend:', 'Referenzen ueber...')."),
    ("CAPACITY_INFORMATION", "eignung", "mittel", "Eignungsanforderungen im Freitext."),
    ("ECONOMIC_OPERATORS_PERSONAL_SITUATION", "eignung", "mittel", "Eignung, Freitext."),
    ("SecurityClearanceTerm", "eignung", "niedrig", "Sicherheitsueberpruefung noetig."),
    ("RESERVED_PARTICULAR_PROFESSION", "eignung", "niedrig", "Berufsvorbehalt (PBefG u. ae.)."),
    ("SubmissionMethodCode", "eignung", "mittel",
     "Elektronische Abgabe Pflicht -> Portal-Registrierung noetig, das dauert."),
    ("TITLE_QUALIFICATION_SYSTEM", "eignung", "mittel",
     "Praequalifikationsverfahren — die Profil-Skizze wuenscht sich PQ-Register als externe Quelle."),
    # --- Wettbewerbe -----------------------------------------------------------
    ("Prize.ValueAmount", "wettbewerbe", "hoch", "Preisgeld (30.000 EUR). Fuer ein Architekturbuero DIE Zahl."),
    ("RESULT_CONTEST/PRIZE_VALUE", "wettbewerbe", "hoch", "Preissumme historisch (66.000-70.000 EUR)."),
    ("AWARDED_PRIZE/VAL_PRIZE", "wettbewerbe", "hoch", "Preissumme (bis 913.150 EUR)."),
    ("TechnicalCommitteePerson", "wettbewerbe", "hoch",
     "Die Preisrichter NAMENTLICH. Wer die Jury kennt, weiss ob die Teilnahme lohnt."),
    ("MEMBERS_NAME", "wettbewerbe", "hoch", "Preisgericht namentlich, in Reihenfolge."),
    ("PROCEDURE/MEMBER_NAME", "wettbewerbe", "hoch", "Dasselbe legacy."),
    ("PARTICIPANTS_NAME", "wettbewerbe", "hoch", "Teilnehmer NAMENTLICH ('Ingenhoven Architekten')."),
    ("PROCEDURE/PARTICIPANT_NAME", "wettbewerbe", "hoch", "Dasselbe."),
    ("FollowupContractIndicator", "wettbewerbe", "hoch", "Folgeauftrag in Aussicht (true bei 42 %)."),
    ("BindingOnBuyerIndicator", "wettbewerbe", "mittel", "Ist der Jury-Entscheid bindend?"),
    ("AWARD_PRIZES/PARTICIPANTS_NUMBER", "wettbewerbe", "mittel", "Teilnehmerzahl (bis 335)."),
    ("RESTRICTED_CONTEST/PARTICIPANTS_NUMBER", "wettbewerbe", "mittel", "Teilnehmerzahl begrenzte Wettbewerbe."),
    ("DATE_DECISION_JURY", "wettbewerbe", "niedrig", "Datum des Preisgerichts."),
    ("DETAILS_PAYMENTS_PARTICIPANTS", "wettbewerbe", "niedrig", "Aufwandsentschaedigung."),
    ("CRITERIA_EVALUATION_PROJECTS", "wettbewerbe", "mittel", "Bewertungsmassstab des Preisgerichts."),
    # --- Aenderungen und Ergebnis ----------------------------------------------
    ("ContractModification.ChangeReason.ReasonCode", "aenderungen", "hoch",
     "Nachtraege: add-wss 74-76 % = zusaetzliche Leistungen. Beziehungs- UND Volumensignal: wer drin ist, waechst mit."),
    ("ContractModification.ChangeReason.ReasonDescription", "aenderungen", "hoch",
     "'Ein AN-Wechsel verursacht erhebliche Termin...' — Auftragnehmerwechsel im Klartext."),
    ("ADDITIONAL_NEED", "aenderungen", "mittel", "Zusaetzliche Leistungen historisch."),
    ("UNFORESEEN_CIRCUMSTANCE", "aenderungen", "mittel", "Unvorhersehbare Umstaende."),
    ("Change.ChangeReason.ReasonCode", "aenderungen", "hoch",
     "In DÖE: cancel 25 % = AUFHEBUNG der Ausschreibung, amtlich."),
    ("DEL/MIXED", "aenderungen", "mittel", "'The awarding procedure has been discontinued'."),
    ("WHERE/LABEL", "aenderungen", "hoch",
     "Berichtigungs-Diff: WELCHES Feld geaendert wurde ('Schlusstermin fuer den Eingang der Angebote')."),
    ("OLD_VALUE", "aenderungen", "hoch", "Alter Wert der Berichtigung."),
    ("NEW_VALUE", "aenderungen", "hoch", "Neuer Wert — zusammen: 'Frist wurde vom X auf den Y verschoben'."),
    ("LotResult.TenderResultCode", "ergebnis", "hoch",
     "'Kein Gewinner' JE LOS, amtlich (clos-nw 9 %). Unser verfahren_status ist heute erschlossen — das hier ist die Quelle."),
    ("ReceivedSubmissionsStatistics", "ergebnis", "hoch", "Bieterstatistik je Los, feiner als unser num_tenders."),
    ("LotTender.RankCode", "ergebnis", "mittel",
     "Rang der Angebote — 651 Notices tragen Rang >1, also einen unterlegenen Bieter. Zu wenig fuer eine Gewinnquote, aber 'wer wurde Zweiter' ist sichtbar."),
    ("AppealRequestsStatistics", "ergebnis", "mittel",
     "Nachpruefungsantraege (14 % der Verfahren) plus deren Art. 'Diese Stelle wird angegriffen' = Verfahrensrisiko."),
    ("FieldsPrivacy", "ergebnis", "hoch",
     "WARUM ein Feld leer ist ('Wert zurueckgehalten, Geschaeftsgeheimnis') und ab wann es oeffentlich wird (2034/2035). Ehrlichkeit als Feature — passt exakt zu unseren Herkunfts-Flags."),
    ("NB_TENDERS_RECEIVED_EMEANS", "ergebnis", "niedrig", "Elektronisch eingereichte Angebote."),
    ("NB_TENDERS_RECEIVED_OTHER_EU", "ergebnis", "niedrig", "Auslaendische Bieter (93-97 % null)."),
    # --- Wiederkehr ------------------------------------------------------------
    ("RecurringProcurementDescription", "wiederkehr", "hoch",
     "'Schuelerbefoerderung', 'IV. Quartal 2027' — der Kaeufer nennt den naechsten Termin SELBST. Wiederkehr-Prognose ohne Modell."),
    ("TIME_FRAME_SUBSEQUENT_CONTRACTS", "wiederkehr", "hoch",
     "Wiederkehr-Intervall explizit in Monaten (12 bei 56 %)."),
    ("RECURRENT_PROCUREMENT", "wiederkehr", "mittel", "'1/2018', '2019' — naechster Termin historisch."),
    ("RECURRENT_CONTRACT/NUMBER_POSSIBLE_RENEWALS", "wiederkehr", "mittel", "Zahl der Verlaengerungen."),
    ("PlannedDate", "wiederkehr", "mittel",
     "Geplantes Veroeffentlichungsdatum der eigentlichen Ausschreibung (aus der Vorinformation)."),
    ("ESTIMATED_TIMING", "wiederkehr", "niedrig", "'2024', '2025' — grober Zeitpunkt."),
    ("ContractExtension.MaximumNumberNumeric", "wiederkehr", "mittel",
     "Verlaengerungsoptionen -> echter Vertragswert ueber die Grundlaufzeit."),
    ("ContractExtension.OptionsDescription", "wiederkehr", "niedrig", "Was die Option umfasst."),
    ("OPTION_DESCRIPTION", "wiederkehr", "niedrig", "Dasselbe historisch."),
    # --- Ort -------------------------------------------------------------------
    ("RealizedLocation.Address.Region", "ort", "hoch",
     "anyw-cou 80-95 % = ORTSUNABHAENGIG erbringbar. Unsere Radius-Suche filtert diese 4.144 Leads heute FAELSCHLICH weg — das ist ein Fehler, kein fehlendes Feature."),
    ("RealizedLocation.Address.CityName", "ort", "mittel",
     "Leistungsort als Ortsname (DÖE 24,5 %); wir haben nur NUTS."),
    ("RealizedLocation.Address.AdditionalStreetName", "ort", "mittel", "Strassenadresse des Leistungsorts."),
    ("PlannedPeriod.StartDate", "ort", "mittel",
     "Geplanter Vertragsbeginn AUS der Ausschreibung statt geschaetzt — hebt duration_source von 'geschaetzt' auf 'echt'."),
    ("PlannedPeriod.EndDate", "ort", "mittel", "Dasselbe fuer das Ende."),
    ("PlannedPeriod.DescriptionCode", "ort", "niedrig", "UNLIMITED = unbefristeter Vertrag."),
    # --- Nachhaltigkeit und Foerderung ----------------------------------------
    ("ProcurementAdditionalType.ProcurementTypeCode", "nachhaltigkeit", "mittel",
     "env-imp 3 % / soc-obj 2 % — Umwelt- und Sozialziele als Vergabekriterium, bei 53,3 % Abdeckung."),
    ("StrategicProcurement", "nachhaltigkeit", "niedrig",
     "Clean-Vehicles-Richtlinie: veh-acq, vehicles-zero-emission, Fahrzeugklassen m1/n1/n3. Winzig, aber wer E-Busse verkauft will genau diese Liste."),
    ("FundingProgramCode", "foerderung", "mittel", "EU-Foerderung ja/nein (2-5 %)."),
    ("Funding.FundingProgramCode", "foerderung", "hoch", "Die Programme NAMENTLICH: ERDF, ERDF_2021, JTF."),
    ("FinancingIdentifier", "foerderung", "mittel", "Foerdermittel-Kennung."),
    ("EU_PROGR_RELATED", "foerderung", "mittel", "'EFRE', 'FAG-Foerderung des Freistaates' — Foerdertext historisch."),
    ("RELATES_TO_EU_PROJECT", "foerderung", "mittel", "Dasselbe."),
    # --- Abwicklung ------------------------------------------------------------
    ("SENDER/LOGIN", "abwicklung", "hoch",
     "Der eSender — WER die Ausschreibung tatsaechlich abwickelt. Ein Buero als eSender betreut laufend Vergaben: ein eigener Lead-Typ (das Buero, nicht die Behoerde)."),
    ("OTHER_BEHALF_CONTRACTING_AUTORITHY", "abwicklung", "mittel",
     "Zentrale Beschaffungsstelle handelt fuer andere."),
    ("ContractingRepresentationType", "abwicklung", "mittel", "cpb-awa: zentrale Beschaffungsstelle."),
    ("ADDRESS_CONTRACTING_BODY_ADDITIONAL", "abwicklung", "niedrig", "Zweiter Auftraggeber (Sammelvergabe)."),
    ("PayerParty", "abwicklung", "mittel", "Wer zahlt — nicht immer der Kaeufer."),
    ("FinancingParty", "abwicklung", "mittel", "Wer finanziert."),
    ("REFERENCE_NUMBER", "abwicklung", "mittel",
     "Aktenzeichen des Kaeufers ('VOB GB3 23/024-36 EU') — Anknuepfung an die Unterlagen eines Kunden."),
    ("FILE_REFERENCE_NUMBER", "abwicklung", "mittel", "Dasselbe."),
    # --- Verweise --------------------------------------------------------------
    ("NoticeDocumentReference.ID", "verweise", "mittel",
     "Verweis auf die zugehoerige Ausschreibung (cn->can). Unser award_tender_link deckt 51 % — das hier ist der AMTLICHE Verweis."),
    ("PREVIOUS_PUBLICATION_NOTICE", "verweise", "hoch", "Vorgaenger-Bekanntmachung, amtlich statt rekonstruiert."),
    ("REF_NOTICE/NO_DOC_OJS", "verweise", "mittel", "Dasselbe fuer ojs (50,5 %)."),
    ("TEXT.RN", "verweise", "mittel", "Dasselbe fuers Textformat (46,4 %)."),
    ("OTHER_PREVIOUS_PUBLICATION", "verweise", "niedrig", "Weitere Vorgaenger."),
    ("EX_ANTE_NOTICE_INFORMATION", "verweise", "niedrig", "VEAT-Verweis (Direktvergabe-Vorankuendigung)."),
    # --- Direktvergabe ---------------------------------------------------------
    ("D_JUSTIFICATION", "direktvergabe", "hoch",
     "Begruendung fuer die Direktvergabe — die Auftraege, die OHNE Wettbewerb vergeben wurden."),
    ("REASON_CONTRACT_LAWFUL", "direktvergabe", "hoch", "Dasselbe."),
    ("ProcessJustification", "direktvergabe", "mittel", "Begruendung der Verfahrenswahl ('§ 15 Abs. 4 VgV')."),
    ("ACCELERATED_PROC", "direktvergabe", "niedrig", "Begruendung beschleunigtes Verfahren."),
    # --- E-Auktion -------------------------------------------------------------
    ("ELECTRONIC_AUCTION", "eauktion", "mittel",
     "Bei einer E-Auktion gewinnt man LIVE ueber den Preis — voellig andere Angebotsvorbereitung. Wer das nicht vorher weiss, verliert."),
    ("AuctionTerms", "eauktion", "mittel", "Dasselbe in eForms."),
    ("EAUCTION", "eauktion", "mittel", "Zusatzangaben zur E-Auktion."),
    # --- OEPNV -----------------------------------------------------------------
    ("PUBLIC_SERVICE_OBLIGATIONS", "oepnv", "niedrig",
     "OEPNV-Direktvergaben nach VO 1370/2007 — ein kompletter Fachbereich mit Qualitaetskennzahlen als Pflichtfeld. Winzige Abdeckung, aber fuer Verkehrsunternehmen der ganze Vertragsinhalt."),
    ("PUNCTUALITY_RELIABILITY", "oepnv", "niedrig", "Puenktlichkeit als Vertragskennzahl."),
    ("CLEANLINESS_ROLLING_STOCK", "oepnv", "niedrig", "Sauberkeit der Fahrzeuge."),
    ("CUST_SATISFACTION_SURVEY", "oepnv", "niedrig", "Fahrgastzufriedenheit."),
    ("COMPLAINT_HANDLING", "oepnv", "niedrig", "Beschwerdemanagement."),
    ("CANCELLATIONS_SERVICES", "oepnv", "niedrig", "Ausfaelle."),
    ("KM_TRANSPORT_SERVICES", "oepnv", "niedrig", "Fahrplan-Kilometer (390.000-8,1 Mio)."),
    ("NB_KILOMETRES", "oepnv", "niedrig", "Dasselbe."),
    ("CONTRACTOR/OWNERSHIP", "oepnv", "mittel",
     "Eigentuemerstruktur des Betreibers — Konzernaufloesung ohne Handelsregister."),
    ("EXCLUSIVE_RIGHTS_GRANTED", "oepnv", "niedrig", "Ausschliessliche Rechte."),
    # --- Sonstiges -------------------------------------------------------------
    ("FORM_LG_LIST", "sonstiges", "niedrig",
     "3 % der Bekanntmachungen erscheinen 13-sprachig = bewusst grenzueberschreitend ausgeschrieben."),
    ("AdditionalNoticeLanguage", "sonstiges", "niedrig", "Zusaetzliche Sprachen — grenzueberschreitendes Interesse."),
    ("SMESuitableIndicator", "sonstiges", "mittel", "'Fuer KMU geeignet', amtlich (true 57 %)."),
    ("ORIGINAL_CPV", "sonstiges", "niedrig", "CPV als Text-Label; wir haben die Codes plus dim_cpv_label."),
    ("SOCIAL_STANDARDS", "sonstiges", "niedrig", "Sozialstandards."),
    ("PERFORMANCE_CONDITIONS", "sonstiges", "niedrig", "Tariftreue, Vergabemindestentgelt."),
    ("UltimateBeneficialOwner", "datenschutz", "nicht_nutzbar",
     "ACHTUNG: traegt FirstName, ResidenceAddress und private Faxnummern natuerlicher Personen. Die Privatanschrift eines wirtschaftlich Berechtigten gehoert NICHT ins Frontend. Verwendbar allenfalls die EXISTENZ der Verknuepfung fuer die Konzernaufloesung."),
    ("TenderResult.AwardDate", "datenqualitaet", "nicht_nutzbar",
     "Traegt zu 33 % (eForms) bzw. 51 % (DÖE) den Platzhalter 2000-01-01. Unser Parser liest einen anderen Pfad (0 von 494.361 betroffen) — nicht umstellen."),
]


def kuratiert(path: str) -> tuple[str, str, str]:
    for muster, cluster, bewertung, idee in KURATIERT:
        if muster in path:
            return cluster, bewertung, idee
    return "", "", ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/export/feld_inventar.csv")
    ap.add_argument("--only-unused", action="store_true",
                    help="nur ungenutzte Pfade (Default: alle, inkl. der genutzten)")
    args = ap.parse_args()

    con = duckdb.connect()
    where = "WHERE NOT is_used" if args.only_unused else ""
    rows = con.execute(f"""
        SELECT schema_gen, path, coverage_pct, n_notices, n_values, max_length,
               example_value, is_attribute, is_used, derived_column
          FROM read_parquet('{INVENTORY}') {where}
         ORDER BY schema_gen, coverage_pct DESC
    """).fetchall()

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    stats = {}
    with out.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")          # ; für Excel-DE
        w.writerow(["generation", "pfad", "abdeckung_pct", "notices", "werte",
                    "max_laenge", "beispielwert", "ist_attribut", "wird_genutzt",
                    "silber_spalte", "kategorie", "cluster", "bewertung", "idee"])
        for (gen, path, cov, nn, nv, ml, ex, is_attr, used, derived) in rows:
            kat = kategorie(path)
            cl, bew, idee = kuratiert(path)
            if not bew and used:
                # Genutzte Pfade brauchen keine Potenzialbewertung — sie sind bereits
                # in einer Silber-Spalte. Sonst blaeht 'ungeprueft' die Statistik auf
                # und verdeckt die Zeilen, um die es geht.
                bew = "bereits_genutzt"
                idee = f"landet in {derived}" if derived else ""
            if not bew and kat != "inhaltlich":
                bew = "nicht_nutzbar"
                idee = f"regelbasiert als '{kat}' eingestuft — nicht einzeln bewertet"
            if is_attr and bew in ("hoch", "mittel", "niedrig"):
                # Attribute (@listName, @currencyID …) erben das Muster ihres Elements.
                # Das ist meist richtig — @listName nennt die Codeliste zum Code — aber
                # es ist eine ABGELEITETE Bewertung, keine eigene. Muss erkennbar sein.
                bew = f"{bew}_attribut"
                idee = "Attribut zum bewerteten Element: " + idee
            if not bew:
                # NICHT "ungeprueft": diese Pfade wurden im vollstaendigen Durchgang
                # gesichtet (legacy/ojs als Cluster ueber die letzten zwei Pfadsegmente,
                # eForms/DÖE/text einzeln), haben aber keine Notiz verdient. Der
                # Unterschied zu "nicht_nutzbar" ist, dass hier keine Regel griff —
                # es ist ein inhaltliches Feld ohne erkennbaren Produktwert.
                bew = "gesichtet_kein_befund"
                idee = ("im Durchgang gesichtet, kein eigener Produktwert erkennbar — "
                        "meist Formularvariante eines bereits bewerteten Feldes")
            w.writerow([gen, path, f"{cov:.2f}".replace(".", ","), nn, nv, ml,
                        (ex or "")[:200], "ja" if is_attr else "nein",
                        "ja" if used else "nein", derived or "", kat, cl, bew, idee])
            stats[bew or "ungeprueft"] = stats.get(bew or "ungeprueft", 0) + 1

    print(f"{len(rows):,} Zeilen → {out}")
    for k, v in sorted(stats.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<16} {v:>6,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
