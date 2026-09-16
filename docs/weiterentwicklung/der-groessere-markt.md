# Der groessere Markt

**Konzept, Stand 2026-09-15.** Einem deutschen Betrieb passende Vergaben im EU-Ausland
vorschlagen, mit einer Liste dessen, was ihm fehlt, um dort Chancen zu haben.

Verwandt: [mappe-an-der-kette.md](mappe-an-der-kette.md) (dieselbe Maschine, nur ueber eine
Grenze), [angebotsmodul-bauplan.md](angebotsmodul-bauplan.md) (die Lueckenliste ist Stufe 2).

## 1. Die Zusage, und warum sie so und nicht anders lautet

**Falsch:** „Dein Markt ist fuenfmal groesser, als du denkst."
**Richtig:** „Drei Dinge einmal erledigen, dann stehen dir 340 Vergaben offen."

Die Marktgroesse ist eine Schlagzeile. Sie bindet **einmal**, dann ist sie eine Lead-Liste mit
mehr Laendern drin und bindet so wenig wie die alte. Was bindet, ist ein **endlicher Aufwand
mit sichtbarem Ergebnis**: Wer sich auf unsere Empfehlung hin irgendwo registriert hat, hat
gehandelt, nicht nur gelesen. Er macht es nicht rueckgaengig, und wir sind der Grund, warum er
in diesem Markt ist.

## 2. Die drei Eimer

Das ist der Entwurfskern. Eine ungegliederte Liste mit siebzehn fehlenden Nachweisen laehmt;
dieselbe Liste, dreifach getrennt, bewegt.

| Eimer | Beispiel | Wirkung |
|---|---|---|
| **einmalig je Land** | Portalregistrierung, E-Signatur, Einheitliche Europaeische Eigenerklaerung (EEE/ESPD) | **Das Produkt.** Endlich, billig, schaltet ein ganzes Land frei. |
| **je Verfahren** | Referenzen im passenden CPV, Versicherungsnachweis, Umsatznachweis | gewoehnliche Angebotsarbeit, gehoert in die Mappe |
| **struktureller Riegel** | Sprache, nationales Praequalifikationsregister, oertliche Niederlassung | **muss frueh und ehrlich gesagt werden**, sonst arbeitet jemand ins Leere |

⚠ Der dritte Eimer ist der wichtigste fuer die Glaubwuerdigkeit. Wer erst nach drei Wochen
merkt, dass er ohne Landesregister gar nicht bieten darf, kommt nicht wieder.

## 3. Wie die Passung entsteht

Drei Signale, alle bereits gebaut, nur nie fuer diesen Zweck verbunden:

- **Was er kann** — `contractor_stats` (172.328 Zeilen): welche CPV-Klassen er gewinnt, in
  welcher Groesse, wie oft.
- **Was er auch koennte** — `cpv_adjacency` (40.742 Kanten, `cond_prob`): welche Segmente
  Firmen bedienen, die schon A bedienen. Aus 7215 folgt 7225, 7221 und 4800 zu 100 %.
- **Wo es sich lohnt** — `market_opportunity` (496 Segmente): `erfolglos_pct`,
  `single_bidder_pct`, `avg_bidders`. **Ein Neuling hat dort Chancen, wo der Wettbewerb duenn
  ist**, nicht dort, wo der Markt gross ist. Das ist der eigentliche Qualitaetsfilter des
  Vorschlags.

Ein Lead ist also gut, wenn er *passt* UND *duenn besetzt* ist. Beides zusammen gibt es
heute in keinem Ausschreibungsdienst.

## 4. Zielgruppe und Zielmaerkte, gemessen (2026-09-15)

**Wer reisefaehig ist.** Ausländeranteil an den Zuschlaegen in DE, je CPV-Abteilung:

    CPV 73  Forschung und Entwicklung      41,1 %   (3.153 Faelle)
    CPV 79  Unternehmensdienstleistungen   27,0 %   (17.221)  ← groesster Markt
    CPV 72  IT-Dienstleistungen            13,8 %   (4.584)
    CPV 48  Softwarepakete und Lizenzen     5,1 %   (729)
    CPV 30  Bueromaschinen und EDV          2,0 %
    CPV 45  Bauarbeiten                     1,7 %
            Durchschnitt aller Vergaben     4,7 %

⚠ **Ausgerechnet Softwarelizenzen reisen nicht.** „Das kann jeder liefern" stimmt technisch
und hilft nicht: Lizenzen gehen an inlaendische Reseller, weil der Vertrag Ansprechpartner,
Rechnungsstellung und Support im Land verlangt. Was reist, sind Leistungen mit Koepfen statt
Kisten.

**Zielgruppe in DE:** 13.253 Firmen in den reisefaehigen Klassen (IT-Dienste 5.059,
Unternehmensdienste 7.685, Forschung 1.380).

**Zielmaerkte.** Aus `docs/sondierung/00-uebersicht.md` (Stand 2026-09-03), Anteil erreichbarer
Unterlagen-Links:

    SI 100 %  ·  LV 100 %  ·  LT 99 %  ·  BG 97 %  ·  PT 89 %  ·  IE 86 %
    RO 85 %   ·  NL 73 %   ·  HU 64 %  ·  BE 60 %
    zum Vergleich:  DE 32 %  ·  AT Anmeldung  ·  CH 0 %  ·  FR 0 %

⚠ **Die Nachbarn sind die falschen Ziele.** AT haelt seine Unterlagen hinter einer Anmeldung,
CH ebenso. Slowenien dagegen ist „ein GET auf die Datei" (`docs/sondierung/si.md`).

⚠ **Und Unterlagen sind dort rueckwirkend holbar.** `docs/sondierung/haltbarkeit.md`
(2026-09-03): 39 von 41 Abrufen auf **14 Monate alte** Vergaben erfolgreich, in zehn Laendern.
Das gilt fuer DE gerade NICHT (Portale rotieren) und fuer LU ausdruecklich nicht (dort wird
nach Fristende entfernt). Wer also im Ausland sammelt, muss nicht warten.

## 5. Was fehlt

| Teil | Stand |
|---|---|
| Profil des Betriebs | gebaut (`contractor_stats`, `cpv_adjacency`) |
| Qualitaetsfilter duenner Wettbewerb | gebaut (`market_opportunity`) |
| **Auslaendische Leads im Bestand** | **fehlt ganz.** Bronze ist beim Ingest nach Land gefiltert; `silver/EU` haelt nur 282 mehrlaendrige Vergaben. Ein TED-Ingest fuer die Zielländer ist dieselbe Kette mit anderem Filter. |
| Portal, Sprache, Verfahrensart | aus der Bekanntmachung ableitbar (AT-Messung: `portal_url` 79 %, `language` 100 %, `procedure_type` 89 %) |
| **Eignungsanforderungen dort** | braucht die Unterlagen des Ziellands. Vokabular und Maschine stehen (`doc_checklist`), der Bestand nicht. |
| Was der Betrieb schon hat | braucht die Nachweisverwaltung aus [angebotsmodul-bauplan.md](angebotsmodul-bauplan.md) Stufe 3 |

## 6. Drei Risiken, die zum Konzept gehoeren

**Ein groesserer Markt bindet nur, wenn er auch gewinnt.** Oeffnen wir die Tuer und er
verliert fuenfmal, haben wir ihn Geld gekostet und das Instrument dreht sich gegen uns. Der
Median liegt bei drei Bietern; im Ausland ist die Ausgangslage eher schlechter. **Die
Trefferwahrscheinlichkeit gehoert neben den Vorschlag**, nicht ins Kleingedruckte.

**Es waehlt die falschen Kunden aus.** Der Median gewinnt EIN Verfahren im Jahr. Dem zu sagen,
sein Markt sei fuenfmal groesser, ist Hohn. Das Instrument passt auf die ambitionierte
Minderheit, und die ist deutlich kleiner als 13.253.

**Wir beraten dann, nicht nur informieren.** Fliegt jemand wegen einer Formalie raus, die auf
unserer Liste fehlte, ist das in seinen Augen unser Fehler. Dieselbe Haftungsfrage wie bei der
Einreichung, nur frueher. ⚠ Der dritte Eimer und eine ausdrueckliche Unvollstaendigkeits-
Kennzeichnung sind deshalb Pflicht, nicht Kuer.

## 7. Der erste Test

Ein Land, eine Branche, und erst danach mehr:

1. **Slowenien, CPV 72 (IT-Dienstleistungen).** SI ist 100 % offen, der Abruf ist ein GET,
   und der Bestand ist klein genug, um ihn ganz zu holen.
2. TED-Ingest fuer SI, Silber und Gold wie fuer jedes Land (`docs/land-onboarding.md`).
3. Unterlagen holen, `doc_checklist` darueber laufen lassen.
4. **Die Differenz messen:** Welche Anforderungen stehen in SI-Verfahren, die in
   vergleichbaren DE-Verfahren nicht stehen? Das ist die To-Do-Liste in ihrer Rohform.
5. Erst wenn diese Differenz belastbar ist, LV, LT und BG dazu.

**Groessenordnung (Schaetzung, nicht gemessen):** SI, LV, LT und BG tragen zusammen 6,9 % der
EU-Unterlagen-Links, also rund 30.000 in zwoelf Monaten. Bei einem IT-Anteil von etwa 4 %
(aus dem DE-Bestand abgeleitet) sind das grob **1.200 IT-Vergaben im Jahr** in diesen vier
Laendern. ⚠ Beide Anteile sind Naeherungen; die echte Zahl kennt erst der Ingest.
