# 05 · Gold — die Kette, und dass sie vollständig ist

> Tor 4. Fällt, wenn **jede** country-fähige Tabelle auch für dieses Land gebaut wird und
> `scripts/pruefe_verdrahtung.py` schweigt.

## Keine „schlanke" Länder-Pipeline ohne Verfallsdatum

`gold.build_at_gold` und `build_ch_gold` waren als schmale Brücken gedacht: „nur die
Felder, die der Export liest". Am 2026-08-13 löste `scripts/build_dach_gold.py` sie ab —
aber die alten Funktionen blieben stehen. Ergebnis: ein AT-Link-Fix landete wochenlang in
einem **toten Zweig** und wirkte nie. Aufgefallen ist es nur, weil ein Test rot wurde.

**Regel:** eine abgelöste Funktion wird gelöscht oder trägt einen Hinweis, der sie als tot
kennzeichnet. Eine Brücke ohne Verfallsdatum wird zur Falle.

## Der Lauf

```bash
python3 scripts/build_dach_gold.py --laender XX --as-of "$(date +%F)"
```

`KETTE` in dieser Datei ist der **Abhängigkeitsgraph**. Der Kommentar hinter jedem Schritt
nennt, wofür sein Ergebnis gebraucht wird — damit man beim Umsortieren sieht, was man
zerreisst. Die kanonische Reihenfolge steht in `govisor/cli.py` (DE-Lauf); wer sie
verändert, verändert sie an **beiden** Stellen.

Wichtige Ankerpunkte der Reihenfolge:

```
build_entities            Basis für alles Käufer-/Gewinner-bezogene
build_dim_cpv(_label)     Vokabular — EU-weit gültig
build_quality             Qualitäts-Flags
  build_review_queue      liest quality
…
build_lead_export         was das Frontend liest — MUSS nach allem Inhaltlichen
  build_lead_text         joint gegen lead_export.lead_id → danach
  build_lead_criteria     dito
  build_lead_requirement  dito
  build_lead_party        dito
```

## ⚠ Die häufigste Fehlerklasse des Projekts

**„Gebaut, aber nicht verdrahtet."** Nicht Denkfehler, sondern korrekte Bausteine, die
niemand aufruft — und **jedes Mal war die Testsuite grün**, weil ein Unit-Test prüft, ob
ein Baustein das Richtige tut, nicht ob ihn jemand benutzt.

Belegte Fälle:

| Fund | Form |
|------|------|
| `build_lead_text` | im DACH-Lauf nie aufgerufen, Datei stand **12 Tage** still |
| `build_lead_lot` | dasselbe, **10 Tage** |
| `dedupe`/`locales` | `country` durchgereicht, nie aktiviert |
| simap `_pick` | Sprachfassungen lagen vor und wurden verworfen |
| `build_at_gold` | Fix landete in einem abgelösten Modul |
| 16 Gold-Tabellen | country-fähiger Builder, im DACH-Lauf nicht aufgerufen |

Die 16 Tabellen sind das lehrreichste Beispiel: `lead_criteria`, `lead_requirement`,
`lead_party`, `value_anchor`, `buyer_stats`, `contractor_stats`, `market_stats`,
`buyer_contractor_history`, `market_opportunity`, `retender_signal`, `cpv_adjacency`,
`region_kpi`, `review_queue`, `dim_cpv_label`, `buyer_recent_awards`, `lead_predecessor`.
Alle waren country-fähig. Probeläufe zeigten echte Zeilen:

```
lead_criteria     AT  22.471 / CH 13.656
value_anchor      AT 228.920 / CH 51.919
lead_party        AT  38.681 / CH 16.462
lead_requirement  AT   2.748 / CH    595
```

## Die Verdrahtungsprüfung

```bash
python3 scripts/pruefe_verdrahtung.py --offen
```

- **Sonde 1 (Frische)**: meldet jede Gold-Datei, die gegenüber dem Lauf **ihres Landes**
  zurückhängt. Schwelle 2 Tage, gemessen: 134 von 142 Dateien lagen darunter, danach
  klaffte eine Lücke bis 4,5 Tage.
- **Sonde 2 (Länderparität)**: meldet jede Tabelle, die es nur in DE gibt.
- **Sonde 4 (Länder)**: meldet jedes Land, das in **Silber** liegt und nicht in Gold
  ankommt. Sonde 1 und 2 sehen nur `data/gold` — ein Land, das es nie dorthin geschafft
  hat, ist für sie unsichtbar. So lagen 326.485 polnische Bekanntmachungen zwei Monate
  lang unbemerkt.
- **Sonde 3 (DE-feste Pfade)**: meldet jedes Skript des Nachtlaufs, das fest
  `data/gold/DE` liest. Sonde 1 und 2 sehen nur die Gold-Ebene — **die Hälfte aller Funde
  sass aber im Verbraucher**: Tabelle sauber je Land gebaut, Exporter liest nur DE.
  Sie parst den Syntaxbaum, damit Docstrings und Kommentare nicht mitzählen.

Sonde 1 deckt seit dem 2026-08-23 auch `web/data` ab. Vorher sah sie nur `data/gold` und
übersah damit die Schicht, die der Nutzer zu sehen bekommt: `firma-profiles.json` war
23 Tage alt, weil sein Erzeuger in **keinem** Lauf steht.

Ausnahmen stehen als **Code im Skript**, nie in einer Textdatei, und
`tests/test_verdrahtung.py` hält sie ehrlich: ohne Begründung, für etwas Gelöschtes oder
für eine längst geschlossene Lücke wird die Suite rot.

⚠ Der ältere **Altersbericht** in `daily_leads.sh` ist eine **handgepflegte Liste von
sechs Eckpfeilern** — genau deshalb hat er `lead_lot` nie gemeldet. Beide bleiben, weil sie
verschiedene Ausfälle sehen: der Altersbericht merkt, wenn der **ganze** Lauf steht (dann
wandert der Bezugspunkt der Sonde mit und sie ist blind); die Sonde merkt, wenn **ein**
Schritt fehlt.

## Die Verdrahtungskarte — wer erzeugt was, und wer liest es

Die Sonden melden, dass etwas **nicht stimmt**. Die Karte sagt, **woran es hängt**:

```bash
python3 scripts/verdrahtungskarte.py lead_lot     # eine Tabelle
python3 scripts/verdrahtungskarte.py --waisen     # nur die auffälligen Fälle
python3 scripts/verdrahtungskarte.py --markdown   # zum Einfügen
```

```
lead_lot
  erzeugt von : build_lead_lot
  gelesen von : govisor/search.py, scripts/export_strategie.py,
                scripts/export_supabase.py, scripts/export_web_leads.py
```

Jeder Fund dieser Sitzung stand darin: `build_lead_lot` lief im DACH-Gold nicht mit,
während vier Verbraucher täglich lasen. Wer vor einem Umbau wissen will, was er zerreisst,
fragt hier — nicht im Kopf.

**Zwei Klassen werden getrennt gemeldet:**

- **Erzeuger ohne Verbraucher** — gebaut, liest niemand. Rechenzeit für nichts.
- **Verbraucher ohne Erzeuger** — gelesen, baut niemand. Läuft ins Leere oder auf einen
  Stand, den niemand auffrischt.

⚠ **Sie wird ERZEUGT, nicht getippt.** Eine von Hand gepflegte Karte verrottet mit dem
ersten Umbau, und dieses Projekt hat an einem Tag gezeigt, wie schnell das geht. Sie liest
den Quelltext und ist damit so aktuell wie er.

⚠ **Ehrlich zur Genauigkeit:** die Karte erkennt Schreibziele über die Muster, die der
Bestand benutzt (`COPY … TO`, `out =`, Schreib-Helfer wie `_write`/`copy_to`). Beim Bauen
hat jedes einzelne davon einmal gefehlt und Tabellen fälschlich als Waisen gemeldet — von
65 falschen Anklagen auf 13 verbliebene, die grösstenteils echt sind (Silber-Tabellen wie
`attributes` haben keinen Gold-Builder). **Wer einen neuen Schreib-Helfer einführt, trägt
ihn in `SCHREIB_HELFER` ein**, sonst sind seine Tabellen plötzlich vaterlos.

## Bewusste Länderlücken sauber begründen

Nicht jede DE-Tabelle muss es überall geben. Der Grund muss die **Quelle** nennen, nicht
den Aufwand — „lohnt sich nicht" ist keine Begründung, sondern eine Vertagung.

Gute Begründungen aus `BEWUSST_NUR_DE`:

- `doe_*` — DÖE ist eine rein deutsche Unterschwellenquelle
- `entity_impressum_beleg` — deutsche Impressumspflicht (§5 DDG), kein AT/CH-Gegenstück
- `entity_merge_map` — Entity-Auflösung ist auf das deutsche Handelsregister getunt
- `document_duplicates` — AT/CH haben 0 Dokument-Dateien (AT hat Dateilisten, aber der Dublettenwall vergleicht Inhalte)
- `lead_region_fill` gilt **nicht** als solche Lücke (s. [Kapitel 07](07-geo-und-regionen.md))

## Halbe Länderlücken benennen

Manche Tabelle **entsteht**, trägt aber nur die halbe Aussage. Das gehört in den Docstring
des Builders, nicht in ein Ticket:

`region_kpi` trägt für AT/CH nur die **Nachfrage**-Seite. Der Kontext kommt aus Destatis
und endet an der deutschen Grenze — gemessen stehen **39 von 40** AT-Regionen und
**23 von 23** CH-Regionen ohne Investitionen, Baubetriebe, Bevölkerung da. Die Spalten
bleiben `NULL` statt `0`; für echten Kontext bräuchte es Statistik Austria bzw. das BFS.

(Die eine gefüllte AT-Zeile ist **kein** Fehljoin, sondern eine österreichische Vergabe
mit Leistungsort Heidelberg. Erst nachsehen, dann urteilen.)

## Die Positivlisten-Falle

`gold._lead_context_sql` liest Attribute über eine **positive WHERE-Liste**. Wer ein neues
Feld ergänzt und den Pfad nicht in die Liste einträgt, baut totes SQL — die Ergänzung ist
syntaktisch korrekt und wirkungslos. Zweimal zugeschlagen; der Kommentar über der Liste
warnt seit dem 2026-08-13 davor.

Ebenso: **jeder Glob auf `attributes` braucht einen Wächter.** DuckDB wirft bei einem Glob
ohne Treffer einen IO-Fehler; ein Land ohne geerntete Attribute bricht sonst mitten im Bau
ab. Rückfall auf eine leere Tabelle mit denselben Spalten.

## Den Link zur Quelle nicht an TED hängen

`documents_url` **nicht** an `ted_url` binden. Für nationale Quellen ist die leer: von
10.877 `atv-`-Vorgängen hatte **null** eine `ted_url`. Die eigene Portalseite steht in
Silber als `portal_url`:

```sql
coalesce(n.ted_url, n.portal_url)      -- und im Kontext: coalesce(ctx.documents_url, nq.portal_url)
```

Das war die Ursache dafür, dass **57 %** der österreichischen Vergaben nicht einmal einen
Link zur Quelle trugen. Nach der Korrektur: 100 %.

⚠ Der Fix gehört in `build_lead_export`, **nicht** in eine länderspezifische Brücke — genau
dort lag er zuerst und wirkte nie (s. oben).

## `_lead_context_sql(cfg, country)` anschliessen

Nimmt das Land als Parameter und liefert Bürgschaft, Nebenangebote, Bindefrist,
Fristuhrzeit und Bieterfragen-Frist aus `attributes`. **Kein zweiter Parser.** Ein neues
Land bekommt sein Vokabular dort eingetragen — und den zugehörigen Pfad **in die
Positivliste** (s. oben), sonst ist der Eintrag wirkungslos.

Gemessen an CH: das Anschliessen hob die Bindefrist von 51 % auf 66 % und die
Bieterfragen-Frist von 0 % auf 45 %.

## Vollständigkeitsprüfung nach dem Bau

Nicht nur „lief durch", sondern:

```bash
python3 -m govisor.cli verify --country XX     # FK-Integrität
python3 scripts/pruefe_verdrahtung.py          # Frische + Parität
```

Und eine Spaltenrunde: welche Gold-Spalten liest der Export **nicht**? Von 22 solchen
Spalten waren die meisten Strukturkram oder konstant (`due_basis` durchgehend
„Angebotsfrist", `timing_implausible` durchgehend `false`) — **eine** trug echte
Information. Diese Runde lohnt sich einmal je Land.

## Ergebnis dieses Kapitels

- `pruefe_verdrahtung.py` schweigt
- `verify` meldet keine FK-Waisen
- jede bewusste Lücke steht mit Quellen-Begründung in `BEWUSST_NUR_DE`
- jede halbe Lücke steht im Docstring ihres Builders
