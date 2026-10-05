# 13 · Währung und Werte — der teuerste blinde Fleck

> Gehört zu Tor 4 und 5. **Zuerst lesen, wenn das neue Land nicht in Euro rechnet.**
> Dieses Kapitel entstand am 2026-08-23 beim Durchspielen eines neuen Landes: es fehlte,
> und die Schweiz zeigte monatelang, was das kostet.
> **Am 2026-09-15 wurde die Lücke geschlossen** — der untere Teil des Kapitels beschreibt
> die Mechanik, der obere bleibt als Lehrstück stehen.

## Der Befund, der das Kapitel ausgelöst hat

```
value_eur gefüllt:    DE 91 %    AT 98 %    CH  1 %
```

**77 von 8.301** Schweizer Leads trugen einen verwertbaren Wert (gemessen 2026-08-23).
49.368 Schweizer Bekanntmachungen trugen das Qualitäts-Flag `waehrung_fremd`.

Der Grund war keine schlechte Quelle — simap liefert Werte. Der Grund war eine einzige
Zeile in `gold.build_quality`:

```sql
CASE WHEN final_value >= 100 AND final_value <= 1e9
          AND (value_currency = 'EUR' OR value_currency IS NULL)   -- ⚠ hier
     THEN final_value END AS final_value_clean
```

**Sie war als Schutz gedacht und wirkte als Filter.** Die Absicht — keine Fremdwährung
darf stillschweigend als Euro gelten — ist richtig und gilt weiter. Aber „nicht als Euro
zählen" und „ganz wegwerfen" sind zwei verschiedene Dinge, und zwischen den beiden lagen
50.339 Schweizer Werte.

**Das ist die Fehlerform, auf die zu achten ist:** eine Sperre, die tut, was dasteht, und
nicht, was gemeint war. Sie löst keinen Alarm aus, weil sie funktioniert.

## Was ein Nicht-Euro-Land dadurch verliert

Jede dieser Kennzahlen hängt am Wert:

| Betroffen | Folge |
|-----------|-------|
| `value_band_effektiv` / Gebühren-Band | Preisstufe fällt auf den Default zurück |
| `value_anchor` | Billing-Plausibilität ohne Anker |
| `market_opportunity` (Wert-Achse) | Segmente ohne Volumen |
| `region_kpi` (`volumen_eur`, `intensitaet_pct`) | Regionsvergleich ohne Grösse |
| Strategie-Pipeline (`volEcht`, `volSchaetz`) | Volumen-Bereich praktisch leer |
| `buyer_stats` / `market_stats` Volumen | Kennzahl ohne Aussage |

Gemessen in der Strategie-Ansicht: CH Bau zeigte **2.479 Verträge, davon 2.477 „ohne
Wert"** und 1,2 Mio € „echt". Die Zahl war nicht falsch, sie war leer — und sie sah aus
wie ein kleiner Markt.

---

## Die Mechanik seit 2026-09-15

### Woher die Kurse kommen

`scripts/fetch_ezb_kurse.py` holt die **EZB-Referenzkurse** (Reihe `EXR`, Frequenz `A` =
Jahresdurchschnitt) nach `data/reference/waehrungskurse.json`:

```bash
python3 scripts/fetch_ezb_kurse.py
```

Geholt werden 13 Währungen — CHF, USD, GBP, DKK, SEK, NOK, PLN, CZK, HUF, RON, BGN, ISK,
TRY —, jeweils ab 2004. Die nordischen und mitteleuropäischen Reihen stehen für die
nächsten Länder schon bereit; gebraucht werden heute (gemessen 2026-09-15 über das Silber
aller vier Länder) CHF (50.339 Sätze), USD (216), GBP (31), BGN (8) und je einer in PLN,
DKK und ISK.

> **⚠ Die EZB-Reihe nennt Einheiten der FREMDWÄHRUNG je Euro.** 2015 kostete ein Euro
> 1,0679 CHF. Umgerechnet wird deshalb mit **`betrag / kurs`**, nicht mal. Beim Franken
> fällt ein vertauschtes Verhältnis kaum auf — der Kurs liegt nahe 1 —, bei HUF (398 je
> EUR) verhundertfacht es still die Marktgrösse. `tests/test_waehrungsumrechnung.py`
> prüft die Richtung mit einer Währung, bei der sie nicht zu übersehen ist.

### Wie umgerechnet wird

`govisor.gold._wert_in_eur_sql(betrag, waehrung, jahr)` baut den SQL-Ausdruck. Drei Fälle:

| Fall | Ergebnis |
|------|----------|
| `EUR` oder `NULL` | Betrag unverändert (TED-Konvention: leere Währung = Euro) |
| Währung mit Kurs | `betrag / kurs des Veröffentlichungsjahres` |
| Währung ohne Kurs (z. B. AED) | **NULL** — ohne Kurs gibt es keinen Euro-Betrag |

Die Kurse sind **nicht fest eingetragen.** Sie kommen täglich aus der EZB-Schnittstelle und
stehen als Jahresreihe in der Datei; der Code kennt keine einzige Zahl.

### Das laufende Jahr — und warum der Abruf in den Tageslauf gehört

Für das laufende Jahr veröffentlicht die EZB noch keinen Jahresdurchschnitt. Den
Vorjahreskurs zu erben wäre eine schlechte Näherung, und zwar messbar: am 2026-09-15 lag
HUF **7,1 %** vom Jahresschnitt 2025 entfernt, NOK 5,0 %, USD 2,9 %, CHF 1,7 %.

Deshalb holt `fetch_ezb_kurse.py` für das laufende Jahr zusätzlich die **Monatsreihe**
(`M.<WÄHRUNG>.EUR.SP00.A`) und mittelt die bisher veröffentlichten Monate — ein *laufender*
Jahresdurchschnitt, der mit jedem Monat genauer wird. Sobald die EZB im Januar den echten
Jahreswert veröffentlicht, hat er Vorrang und der gemittelte verschwindet.

Welche Jahreswerte so entstanden sind, steht im Block `laufend` der Zieldatei — wer mit den
Zahlen rechnet, muss das wissen können, ohne den Code zu lesen.

> **⚠ `geholt_am` gilt für die DATEI, nicht für jede Zahl darin.** Am **2026-10-05** trug die
> Kursdatei das Datum desselben Tages und hatte trotzdem **keinen CHF-Kurs für 2026**: der
> nächtliche Abruf um 01:13 bekam für `M.CHF` einen 504, das Skript übersprang die Reihe und
> schrieb mit **Exit 0** weiter. `A.RON` fiel am selben Lauf ganz aus der Datei. Zwölf von
> dreizehn Währungen waren frisch, eine nicht, und nichts sagte es — der Tageslauf meldete
> „ok", und für die Schweiz rechnete `value_eur` ab da mit dem Vorjahreskurs.
>
> Der Ausfall war ein **Zeitfenster**: dieselben Reihen antworteten am Vormittag sechsmal von
> sechs mit 200. Aus einem vorübergehenden 504 wurde eine dauerhaft fehlende Zahl.
>
> Drei Dinge halten das jetzt auf, und der mittlere ist der wichtigste:
> 1. **Wiederholung** bei 500/502/503/504/408/429 (nicht bei 404 — eine Reihe, die es nicht
>    gibt, gibt es auch beim vierten Fragen nicht). Beim Messen am selben Tag kamen **USD,
>    NOK und PLN erst im zweiten Versuch** durch; ohne Wiederholung wären auch sie
>    ausgefallen.
> 2. **Übernahme aus der vorigen Datei.** Das Skript schreibt die Zieldatei GANZ neu — fällt
>    eine Reihe aus, war die neue Datei bisher schlechter als die alte, und zwar ohne
>    Fehlermeldung. Jetzt wird jeder Wert nachgetragen, den die alte hatte und die neue nicht.
>    ⚠ Ohne Vordatei fehlt der Kurs weiterhin, und das ist richtig so: geraten wird nichts.
> 3. **Zwei Bücher in der Datei** — `luecken` (was nicht geholt werden konnte) und
>    `uebernommen` (was deshalb aus der vorigen Datei stammt) — plus **Exit 2** für den
>    Teilausfall, den `daily_leads.sh` eigens ansagt. 0 hieße „alles geholt", 1 hieße „nichts
>    geschrieben"; beides war hier falsch.
>
> Gewacht wird das von `tests/test_waehrungsumrechnung.py::
> test_chf_wurde_frisch_geholt_und_nicht_uebernommen` — **nur für CHF**, der einzigen
> Fremdwährung mit nennenswertem Bestand. Für ISK oder TRY wäre derselbe Anspruch Lärm.
>
> ⚠ **Die Reihenfolge der Währungsliste ist Teil des Schutzes.** Ein Zeitdeckel begrenzt den
> Lauf (sonst kosten 26 Reihen mal drei Versuche über zwei Stunden), und er wird von vorn
> nach hinten verbraucht: was hinten steht, fällt bei einer kranken Quelle zuerst aus. CHF
> steht deshalb vorn. Am 2026-10-05 hingen `A.ISK` und `A.BGN` reproduzierbar (beide 504 nach
> genau 30 s), während ihre Monatsreihen in 0,2 s antworteten.

```
CHF  2026 laufend: 0.9212 aus 8 Monaten · -1,7 % gegen 2025
HUF  2026 laufend: 369.4938 aus 8 Monaten · -7,1 % gegen 2025
```

> ⚠ **Der Abruf hängt im Tageslauf, VOR dem Gold-Bau.** Beides zählt. Eine Kursdatei, die
> jemand einmal von Hand geholt hat, ist genau so lange richtig, wie sich die Welt nicht
> bewegt — und `_wert_in_eur_sql()` liest die Datei beim **Bauen** der SQL-Ausdrücke, also
> gilt im Gold von heute, was zu diesem Zeitpunkt auf der Platte lag. Stünde der Abruf
> dahinter, rechnete jeder Lauf mit den Kursen des Vortages.
>
> Fällt die EZB aus, bleibt die alte Datei stehen und der Lauf geht weiter: alte Kurse sind
> besser als keine Werte. `tests/test_waehrungsumrechnung.py` hält beides fest — die
> Verdrahtung, die Reihenfolge und eine **30-Tage-Frist** auf `geholt_am`.

⚠ Erst jenseits aller bekannten Jahre greift der Notnagel: dann gilt der jüngste vorhandene
Kurs. Das ist der Fall, den man nie sehen sollte.

Verdrahtet ist der Ausdruck an **vier** Stellen — wer eine neue Wertquelle baut, muss ihn
dort ebenfalls einsetzen:

| Stelle | Feld |
|--------|------|
| `gold.build_quality` | `final_value_clean` |
| `gold.build_leads` | Schätzwert-Fallback (eigener + Zwillingssatz) |
| `gold.build_prospective_leads` | dieselbe zweistufige Kaskade |
| `gold` Lose-Tabelle | `lot_value_eur` (Jahr aus `lo.start_date`, die Abfrage kennt kein `publication_date`) |

### Wie die Herkunft gekennzeichnet wird

**Ein umgerechneter Wert ist kein gemessener.** Drei Marken, die nebeneinander stehen und
sich nicht ersetzen:

| Marke | Sagt |
|-------|------|
| `waehrung_fremd` | Der Auftrag war nicht in Euro ausgeschrieben |
| `waehrung_umgerechnet` | Der Euro-Betrag ist von uns gerechnet, nicht gemessen |
| `wert_umgerechnet` (Spalte in `leads`) | dasselbe, bis in die Oberfläche durchgereicht |

> **Abweichung von dem, was dieses Kapitel ursprünglich forderte.** Punkt 3 der alten
> Fassung verlangte eine eigene Ausprägung in `value_source` („nicht `actual`"). Umgesetzt
> ist es anders, und zwar bewusst: `value_source` hat ein **festes Vokabular**
> (`actual` / `estimated` / `unknown`, abgesichert in
> `tests/test_plumbing.py::_EXPORT_VOCAB`), und mehrere Auswerter vergleichen hart auf
> `= 'actual'`. Eine vierte Ausprägung hätte sie stumm aus der Zählung geworfen — genau
> die Fehlerform, die dieses Kapitel beschreibt. Ausserdem stimmt `actual` sachlich: der
> **Endwert ist** der Endwert, nur seine Euro-Darstellung ist gerechnet. Die
> Kennzeichnung liegt deshalb in einer eigenen Spalte daneben. Der Anspruch des Kapitels
> bleibt erfüllt: **die Oberfläche kann die Herkunft zeigen.**

### Was es gebracht hat

Gemessen am 2026-09-15 gegen das Silber der vier Länder:

```
verwertbare Werte    alt         neu
  CH               2.043  →   52.125     (×25)
  DE             377.569  →  377.578     (+9  · USD/GBP/CHF-Einzelfälle)
  AT              45.381  →   45.381     (±0  · reines Euro-Land)
  LU               7.741  →    7.741     (±0)
```

Gegenprobe am 2026-09-15 an der neu gebauten Qualitätstabelle CH (Sandkasten, 53.417
Zeilen): **52.230
Werte**, davon **50.444 umgerechnet** — und dieselben 50.444 tragen weiterhin
`waehrung_fremd`. Die Verteilung liegt jetzt in derselben Grössenordnung wie DE:

```
Quantile 10/25/50/75/90 in EUR
  CH    177.527 · 343.615 ·   729.766 · 1.937.667 ·  5.768.219
  DE     77.236 · 215.423 ·   589.500 · 4.960.719 · 51.408.000
```

Der Median liegt höher als in DE, der obere Rand deutlich tiefer — das Bild eines
kleineren Marktes mit grösseren Einzelvergaben. Plausibel, und vor allem: nicht mehr leer.

> **⚠ Die Zahlen oben stammen aus Silber und einem Sandkasten-Bau, nicht aus dem Gold der
> Maschine.** Bis der nächste Nachtlauf `build_quality` für alle Länder neu schreibt,
> tragen `data/gold/*/quality.parquet` und alles, was daraus folgt, noch die alten Werte.

## Was zu tun ist, bevor ein Nicht-Euro-Land ausgeliefert wird

1. **Währung erkennen und mitführen.** `value_currency` muss aus der Quelle kommen, nicht
   geraten werden. Es gibt ein Flag `waehrung_angenommen` für den Fall, dass sie
   erschlossen wurde — das ist die ehrliche Variante.
2. **Kurs beschaffen.** Führt die EZB die Währung? Dann reicht
   `python3 scripts/fetch_ezb_kurse.py --waehrungen XXX`. Führt sie sie nicht (AED etwa),
   ist das eine Entscheidung und kein Nebenschauplatz: entweder eine andere Kursquelle
   dokumentieren oder die Werte ausfallen lassen — aber nie „ungefähr Euro".
3. **Kurs zum Vergabejahr, nicht zum Stichtag.** Ein Vertrag von 2004 mit dem Kurs von
   heute bewertet ist bei CHF um 65 % daneben (1,5438 gegen 0,9370). Die Jahresreihe
   steht neben `dim_deflator`, und beide gehören zusammen angewandt: erst in Euro, dann
   in Realwert.
4. **Herkunft kennzeichnen** — siehe oben, `waehrung_umgerechnet` plus `wert_umgerechnet`.
5. **Erst dann** die wertbasierten Kennzahlen für dieses Land einschalten.

## Der Deflator

`dim_deflator` liefert den Realwert-Faktor. Für AT und CH gibt es **keine eigene
CPI-Reihe**; der Lauf verwendet die deutsche Näherung und schreibt das in `cpi_source`:

```
⚠ dim_deflator CH: keine eigene CPI-Reihe — DE-Naeherung verwendet
```

Das ist vertretbar für Nachbarländer mit ähnlicher Inflation und **nicht** vertretbar für
ein Land mit anderer Geldpolitik. Für ein neues Land: entweder eine CPI-Reihe beschaffen
oder die Näherung ausdrücklich als solche stehen lassen — aber nie stillschweigend.

> **⚠ Reihenfolge.** Der Deflator rechnet EUR-2020 aus EUR. Er darf erst **nach** der
> Währungsumrechnung greifen, sonst deflationiert er Franken mit deutschen Preisen.
> In `gold` ist das so verdrahtet (`VUR = VU * dd.factor_to_2020`, und `VU` ist bereits
> in Euro) — bei jeder neuen Wertstrecke ist es nachzuprüfen.

## Wert-Fallen, die unabhängig von der Währung gelten

- **`wert_sentinel`** — 100.000 Platzhalter mit 0,01 oder 1,00. Als „Wert bekannt" gezählt
  wären sie eine Lüge.
- **`schaetzwert_negativ`**, **`wert_verdaechtig`**, **`wert_absurd`** — die Flags gibt es;
  ein neues Land muss sie **auslösen**, nicht nur tragen.
- **Die Plausibilitätsgrenze gilt dem EURO-Betrag, nicht dem Rohbetrag.** `>= 100` soll
  Cent-Platzhalter fangen. Gegen den Rohbetrag geprüft benachteiligt sie jede Währung mit
  kleiner Einheit — 100 HUF sind 25 Cent, 100 ISK sind 69 Cent.
- **Werte nie zu einer Gesamtsumme addieren.** Drei getrennte Klassen (echt / geschätzt /
  unbekannt-Anzahl), gestapelt dargestellt. Das ist eine Produktregel, keine Kosmetik.
- **Die Schätzung trifft nur ~42 % das richtige Band.** Deshalb ist die Preisstufe ein
  Flat-per-Band-Modell und kein Prozentsatz auf einen geratenen Wert.

## Die Sätze ohne Währung — aufgeklärt am 2026-09-15

Beim Nachsehen stellte sich heraus: es sind nicht 1.474, sondern **86.177** über vier
Länder, und es war nie eine Datenlage, sondern ein Parser-Fehler.

```
Endwert ohne Währung        Zeitraum
  DE  74.051                2010-03-10 – 2024-02-02
  AT   8.425                2010-03-10 – 2024-01-05
  LU   2.227                2011-01-04 – 2023-11-28
  CH   1.474                2016-08-09 – 2017-08-17
```

**100 %** dieser Sätze holen ihren Wert über den Vor-2014-Pfad
`COSTS_RANGE_AND_CURRENCY_WITH_VAT_RATE/VALUE_COST`, und in dieser einen Zeile standen
**zwei** Fehler:

```python
amt, cur = _first_amount(costs, ("VALUE_COST",), ("CURRENCY",))
```

1. **Die Währung hängt am Eltern-Knoten**, nicht am Wertknoten. `_first_amount` sucht sie
   am `VALUE_COST` und fand nie eine.
2. **`_to_amount` wirft das Dezimalkomma weg.** `189 945 844,15` wurde zu
   18.994.584.415 — das Hundertfache. Rund 57 % der betroffenen Sätze tragen den Faktor.
   Der Code wusste davon: `_ojs_amount` existiert seit Langem genau für diese Lesart und
   wurde an dieser Stelle nicht benutzt.

**Und der zweite Fehler hat den ersten versteckt.** Ohne Währung fielen die Sätze aus
`final_value_clean` heraus, also rechnete sie nie jemand nach. Die Plausibilitätsgrenze
von 1 Mrd stand die ganze Zeit daneben und hat die 19 Mrd **nie gesehen** — eine Prüfung
hinter einem Filter prüft nur, was der Filter durchlässt. Sichtbar wurde beides erst, als
die Währungsumrechnung die Sätze hereinholte: der eine Fix legte den anderen Fehler frei.

### Behoben

`schema._kosten_betrag()` liest den **Textknoten**, europäisch: Leerzeichen und Punkt sind
Tausender, das Komma ist der Dezimaltrenner. `@FMTVAL` bleibt Rückfall für Knoten ohne
Text. Die Währung kommt vom Eltern-Knoten.

> ⚠ **Der erste Reparaturversuch griff nach `@FMTVAL` — und war schlimmer als der Fehler.**
> Das Attribut sieht maschinenlesbar aus und ist in den alten Jahrgängen nicht normiert.
> In einer einzigen Datei (LU 226973_2011) stehen vier Varianten nebeneinander:
>
> ```
> Text          @FMTVAL                Verhältnis
> 3 636 304     3636304000000000000    × 10¹²
> 1 000 000     100000000              × 100  (Cent)
> 900 000       9000000000             × 10000
> 900 000       900000.00              richtig
> ```
>
> Aus einem Auftrag über 3,6 Mio EUR wurde einer über 3,6 Trillionen. Aufgefallen ist es
> nur, weil `pruefe_werte.py` nach dem Neubau sofort wieder rot meldete — **der Wächter
> fand den Fehler in seiner eigenen Reparatur.** Falle H14 in
> [Kapitel 12](12-fallenkatalog.md).
>
> ⚠ Und die beiden Lesarten sind **gegenläufig**: im Text ist der Punkt Tausender-Trenner
> (`1.234.567,89`), in `@FMTVAL` Dezimal-Trenner (`1234567.89`).
> `tests/test_legacy_kostenwert.py` hält beide Richtungen fest.

Gegengeprüft an drei echten Bronze-Dateien (2785_2017: 4.226.600.976,20 EUR;
371305_2012: 1.148.695.080,00 EUR; 249447_2011: 784.621.625,10 EUR) — alle drei liefern
nach der Reparatur Betrag **und** Währung wie im XML.

### Der Fund daneben: 26.383 fehlende Schätzwerte

Derselbe Block las den Vor-2014-**Schätzwert** überhaupt nicht.
`VAL_ESTIMATED_TOTAL` gibt es erst in den 2014er-Formularen; davor heisst der Knoten
`INITIAL_ESTIMATED_TOTAL_VALUE_CONTRACT`. Der OJS-Zweig las ihn seit Langem, der
Legacy-Zweig nicht — DE 23.663, AT 2.072, LU 648 Schätzwerte blieben leer, die im XML
danebenstanden. Ebenfalls behoben.

### Was der Neubau gebracht hat

Ausgeführt in der Nacht zum 2026-09-16, alle vier Länder, danach der reguläre Nachtlauf
(72 min) über das neue Silber:

```
Silber            ohne Währung        Werte > 1 Mrd      Schätzwerte
  DE       74.051 →      0        2.177 →   211      +23.663
  AT        8.425 →      0          354 →    34       +2.072
  LU        2.227 →      0           56 →    14         +648
  CH        1.474 →      0           49 →    11           ±0
```

Und im ausgelieferten Gold — die Zahl, um die es die ganze Zeit ging:

```
Leads mit Wert      vorher      nachher
  CH                  1 %         96 %   (8.070 von 8.401, davon 6.550 umgerechnet)
  DE                             91 %
  AT                             98 %
  LU                             60 %
```

`waehrung_angenommen` steht in allen vier Ländern auf **0**. Die Abnahmeschwelle dieses
Kapitels („unter 50 % ist das Land nicht wertfähig") ist damit überall gerissen — LU mit
60 % am knappsten, und das ist der nächste Punkt zum Hinsehen.

⚠ **Zwei Dinge fielen beim Neubau auf, die nichts mit Währung zu tun hatten** und ohne ihn
weiter unentdeckt geblieben wären:

- **246.908 + 41.706 + 8.868 Kennungen kamen in der falschen Form zurück.** Das Textformat
  (2004–2010) führt die Nummer als `68-2005`, und `_parse_text` überschrieb damit die
  bereits kanonische Kennung. Es gab dafür eine „Einmal-Migration" — die den Bestand
  geheilt und die Ursache verdeckt hatte. ⚠ **Eine Migration ist keine Einmal-Sache,
  solange der Erzeuger den Fehler weiter erzeugt.**
- **Die Migration selbst war DE-fest** und kannte `master_id`/`duplicate_id` des
  Dublettenwalls nicht — 11 AT-Waisen, gefunden von `pruefe_gold_integritaet`, nicht vom
  Migrationsskript. Beides behoben, beides jetzt über `laender.AKTIV`.

### ⚠ Was noch aussteht

**Die Reparatur sitzt im Parser, also in der Bronze→Silber-Strecke.** Bis Silber für die
betroffenen Länder neu gebaut ist, tragen die Daten die alten Zahlen.

⚠ **Und der Weg dorthin ist nicht für alle Länder derselbe** — das ist die Falle in diesem
Absatz. Es gibt zwei Bronze-Bestände, und welcher gilt, sieht man an den Dateinamen im
Silber:

| Bronze | Silber heisst | Neubau |
|--------|---------------|--------|
| `data/raw/<LAND>/<YYYY-MM>.tar.gz` (Monatspakete) | `2016-08.parquet` | `python3 -m govisor.cli silver --country XX --force` |
| `data/raw_live/<LAND>/…/<pub>.xml` (Live-Abruf) | `2016-08-live.parquet` | `python3 scripts/fetch_ted_live.py --country XX --nur-silber` |

Die Schweiz hat **kein** Monatspaket-Bronze (`silver.available_months` liefert 0) — ihr
gesamter TED-Bestand kam über den Live-Abruf, und `cli silver --country CH` täte
klaglos gar nichts. Genau so sieht ein Neubau aus, der nicht stattgefunden hat.

`--nur-silber` holt nichts aus dem Netz: es parst die vorhandenen XML neu und schreibt sie
über **denselben** Weg wie der Live-Abruf (`_mit_bestand`), sodass die Nachbarquellen
desselben Monats (simap, atverg, DÖE) unberührt bleiben. Dafür gibt es das Bronze — der
Code sagt es selbst: „ein späterer Parser-Fix läuft über lokale Dateien statt 13k neuer
Requests."

`scripts/pruefe_werte.py` sagt jede Nacht, wie weit das ist — solange es Befunde meldet,
steht der Neubau aus. Für DE, AT, CH und LU ist er am 2026-09-16 erledigt; offen bleiben
**EU** (8 von 69 Werten über 1 Mrd) und **PL** (348 von 125.084) — Altbestände der
zurückgebauten Länder, nicht geprüft.

## Prüfung für die Abnahme

```sql
SELECT count(*)                                        AS leads,
       count(value_eur)                                AS mit_wert,
       count(*) FILTER (WHERE value_source='actual')   AS echt,
       count(*) FILTER (WHERE wert_umgerechnet)        AS umgerechnet,
       count(DISTINCT value_currency)                  AS waehrungen
FROM read_parquet('data/gold/XX/lead_export.parquet')
```

**Liegt `mit_wert` unter 50 %, ist das Land nicht wertfähig** — und das gehört in die
Abnahmetabelle und in die Auto-Memory, nicht in den Kopf.

Zweite Prüfung, seit es die Umrechnung gibt: **`umgerechnet` muss bei einem Nicht-Euro-Land
gross sein.** Steht dort 0, greift die Umrechnung nicht — vermutlich fehlt
`data/reference/waehrungskurse.json`, und `_wert_in_eur_sql` fällt still auf die alte
Euro-Sperre zurück. Genau dafür gibt es `test_kurse_vorhanden_und_plausibel`.

## Der Statusvermerk

Die Schweiz war seit Monaten live und **nicht wertfähig**. Das war eine bewusste,
dokumentierte Lage (Auto-Memory `govisor-chf-wertluecke`) — keine Panne. Der Fehler wäre
gewesen, sie nicht zu benennen: dann liest jemand „CH Bau 1,2 Mio €" und hält es für den
Markt.

Seit 2026-09-15 ist sie behoben. Der Vermerk bleibt trotzdem stehen, aus zwei Gründen:
die Lage ist erst nach dem nächsten vollständigen Gold-Bau in den Auslieferungsdaten
angekommen, und die **Lehre** gilt unabhängig davon — ein Land kann monatelang live,
grün und vollständig aussehen und trotzdem in seiner wichtigsten Kennzahl leer sein.
