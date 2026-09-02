# Feasibility: Bieterfragen & Antworten als Datenquelle

**Stand:** 2026-07-27. Alle Zahlen unten sind an den echten Dateien gemessen
(`data/silver/DE/attributes` = 475.331.676 Zeilen, `data/gold/DE/lead_export.parquet`),
nicht aus dem Gedächtnis. READ-ONLY-Untersuchung, kein Code/DDL geändert.

## Frage

Bei jeder oberschwelligen Ausschreibung stellen Bewerber während der Angebotsfrist
**Bieterfragen** an die Vergabestelle; die Antworten müssen **allen** Bietern
diskriminierungsfrei bereitgestellt werden (§ 20 Abs. 3 EU-VgV / § 12a EU-VOB/A:
„zusätzliche Auskünfte … spätestens 6 Tage vor Fristablauf, über dieselben
elektronischen Mittel wie die Vergabeunterlagen"). Diese Q&A sind also faktisch
publiziert. Lassen sie sich automatisiert einholen und auswerten, und was folgt daraus?

---

> ⚠ **NACHTRAG 2026-09-02: Die Antwort unten gilt nur für die untersuchte Quelle.**
> Diese Studie hat die **eForms-Attribute der Bekanntmachungen** durchsucht — dort stimmt das
> Ergebnis. Die Bieterfragen stecken jedoch in den **Vergabeunterlagen** (Bieterinformation,
> Bieterfragenkatalog, Bieterrundschreiben): 257 Vorgänge, 172 mit lesbarem Text, 1.336
> Abschnitte. Sie sind seit dem 02.09. im Lead-Detail sichtbar
> (`scripts/export_bieterfragen.py`).
>
> Das Übergabepapier hat aus dieser Studie ein *existiert nicht und ist nicht abgreifbar*
> gemacht und damit das nach eigener Einschätzung stärkste Ziel für erledigt erklärt. Eine
> Studie beantwortet die Frage, die sie gestellt hat — nicht die, für die man sie später
> zitiert.

## 1. Sind Bieterfragen/Antworten in unseren vorhandenen Daten? — In den Bekanntmachungen nein.

Das `attributes`-Sammelfeld (475,3 Mio. path/value-Zeilen) nach allen plausiblen
eForms-/Legacy-Pfaden durchsucht. Ergebnis:

**Fragen- oder Antwort-Text existiert nicht.** Die einzigen Pfade, die überhaupt
„question/answer/clarif" enthalten:

| Pfad (normalisiert) | Zeilen | Notices | Bedeutung |
|---|---:|---:|---|
| `PriorInformationNotice…EformsExtension.AnswerReceptionPeriod.EndDate` | 99 | 98 | **Frist**, bis wann die Vergabestelle antwortet — nur PIN, verschwindend selten |
| `…AnswerReceptionPeriod.EndTime` | 99 | 98 | dito |

Das ist **kein Inhalt**, sondern ein Datum. Kein Feld trägt Fragetexte, Antworttexte
oder ein „Bieterinformationen"-Bulletin.

Auch `notices` und `requirements` enthalten keine Q&A: `notices.description`/`title`
sind der Ausschreibungstext selbst; `requirements.text` sind Eignungs-/Zuschlags­
kriterien (Ausschlussgründe, Referenzen), also die *Vorgaben* der Stelle — nicht die
*Kommunikation* mit Bietern.

### Was tatsächlich in den Daten liegt: nur die Metadaten *um* die Q&A herum

Diese Felder sind vorhanden und **hoch abgedeckt** — sie beschreiben Frist, Zuständigen
und den Ort, an dem die Q&A stattfindet, aber nie deren Inhalt:

| eForms-Pfad (CN) | distinkte Notices | Was es ist |
|---|---:|---|
| `…TenderingTerms.CallForTendersDocumentReference.Attachment.ExternalReference.URI` | **539.489** | Deep-Link zu den Vergabeunterlagen auf dem Portal |
| `…TenderingTerms.AdditionalInformationParty.PartyIdentification.ID` | 187.346 | Org, die Zusatzauskünfte/Antworten erteilt |
| `…TenderingProcess.AdditionalInformationRequestPeriod.EndDate` | **116.227** | **Frist für Bieterfragen** („bis wann fragen") |
| `…TenderingProcess.AccessToolsURI` | 107.724 | URL des e-Vergabe-Portals (Kommunikationskanal) |

Und im Gold-Layer ist der Portal-Einstieg bereits konsolidiert
(`lead_export.documents_url`):

| phase | Leads | `documents_url` | `source_url` (TED) |
|---|---:|---:|---:|
| **open** | 12.123 | **96,6 %** | 32,5 % |
| expiring | 73.811 | 0,0 % | 95,1 % |

**Kernbefund:** Für **offene** Ausschreibungen (genau die, bei denen Bieterfragen
gerade laufen) haben wir zu **96,6 %** den Portal-Deep-Link — den Einstiegspunkt zur
Q&A. Den Q&A-**Inhalt** haben wir zu **0 %**. TED liefert die Tür, nicht den Raum.

Stichprobe der `documents_url` (offene Leads) — es sind Portal-Verfahrensseiten, unter
denen die „Bieterkommunikation"/„Nachrichten"/„Fragen & Antworten" als Unterbereich hängt:

```
https://www.dtvp.de/Satellite/notice/CXVHY5UYT89EY6Y8/documents
https://vergabemarktplatz.brandenburg.de/VMPSatellite/notice/CXVPYYDYTWXEPLTN/documents
https://www.meinauftrag.rib.de/public/DetailsByPlatformIdAndTenderId/platformId/2/tenderId/207652
https://www.evergabe-online.de/tenderdocuments.html?id=871055
https://www.had.de/NetServer/TenderingProcedureDetails?function=_Details&TenderOID=…
```

**DÖE (oeffentlichevergabe.de):** Die DÖE-`attributes`-Partition ist leer
(`data/silver/DE/attributes/doe/` = 0 Dateien); DÖE liefert den dünnen
`eforms-sdk-0.1`-Dialekt (s. `data-sources.md`), der nicht einmal Losstruktur kennt —
**erst recht keine Q&A**. Als CC0-API ist sie eine Notice-Metadaten-Quelle, kein
Q&A-Kanal.

---

## 2. Wo die Q&A tatsächlich publiziert werden

**Nicht in TED.** eForms hat kein Q&A-Feld; wird eine Frage grundsätzlich beantwortet,
erscheint höchstens eine **Berichtigung** (F14/eForms `Change`) — und die trägt nur den
*geänderten* Wert (Frist, Dokument-Indikator: `ProcurementDocumentsChangeIndicator`
13.804 Notices), nicht den Frage-/Antwort-Dialog.

**Sondern auf dem jeweiligen e-Vergabe-Portal**, im Verfahrensbereich
„Bieterkommunikation" / „Nachrichten" / „Fragen und Antworten" / „Bieterinformationen".
Rechtlich muss die Antwort allen Interessenten über denselben Kanal wie die Unterlagen
zugänglich sein — praktisch heißt das: **im Portal, meist hinter einer (kostenlosen)
Registrierung/Anmeldung für genau dieses Verfahren.** Einige Portale zeigen die Q&A
öffentlich neben den Unterlagen; viele gaten sie hinter Login.

### Portal-Landschaft (gemessen an ~1,02 Mio. Dokument-/Zugangs-URLs)

**1.251 distinkte Domains**, aber stark konzentriert:

| Top-N Portale | kumulierte Abdeckung |
|---|---:|
| Top 5 | 39,9 % |
| Top 10 | 55,6 % |
| Top 20 | 76,5 % |
| Top 30 | 84,8 % |
| Top 50 | 94,1 % |

Größte Portale: DTVP (145.609), evergabe-online.de/Bund (77.968),
meinauftrag.rib.de (76.039), evergabe.de (67.818), Vergabemarktplatz Brandenburg
(38.879), Niedersachsen (37.496), evergabe.nrw.de (31.876), subreport (30.966),
deutsche-evergabe (≈60k über zwei Hosts), aumass (29.183) …

**Entscheidend:** Die 1.251 Domains sind überwiegend **White-Label-Instanzen von nur
~8–12 Plattform-Engines** (cosinex/DTVP+Vergabemarktplatz, RIB/meinauftrag,
Administration Intelligence/evergabe-online, subreport ELViS, Healy Hudson/
deutsche-evergabe, aumass, cosinex-Länderportale, Staatsanzeiger-eServices, Mercell …).
Ein Crawler pro **Engine** — nicht pro Domain — deckt den Großteil ab. Es gibt für die
Q&A **keine offene API** auf irgendeinem dieser Portale.

---

## 3. Was ließe sich aus Q&A ableiten — und wie belastbar

| Signal | Ableitung | Belastbarkeit / Extrahierbarkeit |
|---|---|---|
| **Bieterinteresse / -dichte (Frühindikator)** | viele Fragen ⇒ viel Interesse ⇒ vermutlich mehr Bieter | **Mittel.** Anzahl Fragen ist ohne LLM zählbar. Aber Fragenzahl ≠ Bieterzahl (eine kritische Frage vs. 20 Detailfragen eines einzigen Interessenten). Nützlich als weiches „hier ist was los"-Signal, nicht als Bieterzahl-Prognose. Ergänzt `single_bidder`/`n_bidders` (die erst *nach* Zuschlag vorliegen) um einen **Vorlauf-Indikator**. |
| **Mehrdeutigkeit/Lücken in der Leistungsbeschreibung** | viele Verständnisfragen ⇒ schlecht spezifiziert | **Mittel**, nur mit LLM-Klassifikation der Fragen. Wertvoll, weil unsere Freitextlage ohnehin dünn ist (Median 432 Zeichen inkl. Lose). |
| **Faktische Präzisierungen der Anforderungen** | Antworten nennen konkrete Mengen/Techniken/Fristen, die im Notice fehlen | **Hoch inhaltlich, niedrig strukturiert.** Genau das Material, das die dünne `requirements`/`description`-Lage füllen würde — aber nur als LLM-Extraktion aus PDF/HTML pro Verfahren. Teuer je Lead. |
| **Fristverlängerung** | Antwort/Änderung verschiebt Angebotsfrist | **Hoch** — und teilweise **schon ohne Q&A** aus eForms `Change`/F14 ableitbar (13.804 Dok-Änderungen). Q&A liefert nur die *Begründung*. |
| **Faktische Vorfestlegung / Zuschnitt auf einen Anbieter** | Frage „Produkt X gefordert, gibt es gleichwertige?" + ausweichende Antwort ⇒ Zuschnitt | **Das stärkste, aber unsicherste Signal.** Extrem wertvoll für „hier lohnt sich Bieten nicht / hier ist ein Incumbent zementiert", aber nur per LLM-Interpretation des Dialogs, hohe Fehlerquote, rechtlich heikel zu behaupten. Eher Recherche-Hinweis als Fakt. |
| **Fragen-Timing** | späte Fragenflut kurz vor Frist | schwach; Nebenprodukt. |

Alle inhaltlichen Signale (die interessanten) brauchen **LLM-Extraktion aus
unstrukturiertem PDF/HTML pro Verfahren**. Nur „Anzahl Fragen" und „Frist verschoben"
sind billig/robust — und Letzteres haben wir teilweise schon.

---

## 4. Machbarkeit der automatisierten Einholung

**In-Data:** entfällt — der Inhalt ist nicht da (Abschnitt 1).

**Portal-Crawling** ist der einzige Weg, und er ist **brüchig**:

- **Kein API, überall Login.** Q&A hängt fast durchweg hinter verfahrensbezogener
  Registrierung. Registrierung/Account-Anlage und Login sind laut Betriebsrichtlinie
  **untersagt** (Accounts anlegen, Passwörter eingeben) — das wäre also nicht einmal
  vollautomatisierbar, ohne diese Grenze zu berühren. Öffentlich sichtbare Q&A gibt es
  nur auf einem Teil der Portale.
- **~8–12 Engines, je eigener Crawler**, plus laufende Pflege (Portale ändern Layout,
  Session-Handling, teils CAPTCHAs/Bot-Schutz).
- **Format PDF vs. HTML gemischt** — Antworten oft als angehängtes „Bieterinformation
  Nr. n"-PDF ⇒ PDF-Parsing + LLM je Dokument.
- **Rechtlich/robots:** Zugang „für alle Bieter" heißt nicht „für anonyme Bots";
  Scraping hinter Login und AGB-Zustimmung ist die problematische Zone.
- **Aufwand grob:** MVP für die 2–3 größten Engines (öffentlich sichtbare Q&A, ohne
  Login) = überschaubar (Tage), deckt vielleicht 20–40 % der offenen Leads *und nur die
  ungegateten*. Voll-Abdeckung inkl. Login-Portale = Dauer-Betriebslast (Wartung > Bau),
  plus die Login-Grenze oben. Danach je Verfahren LLM-Kosten für die Inhalts-Extraktion.

**Keine API-Quelle** liefert das (auch DÖE nicht, s. o.).

---

## 5. Fazit & Empfehlung

**Q&A-Inhalte sind nicht in unseren Daten und über keine Quelle sauber automatisiert
einzuholen.** Sie leben verstreut auf ~8–12 Portal-Engines (1.251 Domains), meist hinter
Login, als gemischtes PDF/HTML, ohne API. Der Ertrag ist zwar attraktiv — vor allem der
**Bieterinteresse-Frühindikator** und der **Vorfestlegungs-/Zuschnitt-Hinweis** —, aber
jedes belastbare Signal daraus erfordert LLM-Extraktion je Verfahren, und die Beschaffung
selbst kollidiert teils mit der Login-/Account-Grenze.

**Einordnung: „nice, aber teuer und brüchig" — nicht für V1, nicht für V2.**

Begründung aus den Zahlen:
- Der **Adressraum ist klein**: nur **12.123 offene Leads** überhaupt (Q&A nur hier
  relevant) — der ganze Crawl-Apparat zahlt auf ein Zwölftel des Bestands ein.
- Die **billigen Teile haben wir schon oder fast**: Portal-Deep-Link zu 96,6 %
  (`documents_url`), Fristverschiebung teils aus eForms `Change`, Fragefrist
  (`AdditionalInformationRequestPeriod`, 116k CN) ist ohne jeden Crawl als
  strukturiertes Feld einsammelbar.
- Die **teuren Teile** (Fragen zählen, Zuschnitt erkennen) skalieren mit Crawler-Pflege
  × LLM-Kosten × Portal-Vielfalt — schlechtes Verhältnis, solange die Kernprodukte
  (Radar, Score, Marktchancen) noch reifen.

**Konkrete, günstige Zwischenschritte, die den 80/20-Nutzen mitnehmen ohne den Apparat:**

1. **Fragefrist als Feld ziehen** — `AdditionalInformationRequestPeriod.EndDate` (116k CN,
   strukturiert, schon im `attributes`) als „Fragen möglich bis"-Datum in den Lead-Export
   heben. Nutzt dem Nutzer sofort („noch X Tage, um Fragen zu stellen"), null Crawling.
2. **`documents_url` ist bereits der richtige CTA** — im Frontend als „Zu den Unterlagen
   & Bieterkommunikation" verlinken; der Nutzer holt die Q&A selbst dort, wo er ohnehin
   registriert bieten muss.
3. **Frist-Änderungen** aus eForms `Change`/F14 als schwaches „das Verfahren bewegt sich"-
   Signal — ohne Portal-Crawl.
4. Falls überhaupt ein Crawl-Pilot: **nur die 2–3 größten Engines mit öffentlich
   sichtbarer Q&A und ohne Login**, rein zur Messung „wie viele Fragen ~ Bieterdichte" —
   als Forschungsspike (Negativ-/Positivbefund), nicht als Produktfeature.

---

## Zusammenfassung (für den Nutzer)

- **Q&A-Inhalte stehen zu 0 % in unseren Daten** (475 Mio. `attributes`-Zeilen geprüft):
  TED/eForms hat kein Fragen-/Antwort-Feld — nur Frist, Zuständigen und den Portal-Link.
- **Wir haben aber die Tür**: für offene Ausschreibungen zu **96,6 % den Portal-Deep-Link**
  (`documents_url`) und für 116.227 CN die **Fragefrist** als strukturiertes Feld.
- **Die Q&A selbst liegen auf ~8–12 Portal-Engines (1.251 Domains), meist hinter Login,
  als PDF/HTML, ohne API** — Crawling ist brüchig, dauerpflege-intensiv und berührt teils
  die Account-/Login-Grenze.
- **Ertrag wäre real** (Bieterinteresse-Frühindikator, Zuschnitt-/Vorfestlegungs-Hinweis),
  aber jedes belastbare Signal braucht LLM-Extraktion je Verfahren — schlechtes Verhältnis
  bei nur 12.123 offenen Leads.
- **Empfehlung: nicht für V1/V2 bauen.** Stattdessen billig mitnehmen: Fragefrist als Feld,
  `documents_url` als CTA, Frist-Änderungen aus eForms `Change`. Ein Crawl höchstens als
  begrenzter Forschungsspike auf den 2–3 größten Engines mit öffentlicher Q&A.
