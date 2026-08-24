# 12 · Fallenkatalog

> Jede Falle hier hat einmal Zeit gekostet. Die Spalte „gemessen" ist der Beleg — ohne sie
> wäre es Folklore.

## A · Fallen, die wie Erfolg aussehen

| # | Falle | Woran man es merkt | Gemessen |
|---|-------|--------------------|----------|
| A1 | **Gebaut, aber nicht verdrahtet** | Datei ist alt, Suite grün | `build_lead_text` 12 Tage, `build_lead_lot` 10 Tage still |
| A2 | **Parameter durchgereicht, nie gesetzt** | Funktion nimmt `country`, benutzt es aber nur für Pfade | `dedupe` lief für AT/CH mit DE-Rechtsformen |
| A3 | **Fix im toten Zweig** | Änderung wirkt nicht, Code ist korrekt | AT-Link-Fix in `build_at_gold`, seit 13.08. abgelöst |
| A4 | **Positivliste** | Ergänzung ist syntaktisch korrekt und wirkungslos | `_lead_context_sql` WHERE-Liste, zweimal |
| A5 | **Leeres Feld = „Quelle gibt nichts her"** | niemand fragt nach | AT Bindefrist/Bürgschaft/Lose je 0 %, 6 Wochen lang |
| A6 | **Nominell gefüllt, faktisch wertlos** | 79 % Abdeckung, eine einzige Ausprägung | alle 3.856 CH-Regionen hiessen „Schweiz/Suisse/Svizzera" |
| A7 | **„Alle Schritte grün"** | Lauf meldet Erfolg, Ergebnis ist alt | Anforderungs-Signale aus einem Index vom 31. Juli |
| A9 | **Registry-Eintrag für Code gehalten** | `uk-fts`/`fr-decp` stehen mit Namen, Format und Abdeckung da — und haben NULL Zeilen Code. `candidate` heisst recherchiert. |
| A8 | **Feld misst etwas anderes als sein Name** | `has_documents` = „Quelle bewirbt", nicht „wir haben"; DE zeigt „unknown" bei 7.781 indizierten Vorgängen, CH „offen" bei null |
| A10 | **Statusmeldung als Befund gelesen** | Ein Abrufer meldet „keine Datei"; niemand fragt, ob er an der richtigen Stelle gesucht hat. Der Fehler wirft keine Ausnahme und sieht im Bericht wie erledigte Arbeit aus. | 2026-08-24: fünf Abrufer geprüft, fünf Vermerke falsch, 433 Vorgänge — s. [Kapitel 03](03-input-dokumente.md) |

## B · Fallen beim Zusammenführen von Ländern

| # | Falle | Warum sie beisst | Gemessen |
|---|-------|------------------|----------|
| B1 | **`union_by_name` auf fachlichem Schlüssel** | letzter Treffer gewinnt im Wörterbuch | `market_opportunity` nach `cpv4`: CH-Zahlen hätten DE ersetzt |
| B2 | **DACH-Summe statt je Land** | beantwortet keine Marktfrage und verdeckt beide | Strategie-Ansicht war komplett deutsch |
| B3 | **Wächter fragt nach DE** | fällt DE aus, sind AT/CH mit abgeschaltet | `_FILL = {G}/lead_region_fill.parquet` |
| B4 | **Silber-Glob DE-fest** | mitten in einem sonst länderfähigen Export | `ATTR` → Angebotsaufwand AT/CH genau 0 % |
| B5 | **Zwei Schichten derselben Annahme** | die zweite verschluckt die Reparatur der ersten | `region_ableiten` DE-only **und** Export DE-only |
| B6 | **Glob ins Leere** | DuckDB wirft einen Laufzeitfehler, kein leeres Ergebnis | CH hat keine `award_criteria` |
| B7 | **Namenskollision über Grenzen** | 22 Käufernamen in mehr als einem Land | trifft 463 von 117.241 Leads |
| B8 | **PLZ-Kollision** | AT und CH sind beide 4-stellig | 1010 = Wien AT / Lausanne CH |
| B9 | **Deckel gilt je Branche statt je Land** | drei Länder teilen sich einen Deckel | `CAP = 120`: deutscher Nutzer sähe 196 statt 379 Zuschlägen |
| B10 | **Hartkodierter Wert sieht aus wie ein Feld** | Quellen umgestellt, Ausgabe nicht | `"land": "DE"` mitten im Ausgabe-Aufbau |
| B11 | **Grenzgänger doppelt im Index** | Identität wird je Land eigenständig gebildet | ACP IT Solutions mit 4 Einträgen; Namensdubletten 134 → 868 |
| B12 | **Entartete Kennung verschmilzt Fremdes** | Platzhalter als Gleichheitsbeleg | 29 von 1.722 grenzüberschreitenden `identity_id` sind `solo:id:.` / `N/A` |
| B13 | **Firmen umgestellt, ihre Regionen nicht** | halbe Umstellung, sieht fertig aus | `clean_nuts` verlangte `len==3 and startswith('DE')` |

## C · Fallen bei Namen und Kennungen

| # | Falle | Gemessen |
|---|-------|----------|
| C1 | **Dachkennung** — eine ID, viele Stellen | `9110027589349` = ÖGK Wien + Steiermark + Kärnten; `FN92191a` = 60 ASFINAG-Namen |
| C2 | **Müllkennung** | „0" bei 510 verschiedenen Käufern, „1" bei 178, „AT" bei 133 |
| C3 | **Rechtsform-Reihenfolge** | „gesellschaft mbh" muss vor „ges.m.b.h." stehen, sonst bleibt „gesellschaft" stehen |
| C4 | **Verschiedene Kennungssysteme je Quelle** | TED meldet GLN, atverg Firmenbuch — für dieselbe Vergabe |
| C5 | **Fuzzy-Matching auf Namen** | Schwelle 0.7 → ~24 % Fehl-Merges bei Ertrag 1.428. Verworfen. |
| C6 | **Sperrliste als Teilzeichenkette** | `'land '` traf „Deutschland GmbH" — 211 Grossfirmen unauffindbar |
| C7 | **CPV-4 fürs Matching** | Elektriker bekam Aufzüge und Heizung als „hoch"; CPV-6 ist die Ebene |

## D · Fallen bei Orten und Regionen

| # | Falle | Gemessen |
|---|-------|----------|
| D1 | **NUTS-Ebene ist nicht überall dieselbe** | DE 3 / AT 4 / CH 5 Stellen |
| D2 | **Behördendeutsch als Ortsname** | „stadt" in AT: 46 von 80 Widersprüchen |
| D3 | **Teilzeichenkette statt Wortfolge** | Widerspruch stieg 8,8 % → 21,7 % („senden" in „Wiesendendorf") |
| D4 | **Kürzester Treffer gewinnt** | „Stadt Neustadt am Rübenberge" → „neustadt" in Thüringen |
| D5 | **Vorsilbe auf der falschen Seite geschnitten** | CH: 646 von 4.520 Zeilen erkannt, vier grösste Kantone fielen aus |
| D6 | **Englische geonames-Dubletten** | „Bavaria" neben „Bayern" — überspringen, nicht übersetzen |
| D7 | **Sitz ≠ Leistungsort** | 88 % der AT-Ableitungen zeigen auf Wien (ÖBB, ASFINAG) |
| D8 | **Bundesweite Vergaben fallen aus dem Filter** | 4.144 DE-Leads, Regel war doppelt implementiert |
| D9 | **Quelle liefert nationale Kürzel statt NUTS** | simap: `ZH`/`VD`/`BE` roh in `performance_nuts`; 4.850 Zuschläge ohne Region, `BE` = Bern **oder Belgien** |
| D10 | **Regionsfilter je Verbraucher statt an der Quelle** | dieselbe DE-Annahme steckte in vier Exportern; Fix gehört in den Parser |

## E · Fallen bei Sprachen

| # | Falle | Gemessen |
|---|-------|----------|
| E1 | **Schlüssel zählen statt Werte** | Quelle liefert unbelegte Sprachen als `null` mit Schlüssel |
| E2 | **`{**a, **b}` kippt gefüllte Werte** | Merge lief, Ausbeute blieb **exakt gleich** |
| E3 | **Nur den ersten Knoten nehmen** | 3.511 Sätze sind nur in `summary` mehrsprachig |
| E4 | **`cpv_label` für eine Fassung halten** | 554 Leads bekämen eine Sprachwahl vorgegaukelt statt 76 |
| E5 | **Eine Fassung ist keine Wahl** | sonst zeigt die Oberfläche einen Umschalter mit einem Knopf |

## F · Fallen beim Messen und Testen

| # | Falle | Gemessen |
|---|-------|----------|
| F1 | **Test zählt Prosa mit** | dreimal: `readdir`, `server-only`, `{G}/lead_lot.parquet` — Kommentare vorher entfernen |
| F2 | **Test leiht sich einen echten Listeneintrag** | brach, als die Liste geleert wurde, mit einer Meldung vom Falschen |
| F3 | **Nicht-deterministischer Export** | Sortier-Gleichstand machte jeden Vorher/Nachher-Vergleich wertlos |
| F4 | **Datenzuwachs als Regression fehldeuten** | 346 Abweichungen, tatsächlich Zuwachs seit dem Nachtlauf |
| F5 | **Nur den Füllgrad messen** | CH-Kriterien 100 % gefüllt, 29 % davon reine Etiketten |
| F6 | **Falscher Schlüssel beim Nachmessen** | 0 % in allen Ländern heisst meist: den Schlüssel gibt es nicht |
| F7 | **Namenssuche hält Leichen für lebendig** | einziger Treffer war ein Kommentar, der die Ablösung erklärt |

## G · Fallen im Betrieb

| # | Falle | Gemessen |
|---|-------|----------|
| G1 | **`ps aux` schneidet bei 80 Zeichen ab** | ohne Terminal fällt „govisor" weg → „Bahn frei" |
| G2 | **`grep -q` mit `pipefail` → Exit 141** | Erfolg sieht aus wie Fehler → „Bahn frei" |
| G3 | **System-Python ohne duckdb** | launchd scheitert stumm |
| G4 | **Import ohne `sys.path`** | unter launchd fehlt das Arbeitsverzeichnis |
| G5 | **`git add -A` mit zweiter Sitzung** | zweimal fremde Änderungen mitcommittet |
| G6 | **Falsche Parameter beim Neubau** | `--ab-jahr 2026` statt `2004 --alle-arten` schrieb die Tabelle schmaler |
| G7 | **`SIGALRM` von Playwright verschluckt** | Abrufer hängt und meldet nichts |

## H · Fallen beim Bauen von Kennzahlen

| # | Falle | Gemessen |
|---|-------|----------|
| H1 | **Plausible Verbesserung ohne Nutzen** | ARGE-Zerlegung bewegt 0,6 % der Nachfolgen |
| H2 | **Naives Gewinner-Matching** | ergäbe 78 % Verdrängung statt belastbarer 28,3 % |
| H3 | **Artefakt für Kennzahl halten** | 7 % Incumbent-Rate war ein Paarungsartefakt |
| H4 | **Harte Datumspflicht** | `publication_date`-Pflicht verwarf 93 % von DÖE |
| H5 | **Anreicherung lockern** | „Titel identisch genügt": 28 → 393 Werte, mit fremden Fristen |
| H6 | **Quellen zusammen zitieren** | TED 43,5 % reich / Ø 1,68 Lose gegen DÖE 20,8 % / Ø 1,00 |

## Die Meta-Regel

Fast jede Falle hier hat dieselbe Form:

> **Etwas sieht aus wie eine Aussage über die Welt und ist in Wahrheit eine Aussage über
> unsere Leitung.**

Ein leeres Feld sieht aus wie „gibt es nicht". „Zu wenig Daten" sieht aus wie eine Aussage
über die Vergabestelle. Eine alte Datei sieht aus wie eine frische. Eine Region namens
„Schweiz" sieht aus wie eine Region.

Die Gegenfrage, die man sich zur Gewohnheit machen muss:

> **Fehlt der Wert, oder fehlt die Leitung?**
