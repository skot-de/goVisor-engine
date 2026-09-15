# Preisstufen: Radar, Dossier, Position

**Vorschlag, Stand 2026-09-15.** ⚠ Die drei Betraege sind **gesetzt, nicht gemessen**. Belegt
ist nur der Marktkorridor. Gerendert:
`claude.ai/code/artifact/1efb55f2-2746-4ec9-9273-571a013de996`.

## Der Schnitt laeuft nicht ueber die Menge

Die Preisstufen-Analyse vom 2026-08-18 hat zwei Dinge gemessen, die gegen den naheliegenden
Zuschnitt sprechen:

1. **Zwei Gruppen, nicht drei.** k-means ueber log(Volumen, Zuschlagszahl): bestes k ist in
   allen drei Laendern **2** (Silhouette DE 0,54 · AT 0,55 · CH 0,46). Die dritte Stufe ist
   eine Geschaeftsentscheidung, keine Entdeckung.
2. **Der Median gewinnt EIN Verfahren pro Jahr.** Eine Mengenstaffel sortierte damit fast alle
   nach ganz unten.

Deshalb wird nach **Tiefe der Antwort** geschnitten, und dieser Schnitt liegt im Code bereits:
`redactDetail`, `redactFirma`, `redactStrategie`, `redactMarkt` (seit 2026-08-01, ruhend hinter
`PAYWALL_ENFORCED`).

## Die drei Stufen

| | Frage | Korridor |
|---|---|---|
| **Radar** | Wo kann ich ueberhaupt bieten? | 39 bis 49 € |
| **Dossier** | Lohnt sich dieses eine Verfahren? | 99 bis 199 € |
| **Position** | Gegen wen stehe ich, und wo ist Raum? | 249 bis 599 € |

**Radar:** alle Verfahren in DE/AT/CH/LU, ober- und unterschwellig, Umkreis- und
Regionssuche, Fristenkalender, Benachrichtigungen, Herkunftskennzeichnung jeder Angabe.

**Dossier:** dazu Vergabeunterlagen im Volltext, herausgezogene Anforderungen mit Zitatbeleg,
Leistungsverzeichnis nach Positionen, vollstaendige Vorgangsakte mit Kette, Bausteinbibliothek,
20 eigene Uploads im Monat.

**Position:** dazu Wettbewerber und Marktanteile, Anbieterprofile mit Zahlen, gebundenes
Volumen, Marktchancen-Radar, Historie ab 2004, Amtsinhaber und Nachfolge, Partnersuche.

## ⚠ Woher die Betraege kommen, und wo die Belege aufhoeren

Belegte Marktpreise (abgerufen 2026-09-15): Vergabepilot 0 € Basis / ab 60 € · Vergabe24 ab
19 € · Deutsches Ausschreibungsblatt **49 €** · Patterno ab 99 € · DTAD nennt keinen Preis.
Korridor aus der Recherche vom 2026-07-20: 19 bis 300 €.

**Oberhalb von 99 € gibt es keinen einzigen beobachteten Anbieterpreis.** Die beiden oberen
Korridore sind aus dem Wert hergeleitet und am Markt noch zu pruefen. Die Breite eines
Korridors ist deshalb kein Spielraum, sondern das Mass der Unkenntnis.

**Wertanker fuer die obere Haelfte:** ein Angebot nach VOB/A oder VgV kostet ein Ingenieurbuero
rund **3.050 €** an interner Arbeit (50 h × 61 €); Beratertagessatz 1.200 €; einziger echter
Vergabe-Praezedenzfall fuer Erfolgsabrechnung ist eine US-Beratung mit 10.000 USD je Zuschlag.
Selbst die teuerste Stufe bleibt unter einem einzigen Angebot.

⚠ Eine frühere Begruendung war falsch: 99 € ist **nicht** die Mitte des Korridors 19–300 €
(die liegt bei 159,50 €). Dass 99 € plausibel wirkt, liegt an Patternos Startpreis.

## Drei Einwaende

1. **Dossier verspricht heute etwas, das fuer zwei Drittel leer ist.** 4.719 von 14.923
   offenen Verfahren in DE haben ausgelesene Unterlagen (32 %).
2. **Der Code kennt zwei Stufen, nicht drei.** `web/lib/tier.ts` fuehrt
   `Tier = "free" | "pro"`, alle vier Redaktionsfunktionen verzweigen binaer.
3. **Fuer den Median rechnet sich jedes Abo schwer.** Wer ein Verfahren im Jahr gewinnt, zahlt
   fuer Radar 468 € und fuer Dossier 1.188 € im Jahr.

**Empfehlung:** Radar oeffentlich anbieten, die beiden oberen Stufen zunaechst im Gespraech
verkaufen. Das prueft den Preis am Markt, statt ihn herzuleiten.
