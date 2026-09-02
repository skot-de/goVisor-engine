# Sondierung Polen

> ⚠ **SONDIERT, NICHT AUFGENOMMEN — mit einer Besonderheit.** Polen hat bereits
> Gold-Tabellen auf **Bekanntmachungsebene** (`vorgaenge`, aus dem DACH-Lauf mitgeschrieben).
> Auf **Unterlagenebene** ist nichts angebunden, und darum geht es hier. Die Wache
> `scripts/pruefe_sondierung.py` muss diese beiden Ebenen unterscheiden können.

**Stand 2026-09-02.** Portallandschaft aus dem TED-Monatspaket 2026-06 (im Cache).
Schrankenprüfung an je einer laufenden Vergabe, robots.txt zuerst, keine Konten.

---

## 1. Mengengerüst

| | |
|---|---:|
| Bekanntmachungen im Juni 2026 | **10.179** — mehr als Frankreich (8.027) |
| davon mit Portal-URL | 5.352 (53 %) |
| verschiedene Domains | 513 |

## 2. Engines — konzentrierter als Frankreich

| Engine | Anteil | Betreiber |
|---|---:|---|
| `openNexus` (platformazakupowa.pl) | **30 %** | Open Nexus, privat |
| `marketplanet` (`*.ezamawiajacy.pl`) | **21 %** | Marketplanet, mandantenfähig |
| `ezamowienia` (ezamowienia.gov.pl) | **19 %** | **staatliche Plattform (UZP)** |
| `eb2b` | 8 % | privat |
| `logintrade` | 6 % | privat |
| `propublico` | 4 % | privat |
| unbekannt | 11 % | |

**Sechs Engines decken 89 %.** In Frankreich waren es 75 % bei 25 % unbekannt.

## 3. Schranke — geprüft

### ✅ `ezamowienia.gov.pl` (19 %) — OFFEN, und zwar vollständig

**Das ist die erste offene Tür der ganzen Sondierung.** Drei Ebenen, alle ohne Anmeldung:

**Die Bekanntmachungen** über eine offizielle API, ohne Antrag und kostenfrei:

```
GET /mo-board/api/v1/notice?NoticeType=ContractNotice
                           &PublicationDateFrom=…&PublicationDateTo=…
```
→ HTTP 200, JSON. ⚠ Und sie trägt `isTenderAmountBelowEU` — also **auch die
unterschwellige Ebene** (BZP, das nationale Bulletin). Damit beantwortet dieselbe
Schnittstelle Frage 1 und Frage 2 des Auftrags.

**Die Dokumentenliste** je Vergabe:
```
GET /mp-readmodels/api/Search/GetTenderDocuments?tenderId=<ocds-id>
```
→ HTTP 200, JSON mit Dateinamen und Objekt-IDs.

**Die Dateien selbst:**
```
GET /mp-readmodels/api/Tender/DownloadDocument/<tenderId>/<objectId>
```
→ **HTTP 200, `application/pdf`, 464.178 Bytes, 25 Seiten.** Mit blankem `curl`, ohne
Sitzung, ohne Cookie, ohne CAPTCHA. Am 2026-09-02 an der SWZ der Gmina Gryfów Śląski
(`2026/BZP 00404874/01`) geprüft.

Dass das gewollt ist, sagt die Plattform selbst an zwei Stellen: die Endpunkte heißen
`GetTenderOfferForms**ForUnauthorizedUser**Query`, und jede polnische Bekanntmachung trägt
das Pflichtfeld

> „Zamawiający zastrzega dostęp do dokumentów zamówienia: **Nie**"
> *(Der Auftraggeber beschränkt den Zugang zu den Vergabeunterlagen: nein)*

⚠ Das Feld ist **strukturiert und je Vergabe gesetzt** — es sagt uns also vorab, wo ein
Abruf überhaupt Sinn hat. Kein anderes bisher gesehenes Land liefert diese Angabe.

### ⛔ `openNexus` / platformazakupowa.pl (30 %) — verboten, nicht verschlossen

Die Dateien hängen offen an der Vergabeseite, ohne Login:
`https://platformazakupowa.pl/file/get_new/<hash>.pdf`

Und genau dieser Pfad ist in der robots.txt gesperrt:

```
User-agent: *
Crawl-delay: 900
Allow: /
Disallow: /file/get_new/*
```

**Technisch offen, ausdrücklich untersagt.** Der Betreiber erlaubt das Durchsuchen (mit
900 Sekunden Wartezeit zwischen zwei Abrufen) und verbietet punktgenau das Herunterladen
der Dateien. Eindeutiger kann eine Absicht nicht formuliert sein. Nicht abgerufen.

### Noch offen

`marketplanet` (21 %), `eb2b` (8 %), `logintrade` (6 %), `propublico` (4 %) —
zusammen 39 %, ungeprüft.

## 4. Was Polen von Frankreich unterscheidet

| | FR | PL |
|---|---|---|
| Bekanntmachungen (Juni) | 8.027 | **10.179** |
| Engines für ~90 % | 6 (75 %) | **6 (89 %)** |
| offizielle API | keine | **ja, ohne Antrag** |
| unterschwellige Quelle | DECP, **nur nach Zuschlag** | **BZP, laufende Verfahren** |
| Dokumente ohne Schranke | **0 %** | **19 % bestätigt** |

**Frankreich war zu. Polen ist zu einem Fünftel offen — und das offene Fünftel ist die
staatliche Plattform, also der Teil, der nicht morgen seine Meinung ändert.**

## 5. Empfehlung

Ein Abholer für `ezamowienia` ist **drei Endpunkte weit** und braucht weder Konto noch
Browser-Automatik. Er wäre der erste Abrufer außerhalb Deutschlands — und der einzige
bisher gefundene, der auch die unterschwellige Ebene mitbringt.

⚠ Vor dem Bauen: die robots.txt von `ezamowienia.gov.pl` enthält buchstäblich nur `as`,
also keine Regel. Das ist keine Erlaubnis, sondern eine kaputte Datei. Bei einem Abholer
gehört ein höflicher Takt gesetzt, unabhängig davon, dass niemand ihn verlangt.

---

## 6. Nachtrag 2026-09-02: die unterschwellige Ebene, direkt gemessen

Die Abschnitte oben stützen sich auf TED — und TED kennt nur oberschwellige Vergaben.
Über die BZP-API lässt sich die andere Ebene **direkt** messen, und sie sieht anders aus.

**Größe:** an einem Tag (01.09.) mindestens **400** unterschwellige Ausschreibungen; 400
ist die Seitenobergrenze der API, der wahre Wert liegt darüber. Zum Vergleich: TED-Polen
hat ~340 Bekanntmachungen am Tag über **alle** Notice-Arten. Die Ebene, die aus TED
unsichtbar ist, ist damit **mindestens so groß wie die sichtbare.**

**Gewichtung, je Bekanntmachung gezählt:**

| Engine | oberschwellig (TED) | unterschwellig (BZP) |
|---|---:|---:|
| `ezamowienia` | 19 % | **35 %** |
| `openNexus` | 30 % | 31 % |
| `marketplanet` | 21 % | 17 % |
| `logintrade` | 6 % | 6 % |
| `eb2b` | 8 % | 4 % |
| `propublico` | 4 % | 3 % |

**Das verbessert die Lage.** Die eine Engine, die nachweislich offen ist, ist unterschwellig
die größte — 35 % statt 19 %. Und genau dort liegt die Menge.

## 7. Die vier übrigen Engines — geprüft am 2026-09-02

| Engine | ober / unter | Urteil |
|---|---:|---|
| `marketplanet` | 21 / 17 % | 🟡 **frei im Browser, nicht per Skript** |
| `eb2b` | 8 / 4 % | 🟡 **Katalog öffentlich, Unterlagen nicht** |
| `logintrade` | 6 / 6 % | ⛔ **robots.txt verbietet die Anlagen** |
| `propublico` | 4 / 3 % | ⛔ **Login-Wand** |

**`marketplanet`** hat keine robots.txt. Die Dokumentenliste steht offen samt Dateinamen
und Größen, der Pfad heißt sogar `/app/demand/notice/**public**/…/downloadsiwz`. Der
Download läuft aber zweistufig: ein POST liefert eine signierte Adresse unter
`/repository/download/zip/<token>`, und die ist **sitzungsgebunden** — im Browser
funktioniert sie, mit blankem `curl` kommt eine 404-Seite. Kein Konto nötig, aber kein
Automat. Dieselbe Kategorie wie Bund und AI-evergabe in Deutschland.

**`eb2b`** hat keine robots.txt, und die Verfahrensliste ist öffentlich (5.142 Einträge,
als „Öffentlich" gekennzeichnet, 13 KB gerendert). Die **Verfahrensseite** dagegen rendert
nur Navigation und Cookie-Banner (2 KB), keine Unterlagen. Der Banner lässt nur
„Akzeptieren" oder „Seite verlassen" zu. ⚠ Ob Cookie-Wand oder Anmeldepflicht die Ursache
ist, habe ich **nicht getrennt** — dafür müsste ich die Zustimmung erteilen, und das ist
keine Entscheidung, die ich von mir aus treffe.

**`logintrade`** ist der klarste Fall nach Open Nexus:
```
User-agent: *
Disallow: /zalaczniki/        ← „załączniki" = Anlagen
Disallow: /DocumentService
```
Zweimal punktgenau die Dokumente. Nicht abgerufen.

**`propublico`** leitet die Startseite auf `/Account/SignIn` um. (Die Zertifikatskette
wird unvollständig ausgeliefert — ein technischer Schönheitsfehler, keine Schranke.)

## 8. Polen vollständig

| Engine | ober | unter | Urteil |
|---|---:|---:|---|
| `ezamowienia` | 19 % | **35 %** | ✅ **offen, skriptfähig** |
| `openNexus` | 30 % | 31 % | ⛔ robots verbietet die Dateien |
| `marketplanet` | 21 % | 17 % | 🟡 nur im Browser |
| `eb2b` | 8 % | 4 % | 🟡 Zustimmung/Anmeldung |
| `logintrade` | 6 % | 6 % | ⛔ robots verbietet die Anlagen |
| `propublico` | 4 % | 3 % | ⛔ Login |
| unbekannt | 11 % | 4 % | offen |

**Skriptfähig sind 19 % oberschwellig und 35 % unterschwellig — beides dieselbe Engine,
die staatliche Plattform.** Alles Private ist zu, verboten oder browsergebunden.

⚠ **Bemerkenswert und für die anderen Länder zu prüfen:** die beiden Sperren stammen
nicht von Vergabestellen, sondern von **kommerziellen Betreibern**, die ihre Datei-Pfade
gezielt in die robots.txt setzen. Der Staat gibt heraus, die privaten Plattformen nicht.
Wenn sich dieses Muster wiederholt, ist die Frage je Land nicht „welche Engines gibt es",
sondern **„wie groß ist der staatliche Anteil"**.
