# 10 · Abnahme — die Zahlen, die man verlangen muss

> Ein Land ist fertig, wenn diese Runde durchläuft. „Alle Schritte grün" ist keine Abnahme:
> ein Schritt kann aus drei Gründen nichts erzeugen und trotzdem grün melden — die Quelle
> lieferte nichts, er wurde übersprungen (Sperre, Zeitbudget), oder er fiel weich aus.

## Die Pflichtläufe

⚠ **Die Bibel prüft sich selbst mit.** Sie altert anders als Code — sie fällt nicht um,
sie wird nur langsam falsch. Am 2026-08-23 wurde sie an einem Tag geschrieben und am
selben Tag zweimal von der Wirklichkeit überholt: sechs Zahlen drifteten binnen Stunden,
eine Aussage über die Registry war schon beim Schreiben falsch.

`scripts/pruefe_bibel.py` prüft deshalb drei Dinge, und läuft im Nachtlauf mit:

| Prüfung | Was sie fängt |
|---------|---------------|
| **Datierung** | Eine Zahl ohne Datum liest sich als Gegenwart. Vergangenheitsaussagen („stand 12 Tage still") sind ausgenommen — ein Ereignis altert nicht. |
| **Behauptungen** | Ein Register messbarer Aussagen gegen die **Live-Daten**. Jede nennt ihr Kapitel; fällt sie, weiss man sofort, welche Stelle ab jetzt lügt. |
| **Doppelpflege** | Nennt `CLAUDE.md` eine Zahl, die auch in der Bibel steht? Dann veraltet sie an einer der beiden Stellen zuerst — genau so stand dort „16 Tabellen nur für DE", Stunden nachdem sie verdrahtet waren. |

**Eine neue prüfbare Behauptung gehört ins Register**, nicht nur in den Fliesstext. Was
dort steht, kann verrotten, ohne dass es jemand merkt.

```bash
python3 -m pytest tests/ -q                    # muss GRÜN sein, vor dem Commit
python3 -m govisor.cli verify --country XX     # FK-Integrität
python3 scripts/pruefe_verdrahtung.py --offen  # Sonde 1-4: Frische, Parität, Pfade, Länder
python3 scripts/pruefe_bibel.py --offen        # altert die Anleitung selbst?
cd web && npx tsc --noEmit                     # Typprüfung
cd web && for f in scripts/pruefe-*.mjs; do node "$f"; done
```

⚠ **Nie mit roter Suite committen.** Dreimal passiert, dreimal derselbe Ärger:
`export_web_awards.py` ohne `sys.path` (launchd-Falle), `build_quality` band `n.title`
statt `title`, `_lead_context_sql` stürzte über einen fehlenden Glob. Jedes Mal wäre es
vorher aufgefallen.

## Eine Prüfung, die selbst mitwächst

**Drei Fragen, die wie eine aussehen, und drei verschiedene Stellen.** Wer nur eine davon
beantwortet, hält sich für abgesichert:

| Frage | Wo sie beantwortet wird |
|---|---|
| Fehlt die Tabelle für ein Land? | `pruefe_verdrahtung.sonde_paritaet` — generisch, braucht keine Eintragung |
| Sind die Daten darin gültig? | `verify.gold_integrity` — Fremdschlüssel je Tabelle |
| Wurde eine neue Tabelle vergessen? | `test_jede_gold_tabelle_mit_fk_wird_geprueft` |

Die dritte ist die, die man vergisst. `gold_integrity` führt seine Prüfungen als
handgepflegte Liste; am 2026-08-25 stand sie bei 22, während `data/gold/<L>` auf 64 Tabellen
gewachsen war — 44 kamen nicht vor, darunter die ganze Los-, CPV- und Kriterien-Ebene.
Nebenan behauptete `CLAUDE.md` derweil, alle neuen Tabellen seien erfasst.

> **Gegen eine Liste, die aufhört zu wachsen, hilft kein Vorsatz.** Nur eine Prüfung, die
> neue Einträge von selbst findet und eine Entscheidung erzwingt: geprüft, oder mit Grund
> ausgenommen. Am 2026-08-31 fand sie beim ersten Lauf drei ungeprüfte Tabellen.

**Ausnahmen gehören als Daten neben die Prüfung, nicht in den Fliesstext.** `verify.FK_AUSNAHMEN`
war vorher ein Kommentarblock. Eine Ausnahme, die nur in Prosa steht, kann eine Prüfung nicht
von einer Nachlässigkeit unterscheiden. (`entity_merge_map` hat 100 % Waisen, und das ist sein
Zweck — es nennt die Quell-Entität einer Verschmelzung, die es danach nicht mehr gibt.)

### ⚠ Zwei Arten, wie ein Wächter unbrauchbar wird

Beide sind beim Bau genau dieser Prüfung passiert und beide erst durch den Versuch
aufgefallen, sie absichtlich zum Fehlschlagen zu bringen.

1. **Er lässt sich vom eigenen Kommentar besänftigen.** Die erste Fassung las die geprüften
   Tabellen per Regex aus dem ganzen Quelltext — und die Ausnahmeliste nennt die
   ausgenommenen Tabellen selbst beim Namen. Sie galten damit als geprüft, und jede
   beliebige Erwähnung im Text hätte dieselbe Wirkung gehabt. Ein Wächter, der seine eigene
   Dokumentation als Beleg akzeptiert, prüft nichts. → über den **Syntaxbaum** lesen, nicht
   über den Text.
2. **Er schlägt falsch an.** Die zweite Fassung meldete `entities` und `quality` als
   ungeprüft — die Eltern-Tabellen, deren Spalte ein Primärschlüssel ist. Formal richtig
   erkannt, fachlich Unsinn. **Ein Fehlalarm ist tödlicher als eine Lücke:** er kostet die
   Prüfung beim zweiten Mal das Vertrauen und beim dritten die Existenz.

> **Die Gegenprobe gehört zur Prüfung.** Eine Prüfung, die man nicht zum Fehlschlagen
> gebracht hat, ist unbewiesen. Für jede neue: einmal den Eintrag entfernen, einmal die
> Ausnahme entfernen, und sehen, ob sie wirklich rot wird. Beide Male hat genau das den
> Fehler gefunden, nicht das Nachdenken.

Und die Grenze mitschreiben: dieser Wächter sieht nur, was auf der Platte liegt — eine
gerade hinzugefügte Tabelle ist unsichtbar, bis sie einmal gebaut wurde.

## Die Abnahmetabelle

Eine Zeile je Kennzahl, alle Länder **nebeneinander**. Getrennte Messungen verstecken die
Lücke; nebeneinander springt sie ins Auge.

```
Feld              DE     AT     CH     Bewertung
region           96%    92%   100%     ok
beschreibung     89%   100%   100%     ok
lose             89%    32%    79%     AT prüfen: Silber oder Leitung?
zuschlag         58%    26%    79%     AT prüfen
frist            55%    11%    44%     Quelle (s. u.)
aufwand          30%     4%    23%     AT echte Datenlage
```

Für jede auffällige Zelle **genau eine** Frage beantworten:

> Trägt Silber den Wert und Gold nicht? → **Leitungsfehler.**
> Trägt Silber ihn auch nicht? → **Datenlage**, so benennen und stehen lassen.

Beispiel: die österreichische Frist stand in Gold bei 7 %, in Silber bei **72 %** aus
atverg. Also kein Quellenproblem.

Gegenbeispiel: der österreichische Angebotsaufwand steht bei 4 % — und `lead_export` führt
dort ebenfalls nur 173 Bürgschaften und 326 Bindefristen. Echte Datenlage.

## Die dritte Frage stellen

Füllgrad allein reicht nicht (s. [Kapitel 00](00-reihenfolge-und-tore.md)). Für jede
Kennzahl, die man ausliefert, einmal **hineinsehen**:

```sql
SELECT criterion_name, count(*) FROM read_parquet('data/gold/XX/lead_criteria.parquet')
GROUP BY 1 ORDER BY 2 DESC LIMIT 10
```

Gemessen CH: 29 % der Kriterien heissen „Zuschlagskriterien" und tragen kein Gewicht;
100 % der Eignungsanforderungen sind Verweise auf simap.ch. AT dagegen: 94 % mit Gewicht,
0 % Platzhalter. **Dieselbe Tabelle, zwei völlig verschiedene Qualitäten.**

### ⚠ „Thema erwähnt" ist nicht „Wert müsste da sein"

Die Parser-Selbstdiagnose (`scripts/parser_gaps.py`) misst je Signal, wie oft ein Thema im
Dokument steht (Anker trifft) und wie oft ein Wert herauskommt. Die Differenz gilt als
Arbeitsliste. Gemessen am 2026-08-25 stand dort für DE:

    award_weights   Lücke 4.555   Quote 38 %
    penalty_pct     Lücke 3.630   Quote 49 %
    binding_until   Lücke 2.711   Quote 64 %
    skonto_pct      Lücke 2.497   Quote 10 %

Drei dieser Posten wurden nachgeprüft. **Alle drei lösten sich auf:**

- **Skonto bietet der BIETER an**, der Auftraggeber nennt es nicht. An 200 Dokumenten ohne
  Wert: 30 % blosse Erwähnung im Angebotsformular, 28 % VOB/B-Regelung ohne Zahl, 20 %
  leeres Formularfeld („Gewährung von FORMTEXT ______ % Skonto"), nur 8 % mit einer
  Prozentzahl im Umfeld. Dort ist nichts zu holen — die Lücke von 2.497 war ein Phantom.
- **„Bindefrist endet am"** (353 Treffer) sah nach einem Datum aus. An 120 Dokumenten
  tragen **119 dahinter nichts** — es ist eine Formularbeschriftung.
- **„Zuschlagskriterium Preis"** (1.288 Treffer) sah nach „Preis als alleiniges Kriterium"
  aus und wäre eine wertvolle Regel gewesen. An 120 Dokumenten nennen **101 daneben
  „mehrere Zuschlagskriterien"**: der Satz gehört zu einem Formblatt, das Optionen
  auflistet. Nur 13 sind wirklich Preis-allein.

**Die Lehre für jede Lücken-Kennzahl:** ein Anker trifft ein THEMA. Ob an dieser Stelle
überhaupt ein Wert stehen kann, ist eine zweite Frage — und wo die Antwort „nein" lautet,
erzeugt die Kennzahl eine dauerhaft rote Zeile, die man nach zwei Wochen ignoriert. Das
Werkzeug kennt den Gedanken für Feld-Alternativen bereits (`ALTERNATIVEN`, siehe
`binding_days`); er gilt genauso für Bieterangaben und Formularfelder. Der Bericht weist
jetzt **rohe Lücke · ohne Wert · erreichbar** getrennt aus.

⚠ **Und eine Einschränkung, die zur Ehrlichkeit gehört.** Der „ohne Wert"-Test prüft das
Umfeld auf BEIDEN Seiten des Ankers; eine Ziffer irgendwo in 110 Zeichen genügt, um eine
Fundstelle als verwertbar zu zählen. Er fängt deshalb nur 723 der 4.555
`award_weights`-Fehlschläge. Eine Stichprobe, die nur RECHTS vom Anker sah, kam auf 97 % —
sie misst aber etwas anderes, nämlich „hängt an dieser Erwähnung ein Wert". Welche der
beiden Fragen die richtige ist, hängt am Signal und ist nicht entschieden.

## Determinismus

Zwei Läufe desselben Exports müssen dieselbe Ausgabe liefern. Sonst ist jeder
Vorher/Nachher-Vergleich wertlos — und er ist das einzige Mittel, einen Umbau abzusichern.

```bash
python3 scripts/export_strategie.py && cp web/data/strategie.json /tmp/a.json
python3 scripts/export_strategie.py && diff <(jq -S . /tmp/a.json) <(jq -S . web/data/strategie.json)
```

Gefundene Ursache: ein Sortier-Gleichstand (gleicher Titel **und** gleiche Restlaufzeit).
Ein Feld mehr im `ORDER BY` behebt es.

## Die Produktwege einmal von Hand durchgehen

Tor 6 ist das einzige, das man nicht rein mechanisch prüfen kann. Drei Handgriffe, die
zusammen fünf Minuten brauchen:

1. **Onboarding** — einen Firmennamen dieses Landes in `web/data/suppliers.json` suchen.
   Nicht einen, der auch in Deutschland gewinnt (der ist versehentlich drin), sondern einen
   rein inländischen. Gemessenes Beispiel: PORR war auffindbar, Implenia Schweiz nicht.
2. **Zuschlagsansicht** — `web/data/awards-*.json` nach `land` auszählen. Steht dort nur
   DE, ist entweder die Quelle DE-fest oder das Feld hartkodiert; beides ist vorgekommen.
3. **Firmenprofil** — in `web/data/firma-profiles.json` prüfen, ob Profile dieses Landes
   eine echte `hauptregion` tragen. Ein Regionsfilter à la `nuts1 LIKE 'DE_'` liess dort
   **null von 38.307** Profilen mit AT/CH-Region übrig.

⚠ Die Zahl allein genügt nicht. Nach dem Unionieren stiegen die Namensdubletten im
Firmenindex von 134 auf 868 — der Index war „vollständig" und für die Suche schlechter als
vorher. Also auch: **einen Namen suchen und zählen, wie viele Treffer kommen.**

## Der Dubletten-Selbsttest

Widerspruchsquote der Regionsableitung unter **15 %**. AT startete bei 58 % — die Ursache
war Vokabular, nicht der Ansatz ([Kapitel 07](07-geo-und-regionen.md)).

## Auffällige Aggregate sind Warnsignale

Ein paar echte Beispiele, was hinter einer schönen Zahl steckte:

| Zahl | Sah aus wie | War |
|------|-------------|-----|
| 100 % `volumen` | vollständig | ein formatierter String, auch bei „unbekannt" |
| 79 % CH-Region | gute Abdeckung | einmal „Schweiz/Suisse/Svizzera" für alle |
| 96,6 % `documents_url` | fast alles da | 33 % kommen tatsächlich durch den Trichter |
| 78 % Doktyp-Erkennung | Fortschritt | Zuschlagskriterien **sanken** (Fehlalarm bereinigt) |
| 7 % Incumbent-Rate | belastbar | Paarungs-Artefakt der alten `contract_chains` |
| Median 22 Pflichtfelder | Formularaufwand je Vorgang | 93 % der Formulare setzen das Pflicht-Kennzeichen gar nicht |
| 200.010 LV-Positionen | ein riesiges Leistungsverzeichnis | ein Lastgang: Viertelstundenwerte eines Jahres |
| 198.584 einordenbare Zahlen | eine breite Vergleichsbasis | 2.208; der Rest hat keine Einheit oder keine gemeinsame Grösse |
| „fast alle bei 5 %" | ein enger Markt | zwei Zahlen im Verhältnis 1:25 (5 % Obergrenze, 0,20 % je Werktag) |
| 5× genau −1 Tag Fristabweichung | ein Off-by-one bei uns | verlängerte Fristen: 51 % liegen auf Wochenvielfachen |
| „56 Dateien neu, 54 entfernt" | die Stelle hat das Paket umgebaut | die Fassung steckt im ZIP-Namen; 47 waren byte-gleich |

## Derselbe Inhalt unter anderem Namen

An einem einzigen Tag drei Mal dieselbe Fehlerform, und jedes Mal sah die falsche Zahl
beeindruckend aus:

| Zahl | sah aus wie | war |
|---|---|---|
| 200.010 „LV-Positionen" | ein riesiges Leistungsverzeichnis | ein Lastgang, im Einheitenfeld als „Positionen" geführt |
| 264 Bieterfragen | ein Verfahren mit sehr vielen Fragen | ein Katalog mit 66 Fragen, in vier Ständen abgelegt |
| 56 neue Dateien | ein umgebautes Vergabepaket | dieselben Dateien, der ZIP-Name trägt die Fassung |

**Die gemeinsame Form:** derselbe Inhalt erscheint unter mehreren Namen, und eine Zählung über
Namen multipliziert ihn. Sie fällt nicht auf, weil das Ergebnis plausibel wirkt — grosse Vergaben
haben eben viele Positionen, viele Fragen, viele Dateien.

**Die Gegenprobe kostet eine Zeile: über den INHALT zählen, nicht über den Namen.** Prüfsumme
oder Hash je Dokument, Text je Absatz, Wert je Zeile. Weicht die Zahl danach stark ab, war der
Name das Problem.

⚠ **Und die Normalisierung muss den GANZEN Bezeichner erfassen.** Beim Fassungsvergleich lag die
Versionsnummer sowohl im Verzeichnis (`Version 1/`) als auch im ZIP-Namen
(`Z42-2025-0209_Version 1.zip::`). Wer nur das Verzeichnis normalisiert, hat die Hälfte des
Problems behoben und merkt es nicht — das Ergebnis ist immer noch plausibel, nur falsch.

## Wann ein Rahmen zur Entschuldigung wird

Der Abschnitt weiter unten sagt: vergleiche im richtigen Rahmen, sonst misst du die Vergabeart
statt der Vergabe. Bei **einer** Kennzahl kippt diese Regel, und es lohnt zu wissen, woran man
den Fall erkennt.

Die Verlässlichkeit je Auswertung (Kennzahl 10) misst nicht die Vergabe, sondern **uns**: wie
viele Aussagen des Modells sich nicht belegen liessen. Diese Quote spreizt **3,2-fach nach
Modell** — gpt-5.6-luna 4 %, gemini-2.5-flash 8 %, Llama-3.3-70B 11 %. Nach der üblichen Regel
müsste man je Modell vergleichen. Das wäre falsch: eine dünne Auswertung ist dünn, egal welches
Werkzeug sie erzeugt hat. Der Rahmen nähme dem Nutzer genau die Information, die ihn angeht, und
schriebe unsere Werkzeugwahl als Naturgesetz fest.

**Die Unterscheidung:**

| | Rahmen nimmt heraus | richtig? |
|---|---|---|
| Kennzahl über die **Vergabe** | Streuung, die dem Vorgang äusserlich ist (Regelwerk, Gewerk, Textmenge) | ja |
| Kennzahl über **unsere Arbeit** | Streuung, die aus unseren eigenen Entscheidungen stammt | nein |

Die Prüffrage lautet: **wäre der Rahmen eine Entschuldigung?** „Für ein Llama-Modell ist das
normal" entschuldigt; „für ein Anstrich-Leistungsverzeichnis ist das normal" erklärt. Das erste
darf nicht in eine Kennzahl.

⚠ **Und wo kein Vergleichswert angezeigt wird, muss trotzdem etwas die Schwelle bewachen.** Diese
Kennzahl hat keinen Export, in dem eine Driftprüfung mitlaufen könnte. Also prüft ein Test die
Schwelle gegen den echten Bestand und wird rot, wenn das oberste Zehntel weit wegwandert. Eine
Konstante ohne Wächter ist eine Konstante, die still veraltet.

## Wenn ein Fehlalarm teurer ist als ein verpasster Befund

Die meisten Kennzahlen dürfen im Zweifel melden: „Vertragsstrafe höher als üblich" kostet den
Leser dreissig Sekunden, wenn sie danebenliegt. Bei **einer** ist es umgekehrt — der
Fristwiderspruch. Wer dort einen Fehlalarm sieht, plant um oder verwirft die Vergabe.

Für diese Klasse gelten drei zusätzliche Regeln:

- ⚠ **Der Beleg muss die Behauptung tragen, nicht nur begleiten.** Ein Zitat „Ablauf der
  Angebotsfrist Datum Uhrzeit" (das Etikett eines Formularfelds) stand als Beweis für einen
  28-Tage-Widerspruch da und enthielt kein einziges Datum. Prüfen, ob der Beleg den Wert
  wirklich enthält — 7 % taten es nicht.
- ⚠ **Der Ausschnitt liegt um den Beweis, nicht am Satzanfang.** Die Kürzung auf 150 Zeichen
  schnitt genau das Datum weg, weil es erst nach 150 Zeichen kam. Dieselbe Falle hat schon
  einmal aus „Bindefrist: 30.10.2026" ein „Bindefrist: …" gemacht.
- ⚠ **Im Zweifel schweigen, auch wenn der Befund echt sein könnte.** „Die Angebotsfrist endet am
  10.09.2027" bei einer Bekanntmachung für 2026 ist entweder ein Jahresdreher des Auftraggebers
  (ein wertvoller Fund) oder ein Lesefehler von uns. Ohne das Dokument zu öffnen ist beides
  ununterscheidbar, also wird nichts gemeldet. Ein verpasster echter Fund kostet weniger als ein
  erfundener.

**Und eine Regel für die Aussage selbst:** wo zwei Quellen sich widersprechen und die Daten nicht
sagen, welche recht hat, darf die Anzeige es auch nicht sagen. Beide Werte nennen, den Beleg
dazu, und den einen Satz, der unabhängig davon stimmt.

## Der Rahmen ist selten der, den man zuerst vermutet

Vier Kennzahlen dieser Reihe brauchten eine Vergleichsgruppe, und **dreimal war die naheliegende
die falsche**:

| Kennzahl | naheliegend | gemessen richtig | Spreizung |
|---|---|---|---|
| Aufwand gegen Zeitfenster | der Markt | **Regelwerk** (Mindestfristen) | — |
| Leistungsverzeichnis | CPV-Abteilung | **Gewerk** (CPV 4-stellig) | 5,4× |
| Bezifferte Schwellen | Anforderungsart | **Art × Einheit × Ausprägung** | 25× |
| Standardtext-Anteil | Regelwerk | **Textmenge** | 4,1× gegen 1,8× |

Beim Standardtext lag das Regelwerk besonders nahe: es trennt sichtbar (UVgO 42 %, VOB 25 %),
und bei Kennzahl 1 war es die richtige Antwort gewesen. Es ist trotzdem der schwächere Rahmen.

**Das Verfahren, das die Frage entscheidet, kostet eine Abfrage:** die Kandidaten-Rahmen
kreuzweise auftragen und die Spreizung der Mediane vergleichen. Der stärkere Rahmen ist der,
dessen Muster sich *innerhalb* des anderen wiederholt — beim Standardtext fällt der Anteil in
**jedem** Regelwerk mit wachsender Textmenge, aber die Regelwerks-Reihenfolge dreht sich nicht
um.

⚠ **Und der Grund muss inhaltlich benennbar sein.** Grosse Pakete tragen ein eigenes
Leistungsverzeichnis und eigene technische Anlagen — deshalb sinkt der Kopie-Anteil. Wer einen
Rahmen nur wählt, weil er die grössere Zahl liefert, hat eine Korrelation gefunden und keine
Erklärung.

## Zwei Zahlen unter einem Namen

Eine Anforderungsart kann zwei verschiedene Grössen enthalten, die denselben Namen und dieselbe
Einheit tragen. Die Vertragsstrafe ist der Musterfall: **5 % Obergrenze** und **0,20 % je
Werktag** heissen beide „Vertragsstrafe" und stehen beide in Prozent — im Verhältnis 1:25. Wer
sie zusammen mittelt, bekommt eine Zahl, die für keine von beiden gilt; wer nur eine anzeigt,
sagt dem Nutzer nicht, welche er sieht.

**Woran man es erkennt.** Die Verteilung ist zweigipflig, und der Abstand ist zu gross für
Streuung: Werte um 0,1 bis 0,3 neben Werten um 5 bis 10. Ein Median dazwischen (hier: 1,0 im
unzugeordneten Rest) ist das Warnzeichen — er liegt dort, wo keine echte Vergabe liegt.

⚠ **Und die Unterscheidung steht im Text, nicht in einem Feld.** Drei Regeln dafür, alle drei
teuer erkauft:

- **Das Einheitenfeld ist oft Fliesstext.** „der Auftragssumme je angefangenen Werktag", „€ je
  Vorfall", „pro Woche". Wer nur bekannte Einheiten akzeptiert, verwirft die beste Auskunft.
- ⚠ **Geschwisterzeilen teilen sich das Zitat.** Beide Zahlen stammen aus einem Satz, also
  bekommen beide Zeilen denselben Beleg. Nur die zeilengenauen Felder unterscheiden sie —
  sie müssen **Vorrang** haben, sonst fallen genau die Vorgänge heraus, die beide Zahlen nennen.
- **Eine dritte Bezugsgrösse ist kein Sonderfall der zweiten.** „Pro Woche" ist kein Tagessatz
  und „je Vorfall" auch nicht. Wer sie einsammelt, weil sie „ungefähr passen", baut Fehlalarme.

Wo der Text nichts hergibt, bleibt die Zahl **ohne Etikett und ohne Vergleich**. Das ist besser
als ein Etikett, das in einem von vier Fällen falsch ist.

## Die Driftprüfung gehört in den Lauf, nicht ins Protokoll

Der Abschnitt darunter beschreibt, wie man prüft, ob eine Zahl den Vorgang misst oder uns. Beim
Bau von Kennzahl 6 kam die zweite Hälfte dazu: **dieses Urteil darf nicht von Hand gefällt und
dann eingefroren werden.** Eine Liste „diese Gruppen sind stabil" ist in drei Monaten falsch,
ohne dass es jemand merkt — neue Quellen, neue Abrufquoten, andere Verteilung.

`scripts/export_schwellen.py` rechnet sie deshalb bei jedem Lauf selbst: Median der flach
gelesenen Vorgänge gegen Median der tief gelesenen, und wer weiter als um den Faktor 1,5
auseinanderläuft, fliegt raus. Was rausfliegt, wird **mit Grund gemeldet** — eine stille Auswahl
liest sich später wie „mehr gab es nicht", und die nächste Sitzung sucht die fehlenden Werte im
Renderer.

⚠ **Zwei Regeln, die dabei teuer erkauft sind:**

- **Stabilität ist notwendig, nicht hinreichend.** `technische_mindestanforderung / Prozent`
  besteht die Prüfung mühelos und ist trotzdem unvergleichbar: 20 % Steigung gegen 20 %
  Recyclinganteil. Die Frage „benennt die Gruppe EINE Grösse?" ist ein Urteil und bleibt eines.
- **Die naheliegende Erklärung für eine Drift ist oft falsch.** Beim Mindestumsatz lag „tief
  gelesene Vorgänge sind grosse Vergaben" auf der Hand. Die Schwelle korreliert aber nicht mit
  dem Auftragswert (0,24), und der Anstieg bleibt innerhalb jedes Regelwerks bestehen. Wer eine
  Drift wegerklären will, muss den Erklärungsversuch selbst messen.

## Steht die Zahl schon irgendwo?

Die billigste Frage von allen, und sie wird am zuverlässigsten vergessen. Beim Bau von Kennzahl
5 („Umfang des Leistungsverzeichnisses") war der Export fertig, die Route verdrahtet und der
Renderer geschrieben, bevor beim ersten Blick in die laufende App auffiel: der Block
„Leistungsumfang" zeigte die Zahl seit Monaten an, samt Mengen je Einheit und Positionstabelle.

Der Schaden wäre nicht ein Fehler gewesen, sondern eine **Doppelung** — zwei Kacheln, die
dieselbe Zahl sagen, in einer Oberfläche, die ohnehin an zu vielen Kennzahlen trägt. Solche
Doppelungen fallen im Code nie auf, weil beide Wege für sich richtig sind.

Zwei Handgriffe vor dem Bauen:

- **Im Frontend nach der Zahl suchen, nicht nach dem Kennzahl-Namen.** Die Übergabe nannte sie
  „Mengengerüst", die App nennt sie „Leistungsumfang". Ein Namensvergleich hätte nichts gefunden.
- ⚠ **Und wenn sie schon da ist, prüfen, aus WELCHER Quelle.** Die angezeigte Zahl kam aus den
  geparsten Positionen (`doc_positions.parquet`), der neue Export leitete sie aus
  `doc_checklist` ab. Zwei Quellen für dieselbe Zahl sind immer die schlechtere Lösung, und hier
  war die zweite zusätzlich falsch: ihre Spitzenwerte waren Lastgänge, keine Positionen. Wer
  ergänzt, liest dieselbe Quelle wie der Block, den er ergänzt.

Was am Ende gebaut wurde, ist deshalb **nur der Vergleich**, angehängt an die vorhandene Zeile.
Eine Kennzahl muss keine eigene Kachel bekommen, um eine zu sein.

## Misst die Zahl den Vorgang oder misst sie uns?

Die Frage steht hier eigenhändig, weil sie sich nicht wie ein Fehler anfühlt. Eine Zahl aus den
Vergabeunterlagen kann handwerklich sauber gerechnet, gut belegt und trotzdem eine Aussage über
**unsere Abrufquote** sein statt über die Ausschreibung. Sie sieht dann genau so aus wie eine
echte Kennzahl.

**Der Test dauert eine Abfrage.** Den Wert in Klassen nach Lesetiefe legen (Zahl der geparsten
Dateien) und den Median je Klasse ansehen:

| | 1-5 Dateien | 6-15 | 16-40 | Urteil |
|---|---|---|---|---|
| Anforderungen je Bereich (Kennzahl 2) | stabil | stabil | stabil | **trägt** |
| Formulare je Vorgang (Kennzahl 4) | 2 | 7 | 16 | **trägt nicht** |
| Felder je Vorgang (Kennzahl 4) | 60 | 327 | 606 | **trägt nicht** |
| Felder je Formular (Kennzahl 4) | 27 | 41 | 38 | trägt |

Wächst der Median mit der Lesetiefe, misst die Zahl uns. Zwei Auswege gibt es, und einer davon
ist eine Falle:

- ⚠ **Die Falle: „dann nehme ich nur die vollständigen Vorgänge".** Klingt zwingend und half
  nicht. In den 165 Vorgängen, deren Unterlagen komplett aus **einem** ZIP kamen, wuchs derselbe
  Median genauso (1 → 6 → 18). Vollständig heisst nicht vergleichbar: grosse Vergaben haben
  grosse Pakete. Ein Plateau ist der Beleg, den man sucht, und es gab keins.
- **Der Ausweg: auf Anwesenheit zurückgehen.** Was wir gesehen haben, ist da. Nur das Gegenteil
  dürfen wir nicht behaupten. Eine Anwesenheits-Kennzahl sagt nie „wenig" und bekommt **keinen
  Marktvergleich** — der marktweite Wert stammt aus derselben Untererfassung, und dagegen
  gemessen sähe jeder tief gelesene Vorgang extremer aus als er ist. Sie trägt dafür eine
  absolute Schwelle, und die darf aus der Verteilung stammen.

**Und die Bezugsgrösse ist die zweite Hälfte der Antwort.** `keine` ist kein Eingeständnis,
sondern manchmal die einzige richtige Angabe: siehe `govisor/kennzahlen.py`, wo jede Kennzahl
sagen muss, wogegen sie vergleicht.

## Was in die Dokumentation gehört

Nach der Abnahme, **bevor** man weitergeht:

1. `docs/quellen-landkarte.md` — Status je Quelle ehrlich setzen
2. Auto-Memory — was gemessen wurde und was offen blieb, mit **absolutem Datum**
3. Die Abnahmetabelle selbst — sie ist der Vergleichspunkt für das nächste Mal
4. Offene Punkte als **offen** benennen, nicht als erledigt

⚠ Ein Zwischenstand, der nirgends steht, gilt beim nächsten Mal als fertig. Genau so
verlor Österreich sechs Wochen.

## Rückwärtsgang — was, wenn es schiefgeht

Ein neues Land kann bestehende Daten beschädigen. Drei Wege zurück, in dieser Reihenfolge:

1. **Silber ist wiederherstellbar**, solange Bronze steht. `--max-pages 0 --silber` baut es
   ohne Neuabruf. Deshalb wird Bronze nie überschrieben und nie gefiltert.
2. **Gold ist immer neu baubar** aus Silber. Ein kaputter Gold-Lauf ist ärgerlich, kein
   Datenverlust — vorausgesetzt, niemand hat Silber angefasst.
3. **Ein Land ausschalten** heisst: aus den `LAENDER`-Listen nehmen
   ([Kapitel 15](15-eintragungsliste.md)) und `data/gold/XX/` beiseitelegen, **nicht
   löschen**. `data/archiv_geloescht_<datum>/` ist der eingeführte Ort dafür.

⚠ **Nicht in Silber löschen, um einen Parser-Fehler zu beheben.** Der Parser wird
korrigiert und Silber neu gebaut; ein selektives Löschen hinterlässt eine Lücke, die später
niemand mehr erklären kann.

⚠ **Vor jedem Neubau die Bahn prüfen** ([Kapitel 11](11-betrieb.md)) und **die richtigen
Parameter verwenden** — ein Dubletten-Neubau mit falschem Zeitfenster schreibt die Tabelle
schmaler und niemand sieht es.

## Negativbefunde festhalten

Widerlegte Hypothesen sind Arbeitsergebnisse und gehören dokumentiert, sonst prüft sie der
Nächste erneut. Gesammelt in der Auto-Memory `govisor-negativbefunde`; Beispiele:

- Wettbewerbsdichte sagt **nicht** Single-Bieter voraus
- kein brauchbares AUC-Modell
- sprachübergreifende CH-Dubletten existieren **nicht**
- ARGE-Zerlegung bewegt 0,6 % — nicht bauen
