# 01 · Quellenlandschaft — was es in diesem Land überhaupt gibt

> Tor 1. Fällt, wenn alle drei Vergabeebenen geprüft sind und je Ebene entschieden ist:
> welche Quelle, braucht sie ein Konto, gibt es eine offizielle Schnittstelle.

## Die drei Ebenen — und die dritte wird immer vergessen

**1 · Oberschwellig — TED.** Überall gleich, EU-weit einheitlich, kommt praktisch
geschenkt. Der Bestand liegt bereits monatsweise als XML-Bulk vor; ein neues Land heisst
hier nur, den Länderfilter zu erweitern. Das ist der einfache Teil und verführt dazu, ein
Land für erschlossen zu halten.

**2 · Unterschwellig — nationale Pflichtveröffentlichung.** Hier entscheidet sich der
Aufwand eines Markteintritts, und die Struktur unterscheidet sich fundamental:

- **Deutschland**: auf ein Dutzend Portale zersplittert. `oeffentlichevergabe.de` (DÖE)
  aggregiert nur teilweise.
- **Polen**: ein zentrales *Biuletyn Zamówień Publicznych*. **Ein** Connector gegen zwölf.
- **Österreich**: `offenevergaben.at` (CC0-API) deckt breit ab.
- **Schweiz**: `simap.ch` mit offener JSON-API.

Ein Connector gegen zwölf — das ist der Unterschied zwischen zwei Tagen und zwei Monaten.
Diese Frage gehört **vor** die erste Codezeile.

**3 · Fonds-Ebene — der unsichtbare Markt.** Vergaben von **Empfängern öffentlicher
Fördermittel, die selbst keine öffentlichen Auftraggeber sind**. Die Wettbewerbspflicht
gilt EU-weit über die Fondsverordnungen, die Sichtbarkeit ist rein national.

- Polen führt dafür ein zentrales Portal
  (`bazakonkurencyjnosci.funduszeeuropejskie.gov.pl`).
- Für **DACH geprüft (2026-08-18): kein eigenes Verzeichnis.**

Je mehr Kohäsionsmittel ein Land bekommt, desto grösser dieser sonst unsichtbare Markt.
**Diese Frage bei jedem neuen Land ausdrücklich beantworten** — auch wenn die Antwort
„gibt es nicht" lautet, denn sonst weiss beim nächsten Mal niemand, ob sie gestellt wurde.

## API vor Abgriff

**Erst nach der offiziellen Schnittstelle fragen, dann scrapen.** Das ist keine Höflichkeit,
sondern spart Wochen: ein Portal mit API liefert typisierte Felder, ein Abgriff liefert
HTML, das sich beim nächsten Relaunch ändert.

Der Prüfstand aller bisher untersuchten Portale steht in
[`docs/quellen-landkarte.md`](../quellen-landkarte.md) — Kurzfassung: **nur simap.ch hat
eine echte API.** Alles andere in DACH ist Abgriff.

Reihenfolge der Prüfung:

1. Gibt es eine dokumentierte API? (Suche nach „OpenData", „Schnittstelle", „API", CC0/CC-BY)
2. Gibt es einen Bulk-Download (XML/JSON/CSV je Monat)?
3. Erlaubt `robots.txt` den Abruf? — **wird respektiert.** Die XVergabe-Dienste des
   Bundes sind vorhanden, aber robots-gesperrt; deshalb liegen sie brach, obwohl technisch
   erreichbar.
4. Braucht es ein Konto? Wenn ja: ist es kostenlos, an eine Firma gebunden, an eine
   Interessensbekundung je Vergabe? (simap.ch: Interesse je Vergabe — s.
   [Kapitel 03](03-input-dokumente.md).)

## Rechtlicher Rahmen — die vier Fragen

1. **Lizenz der Daten.** CC0 (DÖE), CC-BY, oder ungeklärt? Ungeklärt heisst: nicht
   weiterverbreiten, nur auswerten.
2. **Schwellenwerte und Verfahrensarten.** Sie bestimmen, was überhaupt veröffentlicht
   werden muss, und damit den Bestand.
3. **Vergaberechtsregime.** In DE `regulatory_regime` (VOB/VgV/UVgO/SektVO) mit 98,2 %
   Abdeckung — das höchste Feld im ganzen Inventar. Das Gegenstück im neuen Land finden.
4. **PII.** Kontaktpersonen, E-Mail, Telefon liegen in Silber (`notice_parties`). Die
   Grenze zum Frontend zieht der Export, nicht die Pipeline. Nicht verwässern.

## Eintrag in die Registry

Jede Quelle bekommt einen Eintrag in `govisor/sources.py`. Das ist keine Formsache: die
Registry ist die einzige Stelle, an der man sieht, was existiert, was läuft und was nur
behauptet wird.

```python
from govisor import sources
sources.STATUSES      # ('live', 'prepared', 'candidate', 'research')
sources.by_country("AT")
sources.dach_matrix()
```

Die vier Status ehrlich verwenden:

| Status | Bedeutung | Falsch verwendet heisst |
|--------|-----------|-------------------------|
| `research` | untersucht, noch keine Zeile Code | — |
| `candidate` | Machbarkeit belegt, Connector geplant | „wir haben das schon" |
| `prepared` | Connector gebaut, läuft nicht im Nachtlauf | **die gefährlichste Lüge**: gebaut, aber nicht verdrahtet |
| `live` | läuft im Nachtlauf, Ausbeute gemessen | — |

⚠ **`prepared` ist die Statusklasse, in der sich Arbeit versteckt.** Ein Connector, der
gebaut ist und nicht läuft, sieht in jeder Übersicht aus wie Fortschritt und liefert
nichts. Wer etwas auf `prepared` setzt, schreibt dazu, was zum `live` fehlt.

## Ehrlicher Konter auf „wir haben 200 Quellen"

Drei Connectoren aggregieren rund 36 Portale. Das ist eine gute Zahl und trotzdem nicht
dasselbe wie 36 Anbindungen: fällt der Aggregator aus, fallen alle 36. Wer Quellen zählt,
zählt **Connectoren**, und nennt die aggregierte Reichweite getrennt.

## Ergebnis dieses Kapitels

Ein Abschnitt in `docs/quellen-landkarte.md` mit:

- je Ebene: Quelle, Status, Lizenz, Konto ja/nein, API ja/nein
- die Fonds-Frage ausdrücklich beantwortet
- gemessene Mengen: wie viele Bekanntmachungen je Jahr erwartet man?

Erst dann Code.
