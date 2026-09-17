# Filteranzeige: eine Zahl statt der Einstellungen

## Was passiert
Man stellt Filter ein, klappt das Filterfeld zu und weiss danach nicht mehr, was
eingestellt ist. Beobachtet waehrend einer Vorfuehrung: „ich sehe meine aktiven
Filtereinstellungen nicht".

## Befund (gemessen 2026-09-17)
Es gibt eine Zaehlung, und sie wird auch angezeigt:

- `web/components/explorer/FilterPanel.tsx:40` `export function advCount(a: Adv): number`
  summiert zwoelf Filterarten.
- `web/components/explorer/ExplorerShell.tsx:1381` rendert sie als Kaestchen neben
  „Filter".

Sichtbar ist also „Filter 4". Nicht sichtbar ist, WELCHE vier. Die Zahl sagt nur, dass
etwas die Liste beschneidet, und laesst den Nutzer raten, was.

Das ist keine Kleinigkeit: wenn die Liste kuerzer ist als erwartet, ist die erste Frage
immer „liegt das an den Daten oder an meinen Filtern". Eine Zahl beantwortet sie nicht.

## Aufgabe
Zeige die aktiven Filter als einzeln abwerfbare Marken ueber der Liste: „Bau",
„2-10 Mio", „NRW", „Vertragsende 1 Monat", jede mit einem x. Dazu eine Moeglichkeit,
alle auf einmal zu loesen.

`advCount` wird dabei ueberfluessig oder bleibt fuer den eingeklappten Zustand. Die
zwoelf Zweige der Funktion sind die vollstaendige Liste dessen, was beschriftet werden
muss. Keinen davon auslassen: ein Filter ohne Marke ist schlimmer als heute, weil dann
nicht einmal mehr die Zahl stimmt.

## Falle
Hausregel: Oberflaechentexte ohne Gedankenstrich. Siehe
`memory/govisor-keine-gedankenstriche.md`. Wertspannen also „2 bis 10 Mio", nicht
„2-10 Mio" mit Halbgeviert.

## Abnahme
- Ein Test, der fuer jede der zwoelf Filterarten prueft, dass eine gesetzte Einstellung
  genau eine Marke erzeugt, und dass ein Klick auf das x genau diese Einstellung
  zuruecknimmt.
- Der Test muss die Filterarten einzeln durchgehen, nicht in Summe. Eine Summenpruefung
  bleibt gruen, wenn zwei Zweige sich gegenseitig ausgleichen.
