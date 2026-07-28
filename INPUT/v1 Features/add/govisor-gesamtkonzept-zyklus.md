# goVisor — Gesamtkonzept: Der Vergabezyklus (v3)

**Erstellt:** 2026-07-27
**Ebene:** High-Level — das Denkgebäude, nicht die Features
**Zweck:** Die drei Phasen (vor / während / nach) zu einem Bild zusammenführen
**Basis:** TED + lokale nationale Datenbestände (DÖE für DE, weitere je Land)
**Verhältnis zu den anderen Dokumenten:** Das Kerndokument sagt *warum*, dieses Dokument sagt *entlang welcher Achse* (der Zyklus, zwei Marktseiten), das Architekturprinzip sagt *wie technisch geklammert*.

---

## 1. Die Grundidee

Bisher denkt goVisor den **Bieter** im **Moment** der offenen Ausschreibung. Das Gesamtkonzept erweitert das in zwei Richtungen:

- **Zeitlich**: vom Moment zum ganzen **Zyklus** — vor, während, nach.
- **Perspektivisch**: von einer Seite (Bieter) zu **zwei Seiten** (Bieter *und* Vergabestelle).

Der Kniff: Beides ist **derselbe Datenbestand**, nur anders befragt. Der Bieter fragt „gegen wen trete ich an?", die Vergabestelle „wer tritt gegen mich an, wen erreiche ich?". Das ist die Inside/Outside-Logik des heutigen Produkts — hochgezogen auf die ganze Marktseite. goVisor baut keine zweite Plattform, es spiegelt die vorhandene.

---

## 2. Der Datenbestand — europäisch gedacht

Der Kern ist **nicht** nur TED + DÖE. Das ist die deutsche Sicht. Europäisch gedacht ist es:

> **TED (EU-weit) + der jeweilige nationale Datenbestand pro Land.**

| Ebene | Deutschland | Andere TED-Länder |
|---|---|---|
| **Oberschwellig** | TED | TED (überall gleich) |
| **National / unterschwellig** | DÖE (oeffentlichevergabe.de) | nationales Portal je Land |

TED ist die gemeinsame Klammer über alle EU-Länder. Die nationale Tiefe kommt Land für Land dazu — DÖE für Deutschland, BASE/IMPIC für Portugal, PLACSP für Spanien, TenderNed für die Niederlande, BOAMP/PLACE für Frankreich. Jedes dieser Länder hat ein Open-Data-Portal für den Unterschwellenbereich, den TED nicht abdeckt.

**Konsequenz für die Architektur:** Der Datenlayer muss von Anfang an „TED + Plug-in pro Land" sein, nicht „TED + DÖE" mit DE fest verdrahtet. Deutschland ist die erste nationale Schicht, nicht die einzige.

> **Die Vision: Willst du an einer Ausschreibung in Europa teilnehmen, holst du dir die Intelligenz von goVisor dazu.** `govisor.eu` ist die logische Endform, nicht Kosmetik.

Über den öffentlichen Vergabedaten stehen in PRE zusätzlich **externe Vorlaufquellen** (Förderung, Gesetzgebung, Haushalt) — dazu Abschnitt 4. Diese sind nicht TED/DÖE, sondern kuratiert dazuzuholen.

---

## 3. Der Zyklus — ein Kreis

```
                        ┌────────────────────┐
                   ┌───▶│        PRE         │────┐
                   │    │  Bedarf entsteht,  │    │
                   │    │  bevor ausge-      │    │
                   │    │  schrieben wird    │    │
                   │    └────────────────────┘    │
                   │                              ▼
        ┌────────────────────┐          ┌────────────────────┐
        │       POST         │          │      DURING        │
        │  Vertrag läuft,    │          │  Ausschreibung     │
        │  Auslauf wird zum  │          │  offen — bewerten  │
        │  nächsten Bedarf   │          │  und entscheiden   │
        └────────────────────┘          └────────────────────┘
                   ▲                              │
                   │                              │
                   │    ┌────────────────────┐    │
                   └────│      ZUSCHLAG       │◀───┘
                        │  Vertrag entsteht,  │
                        │  Laufzeit beginnt   │
                        └────────────────────┘

        Das Auslaufen eines Vertrags (POST) erzeugt den
        nächsten Bedarf (PRE). Der Kreis schließt sich.
```

Der Zuschlag ist nicht das Ende, sondern der Übergang: Er beginnt eine Vertragslaufzeit, deren Ende Jahre später der nächste PRE-Moment ist. goVisor ist als einziges Tool in allen vier Stationen präsent — und verbindet sie zum Kreis. Kein Aggregator, keine KI-Suche denkt über den Moment der offenen Ausschreibung hinaus.

**Wichtig zur Gewichtung:** DURING ist nicht die dünnste, sondern die **substanziellste** Phase — dort lebt das gesamte heutige Produkt. PRE und POST sind die Erweiterungen um dieses feste Zentrum herum, nicht gleichrangige Standbeine über einem dünnen Kern.

---

## 4. Phase PRE — bevor ausgeschrieben wird

Rechtlich frei, weil noch **kein Verfahren läuft** — keine Gleichbehandlungspflicht, keine Neutralitätsmauer. Hier entsteht der Bedarf, und er ist vorhersehbar — aus **mehreren** Signalquellen, nicht nur aus dem Zyklus.

### 4.1 Die vier Vorlaufquellen

**Quelle 1 — Der Zyklus selbst (aus POST).** Ein Vertrag, der bald ausläuft, erzeugt bald eine Ausschreibung. Der stärkste einzelne Indikator, weil er direkt aus den eigenen Daten kommt.

**Quelle 2 — Der historische Zyklus-Abgleich.** Nicht nur „sie tut es wieder", sondern: Wer zum vierten Mal denselben Auftrag ausschreibt, zeigt über die Zyklen ein Muster. Was hat sich verändert — Volumen gestiegen oder gefallen, von einem Los auf fünf gewechselt, Anforderungen verschärft, Gewinner immer derselbe oder wechselnd, Verfahrensart geändert? Eine kleine Zeitreihe pro Vergabestelle-plus-Leistungsgegenstand. Für den Bieter Gold: „Diese Stelle schreibt zum vierten Mal aus, Volumen verdoppelt, seit zwei Zyklen gewinnt derselbe — verwundbar oder zementiert."

**Quelle 3 — Zugesagtes Geld.** Forschungsförderung, Haushaltstitel, EU-Strukturfonds, kommunale Investitionsbeschlüsse. Geld, das vergeben wird, bevor ausgeschrieben wird, ist oft Jahre vorher öffentlich. Eine geförderte Forschungsinitiative erzeugt am Ende Beschaffungsbedarf; die Förderung ist lange vorher bekannt.

**Quelle 4 — Regeländerungen (der breiteste Typ).** Ein neues Gesetz, eine Richtlinie, eine Norm löst eine Welle gleichartiger Ausschreibungen aus — planbar, mit Übergangsfrist, marktweit. Beispiele: Onlinezugangsgesetz (Digitalisierung aller Verwaltungsdienste), NIS2 (Cybersecurity-Pflichten), E-Rechnungspflicht, kommunale Wärmeplanung, Barrierefreiheitsstärkungsgesetz. Wer die Regel kennt, kennt die Welle Monate vorher. Der Unterschied zum Zyklus: Nicht „diese Stelle wird wieder", sondern „dieser ganze Markt wird, weil sich die Regeln geändert haben". In dieselbe Kategorie gehören auslaufende Förderprogramme, Normenwechsel, Gerichts-/Vergabekammer-Entscheidungen und politische Programme.

### 4.2 Die Datenrealität — ehrlich

Ein Befund aus dem Inventar, der die Quellen einordnet:

> **Offizielle Vorinformationen (PIN) sind in den Daten fast leer — unter 1,1 % Abdeckung.**

Die offizielle „Vorab-Ankündigung" als strukturiertes TED-Signal trägt PRE also **nicht**. Die PRE-Intelligenz entsteht aus den vier Quellen oben — Quelle 1 und 2 aus den eigenen Daten (stark), Quelle 3 und 4 aus kuratierten externen Beständen (perspektivisch, nicht sofort, aber der eigentliche Sprung von einem Ausschreibungstool zu einem Marktfrühwarnsystem).

### 4.3 Der Berührungspunkt — Potenziale sehen

Vor dem Verfahren dürfen sich beide Seiten begegnen — das ist **Markterkundung**, vom Vergaberecht erlaubt, heute kaum systematisch genutzt.

„Begegnen" heißt hier ausdrücklich **Potenziale sehen, nicht Kontakt vermitteln**:

- Die Vergabestelle sieht als **Marktbild**: „Für diesen geplanten Auftrag kommen 12 passende Anbieter in eurer Region in Frage." — aggregiert, anonym, keine Kontaktliste.
- Der Anbieter sieht als **Frühwarnung**: „In deinem Feld bahnt sich etwas an." — aus den Vorlaufsignalen, keine Einladung.

Beide sehen Möglichkeiten, goVisor vermittelt keinen Kontakt. Das hält den Berührungspunkt außerhalb der Neutralitäts- und Wettbewerbsprobleme — und adressiert das Ein-Bieter-Problem an der Wurzel.

---

## 5. Phase DURING — die offene Ausschreibung (das Fundament, das steht)

Der Moment, in dem der Anbieter bewertet und entscheidet. **Das ist das heutige Produkt und sein Kern** — nicht eine dünne Auswertungsphase, sondern die Substanz von goVisor.

### 5.1 Was hier bereits lebt

| Baustein | Status |
|---|---|
| Lead Explorer, Relevanz-Score | gebaut |
| Wechselwahrscheinlichkeit (Incumbent-Angreifbarkeit) | gebaut |
| Anforderungs-Check (Leistungsbeschreibung, Eignung, Zuschlagskriterien mit Gewichtung) | Ticket #15 |
| Vergabestellen- und Wettbewerbsanalyse | Ticket #10 |
| Verfahrenskalender, Fristen | Ticket #16 |
| Losebene | Ticket #12 |

DURING ist das reiche Zentrum. PRE und POST erweitern es, ersetzen es nicht.

### 5.2 Bieterfragen — geprüft und verworfen

Ursprünglich als DURING-Erweiterung gedacht: Bieterfragen und -antworten während des Verfahrens auswerten (viele Fragen ⇒ unklare Ausschreibung; wiederkehrende Fragetypen ⇒ Stelle schreibt systematisch unpräzise).

**Die Machbarkeitsprüfung ergab ein klares Nein:**
- Q&A-Inhalte stehen zu **0 %** in den Daten (475 Mio. Attribut-Zeilen geprüft). TED/eForms hat kein Fragen-/Antwort-Feld.
- Die Q&A liegen auf ~8–12 Portal-Engines (1.251 Domains), meist hinter Login, als gemischtes PDF/HTML, ohne API.
- Der Adressraum sind nur **12.123 offene Leads** — der ganze Crawl-Apparat zahlt auf ein Zwölftel des Bestands ein.
- Login-Crawling berührt die eigene Betriebsgrenze (keine Accounts anlegen).

**Fazit: nicht für V1/V2.** Dieser Baustein entfällt. DURING trägt vollständig ohne ihn.

### 5.3 Was billig mitgenommen wird

Zwei Reste aus der Bieterfragen-Analyse sind ohne jeden Crawl wertvoll:

- **Fragefrist als Feld** (`AdditionalInformationRequestPeriod.EndDate`, 116k Notices, strukturiert): „Fragen möglich bis X" — gehört in Ticket #16.
- **Portal-Deep-Link als CTA** (`documents_url`, 96,6 % bei offenen Leads): „Zu den Unterlagen & Bieterkommunikation" — der Nutzer holt die Q&A selbst dort, wo er ohnehin registriert bieten muss. Gehört in Ticket #13.
- **Verfahrensbewegung** aus eForms `Change`/F14 (Friständerungen, Nachträge): schwaches „das Verfahren bewegt sich"-Signal, ohne Crawl.

### 5.4 Die Grenze

goVisor vermittelt keine Frage, verteilt keine Antwort, tritt nie ins Verfahren ein. Die Bieterkommunikation bleibt bei den Plattformen — rechtlich gefesselt (Gleichbehandlung, Anonymisierung), hohes Haftungsrisiko. goVisor liest nur, was das Verfahren nach außen abgibt.

---

## 6. Phase POST — Vertrag und Ausblick

Heute in keinem Intelligenz-Tool präsent. Der Auftrag verschwindet nach Zuschlag. Dabei ist POST der Motor des Kreises.

### 6.1 Der Zuschlag als Datenpunkt

- **Gewinner**: Bestätigung, Erfolgsprämie, Start der Laufzeit-Uhr.
- **Verlierer**: „Du warst dabei? Melde das Ergebnis" — der Ergebnisdaten-Graben.
- **Markt**: neuer Incumbent, neuer künftiger Auslauf, aktualisierte Landschaft.

### 6.2 Die Vertragslaufzeit als Brücke

Ein Zuschlag beginnt eine Laufzeit mit bekanntem oder schätzbarem Ende. Dieses Ende wird zum PRE-Lead des nächsten Zyklus. goVisor ist das einzige Tool, das diesen Bogen spannt.

### 6.3 Sechs Bausteine

**a) Auslauf-Tracking** (nah, sofort) — jeder Zuschlag mit Laufzeit erzeugt einen künftigen Auslauf-Termin, wird rechtzeitig zum Lead für Herausforderer und Incumbent.

**b) Incumbent-Beobachtung** (mittel) — beobachtet die Vertragsphase des Amtsinhabers: Auffälligkeiten, die auf den nächsten Zyklus vorausweisen.

**c) Markt-Nachlese** (mittel, wertvoll) — nach Zuschlag die Auswertung: wer gewann, zu welchem Wert, wie viele Bieter, wie nah der Zweite. Für den Verlierer eine Lernschleife, für die Vergabestelle Vergabe-Controlling.

**d) Vertragsänderungen während der Laufzeit** (mittel) — Nachträge, Volumenerhöhungen, Verlängerungen, teils publiziert (`aenderungen`-Cluster). Signal, dass ein Vertrag „heiß" ist oder aus dem Ruder läuft.

**e) Vorzeitige Neuausschreibung** (stark) — wird ein Rahmenvertrag vor Ablauf neu ausgeschrieben, ist das das **stärkste denkbare Displaceability-Signal**: Der Incumbent hat versagt, die Stelle sucht Ersatz. Der wertvollste POST-Trigger.

**f) Umsetzungs-Ausblick** (strategisch, später) — Verlängerungsoptionen, Zwischenevaluationen, Teilkündigungen als Zeitstrahl des laufenden Vertrags, der die Momente markiert, an denen sich der nächste Zyklus abzeichnet.

**Offene Frage (g):** Zahlungs-/Umsetzungsdaten — falls über Transparenzportale oder Fördermitteldatenbanken sichtbar wird, ob ein Auftrag tatsächlich umgesetzt und bezahlt wurde. Datenlage unklar, zu prüfen.

---

## 7. Die dritte Partei — als Datenattribut, nicht als dritte Seite

Ist der Umsetzungsort eine dritte Partei? Ja, in zwei Fällen (zentrale Beschaffungsstelle; Rahmenvertrag mit Abrufberechtigten) — aber sie ist **kein eigener Nutzer**, sondern ein **Datenpunkt**, der die zwei Kunden besser bedient.

### 7.1 Die Datenlage — ehrlich

| Feld | Abdeckung | Aussage |
|---|---|---|
| Rahmenvertrag-Kennung (`ContractingSystemTypeCode`) | **46,5 %** | Ob es ein Rahmenvertrag ist — brauchbar |
| Max. Operator-Anzahl im Rahmen | 3,9 % | fast leer |
| Abrufberechtigte / „on behalf of" | kaum strukturiert | nicht flächendeckend |

**Befund:** Ob ein Auftrag ein **Rahmenvertrag** ist, steht zu 46,5 % in den Daten — nutzbar. **Wer** daraus abruft, steht fast nie strukturiert drin.

### 7.2 Was folgt

- **Tragfähig:** „Dies ist ein Rahmenvertrag" als Attribut. Das ändert die Bewertung für den Bieter — ein Rahmen hat oft ein Vielfaches des Nennwerts an realem Volumen.
- **Nicht tragfähig:** Die einzelnen Abrufberechtigten als Netzwerk-Teilnehmer.

Die dritte Partei wird als **Rahmenvertrag-Flag** in die Datenschicht aufgenommen (Bieter-Feature: „reales Volumen ≠ Nennwert"), nicht als dritte Kommunikationsseite. Der Kommunikationsweg bleibt für alle drei zu — die Vergabestelle muss die Antworten bündeln (Gleichbehandlung), auch wenn sie den Fachverstand intern beim Bedarfsträger holt.

---

## 8. Die Vergabestellen-Frage — warum in goVisor?

Der ehrlichste Einwand: Wenn goVisor Vergabestellen etwas anbietet — warum sollten sie es dort tun?

### 8.1 Das Prozess-Feld ist besetzt

Etablierte **Vergabemanagement-Systeme** decken die Ausschreibungserstellung seit über 20 Jahren ab:

| System | Was es kann |
|---|---|
| **cosinex VMS/BMS** | Bedarfsmanagement, Vorlagen, Textbausteine, LV wiederverwenden, Vergabeakte, Vertragsmanagement, Berichte |
| **AI Vergabemanager** | Kompletter Vergabeprozess, Vergabehandbücher, LV-Erstellung, Wertung |

Tief in die Behördenprozesse integriert, rechtssicher, mit Destatis-Schnittstelle. **goVisor sollte nicht versuchen, ein Vergabemanagement-System zu werden** — ein Kampf auf deren Terrain, den goVisor verliert.

### 8.2 Was goVisor stattdessen hat

Die Systeme sind stark im **Prozess**, schwach in der **Marktintelligenz**. Genau umgekehrt zu goVisor.

> **goVisor macht nicht die Ausschreibung — es macht die Ausschreibung besser, bevor sie ins Vergabesystem geht.**

| Vergabemanagement-System | goVisor |
|---|---|
| Wie schreibe ich rechtssicher aus? | Wen erreiche ich damit überhaupt? |
| Vorlage wiederverwenden | Wie haben andere Stellen das zugeschnitten? |
| Leistungsverzeichnis erstellen | Welches Volumen/welche Kriterien sind marktüblich? |
| Verfahren dokumentieren | Wie erreiche ich mehr als einen Bieter? |

Der Zuschnitt einer Ausschreibung — Lose, Volumen, Kriterien, Fristen — entscheidet, wie viele Bieter kommen. Diese Entscheidung trifft die Vergabestelle heute blind.

### 8.3 Der Einstieg: der Ausschreibungscheck (manuell, sofort baubar)

Der Vergabestellen-Einstieg braucht **keine** API-Integration und **keinen** Eingriff in den Behördenprozess. Er ist ein eigenständiges Gutachten:

```
Vergabestelle lädt Entwurf hoch
        │
        ▼
goVisor prüft gegen die Marktdaten
        │
        ▼
Hinweise + Analysedokument zurück
        │
        ▼
Vergabestelle arbeitet in ihrem eigenen Tool weiter
```

Konkrete Hinweise:
- „Deine geplante Bürgschaft von €250k schließt 60 % der regionalen Anbieter aus."
- „Vergleichbare Aufträge hatten 3–4 Lose; deins hat 1 — das reduziert die Bieterzahl."
- „Stellen wie deine erreichen mit dieser CPV-Kombination im Median 5 Bieter, du zielst auf einen Nischenmarkt mit 2."

Das ist kein Medienbruch im Arbeitsprozess, weil goVisor den Prozess gar nicht anfasst — es liefert ein Gutachten. Ein natürliches Erstprodukt: ein bezahlter Einzel-Check, bevor es ein Abo braucht. Und es bedroht die Vergabemanagement-Systeme nicht, sondern ergänzt sie.

### 8.4 Perspektivisch: Intelligenz rein, nicht Daten raus

Später denkbar: eine API, die goVisor-Benchmarks **in** das Vergabesystem liefert (Intelligenz kommt zur Stelle, im Moment der Entscheidung), statt Behördendaten zu goVisor zu exportieren. Das ist rechtlich viel leichter (keine sensiblen Entwurfsdaten verlassen die Behörde) und strategisch der markt-formende Endzustand: Wenn Ausschreibungen an goVisor-Benchmarks ausgerichtet werden, formt goVisor den Markt, statt ihn nur zu beobachten. Henne-Ei-gebunden, daher Phase 3–4 — erst muss der manuelle Check den Wert beweisen.

---

## 9. Die Mauern — ehrlich benannt

| Mauer | Bedeutung | Konsequenz |
|---|---|---|
| **Neutralität im Verfahren** | goVisor darf während der Ausschreibung nicht Partei werden | PRE + POST frei, DURING nur Auswertung |
| **Kein kollektives Anbieter-Abwerten** | Vergabestellen dürfen Anbieter nicht gemeinsam auf Sperrlisten setzen | nur faktische, aggregierte Markterfahrung |
| **Kartellrecht bei Bieterdaten** | Ergebnisdaten rückwärts, aggregiert, ab Mindestzahl | gilt unverändert |
| **Vergabemanagement ist besetzt** | cosinex/AI dominieren den Prozess | goVisor macht Intelligenz, nicht Prozess |
| **Bieterfragen nicht holbar** | 0 % in Daten, hinter Login, kein API | DURING ohne diesen Baustein |

---

## 10. Einordnung in die Roadmap

Das Konzept ändert nicht die Reihenfolge, es gibt ihr ein Ziel.

| Zyklus-Baustein | Wer zuerst | Roadmap-Phase |
|---|---|---|
| DURING (das heutige Produkt) | Bieter | 0–1 |
| POST a (Auslauf-Tracking) | Bieter | 1 |
| Rahmenvertrag-Attribut | Bieter | 1 (klein, wertvoll) |
| Fragefrist-Feld + Portal-CTA | Bieter | 0–1 (billig, aus Bieterfragen-Analyse) |
| POST b–e (Ergebnisdaten, Nachlese, Neuausschreibung) | Bieter | 2 (der Graben) |
| PRE Quelle 1–2 (Zyklus, historischer Abgleich) | Bieter | 1–3 |
| PRE Quelle 3–4 (Förderung, Regeländerungen) | beide | 3–4 (externe Quellen) |
| Ausschreibungscheck (manuell) | Vergabestelle | 3 (zweiter Kunde, Einstieg) |
| API-Integration in Vergabesysteme | Vergabestelle | 4 (markt-formend) |
| Weitere TED-Länder | beide | 4 (europäisch) |
| POST f (Umsetzungs-Ausblick) | beide | 4 |

Alles beginnt beim Bieter in DURING/POST, weil dort der Datenbestand sofort trägt und der Graben entsteht. Die Vergabestellen-Seite macht aus dem Werkzeug Infrastruktur — aber erst, wenn die Bieter-Basis steht.

---

## 11. Das Gesamtbild je Phase

**PRE:** goVisor sagt aus vier Quellen voraus, was bald ausgeschrieben wird (Zyklus, historischer Abgleich, zugesagtes Geld, Regeländerungen) und zeigt beiden Seiten die Potenziale — gegen das Ein-Bieter-Problem.

**DURING:** das reiche Zentrum — das heutige Produkt, in dem der Bieter bewertet und entscheidet. Bieterfragen als Kanal fallen weg (nicht holbar); die billigen Reste (Fragefrist, Portal-Link) werden mitgenommen.

**POST:** goVisor begleitet den Vertrag über den Zuschlag hinaus, sechs Bausteine, und macht sein Ende zum Anfang des nächsten Zyklus.

**Vergabestelle:** goVisor ersetzt nicht das Vergabesystem, sondern gibt der Stelle die Marktintelligenz, die dort fehlt — Einstieg über den manuellen Ausschreibungscheck, perspektivisch als Intelligenz-API in die Vergabesysteme.

**Europäisch:** TED als Klammer, nationale Tiefe Land für Land. Willst du an einer Ausschreibung in Europa teilnehmen, holst du dir goVisor dazu.

---

## Anhang: Verhältnis zu den anderen Dokumenten

| Dokument | Rolle |
|---|---|
| Kerndokument (`govisor-kern.md`) | *Warum* — die Idee, zwei Marktseiten |
| **Dieses Dokument** | *Entlang welcher Achse* — die drei Phasen, zwei Seiten, Europa |
| Architekturprinzip (`govisor-architekturprinzip.md`) | *Wie technisch geklammert* — ein Kern, zwei Profile |

| Vision-Stufe | Zyklus-Entsprechung |
|---|---|
| Werkzeug (1) | Bieter in DURING/POST |
| Netzwerk (2) | Ergebnisdaten (POST) + Bieternetzwerk (PRE) |
| Infrastruktur (3) | Vergabestelle (Ausschreibungscheck → API) + europäische Breite |
