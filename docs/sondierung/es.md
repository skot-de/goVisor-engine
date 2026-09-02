# Sondierung Spanien

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.** Keine Zeile in `data/gold` oder `data/silver`.

**Stand 2026-09-02.** Landschaft aus dem TED-Monatspaket 2026-06, Schranken an je einem
Fall geprüft, robots.txt zuerst, keine Konten.

---

## 1. Mengengerüst

⚠ **Die Zahlen dieses Kapitels wurden am 2026-09-02 korrigiert.** Die erste Fassung zählte
alle Notice-Arten und meldete 40 % Portalabdeckung — den schlechtesten Wert der Sondierung.
Das war mein Nenner, nicht Spanien:

| Notice-Art | ES | mit Unterlagen-Link |
|---|---:|---:|
| **ContractNotice** | 2.458 | **100 %** |
| ContractAwardNotice | 3.499 | 0 % |
| PriorInformationNotice | 396 | 3 % |

Zuschlagsbekanntmachungen tragen keinen Unterlagen-Link, weil die Vergabe vorbei ist.
Spanien hat besonders viele davon, deshalb sah es am schlechtesten aus. Gezählt wird jetzt
nur `ContractNotice`, und dann liegen alle drei Länder bei 97 bis 99 %.

| | ES | FR | PL |
|---|---:|---:|---:|
| Ausschreibungen Juni | 2.458 | 5.683 | 5.381 |
| mit Portal-URL | **99 %** | 97 % | 99 % |
| verschiedene Domains | **75** | 443 | 511 |

**75 Domains gegen 443 und 511.** Spanien ist dramatisch zentralisierter, und die Spitze ist
fast durchweg **öffentliche Hand**.

| Engine | Anteil | Träger |
|---|---:|---|
| `placsp` | **63 %** | Staat |
| `euskadi` | 9 % | Baskenland |
| `andalucia` | 8 % | Andalusien |
| `cat-pscp` | **5 %** | Katalonien |
| `madrid` | 4 % | Madrid |
| `galicia` / `navarra` | je 1 % | Regionen |
| unbekannt | 9 % | |

⚠ **Zweite Korrektur:** Katalonien trägt **5 %**, nicht die zuerst gemeldeten 14 %. Die
höhere Zahl stammte aus Domain-Nennungen über alle Notice-Arten. Andalusien ist damit
größer als Katalonien — und ungeprüft.

## 2. Schranke — geprüft

### ⛔ PLACSP (63 %) — gesperrt, und das ist ein Widerspruch in sich

```
User-agent: *
Disallow: /
```

Die gesamte Staatsplattform ist für Automaten untersagt. **Gleichzeitig** betreibt sie
einen dokumentierten Open-Data-Ausgang: ZIP-Pakete und ATOM-Syndikation im CODICE-XML-
Format, samt eigenem Werkzeug (OpenPLACSP, EUPL-lizenziert). Eine Syndikation ist ihrem
Wesen nach für Maschinen gedacht — und liegt auf demselben Host, den robots.txt sperrt.

⚠ Auch der Umweg über das nationale Portal `datos.gob.es` trägt nicht: dessen robots.txt
sperrt `/api/` und die Datenexporte.

⚠ **Am 2026-09-02 nachgeprüft:** PLACSP betreibt einen **zweiten Host**,
`contrataciondelsectorpublico.gob.es`. Auch dort steht `User-agent: * / Disallow: /`.
Die Sperre ist also **konsistent, nicht versehentlich auf einem Server** — und es gibt
keinen unbelasteten Weg zu denselben Daten.

**Das ist keine technische Frage, sondern eine an den Betreiber.** Ein `Disallow: /` neben
einem Open-Data-Angebot ist vermutlich Unachtsamkeit — aufzulösen durch Nachfragen, nicht
durch einen Umweg. Nicht abgerufen.

### ✅ Katalonien (14 %) — offen, und die kooperativste robots.txt der Sondierung

```
User-Agent: *
Allow: /
Visit-time: 18:00-07:00
Crawl-delay: 1
Request-rate: 60/1m
```

Der Betreiber erlaubt nicht nur, er nennt seine Wunschbedingungen. Zwei Endpunkte, beide
anonym mit blankem `curl` bestätigt:

```
GET /portal-api/perfils-contractant/llistat-documents-organ/<id>   → JSON
GET /portal-api/descarrega-document/<docId>/<hash>                 → PDF
```
→ **HTTP 200, `application/pdf`, 572.366 Bytes, 24 Seiten.** Keine Sitzung, kein Cookie.

✅ **Am 2026-09-02 an echten Vergabeunterlagen nachgeholt.** An einer **am selben Tag
veröffentlichten** Ausschreibung (Ajuntament de Cabra del Camp, Frist 22.09.):

```
GET /portal-api/detall-publicacio-expedient/300873140          → JSON mit „plecsDeClausulesAdministratives"
GET /portal-api/descarrega-document/302562190/C0217B60…        → PCAP ALT CAMP.pdf
```
→ **HTTP 200, `application/pdf`, 859.193 Bytes, 30 Seiten.** Anonym, blankes `curl`.
Das sind die Pliegos selbst, nicht ein Profildokument. Die Frage ist damit geklärt.

⚠ Und eine Eigenheit, die beim Bauen zählt: **TED verlinkt bei Katalonien nur das
Käuferprofil, nicht die einzelne Vergabe.** Der Deeplink ist gröber als in DE oder PL — der
Weg von der Bekanntmachung zur Datei ist damit einen Schritt länger.

### ⛔ Baskenland (8,5 %)

Lange Sperrliste, und darunter ausgerechnet `Disallow: /anuncio_contratacion/` — die
Vergabebekanntmachungen selbst.

### ⛔ Galicien (1 %)

`disallow: /`, mit fünf namentlich erlaubten Seiten (Startseite, Fragen, Abo, Anleitung).

### 🔗 Andalusien (8 %) — nicht gesperrt, sondern kaputt

**Eine neue Kategorie, und sie war in keinem der bisherigen Länder aufgetaucht.** Andalusien
sperrt nichts. Seine Adressen führen nur ins Leere:

| Host | Bezüge | Zustand |
|---|---:|---|
| `sirecftdpriexp.chap.junta-andalucia.es` | 86 | ⛔ **DNS löst nicht auf** |
| `ceh.junta-andalucia.es` | 52 | ⛔ **Zertifikat passt nicht** (es gilt für `*.juntadeandalucia.es`, ohne Bindestrich) |
| `sspa.juntadeandalucia.es` | 26 | ⚠ HTTP 403 |
| `sirecbkdexp.chap.junta-andalucia.es` | 6 | ⛔ DNS löst nicht auf |
| `juntadeandalucia.es` | 32 | ✓ erreichbar |

**170 von 206 Bezügen (83 %) sind tot oder abweisend.**

Die Ursache ist ein **Schreibfehler im Hostnamen**: die Bekanntmachungen nennen
`junta-andalucia.es` mit Bindestrich, das Zertifikat gilt für `juntadeandalucia.es` ohne.
Derselbe Pfad, auf den korrigierten Host gelegt, antwortet mit HTTP 200 — es ist dieselbe
Anwendung, nur unter dem richtigen Namen. (Sie ist allerdings eine JS-Anwendung ohne
servergerenderten Inhalt; von dort zu den Dateien wäre noch ein Stück Weg.)

⚠ Ein Fund mit Signalwirkung: **eine Adresse in TED ist kein Beleg, dass es die Seite
gibt.** Madrid trägt denselben Fehler in kleinerem Maßstab — `contratospublicos.comunidad.madrid`
(ohne Bindestrich, 10 Bezüge) und `edicion.contratos-publicos…` (12) lösen ebenfalls nicht auf.

### Erreichbarkeit insgesamt

Von 2.713 spanischen Portalbezügen gehen **1.978 (73 %) auf robots-gesperrte Hosts** —
die habe ich nicht angefragt. Von den übrigen 620:

| | |
|---|---:|
| erreichbar | **70 %** |
| Fehlerseite (403/404) | 4 % |
| **tot** (DNS, Zertifikat, TLS) | **26 %** |

### 🎯 Madrid (4 %) — die Adresse zeigt auf gar keine Vergabe

Madrids Hauptseite lebt (HTTP 200), zwei Nebenhosts nicht (`edicion.contratos-publicos…`
und `contratospublicos…` ohne Bindestrich — derselbe Schreibfehler wie in Andalusien).

Die robots.txt ist differenziert und sperrt unter anderem
`Disallow: /sites/default/files/**PCON**/*` — PCON dürfte für *Pliegos de Condiciones*
stehen, also die Unterlagen — sowie `/contratos?` mit Abfrageparametern. Der Pfad
`/contratos` selbst ist erlaubt.

**Geprüft werden musste das aber gar nicht, denn der Weg endet früher.** Madrids
Unterlagen-Adressen in TED nennen keine Vergabe:

| Adresse | Häufigkeit |
|---|---:|
| `https://contratos-publicos.comunidad.madrid/` | **162** |
| `https://contratos-publicos.comunidad.madrid` | 85 |
| `.../contratos` | 71 |

Von 380 Madrider Adressen tragen **0 %** eine Vergabe-Kennung. Der häufigste
„Unterlagen-Link" ist 162-mal die **Startseite**.

### 🎯 Und das ist keine Madrider Eigenheit

| Engine | Adressen | mit Vergabe-Kennung |
|---|---:|---:|
| PLACSP | 3.958 | **99 %** |
| Katalonien | 438 | 38 % |
| Baskenland | 748 | **0 %** |
| Madrid | 380 | **0 %** |
| Andalusien | 278 | **0 %** |

**Eine fünfte Kategorie, und sie sitzt nicht im Portal, sondern in der Bekanntmachung:**
Host erreichbar, robots erlaubend, Datei vorhanden — und trotzdem kein Weg hin, weil die
Adresse die Vergabe nicht benennt. Wer sie finden will, muss auf dem Portal nach Titel
oder Aktenzeichen suchen. Das ist ein anderes und viel schwereres Problem als ein Abrufer.

Über alle vier Länder, mit dem einzigen zwischen ihnen vergleichbaren Maß — Adressen, die
nichts als eine Portalwurzel enthalten:

| | FR | PL | ES | DE |
|---|---:|---:|---:|---:|
| nur Wurzel | **39 %** | 29 % | 23 % | 23 % |

⚠ **Eine Warnung zur eigenen Messung:** die Spalte „mit Vergabe-Kennung" ist zwischen
Ländern **nicht** vergleichbar, weil die Kennungsformate sich unterscheiden. Deutschland
erscheint mit 23 %, obwohl es das bestabgedeckte Land ist — cosinex benutzt Kennungen wie
`/notice/CXVHY5UYT89EY6Y8/`, die kein Ziffernmuster tragen und durch mein Raster fallen.
Innerhalb Spaniens ist die Spalte belastbar, zwischen Ländern nicht.

### Ungeprüft

Navarra (1 %) und der Rest des Schwanzes.

## 3. Was Spanien für den Plan bedeutet

**Die polnische Vermutung ist widerlegt.** Dort gab der Staat heraus und die kommerziellen
Betreiber sperrten — daraus hatte ich abgeleitet, die Frage je Land laute „wie groß ist der
staatliche Anteil". In Spanien ist es umgekehrt: die **nationale** Plattform sperrt alles,
eine **regionale** gibt vorbildlich heraus.

**Es ist also nicht Staat gegen privat, sondern Betreiber für Betreiber.** Damit fällt die
Abkürzung weg, auf die ich gehofft hatte — jede Engine muss einzeln angesehen werden.

**Stand nach drei Ländern:**

| Land | skriptfähig |
|---|---|
| DE | 32 % |
| FR | **0 %** |
| PL | 19 % ober, 35 % unter |
| ES | **14 % bestätigt**, 63 % gesperrt mit offener Frage |
