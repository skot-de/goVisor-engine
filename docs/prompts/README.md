# Arbeitsvorrat nach der Vorfuehrung vom 17.09.2026

Jede Datei ist als eigenstaendiger Auftrag geschrieben: Befund, Messung, Aufgabe,
Fallen, Abnahme. Sie koennen einzeln und in beliebiger Reihenfolge abgearbeitet
werden.

## Reihenfolge nach Wirkung je Aufwand

| # | Thema | Aufwand | Warum jetzt |
|---|-------|---------|-------------|
| [06](06-demokonto-cpv6.md) | Demokonto auf CPV-6 | mittel | Demo zeigt das Produkt unter Wert |
| [07](07-dubletten.md) | Dubletten-Cluster schliessen | gross | 9.001 Leads, ~5 % |
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

- **[05](05-suche.md) Suche** — 2026-09-17, Commit 617b151. Lose und Vergabenummer im
  Heuhaufen; `fundstelle` hatte zwei tote Zweige. Dazu `pruefe-demoworte.mjs`, das die
  Drehbuchworte gegen den Demo-Satz faehrt — und beim ersten Lauf sofort einen Fall fand.
- **[10](10-schreibwettlauf.md) Schreibwettlaeufe** — 2026-09-17, Commit 5a151a3. Vier
  Schreiber gefunden, zwei mit Lese-Zyklus auf denselben Blob, zwei mit dauerhafter
  Spaltung Spalte/Blob. Der Wettlauf ist abgeschafft, nicht gereiht.

  Migration **eingespielt** am 2026-09-17 mit `python3 scripts/migrate.py`. Gegen die
  Datenbank geprueft: `volMin` wird gesetzt, `cpvFields` bleibt vollstaendig (Transaktion
  mit Ruecknahme). Ich hatte den Punkt faelschlich als „muss ein Mensch machen" notiert —
  der Weg steht in `memory/govisor-supabase-projekt.md`, ich hatte den veralteten
  MEMORY.md-Eintrag der GETEILTEN Instanz gelesen.

  Eine Restzeile bleibt: ein Profil traegt die Wertspanne noch nur in den Spalten. Sie
  heilt beim naechsten Speichern aus /settings von selbst.

- **[09a](09-ladezustand.md) Ladezustand** — 2026-09-17, Commit d833cf6. `loading`
  existierte und wurde von niemandem gelesen. Die neue Sonde prueft die KLASSE: 262
  `useState` geprueft, dabei `planOpen` als tote Zeile gefunden.
- **[08](08-onboarding-schritt3.md) Onboarding Schritt 3** — 2026-09-17, Commit f4da344.
  Uebersprungen bei genau einer BELEGTEN Einheit (79,5 %, nicht die im Auftrag behaupteten
  96,9 %). Der Token-Weg hatte die Abkuerzung schon — ohne die Belegpruefung.

## Offen, mit korrigierter Grundlage

- **[09b](09-ladezustand.md) Nutzlast** — die Annahme im Auftrag war falsch. Die 47 MB
  gehen nie ueber die Leitung (gzip: 5,6 MB), und die Liste braucht fast alle Felder;
  nachladbar sind 9 %, nicht 50 %. Der echte Hebel ist **Brotli** (5,65 → 2,96 MB bei
  Qualitaet 11, vorberechnet). Nicht gebaut, weil `/api/leads` ohne Anmeldung nicht
  pruefbar ist und doppelte Kodierung die Liste fuer jeden zerstoeren wuerde.

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
