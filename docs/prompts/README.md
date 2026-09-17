# Arbeitsvorrat nach der Vorfuehrung vom 17.09.2026

Jede Datei ist als eigenstaendiger Auftrag geschrieben: Befund, Messung, Aufgabe,
Fallen, Abnahme. Sie koennen einzeln und in beliebiger Reihenfolge abgearbeitet
werden.

## Reihenfolge nach Wirkung je Aufwand

| # | Thema | Aufwand | Warum jetzt |
|---|-------|---------|-------------|
| [04](04-analyse-ampel.md) | Analyse-Ampel sichtbar machen | klein | 10.951 fertige Auswertungen liest niemand |
| [09a](09-ladezustand.md) | Ladezustand statt „0 von 0" | klein | schlimmster Moment der Vorfuehrung |
| [03](03-filteranzeige.md) | Aktive Filter anzeigen | klein | Zaehlung existiert schon |
| [01](01-zeitfilter.md) | Zeitfilter vereinheitlichen | mittel | Filter unterschlaegt sichtbare Fristen |
| [06](06-demokonto-cpv6.md) | Demokonto auf CPV-6 | mittel | Demo zeigt das Produkt unter Wert |
| [05](05-suche.md) | Suche: Lose und Vergabenummer | mittel | 3 von 36 unauffindbar, plus Widerspruch |
| [10](10-schreibwettlauf.md) | Weitere Schreibwettlaeufe | mittel | eine Stelle behoben, Klasse offen |
| [07](07-dubletten.md) | Dubletten-Cluster schliessen | gross | 9.001 Leads, ~5 % |
| [09b](09-ladezustand.md) | Nutzlast 49,6 → 25,5 MB | gross | eine offene Entscheidung (`anf`) |
| [08](08-onboarding-schritt3.md) | Onboarding Schritt 3 | klein | 96,9 % sehen eine Ein-Element-Liste |
| [02](02-passungszahl.md) | Passungszahl | klein oder gross | Weggabelung, siehe Datei |

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
