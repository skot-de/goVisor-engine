# Arbeitsvorrat nach der Vorfuehrung vom 17.09.2026

Jede Datei ist als eigenstaendiger Auftrag geschrieben: Befund, Messung, Aufgabe,
Fallen, Abnahme. Sie koennen einzeln und in beliebiger Reihenfolge abgearbeitet
werden.

## Reihenfolge nach Wirkung je Aufwand

| # | Thema | Aufwand | Warum jetzt |
|---|-------|---------|-------------|
| [09a](09-ladezustand.md) | Ladezustand statt „0 von 0" | klein | schlimmster Moment der Vorfuehrung |
| [06](06-demokonto-cpv6.md) | Demokonto auf CPV-6 | mittel | Demo zeigt das Produkt unter Wert |
| [05](05-suche.md) | Suche: Lose und Vergabenummer | mittel | 3 von 36 unauffindbar, plus Widerspruch |
| [10](10-schreibwettlauf.md) | Weitere Schreibwettlaeufe | mittel | eine Stelle behoben, Klasse offen |
| [07](07-dubletten.md) | Dubletten-Cluster schliessen | gross | 9.001 Leads, ~5 % |
| [09b](09-ladezustand.md) | Nutzlast 49,6 → 25,5 MB | gross | eine offene Entscheidung (`anf`) |
| [08](08-onboarding-schritt3.md) | Onboarding Schritt 3 | klein | 96,9 % sehen eine Ein-Element-Liste |
| [02](02-passungszahl.md) | Passungszahl | klein oder gross | Weggabelung, siehe Datei |

## Erledigt

- **[04](04-analyse-ampel.md) Analyse-Ampel** — 2026-09-17, Commit 7216336. Spalte
  „Unterlagen" samt Filter und Sortierung. Dabei zwei Luecken im Verdrahtungs-Waechter
  gefunden und behoben: er zaehlte Dateinamen aus Kommentaren als Leser (28 von 74) und
  Pruefskripte ebenfalls. Und: der Fund lag seit dem 2026-08-25 auf einer Ausnahmeliste
  mit dem Vermerk „verdrahten oder streichen", drei Wochen lang unangetastet.

- **[03](03-filteranzeige.md) Filteranzeige** — 2026-09-17, Commit bba4ce8. Aktive Filter
  als einzeln abwerfbare Marken. Wertgrenzen stehen ausdruecklich EINZELN: „ab 2 Mio."
  waere gestern sichtbar gewesen. `filterMarken` liegt in Plain JS, damit der Waechter die
  echte Funktion faehrt; er geht alle 22 Arten einzeln durch.
- **[01](01-zeitfilter.md) Zeitfilter** — 2026-09-17, Commit bfe11bc. Die Reihenfolge stand
  dreimal im Code, einmal verkehrt. Jetzt einmal, als `handlungsFrist`. Ein-Monats-Horizont
  8.214 → 15.092 Leads.

## Neu aufgenommen (beim Arbeiten gefunden)

- **Zwei Tests sind rot und waren es schon vorher.** `test_kurse_sind_nicht_veraltet`
  (Waehrungskurse aelter als 30 Tage) und `test_standardtext::test_ausgabe_haelt_die_form`
  (Textmengen-Baender trennen nicht mehr, [27, 44] statt >= 54). Beides Datendrift, kein
  Codefehler — aber ein dauerhaft roter Test ist ein Waechter, den man zu ignorieren lernt.
- **Der Uebersetzungs-Waechter war gross-/kleinempfindlich.** `test_verdrahtete_texte_sind_uebersetzt`
  liess 14 neue Texte durch, weil `\b(alle|die|der…)\b` ohne `re.I` lief: jeder Satz, der mit
  einem Funktionswort BEGINNT, galt als nicht-deutsch. Behoben. Fund dabei: `Zur Startseite`
  im Onboarding stand fuer EN- und FR-Besucher auf Deutsch.
- **`firma-index.json` und `doc-listing-index.json`** stehen weiterhin auf der
  Ausnahmeliste in `pruefe_verdrahtung.py`, beide seit dem 2026-08-25 „geschrieben, nie
  gelesen". Jetzt, wo die Sonde schaerfer misst, lohnt die Entscheidung: verdrahten oder
  streichen.

## Was nicht in dieser Liste steht

- **Entity-Zusammenfuehrung fuer den Gesamtbestand.** Eigenes Thema, Vorarbeit liegt
  in `scripts/pruefe_entity_dubletten.py` und `memory/govisor-entity-fragmentierung-klostermann.md`.
- **`Confirm email` in Supabase wieder einschalten.** Fuer die Vorfuehrung
  ausgeschaltet. Muss Sven selbst tun, ich habe die Rechte nicht.

## Zwei Fehler von mir am Tag der Vorfuehrung, damit sie nicht weiterwirken

1. **„Such nach Ubstadt" war ein Fehlgriff.** Geprueft hatte ich gegen den
   Vollbestand. Im geduennten Demo-Datensatz kommen weder Rottweil noch Ubstadt vor.
   Daraus die Regel in [05](05-suche.md): Drehbuchworte gegen die DEMO-Daten pruefen.

2. **„Das Onboarding fuellt die CPV-6-Codes nicht" war falsch.** Der Onboarding-Weg
   traegt sie durchgehend, 98,1 % der Firmen haben sie. Nur `demo_konto.py` laesst sie
   fallen. Das steht jetzt richtig in [06](06-demokonto-cpv6.md).
