# 10 · Abnahme — die Zahlen, die man verlangen muss

> Ein Land ist fertig, wenn diese Runde durchläuft. „Alle Schritte grün" ist keine Abnahme:
> ein Schritt kann aus drei Gründen nichts erzeugen und trotzdem grün melden — die Quelle
> lieferte nichts, er wurde übersprungen (Sperre, Zeitbudget), oder er fiel weich aus.

## Die Pflichtläufe

```bash
python3 -m pytest tests/ -q                    # muss GRÜN sein, vor dem Commit
python3 -m govisor.cli verify --country XX     # FK-Integrität
python3 scripts/pruefe_verdrahtung.py --offen  # Frische + Länderparität
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
