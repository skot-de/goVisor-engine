# Onboarding Schritt 3 zeigt 96,9 % der Nutzer eine Liste mit einem Eintrag

## Was passiert
Schritt 3 fragt „Gehoeren diese Einheiten zu euch?" und zeigt die gefundenen
Firmeneinheiten zur Bestaetigung. Fuer die grosse Mehrheit ist das eine Liste mit
genau einem Element: eine Frage, die keine ist, mitten im Trichter.

## Befund
96,9 % der Firmen im Bestand haben genau eine Einheit. Der Schritt lohnt sich fuer
3,1 %.

## Aufgabe
Den Schritt ueberspringen, wenn es nichts zu entscheiden gibt, und die eine Einheit
still uebernehmen. Bei mehreren Einheiten bleibt er unveraendert.

## Fallen
- Die Plausibilitaetsbremse muss erhalten bleiben: der BELEG wandert mit ins Profil,
  nicht nur der Name. Siehe `memory/govisor-plausibilitaetsbremse.md`. Ein
  uebersprungener Schritt darf nicht bedeuten, dass eine Einheit unbelegt als belegt
  gilt.
- `confirmedEntities` muss auch im uebersprungenen Fall gefuellt werden, mit
  `beleg: "kennung"` oder `"selbstauskunft"` je nach Lage.

## Abnahme
- Ein Test fuer den Ein-Einheit-Fall, der prueft, dass das Profil danach dasselbe
  enthaelt wie nach manueller Bestaetigung.
- Ein Test fuer den Mehr-Einheiten-Fall, der prueft, dass der Schritt erscheint.
