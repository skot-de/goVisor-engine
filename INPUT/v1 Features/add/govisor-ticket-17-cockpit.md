# Feature #17: Cockpit — Merkliste, Pipeline & Historie

**Produkt:** goVisor
**Version:** 1.0
**Status:** Konzept
**Erstellt:** 2026-07-27
**Baut auf:** #1 (Merkliste), #11 (`user_outcomes`, `user_contracts`), #16 (Fristen)
**Aufwand:** überwiegend Frontend + Vorbefüllungs-Logik — die Datenstrukturen aus #11 sind fertig

---

## 1. Warum dieses Ticket

Ein Bid-Manager hat heute keine Übersicht über den Zustand seiner Ausschreibungen: worauf er sich beworben hat, was er gewonnen hat, was bald ausläuft. Diese Übersicht liegt verstreut oder gar nicht vor — „im Forecast stehen Geschichten statt Termine".

goVisor kann diese Übersicht liefern — und zwar **vorbefüllt aus den öffentlichen Daten**, nicht als leeres Blatt. Das ist der entscheidende Unterschied zu jedem Lead-Management-Tool: Beim ersten Login sieht der Nutzer seine eigene Marktgeschichte, ohne einen Finger zu rühren.

Das Feature führt drei bestehende Bausteine zu einer Ansicht zusammen: die **Merkliste** (#1), die **eigenen Meldungen/Bewerbungen** (`user_outcomes`, #11) und die **eigenen Bestandsverträge** (`user_contracts`, #11).

**Abgrenzung — das ist KEIN CRM.** Kein Kontaktmanagement, keine Meeting-Notes, keine Angebotssummen, keine Vertriebsbeziehung. Es verwaltet den **Status der Ausschreibung**, nicht die Vertriebsbeziehung. Siehe Abschnitt 9.

---

## 2. Die drei Bereiche

Drei zusammenklappbare Bereiche, chronologisch von Zukunft nach Vergangenheit:

```
  ┌─────────────────────────────────────────────────────┐
  │  ▼ BEOBACHTET (Merkliste)              3 Leads       │
  │    Zukunft — was ich angehen will                   │
  │    offene Ausschreibungen mit tickender Frist       │
  ├─────────────────────────────────────────────────────┤
  │  ▼ AKTIV (Pipeline)                    5 Leads       │
  │    Gegenwart — woran ich gerade dran bin            │
  │    beworben / abgegeben / auf Entscheidung wartend  │
  ├─────────────────────────────────────────────────────┤
  │  ▶ HISTORIE (eingeklappt)              47 Verträge   │
  │    Vergangenheit — was war, und was daraus folgt    │
  │    gewonnene & verlorene, ausgelaufene Verträge     │
  └─────────────────────────────────────────────────────┘
```

Jeder Bereich einzeln auf-/zuklappbar. Wer an laufenden Bewerbungen arbeitet, klappt die Historie zu. Wer strategisch schaut, klappt sie auf.

### Die Trennlinie zwischen den Bereichen

- **Beobachtet → Aktiv:** der Moment der Entscheidung „ich mache mit". Ein Lead wandert nach unten, sobald der Nutzer sich bewirbt.
- **Aktiv → Historie:** die Entscheidung der Vergabestelle. Ein Lead wandert nach unten, sobald der Zuschlag da ist (gewonnen/verloren).

Beide Übergänge sind natürliche Bewegungen nach unten — kein manuelles Umziehen zwischen getrennten Orten.

---

## 3. Bereich 1 — Beobachtet (Merkliste)

**Was:** Offene Ausschreibungen, die der Nutzer im Auge behält, ohne schon entschieden zu haben.
**Zeitrichtung:** zukunftsgerichtet, fristgebunden.
**Datenquelle:** bestehende Merkliste (#1).
**Kernanzeige:** Angebotsfrist mit Dringlichkeit (aus #16) — „wie lange habe ich noch, um zu entscheiden?"
**Aktion:** „Ich bewerbe mich" → Lead wandert in Bereich 2.

**Grau-Logik:** In diesem Bereich ist fehlender Status **normal** — hier *soll* noch keiner sein. Kein Aufforderungs-Grau, kein Nörgeln.

---

## 4. Bereich 2 — Aktiv (Pipeline)

**Was:** Laufende eigene Bewerbungen.
**Zeitrichtung:** gegenwartsbezogen, statusgetrieben.
**Datenquelle:** `user_outcomes` (`applied=true`, noch kein Ergebnis).
**Status-Werte (bewusst schlank, nur ausschreibungsbezogen):**

| Status | Bedeutung |
|---|---|
| Beworben | Angebot in Vorbereitung / eingereicht |
| Abgegeben | Angebot fristgerecht eingereicht |
| Wartet auf Entscheidung | Frist durch, Zuschlag ausstehend |

**Kernanzeige:** Status + erwarteter Entscheidungstermin (Median 87 Tage nach Angebotsfrist, aus den Daten).
**Aktion:** Bei Zuschlag → „Gewonnen" oder „Verloren" setzen → Lead wandert in Bereich 3 **und** löst die Ergebnismeldung aus (#11).

**Grau-Logik:** Hier ist fehlender Status der **Aufforderungszustand** — ein Eintrag ohne Status wird sanft ausgegraut mit „Status ergänzen". Nicht als Vorwurf („unordentlich"), sondern als Einladung („ein Klick, und es ist vollständig"). Das erzeugt den Vervollständigungsanreiz, der goVisor den Status liefert.

---

## 5. Bereich 3 — Historie

**Was:** Ausgelaufene und vergangene Verträge — gewonnene wie verlorene.
**Zeitrichtung:** rückblickend, aber mit Zukunftssignal.
**Datenquelle:** `user_contracts` (eingetragen) **+ vorbefüllt** aus öffentlichen Zuschlagsdaten (siehe Abschnitt 6).

**Was sich daraus ableitet:**

| Ableitung | Nutzen |
|---|---|
| **Eigene Stammkunden** | Wo bin ich Incumbent? Wo droht Verteidigung bei Auslauf? |
| **Verlorene Stammkunden** | Wo habe ich Boden verloren, an wen — ist der Vertrag wieder ausschreibungsreif? (Rückeroberungs-Lead) |
| **Gewinnquote über Zeit** | Martin-Ha-Frage 2 — näherungsweise aus öffentlichen Gewinnen, exakt erst mit eigenen Ergänzungen |
| **Auslauf → neuer Lead** | Ein ausgelaufener Vertrag, der wieder ausgeschrieben wird, ist ein Lead — der Kreis schließt sich |

**Kernanzeige:** Vertrag, Vergabestelle, Zeitraum, Ausgang (gewonnen/verloren), und — wo relevant — „läuft demnächst wieder aus / wurde neu ausgeschrieben".

---

## 6. Vorbefüllung — der Aktivierungsvorteil

**Beim ersten Login ist das Cockpit nicht leer.** goVisor kennt aus den öffentlichen Daten (`entity_identity` + Zuschlagsdaten), welche öffentlichen Aufträge die Firma gewonnen hat, und füllt Bereich 2 und 3 vor.

### 6.1 Die ehrliche Kante

goVisor sieht nur die **öffentlichen, oberschwelligen** Aufträge. Zwei Grenzen, die die Darstellung ehrlich abbilden muss:

1. **Unterschwelliges fehlt.** Bei CANCOM (viel Oberschwelliges) ist die Vorbefüllung gut, bei einem regionalen Anbieter fast leer. Hinweis: „Das sind eure öffentlich sichtbaren Verträge — ergänzt eure weiteren, um das Bild zu vervollständigen." Sonst denkt der Nutzer, goVisor kenne seinen ganzen Bestand.

2. **Niederlagen fehlen.** goVisor sieht, wer *gewonnen* hat, nicht zuverlässig, wer *verloren teilnahm*. Die vorbefüllte „Gewinnquote" ist deshalb kein echter Quotient, sondern „eure sichtbaren Gewinne". Der Nenner — an wie vielen die Firma teilnahm — kennt nur sie selbst. Ehrlich benennen, nicht als echte Quote verkaufen.

### 6.2 Die drei Provenance-Zustände (konsistent mit dem Hausprinzip)

| Zustand | Bedeutung | Wert |
|---|---|---|
| **Abgeleitet** | goVisor hat ihn aus öffentlichen Daten, Nutzer nie angefasst | „aus öffentlichen Daten, bitte prüfen" |
| **Bestätigt** | Nutzer hat „ja, stimmt" gesagt | jetzt erklärt und belastbar |
| **Korrigiert / ergänzt** | Nutzer hat widersprochen oder hinzugefügt | **die wertvollste Kategorie** — bringt goVisor etwas bei, das es nicht wusste |

Vorbefüllte Einträge tragen sichtbar den Zustand „abgeleitet" — nie als Fakt dargestellt, den der Nutzer nie angefasst hat.

---

## 7. Der Datengraben — warum das Feature strategisch ist

Das Cockpit ist nicht nur Übersicht, es ist der **Kaltstart-Löser für die Ergebnisdaten** (aus #11):

- Der Nutzer pflegt seine Pipeline, **weil es ihm selbst hilft** (Überblick, Forecast) — unabhängig davon, ob es einen Ergebnisdaten-Pool gibt.
- Wenn ein Eintrag auf „gewonnen/verloren" springt, ist die Ergebnismeldung ein **Nebenprodukt** dieser Pflege, kein separater Akt.
- Wer seine echte Gewinnquote sehen will, **ergänzt seine Niederlagen und unterschwelligen Verträge** — genau die Daten, die in keiner öffentlichen Quelle stehen.
- Jede **Korrektur** eines vorbefüllten Eintrags („das war eine Tochterfirma") härtet obendrein den `entity_identity`-Graph.

Das ist das Glassdoor-Muster: Der Eigennutzen erzeugt den Beitrag, der Pool ist die Folge, nicht die Voraussetzung.

---

## 8. Datenmodell

Alles Nötige ist in #11 bereits definiert — dieses Ticket verdrahtet es im Frontend:

| Struktur | Quelle | Nutzung hier |
|---|---|---|
| Merkliste | #1 (vorhanden) | Bereich 1 |
| `user_outcomes` (`applied`, Ergebnis) | #11 (fertig) | Bereich 2 + Übergang zu 3 |
| `user_contracts` (inkl. unterschwellig) | #11 (fertig) | Bereich 3 (eingetragen) |
| Zuschlagsdaten + `entity_identity` | Gold-Layer (vorhanden) | Vorbefüllung Bereich 2/3 |
| `provenance`-Zustand je Eintrag | neu, klein | abgeleitet/bestätigt/korrigiert |

**Neu zu bauen:** die Vorbefüllungs-Logik (öffentliche Zuschläge einer Entität → Cockpit-Einträge) + der Provenance-Zustand je Eintrag + das Frontend der drei Bereiche.

---

## 9. Was das NICHT ist (Nicht-Ziele)

| Nicht | Warum |
|---|---|
| Kontaktverwaltung | Das ist CRM-Territorium, nicht Ausschreibungs-Status |
| Meeting-Notes / Gesprächshistorie | dito |
| Angebotssummen / Kalkulation | goVisor verwaltet den Status, nicht das Angebot |
| Aufgaben / Wiedervorlagen / Team-Zuweisung | Projektmanagement, nicht Lead-Status |
| Ersatz für Salesforce & Co. | goVisor ist die *Ausschreibungs*-Pipeline, nicht die *Vertriebs*-Pipeline |

Die Grenze in einem Satz: **goVisor verwaltet den Status der Ausschreibung, nicht die Vertriebsbeziehung.**

---

## 10. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Drei Bereiche (Beobachtet / Aktiv / Historie), einzeln zusammenklappbar |
| 2 | Merkliste bildet Bereich 1, fristgebunden (aus #16) |
| 3 | Pipeline (Bereich 2) mit schlanken, ausschreibungsbezogenen Status |
| 4 | Historie (Bereich 3) zeigt gewonnene & verlorene, ausgelaufene Verträge |
| 5 | Vorbefüllung aus öffentlichen Zuschlagsdaten beim ersten Login |
| 6 | Ehrliche Kante: unterschwellig fehlt, Niederlagen fehlen — benannt, nicht kaschiert |
| 7 | Drei Provenance-Zustände (abgeleitet/bestätigt/korrigiert), sichtbar |
| 8 | Übergang Beobachtet→Aktiv bei „ich bewerbe mich" |
| 9 | Übergang Aktiv→Historie bei Zuschlag, löst Ergebnismeldung (#11) aus |
| 10 | Grau-Logik: normal in Bereich 1, Aufforderung in Bereich 2 — einladend, nicht vorwurfsvoll |
| 11 | Keine CRM-Features (Nicht-Ziele eingehalten) |
| 12 | Ableitungen aus Historie: Stammkunden, verlorene Kunden, Rückeroberungs-Leads |

---

## 11. Edge Cases

| # | Case | Verhalten |
|---|---|---|
| 1 | Regionaler Anbieter, kaum Oberschwelliges | Vorbefüllung fast leer → Hinweis „ergänze deine Verträge", kein Fehler |
| 2 | Vorbefüllter Vertrag ist falsch (andere Firma) | Nutzer korrigiert → härtet Entity-Graph |
| 3 | Gemerkter Lead, Frist verstreicht ohne Bewerbung | Sanfte Frage „hast du dich beworben?" (Ergebnisdaten-Moment), dann Archiv — nicht nervig |
| 4 | Nutzer will Lead nur beobachten, nie Status pflegen | In Bereich 1 okay (kein Grau-Nörgeln); erst in Bereich 2 wird Status erwartet |
| 5 | Sehr lange Historie | Bereich 3 eingeklappt als Default, Paginierung/Filter |
| 6 | Gewinnquote irreführend (nur Gewinne sichtbar) | Als „sichtbare Gewinne" benannt, echte Quote erst mit Ergänzungen |

---

## 12. Abhängigkeiten & Reihenfolge

| Abhängigkeit | Status |
|---|---|
| Merkliste (#1) | ✅ vorhanden |
| `user_outcomes`, `user_contracts` (#11) | ✅ fertig |
| Fristen (#16) | ✅ für Bereich 1 |
| Vorbefüllungs-Logik | neu, dieses Ticket |
| Provenance-Zustand je Eintrag | neu, klein |

**Bau-Reihenfolge:** (1) drei Bereiche als Frontend über vorhandene Daten, (2) Vorbefüllung Bereich 2/3, (3) Provenance-Zustände + Bestätigen/Korrigieren, (4) Grau-Logik + Übergänge, (5) Ableitungen aus der Historie.

---

## 13. Zusammenfassung

Das Cockpit führt Merkliste, Pipeline und Historie zu einer Ansicht zusammen — drei zusammenklappbare Bereiche von Zukunft (beobachtet) über Gegenwart (aktiv) zu Vergangenheit (Historie). Der entscheidende Zug ist die **Vorbefüllung aus öffentlichen Daten**: Beim ersten Login sieht der Nutzer seine eigene Marktgeschichte, bestätigt und ergänzt sie — und liefert goVisor dabei genau die Daten (Niederlagen, unterschwellige Verträge, Entity-Korrekturen), die in keiner öffentlichen Quelle stehen. Es ist Lead-Management als Arbeitswerkzeug und Kaltstart-Löser für den Ergebnisdaten-Graben in einem — ohne je ein CRM zu werden.
