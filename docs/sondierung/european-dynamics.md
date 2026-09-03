# Sondierung: eine Software statt eines Landes

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.**

**Stand 2026-09-03.** Entstanden als Nebenfrage des irischen Kapitels und sofort geprüft.

---

## 1. Die Frage, die 30 Länderkapitel nicht gestellt haben

Die ganze Sondierung ist bisher **nach Ländern** vorgegangen: ein Kapitel, ein Markt, ein
Abrufer. Irland hat gezeigt, dass das die falsche Achse sein kann — seine Adressen sind
**wortgleich** mit den litauischen:

```
LT   https://viesiejipirkimai.lt/epps/cft/listContractDocuments.do?resourceId=…
IE   https://www.etenders.gov.ie/epps/cft/listContractDocuments.do?resourceId=…
```

Beide Portale stammen von **European Dynamics** (e-PPS). Also die naheliegende Frage:
**wer noch?** Ein Durchlauf über den letzten Monat, jede `/epps/`-Adresse nach Land:

| Land | Nennungen | Host | vorher geprüft? |
|---|---:|---|---|
| **LT** | 732 | `viesiejipirkimai.lt` | ✅ offen |
| **IE** | 539 | `etenders.gov.ie` | ✅ 86 % offen |
| **MT** | 145 | `etenders.gov.mt` | ❌ **nie angesehen** |
| **CY** | 104 | `eprocurement.gov.cy` | ❌ **nie angesehen** |
| LU | 5 | `etendersni.gov.uk` (Nordirland) | Ausreisser |

**Malta und Zypern kamen in keinem der bisherigen Kapitel vor.** Sie sind klein, also fielen
sie in einer nach Landesgrösse sortierten Reihenfolge immer hinten runter.

## 2. ✅ Beide antworten — ohne eine einzige Anmeldung

Dieselbe dreistufige Kette, unverändert, mit den Adressen aus TED:

| | geprüfte Vergaben | anonym mit Dokumenten | Dateien | Anmeldung |
|---|---:|---:|---:|---:|
| **MT** | 7 | **7 (100 %)** | 64 | 0 |
| **CY** | 7 | **7 (100 %)** | 46 | 0 |
| IE | 44 | 38 (86 %) | 199 | 6 |

Beide haben **keine robots.txt** (die Adresse liefert die Startseite).

Je eine Datei vollständig heruntergeladen:

```
MT   CT2127_2026 - Clarification Note 4.pdf        232.762 B, PDF 1.7, 2 Seiten
CY   „…… 11 ………… ……… R2.docx"                       47.401 B, Word
```

⚠ **Malta liefert eine „Clarification Note"** — das ist ein Bieterfragen-Dokument, also
genau die Gattung, die der Zähler in `build_doc_qa_stand.py` liest. Ein englischsprachiges
dazu, was die Mustererkennung einfacher macht als das portugiesische
„Resposta Erros e Omissões".

⚠ **Und Zyperns Dateiname kam zerschossen an.** Im Original steht griechischer Text; in der
`Content-Disposition`-Kopfzeile wurde daraus `------ 11 ---------- -------- R2.docx`. Das
ist dieselbe Stelle wie `Łódź` → `['d']` (Kapitel 14 der Länder-Bibel) und wie die
griechischen Kennungen `9Μ3ΘΩΞ2-8Λ9` — nur diesmal **im HTTP-Kopf statt im Inhalt**. Wer
Dateien unter ihrem gemeldeten Namen ablegt, verliert bei zwei Ländern die Bezeichnung.
**Vor dem ersten Abruf klären**, nicht danach.

## 3. Was das ändert

Vier Länder, ein Abrufer:

| | LT | IE | MT | CY | Summe |
|---|---:|---:|---:|---:|---:|
| Ausschreibungen/Monat (TED) | ~737 | ~540 | ~145 | ~104 | **~1.526** |
| belegt anonym abrufbar | ~99 % | 86 % | 100 % | 100 % | |

Das ist kein grosser Anteil am EU-Volumen — aber es ist **ein einziges Stück Arbeit**, und
drei der vier Länder waren in der Reihenfolge „nach Landesgrösse" noch weit entfernt.

**Die allgemeine Lehre steht über den Zahlen:** die Sondierung hat 30 Länderdateien und
sortiert nach Markt. Portale werden aber nicht je Land gebaut, sondern **je Hersteller**.
Dieselbe Beobachtung von der anderen Seite: LV `eis.gov.lv`, PT AnoGov und GR ΕΣΗΔΗΣ
brauchen alle drei **denselben** sitzungsführenden Abrufer (POST mit Formularzustand) — auch
das drei Länder, eine Bauart.

**Zwei Achsen also, nicht eine:**
- **je Land** — wie gross ist der Markt, welche Ebenen gibt es, wo liegen die Daten
- **je Bauart** — welcher Abrufer öffnet wie viele Länder auf einmal

Die zweite ist bisher gar nicht geführt worden. Ein Anfang wäre, die Hersteller-Merkmale
(`/epps/`, `jsessionid`+JSF, Oracle ADF `ViewState`, Jaggaer, cosinex, E-ZAK, ProeBiz,
Mercell, EU-Supply) über alle 30 Länderdateien zu zählen — **das ist noch nicht geschehen**
und wäre vermutlich der billigste noch offene Fund der ganzen Sondierung.

## 4. Was hier ausdrücklich NICHT geprüft ist

- **Die unterschwellige Ebene** in MT und CY. Irland führt sie auf derselben Plattform
  (Filter `Threshold: Below`); ob Malta und Zypern das auch tun, ist **ungeprüft**.
- **Die Fonds-Ebene** in beiden Ländern. Zypern und Malta sind Kohäsionsempfänger.
- **Die Stichprobe ist klein** (7 Vergaben je Land gegen 44 in Irland). 100 % aus sieben
  Fällen heisst „kein Gegenbeispiel gefunden", nicht „es gibt keins" — Irland zeigte seine
  14 % Anmeldepflicht erst über eine grössere Stichprobe.
