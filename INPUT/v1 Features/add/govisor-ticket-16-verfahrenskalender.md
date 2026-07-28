# Feature #16: Verfahrenskalender

**Produkt:** goVisor
**Version:** Phase 1 — Retention-Hebel
**Status:** Draft
**Erstellt:** 2026-07-27
**Baut auf:** Ticket #9 (Alerts), Ticket #12 (Losebene), Ticket #3 (Lead-Detail)
**Aufwand:** klein–mittel, hohe Wirkung auf Nutzungsfrequenz

---

## 1. Warum dieses Ticket

goVisor findet den Lead — und dann endet das Produkt. Zwischen Fund und Zuschlag liegen im Median **87 Tage**, in denen der Nutzer die Plattform wechselt: ins Vergabeportal für Fristen, in Outlook für Erinnerungen, in Excel für die Übersicht. In dieser Zeit ist goVisor unsichtbar.

Das ist die größte Retention-Schwäche im aktuellen Zuschnitt und zugleich billig zu beheben: **Die Termine liegen in den Daten und werden nicht genutzt.**

**Der strategische Punkt:** Ein Werkzeug, in dem man nur nachschlägt, wird gekündigt, sobald die Neugier nachlässt. Ein Werkzeug, in dem man *arbeitet* — Fristen verfolgt, Termine im Blick hat — bleibt. Das ist auch die Antwort auf Adjudicas „Track"-Stufe, ohne dass goVisor dafür KI-Angebotserstellung braucht.

---

## 2. Datenlage — besser als gedacht

Aus dem Feldinventar. Die wichtigste Frist ist die am besten abgedeckte:

| Termin | Feld | Abdeckung | Bedeutung |
|---|---|---|---|
| **Angebotsfrist** | `TenderSubmissionDeadlinePeriod.EndDate` + `.EndTime` | **82 %** (mit Uhrzeit) | Der harte Stichtag |
| Submissionstermin | `OpenTenderEvent.OccurrenceDate` | 31 % | Öffnung der Angebote |
| Bindefrist | `TenderValidityPeriod.DurationMeasure` | 59 % | Wie lange das Angebot bindet |
| Bieterfragen-Frist | `AdditionalInformationParty` (indirekt) | ~37 % | Letzter Tag für Rückfragen |

**Kernpunkt:** Die Angebotsfrist — der einzige wirklich kritische Termin — liegt zu 82 % vor, sogar mit Uhrzeit. Das trägt das Feature allein. Die übrigen Termine sind Bonus, wo vorhanden.

**Los-genau:** Alle Fristen liegen auf `ProcurementProjectLot`-Ebene (Anschluss an #12). Verschiedene Lose können verschiedene Fristen haben — der Kalender ist deshalb los-genau.

---

## 3. Konzept

### 3.1 Zwei Ansichten desselben Datenbestands

| Ansicht | Wo | Zweck |
|---|---|---|
| **Frist im Lead-Detail** | Ticket #3 | Termine dieses einen Leads |
| **Kalender-Übersicht** | Neue Seite/Sektion | Alle Fristen der beobachteten Leads |

Beide lesen dieselben Termindaten. Keine neue Datenerhebung — nur Darstellung dessen, was schon da ist.

### 3.2 Kein Kalender-Vollprodukt

Ausdrücklich **kein** Google-Calendar-Klon. Kein Erstellen eigener Termine, kein Einladungsmanagement, keine Wochenansicht mit Drag-and-Drop. Das wäre Feature-Kriechen. Was gebraucht wird: eine chronologische Liste der Fristen, die den Nutzer betreffen, mit klarer Dringlichkeit.

---

## 4. Frist im Lead-Detail

Der Übersicht-Tab bekommt eine kompakte Termin-Zeile, bei Mehr-Los-Vergaben los-genau:

```
TERMINE

  Angebotsfrist          15.09.2026, 10:00 Uhr      noch 12 Tage
  Bieterfragen bis        08.09.2026                 noch 5 Tage
  Submission              15.09.2026, 10:15 Uhr
  Bindefrist              30 Tage nach Abgabe

  [👁 Beobachten — Fristen im Kalender verfolgen]
```

Bei fehlenden Terminen: die vorhandenen zeigen, fehlende weglassen (nicht „unbekannt" für jede Zeile — das wäre Lärm). Wenn nur die Angebotsfrist da ist, steht nur die da.

**Dringlichkeits-Färbung** (konsistent mit bestehender Grammatik):
- \> 14 Tage: neutral
- 3–14 Tage: `--flag` (Warnung)
- < 3 Tage: `--risk` (dringend)
- überschritten: ausgegraut, „Frist abgelaufen"

### 4.1 Geschätzte Fristen ehrlich kennzeichnen

Wo die Angebotsfrist fehlt (18 %), **nicht** schätzen und als Fakt zeigen. Falls eine grobe Schätzung sinnvoll ist (z. B. Publikationsdatum + Median-Vorlauf), klar als „voraussichtlich" markieren — konsistent mit dem Ansatz aus Ticket #9.

```
  Angebotsfrist          voraussichtlich Mitte September    geschätzt
```

---

## 5. Kalender-Übersicht

### 5.1 Wo

Eine neue Sektion „Termine" — erreichbar aus der Watchlist („Meine Leads", Ticket #9) und als eigener Einstiegspunkt. Sie zeigt die Fristen **aller beobachteten Leads** chronologisch.

### 5.2 Darstellung

```
┌──────────────────────────────────────────────────────────────┐
│  Termine                              [Diese Woche] [Monat]  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Diese Woche                                                 │
│  ──────────────────────────────────────────────────────────│
│  Mo 08.09   Bieterfragen    BMI Managed Services   ⚠ 5 Tage │
│  Do 11.09   Angebotsfrist   LK Rosenheim IT        ⚠ 3 Tage │
│                                                              │
│  Nächste Woche                                               │
│  ──────────────────────────────────────────────────────────│
│  Mo 15.09   Angebotsfrist   BMI Managed Services   12 Tage  │
│  Mo 15.09   Submission      BMI Managed Services            │
│                                                              │
│  Später                                                      │
│  ──────────────────────────────────────────────────────────│
│  Di 30.09   Angebotsfrist   AA Cloud Migration     27 Tage  │
│  ...                                                         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

Jede Zeile verlinkt zum Lead. Sortierung strikt chronologisch. Nur Fristen beobachteter Leads — der Kalender ist so voll oder leer wie die Watchlist.

### 5.3 Los-genaue Fristen

Bei einer beobachteten Mehr-Los-Vergabe mit unterschiedlichen Los-Fristen erscheint jede relevante Los-Frist einzeln, mit Los-Kennung:

```
  Do 11.09   Angebotsfrist   BMI Los 4 (Managed WP)   ⚠ 3 Tage
  Do 18.09   Angebotsfrist   BMI Los 7 (Support)      10 Tage
```

---

## 6. Alerts-Anbindung (Ticket #9)

Der Kalender ist die visuelle Seite; die Alerts aus #9 sind die aktive Seite. Sie teilen sich die Termindaten.

Ticket #9 kennt bereits Angebotsfrist-Warnungen (14d / 3d). Dieses Ticket ergänzt:

| Alert | Trigger | Gate |
|---|---|---|
| Bieterfragen-Frist naht | 3 Tage vor `AdditionalInformation`-Frist | Paid |
| Angebotsfrist naht | 14d / 3d (aus #9) | Paid |
| Bindefrist-Ende | Info im Kalender, kein eigener Alert | — |

**Keine Doppelung:** Die Angebotsfrist-Warnung bleibt in #9, dieses Ticket ergänzt nur die Bieterfragen-Frist und liefert die Kalenderdarstellung.

---

## 7. Export / Kalender-Abo (leichtgewichtig)

Ein kleiner, hoher Nutzen: Fristen der beobachteten Leads als **iCal-Feed** (`.ics`) abonnierbar. Dann erscheinen sie im Outlook/Google-Kalender des Nutzers, ohne dass goVisor einen eigenen Kalender bauen muss.

```
[📅 Fristen in meinen Kalender abonnieren]
→ ical-Feed-URL, aktualisiert sich automatisch
```

Das ist der klügere Weg als ein eigenes Kalender-UI: Der Nutzer arbeitet ohnehin in seinem Kalender. goVisor liefert die Termine dorthin. Paid-Feature.

---

## 8. Datenmodell

### 8.1 Genutzt (keine neue Erhebung)

Die Termine kommen aus den bestehenden Los-/Lead-Daten:

| Feld | Quelle |
|---|---|
| `submission_deadline` (Datum+Zeit) | `TenderSubmissionDeadlinePeriod` |
| `submission_deadline_source` | `echt` / `geschaetzt` |
| `open_event_date` | `OpenTenderEvent.OccurrenceDate` |
| `validity_days` | `TenderValidityPeriod.DurationMeasure` |
| `question_deadline` | `AdditionalInformation`-Frist, wo ableitbar |

### 8.2 Neu (klein)

**`user_calendar_feed`** (für iCal-Abo)

| Feld | Typ | Bedeutung |
|---|---|---|
| `user_id` | uuid | FK |
| `feed_token` | string | eindeutiger, nicht erratbarer Feed-Schlüssel |
| `created_at` | timestamp | |

Der Feed liest live aus der Watchlist — keine Duplikation der Termine.

---

## 9. Provenance

| Wert | Quelle | Kennzeichnung |
|---|---|---|
| Angebotsfrist | `TenderSubmissionDeadlinePeriod` | echt (82 %) |
| geschätzte Frist | Publikation + Median | `geschaetzt`, „voraussichtlich" |
| Submission | `OpenTenderEvent` | echt (31 %), sonst weglassen |
| Bindefrist | `TenderValidityPeriod` | echt (59 %), sonst weglassen |

**Regel:** Fehlende Termine werden weggelassen, nicht als „unbekannt" ausgewiesen — bei einer Terminliste wäre das nur Lärm. Ausnahme: Wenn die Angebotsfrist (der kritische Termin) fehlt, wird das aktiv gezeigt, weil ihr Fehlen relevant ist.

---

## 10. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Lead-Detail zeigt Termine, wo vorhanden |
| 2 | Angebotsfrist mit Datum und Uhrzeit |
| 3 | Dringlichkeits-Färbung nach Restzeit |
| 4 | Fehlende Termine weggelassen (kein „unbekannt"-Lärm) |
| 5 | Fehlende Angebotsfrist aktiv gezeigt (sie ist kritisch) |
| 6 | Geschätzte Fristen als „voraussichtlich" markiert |
| 7 | Kalender-Übersicht zeigt Fristen aller beobachteten Leads chronologisch |
| 8 | Los-genaue Fristen bei Mehr-Los-Vergaben |
| 9 | Jede Kalenderzeile verlinkt zum Lead |
| 10 | iCal-Feed abonnierbar (Paid) |
| 11 | Bieterfragen-Frist-Alert ergänzt #9 ohne Doppelung |
| 12 | Kein eigenes Kalender-Vollprodukt (kein Termin-Erstellen) |

---

## 11. Edge Cases

| # | Case | Verhalten |
|---|---|---|
| 1 | Nur Angebotsfrist vorhanden | Nur diese zeigen |
| 2 | Kein Termin vorhanden | „Angebotsfrist nicht veröffentlicht", Rest weg |
| 3 | Los-Fristen unterschiedlich | Je Los eigene Zeile im Kalender |
| 4 | Frist bereits abgelaufen | Ausgegraut, „abgelaufen", kein Alert mehr |
| 5 | Geschätzte Frist überschritten | Keine „naht"-Warnung mehr (aus #9) |
| 6 | Watchlist leer | Kalender leer mit Hinweis „Beobachte Leads, um Fristen zu sehen" |
| 7 | Zeitzone des Nutzers ≠ Europe/Berlin | Frist in Nutzer-Zeitzone anzeigen, Original mitführen |
| 8 | iCal-Feed-Token kompromittiert | Neu generierbar (invalidiert alten) |
| 9 | Frist ohne Uhrzeit (nur Datum) | Datum zeigen, keine erfundene Uhrzeit |

---

## 12. Out of Scope

| Was | Warum |
|---|---|
| Eigene Termine erstellen | Kein Kalender-Vollprodukt |
| Team-Kalender / geteilte Termine | Team-Accounts sind V2 |
| Erinnerungen per SMS/Push | V2 (aus #9 Out of Scope) |
| Automatische Angebotsabgabe-Erinnerung mit Checkliste | V2 |
| Verfahrensschritte über die Fristen hinaus (Verhandlungsrunden etc.) | V2 |
| Zwei-Wege-Sync mit Outlook/Google | Nur Lese-Feed (iCal), kein Sync |

---

## 13. Abhängigkeiten

| Abhängigkeit | Status |
|---|---|
| Termindaten im Gold Layer | vorhanden (Angebotsfrist 82 %) |
| Ticket #9 Alerts | Basis, wird ergänzt |
| Ticket #12 Losebene | für los-genaue Fristen |
| Ticket #3 Lead-Detail | wird ergänzt |
| Watchlist (#9) | liefert die beobachteten Leads |

---

## 14. Testfälle

| # | Test | Erwartung |
|---|---|---|
| 1 | Lead mit Angebotsfrist + Uhrzeit | „15.09.2026, 10:00 Uhr, noch X Tage" |
| 2 | Lead nur mit Angebotsfrist | Nur diese Zeile |
| 3 | Lead ohne Angebotsfrist | „Angebotsfrist nicht veröffentlicht" |
| 4 | Frist in 2 Tagen | `--risk`-Färbung |
| 5 | Frist abgelaufen | Ausgegraut, „abgelaufen" |
| 6 | 3 beobachtete Leads | Kalender zeigt alle Fristen chronologisch |
| 7 | Mehr-Los-Vergabe, 2 Los-Fristen | 2 Kalenderzeilen |
| 8 | iCal-Feed abonnieren | `.ics` mit allen Watchlist-Fristen |
| 9 | Watchlist leer | Leerer Kalender mit Hinweis |
| 10 | Geschätzte Frist | „voraussichtlich", markiert |

---

## 15. Offene Fragen

| # | Frage | Empfehlung |
|---|---|---|
| 1 | Kalender eigene Route oder Teil der Watchlist-Seite? | Teil der Watchlist-Seite (Tab „Termine"), kein eigener Nav-Eintrag |
| 2 | iCal-Feed auch für Free? | Nein, Paid — konsistent mit Alerts |
| 3 | Bieterfragen-Frist wo ableitbar unklar | Nur zeigen, wo sauberer Wert; sonst weglassen |
| 4 | Vergangene Fristen im Kalender behalten? | Nein, nur zukünftige; abgelaufene im Lead-Detail sichtbar |
| 5 | Wie weit in die Zukunft? | Alle beobachteten Leads, keine Zeitgrenze |

---

## 16. Zusammenfassung

Der Verfahrenskalender macht aus dem Nachschlage-Tool ein Arbeits-Tool, ohne ein Kalender-Vollprodukt zu bauen. Die Termine liegen bereits in den Daten — die Angebotsfrist als kritischster Wert zu 82 % mit Uhrzeit. Sie werden im Lead-Detail und in einer chronologischen Übersicht der beobachteten Leads dargestellt, los-genau, mit Dringlichkeitsfärbung und ehrlicher Kennzeichnung geschätzter Fristen. Ein iCal-Feed bringt die Fristen in den Kalender, in dem der Nutzer ohnehin arbeitet. Das ist der günstigste Retention-Hebel im ganzen Plan und die schlanke Antwort auf Adjudicas Track-Stufe.
