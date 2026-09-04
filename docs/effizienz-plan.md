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

### Schritt 2 — P2, Vorbereitung ▣ läuft, Zwischenstand 2026-09-04

Werkzeug: `scripts/messe_buendel_drift.py` (`--aufnehmen` / `--vergleichen`). Es hält je
Akte eine Prüfsumme fest und schlüsselt die Unterschiede nach Alter auf.

**Warum nicht über Zeitstempel.** Der naheliegende Weg trägt nicht. Eine Datei-Zeit sagt,
welches BÜNDEL geschrieben wurde, nicht welche AKTE sich geändert hat — und ein Bündel wird
schon wegen einer von rund vierhundert Akten neu geschrieben. Am Messtag kam dazu, dass
Läufe aus einer zweiten Sitzung um 07:57 und 08:41 sämtliche Archiv-Bündel anfassten; die
Zeitstempel waren als Signal wertlos.

#### Was schon gemessen ist

**Der Hash-Schlüssel mischt vollständig — die Voraussetzung für P2 hält.** Stichprobe über
300 der 4.096 Archiv-Bündel, 106.271 datierte Akten:

```
Akten aelter als 2 Jahre        77,2 %
Buendel mit NUR alten Akten     0 von 300   (0,0 %)
Buendel gemischt              300 von 300   (100,0 %)
```

Heute kann also keine einzige alte Akte verschont werden: jedes Bündel enthält Frisches und
wird deshalb jede Nacht angefasst. Genau das würde eine Altersstufe im Schlüssel ändern.

**Was NICHT trägt: „enthält Frisches" als Vorhersage.** Auf der sauberen Produktmenge
(4.096 Bündel, 54.252 Akten) gekreuzt:

```
Bezug „letzte 90 Tage"     neu geschrieben   unveraendert
  enthaelt Frisches                  2.356          1.654
  nur Altes                             37             49
```

1.654 Bündel mit frischen Akten blieben unangetastet. Der Bezug zum Alter ist also da, aber
er ist kein Automatismus.

⚠ **Eigener Fehlgriff, hier korrigiert.** Die 79,8 % weiter oben stammen aus allen 1,99 Mio
DE-Bekanntmachungen. Ich hatte sie zunächst auf die 54.252 Produktakten übertragen — falsch:
die Produktmenge ist naturgemäss jung, dort liegt der Anteil alter Akten bei 22 %. Für P2
zählt das ARCHIV (1.734.199 Akten), und dort gelten die 77,2 % oben.

#### Was noch fehlt: die eine Zahl

Ein erster Vergleich lief, taugt aber nicht als Urteil: die Aufnahme lag mitten in einem
Archiv-Neuaufbau (601.260 Akten festgehalten, am Ende standen 1.734.199 da). Belastbar ist
daraus nur ein Teilbefund — **von den 652.488 Akten, die zum Aufnahmezeitpunkt existierten,
hat sich danach keine einzige geändert und keine ist verschwunden.**

Das Werkzeug wurde daraufhin zweimal geschärft, beide Male mit Gegenprobe:

- Die Aufnahme wartet nun auf zehn Minuten Ruhe **und** darauf, dass kein bauender Prozess
  läuft. Eine Ruhefrist allein reichte nicht: der Export pausiert zwischen seinen
  Abschnitten länger, als die erste Frist von drei Minuten lang war.
- Der Vergleich meldet einen Neuaufbau (Aktenzahl bewegt sich um mehr als 20 %) und gibt
  dann ausdrücklich KEIN Urteil ab, statt eine schöne Quote zu drucken.
- Das Alter einer Akte kommt aus ihrem jüngsten Ereignis, nicht aus `bis`. Sonst gälte eine
  Akte mit Vertragsende 2023 als alt, auch wenn 2026 ein Zuschlag dazukam — und gerade die
  bewegen sich.

**Nächster Schritt:** Aufnahme nach dem laufenden Export, Vergleich nach dem Nachtlauf.
Erst dann steht die Zahl.

**Abnahme:** eine Zahl, die sagt, wie oft sich Akten älter als zwei Jahre zwischen zwei
vollständigen Läufen ändern. Über 0,1 % fällt P2 ersatzlos weg.

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
