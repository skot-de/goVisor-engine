# goVisor — Vertriebsziel-Segmente (Abfragespezifikation)

**Version:** 1.0
**Stand:** 2026-07-30
**Zweck:** Definierte Segmente für die Erstansprache, direkt als Abfragen umsetzbar
**Ergänzt:** `govisor-zielliste-spec.md` (Signal-Scoring) — dieses Dokument definiert die **Kohorten**,
jenes die **Priorisierung innerhalb** einer Kohorte
**Ausgabe:** je Segment eine CSV plus Profil-PDF je Treffer

---

## 0. Gemeinsame Grundlagen

### 0.1 Harte Filter — gelten für alle Segmente

| Filter | Wert | Grund |
|---|---|---|
| `entity_confidence` | **nur `confirmed`** | Ein Profil mit fremden Verträgen zerstört die Ansprache |
| Konzernebene | Konzernmutter statt Einzelgesellschaften (`dim_company_group`) | keine Doppelansprache |
| Rolle | Auftragnehmer, nicht Vergabestelle | |
| Land | DE · AT · CH | DACH |
| Ausschluss | öffentliche Eigenbetriebe, Inhouse-Gesellschaften | bieten nicht im Wettbewerb |

### 0.2 Datenlage nach Land

| Land | Quellen | Abdeckung |
|---|---|---|
| **DE** | TED + DÖE + nationale Portale | ober- und unterschwellig, vollständige Historie |
| **AT** | TED + nationale Quellen | ober- und unterschwellig, vollständige Historie |
| **CH** | TED + simap.ch | ober- und unterschwellig, vollständige Historie |

Alle DACH-Quellen sind angebunden, ober- wie unterschwellig. **Die Segmentgrenzen unten gelten
einheitlich für alle drei Länder**; Trendsegmente (C, D, G) sind auch dort belastbar, weil die
Historie vollständig vorliegt.

**Auszugeben ist trotzdem** je Entität der Anteil der Zuschläge je Quelle (`quellenverteilung`) —
er zeigt, ob ein Unternehmen überwiegend ober- oder unterschwellig unterwegs ist. Das schärft die
Ansprache: Wer fast nur unterschwellig gewinnt, hat andere Bedürfnisse als ein EU-weiter Bieter.

### 0.3 Zeitfenster

| Bezeichnung | Definition |
|---|---|
| **letzte 12 Monate** | rollierend ab Stichtag |
| **letzte 24 Monate** | rollierend |
| **letzte 36 Monate** | rollierend — Standardfenster der Aggregate |
| Bezugsdatum | Zuschlagsdatum, nicht Veröffentlichungsdatum |

### 0.4 Was gezählt wird

Ein „gewonnener Auftrag" = ein Zuschlag mit dieser Entität als Auftragnehmer.

**Vorsicht bei Losen:** Eine Vergabe mit 8 Losen kann 8 Zuschläge erzeugen. Zwei Zählweisen, beide
ausgeben:

| Zählung | Bedeutung |
|---|---|
| `zuschlaege_lose` | Rohzahl der Zuschläge (Lose einzeln) |
| `zuschlaege_verfahren` | distinkte Verfahren — **maßgeblich für die Segmentzuordnung** |

Sonst rutschen Bau-Unternehmen mit Losvergaben künstlich in „High Roller".

---

## 1. Segment A — High Roller

**Definition:** Unternehmen mit **≥ 24 gewonnenen Verfahren in 12 Monaten** (Ø ≥ 2/Monat).

| Parameter | Wert |
|---|---|
| Zählung | `zuschlaege_verfahren` ≥ 24 in letzten 12 Monaten |
| Zusatzfilter | keiner |
| Erwartete Größe DE | klein — vermutlich unter 500 Unternehmen |

**Warum interessant:** Höchste Nutzungsfrequenz, professionelle Bid-Strukturen, Premium-Kandidaten.
Sie haben mit hoher Wahrscheinlichkeit bereits ein Werkzeug — der Verkauf ist ein Verdrängungsverkauf.

**Ansprache-Aufhänger:** nicht „findet mehr Ausschreibungen" (das können sie), sondern
Wettbewerbsintelligenz und Auslauf-Radar — was sie mit ihrem jetzigen Werkzeug nicht sehen.

**Zusätzliche Ausgabespalten:** `hauptwettbewerber`, `dessen_auslauf_12m`, `eigene_auslauf_18m`.

---

## 2. Segment B — Gelegenheitsbieter

**Definition:** **1–5 gewonnene Verfahren in 24 Monaten.**

| Parameter | Wert |
|---|---|
| Zählung | `zuschlaege_verfahren` zwischen 1 und 5 in letzten 24 Monaten |
| Ausschluss | Unternehmen, die in Segment C oder D fallen (dort präziser adressiert) |
| Erwartete Größe DE | groß — vermutlich fünfstellig |

**Warum interessant:** Größte Gruppe, klarster Schmerz (findet zu wenig, bewirbt sich blind), aber
niedrigste Zahlungsbereitschaft. **Founding-Preis-Zielgruppe.**

**Wichtige Untergliederung nach Volumen** — sonst mischen sich Kleinstbetriebe mit Mittelständlern:

| Untersegment | Ø Auftragswert |
|---|---|
| B1 | ≥ 500.000 € — hohe Priorität |
| B2 | 100.000–499.999 € — mittlere Priorität |
| B3 | < 100.000 € — niedrige Priorität, hoher Aufwand pro Kunde |

**Ansprache-Aufhänger:** verpasste Verfahren — wie viele passende Ausschreibungen es im Zeitraum gab,
bei denen sie nicht auftauchten.

---

## 3. Segment C — Absteiger

**Definition:** **fallende Zuschlagszahl über 3 Jahre.**

| Parameter | Wert |
|---|---|
| Bedingung | Zuschläge Jahr −1 < Jahr −2 < Jahr −3 **oder** Rückgang ≥ 40 % von Jahr −3 zu Jahr −1 |
| Mindestbasis | ≥ 6 Zuschläge über die 3 Jahre — sonst ist der Trend Rauschen |
| Erwartete Größe DE | mittel |

**Warum interessant:** Akuter, spürbarer Schmerz. Das Unternehmen weiß, dass etwas nicht stimmt,
kennt aber den Grund oft nicht. goVisor kann ihn zeigen.

**Zusätzliche Ausgabespalten:**

| Spalte | Inhalt |
|---|---|
| `rueckgang_pct` | Veränderung Jahr −3 → Jahr −1 |
| `verlorene_bestandsvertraege` | aus `head_to_head`: an wen ging der Nachfolgeauftrag |
| `hauptgewinner_im_segment` | wer hat in derselben Zeit zugelegt |
| `marktentwicklung_segment` | schrumpft der Markt insgesamt, oder nur dieses Unternehmen? |

**Die letzte Spalte ist entscheidend für die Ehrlichkeit.** Wenn das ganze Segment schrumpft, ist der
Rückgang kein Versäumnis — dann wäre der Aufhänger falsch. Nur ansprechen, wenn das Unternehmen
**gegen den Markttrend** verliert.

---

## 4. Segment D — Aussteiger

**Definition:** früher aktiv, seit **≥ 18 Monaten kein Zuschlag mehr**, obwohl der Markt weiterläuft.

| Parameter | Wert |
|---|---|
| Historie | ≥ 3 Zuschläge zwischen Monat −60 und Monat −18 |
| Aktuell | 0 Zuschläge in den letzten 18 Monaten |
| Marktprüfung | im selben CPV+Region gab es in den letzten 18 Monaten ≥ 10 Vergaben |
| Erwartete Größe DE | mittel |

**Warum interessant:** Kennen das Thema, haben aufgegeben. Müssen nicht vom Markt überzeugt werden,
nur vom leichteren Zugang. Kürzerer Weg als beim Neuling.

**Ansprache-Aufhänger:** „Seit eurem letzten Zuschlag 2024 wurden in eurem Feld N Aufträge über
X Mio € vergeben. Davon hätten Y zu eurem Profil gepasst."

**Vorbehalt:** Das Unternehmen kann bewusst ausgestiegen sein oder existiert nicht mehr. Vor der
Ansprache Aktivität prüfen (Handelsregister, Website) — sonst peinlich.

---

## 5. Segment E — Verteidiger unter Druck

**Definition:** hält Bestandsverträge, die **in 6–18 Monaten auslaufen**, in einem Segment mit
**hoher Wechselquote**.

| Parameter | Wert |
|---|---|
| Auslauf | ≥ 1 eigener Vertrag mit Ende in 6–18 Monaten (`lead_duration`) |
| Volumen | Summe der auslaufenden Verträge ≥ 250.000 € |
| Segment-Wechselquote | > 40 % (Marktretention liegt bei 28,3 % — darüber ist Verdrängung überdurchschnittlich) |
| Erwartete Größe DE | mittel |

**Warum interessant:** Verlustvermeidung wiegt psychologisch schwerer als Gewinnchance. Das ist
vermutlich der **stärkste Aufhänger überhaupt** — es geht um Umsatz, den sie bereits haben.

**Ansprache-Aufhänger:** „X € eures Bestands stehen in 14 Monaten zur Disposition. In eurem Feld
werden 44 % der Verträge beim Auslauf neu vergeben."

**Zusätzliche Ausgabespalten:** `auslauf_volumen`, `naechstes_auslaufdatum`, `wechselquote_segment`,
`eigene_bindungsdauer`.

---

## 6. Segment F — Frische Verlierer

**Definition:** hat in den letzten **6 Monaten einen Bestandsvertrag verloren**.

| Parameter | Wert |
|---|---|
| Bedingung | in `head_to_head` als Vorgänger, Nachfolger ist ein anderer, Zuschlagsdatum ≤ 6 Monate |
| Volumen | verlorener Vertrag ≥ 100.000 € |
| Erwartete Größe DE | klein bis mittel |

**Warum interessant:** Maximaler, aktueller Schmerz. Sucht gerade nach Erklärungen. **Höchste
Konversionswahrscheinlichkeit, kürzestes Zeitfenster.**

**Ansprache-Aufhänger:** wer gewonnen hat, und was bei diesem Gewinner demnächst ausläuft
(Rückeroberungsperspektive).

**Timing:** Diese Liste ist **monatlich neu zu erzeugen** — nach 6 Monaten ist der Effekt verpufft.

---

## 7. Segment G — Aufsteiger

**Definition:** **steigende Zuschlagszahl** über 3 Jahre.

| Parameter | Wert |
|---|---|
| Bedingung | Zuschläge Jahr −1 > Jahr −3, Steigerung ≥ 40 % |
| Mindestbasis | ≥ 6 Zuschläge über 3 Jahre |
| Erwartete Größe DE | mittel |

**Warum interessant:** Professionalisiert sich gerade, führt in dieser Phase Werkzeuge ein. Kein
Schmerz, aber guter Zeitpunkt — und wachsende Budgets.

**Ansprache-Aufhänger:** Skalierung — mehr Verfahren bedeuten mehr Aufwand pro gewonnenem Auftrag,
wenn die Auswahl nicht besser wird.

---

## 8. Überschneidungen und Priorisierung

Ein Unternehmen kann in mehrere Segmente fallen. Zuordnung nach **Ansprache-Priorität**, absteigend:

| Rang | Segment | Begründung |
|---|---|---|
| 1 | **F — Frische Verlierer** | akuter Schmerz, kürzestes Zeitfenster |
| 2 | **E — Verteidiger unter Druck** | bezifferbares Risiko, hoher Wert |
| 3 | **C — Absteiger** | spürbarer Schmerz, Ursache unklar |
| 4 | **A — High Roller** | hoher Wert, aber Verdrängungsverkauf |
| 5 | **D — Aussteiger** | kennt das Thema, braucht neuen Zugang |
| 6 | **G — Aufsteiger** | guter Zeitpunkt, kein Schmerz |
| 7 | **B — Gelegenheitsbieter** | größte Menge, niedrigste Konversion |

Jedes Unternehmen erscheint **nur einmal**, im höchstpriorisierten Segment. Die übrigen Zugehörigkeiten
werden als Spalte `weitere_segmente` mitgeführt — sie schärfen die Ansprache.

---

## 9. Ausgabe

### 9.1 CSV je Segment

Basisspalten für alle Segmente:

| Spalte | Inhalt |
|---|---|
| `entity_id`, `firmenname`, `ort`, `land`, `nuts` | Identität |
| `segment`, `weitere_segmente` | Zuordnung |
| `zuschlaege_verfahren_12m/24m/36m` | Aktivität |
| `zuschlaege_lose_36m` | zum Vergleich (Los-Effekt sichtbar) |
| `volumen_36m`, `avg_wert`, `anteil_echter_wert` | Größe und Datenqualität |
| `top_cpv`, `top_vergabestellen`, `regionen` | Kontext |
| `entity_confidence` | Qualitätssicherung |
| `quellenverteilung` | Anteil ober-/unterschwellig je Entität |

Dazu die segmentspezifischen Spalten aus §1–§7.

### 9.2 Profil-PDF je Treffer

Wie in `govisor-zielliste-spec.md` §6 — mit segmentabhängigem Aufhänger:

| Segment | Aufhänger |
|---|---|
| A | „Ihr Hauptwettbewerber hält N Verträge, davon laufen M in 18 Monaten aus." |
| B | „In Ihrem Feld wurden N Aufträge vergeben, bei denen Sie nicht auftauchten." |
| C | „Ihre Zuschläge sind von N auf M gefallen, während der Markt um X % gewachsen ist." |
| D | „Seit Ihrem letzten Zuschlag wurden N Aufträge über X Mio € vergeben." |
| E | „X € Ihres Bestands stehen in N Monaten zur Disposition." |
| F | „Sie haben [Vertrag] an [Wettbewerber] verloren. Bei diesem laufen N Verträge aus." |
| G | „Sie haben Ihre Zuschläge um X % gesteigert — bei N Verfahren im Feld." |

---

## 10. Betrieb

| Segment | Neuberechnung |
|---|---|
| F — Frische Verlierer | **monatlich** — Zeitfenster 6 Monate |
| E — Verteidiger | monatlich — Auslauftermine wandern |
| C, D, G | quartalsweise |
| A, B | halbjährlich |

`outreach_log` führt angesprochene Entitäten mit Datum und Segment. Keine Doppelansprache innerhalb
von 12 Monaten, auch nicht über ein anderes Segment.

**Trefferquote je Segment erfassen.** Nach 50 Ansprachen zeigt sich, welches Segment tatsächlich
konvertiert — danach Priorisierung in §8 anpassen.

---

## 11. Grenzen

| Grenze | Regel |
|---|---|
| **Entity-Sicherheit** | nur `confirmed` — ein falsch zugeordnetes Profil ist schlimmer als keine Ansprache |
| **Rechtsrahmen je Land** | DE (GWB/VgV/UVgO), AT (BVergG), CH (BöB/IVöB) — Anforderungsbegriffe und Schwellenwerte unterscheiden sich. Für die Segmentierung unerheblich, für die Ansprache relevant |
| **Kontaktdaten** | nicht in den Vergabedaten; separat beschaffen. Bei natürlichen Personen greift die DSGVO |
| **E-Mail-Kaltakquise** | nach UWG § 7 auch im B2B riskant — bevorzugt Post, Telefon, LinkedIn |
| **Segment D** | vor Ansprache prüfen, ob das Unternehmen noch existiert |
| **Segment C** | nur ansprechen, wenn der Rückgang **gegen** den Markttrend läuft |
