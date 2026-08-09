# goVisor — Preismodell & Feature-Zuordnung

**Version:** 1.4
**Stand:** 2026-07-30
**Zweck:** Zuordnung aller Features zu den Stufen · Grundlage für Preisseite und Gating
**Grundlage:** Feature-Matrix v2.0, Marktpreis-Recherche 07/2026, Tickets #1–#25
**Changelog:** 1.0 Erstfassung nach Features · 1.1 Zuordnung auf Bereiche und Tabs umgestellt; Firmenprofil in zwei Tabs geteilt · 1.2 Netzwerk-Grenze definiert (Free passiv, Pro aktiv) · 1.3 Prämien-Auslöser um die Unterlagen-Analyse erweitert · 1.4 Preistafeln festgehalten (Rabattmechanik 10,25 Monate, Vergabestellen-Preise, Zahlungsarten)

---

## 1. Die Leitregel

> **Was pro Ausschreibung passiert, ist unbegrenzt. Was über Ausschreibungen hinweg geht, staffelt.**

Begründung: goVisor verdient über die Erfolgsprämie an **analysierten** Leads mit. Ein Mengenlimit auf
Analysen arbeitet gegen das eigene Geschäftsmodell — jeder nicht aufgeschlossene Lead ist eine
verlorene Prämienchance. Die Staffel greift deshalb dort, wo Funktionen **erst ab einer bestimmten
Marktaktivität Sinn ergeben**: Wer fünf Ausschreibungen im Jahr macht, braucht keine
24-Monats-Pipeline und keine Wettbewerbslandschaft.

Die Trennlinie ist **operativ gegen strategisch**, nicht „viel gegen wenig".

---

## 2. Die Stufen

| Stufe | Wofür | Wer |
|---|---|---|
| **Free** | Kennenlernen. Alles sichtbar, Pro-Funktionen 3× nutzbar. | Nichtnutzer, Gelegenheitsbieter |
| **Pro (+)** | Der komplette Vorgang je Ausschreibung — unbegrenzt. | Regelmäßige Bieter |
| **Premium (++)** | Strategische Marktbearbeitung über Ausschreibungen hinweg. | Systematische Marktbearbeiter, Bid-Teams |

**Erfolgsprämie:** eigene Achse, an Pro und Premium gekoppelt, kein Stufenmerkmal.
**Ergebnisdaten-Reziprozität:** eigene Achse, unabhängig von der Stufe — nie bepreisen.

---

## 3. Zuordnung nach Navigation — Anbieterseite

Die Stufe hängt am **Bereich beziehungsweise Tab**, nicht am einzelnen Feature. Das ist im Interface
eindeutig kennzeichenbar und für den Nutzer nachvollziehbar.

**Grundsatz: eine Stufe je Tab.** Wo ein Tab gemischt wäre, wird er geteilt (§3.5). Ein Tab, in dem
manches nutzbar und manches gesperrt ist, ist weder erklärbar noch verkaufbar.

### 3.1 Bereiche (Navigationsleiste)

| Bereich | Stufe | Begründung |
|---|:---:|---|
| **Akquise** (Liste + Lead-Detail) | gemischt je Tab → §3.2 | Kern des Produkts |
| **Merkliste / Cockpit** (#17) | **+** | Arbeitswerkzeug, setzt regelmäßige Teilnahme voraus |
| **Netzwerk** (Partnersuche, Freigaben) | gemischt → §3.9 | Free passiv, Pro aktiv |
| **Strategie** (8 Sektionen) | **++** | über Ausschreibungen hinweg |
| **Profil** (Bausteine, Import, Einstellungen) | **Free** | Bausteine kosten nichts und binden |

### 3.2 Lead-Detail — Tabs

| Tab | Stufe | Inhalt |
|---|:---:|---|
| Übersicht | **Free** | Eckdaten, Lose, Wettbewerbslage, Leistungsort |
| Teilnahme | **Free** | Fristen, Link zu den Vergabeunterlagen (#13, #16) |
| **Unterlagen** | **+** *(Free 3×)* | Upload, Checkliste, Textbausteine (#23) |
| **Bewertung** | **+** *(Free 3×)* | Direktvergleich, Wechselwahrscheinlichkeit, Anforderungen, Aufwand, Bid/No-Bid (#3/#15/#18/#19) |
| Vergabestelle | **+** | Vergabeverhalten dieser Stelle |
| Markt | **+** | Wettbewerbsumfeld dieser Ausschreibung |
| Team | **+** | interne Zuordnung |

> **Unterlagen und Bewertung lösen die Erfolgsprämie aus.** Wer die Vergabeunterlagen durchgearbeitet
> oder die Bewertung geöffnet hat, hat den Lead analysiert. Beide Tabs liegen deshalb in Pro und sind
> dort unbegrenzt — jede Sperre würde die Prämienbasis verkleinern.
>
> **Ein Lead, ein Auslöser:** Wer beide Tabs nutzt, löst nicht zweimal aus. Der 12-Monats-Cutoff läuft
> ab der ersten auslösenden Handlung.

### 3.3 Zuschlag-Detail — Tabs (#24)

| Tab | Stufe |
|---|:---:|
| gesamter Bereich inkl. Liste, Detail, Alert | **++** |
| Spiegelseite „Ihr habt gewonnen" | **+** |

> Die Spiegelseite gehört in Pro: Wer selbst gewinnt, soll Partner finden können — das füttert das
> Netzwerk und ist kein strategisches Werkzeug.

### 3.4 Cockpit — Bereiche (#17)

| Bereich | Stufe |
|---|:---:|
| Beobachtet (Merkliste) | **Free** |
| Aktiv (Pipeline) | **+** |
| Historie | **+** |

> Die Merkliste bleibt frei, damit Free-Nutzer Leads sammeln können — das erzeugt Bindung und später
> Ergebnisdaten.

### 3.5 Firmenprofil — muss geteilt werden (#25)

Heute eine durchgehende Seite mit gemischtem Wert. Für die Stufenlogik wird sie in **zwei Tabs**
geschnitten:

| Tab | Stufe | Inhalt |
|---|:---:|---|
| **Übersicht** | **+** *(Free 3×)* | Identität, Zuordnungsgüte, Kennzahlen, Leistungsfelder, Regionen |
| **Angriffspunkte** | **++** | Wo das Unternehmen festsitzt · Was dort ausläuft · Kopf an Kopf · weitere Signale · Beobachten |

**Bau-Konsequenz für #25:** Die Seite erhält eine Tab-Leiste. Die Sektionen aus dem Ticket werden
entsprechend verteilt — §5.1 bis §5.5 wandern in „Angriffspunkte", §4 bleibt in „Übersicht".

### 3.6 Strategie — Sektionen (#10)

| Sektion | Stufe |
|---|:---:|
| Pipeline · Felder · Vergabestellen · Wettbewerb | **++** |
| Position · Fähigkeiten · Bindung · Profil | **++** |

Der gesamte Bereich ist Premium. Keine Ausnahme, kein Free-Kontingent.

### 3.7 Querschnitt: was überall frei ist

| Element | Stufe | Begründung |
|---|:---:|---|
| Herkunfts-Flags (gemessen/geschätzt/unbekannt) | **Free** | Ehrlichkeitsprinzip gilt in jeder Stufe |
| Suche, Filter, Lead-Liste | **Free** | kostet nichts, schafft Reichweite |
| Bausteinbibliothek + Import (#23) | **Free** | Speicher kostet nichts, bindet stark |
| Netzwerk: Freigabe, Interesse bekunden, antworten | **Free** | Beiträge nie bepreisen — Dichte (§3.9) |
| Eigene Teilnahmen privat tracken | **Free** | Kaltstart-Löser für die Ergebnisdaten (#11) |

### 3.8 Eigene Achsen

| Achse | Regel |
|---|---|
| **Erfolgsprämie** | ab **+** · 7 Bänder 600–25.000 € · **Auslöser: Unterlagen-Analyse oder Bewertungs-Tab**, je Lead nur einmal · 6 Monate Schonfrist · nur auf echtem Wert · Free-Analysen zählen mit, sofern bei Zuschlag ein Paid-Account besteht |
| **Ergebnisdaten-Reziprozität** | stufenunabhängig · wer meldet, sieht die Wettbewerbsmenge · **nie bepreisen** |

### 3.9 Netzwerk — Free ist passiv, Pro ist aktiv

Das Netzwerk lebt von Dichte. Beiträge dürfen deshalb nie hinter eine Bezahlschranke — wer etwas
**gibt**, darf das in jeder Stufe. Bezahlt wird das **aktive Suchen und Ansprechen**.

| Handlung | Free | + | ++ |
|---|:---:|:---:|:---:|
| Firmenprofil im Netzwerk anlegen, Freigabe setzen | ○ | ○ | ○ |
| **Interesse an einem Los bekunden** | ○ | ○ | ○ |
| Von anderen gefunden und angesprochen werden | ○ | ○ | ○ |
| Auf eine Anfrage antworten | ○ | ○ | ○ |
| Eigene Bekundungen verwalten und zurückziehen | ○ | ○ | ○ |
| **Sehen, wer sonst Interesse an dieser Vergabe hat** | — | ○ | ○ |
| **Partner aktiv suchen und filtern** | — | ○ | ○ |
| Andere von sich aus ansprechen | — | ○ | ○ |
| Zuschlagsgewinner kontaktieren (#24) | — | — | ○ |

**Begründung der Grenze:** Die interessantesten Partner bei Mehr-Los-Vergaben sind oft kleine,
regionale Anbieter, die genau ein Los abdecken — typische Free-Nutzer. Dürften nur Zahlende bekunden,
suchte ein Pro-Kunde in einem leeren Pool und zahlte für ein Feature ohne Gegenüber. Und wer
angesprochen wird, muss antworten können, sonst ist die Kette einseitig.

**Verifizierung statt Bezahlung:** Interesse bekunden darf, wer ein bestätigtes Firmenprofil hat
(`entity_confidence` = confirmed). Das filtert Wegwerf-Accounts, ohne Dichte zu kosten.

**Free-Erlebnis:** Der Free-Nutzer sieht, dass es Interessenten gibt („4 Unternehmen haben Interesse an
Los 2 bekundet"), aber nicht wer — Blur mit Premium-CTA. Angesprochen zu werden bleibt der Weg, auf dem
er das Netzwerk erlebt.

---

## 4. Free: alles sichtbar, Pro-Funktionen dreimal nutzbar

Kein verstecktes Produkt. Jede Funktion ist **im Interface vorhanden** — aber in zwei Zuständen:

- **Pro-Funktionen:** dreimal echt nutzbar, danach gesperrt.
- **Premium-Funktionen:** dauerhaft nur sichtbar, nie nutzbar — auch nicht einmal.

### 4.1 Die drei Darstellungsformen

| Form | Wo | Warum |
|---|---|---|
| **Echte Nutzung (3×)** | Pro-Funktionen | Der Nutzer erlebt den vollen Wert an seinen eigenen Daten |
| **Demowerte** | Premium-Funktionen + verbrauchte Pro-Funktionen, wo die Struktur den Wert zeigt | Strategie-Sektionen, Firmenprofil-Kennzahlen — die Form ist die Botschaft |
| **Blur** | Premium-Funktionen + verbrauchte Pro-Funktionen, wo der Einzelwert die Botschaft ist | Auslaufliste, Kopf-an-Kopf, Wechselwahrscheinlichkeit |

**Regel für die Wahl:** Ist die *Struktur* aussagekräftig (eine Pipeline-Kurve, eine
Wettbewerbstabelle), zeigen Demowerte den Nutzen besser als ein Weichzeichner. Ist der *konkrete Wert*
die Botschaft („dieser Vertrag läuft im März 2027 aus"), ist Blur ehrlicher — Demowerte wären dort
irreführend.

**Pflicht bei Demowerten:** deutlich als Beispiel gekennzeichnet, niemals mit echten Daten verwechselbar.

### 4.2 CTA-Regeln

| Situation | CTA |
|---|---|
| Vor Verbrauch (noch Nutzungen übrig) | Zähler sichtbar: „2 von 3 Analysen diesen Monat" |
| Nach Verbrauch, Pro-Feature | „Unbegrenzt mit Pro" + was konkret freigeschaltet wird |
| Premium-Feature (in Free wie in Pro) | Premium-CTA mit Nutzenbezug auf **diese** Ansicht — kein Zähler, da nie nutzbar |
| Bei Premium-Feature, Nutzer hat Pro | kein Zähler, direkter Premium-CTA mit Begründung |

**Nie:** generisches „Jetzt upgraden". Der CTA benennt immer, was diese eine Ansicht liefert.

### 4.3 Zählweise

Die Einheit ist der **Lead**, nicht die einzelne Analyse. Wer einen Lead aufschließt, hat alle
Vorgangs-Funktionen daran frei — dauerhaft, auch über den Monatswechsel hinaus.

Zweites, getrenntes Kontingent: **3 Firmenprofile** — gezählt wird das Öffnen des Tabs „Übersicht".
Strategie, Zuschlagsphase und der Tab „Angriffspunkte" haben **kein** Kontingent — sie sind Premium
und in Free nie nutzbar.

Begründung: Ein Verfahren zieht sich oft über Monate. Ein Lead, für den man erneut zahlen müsste, wäre
absurd.

---

## 5. Vergabestellenseite

Eigene Logik — die Stelle gewinnt nichts, plant nur. Keine Erfolgsprämie.

| Feature | Erst-Einblick | Check | Abo |
|---|:---:|:---:|:---:|
| Dashboard (Bieterzahl, Aufhebungsquote, KMU-Anteil) | ○ | ○ | ○ |
| Eine Markterkundungs-Kennzahl | ○ | ○ | ○ |
| Ausschreibungscheck (ein Entwurf) | — | ○ | ○ |
| Analysedokument zum Entwurf | — | ○ | ○ |
| Markterkundung, Wettbewerbsdichte, Anbieter-Verfügbarkeit | — | — | ○ |
| Zuschnitt-Optimierung / Bieterzahl-Prognose | — | — | ○ |
| Vergleichbare Vergaben (Comps) | — | — | ○ |
| Vergabe-Güte, Auftragnehmer-Beobachtung ⚖️ | — | — | ○ |
| Eigene Vergabe-Vorschau | — | — | ○ |
| KMU-Förderung, Preis-vs-Qualität-Benchmark | — | — | ○ |

**Kein Dauer-Freemium:** Der Erst-Einblick ist ein einmaliger Türöffner. Behörden kaufen
vorgangsgebunden; ein dauerhafter Gratis-Tier erzeugt hier keinen Netzwerkwert (anders als bei Bietern,
die Dichte und Ergebnisdaten liefern).

---

## 6. Preisniveau — Marktvergleich

Recherchestand 07/2026:

| Anbieter | Preis/Monat | Leistung |
|---|---|---|
| Vergabe24 | 18 € | reine Suche |
| AusschreibungsRadar | 9 / 29 / 79 / 149 € | Watchlist bis Bid/No-Bid + CRM |
| Vergabepilot | 0 / 60 / 125 € | KI-Suche 300+ Portale, KI-Assistent |
| BidFix | 0 / ab 79 € | Suche bis Angebotserstellung |
| Patterno | 99 / 499 / 2.499 € | KI-Suche, Branchenmodule, Marktintelligenz |
| DTAD | auf Anfrage | größte Quellenabdeckung |

**Erwartungshaltung im Markt** (Patterno-Einordnung): KMU mit regelmäßiger Teilnahme 100–500 €/Monat,
Mittelstand mit Bid-Team 500–2.000 €/Monat.

**Marktdurchdringung:** DTAD nennt >5.500 Kunden — bei rund 150.000 bietenden Unternehmen liegt die
Durchdringung im niedrigen einstelligen Prozentbereich. **Der Hauptwettbewerber ist „kein Tool".**

### 6.1 Preistafel Anbieterseite

| Stufe | Monatszahlung | Jahreszahlung | rechnerisch 12× | Rabatt |
|---|---|---|---|---|
| **Pro (+)** | 99 €/Mon | **1.019 €/Jahr** | 1.188 € | 14,2 % |
| **Premium (++)** | 249 €/Mon | **2.559 €/Jahr** | 2.988 € | 14,4 % |
| **Founding Pro** | 49 €/Mon | **509 €/Jahr** | 588 € | 13,4 % |
| **Founding Premium** | 149 €/Mon | **1.529 €/Jahr** | 1.788 € | 14,5 % |

**Rabattmechanik:** Der Jahrespreis entspricht **10,25 Monatspreisen** (12 minus 1,75 Monate),
kaufmännisch aufgerundet auf eine 9er-Endung. Kein Monatsaufschlag — der Monatspreis ist der
Listenpreis, der Jahrespreis der Vorteil.

**Founding:** die ersten **50 Kunden**, Preis **unbegrenzt gültig**, solange das Abo läuft. Gilt für
alle Founding-Kunden gleich — persönliche Kontakte zahlen nicht mehr und nicht weniger als spätere.

**Zahlungsart:** SEPA-Lastschrift als Voreinstellung, Karte als Alternative. SEPA kostet pauschal
0,35 € statt 1,5 % + 0,25 € — bei Premium monatlich rund 44 € Ersparnis pro Kunde und Jahr, also
deutlich mehr als der Gebühreneffekt der Jahresabrechnung (rund 10 €).

**Zur Einordnung:** Der Jahresrabatt ist ein **Cashflow- und Bindungsinstrument**, kein
Kostenoptimierer. Die Gebührenersparnis durch eine statt zwölf Buchungen liegt bei 4–10 € je Kunde
und Jahr und steht in keinem Verhältnis zum Rabatt.

### 6.2 Preistafel Vergabestellen (Vergabeblick)

| Angebot | Preis | Logik |
|---|---|---|
| Erst-Einblick | **0 €** | einmalig, Türöffner — kein Dauer-Freemium |
| Einzel-Ausschreibungscheck | **490 €** | ein Verfahren, ein Gutachten |
| **Jahresabo** | **3.900 €** | entspricht 8 Checks — lohnt ab regelmäßiger Nutzung |

**Nur Jahresabo, kein Monatspreis.** Behörden budgetieren im Haushaltsjahr; ein Monatsabo passt weder
zum Rhythmus noch zur Beschaffungspraxis und erzeugt zwölf Rechnungen statt einer.

**Vergaberechtliche Einordnung (entscheidend):** Direktaufträge für Liefer- und Dienstleistungen sind
auf Bundesebene bis **15.000 € netto** zulässig (UVgO, befristete Regelung; geplante dauerhafte
Anhebung auf 50.000 €), Länder oft darüber. Alle drei Preise liegen deutlich darunter — eine
Vergabestelle kann Vergabeblick **formlos beauftragen**, ohne ein eigenes Vergabeverfahren
durchzuführen. Das ist ein wesentlicher Vertriebsvorteil und begrenzt zugleich den Preisspielraum
nach oben: Ab 15.000 € kippt der Kauf in ein Verfahren und der Verkaufszyklus verlängert sich massiv.

**Warum 3.900 und nicht höher:** Der Markt ist neu, die Zahlungsbereitschaft ungetestet, und ein
niedrigerer Betrag rutscht auch bei restriktiveren Landesregelungen sicher in den formlosen Bereich.
Nach oben ist später jederzeit möglich, nach unten kaum.

**Rechnungsstellung:** Kauf auf Rechnung mit XRechnung und Leitweg-ID über die OZG-Rechnungs­
eingangsplattform ist Pflicht für diese Zielgruppe — Kartenzahlung allein reicht nicht. Am Anfang
manuell (kostenloser Generator + OZG-RE-Upload), Automatisierung erst ab Volumen.

## 7. Offene Entscheidungen

| # | Punkt | Anmerkung |
|---|---|---|
| 1 | Teamgröße als Zusatzachse? | aktuell nicht vorgesehen — prüfen, wenn Bid-Teams kaufen |
| 2 | Free-Kontingente (3 Leads / 3 Firmenprofile) | an realen Kosten und Konversion justieren |
| 3 | **Tickets #6b (Billing) und #23 nachziehen** | Prämien-Auslöser umfasst jetzt auch die Unterlagen-Analyse |
| 4 | Stripe-Konditionen im eigenen Konto gegenprüfen | Quellen nennen 1,4–1,5 % für EWR-Karten; SEPA-Deckelung prüfen |
| 5 | Landesspezifische Direktauftragsgrenzen | für den Vertrieb je Bundesland dokumentieren |
