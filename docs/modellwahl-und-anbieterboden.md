# Modellwahl und Anbieterboden

*Stand 2026-08-23. Gehört zu `govisor/llm.py`, `govisor/kostenbuch.py`,
`govisor/modellkatalog.py`, `govisor/pruefstand.py`, `scripts/kostenbericht.py`,
`scripts/llm_bench.py`, `scripts/llm_qualitaet.py`, `scripts/modellwaechter.py`,
`scripts/modellpruefung.py`.*

Wie wir LLM-Geld sparen, ohne die Analysequalität zu verwetten — und wie beides gemessen
wird statt geglaubt.

---

## Das Problem zerfällt in zwei Hälften

Die Frage „welches Modell ist für uns am effizientesten und wie kommen wir zum günstigsten
Anbieter" klingt nach einer Aufgabe. Sie sind zwei, und sie verhalten sich völlig
verschieden:

| | **Der Weg** (Anbieterboden) | **Das Modell** (Modellwahl) |
|---|---|---|
| Frage | Wer liefert *dasselbe* Modell am billigsten? | Welches Modell taugt für unsere Aufgabe? |
| Qualitätsrisiko | **keines** — identische Gewichte | hoch |
| Messbar durch | Preisvergleich | gepaarten Versuch am eigenen Korpus |
| Automatisierbar | **vollständig** | Messen ja, Umschalten nur mit Riegel |
| Ersparnis | bis 50 % sofort | offen |

Die erste Hälfte ist geschenkt und ist scharfgestellt. Die zweite ist die eigentliche
Arbeit; dafür steht das Werkzeug bereit, die Messung selbst braucht Guthaben.

---

## Hälfte 1: Der Anbieterboden

### Der Befund

OpenRouter führt für **ein** Modell mehrere Endpunkte. Für `google/gemini-2.5-flash`
gemessen am 2026-08-23 (`/api/v1/models/google/gemini-2.5-flash/endpoints`):

| $/Mio ein/aus | Endpunkt | Verfügbarkeit 1 d |
|---|---|---|
| **0,150 / 1,250** | `google-ai-studio/flex` | 100,0 % |
| 0,300 / 2,500 | `google-ai-studio`, `google-vertex/global`, `google-vertex/eu` | 99,3–100 % |
| 0,540 / 4,500 | `google-ai-studio/priority`, `google-vertex/global/priority` | 99,3–100 % |

Gleiches Modell, gleicher Kontext (1.048.576), gleiche Ausgabegrenze (65.535) — **Preisspanne
3,6-fach.**

Ohne Angabe verteilt OpenRouter nach *price-based load balancing*: gewichtet nach dem
inversen Quadrat des Preises. Günstig wird bevorzugt, aber nicht erzwungen. Wir landeten also
regelmäßig auf teureren Endpunkten, ohne dass es irgendwo auffiel.

### Warum `:floor` und nicht `provider.sort`

Naheliegend wäre `{"provider": {"sort": "price"}}`. **Das reicht nicht.** Laut
OpenRouter-Dokumentation sortiert es nur; die Flex-Endpunkte bleiben gesperrt. Die Endung
`:floor` am Modellnamen ist *„a superset of setting provider.sort to price"* — sie sortiert
**und** macht die Flex-Dienstgüte zulässig. Wer nur sortiert, zahlt weiter 0,300.

### Die Falle: anhängen statt voraussetzen

Der erste Entwurf setzte den Boden als Vorgabe in `llm.DEFAULT_MODEL`. Das wäre **in der
Produktion wirkungslos** geblieben, und zwar unbemerkt:

* `scripts/analyse_arbeiter.sh` setzt `OR_MODEL="google/gemini-2.5-flash"` ausdrücklich.
* `scripts/analyze_docs.py` trug denselben Namen noch einmal fest eingebaut.

Die Vorgabe hätte also genau an der Stelle nicht gegriffen, an der das Geld ausgegeben wird —
und im Kostenbuch hätte trotzdem plausibel etwas gestanden. Deshalb gibt es
`llm.mit_boden(modell)`: es **hängt** `:floor` an das an, was tatsächlich gilt, und lässt eine
bereits gesetzte Route (`:nitro`) in Ruhe.

> Dieselbe Fehlerklasse wie „gebaut, nicht verdrahtet": die Mechanik stimmt, sie erreicht nur
> den Ernstfall nicht.

### Die Schalter

| Umgebungsvariable | Vorgabe | Wirkung |
|---|---|---|
| `OR_BODEN` | `an` | `aus` fährt ohne `:floor` — **die Vergleichsgruppe**, ohne die die Ersparnis eine Behauptung bleibt |
| `OR_MODEL` | `google/gemini-2.5-flash` | Modell; der Boden wird angehängt |
| `OR_MAX_PREIS` | *(leer)* | Preisdeckel `„0.30/2.50"` je Mio Token — verbietet teure Endpunkte auch dann, wenn der billige ausfällt |
| `OR_DATENSCHUTZ` | *(leer)* | `deny` schließt speichernde Anbieter aus |

**`OR_MAX_PREIS` ist bewusst nicht vorbelegt.** Ein fest eingebauter Deckel gilt auch für ein
Modell, das jemand später per `OR_MODEL` setzt, und sperrt dann womöglich *jeden* Endpunkt
aus; der Aufruf scheitert mit „no allowed providers" an einer Stelle, an die niemand schaut.

**`OR_DATENSCHUTZ` ebenfalls nicht.** Ob der Flex-Endpunkt unter „speichernd" fällt, sagt die
Schnittstelle nicht — das Feld `data_policy` kam bei allen sieben Endpunkten leer zurück.
Einschalten heißt hier möglicherweise: den halben Preis wieder aufgeben. Das ist eine
Abwägung, keine Vorgabe.

### Was es kostet

Flex ist die **niedrigere Dienstgüte**: langsamer, mehr Warteschlange. Für einen Nachtarbeiter
mit Wachhund und Wiederholung ist das gleichgültig — aber es ist eine Behauptung, bis das
Kostenbuch sie belegt. Latenz und Durchsatz liefert die OpenRouter-Schnittstelle für diese
Endpunkte nicht (beide Felder leer), also bleibt nur die eigene Messung.

---

## Das Kostenbuch

`govisor/kostenbuch.py` schreibt **jeden** LLM-Aufruf mit: `data/llm_kosten.jsonl`, eine
JSON-Zeile je Aufruf.

Möglich wurde das durch eine Eigenschaft, die vorher ungenutzt war: OpenRouter liefert die
abgerechneten Kosten **in der Antwort** (`usage.cost`, dazu
`usage.cost_details.upstream_inference_cost`). Kein Zusatzaufruf, kein Aufpreis, keine
zusätzliche Wartezeit.

| Feld | Inhalt |
|---|---|
| `ts` | Zeitstempel UTC |
| `modell` / `weg` | Modell **ohne** Routing-Endung, Route getrennt (`floor`, `nitro`, `""`) |
| `endpunkt` | wer tatsächlich geantwortet hat (`"Google AI Studio"`) — die einzige Stelle, an der sich prüfen lässt, ob der Boden traf |
| `zweck` / `vorgang` | Anlass und Vergabe-ID |
| `kosten_usd` / `upstream_usd` | abgerechnet / Einkaufspreis |
| `eingabe_token`, `ausgabe_token`, `cache_token`, `sekunden` | Rest |

### Drei Entwurfsentscheidungen, die nicht offensichtlich sind

**1. Modell und Route getrennt.** Stünde `google/gemini-2.5-flash:floor` als Modellname im
Bestand, zerfiele die Historie desselben Modells in zwei Reihen — und der
Vorher-Nachher-Vergleich, um den es beim Boden gerade geht, wäre genau dadurch unmöglich.
`llm.chat()` hält deshalb den **Grundnamen** fest, die Route wandert ins eigene Feld.
`:free` wird *nicht* abgeschnitten: das ist ein anderes Angebot, keine Route.

**2. Es hält nichts an.** Die Bremse ist die Geldwache in `llm._geldwache()` und arbeitet am
Kontostand. Das Buch schreibt nur mit. Eine Bremse muss auch dann greifen, wenn die
Buchhaltung ausfällt — und die Buchhaltung darf nie einen bezahlten Aufruf vernichten. Aus
demselben Grund ist jede Zahlumwandlung im Buch fehlertolerant: ein unerwarteter Wert wird
`null`, keine Ausnahme.

**3. Ein stilles Buch ist schlimmer als keines.** Das Tagesbuch der Geldwache scheiterte
wochenlang lautlos an einem `except: pass`; der Tagesdeckel war wirkungslos und niemand konnte
es sehen. Ein Schreibfehler meldet sich hier **einmal laut** auf stderr und danach nie wieder.

---

## Hälfte 2: Welches Modell — gepaart gemessen

### Warum gepaart

Vergaben unterscheiden sich um ein Vielfaches dessen, was Modelle sich unterscheiden. Wer zwei
Modelle an verschiedenen Vergaben misst, misst die Vergaben. Genau dieser Fehler steckt im
Produktivbestand, und `scripts/llm_qualitaet.py` sagt es selbst: *die Zuteilung war nicht
zufällig* — welches Modell drankam, entschied das Guthaben des jeweiligen Anbieters.

`scripts/llm_bench.py` fährt deshalb **dieselben** Vorgänge durch jedes Modell.

### Der Qualitätsmaßstab, den wir geschenkt bekommen

Wir brauchen keinen gekauften Benchmark und keine handgelabelten Daten, weil die Pipeline sich
selbst prüft: **jede Aussage des Modells wird gegen den Quelltext gegengeprüft, unbelegte
werden verworfen** (Zitat-Verifikation, Ticket #23). Daraus folgen zwei Zahlen, die zusammen
gehören:

* **Punkte** — verifizierte Checklisten-Einträge. Der Ertrag.
* **Verwerfungsquote** — Anteil der Aussagen, deren Zitat nicht wörtlich im Dokument stand.
  Die ehrlichere der beiden: sie misst nicht Fleiß, sondern Genauigkeit. Viele Punkte bei
  hoher Verwerfung heißt **viel behauptet, wenig belegt**.

Dazu seit heute:

* **USD je belegtem Punkt** — erst diese Zahl macht „effizient" messbar. Ein Modell, das 20 %
  mehr findet und dreimal so viel kostet, ist keine Verbesserung.
* **Vorzeichentest** — gewinnt der Kandidat Vorgang für Vorgang, oder schwankt es nur? Bei
  vier Vorgängen ist praktisch jeder Unterschied Rauschen. Ohne diese Spalte lud die alte
  Tabelle zu genau der falschen Schlussfolgerung ein.

⚠ **Nur Modell-Einträge zählen.** Alles mit `parser` (gaeb/xlsx/pdf_fields) stammt aus einem
deterministischen Leser. Bei ~15 % Parser-Anteil verschiebt das jede Rangfolge, wenn man es
mitzählt.

⚠ **Der Titelverteidiger läuft mit.** Die alte Fassung verglich Kandidaten gegen den
*gespeicherten* Bestand. Das mischt zwei Ursachen: seither haben sich Doktyp-Erkennung,
Prompts und Dublettenlogik geändert. Ein Kandidat hätte gewinnen können, weil die **Pipeline**
besser wurde. Heute läuft `google/gemini-2.5-flash` frisch mit, unter identischen Bedingungen.

⚠ **Nach jedem Vorgang gesichert.** Am 2026-08-23 gingen 1,27 $ verloren, weil ein Lauf erst
am Ende schreiben wollte und vorher starb — zweimal am selben Tag. Zwischenstand:
`data/analyse/modellvergleich.json`, Wiederaufnahme mit `--fortsetzen`.

### Der Beförderungsriegel

Der Anbieterwechsel darf **voll automatisch** laufen: gleiches Modell, kein Risiko.

Ein **Modellwechsel** nicht. Ein Kandidat steigt nur auf, wenn er

1. auf **denselben** Vorgängen mehr belegte Punkte findet,
2. die Verwerfungsquote **nicht** verschlechtert,
3. über eine ausreichende Zahl Vorgänge (Vorzeichentest ✓, also p < 0,05 — praktisch ab
   ~10–15 Vorgängen erreichbar),
4. und der Preis je belegtem Punkt die Entscheidung trägt.

Sonst tauschen wir irgendwann still gegen ein Modell, das schneller *behauptet* statt besser
*belegt*. Der Modellvergleich vom 2026-08-18 zeigt genau diesen Effekt: die Modelle, die am
wenigsten finden, erklären am meisten für grün.

---

## Der Kreislauf: täglich schauen, geprüft wechseln

Die Modellwahl ist keine einmalige Entscheidung. Preise ändern sich, Modelle erscheinen und
verschwinden, und ein Modell kann **schlechter werden**, ohne dass es jemand ankündigt.
Deshalb läuft das hier als Kreislauf, und zwar täglich:

```
  ┌─ scripts/modellwaechter.py --pruefen ──────────────── täglich, 0 $ ─┐
  │   Katalog holen · Tagesstand ablegen · mit gestern vergleichen      │
  │   lohnende Kandidaten einreihen · Modellwahl auffrischen            │
  └─────────────────────────────┬───────────────────────────────────────┘
                                ↓
  ┌─ scripts/modellpruefung.py ────────────── täglich, eigener Testtopf ─┐
  │   Vorprüfung (3 Vorgänge) → Hauptprüfung (15) → Urteil               │
  │   Bestandene werden freigegeben                                      │
  └─────────────────────────────┬────────────────────────────────────────┘
                                ↓
  ┌─ data/modellwahl.json ───────────────────────── vor jedem Analyselauf ─┐
  │   `scripts/analyze_docs.py` liest das billigste FREIGEGEBENE Modell    │
  └────────────────────────────────────────────────────────────────────────┘
```

Beide Schritte hängen in `scripts/daily_leads.sh` und dürfen den Lauf **nie** aufhalten.

### Warum täglich und nicht monatlich

Sven, 2026-08-23: *„nicht einmal im monat checken, sondern jeden tag. die preise sind
variable."* Wer im Monatstakt schaut, zahlt im Schnitt zwei Wochen zu viel und erfährt von
einer Abkündigung erst, wenn die Aufrufe scheitern. Der Blick kostet nichts: **ein** HTTP-
Aufruf holt den ganzen Katalog (422 Modelle am 2026-08-23), ohne Token und ohne Guthaben.

### Die Trennung, auf der alles steht

| | Wächter | Prüfstand |
|---|---|---|
| Kosten | 0 $ — reines HTTP | echtes Geld, eigener Topf |
| Häufigkeit | täglich | täglich, höchstens 2 Kandidaten |
| Sagt | „hier hat sich etwas geändert" | „dieses Modell ist besser/schlechter" |
| Entscheidet | **nichts** über Qualität | den Wechsel |

Ein Benchmark im Tagestakt verbrennt Geld für die Bestätigung, dass alles beim Alten ist.
Ein Wächter allein kann nur Preise vergleichen — und Preis ist keine Güte.

---

## Woher die Kandidaten kommen

`/api/v1/models` liefert je Modell `context_length`, `pricing`, `supported_parameters`
und `expiration_date`. Daraus wird die Tauglichkeit **abgeleitet, nicht geraten**:

* **Kontext ≥ 200.000** — `analyze_docs.py` schickt je Doktyp einen Aufruf bis zu einem
  200k-Token-Deckel. Ein Modell mit weniger kann die Aufgabe nicht annehmen, egal wie
  billig. (Genau diese Auswahl war mit mazhs Daten unmöglich: dort war `context_window`
  bei allen 740 Modellen leer.)
* **`structured_outputs`** — die typisierte Extraktion erzwingt ein Schema.

Am 2026-08-23: **243 von 422 Modellen** taugen, **47** sind laut Katalog billiger als unser
Bodenpreis, **40** reißen zusätzlich die Latte von 20 % Ersparnis und stehen in der
Warteschlange. Bei zwei Prüfungen je Tag ist das in drei Wochen abgearbeitet — die
Warteschlange begrenzt sich selbst.

⚠ **Der Katalogpreis ist nicht unser Preis.** `/api/v1/models` nennt den Listenpreis
(0,300), wir zahlen den Bodenpreis (0,150). Verglichen wird deshalb Boden gegen Katalog,
und zwar am **Mischpreis**: unsere Last ist eingabelastig (rund 15:1), und ein Modell nach
der bloßen Summe beider Preise zu wählen würde teure Ausgabe überbewerten. Sobald 50
Buchungen vorliegen, wird das Verhältnis **gemessen** statt geschätzt.

---

## Die Entscheidungsregel

Sven, 2026-08-23: *„für mich steht qualität oben, aber danach kommt direkt der preis.
geschwindigkeit ist nicht wichtig […] sollte mit gemessen werden."* Das steht als Code in
`govisor/pruefstand.py:entscheide()` und nirgends sonst:

| # | Prüfung | Ergebnis |
|---|---|---|
| 1 | **Verwerfungsriegel**: verwirft mehr als der Amtierende (> 2 Punkte) | **durchgefallen**, egal wie billig |
| 2 | signifikant weniger Punkte (Vorzeichentest, p < 0,05) | durchgefallen |
| 3 | signifikant mehr Punkte | **bestanden** — auch wenn teurer |
| 4 | gleichwertig **und** ≥ 20 % billiger | **bestanden** |
| 5 | gleichwertig, kaum billiger | gleichwertig, kein Wechsel |
| — | Geschwindigkeit | gemessen, ausgewiesen, **entscheidet nichts** |

Der Verwerfungsriegel steht ganz oben, und das ist keine Förmlichkeit. Unsere eigene
Messung vom 2026-08-18: die Modelle, die am **wenigsten** fanden, erklärten am **meisten**
für grün. Ein Modell, das flüssig behauptet und selten belegt, sieht in jeder Punktzahl gut
aus und ist trotzdem unbrauchbar.

### Was das Prüfen bezahlbar hält

* **Zwei Stufen.** Vorprüfung über 3 Vorgänge tötet offensichtliche Nieten für ein Fünftel
  des Preises; ihre Messwerte werden in der Hauptprüfung (15 Vorgänge) **weiterverwendet**.
* **Der Amtierende wird einmal gemessen**, nicht je Kandidat. Die Grundlinie liegt fest und
  wird nach 14 Tagen erneuert — die Pipeline ändert sich, also darf die Grundlinie nicht
  ewig gelten.
* **Fester Prüfsatz.** Dieselben Vergaben für jeden Kandidaten, dauerhaft. Ein wechselnder
  Satz würde Kandidaten an verschiedenen Aufgaben messen — genau der Fehler, den der
  gepaarte Aufbau vermeiden soll.
* **Durchgefallene werden nicht erneut geprüft**, solange ihr Preis nicht materiell fällt.
  Sonst prüft der Prüfstand jede Nacht dieselben Nieten.
* **Eigener Testtopf** (`GOVISOR_TEST_USD`, Vorgabe 0,50 $/Tag). Am 2026-08-23 fraß ein
  Versuch das Guthaben des Analyse-Arbeiters auf; danach stand die Produktion, während der
  Versuch weiterlief. Genau dagegen.

---

## Abdriften: die Zeitreihe

```bash
scripts/llm_qualitaet.py --zeitreihe
```

Ein Modell kann sich ändern, ohne dass es jemand ankündigt — Anbieter wechseln
Quantisierung, Endpunkte kommen und gehen. Der Gesamtdurchschnitt zeigt das **nie**: eine
Verschlechterung, die vor drei Wochen begann, verschwindet darin. Die Zeitreihe gruppiert je
Woche und vergleicht den jüngsten Zeitraum mit dem **Median** der vorherigen (nicht dem
Mittelwert — ein Ausreißer soll die Messlatte nicht verschieben). Fällt die Ausbeute unter
85 % oder steigt die Verwerfung um mehr als 5 Punkte, gibt es eine Warnung.

⚠ Grundlage ist `analysiert_am`, das seit dem 2026-08-23 geschrieben wird. Ältere
Datensätze tragen kein Datum und werden **bewusst nicht geschätzt**: eine erfundene
Einordnung sähe wie ein Messwert aus.

---

## Betrieb: drei Rezepte

### 1. Beweisen, dass der Boden wirkt

```bash
scripts/kostenbericht.py --boden
```

Solange nur Zeilen *mit* Boden im Buch stehen, sagt es das und rechnet nicht. Für die
Vergleichsgruppe eine Zeit lang mit `OR_BODEN=aus` fahren, dann erneut auswerten.

Der Preis je Mio Token ist dabei belastbar (der Tarif hängt nicht am Dokument), die Dauer
**nicht** — dafür müssten dieselben Vorgänge über beide Wege laufen.

### 2. Ein neues Modell prüfen

```bash
scripts/llm_bench.py --modelle openai/gpt-5-mini --n 15 --budget-usd 2.00 --fortsetzen
```

### 3. Wofür ging das Geld

```bash
scripts/kostenbericht.py --nach zweck
scripts/kostenbericht.py --nach modell,weg,endpunkt --seit 2026-08-23
scripts/llm_qualitaet.py
```

### 4. Was macht der Prüfstand gerade

```bash
scripts/modellpruefung.py --stand
```

### 5. Ein Modell von Hand freigeben oder sperren

```bash
scripts/modellwaechter.py --freigeben openai/gpt-5-mini --grund "Prüfstand 2026-09-01, p=0.01"
```

Freigaben stehen in `data/modellfreigabe.json`, die Warteschlange in `data/pruefstand.json`.
Ein Eintrag dort von Hand zu löschen setzt einen Kandidaten zurück.

---

## Was NICHT gebaut ist

* **Notmodell am Tagesdeckel.** imprests `action_at_limit: 'fallback'` — statt zu stoppen
  auf ein vorher geprüftes, billigeres Modell fallen. Der Unterbau steht jetzt (Freigaben +
  Mischpreis), es fehlt nur die Verdrahtung in `llm._geldwache()`.
* **Ein zweiter Anbieter neben OpenRouter.** Gemessen lohnt es nicht: OpenRouter berechnet
  **keinen Aufschlag je Token** (unsere eigene Buchung: `kosten_usd == upstream_usd`,
  Differenz 0), und Googles Direktpreis für Gemini 2.5 Flash ist mit 0,15/1,25 im Batch- und
  Flex-Tarif exakt das, was wir über OpenRouter zahlen. Ein Direktkonto spart nur die
  Aufladegebühr von 5,5 % — gegen ein zweites Konto, einen zweiten Schlüssel und einen
  zweiten Ausfallweg.
* **`scripts/analyse_arbeiter.sh` liest die Wahl nicht selbst.** Es setzt weiter
  `OR_MODEL="${OR_MODEL:-google/gemini-2.5-flash}"`; die Wahl greift trotzdem, weil
  `analyze_docs.py` `data/modellwahl.json` **vor** `OR_MODEL` auswertet. Sauberer wäre
  `OR_MODEL=$(scripts/modellwaechter.py --waehlen 2>/dev/null)` im Arbeiter — das braucht
  einen Moment, in dem er nicht läuft (bash liest Skripte häppchenweise).
* **`scripts/succession_llm.py` umgeht die Geldwache.** Es postet direkt mit `requests` — ohne
  Reserve, Lauf- und Tagesdeckel, ohne Kostenbuch. Als Pilot mit `LIMIT` begrenzt; `LIMIT=0`
  würde ungebremst Geld ausgeben. Den Anbieterboden hat es bekommen, den Umbau auf
  `llm.chat()` nicht.

## Zwei Befunde aus dem ersten Echtbetrieb (2026-08-24)

### Formatfehler sind kein Qualitätsurteil

`docextract.extract` erzwingt **kein** Schema — es bittet im Prompt um JSON, streift
Code-Zäune ab und wiederholt einmal. Gemessen an vier Antwortformen:

| Antwort des Modells | Ergebnis |
|---|---|
| sauberes JSON | geparst |
| in ```` ```json ```` gewickelt | geparst |
| **JSON mit Prosa drumherum** | **`parse_error`** |
| gar kein JSON | `parse_error` |

Ein `parse_error` liefert nach oben **0 Punkte und 0 verworfene Aussagen** — das sieht aus
wie „findet nichts bei perfekter Genauigkeit". Ohne Gegenmaßnahme wäre ein Modell, das
unsere Aufgabe beherrscht und nur höflich drumherum redet, als `durchgefallen` abgestempelt
und **nie wieder geprüft** worden. Besonders heikel, weil wir Kandidaten zwar nach
`structured_outputs` filtern, die Fähigkeit aber gar nicht nutzen.

Deshalb zählt `analyze_notice` jetzt `llm_aufrufe` und `formatfehler`, und im Prüfstand
steht ein **Formatriegel vor allen Qualitätsregeln**: über 20 % unlesbare Antworten ergeben
den Status `formatproblem` statt eines Urteils. Wiederholt wird nicht automatisch (es
scheiterte identisch und kostete Geld); die Abhilfe steht im Befund: erzwungenes Schema.

### Das Kostenbuch kann nicht vollständig sein — also weist es seine Lücke aus

Am 2026-08-24 fehlten 0,0208 $ zwischen Buch und Abrechnung. Ursache zum Teil gefunden:
**leere 200er wurden nicht gebucht**, obwohl OpenRouter sie abrechnet. Das ist behoben
(`leer: true` im Buch). Der Rest ist prinzipiell nicht buchbar — bei einem Client-Timeout
wurde die Anfrage oben verarbeitet und abgerechnet, ohne dass wir je eine Antwort sahen.

```bash
scripts/kostenbericht.py --abgleich      # Buch gegen OpenRouters total_usage
scripts/kostenbericht.py --marke-neu     # Messpunkt neu setzen
```

⚠ Der Abgleich rechnet mit **`total_usage`**, nicht mit dem Kontostand. Die erste Fassung
nahm die Kontostandsdifferenz — die wird durch jede **Aufladung** sinnlos, und genau die
stand unmittelbar bevor. `total_usage` steigt nur und kennt keine Aufladung.

## Der Trockenlauf

```bash
scripts/modellpruefung.py --trocken
```

Fährt den **kompletten** Ablauf mit echtem Prüfsatz und echten Dokumenten — Doktyp-
Erkennung, Parser-Schiene, Dublettenlogik, Textdeckel — und befragt nur kein Modell.
Deshalb ist die Eingabeseite **exakt** und nicht geschätzt; die Ausgabemenge wird aus dem
Kostenbuch hochgerechnet und als Schätzung ausgewiesen. Er arbeitet auf einer Kopie des
Zustands und gibt nichts aus.

Er beantwortet drei Fragen vor dem ersten bezahlten Lauf: *wie viele Aufrufe werden das*,
*was kostet der Abend*, und — die wichtigste — *taugen die Prüfvergaben überhaupt, zwei
Modelle zu unterscheiden?*

Am 2026-08-24 fand er auf Anhieb drei Dinge, die kein Test gesehen hatte:

1. **Drei von fünfzehn Prüfvergaben waren taub.** Je ein einziges Dokument, alle drei
   dieselbe Russland-Sanktions-Eigenerklärung (gleiche Prüfsumme), Doktyp
   `eigenerklaerung` — den kennt `docextract` gar nicht. Kein Extraktionsaufruf, beide
   Modelle null Punkte, im Vorzeichentest ein Unentschieden, das herausfällt. Die
   wirksame Stichprobe wäre still unter das Mindestmaß gerutscht. `pruefsatz()` verlangt
   jetzt mindestens einen extrahierbaren Doktyp.
2. **Der günstigste Kandidat der Warteschlange war nicht bestellbar.**
   `inclusionai/ling-2.6-flash` steht im Katalog und hat **null Endpunkte**. Er hätte
   einen der zwei Tagesplätze verbraucht, an jedem Aufruf scheitern und als
   `durchgefallen` enden müssen — ein Qualitätsurteil über ein nie gesehenes Modell.
   Jetzt: Status `nicht_lieferbar`, kein Urteil.
3. **Und beim Beheben von (2) gleich der nächste:** `bodenpreis()` liefert `None` sowohl
   bei „niemand liefert das" als auch bei einem **Netzfehler**. Wer beides gleich
   behandelt, schreibt bei einem Aussetzer die halbe Warteschlange ab. Gegenprobe ist
   jetzt der Amtierende — er hat garantiert Endpunkte.

Die Vorschau für den ersten echten Lauf (Stand 2026-08-24): 15 Prüfvergaben, 59 Aufrufe,
430.058 Token Eingabe. Grundlinie **0,4694 $**, ein Kandidat wie `nex-agi/nex-n2-mini`
0,0086 $ für die Vorprüfung und 0,0431 $ für den vollen Satz. Der Trockenlauf warnt selbst,
dass die Grundlinie den Tagestopf von 0,50 $ fast ausfüllt.

## Der erste bezahlte Lauf (2026-08-24, 0,62 $)

Grundlinie über 15 Vergaben: **0,6073 $**, 41,0 belegte Punkte je Vergabe im Mittel. Der
Trockenlauf hatte 0,4694 $ vorhergesagt — 29 % daneben, weil er die Ausgabemenge aus nur
vier Buchungen hochrechnete. Die Größenordnung stimmte.

Der erste echte Kandidat, `nex-agi/nex-n2-mini`, hat drei Dinge gezeigt, die keine Attrappe
hätte zeigen können:

**1. Ein Modell kann davonlaufen.** Ein einziger Aufruf erzeugte **65.536 Ausgabe-Token** —
exakt die Obergrenze des Endpunkts — und brauchte dafür **761 Sekunden**. Der Amtierende
liegt bei 775 Token und 3,7 s im Median. Wir setzten bis dahin **kein `max_tokens`**.

**2. Der `timeout` von `requests` schützt davor nicht.** Er misst die Pause *zwischen*
Bytes, nicht die Gesamtdauer; die Gegenstelle hält die Verbindung mit Füllbytes offen. Der
761-Sekunden-Aufruf lief mit `timeout=120` durch. Es braucht eine echte Uhr
(`llm.frist()`), die den Faden liegenlässt statt auf ihn zu warten.

**3. Und das Urteil war falsch.** Zwei von drei Vorgängen rissen die Frist, der dritte ergab
null Punkte — dort hatte aber auch der Amtierende null. Es lag also **kein einziger**
verwertbarer Vergleich vor, und der Prüfstand meldete trotzdem „durchgefallen: findet nur
0,0 statt 41,0 Punkte". Ein Qualitätsurteil über Antworten, die nie angekommen sind.

Jetzt steht ein **Fristriegel ganz vorn** in `entscheide()` — noch vor der Mindestmenge,
denn ein Kandidat, der in die Frist läuft, hat zwangsläufig zu wenige gepaarte Vorgänge und
wäre sonst als „zu wenig Daten" in der Schlange geblieben, um morgen wieder Zeit zu
verbrennen. Status: `zu_langsam`, kein Qualitätsurteil.

| Grenze | Wert | wogegen |
|---|---|---|
| `OR_MAX_TOKENS` | 56.000 | Davonlaufende Ausgabe (über allem Legitimen: Maximum 50.964) |
| `OR_FRIST` | 600 s | Hänger in der Produktion (Maximum legitim: 185 s) |
| `KANDIDAT_FRIST` | 240 s | Hängender Aufruf eines Kandidaten |
| `ZEIT_FAKTOR` | 4× | Vorgang, der insgesamt zu lange braucht |

## Fallen, die schon zugeschlagen haben

1. **`sort: "price"` statt `:floor`** — sortiert nur, erreicht Flex nie. Zahlt weiter 0,300.
2. **Boden als Vorgabe statt als Anhang** — greift genau dort nicht, wo das Geld ausgegeben
   wird, weil Arbeiter und Skript den Modellnamen selbst setzen.
3. **Route im Modellnamen mitführen** — zerschneidet die Historie desselben Modells.
4. **Zahlumwandlung außerhalb des Schutzes** — hätte einen erfolgreichen, *bezahlten* Aufruf
   in eine Ausnahme verwandelt. Buchhaltung darf nie die Ware vernichten, die sie verbucht.
5. **Import ohne Wurzelpfad** — `python scripts/x.py` setzt `sys.path[0]` auf `scripts/`.
   `scripts/succession_llm.py` hatte keinen und starb sofort am neuen Import.
6. **Zeilenzahl als Marke im Kostenbuch** — der Analyse-Arbeiter schreibt parallel hinein.
   Nur eine Byte-Marke plus Filter auf `zweck` ist richtig.
7. **`.replace(",", ".")` auf einen ganzen Satz** — macht aus „422 Modelle, davon 243
   tauglich" ein „422 Modelle. davon". Tausenderpunkte gehören in einen Zahlenformatierer.
8. **Katalogpreis gegen Bodenpreis vergleichen** — meldet jedes zweite Modell fälschlich
   als billiger. Boden gegen Katalog, und am Mischpreis.
9. **Zwei Kopien der bezahlten Schleife** — Handbetrieb und Automatik liefen fast
   auseinander. `pruefstand.messe_reihe()` ist die einzige; beide rufen dorthin.
10. **15:1 statt 1,33:1 beim Token-Verhältnis** — geschätzt statt gemessen, daneben um den
    Faktor 11. Unsere Kosten liegen zu **86 % bei der Ausgabe**, weil die Extraktion die
    Belegzitate mit zurückgibt. Damit ist jeder Eingabe-Hebel (Prompt-Caching!) auf 14 %
    gedeckelt — die Rangfolge der Kandidaten hing daran.
11. **Unlesbare Antwort als Qualitätsurteil verbucht** — siehe oben, Formatriegel.
12. **Abgleich über den Kontostand** — bricht bei der ersten Aufladung. `total_usage`.
13. **Stellschrauben als Vorgabewerte in der Signatur** (`min_n: int = MIN_N`) — beim
    Import eingefroren; ein späteres `pruefstand.MIN_N = 3` bleibt wirkungslos. Ein Modul,
    dessen Regler nach dem Laden nichts mehr tun, sieht einstellbar aus und ist es nicht.
14. **Prüfvergaben ohne extrahierbaren Doktyp** — siehe Trockenlauf.
15. **Katalogeintrag mit null Endpunkten** als Qualitätsmangel verbucht — siehe Trockenlauf.
16. **Kein `max_tokens`** — ein Modell schrieb 65.536 Token in einem Aufruf.
17. **`requests`-Timeout für eine Gesamtfrist gehalten** — er misst Pausen zwischen Bytes.
18. **Fristabbruch als Qualitätsurteil** verbucht, und der Riegel dagegen zuerst hinter der
    Mindestmengenprüfung — die immer zuerst gegriffen hätte.
