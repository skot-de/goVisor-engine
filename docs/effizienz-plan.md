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

## P2 · Die Vorgangsbündel streuen Änderungen absichtlich

**Befund.** `export_vorgaenge` bündelt Akten nach `sha1(land:vorgang_id)[:3]` — 4.096 Bündel,
gleichmässig gefüllt. Das ist bewusst so gebaut, und die Begründung im Skript ist richtig:
256 Bündel wären beim Upload teurer, feiner scheitert an der Dateigrenze von `next build`
(bei ~156.000 Dateien SIGABRT, heute 107.529).

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

### Schritt 2 — P2, Vorbereitung (ein Tag)

1. **Messen, ob alte Akten wirklich unveränderlich sind:** einen Lauf lang aufzeichnen,
   welche Bündel sich ändern, und deren Vorgänge nach Alter aufschlüsseln. Ergibt die
   Messung, dass auch alte Akten regelmässig berührt werden, fällt P2 ersatzlos weg.
2. Erst wenn die Messung trägt: Schlüssel entwerfen, Dateizahl gegen die
   `next build`-Grenze rechnen (heute 107.529 von ~156.000).

**Abnahme:** eine Zahl, die sagt, wie viele der nächtlich geschriebenen Bündel alte
Vorgänge betreffen.

### Schritt 3 — P2, Umsetzung (zwei Tage)

1. Schlüssel in `export_vorgaenge.py` **und** `web/lib/vorgangsakte.ts` ändern — sie müssen
   übereinstimmen, das steht schon als Warnung im Skript.
2. Einmalige vollständige Neuschreibung, alter Bestand bleibt bis zur Abnahme liegen.
3. `next build` fahren: die Dateizahl ist die harte Grenze.

**Abnahme:** zwei Nachtläufe hintereinander schreiben unter 15 % der Bündel neu, und eine
Stichprobe von Akten ist über die Oberfläche unverändert erreichbar.

### Schritt 4 — P4, Messung (ein Tag, dann Entscheidung)

Prüfsummen und Bauzeiten je Gold-Tabelle mitschreiben, eine Woche laufen lassen, danach
entscheiden. Kein Umbau ohne diese Woche.

### Nicht im Plan

P3 bleibt liegen, bis P1 gemessen ist. Wird der Listenabruf durch das Zwischenspeichern
selten genug, lohnt der Umbau nicht — und ein Umbau, der sich nicht lohnt, kostet zweimal:
einmal beim Bauen und einmal bei jedem, der ihn später verstehen muss.
