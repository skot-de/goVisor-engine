# 13 · Währung und Werte — der teuerste blinde Fleck

> Gehört zu Tor 4 und 5. **Zuerst lesen, wenn das neue Land nicht in Euro rechnet.**
> Dieses Kapitel entstand am 2026-08-23 beim Durchspielen eines neuen Landes: es fehlte,
> und die Schweiz zeigt seit Monaten, was das kostet.

## Der Befund, in einer Zeile

```
value_eur gefüllt:    DE 91 %    AT 98 %    CH  1 %
```

**77 von 8.301** Schweizer Leads tragen einen verwertbaren Wert (gemessen 2026-08-23). 49.368 Schweizer
Bekanntmachungen tragen das Qualitäts-Flag `waehrung_fremd`.

Der Grund ist keine schlechte Quelle — simap liefert Werte. Der Grund ist, dass die
Pipeline **CHF nicht in EUR umrechnet** und `final_value_clean` nur bei plausibel **und
EUR** gefüllt wird. Was danach kommt, fällt reihenweise aus.

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

Gemessen in der Strategie-Ansicht: CH Bau zeigt **2.479 Verträge, davon 2.477 „ohne Wert"**
und 1,2 Mio € „echt". Die Zahl ist nicht falsch, sie ist leer — und sie sieht aus wie ein
kleiner Markt.

## Was zu tun ist, bevor ein Nicht-Euro-Land ausgeliefert wird

1. **Währung erkennen und mitführen.** `value_currency` muss aus der Quelle kommen, nicht
   geraten werden. Es gibt bereits ein Flag `waehrung_angenommen` für den Fall, dass sie
   erschlossen wurde — das ist die ehrliche Variante.
2. **Umrechnungskurs entscheiden.** Zwei Wege, und die Wahl gehört dokumentiert:
   - **Stichtagskurs** — einfach, aber ein Vertrag von 2019 wird mit dem Kurs von heute
     bewertet.
   - **Kurs zum Vergabedatum** — richtig für Zeitreihen, braucht eine Kursreihe je Jahr.
     Für Realwerte gibt es bereits `dim_deflator`; die Kursreihe gehört daneben.
3. **Herkunft kennzeichnen.** Ein umgerechneter Wert ist kein gemessener. Er braucht seine
   eigene Ausprägung in `value_source` (nicht `actual`), sonst behauptet die Oberfläche
   eine Genauigkeit, die es nicht gibt.
4. **Erst dann** die wertbasierten Kennzahlen für dieses Land einschalten.

## Der Deflator

`dim_deflator` liefert den Realwert-Faktor. Für AT und CH gibt es **keine eigene
CPI-Reihe**; der Lauf verwendet die deutsche Näherung und schreibt das in `cpi_source`:

```
⚠ dim_deflator CH: keine eigene CPI-Reihe — DE-Naeherung verwendet
```

Das ist vertretbar für Nachbarländer mit ähnlicher Inflation und **nicht** vertretbar für
ein Land mit anderer Geldpolitik. Für ein neues Land: entweder eine CPI-Reihe beschaffen
oder die Näherung ausdrücklich als solche stehen lassen — aber nie stillschweigend.

## Wert-Fallen, die unabhängig von der Währung gelten

- **`wert_sentinel`** — 100.000 Platzhalter mit 0,01 oder 1,00. Als „Wert bekannt" gezählt
  wären sie eine Lüge.
- **`schaetzwert_negativ`**, **`wert_verdaechtig`**, **`wert_absurd`** — die Flags gibt es;
  ein neues Land muss sie **auslösen**, nicht nur tragen.
- **Werte nie zu einer Gesamtsumme addieren.** Drei getrennte Klassen (echt / geschätzt /
  unbekannt-Anzahl), gestapelt dargestellt. Das ist eine Produktregel, keine Kosmetik.
- **Die Schätzung trifft nur ~42 % das richtige Band.** Deshalb ist die Preisstufe ein
  Flat-per-Band-Modell und kein Prozentsatz auf einen geratenen Wert.

## Prüfung für die Abnahme

```sql
SELECT count(*)                                        AS leads,
       count(value_eur)                                AS mit_wert,
       count(*) FILTER (WHERE value_source='actual')   AS echt,
       count(DISTINCT value_currency)                  AS waehrungen
FROM read_parquet('data/gold/XX/lead_export.parquet')
```

**Liegt `mit_wert` unter 50 %, ist das Land nicht wertfähig** — und das gehört in die
Abnahmetabelle und in die Auto-Memory, nicht in den Kopf.

## Der Statusvermerk, der fehlen würde

Die Schweiz ist seit Monaten live und **nicht wertfähig**. Das ist eine bewusste,
dokumentierte Lage (Auto-Memory `govisor-chf-wertluecke`) — keine Panne. Der Fehler wäre,
sie nicht zu benennen: dann liest jemand „CH Bau 1,2 Mio €" und hält es für den Markt.
