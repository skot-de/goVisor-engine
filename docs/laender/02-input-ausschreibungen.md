# 02 · Input Ausschreibungen — Bronze, Silber, Parser

> Tor 2. Fällt, wenn Silber gebaut ist, die Feldabdeckung **je Quelle** gemessen wurde
> und die Bekanntmachungs-IDs kanonisch sind.

## Der Weg

```
Bronze   Originalformat, verlustfrei, nach Land gefiltert
         data/raw*/…      XML (TED) · JSONL (simap) · JSON (DÖE, atverg)
   ↓     ein Parser je Quelle, ein `schema_gen`-Wert
Silber   normalisierte Parquet-Tabellen, KEIN JSON
         data/silver/<LAND>/<tabelle>/year=<jjjj>/*.parquet
   ↓     govisor/gold.py
Gold     abgeleitet und kuratiert  →  Kapitel 05
```

**Bronze wird nie überschrieben und nie gefiltert.** Was man heute für irrelevant hält,
ist die Kennzahl von übermorgen. Unbekanntes geht nach `attributes`, Zweifelsfälle in die
`review`-Queue.

## Ingest-Befehle

```bash
python3 -m govisor.cli ingest        --country XX   # TED-Monatspakete
python3 -m govisor.cli silver        --country XX   # Bronze → Parquet
python3 -m govisor.cli ingest-simap  --country CH --silver
python3 -m govisor.cli ingest-atverg --country AT --silver
python3 -m govisor.cli ingest-doe                   # DE, unterschwellig
```

`--max-pages 0 --silber` baut **nur** Silber aus vorhandenem Bronze, ohne neu zu laden.
Das ist der Befehl, den man nach einer Parser-Änderung braucht.

## `schema_gen` — eine Zeile pro Quellformat

Jede Bekanntmachung trägt, aus welchem Format sie stammt. Ohne dieses Feld sind alle
späteren Messungen wertlos, weil sich Quellen dramatisch unterscheiden:

| Land | `schema_gen` | Bedeutung |
|------|--------------|-----------|
| DE | `legacy` | TED_EXPORT, 1,15 Mio |
| DE | `eforms` | eForms, 0,43 Mio |
| DE | `text` | Vor-XML-Textformat, 0,25 Mio, cp1252-Fallback |
| DE | `ojs` | INTERNAL_OJS, OPOCE-Altformat (u. a. 2008-05) |
| DE | `doe` | oeffentlichevergabe.de, unterschwellig |
| AT | `atverg` | offenevergaben.at |
| CH | `simap` | simap.ch |

**Quellen niemals zusammen zitieren.** Gemessen: TED liefert 43,5 % reiche Beschreibungen
bei Ø 1,68 Losen, DÖE nur 20,8 % bei Ø 1,00 — der `eforms-sdk-0.1`-Dialekt von DÖE kennt
gar keine Losstruktur. Eine gemischte Zahl beschreibt keinen der beiden Bestände.

## Die Feldabdeckung MUSS je Quelle gemessen werden

```sql
SELECT schema_gen, count(*) n,
       count(submission_deadline) mit_frist,
       round(100.0*count(submission_deadline)/count(*)) pct
FROM read_parquet('data/silver/XX/notices/**/*.parquet')
WHERE notice_kind IN ('cn','pin')
GROUP BY 1 ORDER BY 2 DESC
```

Gemessenes DACH-Beispiel (2026-08-23), Frist je Quelle:

```
DE  legacy 67 %   doe 95 %   eforms 79 %   text 0 %
AT  atverg 72 %   legacy 54 %   eforms 65 %   text 0 %
CH  legacy 98 %   eforms 98 %   simap 100 %
```

`text` bei 0 % ist kein Fehler: das Vor-XML-Textformat kennt das Feld nicht.

⚠ **Wenn eine Kennzahl in Gold dünn ist, hier nachsehen, bevor man den Builder verdächtigt.**
Umgekehrt gilt aber auch: wenn Silber 72 % trägt und Gold 7 %, liegt der Fehler *nicht* an
der Quelle. Genau so gefunden bei der österreichischen Frist.

## Bekanntmachungs-IDs kanonisieren

Zwei Formate für dieselbe Bekanntmachung sind ein stiller Datenverlust: beim Monatswechsel
ersetzt das Archiv den Live-Stand, und alle Gold-Zeilen auf der Altform verwaisen.

`schema.normalize_notice_id` (`^0*(\d+)[-_](\d{4})$` → `\1_\2`) hängt an **beiden**
Silber-Pfaden (Archiv und Live). Wer einen neuen Ingest-Pfad baut, hängt sie dort auch ein.

**Bewusst NICHT normalisiert**, und das ist wichtig:

- der TED-öffentliche `publication_number`-Raum (Bindestrich ist dort kanonisch und steckt
  in Award-Link-Joins und TED-URLs)
- fremde Namensräume wie DÖE (UUIDs, reine Zahlen) — sie matchen das Muster nicht und
  würden sonst mit TED kollidieren

Regressionswächter: `tests/test_plumbing.py::test_silver_gold_notice_ids_are_canonical`.

## Sprachfassungen — der Fund, den man leicht verschenkt

Nationale Quellen liefern Titel und Beschreibung oft in **mehreren Amtssprachen im selben
Satz**. Wer den Knoten mit einer „nimm die erste"-Funktion abfrühstückt, wirft das weg.

Gemessen an simap.ch (2026-08-23): **10.139 von 32.592 Sätzen (31 %)** tragen den Titel in
mehr als einer Amtssprache, meist de+fr. Vor der Korrektur bekam **kein einziger**
Schweizer Lead eine Sprachwahl — die 164 mehrsprachigen CH-Leads stammten ausnahmslos aus
TED.

Die Fassungen gehören nach `notice_text` (Silber) → `lead_text` (Gold) → Frontend.

**Drei Fallen, alle real zugeschlagen:**

1. **Leere Sprachen zählen nicht.** Die Quelle liefert unbelegte Sprachen als `null`
   **mit Schlüssel**. Wer die Schlüssel zählt statt die Werte, meldet vier Sprachen und
   liefert eine.
2. **Mehrere Knoten zusammenlegen, nicht den ersten nehmen.** Bei simap sind 3.511 Sätze
   **nur** in `summary.title` mehrsprachig, umgekehrt kein einziger. Ein `or` zwischen
   beiden hätte sie stillschweigend auf eine Sprache reduziert. Das Zusammenlegen ist
   belegt, nicht geraten: wo beide Knoten dieselbe Sprache führen, stimmen sie in
   **39.533 von 39.533** Fällen wörtlich überein.
3. **`{**a, **b}` kippt die Sache.** Beide Knoten führen die unbelegten Sprachen als
   `null` mit Schlüssel, also überschreibt das `"fr": null` des einen das gefüllte `"fr"`
   des anderen. Beim ersten Versuch blieb die Ausbeute deshalb **exakt gleich** — der
   Merge lief und brachte nichts. Nur gefüllte Werte zusammenlegen.

Ausserdem: **eine einzige Fassung ist keine Sprachwahl**, sondern die Sprache der
Veröffentlichung. Nur ausgeben, wenn es wirklich eine Wahl gibt — sonst gaukelt die
Oberfläche eine Auswahl vor.

⚠ Und: `cpv_label` ist die übersetzte CPV-Kategorie, **keine** Fassung des Dokuments. Sie
steht in 24 Sprachen auch dann da, wenn es nur EINEN Titel gibt. Ungefiltert bekämen
gemessen 554 Leads eine Sprachwahl vorgegaukelt — mehr als die 76, die wirklich eine haben.

## Zuschläge sind die zweite Hälfte des Inputs

Es ist verführerisch, nur Ausschreibungen (`cn`/`pin`) zu holen — das ist die Lead-Sicht.
Ohne **Zuschläge** (`can`) fehlt aber die halbe Analytik: Nachfolge-Ketten, Amtsinhaber,
`value_anchor`, Marktkennzahlen, die Zuschlagsphase im Frontend.

Gemessener Bestand (2026-08-23):

```
DE  814.142 Zuschläge von 2.262.483 Bekanntmachungen
AT  228.920 von   420.311
CH   51.919 von   121.375
```

⚠ Bei den Dubletten und beim Marktpuls braucht es deshalb `--alle-arten`: das ist die
**Veröffentlichungs**-Sicht statt der Lead-Sicht. Gemessen 2026-08-13: von 4.345
AT-Treffern, die nur sie fanden, waren **3.403 Zuschläge**; in CH 2.385 von 2.695.

## Was, wenn das Land kein CPV führt?

Oberschwellig ist CPV Pflicht. Unterschwellig nicht: es gibt Quellen ohne jede
CPV-Kennung, und dann greift kein einziger Branchenfilter.

Für Deutschland gibt es dafür den **Kategorie-Wasserfall** (`govisor/kategorie.py` →
`lead_kategorie.parquet`), der aus Titel und Vokabular ableitet, was die Quelle nicht sagt.
Er liest DE-Dubletten und deutsches Vokabular und ist deshalb bewusst DE-only
([Kapitel 05](05-gold-kette.md)).

**Für ein neues Land ohne CPV in der Unterschwelle:** entweder ein eigenes Vokabular bauen
oder die betroffenen Leads ehrlich als „ohne Branche" führen. Was **nicht** geht: sie
stillschweigend in eine Restkategorie schieben — dann findet sie niemand und alle
Branchenzahlen des Landes sind zu klein.

## Fristzeitpunkt und Zeitzone

`deadline_time` ist dünn (DE 13 %, AT 2 %, CH 10 %) und trägt eine **Uhrzeit ohne Zone**.
eForms stempelt einen Offset (`2024-07-01+02:00`), den der Parser abstreift.

Innerhalb von MEZ fällt das nicht auf. Bei einem Land in WEZ (Portugal, Irland) oder OEZ
(Finnland, Bulgarien, Griechenland) ist eine Frist „10:00" um ein bis zwei Stunden falsch —
und zwar genau dann, wenn es zählt: bei der Erinnerung kurz vor Abgabe.

**Für ein neues Land ausserhalb MEZ: entscheiden, ob die Uhrzeit in Landeszeit oder in
UTC geführt wird**, und die Entscheidung im Feld kenntlich machen. Ein Zeitpunkt ohne Zone
ist keine Angabe, sondern eine Vermutung.

## Attribute — der Auffangkorb, der später Gold wird

Alles, was der Parser nicht typisiert kennt, geht nach `attributes` (`notice_id`, `path`,
`value`). Das ist kein Abstellgleis: vier Stufe-1-Kennzahlen (Vergaberegime, Käufertyp,
Käufer-Aktivität, Unterlagen-Link) wurden später **in einem Durchlauf** daraus gelesen
statt in 2,5 Stunden Voll-Reparse.

Wer eine neue Quelle baut: lieber zu viel nach `attributes` als zu wenig.

## Schema-Anpassungen

Neue Silber-Spalten gehören in `govisor/model.py` (`TABLES`). Der Writer baut die
Arrow-Tabelle **gegen dieses Schema**:

```python
arrow = pa.Table.from_pylist(rows, schema=model.TABLES[table])
```

⚠ Eine Zeile mit einem Schlüssel, den das Schema nicht kennt, schreibt gegen eine Spalte,
die es nicht gibt. Konkret zugeschlagen: `year` in den `notice_text`-Zeilen — das Jahr
kommt aus der Partition (`year=…/`), nicht aus der Zeile.

## Ergebnis dieses Kapitels

- `data/silver/<LAND>/` existiert mit allen Tabellen
- eine Tabelle „Feldabdeckung je `schema_gen`" ist gemessen und abgelegt
- IDs sind kanonisch (Test grün)
- Sprachfassungen sind entweder da oder es ist belegt, dass die Quelle nur eine führt
