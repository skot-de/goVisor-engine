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
