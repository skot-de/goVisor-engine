# AGB: Entwurf und Entscheidungsvorlage

> **Status: Entwurf, bewusst nicht als Seite veröffentlicht.** Stand 2026-10-02.

## Warum dies ein Dokument ist und keine Seite

Impressum und Datenschutzerklärung sind **Pflichtangaben**: sie beschreiben, was ohnehin
gilt, und sie müssen vor dem Start da sein. Beide stehen deshalb als Seite im Code.

AGB sind etwas anderes. Sie sind ein **Vertrag**, den du einseitig stellst, und sie werden
an §§ 305 ff. BGB gemessen. Eine unwirksame Klausel fällt dabei nicht einfach weg, sondern
wird durch das Gesetz ersetzt, und das Gesetz ist im Zweifel strenger als das, was du
gewollt hättest. Eine Haftungsklausel, die zu weit greift, ist am Ende gar keine.

Dazu kommt: **es gibt noch nichts zu verkaufen.** Gemessen am 2026-10-02 sind sowohl der
Zahlungsweg (`web/lib/stripe.ts`) als auch der Mailversand (`web/lib/email.ts`)
Integrations-Stubs ohne Schlüssel. Ohne Vertragsschluss gegen Entgelt gibt es keinen
Anwendungsfall für AGB, der heute drängt. Es gibt ihn am Tag des ersten bezahlten Zugangs,
und bis dahin ist dies die Vorlage.

⚠ **Dieses Dokument ist keine Rechtsberatung.** Es ist eine fachlich fundierte Gliederung
mit den Stellen, an denen deine Entscheidung fehlt, damit die anwaltliche Durchsicht kurz
und billig wird statt lang und teuer.

---

## Die acht Entscheidungen, die vor dem Text stehen

Ohne diese Antworten lässt sich der Text nicht schreiben, nur raten.

| # | Entscheidung | Warum sie den Text prägt |
|---|---|---|
| 1 | **Nur Unternehmer oder auch Verbraucher?** | Der Unterschied zieht sich durch alles: Widerrufsrecht, zulässige Haftungsklauseln, Gerichtsstand. goVisor richtet sich an Anbieter in Vergabeverfahren, also faktisch an Unternehmer. Dann gehört eine klare Beschränkung auf Unternehmer in § 1 und die Registrierung muss das abfragen. |
| 2 | **Was genau wird geschuldet?** | Zugang zu einer Auswertung, nicht ein Ergebnis. Das muss dastehen, sonst schuldest du im Streitfall die Prognose. |
| 3 | **Laufzeit, Verlängerung, Kündigungsfrist** | `supabase/0015_abo_laufzeit.sql` legt eine Abo-Laufzeit an; die Fristen stehen nirgends. ⚠ Bei Verbrauchern gilt § 309 Nr. 9 BGB, bei automatischer Verlängerung zusätzlich die Kündigungsbutton-Pflicht. |
| 4 | **Preise und Preisänderung** | `govisor/pricing.py` ist seit 2026-08-17 gelöscht. Ohne Preismodell keine Preisklausel. |
| 5 | **Verfügbarkeit** | Sagst du eine Quote zu? Wenn ja, welche, und was passiert bei Unterschreitung? Wenn nein, muss das als Nicht-Zusage dastehen. |
| 6 | **Haftung** | Der heikelste Punkt bei diesem Produkt, siehe unten. |
| 7 | **Nutzungsrechte an hochgeladenen Unterlagen** | Der Nutzer lädt Vergabeunterlagen hoch. Darfst du daraus die Bausteinbibliothek speisen, und wenn ja, in welcher Form? ⚠ `govisor/pii.py` schwärzt beim Baustein-Import, nicht beim Upload. |
| 8 | **Daten bei Vertragsende** | Wie lange bleiben Profil, Merkliste und Unterlagen abrufbar, wann wird gelöscht? Muss zur Datenschutzerklärung passen, sonst widersprechen sich zwei Texte. |

---

## ⚠ Der Punkt, an dem dieses Produkt anders ist als andere SaaS

goVisor verkauft **Prognosen und abgeleitete Kennzahlen**: Verdrängbarkeit, erwartete
Neuvergabe, Wertbänder. Das ist etwas anderes als eine Datenbank, die Veröffentlichungen
weiterreicht. Zwei Folgen:

**Erstens muss der Vertragsgegenstand die Ableitung als Ableitung benennen.** Wer liest,
dass er eine Prognose kauft, kann nicht später den Eintritt verlangen. Steht es nicht da,
ist die Abgrenzung im Streitfall deine Aufgabe.

**Zweitens trägt das Produkt diese Unterscheidung bereits in den Daten.** Das ist dein
stärkstes Argument und es gehört in den Vertragstext, nicht nur in die Oberfläche: goVisor
kennzeichnet bei jeder Angabe, ob sie gemessen, geschätzt oder unbekannt ist, weist
umgerechnete Beträge als umgerechnet aus und nennt die Quelle je Wert. Ein Haftungsabschnitt,
der darauf verweist, beschreibt etwas Überprüfbares statt eine Schutzbehauptung.

⚠ **Was nicht geht:** eine pauschale Freizeichnung für alle Schäden. Unwirksam sind
Ausschlüsse für Vorsatz und grobe Fahrlässigkeit, für Schäden an Leben, Körper und
Gesundheit sowie für die Verletzung wesentlicher Vertragspflichten (Kardinalpflichten).
Der übliche und haltbare Weg ist: unbeschränkt für die genannten Fälle, bei einfacher
Fahrlässigkeit begrenzt auf den vertragstypischen vorhersehbaren Schaden.

---

## Gliederung

1. **Geltungsbereich und Vertragspartner** (Entscheidung 1)
2. **Vertragsgegenstand**: Zugang zur Auswertungsplattform. Ausdrücklich: Prognosen und
   abgeleitete Kennzahlen, keine amtliche Auskunft, kein zugesichertes Ergebnis.
   Verbindlich bleibt die Bekanntmachung der Vergabestelle.
3. **Registrierung und Konto**: Angaben wahrheitsgemäß, Zugangsdaten geheim, ein Konto je
   Nutzer. Hier auch die Prüfung der Unternehmenszugehörigkeit erwähnen, weil sie in die
   Registrierung eingreift.
4. **Leistungsumfang und Änderungen**: Welche Pakete, was sie enthalten (Entscheidung 4),
   Weiterentwicklung erlaubt, wesentliche Verschlechterung mit Ankündigung und
   Sonderkündigungsrecht.
5. **Verfügbarkeit** (Entscheidung 5). Wartungsfenster und Störungen außerhalb des
   Einflussbereichs ausnehmen.
6. **Pflichten des Nutzers**: keine automatisierten Massenabrufe, keine Weitergabe der
   Zugangsdaten, keine Weiterveräußerung der Auswertungen. ⚠ Beim Upload: keine
   Unterlagen mit personenbezogenen Daten Dritter, dieselbe Aussage wie in der
   Datenschutzerklärung.
7. **Nutzungsrechte** (Entscheidung 7). Zwei Richtungen trennen: was der Nutzer mit den
   Auswertungen darf, und was du mit seinen Uploads darfst.
8. **Vergütung und Zahlung** (Entscheidung 4).
9. **Laufzeit und Kündigung** (Entscheidung 3).
10. **Haftung** (siehe oben).
11. **Datenschutz**: Verweis auf die Datenschutzerklärung, keine abweichenden Regelungen.
12. **Änderungen der AGB**: Ankündigungsfrist, Widerspruchsmöglichkeit.
13. **Schlussbestimmungen**: deutsches Recht, Gerichtsstand Hamm bei Unternehmern,
    salvatorische Klausel. ⚠ Eine Gerichtsstandsvereinbarung ist gegenüber Verbrauchern
    unwirksam, deshalb hängt auch das an Entscheidung 1.

---

## Was ich bauen kann, sobald die acht Entscheidungen stehen

Die Seite selbst ist eine halbe Stunde: `web/app/agb/page.tsx` nach demselben Muster wie
Impressum und Datenschutzerklärung, Verdrahtung über `RECHTLICHES` in
`web/middleware.ts`, Eintrag in der Sitemap, Prüfungen in `tests/test_rechtstexte.py`.

⚠ Vor der Veröffentlichung gehört der Text einmal durch eine anwaltliche Durchsicht. Was
hier steht, macht diese Durchsicht kurz, es ersetzt sie nicht.
