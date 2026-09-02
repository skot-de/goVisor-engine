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

## 4. ⚪ Estland — ungeprüft

`riigihanked.riik.ee` (RHR), 100 % des Landes, keine robots-Sperre. Die TED-Adressen sind
Deeplinks mit Fragment-Routing:
```
https://riigihanked.riik.ee/rhr-web/#/procurement/10174386/documents?group=B
```
Das `#` heißt: eine JS-Anwendung, deren API erst zu finden ist. Ein erster geratener
Endpunkt (`/rhr-web/api/public/procurements/<id>`) gab 404.

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
