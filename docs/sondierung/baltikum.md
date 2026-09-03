# Sondierung Baltikum — Litauen, Lettland, Estland

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.**

**Stand 2026-09-03.** Drei Länder in einem Kapitel, weil sie **strukturell identisch** sind.

---

## 1. Der größte Hebel der ganzen Sondierung

| Land | Ausschreibungen Juni | Anteil EU | Domains | Anteil der größten |
|---|---:|---:|---:|---:|
| **LT** | 737 | 2,0 % | **2** | 99 % |
| **LV** | 565 | 1,5 % | **1** | 100 % |
| **EE** | 325 | 0,9 % | **1** | 100 % |

**Ein-Plattform-Länder.** Lettland und Estland haben in einem ganzen Monat *je eine
einzige Domain*, Litauen praktisch auch. Alle drei sind staatliche Plattformen.

Zum Vergleich: Italien hat 538 Domains, Polen 511, Frankreich 443.

**Ein Abrufer deckt hier ein ganzes Land.** Das ist das beste Verhältnis von Aufwand zu
Ertrag, das die Sondierung gefunden hat — auch wenn die Länder klein sind.

Keines der drei hat eine robots.txt (404 bzw. weiches 404). Nichts untersagt.

## 2. ✅ Litauen — offen, und die Plattform sagt es selbst

`viesiejipirkimai.lt` (CVP IS), 99 % des Landes. Der Weg ist dreistufig und trägt seine
Absicht im Namen:

```
GET /epps/cft/listContractDocuments.do?resourceId=<n>      → Dokumentenliste (servergerendert!)
     … die Liste ruft downloadDocForAnonymous('<docId>')   ← der Name sagt alles
GET /epps/cft/prepareAnonymousDownload.do?resourceId=…&documentId=…
GET /epps/cft/downloadContractDocument.do?documentId=…&resourceId=…
```

Die Zwischenseite warnt auf Litauisch, sinngemäß: *„Sie sind nicht angemeldet, deshalb
kann das System Sie nicht mit der Vergabe verknüpfen und Sie nicht über Nachträge,
Berichtigungen oder Erläuterungen informieren."* Und bietet dann **ABBRECHEN** oder
**HERUNTERLADEN**.

**Derselbe Aufbau wie beim französischen AWS-Achat — nur ohne CAPTCHA.**

Belegt am 2026-09-03: **HTTP 200, `application/x-zip-compressed`, 410.064 Bytes**, ein
gültiges ZIP mit **sieben echten Vergabedokumenten**:

```
11838 Pirkimo dokumentu SPS AK (RLU) (1).docx
11838 SPS 2 priedas_Sutarties projektas (RLU) (1).docx   ← Vertragsentwurf
11838_SPS 1 priedas Technin specifikacija.docx           ← technische Spezifikation
3 priedas espd-request 11838.zip                         ← ESPD
BPS AK Pirkimo salygos.docx                              ← Vergabebedingungen
```

⚠ Und ein praktischer Vorteil: die **Dokumentenliste ist servergerendert**. `curl` bekommt
sie ohne Browser — anders als bei fast allen anderen Plattformen dieser Sondierung.

## 3. 🟡 Lettland — offen sichtbar, Abrufweg ungeklärt

`eis.gov.lv` (EIS), 100 % des Landes. Keine robots-Sperre.

Die Vergabeseite listet die Dokumente **öffentlich und vollständig** — im geprüften Fall
**33 Einträge** mit Typ, Datum und Bezeichnung („Iepirkuma priekšmeta 12.daļas prasības,
2.versija"). Der Download-Link trägt den Titel *„Lejupielādēt datni/-es"* (Datei
herunterladen).

Er ruft aber `viewDocument({...})`, und das öffnet ein **Modal per POST**:
```js
function viewDocument(n,t){openModal({data:n,url:t,type:"POST",containerId:"document-container"})}
```

Damit ist der eigentliche Dateiendpunkt nicht ohne Weiteres greifbar. **Kein Hinweis auf
eine Schranke** — die Liste ist öffentlich, nichts verlangt Anmeldung. Nur der Weg ist
verwinkelter als bei Litauen.

**Nachzuholen.** Ein Land mit einer einzigen Plattform ist die Mühe wert.

## 4. 🟡 Estland — Liste offen, Dateiendpunkt nicht gefunden

`riigihanked.riik.ee` (RHR), 100 % des Landes, keine robots.txt (404).

**Zwei offizielle Wege, beide ohne Anmeldung:**

Die Seite führt einen Menüpunkt **„Avaandmed"** (offene Daten). Er sagt: Bekanntmachungen
gibt es **monatsweise zum Herunterladen oder über eine Maschinenschnittstelle**, nächtlich
aktualisiert, im eForms-XSD-Schema. ⚠ Das betrifft die **Bekanntmachungen**, nicht die
Unterlagen — dasselbe Muster wie DECP in Frankreich.

Und eine öffentliche REST-API unter `/rhr/api/public/v1/`:

```
GET /rhr/api/public/v1/proc-vers/<verId>/documents/general-info
    → 200, JSON: procurementDocuments[] mit name, fileName, fileSize,
      failservId, visibilityCode, documentSubtypeCode
```

Geprüft an einer Vergabe der Eesti Pank: **9 Dokumente**, alle mit
`visibilityCode: "PUBLIC"` — die Plattform kennzeichnet sie ausdrücklich als öffentlich.

**Den Dateiendpunkt habe ich nicht gefunden.** Fünf plausible Pfade probiert (`failserv/`,
`file/`, `document/<id>/file`, …) — alle 500. ⚠ Und das ist die Falle: **diese API
antwortet auf einen unbekannten Pfad mit 500, nicht mit 404.** Raten liefert also kein
Signal, und der Klick im Browser löste keinen Netzaufruf aus, den ich mitlesen konnte.

⚠ **Ein Fund, der für jede weitere API zählt:** mein erster Aufruf mit
`Accept: application/json` gab **500**. Mit `Accept: application/json, text/plain, */*`
kam **HTTP 200 und 586 KB**. Die Schnittstelle war nie zu — meine Kopfzeile war zu eng.
Wer bei einer 500 aufhört, hält eine offene Tür für verschlossen.

**Nachzuholen.** Ein Land, eine Plattform, Dokumente ausdrücklich als öffentlich markiert —
es fehlt nur der letzte Aufruf.

## 5. Warum das für den Plan zählt

Die Sondierung hat bisher gezeigt, dass große Länder viel Arbeit machen: Italien 538
Domains, Frankreich 443. Das Baltikum dreht das Verhältnis um.

| | Domains | Ausschreibungen je Domain |
|---|---:|---:|
| LV | 1 | **565** |
| EE | 1 | **325** |
| LT | 2 | **369** |
| DE | — | ~50 |
| IT | 538 | **3** |

**Wer nach Ertrag je Abrufer sortiert statt nach Landesgröße, fängt im Baltikum an.**
