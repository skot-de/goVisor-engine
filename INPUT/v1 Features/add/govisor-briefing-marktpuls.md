# Briefing: Marktpuls — Saisonalität und aktuelle Marktlage

**Produkt:** goVisor
**Version:** 1.0
**Status:** Bau-Briefing für Claude Code
**Erstellt:** 2026-08-13
**Typ:** Wiederverwendbares Anzeige-Element, nicht an eine Seite gebunden

---

## 1. Was gebaut wird

Ein eigenständiges Element, das die Marktlage öffentlicher Vergaben im DACH-Raum zeigt. Zwei Teile:

1. **Saisonalität** — durchschnittliche Zahl neu veröffentlichter Ausschreibungen je Kalendermonat
   über mehrere Jahre. Beantwortet: Wann wird ausgeschrieben, gibt es ein Sommerloch?
2. **Aktuelle Lage** — wie viele Verfahren gerade laufen, mit Aufschlüsselung nach Branche.

**Einbauort noch offen.** Das Element wird als in sich geschlossene Komponente gebaut und später
platziert (Landingpage, Blog, Strategie-Bereich). Es darf keine Annahmen über seine Umgebung machen.

**Warum das wichtig ist:** Es ist einer der wenigen Inhalte, die goVisor als **Datenquelle** statt als
Anbieter positionieren — der Weg, über den man in KI-Suchen und fremden Artikeln zitiert wird.

---

## 2. Datengrundlage

Alles aus dem vorhandenen Gold Layer. Keine neuen Quellen.

| Element | Quelle | Bemerkung |
|---|---|---|
| Veröffentlichungsdatum | Bekanntmachung | Basis der Zeitreihe |
| Notice-Typ | Bekanntmachungsart | Ausschreibung / Zuschlag / Aufhebung |
| Angebotsfrist | `deadline` (#16) | bestimmt, ob ein Verfahren „läuft" |
| CPV | Bekanntmachung | Branchenaufschlüsselung |
| Land | DE / AT / CH | Filter |

### 2.1 Abzugrenzen

| Kategorie | Definition |
|---|---|
| **Ausschreibung** | Verfahren mit Angebotsfrist, auf das geboten werden kann |
| **Zuschlag** | Vergabebekanntmachung, Auftrag erteilt |
| **Aufhebung** | Verfahren beendet ohne Zuschlag |

**Nicht als Ausschreibung zählen:** Vorinformationen ohne Frist, Korrekturbekanntmachungen zu einem
bereits gezählten Verfahren. Sonst wird doppelt gezählt.

**Zähleinheit ist das Verfahren, nicht die Bekanntmachung.** Ein Verfahren mit Korrektur und drei
Losbekanntmachungen ist **ein** Verfahren. Distinkte `notice_id`-Gruppierung nötig.

---

## 3. Teil 1 — Saisonalität (Hauptaussage)

### 3.1 Berechnung

Durchschnittliche Zahl **neu veröffentlichter Ausschreibungen** je Kalendermonat, gemittelt über die
letzten **5 vollständigen Jahre**.

```
je Monat m (1..12):
  wert(m) = Ø über Jahre y in [aktuelles_Jahr-5 .. aktuelles_Jahr-1]:
              COUNT(DISTINCT verfahren
                    WHERE veröffentlichungsmonat = m
                      AND jahr = y
                      AND typ = 'Ausschreibung')
```

Zusätzlich je Monat die **Abweichung vom Jahresmittel** in Prozent — das ist die eigentliche Aussage.

### 3.2 Was das Ergebnis beantworten muss

Die Frage lautet: **Gibt es ein Sommerloch?**

Das Ergebnis ist **offen**. Beide Ausgänge sind gute Inhalte:

| Befund | Aussage |
|---|---|
| August liegt deutlich über dem Mittel | „Der August ist der stärkste Monat — Budgets müssen bis Jahresende raus." |
| August liegt im Mittel oder darunter | „Das Sommerloch ist ein Mythos" bzw. „Es gibt es tatsächlich" |

**Wichtig:** Das Ergebnis wird **nicht vorher festgelegt**. Der Text zur Grafik wird aus den
berechneten Werten erzeugt, nicht andersherum. Wenn die Daten keine Auffälligkeit zeigen, ist die
ehrliche Aussage „Die Verteilung ist über das Jahr gleichmäßiger als vermutet."

### 3.3 Darstellung

- Balkendiagramm, 12 Monate
- Jahresmittel als horizontale Linie
- Monate über dem Mittel hervorgehoben
- Achsenbeschriftung mit absoluten Zahlen
- Unter der Grafik: berechneter Ein-Satz-Befund

### 3.4 Aufschlüsselung

Umschaltbar, ohne Neuladen:

| Dimension | Werte |
|---|---|
| Land | DACH gesamt (Standard) · DE · AT · CH |
| Branche | alle (Standard) · Bau · IT · Beratung · Medizin · Sicherheit · Energie |

**Mindestfallzahl je Kombination: 200 Verfahren über den Betrachtungszeitraum.** Darunter wird die
Kombination nicht angeboten (Auswahl ausgegraut, Hinweis „zu wenige Verfahren").

---

## 4. Teil 2 — Aktuelle Lage

### 4.1 Berechnung

```
laufende Ausschreibungen = COUNT(DISTINCT verfahren
                                 WHERE typ = 'Ausschreibung'
                                   AND angebotsfrist >= heute)
```

Dazu:
- Zuschläge der letzten 30 Tage
- Aufhebungen der letzten 30 Tage
- Aufschlüsselung der laufenden Ausschreibungen nach Branche (Top 6 + „übrige")

### 4.2 Darstellung

Eine Kennzahlenzeile plus eine kurze Branchenliste. **Kein Zeitverlaufsdiagramm** — siehe §6.

### 4.3 Aktualität

| Anforderung | Wert |
|---|---|
| Aktualisierung | täglich, nachts |
| Sichtbarer Stand | „Stand: 13.08.2026" — immer anzeigen |
| Bei ausgefallener Aktualisierung | letzten erfolgreichen Stand zeigen, Datum entsprechend; **niemals stillschweigend alte Zahlen als aktuell ausgeben** |

---

## 5. Technische Umsetzung

| Anforderung | Vorgabe |
|---|---|
| Vorberechnung | Beide Teile werden als **Materialized View** oder Aggregattabelle vorberechnet, nicht live gegen den Gold Layer abgefragt |
| Aktualisierung | Saisonalität monatlich, aktuelle Lage täglich |
| Auslieferung | statisches JSON, keine Datenbankabfrage im Seitenaufruf |
| Ladeverhalten | Element rendert vollständig ohne JavaScript-Nachladen; Umschalter arbeitet auf dem bereits geladenen JSON |
| Größe | JSON unter 50 KB — nur aggregierte Werte, keine Einzelverfahren |
| Barrierefreiheit | Diagrammwerte zusätzlich als Tabelle verfügbar (auf-/zuklappbar) |

---

## 6. Was ausdrücklich NICHT gebaut wird

| Nicht | Grund |
|---|---|
| **Live-Zeitverlaufskurve der letzten Wochen** | Zeigt vor allem die Befüllung des eigenen Systems, nicht den Markt. Eine Kurve, die von 2.000 auf 10.000 springt, ist ein Ingest-Artefakt und kein Marktsignal — sie würde bei genauem Hinsehen gegen uns arbeiten |
| Echtzeit-Aktualisierung | Ein stehengebliebenes Diagramm wirkt schlechter als ein tagesaktuelles mit Datum |
| Prognosen („im Herbst werden X Verfahren erwartet") | Nicht belegbar |
| Einzelne Verfahren im Element | Das ist Aufgabe der Lead-Liste |
| Vergleich mit Wettbewerbern | Nicht Zweck dieses Elements |

---

## 7. Textbausteine

Die Grafik erzeugt ihren Begleittext **aus den berechneten Werten**. Muster:

| Fall | Text |
|---|---|
| Ein Monat > 25 % über Mittel | „Der stärkste Monat ist {Monat} mit {N} Ausschreibungen — {X} % über dem Jahresmittel." |
| Ein Monat > 25 % unter Mittel | „Der schwächste Monat ist {Monat} mit {N} — {X} % unter dem Jahresmittel." |
| Keine Abweichung über 25 % | „Die Ausschreibungen verteilen sich über das Jahr gleichmäßiger als oft angenommen." |
| Aktuelle Lage | „Aktuell laufen {N} Ausschreibungen im DACH-Raum, auf die geboten werden kann." |

Immer mit Basisangabe: Zeitraum, Zahl der ausgewerteten Verfahren, Stand.

---

## 8. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Element ist in sich geschlossen und ohne Annahmen über die Umgebung einbaubar |
| 2 | Zähleinheit ist das Verfahren, nicht die Bekanntmachung — keine Doppelzählung durch Korrekturen oder Lose |
| 3 | Vorinformationen ohne Frist zählen nicht als Ausschreibung |
| 4 | Saisonalität über 5 vollständige Jahre, mit Jahresmittel-Linie |
| 5 | Begleittext wird aus den Werten erzeugt, nicht vorformuliert |
| 6 | Umschaltung nach Land und Branche, Mindestfallzahl 200 |
| 7 | Aktuelle Lage mit sichtbarem Stand-Datum |
| 8 | Bei ausgefallener Aktualisierung: alter Stand mit korrektem Datum, nie als aktuell ausgegeben |
| 9 | Vorberechnet, Auslieferung als statisches JSON unter 50 KB |
| 10 | Diagrammwerte zusätzlich als Tabelle verfügbar |
| 11 | Keine Live-Zeitverlaufskurve, keine Prognosen |

---

## 9. Offene Punkte

| # | Punkt | Zu klären |
|---|---|---|
| 1 | Einbauort | Landingpage, Blog oder Strategie — nach Fertigstellung entscheiden |
| 2 | Ergebnis der Saisonalitätsberechnung | Erst nach dem ersten Lauf bekannt. Die Aussage richtet sich danach, nicht umgekehrt |
| 3 | Ob 5 Jahre der richtige Zeitraum sind | Prüfen, ob frühere Jahre durch Datenlücken oder Regeländerungen verzerren |
| 4 | Branchenschnitt | CPV-Bündelung mit der Bündelung aus der Lead-Liste abgleichen, damit Zahlen konsistent sind |
