# goVisor Data Engine — Konzept v3

**Stand:** 2026-07-17. Ersetzt [`INPUT/govisor-data-engine-concept.md`](../INPUT/govisor-data-engine-concept.md) (v2.0, Januar 2026).
Jede Zahl hier ist an echten Daten gemessen. Messgrundlage steht in [`data-sources.md`](data-sources.md).

## 1. Ziel

Eine Plattform, die Zugang zu Wahrscheinlichkeitsaussagen über kommende Ausschreibungen verkauft:

> „Mit 90 % Wahrscheinlichkeit schreibt Behörde X im Juli 2026 1.000 SAP-Lizenzen aus. In den 5 vorherigen Runden gab es 3 verschiedene Lieferanten."

Das Produkt existiert bereits manuell als `INPUT/Leads/goVisor_X-RAY.xlsx` (78 Aufträge, Editionen PING/SCAN/FOCUS/X-RAY). Die Engine soll es automatisieren und skalieren.

## 2. Was sich gegenüber v2 ändert

| Thema | v2 | v3 | Grund |
|---|---|---|---|
| Quelle | TED CSV | **TED XML-Bulk** | CSV hat keinen Freitext und endet 2023-12-31 |
| Import | ~80 Felder handverlesen | **alle ~3.600 Felder verlustfrei** | Handpflege über 3 Schema-Generationen ist nicht wartbar |
| Granularität | pro Notice | **pro Los** | 13.716 Notices tragen 20.043 Lose; das Produkt ist los-granular |
| Branche | CPV direkt | **redaktionelle Schicht über CPV** | Branche ist Geschäftsentscheidung, kein Datum |
| LLM | Extraktion aller Felder | **gezielt auf Verlängerungslogik** | der Rest steht strukturiert da — die Verlängerung nicht |

## 3. Der zentrale Befund: Laufzeit lebt in zwei Dokumenten

Gemessen an den **78 echten X-RAY-Aufträgen**:

- X-RAY besteht zu 99 % aus **Vergabebekanntmachungen (F03/CAN)**.
- **0 von 78** enthalten ein Laufzeitfeld. CANs sagen *wer* und *wie viel*, nicht *wie lange*.
- **75 von 78 (96 %)** verweisen per `REF_NOTICE` auf ihre **Auftragsbekanntmachung (F02/CN)**, meist aus dem Vorjahr.
- Alle 75 Verweise ließen sich auflösen — **kein toter Link**.
- In den CNs: **98,7 % haben `DURATION` oder `DATE_END`**. `DURATION` ist immer `TYPE="MONTH"`.

**Ohne den Join CAN→CN gibt es keine Laufzeit und damit kein Produkt.** Das ist die Kernmechanik der Engine, nicht ein Detail der Normalisierung.

### Und die Laufzeit allein reicht nicht

Rekonstruktionsversuch der X-RAY-Spalte „Fällig*" aus Vergabedatum + `DURATION`: **31 % Treffer**. Die Abweichungen sind systematisch:

| Auftrag | `DURATION` | `RENEWAL_DESCR` (Freitext) | X-RAY |
|---|---|---|---|
| 114908-2022 | 24 | „verlängert sich **zweimalig um jeweils ein weiteres Jahr** … maximale Laufzeit vier Jahre" | 2026 Q1 = 48 M |
| 127876-2022 | 12 | „**dreimalige** Verlängerungsoption um jeweils 12 Monate … max. **48 Monate**" | 2026 Q1 = 48 M |
| 157320-2022 | 24 | „verlängert sich maximal einmal um **zwei weitere Jahre** … maximale Laufzeit von **vier Jahren**" | 2026 Q1 = 48 M |

Das strukturierte Feld nennt die **Grundlaufzeit**. Die **Maximallaufzeit** — die für die Prognose zählt — steht nur im Freitext, in `RENEWAL_DESCR` (62,7 % der CNs) und `OPTIONS_DESCR`.

**Das ist der Job des LLM.** Nicht „Freitext auslesen" im Allgemeinen, sondern eine scharf umrissene Aufgabe: aus `RENEWAL_DESCR` + `OPTIONS_DESCR` + `DURATION` die maximale Vertragslaufzeit in Monaten ableiten.

## 4. X-RAY ist kein Validierungsset

**Bestätigt durch Sven (2026-07-17): Die Spalte „Fällig*" wurde manuell als „Vergabedatum + 48 Monate" gesetzt.** Sie ist eine Faustregel, keine Einzelfallprüfung.

Die Regel ist nicht willkürlich — Art. 33 RL 2014/24/EU deckelt Rahmenvereinbarungen auf vier Jahre, 48 Monate sind der Normalfall. Aber sie ist ungeprüft, und ein Abgleich der Engine gegen X-RAY würde nur messen, ob die Engine die Faustregel reproduziert.

### Wie oft ist die Faustregel falsch?

Gemessen an den 75 X-RAY-Aufträgen mit aufgelöster Bekanntmachung, **nur anhand strukturierter Felder, ohne LLM**:

| Befund | Anteil |
|---|---|
| **Nachweislich falsch** (Laufzeit steht da, ist nicht ~48 M, keine Verlängerung vorgesehen) | **10/75 (13 %)** |
| Nachweislich richtig (~48 M, keine Verlängerung) | 17/75 (23 %) |
| Unentscheidbar ohne Freitext (`RENEWAL` gesetzt → Maximum steht nur im Text) | 48/75 (64 %) |

Die zehn Fehler, nachprüfbar:

| Auftrag | Reale Laufzeit | Fehler | Richtung |
|---|---|---|---|
| `453244-2022` RV Apple Komponenten | 5 M | 43 M | Lead war tot — prüfen, ob Datenfehler |
| `464240-2022` RV Unified Communications | 24 M | 24 M | zu spät |
| `656949-2022` RV Anwendungsentwicklung | 72 M | 24 M | zu früh |
| `269425-2022`, `297553-2022`, `67023-2022`, `727828-2022`, `730057-2022` | je 60 M | 12 M | zu früh |
| `136007-2022`, `454432-2022` | 41–53 M | 5–7 M | gemischt |

3 Fälle laufen **kürzer** als angenommen (Ausschreibung längst gelaufen, Lead tot), 7 laufen **länger** (Kunde ruft Jahre zu früh an).

### Konsequenzen

1. **Kein Abgleich gegen X-RAY.** Als Zielliste bleibt es wertvoll — Auftraggeber, Dienstleister, Volumen, Bieterzahl stammen aus den Daten und stimmen. Nur die Prognosespalte ist Annahme.
2. **Erster belegbarer Mehrwert der Engine: 13 % korrigierte Termine, ohne LLM.** Nicht „mehr Leads", sondern „die Termine stimmen".
3. **Das LLM entscheidet die 64 %.** Seine Rolle ist damit messbar begründet, nicht Nice-to-have.
4. **Testset für den LLM-Prompt: die 23 %**, wo die Antwort strukturiert bekannt ist. Dort muss das LLM dasselbe herausbekommen.
5. **Backtesting wird Pflicht.** Der einzige verbliebene Weg zu einer ehrlichen Prozentzahl: Verträge aus 2016–2019 nehmen, Nachfolger prognostizieren, in den Daten nachsehen, ob er kam — Datum, Gewinner, Volumen. Ohne das käme die „90 %" aus dem Nichts.

Kalibrierungs-Bonus: `ESTIMATED_TIMING` — der Auftraggeber nennt selbst den nächsten Termin („2. Quartal 2027"). Nur 0,8 % der Notices, aber über 22 Jahre DE ~30.000 Fälle, in denen die Antwort in den Daten steht.

## 4a. Prototyp der Extraktion — Ergebnis

Durchgeführt am 2026-07-17 an den 75 X-RAY-Bekanntmachungen. Claude las die Verlängerungs-Freitexte und bestimmte die Maximallaufzeit; Ergebnis in `OUTPUT/goVisor_X-RAY_korrigiert.xlsx`, jede Zeile mit Belegzitat.

**51 der 75 Fälle tragen einen Verlängerungstext.** Davon:

| | Anzahl | Anteil |
|---|---|---|
| „+48 Monate" bestätigt | 31 | 61 % |
| **„+48 Monate" falsch** | **20** | **39 %** |
| — davon X-RAY zu **früh** (Kunde ruft zu zeitig an) | 15 | |
| — davon X-RAY zu **spät** (Lead ist weg) | 5 | |

Größte Abweichungen: `339313-2022` (+6,5 Jahre), `506477-2022` (+4 J), `174276-2022` (+3,25 J), `193879-2022` (+3 J, EZB).

Die fünf „zu spät"-Fälle sind die teuren: `633055-2022` und `693535-2022` waren 2026 Q2 fällig, X-RAY sagt 2026 Q4 — wer danach arbeitet, ruft nach der Ausschreibung an.

### Was der Prompt können muss (aus den Daten gelernt)

1. **`DURATION` ist mal Grundlaufzeit, mal Maximum.** `325056-2022`: DURATION=48, Text sagt „2 × 12 Monate" obendrauf → 72. `359349-2022`: DURATION=48, Text sagt „nach 36 Monaten Grundlaufzeit ... bis zu 12 Monate" → 48, die Option steckt schon drin. Das Feld allein ist nicht interpretierbar; der Text entscheidet.
2. **`OPTIONS_DESCR` ist meist keine Laufzeitoption.** Bei `224378`, `504775`, `649346` steht dort Textbaustein-Prosa über Auftragsänderungen. Wer daraus eine Verlängerung liest, verlängert Verträge, die nicht verlängerbar sind.
3. **Absolute Enddaten schlagen Arithmetik.** „Der Rahmenvertrag endet somit spätestens am 31.12.2028" (`687981`) ist präziser als jede Rechnung.
4. **Der Ankerpunkt wechselt.** „48 Monate **nach Zuschlagserteilung**" (`407126`, `88013`, `569763`) rechnet ab Vergabedatum, nicht ab `DATE_END`.
5. **Nicht alles ist deutsch.** Die EZB schreibt englisch: „Up to 3 renewals of 12 month duration each".
6. **Ausgabe muss das Zitat enthalten.** Ohne Beleg ist eine Prognose nicht prüfbar — und das Produkt verkauft Prüfbarkeit.

Testset für den Produktions-Prompt: die 17 Fälle mit `NO_RENEWAL` und bekannter Laufzeit (Abschnitt 4) — dort ist die Antwort strukturiert bekannt und das LLM muss sie treffen.

## 4b. Herkunft und Quellenlinks

Anforderung (Sven, 2026-07-17): Der TED-Link gehört in die Datenbank. Wenn das Produkt sagt „in den letzten 3 Ausschreibungen war das so", müssen die Belege danebenliegen — der Leser soll sich selbst durchklicken können.

Deckung, gemessen an DE `2023-06`:

| Feld | Deckung | Inhalt |
|---|---|---|
| `publication_number` | 100 % | `330482-2023` |
| `oj_ref` | 100 % | `2023/S 105-330482` — die formale Amtsblatt-Zitation |
| `publication_date` | 100 % | aus `REF_OJS/DATE_PUB` |
| `ted_url` | 100 % | kanonische Detailseite |
| `ref_ted_url` | 52,7 % | Link zur verwiesenen Notice (bei Vergaben/F03: 96 %) |

### Warum nicht die URL nehmen, die TED liefert

`URI_DOC` enthält `https://ted.europa.eu/udl?uri=TED:NOTICE:330482-2023:TEXT:DE:HTML`. Der Link funktioniert — aber nur per **HTTP 301** auf `https://ted.europa.eu/de/notice/-/detail/330482-2023`. Wir speichern das Ziel, nicht die Weiterleitung: eine Redirect-Regel kann TED abschalten, und dann wären sämtliche Belege im Bestand tot.

Zusätzlich liegt `oj_ref` daneben. Die Amtsblatt-Zitation ist keine URL, sondern eine Fundstelle — sie bricht nie, auch wenn TED die Website umbaut.

### Fallstrick: zwei OJ-Nummern pro Dokument

`NO_DOC_OJS` kommt zweimal vor:

| Pfad | Bedeutung | Deckung |
|---|---|---|
| `NOTICE_DATA/NO_DOC_OJS` | **eigene** Nummer | 100 % |
| `NOTICE_DATA/REF_NOTICE/NO_DOC_OJS` | **verwiesene** Notice | 58 % |

Die Dokumentreihenfolge stellt die eigene zufällig nach vorn, aber darauf zu bauen ist fragil. `_provenance()` selektiert auf den Elternknoten; `tests/test_schema.py` hält es fest. Ein Verwechseln würde jede Vergabe auf sich selbst verlinken — und die Ketten stillschweigend zerstören.

## 5. Weitere nutzbare Signale

Neben Laufzeit und Verlängerung (gemessen an DE `2023-06`):

| Feld | Deckung | Wert für das Produkt |
|---|---|---|
| `REF_NOTICE` | 96 % (CAN→CN) | verbindet Vergabe mit Bekanntmachung — die Kernmechanik |
| `RENEWAL` / `NO_RENEWAL` | 62,7 % / 38,7 % | ist Verlängerung überhaupt vorgesehen? |
| `NUMBER_OFFERS` | — | Bieterzahl = Wettbewerbsintensität = Verdrängbarkeit |
| `RECURRENT_PROCUREMENT` | 1,3 % ja / 38,9 % nein | Auftraggeber sagt selbst, ob wiederkehrend |
| `ESTIMATED_TIMING` | 0,8 % | Auftraggeber nennt den nächsten Termin |
| F20-Änderungen | 1.406/Monat | **tatsächlich gezogene** Verlängerungen, nicht nur geplante |
| `NUMBER_POSSIBLE_RENEWALS` | — | Anzahl Verlängerungen, strukturiert |

F20 verdient Aufmerksamkeit: Eine Änderungsbekanntmachung ist der Beweis, dass eine Option *gezogen* wurde. Damit lässt sich messen, wie oft Optionen real genutzt werden — die empirische Basis für „mit 90 % Wahrscheinlichkeit".

## 6. Architektur

```
Bronze   Original-XML, gefiltert nach Land          38 MB/Monat DE · unveränderlich
   │
Silber   verlustfrei geflacht, ~3.600 Felder        Parquet, partitioniert land/jahr
   │
Gold     Sternschema, normalisiert                  Serving-DB
   │
Produkt  Wahrscheinlichkeiten
```

Gold:

```
dim_branche      branche_id, name, version      ← redaktionell, versioniert
dim_cpv          cpv_code, division, branche_id
dim_buyer        + name_variants                ← Entity Resolution lebt hier
dim_supplier     + name_variants
fact_los         los_id, notice_id, ausschreibung_id, buyer, supplier,
                 wert, laufzeit_basis, laufzeit_max, laufzeit_quelle, ende_prognose
bridge_los_cpv   los_id, cpv_code, is_main      ← das n:m lebt hier
fact_notice      notice_id, ausschreibung_id, form, art
ref_notice       notice_id → notice_id          ← aus REF_NOTICE
```

Navigation Land → Branche → CPV → Ausschreibung ist eine Abfrage darüber, keine Ordnerstruktur: 10,5 % der Notices haben mehrere CPV-Divisionen, 13,5 % der Lose weichen von ihrer Notice ab.

`laufzeit_quelle` ist Pflicht: `structured` | `llm_renewal_descr` | `legal_cap_48m` | `unknown`. Bei einem Produkt, das Prozentzahlen verkauft, muss jede Zahl sagen können, woher sie kommt.

## 7. Phasen

**Phase 1 — statisch, Basis erarbeiten**
1. Vollimport DE, alle Notice-Typen, statisch heruntergeladen
2. Silber: verlustfreies Flatten, alle Felder
3. `ref_notice`-Graph, CAN→CN-Join
4. Entity Resolution Käufer/Lieferant ← **das Risiko, siehe unten**
5. LLM auf `RENEWAL_DESCR` → Maximallaufzeit
6. Backtest gegen 2015–2019

**Phase 2 — laufend**
Monatlicher Auto-Ingest jedes abgeschlossenen Monats, gleiche Pipeline.

## 8. Das größte Risiko: Entity Resolution

`NATIONALID` ist bei DE zu **3,9 %** gefüllt (gemessen an DE `2023-06`, deckt sich mit dem CSV-Befund von 3,1 %). Ohne stabile ID muss „Bundesministerium des Innern" über 22 Jahre Schreibweisen, Umbenennungen und Reformen hinweg als dieselbe Entität erkannt werden.

Ohne funktionierende Entity Resolution gibt es kein „in den 5 vorherigen Runden". Das ist nicht ein Schritt der Normalisierung, das ist das Produkt.

### Das Behördenregister taugt nicht als Basis

`INPUT/behoerdeneinrichtungen-data.pdf` ist das Glossar des Sprachendienstes des Auswärtigen Amts, Stand 11.06.2015. Ausgewertet: **1.165 Einträge, 498 mit Akronym, 465 mit übergeordneter Behörde, 32 mit „ehemals"**.

Test gegen die 44 eindeutigen X-RAY-Auftraggeber: **9 Treffer (20 %), davon 1 Fehlalarm** — „Die Autobahn GmbH des Bundes" wurde über das Akronym „DIE" auf „Deutsches Institut für Entwicklungspolitik" abgebildet.

Drei Gründe, warum es nicht trägt:

1. **11 Jahre veraltet.** `BMWi` steht drin samt „ehemals BMWT". `BMWK` fehlt (Umbenennung 12/2021), „Die Autobahn GmbH" fehlt (gegründet 2018). Die Umbenennungskette bricht 2015 ab.
2. **Falscher Zielmarkt.** Das Register listet Ministerien und Bundesbehörden. Die IT-Einkäufer sind ITDZ Berlin, IT.NRW, GKD Recklinghausen, HZD, Charité, Universitäten, BLKA — strukturell nicht enthalten.
3. **Akronym-Matching ohne Absicherung produziert selbstbewussten Unsinn** (siehe „DIE").

**Verdikt:** als Anreicherung für Bundesbehörden brauchbar (Akronyme, Hierarchie, 32 Umbenennungen), als Basis ungeeignet. Ein aktuelleres Register mit IDs bleibt wünschenswert.

### Die Basis liefert TED selbst

Gemessen an DE `2023-06` (13.634 Notices mit Auftraggeber-Block):

| Merkmal | Deckung |
|---|---|
| `OFFICIALNAME` | 100 % |
| `E_MAIL` | 100 % |
| `TOWN` | 100 % |
| `NUTS` | 100 % |
| `URL_GENERAL` | 100 % |
| `POSTAL_CODE` | 98,6 % |
| `NATIONALID` | **3,9 %** |

4.053 eindeutige Namen, 2.578 eindeutige E-Mail-Domains. Adresse, Ort, NUTS und Domain sind ungleich stärkere Signale als ein externes Glossar — und sie sind lückenlos da.

### Aber: Domain ≠ Identität

**638 Domains tragen mehr als einen Auftraggebernamen** — und das sind meist keine Schreibvarianten, sondern echte verschiedene Behörden:

| Domain | Namen | Was es wirklich ist |
|---|---|---|
| `@kubus-mv.de` | 43 | Einkaufsdienstleister für viele Kommunen |
| `@gmsh.de` | 36 | Gebäudemanagement Schleswig-Holstein als Vergabestelle |
| `@deutschebahn.com` | 30 | echte Konzerntöchter (DB Netz AG, DB Energie GmbH …) |
| `@vbv.bwl.de` | 26 | zentrale Vergabestelle Baden-Württemberg |

### Auftraggeber ≠ Vergabestelle

Deutsche Vergabe läuft massiv über Vertreter. Gemessen:

- **10,0 %** der DE-Notices tragen das strukturierte Flag `ON_BEHALF` / `CENTRAL_PURCHASING`
- **4,8 %** tragen den Hinweis im Namen („vertreten durch", „im Auftrag von", „c/o", „für die")

Beispiele: „Stadt Nürnberg vertreten durch WBG KOMMUNAL GmbH", „Landkreis Harburg – Zentrale Vergabestelle für die Samtgemeinde Jesteburg", „Bundesrepublik Deutschland, vertreten durch das Beschaffungsamt des BMI".

**Das ist produktkritisch.** Wer „KUBUS Kommunalberatung" als Käufer ausweist, nennt dem Kunden den Dienstleister statt des Entscheiders. Der Lead geht an die falsche Adresse.

X-RAY macht die Unterscheidung bereits von Hand — Spalte „Auftraggeber" enthält „Beschaffungsamt des BMI (für BMVI)". Das Datenmodell muss sie explizit abbilden:

```
fact_los.auftraggeber_id   → wer beschafft (Prinzipal, der Entscheider)
fact_los.vergabestelle_id  → wer das Verfahren führt (Agent)
```

### Die Lieferantenseite ist schlechter ausgestattet

Gemessen an DE `2023-06`, 12.480 Gewinner-Blöcke (`CONTRACTOR`):

| Merkmal | Auftraggeber | **Lieferant** |
|---|---|---|
| `OFFICIALNAME`, `TOWN`, `NUTS` | 100 % | 100 % |
| `POSTAL_CODE` | 98,6 % | 71,6 % |
| `E_MAIL` | 100 % | **27,6 %** |
| `URL` | 100 % | 7,4 % |
| `NATIONALID` | 3,9 % | **0,8 %** |
| `SME`-Flag | — | 49,7 % |

5.780 eindeutige Lieferantennamen pro Monat. Das stärkste Blocking-Signal der Auftraggeberseite — die E-Mail-Domain — fehlt bei Lieferanten in drei von vier Fällen. Übrig bleiben Name, Ort, NUTS.

### Das Handelsregister löst die Lieferantenseite größtenteils

`C10_ipv4analyse/de_companies_ocdata.jsonl.bz2` (aus einem Nachbarprojekt) enthält **5.305.727 deutsche Firmen** aus dem Handelsregister: Name, HRB-Nummer, Sitz, Adresse, Geschäftsführer. Stand ca. 2018.

Abgleich gegen die 5.463 normalisierten TED-Lieferanten aus DE `2023-06`, **exakter Namensabgleich ohne Fuzzy-Matching**:

- **2.934 von 5.463 (53,7 %)** eindeutige Namen aufgelöst
- **7.397 von 12.480 Vergaben (59,3 %)** gewichtet nach Vergabezahl
- Ergebnis: stabile HRB-Nummer als ID — genau das, was TED mit 0,8 % `NATIONALID` nicht liefert

Die Fehlschläge sind systematisch und größtenteils behebbar:

| Typ | Beispiel | Lösung |
|---|---|---|
| Rechtsform ausgeschrieben | `Ed. Züblin AG` vs. „Aktiengesellschaft" im Register | Normalisierer erweitern |
| **Tippfehler in TED** | `LEONARD WEISS GmbH & Co.KG` (34×) vs. `Leonhard Weiss GmbH & Co. KG` (103×) — dieselbe Firma | Fuzzy-Matching |
| Bietergemeinschaft | `ARGE Hentschke Bau/Amand/Gleisbau Bautzen, c/o Hentschke Bau GmbH` | zerlegen in Mitglieder, `B_AWARDED_TO_A_GROUP` nutzen |
| Natürliche Person | `Taxi Arians`, `Paul Skidmore`, `Sarah Keenan` | nicht auflösbar — als Person markieren |
| Verein | `Bildungswerk der Hessischen Wirtschaft e.V.` | Vereinsregister, andere Quelle |

`Leonhard Weiss` ist das Lehrstück: ein Tippfehler macht aus einem Anbieter zwei. Bei „3 verschiedene Lieferanten" zählt das direkt falsch.

### Quellenlage

| Quelle | Deckung | Verdikt |
|---|---|---|
| **Handelsregister-Extrakt** (5,3 M Firmen, ~2018) | 59,3 % der Vergaben, gewichtet | **Basis für Lieferanten.** Liefert stabile HRB-ID. |
| **TED selbst** (E-Mail, NUTS, PLZ, URL) | ~100 % auf Auftraggeberseite | **Basis für Auftraggeber.** |
| Behörden-Glossar AA (2015) | 20 % der X-RAY-Auftraggeber, 1 Fehlalarm | Anreicherung: Akronyme, Hierarchie, 32 Umbenennungen |
| Wikipedia „Bundesbehörde (Deutschland)" | ~150 Behörden, nach Ebene gegliedert, mit Abschnitt „Ehemalige Bundesbehörden" samt Nachfolgern | Anreicherung: aktueller als das Glossar, gut für Umbenennungsketten. Deckt aber nur die Bundesspitze — die IT-Einkäufer (ITDZ, IT.NRW, GKD, Unikliniken) sind Länder- und Kommunalebene. |

**Das Glossar ist ein Output, kein Input.** Externe Quellen liefern Startpunkte und Prüfsteine; die eigentliche Arbeit ist, aus 22 Jahren TED-Daten selbst eine kanonische Entitätenliste zu erzeugen — für Behörden *und* Firmen. Es muss versioniert sein, aus demselben Grund wie die Branchen-Zuordnung.

### Prototyp Lieferanten-Auflösung — Ergebnis (2026-07-17)

Gemessen an DE `2023-06` gegen das Handelsregister-Extrakt. `govisor/entities.py`, Tests in `tests/test_entities.py`.

**Erst klassifizieren, dann auflösen.** Nicht jeder Lieferant ist eine Firma:

| Art | Namen | Vergaben |
|---|---|---|
| Firma | 89,5 % | 11.180 |
| Person | 5,5 % | 504 |
| Verein | 3,4 % | 411 |
| Bietergemeinschaft | 1,4 % | 376 |
| Behörde | 0,2 % | 9 |

Personen und Bietergemeinschaften als „nicht gefunden" zu zählen verschleiert, dass sie in keinem Firmenregister stehen *können*.

**Auflösungsquote der Firmen:**

| Stufe | Namen | Anteil |
|---|---|---|
| exakt über normalisierten Namen | 2.981 | 60,0 % |
| + Fuzzy ≥ 0,90 | 159 | 3,2 % |
| **= aufgelöst** | **3.140** | **63,2 %** |

Gewichtet nach Vergaben: **70,6 % der Firmen-Vergaben** aufgelöst.

### Fuzzy-Matching ist gefährlicher als es aussieht

Die 159 Fuzzy-Treffer gegen die PLZ geprüft:

| | Anteil |
|---|---|
| PLZ bestätigt | 19,5 % |
| **PLZ widerspricht** | **17,0 %** |
| PLZ unbekannt | 63,5 % |

Beispiele für das, was Fuzzy verschmolzen hätte:

| Ähnlichkeit | TED | Handelsregister | |
|---|---|---|---|
| 0,952 | `Schreinerei Deininger` (73491) | `Schreinerei Neininger GmbH` (78052) | ein Buchstabe, andere Stadt |
| 0,955 | `BM Baulogistik + Service` | `BS Baulogistik & Service` | BM ≠ BS |
| 0,923 | `QS Trockenbau GmbH` | `AS - Trockenbau GmbH` | QS ≠ AS |

Kurze, unterscheidende Präfixe sind genau das, was Firmen trennt — Edit-Distanz behandelt sie als Rauschen. Derselbe Fehlertyp wie die „DIE"-Kollision beim Behördenregister.

**Netto ist Fuzzy ohne Bestätigung ein Verlustgeschäft:** 3,2 % Gewinn gegen mindestens 17 % Falschverknüpfungen. Nur PLZ-bestätigte Treffer übernehmen.

### Woran die restlichen 30 % scheitern

Die größten offenen Fälle nennen die Ursachen:

| Fall | Problem |
|---|---|
| `Wayss & Freytag Ingenierbau AG` | Tippfehler in TED („Ingenieurbau") |
| `LEONARD WEISS GmbH & Co.KG` (34×) | Tippfehler („Leonhard") — dieselbe Firma erscheint zweimal |
| `Abacus Medicine A/S`, `... Ltd` | ausländische Rechtsform, nicht im deutschen HR |
| `Strabag Rail GmbH, Bereich Ost` | Abteilungszusatz im Namen |
| `Amand Bau GmbH` / `Amand Bau GmbH & Co KG` | Konzernvarianten |
| `Taxi Arians` | Kleingewerbe, nicht eintragungspflichtig |

Dazu: **Das Register ist von 2018, die Daten von 2023.** Jede Firma, die seither gegründet wurde, fehlt zwangsläufig. Ein aktuelleres Extrakt dürfte der größte Einzelhebel sein.

Konzentration: Die Top 100 Namen decken 26,9 % der Vergaben, die Top 1000 nur 57,8 % — der Schwanz ist lang. Die größten **383** offenen Namen decken die Hälfte der offenen Vergaben; Handarbeit lohnt dort, aber löst es nicht allein.

### Vorgehen

1. **Auftraggeber:** Blocking über NUTS + PLZ + E-Mail-Domain (alle ~100 % gedeckt), dann Namensähnlichkeit innerhalb der Blöcke
2. **Lieferanten:** klassifizieren, dann Handelsregister-Join über normalisierten Namen. Fuzzy **nur** mit PLZ-Bestätigung
3. **Prinzipal/Agent-Trennung:** Flag `ON_BEHALF` (10 %) + Namensmuster (4,8 %) + LLM für die Restfälle
4. **Bietergemeinschaften** zerlegen — `B_AWARDED_TO_A_GROUP` als Einstieg
5. Externe Register als Anreicherung, nicht als Basis
6. Manuelle Prüfung der größten Entitäten — das Volumen konzentriert sich auf wenige

## 9. Entschieden

- **Silber-Technologie:** Bronze + Silber lokal auf DuckDB/Parquet, nur Gold in Supabase. (Sven, 2026-07-17)
- **Scope:** alle DE importieren, IT nur als Sicht darüber.
- **Import-Staffelung:** Stufe 1 = 2016–2026 (2014er-Formulare + eForms, Parser existiert), Stufe 2 = 2004–2015 (alte Formularfamilien, eigener Mapper). Download einmalig für alles, Verarbeitung gestaffelt.

## 10. Ansprechpartner und Kontaktdaten

Anforderung (Sven, 2026-07-17): Genannte Ansprechpartner zwingend aufnehmen. X-RAY führt sie bereits manuell („Kontakt Mail (Vergabe)", „Decision Maker / Ansprechpartner").

Gemessen an DE `2023-06`:

| Feld | Deckung |
|---|---|
| `E_MAIL` | 100 % |
| `PHONE` | 66,1 % |
| `CONTACT_POINT` | 54,2 % |
| — davon nach Person aussehend | **13,5 %** |

Kontaktblöcke existieren mehrfach: `ADDRESS_CONTRACTING_BODY` (14.032), `ADDRESS_CONTRACTOR` (12.480), `ADDRESS_REVIEW_BODY` (12.789).

Die meisten `CONTACT_POINT`-Werte sind Organisationseinheiten („Zentrale Vergabestelle"). Benannte Personen („Kuhn, Kristoffer") sind mit 13,5 % die Minderheit — und die einzige heikle Gruppe.

### Trennung im Modell

```
fact_los.kontakt_org   → Funktionspostfach, Vergabestelle   (~100 %, nicht personenbezogen)
dim_person             → benannte Personen + Herkunft + Zeitstempel   (13,5 %)
```

Gründe:

1. **DSGVO.** Benannte Ansprechpartner sind personenbezogene Daten natürlicher Personen; öffentliche Zugänglichkeit ersetzt keine Rechtsgrundlage. Für B2B-Leadgenerierung ist Art. 6 Abs. 1 f (berechtigtes Interesse) der übliche Weg, Art. 14 verlangt Information der Betroffenen bei Nicht-Direkterhebung, dazu Auskunfts- und Löschansprüche; bei Kaltakquise zusätzlich UWG § 7. **Anwaltlich klären, bevor die Plattform live geht.** Die getrennte Tabelle macht ein Löschverlangen zu einer Zeilenoperation statt zu einer Migration.
2. **Funktionspostfächer decken den Anwendungsfall ohnehin.** 100 % gegen 13,5 % — und sie sind nicht personenbezogen.
3. **Zeitstempel ist fachlich nötig.** Ein Ansprechpartner von 2018 ist 2026 vermutlich nicht mehr im Amt. Ein Kontakt ohne Datum ist ein Lead ins Leere.

## 11. Offene Punkte

- Aktuelleres Behördenregister mit IDs — Sven sucht parallel. Das 2015er-Glossar reicht nur zur Anreicherung.
- `453244-2022`: 5 Monate Laufzeit für einen Rahmenvertrag — echt oder Datenfehler? Beispielfall für die Plausibilitätsprüfung.
- Wie wird die Prinzipal/Agent-Trennung in der Oberfläche dargestellt? Der Kunde will den Entscheider sehen, nicht die Vergabestelle.
