# Suche: der Heuhaufen ist kleiner als das Versprechen

## Was passiert
Eine Suche nach einem Ortsnamen findet Vorgaenge nicht, in deren Los-Titel der Ort
steht. Eine Suche nach einer Vergabenummer findet gar nichts, obwohl die Oberflaeche
„Vergabenummer" als Fundstelle kennt.

## Befund (gemessen 2026-09-17)
`web/lib/explorerCore.js:286` baut den durchsuchten Text:

    const leadText = l => (l.titel+' '+l.buyer+' '+l.buyerShort+' '+l.natur+' '
                          +(l.beschreibung||'')+' '+(l.kw||[]).map(k=>k.w).join(' ')).toLowerCase();

Sechs Felder. Nicht dabei: `lose[].titel` und `vergabenr`.

Gemessen ueber den Vollbestand (87.352 Leads), Suchwort „rottweil":

    vorhanden  36 Leads
    auffindbar 33 Leads
    unsichtbar  3 Leads   (Ort steht ausschliesslich im Los-Titel)

Dazu ein Widerspruch: `fundstelle()` ab Zeile 307 prueft `l.vergabenr` und kann
„Vergabenummer" als Fundort melden. `matchToken` kann einen solchen Treffer aber nie
erzeugen, weil `leadText` die Nummer nicht enthaelt. Eine Funktion beschreibt also
einen Trefferfall, den es nicht gibt.

## Aufgabe
1. `lose[].titel` in `leadText` aufnehmen. Bei Mehrlos-Vergaben steht dort regelmaessig
   der Ort und das eigentliche Gewerk.
2. `vergabenr` aufnehmen, oder `fundstelle()` den Zweig nehmen. Beides nebeneinander
   stehen zu lassen ist der schlechteste Zustand.
3. Danach neu messen. Die 33 von 36 sind die Vergleichsgroesse.

## Falle: Der Heuhaufen waechst
`leadText` laeuft ueber jeden Lead bei jedem Tastendruck. Lose dazuzunehmen
vergroessert die Zeichenkette spuerbar. Vor dem Einbau messen, danach wieder. Wenn es
bremst, den Text je Lead einmal bauen und behalten statt ihn je Anschlag neu zu
falten.

## Falle: Demo-Daten sind nicht der Vollbestand
Diese Luecke wurde gesucht, weil in einer Vorfuehrung eine Ortssuche leer blieb. Die
Ursache war dort eine andere: der Vorgang lag gar nicht im geduennten Demo-Datensatz.
`scripts/demo_datensatz.py` siebt nach Informationsdichte und kann ganze Regionen
fallen lassen.

Daraus die Regel: Jedes Suchwort, das in einer Vorfuehrung vorkommen soll, vorher
GEGEN DEN DEMO-DATENSATZ pruefen, nicht gegen den Vollbestand. Am besten als Skript,
das die Worte des Drehbuchs (`docs/demo-ablauf.md`) durchgeht und meldet, welche
davon ins Leere laufen.

## Abnahme
- Zaehlung vorher/nachher fuer mindestens drei Suchworte im Commit.
- Ein Test mit einem Lead, dessen Suchwort ausschliesslich im Los-Titel steht.
- Ein Test, der Fundstelle und Treffer gegeneinander haelt: jeder Fundort, den
  `fundstelle` melden kann, muss von `matchToken` erreichbar sein.
