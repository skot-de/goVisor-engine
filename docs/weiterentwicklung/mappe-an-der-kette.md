# Mappe an der Kette

**Konzept, Stand 2026-09-15.** Die Angebotsmappe haengt nicht am Kalender, sondern an der
Verfahrensakte. Wer zum zweiten Mal auf denselben Bedarf bietet, bekommt seine eigene Arbeit
von letztem Mal zurueck. Beim dritten Mal meldet sich die Mappe, **bevor** die Ausschreibung
erscheint. Gerendert: `claude.ai/code/artifact/03b4e11f-8014-4ed5-8aa0-2633160bda24`.

Der Bauweg dazu: [angebotsmodul-bauplan.md](angebotsmodul-bauplan.md).

## Der Hebel, gemessen (2026-09-15, DE)

    47.475  Verfahrensketten
    19.230  davon mit drei und mehr Gliedern
    82 %    der Wiederholungen binnen 1 bis 5 Jahren (82.743 von 100.339 Paaren)
     4.834  Ketten rechnerisch 2026/27 wieder faellig
    Median-Takt 2 Jahre · verbreitetste Takte: 1 J (6.358), 2 J (4.792), 3 J (2.607)

Ein Rahmenvertrag laeuft aus und wird neu ausgeschrieben. Dazwischen liegen im Median zwei
Jahre. Im Betrieb ist in dieser Zeit die Person gewechselt, der Ordner verschoben, die
Kalkulation in einer Datei, die niemand mehr sucht. **Der Bedarf kommt wieder, die Erinnerung
nicht.**

## Die drei Zustaende

**1 Erstbewerbung.** Kein Vorgaenger in der Kette. Die Mappe startet mit dem, was der Vorgang
hergibt: Unterlagen, Fristen, geforderte Nachweise, Losstruktur. Der Normalfall heute.

**2 Wiederkehr.** Die Kette hat einen Vorgaenger, auf den der Kunde geboten hat. Seine alten
Bausteine, die Kalkulation, die eingereichten Nachweise liegen bei — **und daneben, was sich
geaendert hat** (`anlauf_vergleich.parquet`). Bei 19.230 Ketten moeglich.

**3 Vorwarnung.** Die Kette ist rechnerisch faellig, es steht aber noch nichts drin. Die Mappe
oeffnet sich trotzdem, mit den alten Unterlagen und der Frage, ob der Kunde wieder antritt.
Vorbereitungszeit statt Fristendruck. 4.834 Ketten in 2026/27; nachgeprueft tragen 98 % davon
ihr letztes Glied ab 2022, 85 % ab 2024.

⚠ **Zustand 3 kann sonst niemand.** Fuer eine Vorwarnung braucht man die Kette, fuer die Kette
die Historie. Wer den laufenden Strom verkauft, kann nur melden, was schon veroeffentlicht ist.

## Was in einer Mappe liegt

| Bestandteil | Herkunft | Stand |
|---|---|---|
| Verfahrensakte | Ausschreibung, Korrekturen, Unterlagen, Zuschlag unter einer Nummer | gebaut |
| Anforderungen | Bindefrist, Buergschaft, Lose, Eignung, mit Zitatbeleg | gebaut |
| Leistungsverzeichnis | 1.243.063 Positionen, 93 % mit Menge, 5.831 Vorgaenge erschlossen | gebaut |
| Textbausteine | wiederverwendbare Passagen aus eigenen Angeboten | gebaut |
| Eigene Kalkulation | was der Kunde je Position angesetzt hat | zu bauen |
| Nachweise mit Ablaufdatum | Praequalifikation, Unbedenklichkeit, Versicherungen | zu bauen |
| Fristen und Zustaendigkeiten | wer macht was bis wann | zu bauen |
| Ausgang | gewonnen oder verloren, und gegen wen | Tabelle da, Erfassung fehlt |

Die linke Haelfte kommt aus unseren Daten. **Die rechte gehoert dem Kunden und erzeugt die
Wechselkosten.**

## Warum es sich selbst verstaerkt

**79 % aller Gebote stammen von Bietern, die nie namentlich genannt werden** (248.526 Gebote
in 52.971 Verfahren mit bekannter Bieterzahl, davon nur die 52.971 Gewinner bekannt). Wer
seinen eigenen Ausgang meldet, fuellt eine Zelle, die kein Wettbewerber abgreifen kann, und
bekommt dafuer beim naechsten Mal das Bild des Feldes.

## Zwei Grenzen, die ins Konzept gehoeren

⚠ **Kartellrecht.** Teilnahme und Ausgang melden ist unproblematisch. Angebotspreise zwischen
Wettbewerbern sichtbar machen kann eine abgestimmte Verhaltensweise begruenden. Preise nur
aggregiert, nie einem Einzelnen zuordenbar, keine Auswertung auf weniger als eine Handvoll
Melder. Mit den AGB anwaltlich klaeren, nicht danach.

⚠ **Eine falsche Kettenverknuepfung zeigt die falsche alte Mappe.** Von 148.745 Gliedern sind
73.421 inhaltlich eindeutig, 27.849 maschinell entschieden. Eine falsch angebotene Mappe ist
schlimmer als gar keine: bei schwacher Kette bestaetigt der Kunde die Zuordnung.
