# Schritt 3: eine Frage, auf die es nur eine Antwort gibt

## Der Befund

Schritt 3 des Onboardings fragt „Gehoeren diese Einheiten zu euch?" und listet die
Mitglieder der Firmengruppe. Bei EINER Einheit ist das keine Frage, sondern eine Liste mit
einem Eintrag — ueber den in Schritt 2 gerade entschieden wurde.

Gemessen am 2026-09-18, zwei Grundmengen. ⚠ **Beide sind richtig, sie beantworten
verschiedene Fragen:**

    alle DE-Identitaeten (entity_identity.parquet)  304.994 · 96,9 % mit EINER Einheit
    Firmen, die das Onboarding findet (suppliers)    37.948 · 79,5 % mit EINER Einheit

Die zweite ist die einschlaegige: Schritt 3 erreicht nur, wer in Schritt 2 einen Treffer
aus `suppliers.json` bestaetigt hat.

## ⚠ Die erste Fassung hat das Falsche getan

Am 2026-09-17 habe ich den Schritt UEBERSPRUNGEN, wenn genau eine belegte Einheit vorlag.
Das ist die falsche Loesung, und der Auftrag sagt es ausdruecklich:

> Was der Schritt trotzdem leistet, und warum er NICHT uebersprungen werden soll: er
> traegt die Zusage „Mit der Bestaetigung merken wir uns diese Einheiten als eure
> Identitaet. 509 Siege fliessen in euer Profil." Das ist die Stelle, an der aus „wir
> kennen euch" ein Profil wird.

Falsch ist nicht der Schritt, sondern die FRAGE.

## Behoben am 2026-09-18

Gleiche Seite, gleiche Knoepfe, gleiche Zahlen — nur keine Scheinfrage mehr:

    mehrere Einheiten   „Gehoeren diese Einheiten zu euch?"      (Frage, unveraendert)
    genau eine          „Das ist euer Bestand"                   (Aussage)

Die Bedingung haengt an `members.length`, nicht an `matched` — `matched` ist auch bei
mehreren Einheiten gesetzt.

## ⚠ Der offene Punkt aus dem Auftrag, geprueft

Der Auftrag liess ausdruecklich offen, ob der Hinweis „spaeter ergaenzen" ueberhaupt
stimmt: „Falls nicht, darf der Text ihn nicht versprechen; dann lieber weglassen als
erfinden."

**Geprueft: er stimmt nicht.** Es gibt keinen Weg, eine Einheit nachtraeglich zu ERGAENZEN.
`EntityKorrektur` unter „Unternehmen" (`UnternehmenView.tsx:242`) ERSETZT die Zuordnung
(„Falsche Gesellschaft zugeordnet? Firma suchen und richtige Identitaet waehlen"). Der
Text sagt deshalb, was wirklich geht: die Zuordnung laesst sich berichtigen.

Ein Waechter faengt den Rueckfall: taucht „ergaenzen" oder „hinzufuegen" im Umfeld der
Aussage auf, wird er rot.

## Beide Faelle durchlaufen

Ueber die echte Schnittstelle des laufenden Servers geprueft, wie der Auftrag verlangt:

    H. Klostermann Baugesellschaft mbH    1 Einheit    → Aussage
    Man SE                              130 Einheiten  → Frage

## Was NICHT hilft

Den Schritt ueberspringen. Die Zusage ist der Grund, warum es ihn gibt.
