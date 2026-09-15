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

Für das **laufende Jahr** gibt es noch keinen Jahresdurchschnitt; dann gilt der jüngste
vorhandene Kurs. Das ist eine Näherung, und sie ist im Code als solche benannt.

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

## Offen: die Sätze ohne Währung

**⚠ Aufgenommen 2026-09-15, nicht behoben.** In CH tragen **1.474** Bekanntmachungen einen
Wert **ohne** Währung — alle `can`, alle aus dem Fenster 2016-08 bis 2017-08, also eine
abgegrenzte Parser-Ära. Ihr Median liegt bei **17,1 Mio**, gegen 698 Tsd bei den
CHF-Sätzen desselben Landes. Sie gelten nach der TED-Konvention als Euro.

Zwei Dinge daran sind zu klären, bevor jemand mit diesen Zahlen rechnet:

1. **„Leer heisst Euro" ist eine TED-Konvention, keine Naturkonstante.** In einem Land,
   das nicht in Euro rechnet, ist die wahrscheinlichere Lesart die Landeswährung.
2. **Der Faktor 25 erklärt sich damit trotzdem nicht.** CHF→EUR verschöbe den Median um
   rund 7 %, nicht um das 25-fache. Dahinter steckt etwas anderes — eine andere Einheit,
   eine Rahmensumme oder ein Parser-Fehler jener Ära. Das ist zu messen, nicht zu raten.

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
