# Wo die App Arbeit verschwendet — gemessen, mit Umsetzungsplan

**Stand 2026-09-04.** Alle Zahlen hier sind gemessen, nicht geschätzt; wo etwas geschätzt ist,
steht es dabei. Wer das Dokument in einem Monat liest: die Zahlen wandern, die Befunde
bleiben, bis sie abgearbeitet sind.

## Der Ist-Zustand in drei Zahlen

```
Nachtlauf           119 min, davon drei Schritte 62 %
Ausliefergut        4,03 GB in 116.260 Dateien (Upload-Auswahl)
Listenabruf         47,2 MB roh / 5,6 MB gzip — bei JEDEM Aufruf neu
```

### Nachtlauf, oberste Ebene (2026-09-04)

| Schritt | min | Anteil |
|---|---:|---:|
| Gold-Rebuild | 32,1 | 27 % |
| Frontend-Daten exportieren | 26,7 | 22 % |
| Healy-Hudson-Bekanntmachungen | 14,9 | 13 % |
| DÖE-Ingest | 6,2 | 5 % |
| übrige (13 Schritte) | 33,1 | 28 % |

Im Frontend-Export dominiert **`export_vorgaenge` mit 18,4 min** — zwei Drittel des Schritts.

### Ausliefergut

| Verzeichnis | GB | Anteil |
|---|---:|---:|
| `vorgang-archiv` | 1,76 | 44 % |
| `doc-text` | 0,62 | 15 % |
| `doc-analysis` | 0,51 | 13 % |
| `vorgang-kennung` | 0,44 | 11 % |
| übrige | 0,70 | 17 % |

---

## P1 · Der Listenabruf wird bei jedem Aufruf neu geladen

**Befund.** `/api/leads?branche=bau` liefert die ganze Datei und setzt dabei
`cache-control: no-store`. Gemessen:

```
leads-bau.json   47,2 MB roh → 5,6 MB gzip (8,4×) · 18.731 Leads
JSON.parse serverseitig: 103 ms (nur wenn Zuschläge dazukommen)
```

Die Daten ändern sich **einmal am Tag**. `no-store` heisst: jeder Neuladevorgang und jeder
Wechsel des Grundraums kostet erneut 5,6 MB — auch der Wechsel zurück, eine Minute später.

**Vorschlag.** `ETag` aus Größe und Zeitstempel der Quelldatei, dazu
`cache-control: private, max-age=0, must-revalidate`. Der Browser fragt dann nur noch nach,
ob sich etwas geändert hat (ein paar hundert Byte), und lädt neu, wenn der Nachtlauf durch
ist. Kein Risiko veralteter Daten: die Prüfung findet bei jedem Aufruf statt.

**Aufwand** klein (eine Route). **Risiko** gering. **Ertrag** wiederholte Aufrufe von 5,6 MB
auf nahe null.

⚠ Voraussetzung: die Antwort muss überhaupt komprimiert ausgeliefert werden. Das ist auf
einem Deployment üblich, lokal nicht — vor der Umsetzung einmal am echten Host nachsehen.

## P2 · Die Vorgangsbündel streuen Änderungen absichtlich ❌ WIDERLEGT

> **Gemessen am 2026-09-05, siehe Schritt 2.** Die Annahme dieses Abschnitts — alte Akten
> ändern sich nicht mehr — hält nicht: sie stellen **92 % aller nächtlichen Änderungen**.
> Und bei gleicher Bündelzahl schlägt ein schlichter, feinerer Hash die Alterstufe um 21 %.
> Der Hebel ist die Granularität, nicht das Alter. Der Rest dieses Abschnitts steht als
> Beleg dafür, wie plausibel die falsche These war.


**Befund.** `export_vorgaenge` bündelt Akten nach `sha1(land:vorgang_id)[:3]` — 4.096 Bündel,
gleichmässig gefüllt. Das ist bewusst so gebaut, und die Begründung im Skript ist richtig:
256 Bündel wären beim Upload teurer, feiner scheitert an der Dateigrenze von `next build`
(bei ~156.000 Dateien SIGABRT; Stand 2026-09-04: 116.307, bewacht von
`pruefe_verdrahtung.py --sonde baugrenze`).

Nur streut ein gleichmässiger Schlüssel eben auch die Änderungen. Gemessen im Lauf vom
2026-09-04:

```
Produktmenge   2.393 geschrieben, 1.703 unverändert
Archiv         2.633 geschrieben, 1.463 unverändert
Kennungen      3.020 geschrieben, 1.076 unverändert
               ─────────────────────────────────────
               8.046 von 12.288 Bündeln neu (65 %)
```

Dem steht gegenüber, wie viel sich wirklich ändert:

```
1.990.055 DE-Bekanntmachungen mit Datum
  älter als 2 Jahre   1.588.569   79,8 %   ← ändern sich nie wieder
  90 Tage bis 2 Jahre   339.568   17,1 %
  letzte 90 Tage         61.918    3,1 %
```

**Vorschlag.** Den Bündelschlüssel um eine Alters- oder Jahresstufe ergänzen, etwa
`<jahr>/<hash2>`. Alte Jahrgänge landen dann in eigenen Bündeln, werden einmal geschrieben
und nie wieder angefasst; die Nachtarbeit konzentriert sich auf die letzten Monate. Die
Zahl der Dateien bleibt in derselben Größenordnung (Jahresstufe × gröberer Hash), die
Bündelgröße ebenfalls.

**Aufwand** mittel. **Risiko** mittel: der Schlüssel muss mit `web/lib/vorgangsakte.ts`
übereinstimmen (steht so im Skript), und die Umstellung schreibt den Bestand einmal
vollständig neu. **Ertrag** geschätzt 65 % → 5–10 % neu geschriebener Bündel je Nacht;
entsprechend weniger Upload.

⚠ Vor der Umsetzung zu prüfen: ob die Akte eines alten Vorgangs wirklich unveränderlich ist.
Ein nachträglich verknüpfter Zuschlag oder eine Ketten-Zuordnung könnte sie berühren. Diese
Messung fehlt noch und ist die erste Aufgabe des Schritts.

## P3 · Die Liste trägt Detailgewicht mit

**Befund.** Feldanteile in `leads-bau.json` (31,2 MB Feldinhalt):

```
beschreibung  6,3 MB  20,1 %      unterlagen  2,4 MB   7,8 %
anf           4,3 MB  13,9 %      lose        2,0 MB   6,5 %
```

Vier Felder machen 48 % aus. **Sie lassen sich aber nicht einfach weglassen:**
`beschreibung` speist die Volltextsuche im Browser (`leadText` in `explorerCore.js`), und
`detail-<branche>.json` enthält diese Felder NICHT — es gibt also keine Dopplung, aus der
man schöpfen könnte.

**Vorschlag.** Zwei Stufen statt einer: `/api/leads` liefert zuerst die Felder, die Liste und
Filter brauchen; ein zweiter Abruf holt den Suchindex (Beschreibung und Anforderungen) im
Hintergrund nach. Die Suche bleibt vollständig, sie steht nur eine Sekunde später bereit —
und die erste Darstellung kommt mit geschätzt 2,9 statt 5,6 MB.

**Aufwand** mittel. **Risiko** mittel: der Datenfluss des Explorers wird angefasst, und die
Suche darf zwischen den Stufen keine falschen Trefferzahlen zeigen. **Ertrag** erste
Darstellung rund doppelt so schnell.

⚠ Erst nach P1 angehen. Wenn der Abruf ohnehin nur einmal je Tag stattfindet, ist der
Gewinn kleiner als der Umbau — dann lieber lassen.

## P4 · Gold-Rebuild: was muss wirklich täglich?

**Befund, unvollständig.** 32,1 min, 48 Bauschritte, 72 Tabellen je Land. Was davon sich
täglich ändert, ist **nicht gemessen**. Plausibel, aber unbelegt: die Historien-Aggregate
über 2004–2025 (Marktpuls-Jahreslayer, Nachfolge-Ketten, `dim_*`) ändern sich kaum.

**Vorschlag.** Zuerst messen, dann entscheiden — nicht umgekehrt. Ein Lauf, der je Tabelle
Prüfsumme und Bauzeit festhält, beantwortet nach einer Woche, welche Tabellen einen
Wochen- statt Tagesrhythmus vertragen.

**Aufwand** klein für die Messung, offen für die Umsetzung. **Ertrag** unbekannt — genau
deshalb erst messen.

## P5 · Nicht vorgeschlagen, und warum

**Healy-Hudson (14,9 min)** ist ein Netzabruf über 16 Länder mit rotierender Liste. Ohne
Messung, wo die Zeit hingeht (Wartezeit gegen Verarbeitung), wäre jeder Vorschlag geraten.

**`doc-text` und `doc-analysis` (1,13 GB Ausliefergut)** sind das Produkt selbst. Hier ist
nichts zu sparen, ohne etwas wegzunehmen.

---

## Umsetzungsplan

Die Reihenfolge folgt dem Verhältnis von Ertrag zu Risiko, nicht der Größe der Zahl.

### Schritt 1 — P1, Cache-Header ✅ erledigt 2026-09-04

1. Am echten Host prüfen, ob Antworten komprimiert ausgeliefert werden.
2. `ETag` aus `stat()` der Quelldatei; `must-revalidate` statt `no-store`.
3. Test: zweiter Abruf mit `If-None-Match` muss `304` liefern und keinen Rumpf.
4. Test: nach einem Nachtlauf muss sich der `ETag` geändert haben.

**Abnahme:** ein Grundraumwechsel hin und zurück überträgt die Daten genau einmal.

⚠ **Teilweise erfüllt.** Die Regel (`web/lib/etag.js`) ist über `node` vollständig geprüft,
13 Fälle. Der echte Rundlauf gegen den Server **nicht**: `/api/leads` liegt hinter dem
Anmelde-Tor. Punkt 1 der Liste — ob der Host überhaupt komprimiert ausliefert — bleibt
ebenfalls offen, es ist nichts deployt. Beides gehört zum ersten Go-live-Durchgang.

### Schritt 2 — P2, Messung ✅ abgeschlossen 2026-09-05 · **P2 fällt**

Gemessen mit `scripts/messe_buendel_drift.py`: eine Aufnahme je Akte am 2026-09-04 09:56,
verglichen nach dem Nachtlauf vom 2026-09-05 03:34.

#### 1. Alte Akten sind NICHT unveränderlich

Das war die Annahme, auf der P2 stand. Sie hält nicht:

```
vorgang-archiv   1.397 von 1.733.129 Akten geaendert (0,08 %)
  letzte 90 Tage      22 von    52.012   0,04 %
  90 Tage bis 2 J.    83 von   279.261   0,03 %
  aelter als 2 Jahre 1.292 von 1.120.437  0,12 %   ← 92 % ALLER Aenderungen
```

Alte Akten ändern sich nicht nur, sie sind die **Mehrheit** der Änderungen — anteilig
häufiger als frische. In der Produktmenge noch deutlicher: 1,65 % bei alten gegen 0,74 %
bei frischen.

#### 2. Und selbst wenn: die Alterstufe ist der falsche Hebel

Entscheidend ist nicht, ob Akten sich ändern, sondern wie viele AKTEN dadurch neu
geschrieben werden. Simuliert auf den echten Daten des Archivs (1.736.042 Akten,
4.310 berührt), bei jeweils gleicher Bündelzahl:

| Schlüssel | Bündel | neu | Akten neu geschrieben |
|---|---:|---:|---:|
| heute `hash[:3]` | 4.096 | 2.693 | 1.143.115 |
| `Alter + hash[:2]` | 1.024 | 862 | 1.561.977 |
| `Alter + hash[:3]` | 16.384 | 3.669 | 507.598 |
| **`hash[:3] + 2 Bit` (ohne Alter)** | **16.384** | 3.780 | **402.896** |

Die letzten beiden Zeilen sind der eigentliche Befund: bei **derselben** Bündelzahl schlägt
der schlichte, feinere Hash die Alterstufe um 21 %. Die Alterstufe ist also nicht nur
wirkungslos, sie ist schlechter — sie erzeugt ungleich grosse Bündel (die Stufe „alt" hält
65 % der Akten in einem Viertel der Bündel), und jedes Anfassen kostet entsprechend mehr.

**Der Hebel ist die Granularität, nicht das Alter.** Und die ist bereits gedeckelt: mehr
Bündel heisst mehr Dateien, und `next build` stirbt bei rund 156.000 (Sonde 6, Stand
116.307). Das Archiv von 4.096 auf 16.384 zu bringen kostet +12.288 Dateien — knapp ein
Drittel der verbliebenen Luft für rund 65 % weniger Schreibvolumen (1,07 → 0,38 GB je Nacht).

**Abnahme erfüllt:** die Zahl liegt vor, und sie sagt Nein.

### Schritt 3 — ~~P2, Umsetzung~~ gestrichen

Der Umbau entfällt. Zwei Tage gespart, und das Wissen bleibt: wer das Schreibvolumen des
Archivs senken will, dreht an der Zahl der Hexstellen und rechnet vorher gegen die
Baugrenze — nicht am Alter.

### Schritt 4 — P4, Messung (ein Tag, dann Entscheidung)

Prüfsummen und Bauzeiten je Gold-Tabelle mitschreiben, eine Woche laufen lassen, danach
entscheiden. Kein Umbau ohne diese Woche.

### Nicht im Plan

P3 bleibt liegen, bis P1 gemessen ist. Wird der Listenabruf durch das Zwischenspeichern
selten genug, lohnt der Umbau nicht — und ein Umbau, der sich nicht lohnt, kostet zweimal:
einmal beim Bauen und einmal bei jedem, der ihn später verstehen muss.
