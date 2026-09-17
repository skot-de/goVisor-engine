# Dubletten: derselbe Lead steht mehrfach in der Liste

## Was passiert
Auf der Startseite erscheint derselbe Vorgang bis zu viermal. In einer gefilterten
Liste von sechs Eintraegen war einer doppelt. Aus Nutzersicht wirkt das wie ein
Zaehlfehler im ganzen Produkt.

## Befund (gemessen 2026-09-16/17)
9.001 ausgelieferte Leads sind Dubletten, rund 5 % des Bestands. Rund 3.100 Faelle.

⚠ Eine frueher gemessene Zahl von 2,85 Millionen Geschwisterpaaren ist rechnerisch
richtig und praktisch nutzlos: sie waechst quadratisch mit der Clustergroesse. Die
Zahl, die zaehlt, ist die der ausgelieferten Doppelungen.

Die Dubletten-Firewall (`memory/govisor-dubletten-firewall.md`) markiert statt zu
loeschen und arbeitet paarweise. Die Luecke ist die Transitivitaet: wenn A=B und B=C
erkannt sind, aber A=C nicht, bleiben Teile des Clusters stehen.

## Aufgabe
1. Die paarweisen Marken zu Clustern schliessen (Union-Find oder gleichwertig), statt
   je Paar zu entscheiden.
2. Je Cluster einen Vertreter waehlen. Die Regel muss deterministisch sein, sonst
   wechselt die Liste zwischen zwei Aufrufen ohne Datenaenderung.
3. Erst danach ausliefern.

## Fallen
- Nur belegte Master. Beim Dokument-Wall hielten 46 % der vermuteten Master nicht
  stand, siehe `memory/govisor-dokument-dubletten.md`. Dieselbe Vorsicht gilt hier.
- Markieren statt loeschen bleibt. Ein zusammengefasster Cluster muss aufklappbar
  sein, sonst ist nicht pruefbar, ob richtig zusammengefasst wurde.
- Zahlen- und Geschwistersperre der bestehenden Firewall nicht umgehen.

## Abnahme
- Zahl der ausgelieferten Dubletten vorher/nachher im Commit.
- Ein Test mit einem Dreier-Cluster, bei dem nur zwei der drei Paare erkannt sind.
  Genau dieser Fall faellt heute durch.
