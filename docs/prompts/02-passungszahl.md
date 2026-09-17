# Passungszahl: sieht aus wie Prozent, hat acht Stufen

## Was passiert
In der Lead-Liste tragen auffaellig viele Leads die Relevanz 86. Nicht alle, aber die
Zahl wiederholt sich so oft, dass sie wie ein Platzhalter wirkt statt wie eine Messung.

## Ursache (gemessen 2026-09-17)
`web/lib/profileEngine.js:139-141`

    const S_MIN = 2, S_MAX = 5.5;
    export function passungsZahl(s) {
      const v = Math.round(((s - S_MIN) / (S_MAX - S_MIN)) * 100);

`s` wird aus vier Zuschlaegen gebaut (Zeilen 265-276) und kann nur Vielfache von 0,5
zwischen 2 und 5,5 annehmen. Die angezeigte Zahl hat damit genau acht moegliche Werte:

    s    2.0  2.5  3.0  3.5  4.0  4.5  5.0  5.5
    →      0   14   29   43   57   71   86  100

86 bedeutet: Feldtreffer voll, Region passt, Volumen passt, kein Zielrichtungsbonus.
Das ist der Normalfall eines gut passenden Leads. Die Zahl ist also nicht falsch
gerechnet. Sie behauptet nur eine Feinheit, die sie nicht hat.

## Aufgabe
Eins von beidem, nicht beides halb:

**(a) Die Zahl ehrlich machen.** Acht Stufen als acht Stufen zeigen: Balken, Punkte,
Wortmarke. Dann verspricht die Anzeige nichts, was die Rechnung nicht hergibt.

**(b) Die Rechnung feiner machen.** Dann braucht sie stetige Beitraege statt
Halbe-Punkte-Zuschlaege: CPV-Naehe als Abstand statt als ok/nachbar, Volumen als
Abstand zur Spanne statt als drei Faelle, Region als Entfernung statt als Treffer.
Das ist die groessere Arbeit und die bessere Antwort, wenn die Zahl im Produkt
tragend sein soll.

## Was NICHT hilft
Die Spreizung kosmetisch erhoehen, etwa S_MAX senken. Dann stehen dort acht andere
Zahlen. Die Stufigkeit sitzt in `s`, nicht in der Normierung.

## Abnahme
- Ein Test, der ueber den realen Bestand die Verteilung der angezeigten Werte zaehlt
  und festhaelt, wie viele verschiedene Werte vorkommen.
- Bei Variante (b): dieselbe Verteilung vorher/nachher im Commit, sonst ist nicht
  belegt, dass die Verfeinerung etwas geaendert hat.
- Bei Variante (a): ein Test, der bricht, sobald wieder eine Prozentzahl gerendert wird.
