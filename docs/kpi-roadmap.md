# KPI-Roadmap — Vorschlag zum Weitermachen

Grundlage: `feld_inventar.csv` (7.857 Rohfelder mit UI-Kategorie und Bewertung),
`docs/cross-kpis.md` (drei Messrunden), `docs/rohdaten-potenzial-gesamt.md`.
Stand 2026-07-23.

Der Vorschlag ist in drei Stufen geschnitten, **nach Wirkung je Aufwand**, nicht nach
thematischer Ordnung. Jede Stufe ist für sich auslieferbar.

---

## Stufe 1 · Was in der Liste sofort wirkt

Fünf Eingriffe, alle gemessen, alle ein bis zwei Spalten. Zusammen etwa zwei Arbeitstage.

| # | Was | Abdeckung | Warum zuerst |
|---|---|---|---|
| 1.1 | **`RegulatoryDomain`** als Filter — VOB / UVgO / VgV / SektVO | **98,7 % aller Leads** | Ein Bauunternehmer räumt damit die halbe Liste weg. Höchste Abdeckung im ganzen Inventar. |
| 1.2 | **`anyw-cou`-Fix** in der Umkreissuche | 4.144 Leads | **Behebt einen Fehler**: bundesweit erbringbare Leistungen fallen heute aus dem Radius-Filter. Kein neues Feature, eine Reparatur. |
| 1.3 | **Käufertyp + Tätigkeitsfeld** im Vergabestelle-Tab | 79 % / 85 % aller Leads | Zwei Codelisten, über die **gesamte Historie** verfügbar. Grundlage für 3.2. |
| 1.4 | **Unterlagen-Direktlink** | **96,8 % der offenen** Leads | Unser `portal_url` liegt bei 44,5 % / DÖE **0 %** — wir zeigen seit jeher das schlechtere Feld. |
| 1.5 | **Einstiegsschwelle + „Lose nur auf dem Papier"** — als **Paar** | 4.084 / 33.664 | Einzeln ist jeder der beiden irreführend, s. unten. |

### Warum 1.5 nur als Paar geht
Die Einstiegsschwelle sagt: *„388.437 € Gesamtwert, aber ab 10.773 € dabei."* Die
Papier-Lose sagen: *„bei dieser Stelle gehen 7.769 Mehrlos-Vergaben komplett an einen."*
Wer nur den ersten zeigt, verkauft eine Zugänglichkeit, die es nicht gibt.

**Das ist die Regel, die ich für alle weiteren KPIs vorschlagen würde:** wo ein
Gegen-Indikator existiert, wird er mit ausgeliefert oder der KPI gar nicht.

---

## Stufe 2 · Die Blindstellen schließen

| # | Was | Zustand heute | Nachher |
|---|---|---|---|
| 2.1 | **Erwartete Bieterzahl** als Spanne | `n_bidders` bei **allen 12.123 offenen Leads 0 %** | „3–7 Bieter erwartet", MAE 2,55 bei 91 % Abdeckung |
| 2.2 | **Fristen-Trio**: Bindefrist · Submissionstermin · Bieterfragen-Frist | keins davon im Produkt | 66,7 % / 42,4 % / 28,7 % der offenen Leads |
| 2.3 | **Marktverschluss** (`fa-wo-rc` × Restlaufzeit) | nicht sichtbar | 12.333 Leads, davon 1.968 über 3 Jahre gesperrt |
| 2.4 | **Preisdruck vs. Einstiegshürde** | nicht sichtbar | Preis 100 % → 5,31 Bieter, Preis < 40 % → 4,00 |

2.1 braucht eine Zusicherung im Code: **nie als Punktwert rendern.** Bei ±2,55 Abweichung
wäre „5 Bieter" Scheingenauigkeit. Die Spanne ist die Aussage.

---

## Stufe 3 · Der Produktsprung

| # | Was | Voraussetzung |
|---|---|---|
| 3.1 | **Aufwand-Rendite als Listen-Sortierung** — `(Wert × Chance) ÷ Aufwand` | Stufe 2 (die Chance-Komponente braucht 2.1) |
| 3.2 | **Käufer-Zwillinge** — „Stellen wie eure Kunden, wo ihr noch nicht seid" | 1.3 |
| 3.3 | **Eignungs-Match** — 32 typisierte Codes gegen das Firmenprofil | Nutzer pflegt sein Profil |
| 3.4 | **Partner-Cluster** — Los-Obergrenze, Bietergemeinschafts-Klausel, Untervergabe, Firmengröße | eigene UI-Fläche |

3.1 ist der eigentliche Hebel: Heute sortiert die Liste nach Frist oder Wert. Nach
Rendite zu sortieren wäre die Kernfunktion — **und jede Zutat liegt vor.**

---

## Was ich nicht bauen würde

Vier Wege sind gemessen zu und sollten nicht wiederkehren:

| Idee | Warum zu |
|---|---|
| **Regionale Makro-Prädiktoren** (Anbieterdichte, Baugenehmigungen, Verschuldung) | Drei unabhängige Tests, alle flach nach Normierung auf Einwohner. Baugenehmigungen: r = 0,434 absolut, **−0,089 je Kopf**. Destatis gehört ins UI als Beschreibung, nicht als Prognose. |
| **Textähnlichkeit für Nachfolge-Erkennung** | 61 % der Beschreibungen unter 200 Zeichen; das Leistungsverzeichnis liegt hinter einer Registrierung (an fünf Plattformen geprüft). |
| **„Kurze Frist begünstigt den Amtsinhaber"** | Nur 473 prüfbare Fälle, und das Muster zeigt in die Gegenrichtung. |
| **Bürgschaft × Gewinnergröße** | Zutaten liegen auf verschiedenen Bekanntmachungen, `award_tender_link` bringt sie nicht zusammen. |

---

## Arbeitsweise für jeden neuen KPI

Aus den Fehlern dieser Analyse abgeleitet — jeder Punkt steht für einen konkreten Fall,
in dem es schiefging:

1. **Abdeckung auf LEAD-Ebene messen, nach Phase getrennt.** Der Unterlagen-Link hat
   98,5 % über Notices, aber **13,7 % über Leads** (86 % unserer Leads sind `expiring`).
   Beide Zahlen stimmen, nur eine ist relevant.
2. **Normieren, bevor korreliert wird.** r = 0,434 zwischen Baugenehmigungen und
   Bau-Vergaben war reine Bevölkerungsgröße.
3. **Verkettung der Zutaten vor dem Bauen prüfen.** Bürgschaft und Firmengröße existieren
   beide — nur nie auf demselben Dokument.
4. **Gegen-Indikator mitliefern oder gar nicht.** Einstiegsschwelle ohne Papier-Lose ist
   eine halbe Wahrheit.
5. **Herkunft flaggen.** Das Produkt hat dafür bereits `val(…, src, hint)`. Ein
   geschätzter Wert ohne Flag ist eine Behauptung.
6. **Negativbefunde dokumentieren.** Sonst kommt die Anbieterdichte in sechs Monaten
   wieder auf den Tisch — sie stand schon zweimal drauf.

---

## Konkreter nächster Schritt

Ich würde mit **1.1 bis 1.4** anfangen: vier Spalten, alle gemessen, keine offenen Fragen,
zusammen etwa ein Arbeitstag. Danach ist die Liste spürbar besser, und wir haben einen
belastbaren Eindruck davon, wie sich neue Felder im Frontend anfühlen — bevor Stufe 2 und
3 größere Eingriffe bringen.

1.5 würde ich direkt hinterherziehen, weil das Paar zusammengehört.
