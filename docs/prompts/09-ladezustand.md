# Erstaufruf dauert rund 12 Sekunden, ohne dass etwas passiert

## Was passiert
Nach der Anmeldung steht „0 von 0" auf dem Schirm. Rund zwoelf Sekunden lang sieht es
aus, als gaebe es keine Daten. Erst danach fuellt sich die Liste. Waehrend einer
Vorfuehrung ist das der gefaehrlichste Moment des Produkts.

## Zwei getrennte Aufgaben

### (a) Der Ladezustand
„0 von 0" ist eine Aussage ueber die Daten. Sie ist waehrend des Ladens falsch. Es
braucht einen dritten Zustand neben „leer" und „gefuellt": „laedt noch". Solange der
gilt, darf keine Zahl dastehen, die wie ein Ergebnis aussieht.

Das ist die kleinere Aenderung und die, die den Schaden abstellt.

### (b) Die Nutzlast
Gemessen: 49,6 MB im Erstaufruf. Erreichbar sind rund 25,5 MB, wenn Felder, die die
LISTE nicht braucht, erst beim Oeffnen eines Leads nachgeladen werden.

⚠ Offene Entscheidung: `anf` (Anforderungen). Das Feld ist gross. Ob die Liste es
braucht, haengt daran, ob Anforderungen in der Listenansicht gezeigt oder gefiltert
werden. Das vor dem Umbau klaeren, nicht waehrend.

Vorbild fuer den Schnitt ist `leads-fristen.json`: dieselben Leads, sechs Felder,
7,2 MB statt 110 MB. Siehe Kopf von `web/lib/leadIndex.ts`.

## Falle
Wer (b) macht und (a) laesst, hat den Schrecken nur verkuerzt, nicht beseitigt. Wer
(a) macht und (b) laesst, hat eine ehrliche Anzeige fuer eine zu langsame Seite. Beide
sind einzeln sinnvoll, (a) zuerst.

## Abnahme
- Nutzlast in MB vorher/nachher im Commit, gemessen am Netzwerkprotokoll, nicht
  geschaetzt.
- Ein Test, der prueft, dass waehrend des Ladens keine Ergebniszahl gerendert wird.
