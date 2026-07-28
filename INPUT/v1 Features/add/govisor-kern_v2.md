# goVisor — Die Idee

**Ebene:** Kerndokument. Das Denkgebäude, aus dem sich alles ableitet — Produkt, Roadmap, und je nach Publikum ein Investoren-Pitch, ein Sales-One-Pager oder ein Onboarding-Dokument.
**Stand:** 2026-07-27

---

## 1. Der Kern in einem Satz

> **goVisor ist die Marktintelligenz für öffentliche Aufträge in Europa — nicht ein weiterer Ort, an dem man Ausschreibungen findet, sondern der Ort, an dem man weiß, ob man sie gewinnen kann.**

Finden können viele. Ob sich eine Bewerbung lohnt, gegen wen man antritt, wie fest der Amtsinhaber sitzt, was marktüblich ist — das ist die Lücke, die goVisor besetzt.

---

## 2. Das Problem

Öffentliche Aufträge in Europa sind ein Markt von **hunderten Milliarden Euro im Jahr** — allein in Deutschland je nach Erfassung 350 Milliarden und mehr. Er ist per Gesetz vollständig transparent: Jede Vergabe, jeder Gewinner, jeder Wert ist öffentlich.

Und trotzdem ist er für die meisten Anbieter eine Blackbox. Nicht, weil Daten fehlen — sie sind da — sondern weil sie **unbrauchbar sind**:

- Verstreut über TED, nationale Portale und hunderte Plattformen
- Publiziert im Moment und dann wieder verschwunden
- Ohne Kontext: Wer hält den Vertrag? Wie oft wechselt die Stelle? Gegen wen trete ich an? Was ist marktüblich?

Die Folge trifft beide Marktseiten. **Anbieter** bewerben sich blind, unterbieten aus Unwissenheit oder lassen Chancen liegen, die sie gewinnen könnten. **Vergabestellen** erreichen zu wenige Bieter: In vier von zehn Verfahren gibt am Ende nur ein einziger ab — nicht weil es keinen Wettbewerb gäbe, sondern weil niemand sonst die Ausschreibung bemerkt oder richtig eingeschätzt hat.

Das ist kein Suchproblem. Es ist ein **Intelligenzproblem**.

---

## 3. Die Einsicht

Andere Branchen haben dasselbe Grundproblem längst gelöst — überall dort, wo ein öffentlicher Datenbestand chaotisch ist und jemand ihn nutzbar macht. Aus ihnen kommt eine einzige, wiederkehrende Erkenntnis:

> **Wenn ein öffentlicher Datenbestand chaotisch ist, gewinnt nicht, wer ihn am breitesten sammelt, sondern wer die verifizierte Schicht darüber baut, die niemand kopieren kann.**

Die Kapitalmarkt-Datenbank verkauft nicht die Deals, die jeder sieht, sondern die geprüfte Schicht darüber. Der Sportdaten-Anbieter besitzt öffentlich sichtbare Spiele nicht — er erhebt, was zwischen den Toren passiert, und besitzt am Ende die Maßeinheit, in der über den Sport gesprochen wird. Der Rechtsdaten-Dienst strukturiert öffentliche Gerichtsakten und füllt ihre Lücken. Der Immobiliendaten-Riese verifiziert mit einer Rechercheabteilung, was in öffentlichen Registern nur halb steht.

Viermal dasselbe Muster: **Der Graben ist nie die Rohdaten. Er ist die Schicht darüber.**

Das ist die zentrale strategische Weichenstellung für goVisor: Nicht das Rennen um die meisten Portale gewinnen — das gewinnt ohnehin der Staat, der die Daten zunehmend zentralisiert. Sondern die Schicht besitzen, die aus öffentlichen Vergabedaten echte Entscheidungsintelligenz macht, und die mit jedem Nutzer wertvoller wird.

---

## 4. Die Lösung: zwei Marktseiten, ein Datenkern

goVisor betrachtet denselben Datenbestand aus zwei entgegengesetzten Richtungen.

```
                    Öffentlicher Vergabedatenbestand
                       (TED + nationale Portale)
                                 │
                   ┌─────────────┴─────────────┐
                   │                           │
             ANBIETER fragt:            VERGABESTELLE fragt:
          "Gegen wen trete            "Wer tritt gegen mich an?
           ich an? Lohnt es            Wen erreiche ich
           sich?"                      überhaupt?"
                   │                           │
                   └─────────────┬─────────────┘
                                 │
                        Dieselbe Maschine.
                        Zwei Blickrichtungen.
```

Der Anbieter will wissen, ob er gewinnen kann. Die Vergabestelle will wissen, ob sie genug Bieter erreicht und ob ihr Verfahren marktgerecht zugeschnitten ist. Beide leiden am selben Informationsdefizit, und goVisor — das beide Seiten kennt — ist der einzige denkbare Ort, der es schließt.

Das ist kein zweites Produkt. Es ist **ein Datenkern mit zwei Sichten**: dieselben Daten, dieselbe Analyselogik, nur andere Fragestellung und andere Oberfläche.

---

## 5. Der Vergabezyklus

Öffentliche Beschaffung ist kein Moment, sondern ein Kreis. goVisor ist als einziges Werkzeug in allen Stationen präsent — und verbindet sie.

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

        Das Auslaufen eines Vertrags erzeugt den nächsten
        Bedarf. Der Kreis schließt sich.
```

### DURING — die offene Ausschreibung (das Fundament, das steht)

Der Moment, in dem der Anbieter bewertet und entscheidet. Das ist das heutige Produkt und sein Kern: Ausschreibungen finden, Relevanz einschätzen, den Amtsinhaber und seine Angreifbarkeit bewerten, Anforderungen prüfen (Leistungsbeschreibung, Eignung, Zuschlagskriterien mit Gewichtung), die Wettbewerbslandschaft lesen, Fristen verfolgen. Hier ist goVisor bereits stark. PRE und POST sind die Erweiterungen um dieses feste Zentrum herum.

### PRE — bevor ausgeschrieben wird

Rechtlich frei, weil noch kein Verfahren läuft. Hier entsteht der Bedarf, und er ist vorhersehbar — aus mehreren Signalquellen, die sich in der Datengrundlage stark unterscheiden. Diese Unterscheidung ehrlich zu machen ist wichtig, weil PRE sonst mehr verspricht, als die Daten heute hergeben:

**Aus den eigenen Daten gedeckt (heute tragfähig):**
- **Der Zyklus selbst**: Ein Vertrag, der bald ausläuft, erzeugt bald eine Ausschreibung. Und mehr: Wer zum vierten Mal denselben Auftrag ausschreibt, zeigt über die Zyklen ein Muster — Volumen gestiegen, Losstruktur verändert, Gewinner zementiert oder wechselnd. Dieser Abgleich von Vergangenheit und Zukunft ist durch Laufzeit- und Amtsinhaber-Daten real gedeckt.

**Externe Quellen (konzeptionell stark, datenseitig noch nicht erschlossen):**
- **Zugesagtes Geld**: Forschungsförderung, Haushaltstitel, EU-Strukturfonds, kommunale Investitionsbeschlüsse — Geld, das vergeben wird, bevor ausgeschrieben wird, ist oft Jahre vorher öffentlich. Erfordert kuratierte externe Bestände, die es noch zu erschließen gilt.
- **Regeländerungen**: Ein neues Gesetz, eine Richtlinie, eine Norm löst eine Welle gleichartiger Ausschreibungen aus — planbar, mit Übergangsfrist, marktweit. Konzeptionell der breiteste Vorlauf-Signaltyp, weil er auf einen ganzen Markt wirkt statt auf eine Stelle. Datenseitig aber der am wenigsten erschlossene: „Gesetz → Ausschreibungswelle" ist ein anspruchsvolles Mapping ohne Vorarbeit. Als Vision stark, als heutiges Feature nicht vorhanden.

Die offizielle Vorab-Ankündigung (PIN) trägt PRE übrigens nicht — sie ist in den Daten fast leer (unter 1,1 % Abdeckung). PRE entsteht aus dem Zyklus (heute) und den externen Quellen (perspektivisch), nicht aus formalen Ankündigungen.

Aus diesen Signalen entsteht der **Berührungspunkt beider Seiten**: Die Vergabestelle sieht als Marktbild, wie viele Anbieter für ihren geplanten Auftrag in Frage kommen. Der Anbieter sieht, dass sich in seinem Feld etwas anbahnt. goVisor zeigt beiden Seiten das **Potenzial** — es vermittelt keinen Kontakt, es macht Möglichkeiten sichtbar. Das adressiert das Ein-Bieter-Problem an der Wurzel.

### POST — nach dem Zuschlag

Heute in keinem Intelligenz-Werkzeug präsent — der Auftrag verschwindet. Dabei ist POST der Motor des Kreises. Der Zuschlag beginnt eine Vertragslaufzeit mit bekanntem Ende, und dieses Ende ist der nächste Bedarf. goVisor begleitet den Vertrag über den Zuschlag hinaus: Auslauf-Verfolgung, Beobachtung des Amtsinhabers, Marktnachlese (wer gewann, wie knapp, warum), Vertragsänderungen während der Laufzeit, und das stärkste Signal überhaupt — die vorzeitige Neuausschreibung, wenn ein Vertrag scheitert.

---

## 6. Was goVisor uneinholbar macht — und was heute erst abhebt

Jedes einzelne Analyse-Feature ist kopierbar. Der dauerhafte Vorsprung entsteht nicht aus Features, sondern aus zwei Schichten, die mit jedem Nutzer wachsen. Wichtig für die ehrliche Einordnung: Diese zwei Schichten sind der **strategische Zug**, nicht der heutige Stand. Sie sind noch zu bauen. Was heute bereits real abhebt, ist ein Drittes — die Ehrlichkeit — und das ist ein Vertrauensvorsprung, kein struktureller Graben. Diese Unterscheidung durchzuhalten ist selbst Teil des Ehrlichkeitsprinzips.

### Die Ergebnisdaten — der Graben, den kein Crawler schließt (zu bauen)

Der öffentliche Datenbestand hat eine strukturelle Lücke: Er zeigt den Gewinner, nie die unterlegenen Bieter. Wer außer dem Sieger geboten hat, wissen nur die Bieter selbst.

goVisor sammelt genau das — nach einem Prinzip, das andere Datenmärkte perfektioniert haben: **Wer beiträgt, sieht die Wettbewerbsmenge, die nur hier existiert.** Mit jedem Nutzer wird sie vollständiger. Ein Wettbewerber kann alle öffentlichen Daten crawlen, aber er kann nicht die Bietergeschichte von tausend Firmen kaufen, die es nur bei goVisor gibt. Das ist die verifizierte Schicht aus der Einsicht — und der einzige Graben, der mit der Zeit tiefer wird statt einholbar.

**Das Kaltstartproblem, ehrlich benannt.** Dieser Graben hat ein Henne-Ei-Problem, an dem jedes „gib-um-zu-sehen"-Netzwerk jahrelang gelitten hat, von Glassdoor bis PitchBook: Niemand trägt seine Bietgeschichte bei, um einen Pool zu sehen, der noch leer ist. Die Wettbewerbsmenge *ist* der Beitrag — solange sie fehlt, fehlt der Anreiz beizutragen. Wer diesen Graben als selbstverständlich existierend darstellt, verstößt gegen das eigene Ehrlichkeitsprinzip.

Die Lösung liegt darin, den **ersten Beitrag vom Pool zu entkoppeln**: Die eigene Biethistorie muss der Firma *allein* nützen — als privates Tracking der eigenen Teilnahmen, als Fristerinnerung, als Nachweis für die Erfolgsprämie — unabhängig davon, ob schon jemand anderes beigetragen hat. Aus diesem Eigennutzen wird dann aggregiert. So war es auch bei Glassdoor: Sein Gehalt einzutragen war ein sinnvoller Akt für sich; die „gib-um-zu-sehen"-Mechanik hat ihn nur verstärkt, nicht erst erzeugt. Das macht aus dem Henne-Ei ein Bootstrapping statt eines Versprechens — aber es ist Arbeit, die vor dem Graben kommt, nicht der Graben selbst.

### Das Netzwerk — die Bindung, die nicht von Daten abhängt

Bei Aufträgen mit mehreren Losen suchen Anbieter Partner, um gemeinsam zu bieten. goVisor vermittelt diese Verbindungen — und lässt sie im Produkt leben. Wenn die Partnerbeziehung in goVisor entsteht und dort gepflegt wird, kostet ein Weggang nicht nur Daten, sondern Kontakte. Das ist der einzige Grabentyp, den kein besserer Parser einholt.

### Die Ehrlichkeit — das, was heute abhebt (kein struktureller Graben)

goVisor zeigt lieber „unbekannt" als eine falsche Zahl. Jeder Wert trägt seine Herkunft: gemessen, geschätzt, unbekannt. Wo die Datenlage dünn ist, sagt goVisor das. In einem Markt voller behaupteter „Marktintelligenz" ist prüfbare Ehrlichkeit ein echter Wettbewerbsvorteil — gegenüber einer Zielgruppe, die Bid Manager und Geschäftsführer sind und Übertreibung sofort erkennen.

Anders als die zwei Gräben ist die Ehrlichkeit **heute bereits versendet** — die Herkunfts-Flags ziehen sich durch das ganze Produkt bis in den Export. Aber sie ist ehrlich einzuordnen als das, was sie ist: ein **Vertrauens-Differential, kein uneinholbarer Graben**. Ein Wettbewerber kann morgen auch „unbekannt" anzeigen. Es ist der reale Vorsprung von heute, nicht der Schutz von übermorgen — und genau deshalb steht es hier neben, nicht in derselben Kategorie wie die zwei wachsenden Schichten.

---

## 7. Das Geschäftsmodell folgt der Idee

Kein Abo, das unabhängig vom Nutzen kassiert, sondern ein Modell, das sich am Erfolg ausrichtet:

- **Kostenlos**, was Dichte und Vertrauen aufbaut: die Liste, die Basisdaten, die Netzwerkteilnahme.
- **Bezahlt**, was echten Analysewert liefert: Wettbewerbssicht, Strategie, Export, Fristen.
- **Erfolgsprämie**, gestaffelt, nur bei nachgewiesenem Gewinn — und nur auf echten Werten, nie auf geratenen.

goVisor verdient, wenn der Kunde gewinnt, nicht wenn er nur zahlt. Das setzt eine Datenqualität voraus, die kein Wettbewerber mit sauberer Zuschlagsverknüpfung erreicht — das Modell ist damit selbst ein Graben.

Für die Vergabestellen-Seite kommt ein eigener, einfacher Einstieg hinzu: ein **Ausschreibungscheck**, der einen Entwurf gegen die Marktdaten prüft und Optimierungsvorschläge liefert — bevor das Verfahren startet, ohne den Behördenprozess anzufassen.

---

## 8. Vom Werkzeug zur Infrastruktur

goVisor entwickelt sich in drei Stufen, die aufeinander aufbauen.

```
  STUFE 3 — INFRASTRUKTUR
  Der Ort, an dem sich der Vergabemarkt trifft.
  Anbieter und Vergabestellen. Die Kennzahlen von goVisor
  werden zur Norm, nach der Ausschreibungen zugeschnitten werden.
        ▲
  STUFE 2 — NETZWERK
  Die Ergebnisdaten machen goVisor einzigartig.
  Das Netzwerk macht es unkündbar.
  Der Graben, der mit jedem Nutzer wächst.
        ▲
  STUFE 1 — WERKZEUG
  Finden, bewerten, gegen wen, mit welcher Chance.
  Ehrlich, tief, deutschland-fokussiert. (heute)
```

Heute ist goVisor auf Stufe 1 — und muss sie gewinnen: ausliefern, was der Markt erwartet, plus die Ehrlichkeit, die abhebt. Stufe 2 ist der strategische Zug: die zwei Gräben, die einholbare von uneinholbarer Konkurrenz trennen. Stufe 3 ist der Fluchtpunkt — der Punkt, an dem goVisor nicht mehr ein Werkzeug unter mehreren ist, sondern die Infrastruktur, an der der Markt nicht vorbeikommt.

---

## 9. Europa

Der Datenbestand ist von Anfang an europäisch. TED ist die gemeinsame Klammer über alle EU-Länder; die nationale Tiefe kommt Land für Land dazu — Deutschland mit seinem Unterschwellen-Portal zuerst, dann die weiteren TED-Länder mit ihren nationalen Open-Data-Quellen.

> **Willst du an einer Ausschreibung in Europa teilnehmen, holst du dir die Intelligenz von goVisor dazu.**

Der Zyklus-Gedanke skaliert mit: Vor, während und nach der Ausschreibung funktionieren in jedem Land auf denselben Feldern. `govisor.eu` ist nicht Kosmetik, sondern die logische Endform.

---

## 10. Für wen

goVisor ist eine **Plattform, kein Nischenprodukt**: IT-Systemhäuser sind der Pilot, an dem die Maschine geschärft wird — das Modell gilt für jeden Sektor.

| Zielgruppe | Wann |
|---|---|
| IT-Systemhäuser (Pilot) | zuerst — warme Kontakte, hoher Wert |
| Mittelständische und regionale Anbieter | früh — größte Zahl, klarster Schmerz |
| Sektor-agnostisch (Bau, FM, Beratung) | danach — dieselbe Maschine, andere Fächer |
| Vergabestellen | die zweite Marktseite, der stärkste Graben |

---

## 11. Was goVisor nicht ist

| Nicht | Sondern |
|---|---|
| Ein weiterer Ausschreibungs-Aggregator | Die Intelligenzschicht darüber |
| Ein Portal, das Dokumente bereitstellt | Ein Werkzeug, das sie auswertet |
| Ein Vergabemanagement-System für Behörden | Die Marktintelligenz, die dort fehlt |
| Ein Tool, das die Zukunft vorhersagt | Ein Werkzeug, das die Vergangenheit ehrlich lesbar macht |
| Ein Abo, das unabhängig vom Nutzen kassiert | Ein Partner, der am Erfolg verdient |
| Multi-Country-Breite ohne Tiefe | Deutschland-Tiefe zuerst, dann Europa |

---

## 12. Die Idee in drei Sätzen

goVisor verwandelt den transparenten, aber unbrauchbar verstreuten europäischen Vergabemarkt in echte Entscheidungsintelligenz — für beide Seiten desselben Marktes, entlang des ganzen Vergabezyklus, ehrlich dort, wo andere breit und behauptet bleiben. Der dauerhafte Vorsprung entsteht nicht aus Features, die jeder kopieren kann, sondern aus zwei Schichten, die mit jedem Nutzer wachsen: den Bietergebnissen, die nur hier existieren, und dem Netzwerk, in dem die Beziehungen des Marktes leben. Am Ende dieser Linie ist goVisor kein Werkzeug mehr, das man nutzt, sondern die Infrastruktur, an der der öffentliche Vergabemarkt nicht mehr vorbeikommt.
