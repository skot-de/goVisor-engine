# Betriebskosten und Marge

**Stand 2026-09-15.** Mengen am laufenden Bestand gemessen, Listenpreise am 2026-09-11
nachgeschlagen. Gerendert: `claude.ai/code/artifact/f2ae2476-b7ac-4585-9d6b-45d412d914cc`.

## Fixkosten: 700 € im Monat

| Posten | Betrag | Skaliert mit |
|---|---:|---|
| Dokumentenanalyse (LLM) | 80 $ | Dokumentenmenge |
| Pipeline-Maschine (Strom + anteilige Abschreibung) | 30 € | eigene Hardware |
| Supabase Pro | 25 $ | bis 100.000 aktive Nutzer |
| Vercel Pro | 20 $ | Sitzplaetze, nicht Nutzer |
| Mailversand (Resend) | 20 $ | **heute ein Platzhalter** |
| Schreibvorgaenge R2 (0,22 Mio. berechnet) | 0,99 $ | Dateianzahl |
| Buchhaltung (Lexware Office L) | 22 € | fest |
| Mail/Kalender/Ablage | 12 € | je Person |
| Vermoegensschadenhaftpflicht | 60 € | fest |
| Rechtliches laufend, Cyber, Konto, Kammer, Vertriebswerkzeuge | 240 € | fest |
| **Summe** | **700 €** | 166 € Technik, 534 € Verwaltung |

⚠ **Die Verwaltung ist mehr als das Dreifache der Technik.** Wer nur die Server rechnet,
rechnet ein Viertel.

## Variabel: 1,00 € je Abonnent

Einzug per SEPA-Lastschrift ueber **Stripe** (gesetzte Annahme): 0,35 € Einzug + 0,34 €
Stripe Billing (0,7 % von 49 €) + 0,08 € Ruecklage (3,50 € je gescheitertem Einzug bei 1 %,
15 € je Rueckbuchung bei 0,3 %) + 0,22 € Analyse hochgeladener Unterlagen + 0,01 € Rechenzeit.
Datenverkehr 201 MB/Monat, im Kontingent.

**Zahlungswege im Vergleich** (49 € Monatspreis, Preise 2026-09-11):
Mollie Lastschrift 0,35 € · **Stripe Lastschrift 0,69 €** · Mollie EWR-Karte 1,13 € ·
Stripe EWR-Karte 1,33 € · Paddle 2,91 €.

⚠ **Warum Stripe trotz Mollie.** Mollies 0,35 € sind reiner Einzug. Lexware fuehrt danach die
Buecher, schreibt aber keine 500 Aborechnungen und mahnt keine Rueckläufer. Diese Schicht
steckt bei Stripe in den 0,7 %. Der Aufpreis von 0,34 € je Abo ist zugleich das Budget, sie
selbst zu bauen: bei 500 Abonnenten 170 € im Monat. **Ein Wechsel zu Mollie lohnt sich ab
einigen hundert Kunden.**

⚠ Eine SEPA-Rueckbuchung ist **endgueltig**, es gibt kein Widerspruchsverfahren wie bei der
Karte. Vor jedem Einzug ist der Kunde vorab zu informieren, und es braucht ein Mandat: der
Mailversand traegt also Benachrichtigungen UND Vorabankuendigungen.

## Marge (49 €, ohne Gehalt)

| Abonnenten | Umsatz | Kosten | Marge | Deckungsbeitrag |
|---:|---:|---:|---:|---:|
| 15 | 735 € | 715 € | 2,7 % | 20 € |
| 50 | 2.450 € | 750 € | 69,4 % | 1.700 € |
| 100 | 4.900 € | 800 € | 83,7 % | 4.100 € |
| 500 | 24.500 € | 1.200 € | 95,1 % | 23.300 € |
| 1.000 | 49.000 € | 1.700 € | 96,5 % | 47.300 € |

**Deckung ab 15 Abonnenten.** Ab etwa 90 traegt der Ueberschuss ein Gehalt von 4.000 €
(rund 5.000 € Aufwand fuer die Gesellschaft).

## Das Roharchiv bleibt lokal

282,3 GB Vergabeunterlagen, Zuwachs **74 GB im Monat** (Median 2,47 GB/Tag ueber acht
Septembertage), also rund 1,17 TB in zwoelf Monaten. Vier Jahre Cloud kosten ~1.340 €, ein
gespiegeltes SSD-Paar ~500 €, und der Nachtlauf braucht die Dateien ohnehin lokal.

⚠ **Der Spiegel ersetzt keine Sicherung, aber sie ist fast geschenkt:** aus 282,3 GB ZIPs sind
1,07 GB gewonnen (Volltext, Positionen, Analysen), ein Verhaeltnis von **264 zu 1**. Diese
1,07 GB ausser Haus zu sichern kostet zwei Cent im Monat. Geht alles verloren, fehlt nur die
Moeglichkeit, mit einem besseren Parser neu auszulesen, nicht das Produkt.

## ⚠ Zwei Baustellen, die Geld kosten koennen

1. **Die Lead-Route schickt dem Browser die ganze Branchendatei**, ungefiltert (50 MB roh,
   5,9 MB komprimiert fuer Bau). Das skaliert mit der **Datenmenge**, nicht mit den Nutzern.
2. **Objektspeicher-Wahl entscheidet ueber 0 oder 135 $**: der Server laedt bei jedem
   Kaltstart eine 50-MB-Datei nach. Diese Rechnung unterstellt durchgehend Null-Egress (R2).

## Was nicht drinsteht

Kundengewinnung (der groesste Posten, vor den ersten zwanzig Kunden nicht bezifferbar),
Rechtliches vor dem Start (einmalig 1.500 bis 3.000 €), Arbeitszeit, Schadsoftware-Pruefung,
Marke (~300 € einmalig).
