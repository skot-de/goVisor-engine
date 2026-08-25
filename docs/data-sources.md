# Datenquellen — Prüfergebnis

**Stand:** 2026-07-17. Alle Zahlen unten sind an den echten Dateien gemessen, nicht aus der Dokumentation übernommen.

Dieses Dokument korrigiert Abschnitt 2 und 4 von [`INPUT/govisor-data-engine-concept.md`](../INPUT/govisor-data-engine-concept.md) (v2.0). Das Konzept plant den CSV-Export als Primärquelle. Das trägt nicht.

## Kurzfassung

| | CSV-Subset (Konzept v2) | Monatliche XML-Pakete (jetzt) |
|---|---|---|
| Abdeckung | 2006-01-01 → **2023-12-31** | **2004-01 → laufender Monat** |
| Letzte Aktualisierung | 2024-01-25 (eingefroren) | laufend |
| Freitext-Beschreibung | **nein** | ja (99,9 % der DE-Notices) |
| Titel | nur in CAN | ja |
| Strukturierte Felder | ja, vorgeparst | ja, aber selbst zu mappen |
| Aufwand | gering | Schema-Mapper über 3 Generationen |

**Entscheidung: XML-only.** Die CSV wird nicht verwendet — weder als Quelle noch zur Validierung. Sie kann nichts, was das XML nicht auch kann, endet 2023 und würde einen zweiten Feld-Dialekt in die Pipeline holen, der dauerhaft gepflegt werden müsste. Der Abschnitt unten dokumentiert nur noch, *warum* sie ausscheidet.

## Warum die CSV ausscheidet

### 1. Kein Freitext

Der Extraction-Prompt des Konzepts (Abschnitt 5.3) füllt `{description}`. Dieses Feld existiert im CSV-Export nicht — geprüft an `export_CAN_2023.csv` (75 Spalten) und der CN-Datei (64 Spalten):

- `SHORT_DESCR` / `DESCRIPTION`: in **keiner** der beiden Dateien
- `TITLE`: nur in CAN, nicht in CN
- an Freitext existiert ausschließlich `TITLE` (CAN) und `CRIT_CRITERIA`

Ohne Freitext gibt es keine Schicht 2. Das ist der Grund für den Quellenwechsel.

### 2. Eingefroren seit Januar 2024

Zeitliche Abdeckung laut Portal-Metadaten: `2006-01-01` bis `2023-12-31`, `modified: 2024-01-25`. Das Konzept plant „TED CSV Download (2006-2025)" — die letzten 2,5 Jahre existieren dort nicht.

### 3. Felder, die im Konzept-Schema stehen, aber in CAN fehlen

`raw_notices_can` (Abschnitt 4.2) listet `duration`, `contract_start`, `contract_completion`, `b_options`. Diese Spalten gibt es nur in CN. Der Pfad „Priorität 2: Strukturiertes Feld" in `merge_duration()` greift für CAN also nie.

### 4. Füllgrade (DE, CN 2023, 95.712 Zeilen)

| Feld | EU gesamt | **DE** | Konsequenz |
|---|---|---|---|
| `FUTURE_CAN_ID` | 58,2 % | **51,9 %** | im Konzept „GOLD!" — trägt aber nur die halbe Kette. Buyer+CPV+Zeit-Matching ist Hauptpfad, nicht Fallback. |
| `CAE_NATIONALID` | 66,7 % | **3,1 %** | Entity Resolution über nationale IDs scheidet für DE aus. Nur Fuzzy-Matching auf Namen. |
| `VALUE_EURO` | 52,4 % | **18,6 %** | jede wertbasierte Auswertung läuft auf einem Fünftel der Daten. |
| `DURATION` | 94,9 % | 93,1 % | gut. |

## Die XML-Pakete

```
https://ted.europa.eu/packages/monthly/YYYY-MM
```

Verifiziert: `2004-01`, `2006-06`, `2010-06`, `2015-06`, `2020-06`, `2023-06`, `2024-06`, `2026-06` — alle HTTP 200.

Gemessen an `2023-06`:

- 212 MB gzip, 1,2 GB entpackt, **69.655 Notices**
- Scan-Durchsatz **~37.600 Dateien/s** — ein Monat in 2 s, der Country-Filter ist praktisch gratis
- Flaschenhals ist allein der Download (~55 GB für 22 Jahre, EU-weit)
- Länderverteilung: DE 19,7 %, FR 12,9 %, PL 11,3 %

### Das Paketformat wechselt — und der Fehler ist stumm

Die Monatspakete haben **zwei Layouts**:

| Layout | Aufbau |
|---|---|
| flach (neuere Monate) | `330482_2023.xml`, `327209_2023.xml`, … direkt im Paket |
| **verschachtelt** (ältere Monate) | `10/20191030_2019210.tar.gz` — ein **Tagespaket** je Publikationstag, die XML liegen darin |

Ein Leser, der nur die oberste Ebene nach `.xml` durchsucht, findet im verschachtelten Layout **nichts** — und meldet keinen Fehler, sondern einen leeren Monat. Beim ersten Vollimport gingen so **43 von 126 Monaten** verloren; das Log sagte nur `0 behalten`.

`bulk.iter_notices()` steigt in Tagespakete ab, `tests/test_bulk.py` hält beide Layouts fest.

### Abgeschnittene Downloads sehen aus wie ruhige Monate

TED kappt die Verbindung unter Dauerlast (`Connection reset by peer`). Ein abgebrochener gzip-Stream wirft beim Schreiben **nicht immer** eine Ausnahme — er endet einfach. Ohne Prüfung landet ein halber Monat als vollständiger im Bestand.

Real passiert: `2023-11` wurde mit **1.555 statt ~12.300 Notices** geschrieben. In einer Auswertung sieht das nach einem schwachen November aus, nicht nach einem Bug.

`bulk.download()` prüft deshalb Content-Length gegen die geschriebenen Bytes, liest das Archiv einmal komplett durch (`_verify`) und benennt erst dann um. Bei Abbruch: Backoff und neuer Versuch, statt TED weiter zu hämmern.

Erkennungshilfe für stille Ausfälle: Notices je Monat gegen den Jahresmedian. DE wächst stetig von ~6.000/Monat (2016) auf ~12.300 (2023) — ein Monat unter 50 % des Jahresmedians ist verdächtig.

### Speicherbedarf nach Filter (gemessen)

| | pro Monat | pro Jahr | 22 Jahre |
|---|---|---|---|
| DE roh (gefiltert, gzip) | 38 MB | ~456 MB | **~10 GB** |
| DE Index (jsonl.gz) | 2,4 MB | ~29 MB | ~0,6 GB |

Deutlich unter der Konzept-Schätzung von 20–50 GB.

## Drei Schema-Generationen

Sie koexistieren **im selben Paket**. Ein Parser, der nur `SHORT_DESCR` kennt, verliert still an beiden Enden des Archivs.

| Generation | Wurzel / Form | Freitextfeld |
|---|---|---|
| Vor-2014-Formulare | `TED_EXPORT` → `FD_CONTRACT_AWARD` | `SHORT_CONTRACT_DESCRIPTION` |
| 2014er-Formulare | `TED_EXPORT` → `F0x_2014` | `SHORT_DESCR` |
| eForms (ab 2022) | UBL `ContractAwardNotice` u. a. | `cbc:Description` |

Das ist keine reine Historie: im Juni 2023 nutzen **62 DE-Notices** noch `SHORT_CONTRACT_DESCRIPTION`, und `863-2024` liegt noch als Legacy vor, während `1465-2024` bereits eForms ist. Beide Formate laufen parallel.

## Der Freitext ist los-basiert

TED beschreibt einen Auftrag auf zwei Ebenen, und beide heißen `SHORT_DESCR`:

| Ort im XML | TED-Abschnitt | Bedeutung |
|---|---|---|
| `OBJECT_CONTRACT/SHORT_DESCR` | II.1.4 | Beschreibung der Bekanntmachung |
| `OBJECT_CONTRACT/OBJECT_DESCR/SHORT_DESCR` | II.2.4 | Beschreibung **je Los** |

In eForms dieselbe Struktur: `ProcurementProject` (Notice-Ebene) gegen `ProcurementProjectLot/ProcurementProject` (Los-Ebene).

Das ist kein Randfall. Gemessen an DE `2023-06` (13.716 Notices):

- **92,3 %** haben mehr als ein Beschreibungs-Vorkommen, bis zu 8 und mehr
- 13.716 Notices tragen **20.043 Lose**
- wer nur das erste Vorkommen nimmt, verliert **67,2 % des Freitexts** (5,3 M statt 15,0 M Zeichen)

Ein Parser, der pro Notice ein `description`-Feld annimmt, verliert also zwei Drittel des Materials, auf dem Schicht 2 arbeiten soll — lautlos, weil jede Notice ja *eine* Beschreibung hat. `Notice.lots` hält die Los-Ebene getrennt; `Notice.descriptions` liefert beides in Dokumentreihenfolge.

> Konsequenz für das Konzept: `extracted_notices` (Abschnitt 5.2) ist pro Notice modelliert. Die Extraktion muss pro Los laufen, sonst mittelt sie Lose mit unterschiedlicher Laufzeit und Technik zu einem Datensatz zusammen.

## Wie viel Inhalt steht wirklich drin?

Gemessen 2026-07-23 an **437.401 offenen Ausschreibungen** (`cn`/`pin`, eForms ab 2024):

| Beschreibungslänge | nur Notice-Ebene | Notice **+ Lose** |
|---|---|---|
| Median | 129 Zeichen | **432 Zeichen** |
| < 200 Zeichen (Zweizeiler) | 60,9 % | — |
| ≥ 1.000 Zeichen („substanziell") | 14,6 % | **32,9 %** |

**Diese Gesamtzahl mittelt zwei sehr verschiedene Quellen** — getrennt gemessen:

| Quelle | Anzahl | Median Notice | Median + Lose | ≥ 1.000 Zeichen | Ø Lose |
|---|---:|---:|---:|---:|---:|
| **TED** (oberschwellig) | 232.986 | 173 | **812** | **43,5 %** | 1,68 |
| **DÖE** (unterschwellig) | 204.415 | 102 | **204** | **20,8 %** | 1,00 |

DÖE ist rund **viermal dünner** und trägt **exakt ein Los** je Notice — der schlanke
`eforms-sdk-0.1`-Dialekt kennt keine Losstruktur. Wer die 32,9 % ohne diese Aufteilung
zitiert, verspricht für den Unterschwellenmarkt das Doppelte dessen, was dort steht.

Im Lead-Export schlägt das gedämpft durch, weil nur *offene* DÖE-Ausschreibungen Leads
werden: 3.653 von 85.947 (4,3 %), davon 23,7 % „reich" gegen 40,4 % bei TED.
DÖEs Beitrag ist zudem **stark gewerkeabhängig** — 9,7 % aller Bau-Leads (CPV 45), aber
0 % bei Finanz (66) und Nahrungsmitteln (15) und 0,1 % bei Pharma (33): solche Verträge
liegen praktisch immer über dem EU-Schwellenwert.

### `contract_nature` — 5,8 % bei DÖE, 99,9 % bei TED (gemessen 2026-08-25)

Die Vertragsart (works / supplies / services, BT-23) steht bei TED-eForms praktisch
immer, bei DÖE fast nie:

| Generation | Sätze | mit `contract_nature` |
|---|---:|---:|
| `eforms` (TED) | 454.036 | 99,9 % |
| `doe` | 391.784 | **5,8 %** — 369.239 leer |

⚠ **Das ist die QUELLE, nicht der Parser.** Der Verdacht lag nahe, denn DÖE ist eForms
(Dialekt `eforms-sdk-0.1`), und der Parser wählt `ProcurementTypeCode` über seine Position
im Baum. Nachgemessen an 400 Roh-XML je Dialekt, einmal mit der Positionsregel und einmal
über das Attribut `listName="contract-nature"`: **identisches Ergebnis** (DÖE 45/400, TED
400/400). Die übrigen 355 DÖE-Dokumente tragen das Element schlicht nicht.

Wer diesen Weg noch einmal geht, spart sich eine Falle: die Dateinamen im DÖE-ZIP tragen
ein Versionssuffix (`<uuid>-10.xml`), die `notice_id` in Silber ist die nackte UUID. Ein
Abgleich über den Dateinamen läuft leer — und wer dann eine beliebige Datei als Beispiel
nimmt, baut sich eine Hypothese, die die Messung widerlegt.

Produktfolge: die Bau/Dienstleistung/Lieferung-Unterscheidung ist für den unterschwelligen
Bestand nicht aus `contract_nature` zu haben. Sie kommt dort über CPV und über die
VOB/A-Regel (`kategorie.aus_regelwerk`).

Zwei Aussagen, die beide stimmen und leicht gegeneinander ausgespielt werden:

1. **Der Regelfall ist dünn.** Die Mehrheit der Bekanntmachungen beschreibt in zwei
   Zeilen, *wer* bieten darf — nicht *was* gekauft wird. Strukturierte Spezifikation gibt
   es nur als `ItemClassificationCode` (CPV) und `DurationMeasure`; keine Mengen, Maße
   oder technischen Vorgaben. Das Leistungsverzeichnis liegt hinter dem Portal-Link, und
   den trägt nur **24 %** der offenen Ausschreibungen (`portal_url`).
2. **Der reiche Schwanz ist groß.** Ein knappes Drittel trägt ≥ 1.000 Zeichen, die
   längste 17.672. Wer auf TED durchklickt, landet regelmäßig darin — der Median
   beschreibt den Normalfall, nicht die Erfahrung beim Stöbern.

> Konsequenz fürs Produkt: Die Beschreibung darf **nicht** das tragende Element der
> Detailseite sein. Tragend sind CPV, Leistungsort, Wert, Frist, Wettbewerb, Eignung —
> die entscheiden über *Passt das zu mir?*. Der Volltext ist Bonus, wo er existiert;
> `lead_export.has_detailed_description` (rechnet über **beide** Ebenen) sagt dem UI,
> wann sich ein ausklappbarer Volltext-Bereich lohnt. Die Los-Texte liegen in
> `gold.lead_lot` → Supabase `gov_lead_lots`.

## Nicht erfasste Felder

Bewusst offen gelassen, gemessen an DE `2023-06`:

| Feld | Umfang | Warum relevant |
|---|---|---|
| `MODIFICATIONS_CONTRACT/INFO_MODIFICATIONS` | 312 k Zeichen | F20 = Auftragsänderung. Begründung der Änderung — direktes Verlängerungs-Signal. |
| `MODIFICATIONS_CONTRACT/DESCRIPTION_PROCUREMENT` | 233 k Zeichen | Beschreibung des geänderten Auftrags. |
| `RENEWAL_DESCR`, `OPTIONS_DESCR` | pro Notice | **Verlängerungsoptionen stehen in eigenen Feldern.** Das Konzept lässt `extension_months` vom LLM aus der Beschreibung raten — das ist teils gar nicht nötig. |

Diese Felder haben andere Semantik als eine Auftragsbeschreibung und gehören nicht in `description`. Sie sind für Wechsel-Prognosen aber genau das interessante Material — offene Entscheidung, wie sie modelliert werden.

## Vollständigkeit prüfen: gegen eine unabhängige Quelle, nie gegen sich selbst

Monate untereinander zu vergleichen findet nur Ausreißer. Fehlen in *jedem* Monat 10.000 Notices, ist die Kurve glatt, plausibel und falsch. Es braucht eine externe Referenz.

### TED Search API — exakt, aber erst ab 2016-08

Kalibriert an DE `2023-06`: die API meldet **69.655** Notices für alle Länder, das Paket enthält **69.655**. Exakt.

Zwei getrennte Prüfungen je Monat:

| Prüfung | Beweist |
|---|---|
| gescannte Paketgröße == API-Gesamtzahl | der **Download** war vollständig |
| behaltene DE-Zahl == API-DE-Zahl | der **Filter** hat nichts verloren |

Abdeckung der API (unser Paket-Scan gegen ihre Gesamtzahl):

| Zeitraum | API deckt |
|---|---|
| 2016-01 … 2016-06 | **0 %** — kein Index |
| 2016-07 | 50,4 % — der Index beginnt mitten im Monat |
| ab 2016-08 | **100,0 %**, exakt |

Für 2022 ergibt der Abgleich in **allen zwölf Monaten exakt 0 Delta**. So genau kann die Prüfung sein — und so klar zeigt jede Abweichung ein echtes Problem.

### Notice-für-Notice statt Zahlenvergleich

Die API liefert per `paginationMode: ITERATION` alle Publikationsnummern eines Monats (250/Seite). Damit lässt sich jede einzelne Notice abgleichen, statt Summen zu vergleichen.

An DE `2023-06` durchgeführt: **13.720 laut API, 13.716 bei uns — 4 fehlten, 0 überzählig.** Alle vier waren eForms-Notices (z. B. `368284-2023`, eine `PriorInformationNotice`), verworfen vom damals noch kaputten eForms-Zweig. Ein Verlust von 0,03 %, den keine Statistik je gezeigt hätte.

### CSV-Gegenprobe für 2016-01 … 2016-06

Der CSV-Export wird **nicht als Datenquelle genutzt** (siehe oben), taugt aber als unabhängiger Zeuge für die Monate ohne API-Index.

Abgleich der Publikationsnummern aus `TED_NOTICE_URL` (Format `TED:NOTICE:1-2016`) gegen unser Bronze:

| | |
|---|---|
| DE-Notices in der CSV 2016 (CN+CAN, dedupliziert) | 59.530 |
| davon in unserem Bronze wiedergefunden | **59.530** |
| fehlend | **0** |

Über alle zwölf Monate, jeder einzelne Monat null Verlust.

**Grenze der Aussage:** Die CSV enthält nur CN und CAN — 59.530 der 70.150 Notices, also 85 %. Vorinformationen, Berichtigungen und Wettbewerbe deckt sie nicht ab. Für diese 15 % bleibt in 2016-01…06 als Beleg nur, dass das Paket vollständig geladen und komplett gelesen wurde.

## Die alten Formularfamilien nennen das Feld nochmal anders

Der Formularwechsel auf die 2014er-Familie ist in den Daten sichtbar und fällt exakt auf die Umsetzungsfrist der Richtlinie 2014/24/EU (18.04.2016):

| Monat (DE) | alte Formulare | 2014er | Lose |
|---|---|---|---|
| 2016-01 | 98,6 % | 1,4 % | 85 |
| 2016-04 | 95,1 % | 4,9 % | 456 |
| **2016-05** | 68,1 % | **31,9 %** | 2.626 |
| 2016-06 | 57,6 % | 42,4 % | 3.876 |
| 2023-06 | 0,7 % | 99,3 % | 20.043 |

Die alten Familien haben je ein eigenes Beschreibungsfeld — gemessen an DE `2016-01`, jeweils 100 % Deckung innerhalb der Familie:

| Formular | Feld |
|---|---|
| `F0x_2014` | `SHORT_DESCR` |
| `CONTRACT`, `CONTRACT_AWARD`, `CONTRACT_UTILITIES`, `*_DEFENCE` | `SHORT_CONTRACT_DESCRIPTION` |
| `CONTRACT_AWARD_UTILITIES` | `SHORT_DESCRIPTION` |
| `RESULT_DESIGN_CONTEST` | `DESCRIPTION` |
| `OTH_NOT` (Berichtigungen) | `CONTENTS` |
| `PRIOR_INFORMATION` | `TOTAL_QUANTITY_OR_SCOPE` |

Vor der Erweiterung hatten **760 von 4.743 DE-Notices in 2016-01 (16 %) gar keinen erkannten Freitext** — gegenüber 0,1 % in 2023-06. Die Lücke war nicht in den Daten, sondern im Parser.

**Reihenfolge ist kritisch:** `TOTAL_QUANTITY_OR_SCOPE` kommt auch in `CONTRACT` vor (81 %), dort aber als Zusatzfeld *neben* der Beschreibung. Es darf nur als letzte Rückfallebene greifen, sonst überschreibt es auf dem häufigsten Formular überhaupt die richtige Antwort. `tests/test_schema.py` sichert das ab.

## Zwei Fallstricke

**Sprachfassungen.** Die Bulk-XML enthält meist nur `CATEGORY="ORIGINAL"`, aber nicht immer: in `2023-06` haben 587 Dateien zwei Formularsektionen, 10 haben drei und **303 haben 24** (alle Amtssprachen). Wer die erste Sektion nimmt, bekommt dort zufällige Sprache. `parse()` selektiert deshalb auf `CATEGORY="ORIGINAL"`.

> Nicht verwechseln mit dem Web-Endpoint `ted.europa.eu/en/notice/<id>/xml`: der liefert *immer* alle Sprachen (`MUL`). Ein früher Prototyp zog darüber bulgarische Titel für deutsche Notices.

**Ländercodes.** Legacy nutzt alpha-2 (`DE`), eForms alpha-3 (`DEU`). Beide Kodierungen laufen über `govisor/countries.py`. Zusätzlich gilt: TED schreibt Griechenland `EL` (nicht `GR`), und das UK erscheint über die Jahre als `UK` und `GB`.

Ländercodes stehen im XML mehrfach — Käufer-Adresse *und* Erfüllungsort. `probe_countries()` ist bewusst überinklusiv (billiger Vorfilter); erst `parse()` entscheidet über die Käufer-Nationalität.

## Was noch offen ist

- **`FUTURE_CAN_ID` im XML:** Die CSV hatte das Feld bereits aufgelöst (DE 51,9 %). Da wir sie nicht nutzen, müssen wir die CN→CAN-Verknüpfung selbst aus dem XML ziehen. Ob und wo sie dort steht, ist ungeprüft — davon hängt Methode 1 des Chain Building ab.
- **eForms-Anteil über die Zeit:** in `2023-06` erst 1 % (703 von 69.655). Ab wann kippt es?
- **Notice-Typen:** Die Pakete enthalten alles (CN, CAN, Korrekturen F14, Änderungen F20). Filterung nach Typ ist noch nicht implementiert.
