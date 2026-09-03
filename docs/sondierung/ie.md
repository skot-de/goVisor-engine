# Sondierung Irland

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.** Kein Connector, keine Tabelle, kein Kapitel in
> `docs/laender/`.

**Stand 2026-09-03.**

---

## 1. Ein Land, eine Plattform, eine bekannte Software

| | |
|---|---:|
| `etenders.gov.ie` am Unterlagen-Feld | **98,9 %** (5.845 von 5.912, 12 Monate) |
| Domains insgesamt | 20 |
| Links, die ein Verfahren nennen | **99 %** |

⚠ **Der zweite Wert ist der wichtigere**, und er stammt aus der Lehre des griechischen
Kapitels: dort führten **43 %** der Links nur auf eine Startseite. In Irland sind es **1 %**
(32 von 2.174). Das ist die sauberste Verlinkung der ganzen Sondierung.

Und die Plattform ist keine neue: die Startseite nennt als Hersteller **European Dynamics**,
Kontextpfad `/epps` — **dieselbe Software wie Litauens `viesiejipirkimai.lt`**, das einzige
Land, das bisher als vollständig offen belegt war.

Die Adressen sind wortgleich:
```
LT   https://viesiejipirkimai.lt/epps/cft/listContractDocuments.do?resourceId=…
IE   https://www.etenders.gov.ie/epps/cft/listContractDocuments.do?resourceId=7741546
```

**robots.txt: liefert die Startseite (weiches 404) — keine Beschränkung.**

## 2. ✅ Die litauische Kette funktioniert unverändert

Dreistufig, servergerendert, ohne Browser:

```
1  GET /epps/cft/listContractDocuments.do?resourceId=7741546
       → 200, HTML mit downloadDocForAnonymous('7769371') je Datei
2  GET /epps/cft/prepareAnonymousDownload.do?resourceId=…&documentId=…
3  GET /epps/cft/downloadContractDocument.do?documentId=…&resourceId=…
       → 200, die Datei
```

Belegt am 2026-09-03:

```
Lu Festival of Light Request for Tender Document 2026.docx        64.836 B
TENDER COMPANION DOCUMENT - Lu- Festival of Light 2026 .docx   1.701.456 B
c4t_7741546_1.xml                                                    815 B
```

⚠ **Die dritte Datei ist mehr als eine Beigabe.** Sie trägt die **Wertungsstruktur
typisiert**:

```xml
<c4t cftid="7741546" procedure="accelerated.open"
     eval-type="prompt.lowest.price" num-of-lots="0" round="1">
  <envelope type="offline" …><section …><label>Complete Tender</label>
    <criterion level="1" pos="1" …>
```

Verfahrensart, Wertungsart, Loszahl und die Kriterien als Baum — nicht als Fliesstext in
einem PDF, sondern maschinenlesbar. Wer Zuschlagskriterien auswertet, bekommt sie hier
geschenkt, statt sie aus Dokumenten zu erschliessen.

## 3. Gemessen, nicht am Glücksfall: 86 %

Ein einzelner geglückter Abruf sagt nichts. **44 Vergaben aus dem letzten Monat, jede
einzeln geprüft:**

| | Anzahl | Anteil |
|---|---:|---:|
| anonym, mit gelisteten Dokumenten | **38** | **86 %** |
| hinter CAS-Anmeldung | 6 | 14 % |
| erreichbar, aber ohne Dateien | 0 | 0 % |

**199 Dateien** über die 38 offenen Vergaben (2 bis 9 je Vergabe).

⚠ **Die 14 % sind kein Rauschen, sondern eine echte Grenze.** Diese Vergaben leiten auf
`Central Authentication Service` um — Benutzername und Passwort. Ein Abrufer muss damit
rechnen und darf eine Umleitung nicht als Fehler zählen; sie ist die normale Antwort für
einen Teil des Bestands.

Irland ist damit **nicht** „offen wie Litauen", sondern **86 % offen** — und diese Zahl ist
gemessen, nicht geschätzt.

## 4. Die unterschwellige Ebene liegt auf derselben Plattform

Die **erweiterte Suche ist ohne Anmeldung erreichbar**
(`/epps/prepareAdvancedSearch.do?type=cftFTS`) und führt unter den Filtern:

```
Threshold:  - Select Threshold -  /  Above  /  Below
```

**Damit ist die Frage nach Ebene 2 beantwortet, ohne sie zu vermuten:** eTenders führt
ober- **und** unterschwellige Verfahren, und der Unterschied ist ein Filterwert, kein
zweites Portal. Das ist die polnische Lage (eine zentrale Quelle), nicht die deutsche
(ein Dutzend Portale).

Dazu ein öffentliches Verzeichnis der laufenden Vergaben:
```
GET /epps/prepareCurrentOpportunities.do?mode=cft
    → 200: „Displaying: 1-10 | 2.931 results in total"
```

**2.931 laufende Vergaben, anonym, ohne TED.** Zum Vergleich: Irland hatte in vier Monaten
2.163 TED-Ausschreibungen.

⚠ **Was NICHT funktioniert hat:** das Blättern. Der Parameter `d-3680175-p=N` liefert bei
1, 2 und 5 **dieselben zehn** Kennungen — die Seite hält den Stand offenbar in der Sitzung,
nicht in der Adresse. Aufzählen ist also möglich, aber der Weg dahin ist noch nicht
gefunden. **Offen, nicht gelöst.**

⚠ Und eine Falle beim Suchen: Pfade zu raten bringt hier nichts. `/cft/rss.do`,
`/cft/searchNoticeAction.do` und `/opendata` antworten mit **500 bzw. 404 — aber auf einer
Fehlerseite der Anwendung**, nicht mit einem klaren Signal. Dieselbe Lage wie bei der
estnischen API. Der Weg führte über die **echte Navigation der Startseite**, nicht über
Vermutungen.

## 5. Die dritte Ebene

**Fonds-Ebene: nicht recherchiert.** Irland ist ein kleiner Kohäsionsempfänger, damit nach
der Regel aus [`fonds-ebene.md`](fonds-ebene.md) nachrangig — aber ungeprüft ist ungeprüft.

## 6. Was Irland für den Plan bedeutet

| Land | Domains | belegt offen | Aufwand |
|---|---:|---:|---|
| **LT** | 2 | ~99 % | European Dynamics |
| **IE** | 20 | **86 %** | **derselbe Abrufer** |
| PT | 25 | 88,8 % | zwei eigene |
| GR | 112 | *bedingt* | Sitzung nötig |

**Der Abrufer für Litauen deckt Irland mit.** Das ist der zweite Fund dieser Art an einem
Tag — nach der Erkenntnis, dass LV, PT-AnoGov und GR-ΕΣΗΔΗΣ **dieselbe** sitzungsführende
Bauform brauchen.

⚠ Daraus folgt eine Frage, die die Sondierung bisher nicht gestellt hat: **nicht „welches
Land als nächstes", sondern „welche Software als nächstes".**

**Diese Frage ist jetzt beantwortet** — die Prüfung über alle Länder hat zwei weitere
Staaten gefunden, die dieselbe Kette fahren und nie angesehen wurden: **Malta und Zypern,
beide 100 % anonym.** Eigenes Kapitel: [`european-dynamics.md`](european-dynamics.md).
