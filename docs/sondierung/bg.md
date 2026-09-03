# Sondierung Bulgarien

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.** Kein Connector, keine Tabelle, kein Kapitel in
> `docs/laender/`.

**Stand 2026-09-03.**

---

## 1. Der sauberste Fall der ganzen Sondierung

| | |
|---|---:|
| `app.eop.bg` (ЦАИС ЕОП) am Unterlagen-Feld | **100,0 %** (9.135 von 9.137, 12 Monate) |
| Domains insgesamt | 3 (die anderen zwei je **1** Nennung) |
| Links, die ein Verfahren nennen | **100 %** (2.056 von 2.056) |
| Vergaben mit abrufbaren Dokumenten | **97 %** (28 von 29) |

Und die robots.txt ist ein Novum:

```
User-agent: Googlebot
Disallow: /nogooglebot/

User-agent: *
Allow: /
```

⚠ **Das ist die erste robots der ganzen Sondierung, die ausdrücklich ERLAUBT.** Bisher gab
es nur zwei Sorten: Sperren (SK, GR-nepps, SE) oder Schweigen (404, weiches 404, 403). Ein
`Allow: /` ist eine Aussage, kein Fehlen einer Aussage — und beendet jede Uneindeutigkeit
der Sorte, die bei Vortal offenblieb.

## 2. Die Kette: drei Aufrufe, alle anonym

Die Seite ist eine Angular-Anwendung; `curl` bekommt 7,5 KB „Loading…". Dahinter liegt ein
WCF-Dienst auf einem **eigenen Host** — das ist der Grund, warum das Netzprotokoll des
Browsers zunächst leer aussah.

```
1  POST https://service.eop.bg/NX1Service.svc/GetPublishedTenderDetails
       {"tenderId":582421,"ianaTimeZone":"Europe/Sofia"}
       → 450 KB JSON, darin TenderDescriptionDocuments[]

2  POST https://service.eop.bg/NX1Service.svc/GetSignedUrlByDocumentId
       {"documentId":54804187}
       → { BaseUri, Container, CloudName, Url: <vorsignierte S3-Adresse> }

3  GET  https://storage.eop.bg/user-110343/02c6ce23-…?X-Amz-Expires=1800&X-Amz-Signature=…
       → 200, die Datei
```

⚠ **Der `Url` ist eine vorsignierte AWS-S3-Adresse mit 30 Minuten Gültigkeit**
(`X-Amz-Expires=1800`). Ein Abrufer darf sie nicht zwischenspeichern und später verwenden —
sie muss unmittelbar vor dem Herunterladen erzeugt werden.

**Belegt am 2026-09-03:** `ТЕХНИЧЕСКА СПЕЦИФИКАЦИЯ (44).docx`, **65.411 Bytes**.

### Die Schnittstelle liefert die Prüfsumme mit

Je Dokument stehen `Name`, `Extension`, `Size`, `MimeType` — **und `MD5Hash`**:

```
MD5 der heruntergeladenen Datei:  608EF477644657AF8464C8535028941A
MD5 laut Schnittstelle:           608EF477644657AF8464C8535028941A
```

⚠ Das ist mehr als eine Bequemlichkeit: eine **Integritätsprüfung frei Haus**. Kein anderes
Portal dieser Sondierung liefert das. Ein Abrufer kann einen halben Download erkennen, statt
ihn als Datei abzulegen — und die `Size`-Angabe erlaubt, vor dem Abruf zu entscheiden, ob
man ihn will.

## 3. ⚠ Zwei Fehler auf dem Weg, beide vermeidbar

**Der 500er war ein fehlender Parameter, kein Verbot.** `{"tenderId":576411}` allein gab
HTTP 500. Die Signatur ist `(tenderId, ianaTimeZone)` — sie steht im Klartext unter
`service.eop.bg/NX1Service.svc/**js**`, dem WCF-Aufrufgerüst.

> Das ist derselbe Fall wie Vortals leeres `languageCode` und Estlands zu enger
> `Accept`-Kopf. **Dritter Beleg in drei Ländern.**

**Und ein Auslesefehler bei mir:** ich griff mit `.get("d", {})` auf die Antwort zu — die
Antwort ist aber nicht in `d` verpackt. Ergebnis: fünf Vergaben zeigten „0 Dokumente" und
`CanDownload=None`, obwohl die Seite im Browser drei Dateien listete. Beim ersten Aufruf
hatte ich `.get("d", d)` benutzt, was auf die volle Antwort zurückfiel und richtig war.

⚠ **Die Falle: mein Fehler sah aus wie ein Befund.** „Bulgarien liefert keine Dokumente"
wäre eine plausible Aussage gewesen, sauber gemessen und komplett falsch. Was sie auffliegen
liess, war der Widerspruch zur Browser-Ansicht — nicht die Zahl selbst.

## 4. ✅ Aufzählbar ohne TED

Der Suchaufruf war nicht zu erraten (drei Formen gaben 500). Er liess sich aber
**mitschneiden**, indem `XMLHttpRequest.send` in der laufenden Anwendung überschrieben und
die App dann selbst zur Trefferliste navigiert wurde:

```
POST /NX1Service.svc/GetPublishedTendersBySpecified
  {"searchParameters":{"StartIndex":1,"EndIndex":50,"PropertyFilters":[],"SearchText":"",
    "SearchProperty":{"PropertyName":"Status","PropertyValue":"1"},
    "OrderAscending":false,"OrderColumn":"PublicationDate","Keywords":[]}}
  → ResultsCount: 1.403 · CurrentPageResults: 50
```

**1.403 laufende Vergaben, anonym, geblättert.** Je Treffer neben Käufer, Frist und Wert:

```
IsEUFunding · IsGreenCriteria · IsSocialService · IsSecurityAndDefense
IsFrameworkAgreement · IsProtectedJobs · AggregateOfferCount
```

⚠ `AggregateOfferCount` ist die **Zahl der eingegangenen Angebote** — genau die Grösse, aus
der `single_bidder` und die Verdrängbarkeit gerechnet werden. Bulgarien liefert sie direkt,
statt sie aus dem Zuschlag erschliessen zu müssen.

## 5. Datenmenge und Personendaten

**274,7 MB aus 29 Vergaben** — im Schnitt **9,5 MB je Vergabe**, 2,4 MB je Datei. Das ist
mit Abstand der grösste Umfang je Vergabe in der Sondierung. Hochgerechnet auf 9.137
Unterlagen-Links im Jahr wären das grob **85 GB jährlich** allein für Bulgarien.

⚠ **Und die Schnittstelle gibt Personendaten heraus, ohne dass man danach fragt.** Je
Dokument stehen `Owner` (der Klarname der bearbeitenden Person: „Жани Велинова", „Нелина
Ковачева"), `OwnerId`, `CreatedById` und ein Feld `PersonalDataConsent: True`.

Das ist kein Versehen des Portals — es ist Teil des öffentlichen Registers. Für uns heisst
es: **diese Felder gehören nicht ungefiltert in Bronze.** goVisor hat dafür bereits eine
Stelle (PII-Schwärzung aus Ticket 23); sie müsste beim Anschluss greifen, nicht danach.

## 6. Die anderen beiden Ebenen

**Unterschwellig:** ЦАИС ЕОП ist das *zentrale* Register — bulgarische Vergabestellen sind
verpflichtet, dort zu veröffentlichen, nicht nur oberschwellig. Die 1.403 laufenden Vergaben
gegen rund 685 TED-Ausschreibungen im Monat deuten darauf hin, dass das Register mehr trägt
als TED. ⚠ **Deuten, nicht belegen** — ein Bestand (1.403 offen) und ein Fluss (685/Monat)
sind nicht direkt vergleichbar. Ein Filter auf „unterschwellig" wurde nicht gefunden.

**Fonds-Ebene:** nicht recherchiert. ⚠ Aber die Trefferliste trägt `IsEUFunding` — damit
liesse sich die EU-geförderte Teilmenge unmittelbar abgrenzen. Das ist noch nicht die
Fonds-Ebene (das wären Vergaben *privater* Fördermittelempfänger), aber der erste Anhaltspunkt,
den ein Land der Sondierung dafür geliefert hat.

## 7. Ergebnis

| | |
|---|---|
| Ausschreibungen | ✅ vollständig, anonym, **aufzählbar** (1.403 offen) |
| Dokumente | ✅ **97 %**, mit MD5 und Grösse vorab |
| robots | ✅ **ausdrücklich `Allow: /`** |
| Aufwand | drei Aufrufe, kein Browser nötig |
| ⚠ Vorsicht | S3-Adresse 30 min gültig · Personendaten in der Antwort · 9,5 MB je Vergabe |

**Bulgarien ist das am besten erschlossene Land der Sondierung** — besser als Litauen, weil
es zusätzlich aufzählbar ist, Prüfsummen liefert und ausdrücklich erlaubt.

⚠ Und es lag zwölf Kapitel lang unangesehen da, weil die Reihenfolge nach Marktgrösse ging.
Dieselbe Lücke wie bei Malta und Zypern — siehe [`european-dynamics.md`](european-dynamics.md).
