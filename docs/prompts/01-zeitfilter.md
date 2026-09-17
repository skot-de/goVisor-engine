# Zeitfilter: Filter und Liste meinen zwei verschiedene Daten

## Was passiert
Filtert man im Explorer „Vertragsende: 1 Monat", erscheinen zwei Leads mit 8 Tagen
Frist. Stellt man auf „egal", tauchen Leads mit 4, 5, 6 Tagen auf, die der Ein-Monats-
Filter verschwiegen hat. Aus Nutzersicht: der Filter unterschlaegt genau die Faelle,
die er zeigen muesste.

## Ursache (gemessen 2026-09-17)
Zwei Stellen ordnen dieselben zwei Datumsfelder gegensaetzlich:

- `web/components/explorer/ExplorerShell.tsx:62` (Filter)
  `const days = (l.endTage) ?? (l.tage);`   → Vertragsende zuerst, Frist als Rueckfall
- `web/lib/explorerCore.js:617` (Sortierung)
  `l.tage != null ? l.tage : (l.endTage != null ? l.endTage : 9999)` → Frist zuerst

Die Liste zeigt die Frist (`tage`). Ein Lead mit `tage=4` und `endTage=800` hat also
sichtbar „4 Tage", faellt aber aus dem Ein-Monats-Filter, weil der 800 misst.

## Aufgabe
1. Entscheide, was „Zeithorizont" bedeuten SOLL. Die zwei Bedeutungen sind verschieden
   und beide legitim: Angebotsfrist (wann muss ich abgeben) und Vertragsende (wann wird
   neu vergeben). Sie gehoeren nicht in dieselbe Zahl.
2. Setze die Entscheidung an BEIDEN Stellen gleich um. Wenn zwei Horizonte gebraucht
   werden, dann als zwei getrennte Bedienelemente mit eigenen Beschriftungen.
3. Was die Liste in der Spalte anzeigt, muss dasselbe Feld sein, nach dem der Filter
   siebt. Wenn nicht, muss die Spalte sagen, welches der beiden sie zeigt.

## Falle
`endTage` ist NICHT die Angebotsfrist. Das steht schon in
`memory/govisor-leseprobe.md` als eine der vier Datenfallen und hat hier erneut
zugeschlagen. Vor dem Umbau nachlesen.

## Abnahme
- Ein Gegenbeweis-Test: ein Lead mit kleinem `tage` und grossem `endTage` muss unter
  dem Filter erscheinen, der seine ANGEZEIGTE Zahl meint.
- Der Test muss rot werden, wenn man die Reihenfolge an einer der beiden Stellen
  zurueckdreht. Sonst prueft er die Absicht, nicht den Code.
- Zaehle vorher und nachher, wie viele Leads je Horizontstufe sichtbar sind, und nimm
  die Zahlen in den Commit. Beim ersten Messen waren 3.283 Leads betroffen.
